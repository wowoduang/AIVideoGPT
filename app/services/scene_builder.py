from __future__ import annotations

import os
import subprocess
from typing import Dict, List, Optional

from loguru import logger
from app.utils import ffmpeg_utils, utils

try:
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import ContentDetector
    _SCENEDETECT_AVAILABLE = True
except Exception:
    _SCENEDETECT_AVAILABLE = False


_FORCE_SPLIT_GAP = 4.0
_MICRO_SCENE_THRESHOLD = 2.0
_KEYFRAME_CANDIDATES = 4
_HEVC_CODEC_NAMES = {"hevc", "h265", "h.265"}
_SCENE_PROXY_MAX_WIDTH = 960
_SCENE_PROXY_FPS = 12


def _probe_primary_video_codec(video_path: str) -> str:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return str(completed.stdout or "").strip().lower()
    except Exception as exc:
        logger.debug(f"scene_builder: failed to probe video codec for {video_path}: {exc}")
        return ""


def _build_scene_proxy_path(video_path: str) -> str:
    cache_key = utils.md5(f"{video_path}:{os.path.getmtime(video_path)}")
    return os.path.join(utils.temp_dir("scene_proxy"), f"{cache_key}_scene_proxy.mp4")


def _remove_file_if_exists(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def _summarize_process_error(stderr: str, max_lines: int = 4, max_chars: int = 400) -> str:
    lines = [line.strip() for line in str(stderr or "").splitlines() if line.strip()]
    if not lines:
        return "unknown error"
    summary = " | ".join(lines[-max_lines:])
    if len(summary) > max_chars:
        summary = summary[-max_chars:]
    return summary


def _ensure_scene_detect_proxy(video_path: str) -> str:
    proxy_path = _build_scene_proxy_path(video_path)
    if os.path.isfile(proxy_path) and os.path.getsize(proxy_path) > 0:
        return proxy_path

    _remove_file_if_exists(proxy_path)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *ffmpeg_utils.get_resilient_decode_input_args(
            ignore_decode_errors=True,
            discard_corrupt=True,
        ),
        "-i",
        video_path,
        "-an",
        "-vf",
        f"scale=w='min({_SCENE_PROXY_MAX_WIDTH},iw)':h=-2:force_original_aspect_ratio=decrease,fps={_SCENE_PROXY_FPS}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "32",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        proxy_path,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode == 0 and os.path.isfile(proxy_path) and os.path.getsize(proxy_path) > 0:
        return proxy_path

    _remove_file_if_exists(proxy_path)
    logger.warning(
        "scene_builder: failed to generate H.264 scene proxy for {}: {}",
        os.path.basename(video_path),
        _summarize_process_error(completed.stderr),
    )
    return ""


def _prepare_scene_detection_input(video_path: str) -> str:
    codec_name = _probe_primary_video_codec(video_path)
    if codec_name not in _HEVC_CODEC_NAMES:
        return video_path

    proxy_path = _ensure_scene_detect_proxy(video_path)
    if proxy_path:
        logger.info(
            "scene_builder: using generated H.264 proxy for HEVC source {}",
            os.path.basename(video_path),
        )
        return proxy_path

    logger.warning("scene_builder: failed to prepare H.264 proxy for HEVC source, skipping visual detection")
    return ""


def _run_scene_detection(scene_input_path: str, threshold: float, min_scene_len: float) -> List:
    video = None
    try:
        video = open_video(scene_input_path)
        fps = float(getattr(video, "frame_rate", 24.0) or 24.0)
        detector_min_scene_len = max(int(round(max(float(min_scene_len), 0.1) * fps)), 1)
        manager = SceneManager()
        manager.add_detector(
            ContentDetector(
                threshold=threshold,
                min_scene_len=detector_min_scene_len,
            )
        )
        manager.detect_scenes(video)
        return manager.get_scene_list()
    finally:
        close_fn = getattr(video, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass


def _detect_scenes_from_video_resilient(
    video_path: str,
    subtitle_segments: List[Dict],
    *,
    threshold: float,
    min_scene_len: float,
    force_split_gap: float,
    micro_threshold: float,
    min_scene_duration: float,
) -> List[Dict]:
    if not _SCENEDETECT_AVAILABLE:
        logger.warning("PySceneDetect unavailable, skipping visual scene detection")
        return []

    scene_input_path = _prepare_scene_detection_input(video_path)
    if not scene_input_path:
        return []

    try:
        raw_scenes = _run_scene_detection(
            scene_input_path=scene_input_path,
            threshold=threshold,
            min_scene_len=min_scene_len,
        )
    except Exception as exc:
        if scene_input_path == video_path:
            proxy_path = _ensure_scene_detect_proxy(video_path)
            if proxy_path:
                try:
                    raw_scenes = _run_scene_detection(
                        scene_input_path=proxy_path,
                        threshold=threshold,
                        min_scene_len=min_scene_len,
                    )
                    logger.warning("scene_builder: scene detection failed on source video, recovered with H.264 proxy")
                except Exception as proxy_exc:
                    logger.warning(
                        f"scene_builder: scene detection failed on source and proxy videos, falling back to subtitles: {proxy_exc}"
                    )
                    return []
            else:
                logger.warning(f"scene_builder: scene detection failed, falling back to subtitles: {exc}")
                return []
        else:
            logger.warning(
                f"scene_builder: scene detection failed on proxy video, falling back to subtitles: {exc}"
            )
            return []

    if not raw_scenes:
        return []

    boundaries: List[float] = []
    for start_tc, end_tc in raw_scenes:
        boundaries.append(round(start_tc.get_seconds(), 3))
        boundaries.append(round(end_tc.get_seconds(), 3))

    boundaries = _inject_subtitle_gap_boundaries(
        boundaries=boundaries,
        subtitle_segments=subtitle_segments,
        force_split_gap=force_split_gap,
    )

    scenes = _boundaries_to_scenes(boundaries)
    scenes = _merge_micro_scenes(scenes, micro_threshold)
    scenes = _postprocess_scenes(
        scenes=scenes,
        min_scene_duration=min_scene_duration,
    )
    return scenes


def build_scenes(
    subtitle_segments: Optional[List[Dict]] = None,
    video_path: str = "",
    keyframe_files: Optional[List[str]] = None,
    *,
    mode: str = "balanced",
    preset: Optional[Dict] = None,
    scene_threshold: Optional[float] = None,
    min_scene_len: Optional[float] = None,
    max_scene_duration: Optional[float] = None,
    max_gap: Optional[float] = None,
    force_split_gap: Optional[float] = None,
    merge_micro: bool = True,
    micro_threshold: Optional[float] = None,
    min_scene_duration: Optional[float] = None,
    fallback_interval: float = 3.0,
) -> List[Dict]:
    preset = dict(preset or {})

    scene_threshold = float(scene_threshold or preset.get("scene_threshold", 27.0))
    min_scene_len = float(min_scene_len or preset.get("min_scene_len", 2.0))
    max_scene_duration = float(max_scene_duration or preset.get("max_scene_duration", 12.0))
    max_gap = float(max_gap or preset.get("max_gap", 1.2))
    force_split_gap = float(force_split_gap or preset.get("force_split_gap", _FORCE_SPLIT_GAP))
    micro_threshold = float(micro_threshold or preset.get("micro_threshold", _MICRO_SCENE_THRESHOLD))
    min_scene_duration = float(min_scene_duration or preset.get("min_scene_duration", 1.5))

    if video_path and os.path.isfile(video_path):
        scenes = detect_scenes_from_video(
            video_path=video_path,
            subtitle_segments=subtitle_segments or [],
            threshold=scene_threshold,
            min_scene_len=min_scene_len,
            force_split_gap=force_split_gap,
            micro_threshold=micro_threshold,
            min_scene_duration=min_scene_duration,
        )
        if scenes:
            logger.info(f"build_scenes: 使用视频场景检测，得到 {len(scenes)} 个 scenes")
            return scenes

    if subtitle_segments:
        scenes = build_scenes_from_subtitles(
            subtitle_segments=subtitle_segments,
            max_scene_duration=max_scene_duration,
            max_gap=max_gap,
            min_scene_duration=min_scene_duration,
            force_split_gap=force_split_gap,
            merge_micro=merge_micro,
            micro_threshold=micro_threshold,
        )
        logger.info(f"build_scenes: 回退到字幕切分，得到 {len(scenes)} 个 scenes")
        return scenes

    if keyframe_files:
        scenes = build_fallback_scenes_from_keyframes(
            keyframe_files=keyframe_files,
            fallback_interval=fallback_interval,
        )
        logger.info(f"build_scenes: 使用关键帧回退，得到 {len(scenes)} 个 scenes")
        return scenes

    logger.warning("build_scenes 未收到可用输入，返回空场景列表")
    return []


def detect_scenes_from_video(
    video_path: str,
    subtitle_segments: List[Dict],
    *,
    threshold: float = 27.0,
    min_scene_len: float = 2.0,
    force_split_gap: float = _FORCE_SPLIT_GAP,
    micro_threshold: float = _MICRO_SCENE_THRESHOLD,
    min_scene_duration: float = 1.5,
) -> List[Dict]:
    return _detect_scenes_from_video_resilient(
        video_path=video_path,
        subtitle_segments=subtitle_segments,
        threshold=threshold,
        min_scene_len=min_scene_len,
        force_split_gap=force_split_gap,
        micro_threshold=micro_threshold,
        min_scene_duration=min_scene_duration,
    )

    if not _SCENEDETECT_AVAILABLE:
        logger.warning("PySceneDetect 不可用，跳过视频场景检测")
        return []

    try:
        video = open_video(video_path)
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=threshold))
        manager.detect_scenes(video)
        raw_scenes = manager.get_scene_list()
    except Exception as exc:
        logger.warning(f"视频场景检测失败，回退字幕切分: {exc}")
        return []

    if not raw_scenes:
        return []

    boundaries: List[float] = []
    for start_tc, end_tc in raw_scenes:
        boundaries.append(round(start_tc.get_seconds(), 3))
        boundaries.append(round(end_tc.get_seconds(), 3))

    boundaries = _inject_subtitle_gap_boundaries(
        boundaries=boundaries,
        subtitle_segments=subtitle_segments,
        force_split_gap=force_split_gap,
    )

    scenes = _boundaries_to_scenes(boundaries)
    scenes = _merge_micro_scenes(scenes, micro_threshold)
    scenes = _postprocess_scenes(
        scenes=scenes,
        min_scene_duration=min_scene_duration,
    )
    return scenes


