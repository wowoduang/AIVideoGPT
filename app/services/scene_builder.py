from __future__ import annotations

import os
from typing import Dict, List, Optional

from loguru import logger

try:
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import ContentDetector
    _SCENEDETECT_AVAILABLE = True
except Exception:
    _SCENEDETECT_AVAILABLE = False


_FORCE_SPLIT_GAP = 4.0
_MICRO_SCENE_THRESHOLD = 2.0
_KEYFRAME_CANDIDATES = 4


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