def build_scenes_from_subtitles(
    subtitle_segments: List[Dict],
    max_scene_duration: float = 9.0,
    max_gap: float = 1.2,
    min_scene_duration: float = 1.0,
    force_split_gap: float = _FORCE_SPLIT_GAP,
    merge_micro: bool = True,
    micro_threshold: float = _MICRO_SCENE_THRESHOLD,
) -> List[Dict]:
    if not subtitle_segments:
        return []

    scenes: List[Dict] = []
    current: Dict = {
        "scene_id": "scene_001",
        "start": float(subtitle_segments[0]["start"]),
        "end": float(subtitle_segments[0]["end"]),
        "subtitle_ids": [subtitle_segments[0].get("seg_id", "sub_001")],
        "subtitle_texts": [subtitle_segments[0].get("text", "")],
    }

    for seg in subtitle_segments[1:]:
        seg_start = float(seg["start"])
        seg_end = float(seg["end"])
        gap = seg_start - current["end"]
        next_duration = seg_end - current["start"]

        should_split = (
            gap > force_split_gap
            or gap > max_gap
            or next_duration > max_scene_duration
        )

        if should_split:
            scenes.append(current)
            current = {
                "scene_id": f"scene_{len(scenes)+1:03d}",
                "start": seg_start,
                "end": seg_end,
                "subtitle_ids": [seg.get("seg_id", f"sub_{len(scenes)+1:03d}")],
                "subtitle_texts": [seg.get("text", "")],
            }
        else:
            current["end"] = max(current["end"], seg_end)
            current["subtitle_ids"].append(seg.get("seg_id", ""))
            current["subtitle_texts"].append(seg.get("text", ""))

    scenes.append(current)

    if merge_micro and len(scenes) > 1:
        scenes = _merge_micro_scenes(scenes, micro_threshold)

    scenes = _postprocess_scenes(scenes, min_scene_duration=min_scene_duration)
    logger.info(f"场景构建完成: {len(subtitle_segments)} 条字幕 -> {len(scenes)} 个 scene")
    return scenes


def _inject_subtitle_gap_boundaries(
    boundaries: List[float],
    subtitle_segments: List[Dict],
    force_split_gap: float,
) -> List[float]:
    pts = set(round(b, 3) for b in boundaries if b >= 0)

    for prev_seg, next_seg in zip(subtitle_segments[:-1], subtitle_segments[1:]):
        prev_end = round(float(prev_seg["end"]), 3)
        next_start = round(float(next_seg["start"]), 3)
        gap = next_start - prev_end
        if gap > force_split_gap:
            pts.add(prev_end)
            pts.add(next_start)

    ordered = sorted(pts)
    deduped = []
    for b in ordered:
        if not deduped or abs(b - deduped[-1]) > 1e-3:
            deduped.append(b)
    return deduped


def _boundaries_to_scenes(boundaries: List[float]) -> List[Dict]:
    if len(boundaries) < 2:
        return []

    scenes: List[Dict] = []
    for idx in range(len(boundaries) - 1):
        start = float(boundaries[idx])
        end = float(boundaries[idx + 1])
        if end <= start:
            continue
        scenes.append({
            "scene_id": f"scene_{idx+1:03d}",
            "start": round(start, 3),
            "end": round(end, 3),
            "subtitle_ids": [],
            "subtitle_texts": [],
        })
    return scenes


def _merge_micro_scenes(scenes: List[Dict], micro_threshold: float) -> List[Dict]:
    if len(scenes) <= 1:
        return scenes

    merged: List[Dict] = [dict(scenes[0])]
    for scene in scenes[1:]:
        duration = float(scene["end"]) - float(scene["start"])
        if duration < micro_threshold:
            prev = merged[-1]
            prev["end"] = max(float(prev["end"]), float(scene["end"]))
            prev.setdefault("subtitle_ids", []).extend(scene.get("subtitle_ids", []))
            prev.setdefault("subtitle_texts", []).extend(scene.get("subtitle_texts", []))
        else:
            merged.append(dict(scene))
    return merged


def _postprocess_scenes(
    scenes: List[Dict],
    min_scene_duration: float = 1.0,
) -> List[Dict]:
    out: List[Dict] = []
    for idx, scene in enumerate(scenes, start=1):
        cloned = dict(scene)
        cloned["scene_id"] = f"scene_{idx:03d}"
        if float(cloned["end"]) - float(cloned["start"]) < min_scene_duration:
            cloned["end"] = round(float(cloned["start"]) + min_scene_duration, 3)

        cloned["duration"] = round(float(cloned["end"]) - float(cloned["start"]), 3)
        cloned["subtitle_text"] = " ".join(cloned.get("subtitle_texts", [])).strip()
        cloned["keyframe_candidates"] = _compute_keyframe_candidates(
            float(cloned["start"]),
            float(cloned["end"]),
        )
        out.append(cloned)
    return out


def _compute_keyframe_candidates(
    start: float,
    end: float,
    max_candidates: int = _KEYFRAME_CANDIDATES,
) -> List[float]:
    duration = end - start
    if duration <= 0:
        return [round(start, 3)]

    count = min(max_candidates, max(2, int(duration / 2.0) + 1))
    if count <= 1:
        return [round((start + end) / 2.0, 3)]

    step = duration / (count - 1)
    return [round(start + i * step, 3) for i in range(count)]


def build_fallback_scenes_from_keyframes(
    keyframe_files: List[str],
    fallback_interval: float = 3.0,
) -> List[Dict]:
    scenes: List[Dict] = []
    for idx, frame in enumerate(keyframe_files or [], start=1):
        start = (idx - 1) * fallback_interval
        end = start + fallback_interval
        scenes.append(
            {
                "scene_id": f"scene_{idx:03d}",
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(fallback_interval, 3),
                "subtitle_ids": [],
                "subtitle_text": "",
                "subtitle_texts": [],
                "fallback_frame": frame,
                "keyframe_candidates": [round((start + end) / 2.0, 3)],
            }
        )
    return scenes


def build_video_boundary_candidates(
    video_path: str,
    subtitle_segments: Optional[List[Dict]] = None,
    *,
    threshold: float = 27.0,
    min_scene_len: float = 2.0,
    force_split_gap: float = _FORCE_SPLIT_GAP,
    micro_threshold: float = _MICRO_SCENE_THRESHOLD,
    min_scene_duration: float = 1.5,
    merge_window_sec: float = 2.0,
) -> List[Dict]:
    """Build weighted video boundary candidates for subtitle/story fusion.

    Returns items like:
    {time, source, type, score, reason, reasons}
    """
    subtitle_segments = subtitle_segments or []
    scenes = detect_scenes_from_video(
        video_path=video_path,
        subtitle_segments=subtitle_segments,
        threshold=threshold,
        min_scene_len=min_scene_len,
        force_split_gap=force_split_gap,
        micro_threshold=micro_threshold,
        min_scene_duration=min_scene_duration,
    )
    if not scenes:
        return []

    gap_lookup: Dict[float, float] = {}
    for prev_seg, next_seg in zip(subtitle_segments[:-1], subtitle_segments[1:]):
        prev_end = round(float(prev_seg.get("end", 0.0) or 0.0), 3)
        next_start = round(float(next_seg.get("start", prev_end) or prev_end), 3)
        gap_lookup[prev_end] = max(gap_lookup.get(prev_end, 0.0), next_start - prev_end)

    raw: List[Dict] = []
    for prev_scene, next_scene in zip(scenes[:-1], scenes[1:]):
        boundary_time = round(float(prev_scene.get("end", 0.0) or 0.0), 3)
        prev_duration = float(prev_scene.get("duration", 0.0) or 0.0)
        next_duration = float(next_scene.get("duration", 0.0) or 0.0)
        score = 0.68
        reasons = ["视觉场景切换候选"]
        gap = gap_lookup.get(boundary_time, 0.0)
        if gap >= force_split_gap:
            score += 0.14
            reasons.append("长静默后发生画面变化")
        if max(prev_duration, next_duration) >= 8.0:
            score += 0.06
            reasons.append("边界前后存在较完整场景")
        raw.append(
            {
                "time": boundary_time,
                "source": "video",
                "sources": ["video"],
                "type": "scene_cut_candidate",
                "score": min(round(score, 3), 0.92),
                "reason": reasons[0],
                "reasons": reasons,
            }
        )

    # merge close-by visual candidates locally to reduce jitter
    raw.sort(key=lambda x: x["time"])
    merged: List[Dict] = []
    for item in raw:
        if merged and abs(float(item["time"]) - float(merged[-1]["time"])) <= merge_window_sec:
            prev = merged[-1]
            prev["time"] = round((float(prev["time"]) + float(item["time"])) / 2.0, 3)
            prev["score"] = max(float(prev.get("score", 0.5)), float(item.get("score", 0.5)))
            prev["reasons"] = list(dict.fromkeys((prev.get("reasons") or []) + (item.get("reasons") or [])))
            prev["reason"] = prev["reasons"][0]
        else:
            merged.append(dict(item))
    return merged
