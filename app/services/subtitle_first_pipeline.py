from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.services.evidence_fuser import fuse_scene_evidence
from app.services.generate_narration_script_clean import generate_narration_from_scene_evidence
from app.services.plot_chunker import build_plot_chunks_from_subtitles
from app.services.scene_builder import build_video_boundary_candidates, detect_scenes_from_video
from app.services.plot_understanding_clean import (
    add_local_understanding,
    build_full_subtitle_understanding,
    build_global_summary,
    plan_story_highlights,
)
from app.services.preflight_check import PreflightError, validate_script_items
from app.services.representative_frames import extract_representative_frames_for_scenes
from app.services.script_fallback import ensure_script_shape
from app.services.llm_config import get_text_llm_config
from app.services.story_boundary_aligner import align_story_boundaries, collect_candidate_boundaries
from app.services.story_validator_clean import validate_story_segments
from app.services.subtitle_pipeline import build_subtitle_segments
from app.utils import utils


_TAIL_PREVIEW_CUES = {
    "下集预告": 6.0,
    "下期预告": 6.0,
    "下回预告": 6.0,
    "次集预告": 6.0,
    "下周预告": 5.5,
    "精彩预告": 5.0,
    "未完待续": 4.8,
    "敬请期待": 4.2,
    "欲知后事如何": 5.2,
    "下一集": 2.4,
    "下集": 1.6,
    "下期": 1.6,
    "下回": 1.6,
    "预告": 2.4,
}
_TAIL_CREDITS_CUES = {
    "片尾曲": 6.0,
    "片尾": 3.5,
    "主题曲": 2.6,
    "职员表": 5.0,
    "演职员": 5.0,
    "演职员表": 5.4,
    "领衔主演": 2.4,
    "主演": 1.5,
    "特别出演": 2.2,
    "友情出演": 2.2,
    "联合主演": 2.2,
    "出品人": 1.8,
    "总制片人": 2.0,
    "制片人": 1.6,
    "总监制": 2.0,
    "监制": 1.4,
    "导演": 1.4,
    "编剧": 1.4,
    "摄影指导": 1.6,
    "美术指导": 1.6,
    "后期制作": 1.6,
    "鸣谢": 2.0,
}
_TAIL_BRACKET_RE = re.compile(
    r"^[\[\(【（]?(?:片尾曲|片尾|下集预告|下期预告|下回预告|精彩预告|预告)[\]\)】）]?$",
    re.IGNORECASE,
)


_PROLOGUE_CUE_ONLY_RE = re.compile(
    r"^\s*[\[\(]?\s*(?:bgm|music|applause|laughter|laughing|sigh|crying|phone ringing|ringtone|"
    r"音乐|配乐|掌声|笑声|哭声|叹气|电话铃声)\s*[\]\)]?\s*$",
    re.IGNORECASE,
)


_SCENE_ALIGN_NARRATION_WINDOW_SECONDS = 1.2
_SCENE_ALIGN_RAW_VOICE_WINDOW_SECONDS = 4.0
_HIGHLIGHT_SNAP_WINDOW_DEFAULT_SECONDS = 1.5
_HIGHLIGHT_SNAP_WINDOW_HIGH_SECONDS = 2.5
_HIGHLIGHT_SNAP_WINDOW_RAW_VOICE_SECONDS = 4.0


def run_subtitle_first_pipeline(
    video_path: str,
    subtitle_path: str = "",
    *,
    text_api_key: str = "",
    text_base_url: str = "",
    text_model: str = "",
    style: str = "general",
    keyframe_dir: str = "",
    output_script_path: str = "",
    generation_mode: str = "balanced",
    visual_mode: str = "",
    scene_overrides: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    asr_backend: str = "",
    regenerate_subtitle: bool = False,
) -> Dict[str, Any]:
    def _progress(pct: int, msg: str = "") -> None:
        if progress_callback:
            try:
                progress_callback(pct, msg)
            except Exception:
                pass

    try:
        return _run(
            video_path=video_path,
            subtitle_path=subtitle_path,
            text_api_key=text_api_key,
            text_base_url=text_base_url,
            text_model=text_model,
            style=style,
            output_script_path=output_script_path,
            generation_mode=generation_mode,
            visual_mode=visual_mode,
            scene_overrides=scene_overrides or {},
            progress=_progress,
            asr_backend=asr_backend,
            regenerate_subtitle=regenerate_subtitle,
        )
    except Exception as exc:
        logger.exception("影视解说主链执行失败: {}", exc)
        return {
            "script_items": [],
            "script_path": "",
            "success": False,
            "error": str(exc),
        }


def _resolve_target_minutes(mode: str, overrides: Dict[str, Any]) -> int:
    if overrides.get("target_duration_minutes"):
        try:
            return max(int(overrides["target_duration_minutes"]), 1)
        except Exception:
            pass
    default_map = {"fast": 5, "balanced": 8, "quality": 10}
    return default_map.get(mode, 8)


def _resolve_visual_mode(visual_mode: str) -> str:
    if visual_mode in {"off", "auto", "boost"}:
        return visual_mode
    return "auto"


def _ensure_llm_ready(api_key: str, base_url: str, model: str) -> tuple:
    """
    确保 LLM 配置就绪，如果参数为空则从 config.app 读取
    
    Returns:
        tuple: (api_key, base_url, model) - 确保都有值的配置
    """
    cfg = get_text_llm_config()
    
    # 优先使用传入的参数，如果为空则从配置读取
    final_api_key = str(api_key or "").strip() or cfg.get('api_key', '')
    final_model = str(model or "").strip() or cfg.get('model', '')
    final_base_url = str(base_url or "").strip() or cfg.get('base_url', '')
    
    # 检查是否仍缺少配置
    missing = []
    if not final_api_key:
        missing.append("text_api_key")
    if not final_model:
        missing.append("text_model")
    if missing:
        raise ValueError(f"字幕优先影视解说链需要完整的 LLM 配置，缺少: {', '.join(missing)}")
    
    return final_api_key, final_base_url, final_model


def _collect_scene_cut_points(video_path: str, segments: List[Dict], scene_overrides: Dict[str, Any]) -> List[float]:
    scenes = detect_scenes_from_video(
        video_path=video_path,
        subtitle_segments=segments or [],
        threshold=float(scene_overrides.get("scene_threshold", 27.0) or 27.0),
        min_scene_len=float(scene_overrides.get("min_scene_len", 2.0) or 2.0),
        force_split_gap=float(scene_overrides.get("force_split_gap", 4.0) or 4.0),
        micro_threshold=float(scene_overrides.get("micro_threshold", 2.0) or 2.0),
        min_scene_duration=float(scene_overrides.get("min_scene_duration", 1.5) or 1.5),
    )
    points = set()
    for scene in scenes or []:
        try:
            points.add(round(float(scene.get("start", 0.0) or 0.0), 3))
            points.add(round(float(scene.get("end", 0.0) or 0.0), 3))
        except Exception:
            continue
    return sorted(points)


def _snap_time_to_cut(target: float, cut_points: List[float], *, window: float, direction: str) -> tuple[float, float | None]:
    if not cut_points:
        return round(target, 3), None

    if direction == "backward":
        candidates = [p for p in cut_points if target - window <= p <= target]
        if not candidates:
            candidates = [p for p in cut_points if abs(p - target) <= window]
    elif direction == "forward":
        candidates = [p for p in cut_points if target <= p <= target + window]
        if not candidates:
            candidates = [p for p in cut_points if abs(p - target) <= window]
    else:
        candidates = [p for p in cut_points if abs(p - target) <= window]

    if not candidates:
        nearest = min(cut_points, key=lambda p: abs(p - target))
        return round(target, 3), round(abs(nearest - target), 3)

    snapped = min(candidates, key=lambda p: abs(p - target))
    return round(snapped, 3), round(abs(snapped - target), 3)


def _build_scene_intervals(cut_points: List[float]) -> List[tuple[float, float]]:
    ordered = sorted({round(float(x), 3) for x in (cut_points or [])})
    if len(ordered) < 2:
        return []
    intervals: List[tuple[float, float]] = []
    for idx in range(len(ordered) - 1):
        start = ordered[idx]
        end = ordered[idx + 1]
        if end > start:
            intervals.append((start, end))
    return intervals


def _align_range_to_scene_group(
    start: float,
    end: float,
    cut_points: List[float],
    *,
    lead_window: float,
    tail_window: float,
    hard_start_floor: float | None = None,
    hard_end_ceiling: float | None = None,
) -> Dict[str, Any]:
    def _apply_hard_bounds(result: Dict[str, Any]) -> Dict[str, Any]:
        cur = dict(result)
        floor = round(float(hard_start_floor or 0.0), 3) if hard_start_floor is not None else None
        ceiling = round(float(hard_end_ceiling or 0.0), 3) if hard_end_ceiling is not None else None
        cur["start"] = round(float(cur.get("start", semantic_start) or semantic_start), 3)
        cur["end"] = round(float(cur.get("end", semantic_end) or semantic_end), 3)
        if floor is not None:
            cur["start"] = round(max(cur["start"], floor), 3)
        if ceiling is not None:
            cur["end"] = round(min(cur["end"], ceiling), 3)
        if cur["end"] <= cur["start"]:
            fallback_end = semantic_end
            if ceiling is not None:
                fallback_end = min(fallback_end, ceiling)
            cur["end"] = round(max(cur["start"] + 0.5, fallback_end), 3)

        clipped_ranges = []
        for left, right in cur.get("scene_group_ranges") or []:
            clipped_left = round(float(left or 0.0), 3)
            clipped_right = round(float(right or clipped_left), 3)
            if floor is not None:
                clipped_left = round(max(clipped_left, floor), 3)
            if ceiling is not None:
                clipped_right = round(min(clipped_right, ceiling), 3)
            if clipped_right > clipped_left:
                clipped_ranges.append([clipped_left, clipped_right])

        cur["scene_group_ranges"] = clipped_ranges
        cur["scene_group_count"] = len(clipped_ranges)
        if cur.get("scene_group_mode") == "scene_group" and not clipped_ranges:
            cur["scene_group_mode"] = "cut_snap_fallback"
        return cur

    semantic_start = round(float(start or 0.0), 3)
    semantic_end = round(float(end or semantic_start), 3)
    if semantic_end <= semantic_start:
        semantic_end = round(semantic_start + 0.5, 3)

    intervals = _build_scene_intervals(cut_points)
    if not intervals:
        return _apply_hard_bounds({
            "start": semantic_start,
            "end": semantic_end,
            "scene_group_count": 0,
            "scene_group_ranges": [],
            "scene_group_mode": "semantic_keep",
        })

    target_left = semantic_start - max(float(lead_window or 0.0), 0.0)
    target_right = semantic_end + max(float(tail_window or 0.0), 0.0)
    overlapping = [
        (left, right)
        for left, right in intervals
        if _ranges_overlap(left, right, target_left, target_right, 0.0)
    ]
    if not overlapping:
        snapped_start, _ = _snap_time_to_cut(semantic_start, cut_points, window=max(lead_window, 2.0), direction="backward")
        snapped_end, _ = _snap_time_to_cut(semantic_end, cut_points, window=max(tail_window, 2.0), direction="forward")
        if snapped_end <= snapped_start:
            snapped_end = round(max(snapped_start + 0.5, semantic_end), 3)
        return _apply_hard_bounds({
            "start": snapped_start,
            "end": snapped_end,
            "scene_group_count": 0,
            "scene_group_ranges": [],
            "scene_group_mode": "cut_snap_fallback",
        })

    aligned_start = round(min(x[0] for x in overlapping), 3)
    aligned_end = round(max(x[1] for x in overlapping), 3)
    return _apply_hard_bounds({
        "start": aligned_start,
        "end": aligned_end,
        "scene_group_count": len(overlapping),
        "scene_group_ranges": [[round(left, 3), round(right, 3)] for left, right in overlapping],
        "scene_group_mode": "scene_group",
    })


def _align_script_items_to_scene_cuts(
    script_items: List[Dict],
    cut_points: List[float],
    *,
    narration_window: float = _SCENE_ALIGN_NARRATION_WINDOW_SECONDS,
    raw_voice_window: float = _SCENE_ALIGN_RAW_VOICE_WINDOW_SECONDS,
) -> List[Dict]:
    if not script_items:
        return []

    aligned: List[Dict] = []
    for item in script_items:
        cur = dict(item)
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)
        ost = int(cur.get("OST", 2) or 2)
        hard_start_floor = None
        hard_end_ceiling = None
        if cur.get("prologue_end") is not None and (
            cur.get("prologue_trimmed")
            or cur.get("prologue_original_before_prologue_end")
            or cur.get("before_prologue_end")
        ):
            hard_start_floor = float(cur.get("prologue_end", 0.0) or 0.0)
        if cur.get("story_end") is not None and (
            cur.get("story_end_trimmed")
            or cur.get("story_end_original_after_story_end")
            or cur.get("after_story_end")
        ):
            hard_end_ceiling = float(cur.get("story_end", 0.0) or 0.0)
        semantic_start = round(start, 3)
        semantic_end = round(end, 3)
        cur["semantic_start"] = semantic_start
        cur["semantic_end"] = semantic_end
        cur["semantic_timestamp"] = f"{utils.format_time(semantic_start)}-{utils.format_time(semantic_end)}"

        if ost == 1:
            grouped = _align_range_to_scene_group(
                start,
                end,
                cut_points,
                lead_window=raw_voice_window,
                tail_window=raw_voice_window,
                hard_start_floor=hard_start_floor,
                hard_end_ceiling=hard_end_ceiling,
            )
            snapped_start = float(grouped["start"])
            snapped_end = float(grouped["end"])
            start_dist = round(abs(snapped_start - semantic_start), 3)
            end_dist = round(abs(snapped_end - semantic_end), 3)
            cur["scene_aligned"] = True
            cur["scene_align_mode"] = "raw_voice_scene_group"
            cur["scene_align_distance"] = {"start": start_dist, "end": end_dist}
            cur["scene_group_count"] = grouped["scene_group_count"]
            cur["scene_group_ranges"] = grouped["scene_group_ranges"]
            cur["scene_group_mode"] = grouped["scene_group_mode"]
            cur["start"] = snapped_start
            cur["end"] = round(snapped_end, 3)
        else:
            grouped = _align_range_to_scene_group(
                start,
                end,
                cut_points,
                lead_window=narration_window,
                tail_window=narration_window,
                hard_start_floor=hard_start_floor,
                hard_end_ceiling=hard_end_ceiling,
            )
            snapped_start = float(grouped["start"])
            snapped_end = float(grouped["end"])
            start_dist = round(abs(snapped_start - semantic_start), 3)
            end_dist = round(abs(snapped_end - semantic_end), 3)
            if start_dist is not None and end_dist is not None and snapped_end > snapped_start:
                cur["scene_aligned"] = True
                cur["scene_align_mode"] = "scene_group_soft_snap"
                cur["scene_align_distance"] = {"start": start_dist, "end": end_dist}
                cur["scene_group_count"] = grouped["scene_group_count"]
                cur["scene_group_ranges"] = grouped["scene_group_ranges"]
                cur["scene_group_mode"] = grouped["scene_group_mode"]
                cur["start"] = snapped_start
                cur["end"] = snapped_end
            else:
                cur["scene_aligned"] = False
                cur["scene_align_mode"] = "semantic_keep"
                cur["scene_align_distance"] = {"start": start_dist, "end": end_dist}
                cur["scene_group_count"] = 0
                cur["scene_group_ranges"] = []
                cur["scene_group_mode"] = "semantic_keep"

        cur["duration"] = round(max(float(cur["end"]) - float(cur["start"]), 0.1), 3)
        cur["timestamp"] = f"{utils.format_time(float(cur['start']))}-{utils.format_time(float(cur['end']))}"
        aligned.append(cur)

    return aligned


def _merge_highlight_segments(highlights: List[Dict[str, Any]], gap_threshold: float = 1.2) -> List[Dict[str, Any]]:
    if not highlights:
        return []

    ordered = sorted(highlights, key=lambda x: (float(x.get("start", 0.0) or 0.0), -float(x.get("highlight_score", 0.0) or 0.0)))
    merged: List[Dict[str, Any]] = [dict(ordered[0])]
    for item in ordered[1:]:
        current = dict(item)
        prev = merged[-1]
        prev_end = float(prev.get("end", 0.0) or 0.0)
        current_start = float(current.get("start", 0.0) or 0.0)
        overlaps = current_start <= prev_end + gap_threshold
        if not overlaps:
            merged.append(current)
            continue

        prev["start"] = round(min(float(prev.get("start", 0.0) or 0.0), current_start), 3)
        prev["end"] = round(max(prev_end, float(current.get("end", prev_end) or prev_end)), 3)
        prev["semantic_start"] = round(min(float(prev.get("semantic_start", prev["start"]) or prev["start"]), float(current.get("semantic_start", current_start) or current_start)), 3)
        prev["semantic_end"] = round(max(float(prev.get("semantic_end", prev["end"]) or prev["end"]), float(current.get("semantic_end", prev["end"]) or prev["end"])), 3)
        prev["duration"] = round(max(float(prev["end"]) - float(prev["start"]), 0.1), 3)
        prev["semantic_duration"] = round(max(float(prev["semantic_end"]) - float(prev["semantic_start"]), 0.1), 3)
        prev["highlight_score"] = round(max(float(prev.get("highlight_score", 0.0) or 0.0), float(current.get("highlight_score", 0.0) or 0.0)), 3)
        prev["plot_functions"] = sorted({*(prev.get("plot_functions") or []), *(current.get("plot_functions") or [])})
        prev["scene_ids"] = sorted({*(prev.get("scene_ids") or []), *(current.get("scene_ids") or [])})
        prev["segment_ids"] = sorted({*(prev.get("segment_ids") or []), *(current.get("segment_ids") or [])})
        prev["evidence_ids"] = sorted({*(prev.get("evidence_ids") or []), *(current.get("evidence_ids") or [])})
        prev["highlight_reasons"] = sorted({*(prev.get("highlight_reasons") or []), *(current.get("highlight_reasons") or [])})
        prev["raw_voice_retain"] = bool(prev.get("raw_voice_retain") or current.get("raw_voice_retain"))
        left_story_end = prev.get("story_end")
        right_story_end = current.get("story_end")
        if left_story_end is None:
            prev["story_end"] = right_story_end
        elif right_story_end is None:
            prev["story_end"] = left_story_end
        else:
            prev["story_end"] = round(min(float(left_story_end), float(right_story_end)), 3)
        prev["story_end_trimmed"] = bool(prev.get("story_end_trimmed") or current.get("story_end_trimmed"))
        prev["story_end_original_after_story_end"] = bool(
            prev.get("story_end_original_after_story_end") or current.get("story_end_original_after_story_end")
        )
        prev["after_story_end"] = bool(prev.get("after_story_end") or current.get("after_story_end"))
        prev["boundary_confidence"] = "high" if "high" in {str(prev.get("boundary_confidence") or ""), str(current.get("boundary_confidence") or "")} else str(prev.get("boundary_confidence") or current.get("boundary_confidence") or "medium")
        prev["timestamp"] = f"{utils.format_time(float(prev['start']))}-{utils.format_time(float(prev['end']))}"
        prev["semantic_timestamp"] = f"{utils.format_time(float(prev['semantic_start']))}-{utils.format_time(float(prev['semantic_end']))}"

    for idx, item in enumerate(merged, start=1):
        item["highlight_id"] = f"highlight_{idx:03d}"
        item["highlight_rank"] = idx
    return merged


def _extract_story_highlights(
    scene_evidence: List[Dict[str, Any]],
    cut_points: List[float],
    highlight_selectivity: str = "balanced",
) -> List[Dict[str, Any]]:
    if not scene_evidence:
        return []

    highlight_selectivity = _resolve_highlight_selectivity(highlight_selectivity)
    min_score = {
        "loose": 1.0,
        "balanced": 1.6,
        "strict": 2.0,
    }[highlight_selectivity]
    raw: List[Dict[str, Any]] = []
    for pkg in scene_evidence:
        score = float(pkg.get("final_story_score", 0.0) or 0.0)
        importance = str(pkg.get("importance_level") or "medium")
        plot_function = str(pkg.get("plot_function") or "")
        block_type = str(pkg.get("block_type") or "dialogue")
        validator_status = str((pkg.get("story_validation") or {}).get("validator_status") or "pass")
        attraction = str(pkg.get("attraction_level") or "")

        if pkg.get("before_prologue_end"):
            continue
        if pkg.get("after_story_end"):
            continue

        if validator_status == "risky" and (
            importance == "low" or highlight_selectivity != "loose"
        ):
            continue
        if highlight_selectivity == "loose" and score >= min_score:
            score = max(score, 1.6)
        if score < 1.6 and importance != "high" and plot_function not in {"\u53cd\u8f6c", "\u60c5\u611f\u7206\u53d1", "\u7ed3\u5c40\u6536\u675f", "\u51b2\u7a81\u5347\u7ea7"}:
            continue

        semantic_start = round(float(pkg.get("start", 0.0) or 0.0), 3)
        semantic_end = round(float(pkg.get("end", semantic_start) or semantic_start), 3)
        raw_voice_keep = bool(pkg.get("llm_raw_voice_keep")) or (
            bool(pkg.get("raw_voice_retain_suggestion"))
            and plot_function in {"\u60c5\u611f\u7206\u53d1", "\u53cd\u8f6c", "\u7ed3\u5c40\u6536\u675f"}
            and importance == "high"
        )
        snap_window = (
            _HIGHLIGHT_SNAP_WINDOW_RAW_VOICE_SECONDS
            if raw_voice_keep
            else (
                _HIGHLIGHT_SNAP_WINDOW_HIGH_SECONDS
                if importance == "high"
                else _HIGHLIGHT_SNAP_WINDOW_DEFAULT_SECONDS
            )
        )
        grouped = _align_range_to_scene_group(
            semantic_start,
            semantic_end,
            cut_points,
            lead_window=snap_window,
            tail_window=snap_window,
            hard_start_floor=float(pkg.get("prologue_end", 0.0) or 0.0) if pkg.get("prologue_trimmed") else None,
            hard_end_ceiling=float(pkg.get("story_end", 0.0) or 0.0) if pkg.get("story_end") is not None else None,
        )
        snapped_start = float(grouped["start"])
        snapped_end = float(grouped["end"])

        reasons: List[str] = []
        if importance == "high":
            reasons.append("high_importance")
        if plot_function:
            reasons.append(f"plot:{plot_function}")
        if block_type in {"action", "emotion", "visual"}:
            reasons.append(f"block:{block_type}")
        if attraction in {"\u9ad8", "high"}:
            reasons.append("high_attraction")
        if raw_voice_keep:
            reasons.append("raw_voice_candidate")
        if str(pkg.get("boundary_confidence") or "") == "high":
            reasons.append("high_boundary_confidence")
        if pkg.get("llm_highlight_selected"):
            reasons.append("llm_highlight_selected")
        if pkg.get("llm_highlight_reason"):
            reasons.append(str(pkg.get("llm_highlight_reason")))

        raw.append(
            {
                "highlight_id": "",
                "highlight_rank": 0,
                "scene_ids": [pkg.get("scene_id")] if pkg.get("scene_id") else [],
                "segment_ids": [pkg.get("segment_id")] if pkg.get("segment_id") else [],
                "evidence_ids": [pkg.get("segment_id") or pkg.get("scene_id")] if (pkg.get("segment_id") or pkg.get("scene_id")) else [],
                "plot_functions": [plot_function] if plot_function else [],
                "highlight_reasons": reasons,
                "highlight_score": round(score, 3),
                "importance_level": importance,
                "boundary_confidence": str(pkg.get("boundary_confidence") or "medium"),
                "raw_voice_retain": raw_voice_keep,
                "semantic_start": semantic_start,
                "semantic_end": semantic_end,
                "semantic_duration": round(max(semantic_end - semantic_start, 0.1), 3),
                "semantic_timestamp": f"{utils.format_time(semantic_start)}-{utils.format_time(semantic_end)}",
                "start": round(snapped_start, 3),
                "end": round(snapped_end, 3),
                "duration": round(max(snapped_end - snapped_start, 0.1), 3),
                "timestamp": f"{utils.format_time(snapped_start)}-{utils.format_time(snapped_end)}",
                "source_text": str(pkg.get("subtitle_text") or pkg.get("main_text_evidence") or "").strip(),
                "validator_status": validator_status,
                "scene_align_mode": "raw_voice_scene_group" if raw_voice_keep else "highlight_scene_group",
                "scene_group_count": grouped["scene_group_count"],
                "scene_group_ranges": grouped["scene_group_ranges"],
                "scene_group_mode": grouped["scene_group_mode"],
                "story_end": pkg.get("story_end"),
                "story_end_trimmed": bool(pkg.get("story_end_trimmed")),
                "story_end_original_after_story_end": bool(pkg.get("story_end_original_after_story_end")),
                "after_story_end": bool(pkg.get("after_story_end")),
            }
        )

    merged = _merge_highlight_segments(raw)
    merged.sort(key=lambda x: (-float(x.get("highlight_score", 0.0) or 0.0), float(x.get("start", 0.0) or 0.0)))
    for idx, item in enumerate(merged, start=1):
        item["highlight_rank"] = idx
    return merged


def _filter_script_items_by_highlights(
    script_items: List[Dict[str, Any]],
    story_highlights: List[Dict[str, Any]],
    *,
    overlap_slack: float = 0.8,
) -> List[Dict[str, Any]]:
    def _is_allowed(cur: Dict[str, Any]) -> bool:
        seg_id = str(cur.get("segment_id") or "")
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)
        semantic_start = float(cur.get("semantic_start", start) or start)
        semantic_end = float(cur.get("semantic_end", end) or end)

        if seg_id in allowed_segment_ids:
            return True
        return any(
            _ranges_overlap(start, end, left, right, overlap_slack)
            or _ranges_overlap(semantic_start, semantic_end, left, right, overlap_slack)
            for left, right in allowed_ranges
        )

    if not script_items:
        return []
    if not story_highlights:
        return script_items

    allowed_ranges = [
        (
            float(item.get("start", 0.0) or 0.0),
            float(item.get("end", 0.0) or 0.0),
        )
        for item in story_highlights
    ]
    allowed_segment_ids = {
        str(seg_id)
        for item in story_highlights
        for seg_id in (item.get("segment_ids") or [])
        if seg_id
    }

    kept: List[Dict[str, Any]] = []
    for item in script_items:
        cur = dict(item)
        keep = _is_allowed(cur)
        cur["highlight_filter_selected"] = bool(keep)
        if keep:
            kept.append(cur)

    if not kept:
        return script_items

    for idx, item in enumerate(kept, start=1):
        item["_id"] = idx
    return kept


def _unique_strings(values: List[Any], limit: int = 0) -> List[str]:
    out: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in out:
            continue
        out.append(text)
        if limit and len(out) >= limit:
            break
    return out


def _merge_text_snippets(values: List[Any], limit: int = 4, max_chars: int = 240) -> str:
    pieces = _unique_strings(values, limit=limit)
    if not pieces:
        return ""
    return "；".join(pieces)[:max_chars].strip("；")


def _representative_frame_desc(frame_path: str, rank: int, timestamp_seconds: float | None = None) -> str:
    if timestamp_seconds is not None:
        return f"第{rank}张代表帧，时间点 {utils.format_time(float(timestamp_seconds))}"
    return f"第{rank}张代表帧，来自 {os.path.basename(frame_path)}"


def _highlight_frame_budget(highlight: Dict[str, Any]) -> int:
    start = float(highlight.get("start", 0.0) or 0.0)
    end = float(highlight.get("end", start) or start)
    duration = max(end - start, 0.1)
    if duration >= 35.0:
        return 5
    if duration >= 18.0 or str(highlight.get("importance_level") or "") == "high":
        return 4
    return 3


def _prepare_highlight_frame_targets(story_highlights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    for item in story_highlights or []:
        cur = dict(item)
        highlight_id = str(cur.get("highlight_id") or "").strip()
        if not highlight_id:
            continue
        cur["scene_id"] = highlight_id
        cur["segment_id"] = highlight_id
        cur["frame_budget"] = int(cur.get("frame_budget") or _highlight_frame_budget(cur))
        targets.append(cur)
    return targets


def _build_highlight_visual_summary(
    highlight_id: str,
    highlight_frame_records: List[Dict[str, Any]],
    source_visual_summary: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    records = sorted(
        [
            dict(rec)
            for rec in (highlight_frame_records or [])
            if str(rec.get("scene_id") or rec.get("segment_id") or "").strip() == highlight_id
        ],
        key=lambda x: (
            int(x.get("rank", 0) or 0),
            float(x.get("timestamp_seconds", 0.0) or 0.0),
        ),
    )

    if records:
        visual_summary: List[Dict[str, Any]] = []
        representative_frames: List[Dict[str, Any]] = []
        for idx, rec in enumerate(records, start=1):
            frame_path = str(rec.get("frame_path") or "").strip()
            if not frame_path:
                continue
            timestamp_seconds = float(rec.get("timestamp_seconds", 0.0) or 0.0)
            desc = _representative_frame_desc(frame_path, idx, timestamp_seconds=timestamp_seconds)
            visual_summary.append(
                {
                    "frame": frame_path,
                    "desc": desc,
                    "timestamp_seconds": round(timestamp_seconds, 3),
                    "rank": int(rec.get("rank", idx) or idx),
                }
            )
            representative_frames.append(
                {
                    "frame_path": frame_path,
                    "timestamp_seconds": round(timestamp_seconds, 3),
                    "timestamp": utils.format_time(timestamp_seconds),
                    "rank": int(rec.get("rank", idx) or idx),
                    "desc": desc,
                }
            )
        return visual_summary, [x["frame_path"] for x in representative_frames], representative_frames

    fallback_visual_summary: List[Dict[str, Any]] = []
    fallback_frames: List[Dict[str, Any]] = []
    for idx, item in enumerate(source_visual_summary[:4], start=1):
        frame_path = str(item.get("frame") or item.get("frame_path") or "").strip()
        desc = str(item.get("desc") or item.get("observation") or "").strip()
        if not frame_path and not desc:
            continue
        fallback_visual_summary.append(
            {
                "frame": frame_path,
                "desc": desc or _representative_frame_desc(frame_path, idx),
                "timestamp_seconds": item.get("timestamp_seconds"),
                "rank": idx,
            }
        )
        fallback_frames.append(
            {
                "frame_path": frame_path,
                "timestamp_seconds": item.get("timestamp_seconds"),
                "timestamp": utils.format_time(float(item.get("timestamp_seconds", 0.0) or 0.0))
                if item.get("timestamp_seconds") is not None
                else "",
                "rank": idx,
                "desc": desc or _representative_frame_desc(frame_path, idx),
            }
        )
    return fallback_visual_summary, [x.get("frame_path", "") for x in fallback_frames if x.get("frame_path")], fallback_frames


def _collect_highlight_source_packages(
    highlight: Dict[str, Any],
    scene_evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    highlight_segment_ids = {str(x).strip() for x in (highlight.get("segment_ids") or []) if str(x or "").strip()}
    highlight_scene_ids = {str(x).strip() for x in (highlight.get("scene_ids") or []) if str(x or "").strip()}
    highlight_start = float(highlight.get("start", 0.0) or 0.0)
    highlight_end = float(highlight.get("end", highlight_start) or highlight_start)

    matched: List[Dict[str, Any]] = []
    for pkg in scene_evidence or []:
        seg_id = str(pkg.get("segment_id") or "").strip()
        scene_id = str(pkg.get("scene_id") or "").strip()
        start = float(pkg.get("start", 0.0) or 0.0)
        end = float(pkg.get("end", start) or start)
        if (
            (seg_id and seg_id in highlight_segment_ids)
            or (scene_id and scene_id in highlight_scene_ids)
            or _ranges_overlap(start, end, highlight_start, highlight_end, 0.8)
        ):
            matched.append(dict(pkg))
    matched.sort(key=lambda x: (float(x.get("start", 0.0) or 0.0), float(x.get("end", 0.0) or 0.0)))
    return matched


def _build_highlight_story_validation(source_packages: List[Dict[str, Any]], raw_voice_keep: bool) -> Dict[str, Any]:
    validator_status = "pass"
    validator_hints: List[str] = []
    for pkg in source_packages or []:
        validation = dict(pkg.get("story_validation") or {})
        status = str(validation.get("validator_status") or "pass")
        if status == "risky":
            validator_status = "risky"
        validator_hints.extend(validation.get("validator_hints") or [])
    return {
        "validator_status": validator_status,
        "validator_hints": _unique_strings(validator_hints, limit=6),
        "raw_voice_keep": bool(raw_voice_keep),
    }


def _build_highlight_local_understanding(source_packages: List[Dict[str, Any]]) -> Dict[str, Any]:
    core_events: List[str] = []
    emotions: List[str] = []
    characters: List[str] = []
    risk_flags: List[str] = []
    for pkg in source_packages or []:
        local = dict(pkg.get("local_understanding") or {})
        if local.get("core_event"):
            core_events.append(local["core_event"])
        if local.get("emotion"):
            emotions.append(local["emotion"])
        characters.extend(local.get("characters") or [])
        risk_flags.extend(local.get("narrative_risk_flags") or [])
    emotion_pick = _unique_strings(emotions, limit=1)
    return {
        "core_event": _merge_text_snippets(core_events, limit=3, max_chars=120),
        "emotion": emotion_pick[0] if emotion_pick else "",
        "characters": _unique_strings(characters, limit=8),
        "narrative_risk_flags": _unique_strings(risk_flags, limit=6),
    }


def _build_highlight_narration_segments(
    *,
    story_highlights: List[Dict[str, Any]],
    scene_evidence: List[Dict[str, Any]],
    highlight_frame_records: List[Dict[str, Any]],
    global_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    packages: List[Dict[str, Any]] = []
    for idx, highlight in enumerate(story_highlights or [], start=1):
        highlight_id = str(highlight.get("highlight_id") or f"highlight_{idx:03d}").strip()
        start = round(float(highlight.get("start", 0.0) or 0.0), 3)
        end = round(float(highlight.get("end", start) or start), 3)
        if end <= start:
            end = round(start + 0.5, 3)

        source_packages = _collect_highlight_source_packages(highlight, scene_evidence)
        subtitle_ids: List[Any] = []
        source_visual_summary: List[Dict[str, Any]] = []
        speaker_names: List[str] = []
        exchange_pairs: List[Any] = []
        frame_paths_from_source: List[str] = []
        for pkg in source_packages:
            subtitle_ids.extend(pkg.get("subtitle_ids") or [])
            source_visual_summary.extend(pkg.get("visual_summary") or [])
            speaker_names.extend(pkg.get("speaker_names") or [])
            exchange_pairs.extend(pkg.get("exchange_pairs") or [])
            frame_paths_from_source.extend(pkg.get("frame_paths") or [])

        visual_summary, frame_paths, representative_frames = _build_highlight_visual_summary(
            highlight_id,
            highlight_frame_records,
            source_visual_summary,
        )
        if not frame_paths:
            frame_paths = _unique_strings(frame_paths_from_source, limit=6)

        main_text = _merge_text_snippets(
            [pkg.get("main_text_evidence") or pkg.get("subtitle_text") for pkg in source_packages] + [highlight.get("source_text")],
            limit=6,
            max_chars=320,
        )
        surface_dialogue = _merge_text_snippets(
            [pkg.get("surface_dialogue_meaning") for pkg in source_packages],
            limit=4,
            max_chars=220,
        )
        real_state = _merge_text_snippets(
            [pkg.get("real_narrative_state") for pkg in source_packages],
            limit=4,
            max_chars=220,
        )
        plot_functions = _unique_strings(
            list(highlight.get("plot_functions") or []) + [pkg.get("plot_function") for pkg in source_packages],
            limit=4,
        )
        picture = "；".join(str(item.get("desc") or "").strip() for item in visual_summary[:2]).strip("；")
        if not picture:
            picture = " / ".join(_unique_strings(highlight.get("highlight_reasons") or [], limit=2)) or main_text[:80] or "高光片段"

        raw_voice_keep = bool(highlight.get("raw_voice_retain"))
        local_understanding = _build_highlight_local_understanding(source_packages)
        story_validation = _build_highlight_story_validation(source_packages, raw_voice_keep)
        importance_level = str(highlight.get("importance_level") or "high")
        plot_function = plot_functions[0] if plot_functions else ""
        attraction_candidates = _unique_strings([pkg.get("attraction_level") for pkg in source_packages], limit=3)
        attraction_level = attraction_candidates[0] if attraction_candidates else ("high" if importance_level == "high" else "medium")
        confidence_candidates = _unique_strings([pkg.get("confidence") for pkg in source_packages], limit=3)
        confidence = confidence_candidates[0] if confidence_candidates else "highlight"
        plot_role_candidates = _unique_strings([pkg.get("plot_role") for pkg in source_packages], limit=3)
        plot_role = plot_role_candidates[0] if plot_role_candidates else ""
        narrative_risk_flags = _unique_strings(
            [flag for pkg in source_packages for flag in (pkg.get("narrative_risk_flags") or [])],
            limit=8,
        )

        package = {
            "segment_id": "+".join(highlight.get("segment_ids") or []) or highlight_id,
            "scene_id": highlight_id,
            "highlight_id": highlight_id,
            "highlight_rank": int(highlight.get("highlight_rank", idx) or idx),
            "highlight_reasons": list(highlight.get("highlight_reasons") or []),
            "source_segment_ids": _unique_strings(highlight.get("segment_ids") or [], limit=12),
            "source_scene_ids": _unique_strings(highlight.get("scene_ids") or [], limit=12),
            "source_evidence_ids": _unique_strings(highlight.get("evidence_ids") or [], limit=12),
            "time_window": [start, end],
            "timestamp": f"{utils.format_time(start)}-{utils.format_time(end)}",
            "semantic_timestamp": highlight.get("semantic_timestamp") or f"{utils.format_time(start)}-{utils.format_time(end)}",
            "start": start,
            "end": end,
            "duration": round(max(end - start, 0.1), 3),
            "plot_function": plot_function,
            "plot_functions": plot_functions,
            "plot_role": plot_role,
            "importance_level": importance_level,
            "attraction_level": attraction_level,
            "confidence": confidence,
            "boundary_confidence": highlight.get("boundary_confidence"),
            "scene_align_mode": highlight.get("scene_align_mode"),
            "scene_group_count": highlight.get("scene_group_count", 0),
            "scene_group_ranges": list(highlight.get("scene_group_ranges") or []),
            "scene_group_mode": highlight.get("scene_group_mode", ""),
            "main_text_evidence": main_text,
            "subtitle_text": main_text,
            "subtitle_ids": list(dict.fromkeys(subtitle_ids)),
            "surface_dialogue_meaning": surface_dialogue,
            "real_narrative_state": real_state,
            "visual_summary": visual_summary,
            "frame_paths": frame_paths,
            "representative_frames": representative_frames,
            "picture": picture,
            "speaker_names": _unique_strings(speaker_names, limit=6),
            "speaker_turns": sum(int(pkg.get("speaker_turns", 0) or 0) for pkg in source_packages),
            "exchange_pairs": exchange_pairs[:6],
            "emotion_hint": local_understanding.get("emotion") or "平静",
            "local_understanding": local_understanding,
            "story_validation": story_validation,
            "raw_voice_retain_suggestion": bool(raw_voice_keep),
            "raw_voice_retain": bool(raw_voice_keep),
            "llm_highlight_selected": True,
            "llm_raw_voice_keep": bool(raw_voice_keep),
            "narrative_risk_flags": narrative_risk_flags,
            "need_visual_verify": any(bool(pkg.get("need_visual_verify")) for pkg in source_packages),
            "before_prologue_end": False,
            "after_story_end": bool(highlight.get("after_story_end")),
            "prologue_end": None,
            "story_end": highlight.get("story_end"),
            "story_end_trimmed": bool(highlight.get("story_end_trimmed")),
            "story_end_original_after_story_end": bool(highlight.get("story_end_original_after_story_end")),
            "_global_summary": global_summary,
        }
        packages.append(package)

    packages.sort(key=lambda x: (float(x.get("start", 0.0) or 0.0), int(x.get("highlight_rank", 0) or 0)))
    return packages


def _build_highlight_only_script(highlight_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for idx, item in enumerate(highlight_segments, start=1):
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start) or start)
        if end <= start:
            end = start + 0.5
        reasons = " / ".join(item.get("highlight_reasons") or [])
        picture = (item.get("picture") or reasons or "高光片段")[:80]
        items.append(
            {
                "_id": idx,
                "timestamp": f"{utils.format_time(start)}-{utils.format_time(end)}",
                "source_timestamp": f"{utils.format_time(start)}-{utils.format_time(end)}",
                "semantic_timestamp": item.get("semantic_timestamp") or f"{utils.format_time(start)}-{utils.format_time(end)}",
                "picture": picture,
                "narration": "",
                "OST": 1,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(max(end - start, 0.1), 3),
                "segment_id": str(item.get("segment_id") or "+".join(item.get("segment_ids") or []) or item.get("highlight_id")),
                "scene_id": item.get("highlight_id"),
                "plot_function": item.get("plot_function") or ",".join(item.get("plot_functions") or []),
                "importance_level": item.get("importance_level", "high"),
                "llm_highlight_selected": True,
                "llm_raw_voice_keep": bool(item.get("raw_voice_retain") or item.get("llm_raw_voice_keep")),
                "scene_align_mode": item.get("scene_align_mode"),
                "scene_group_count": item.get("scene_group_count", 0),
                "scene_group_ranges": item.get("scene_group_ranges", []),
                "scene_group_mode": item.get("scene_group_mode", ""),
                "story_end": item.get("story_end"),
                "story_end_trimmed": bool(item.get("story_end_trimmed")),
                "story_end_original_after_story_end": bool(item.get("story_end_original_after_story_end")),
                "after_story_end": bool(item.get("after_story_end")),
                "highlight_id": item.get("highlight_id"),
                "highlight_rank": item.get("highlight_rank"),
                "highlight_reasons": item.get("highlight_reasons") or [],
                "frame_paths": list(item.get("frame_paths") or []),
                "visual_summary": list(item.get("visual_summary") or []),
                "representative_frames": list(item.get("representative_frames") or []),
                "source_segment_ids": list(item.get("source_segment_ids") or item.get("segment_ids") or []),
                "source_scene_ids": list(item.get("source_scene_ids") or item.get("scene_ids") or []),
                "source_evidence_ids": list(item.get("source_evidence_ids") or item.get("evidence_ids") or []),
                "main_text_evidence": item.get("main_text_evidence") or item.get("source_text") or "",
                "char_budget": 0,
                "fit_check": {"status": "highlight_only", "target_chars": 0, "actual_chars": 0},
                "narration_validation": {"status": "skip", "issues": [], "safe_rewrite_hint": "", "raw_voice_keep": True},
            }
        )
    return items


def _resolve_highlight_selectivity(value: str) -> str:
    normalized = str(value or "balanced").strip().lower()
    if normalized in {"loose", "balanced", "strict"}:
        return normalized
    return "balanced"


def _validate_pipeline_quality(
    *,
    full_subtitle_understanding: Dict[str, Any],
    llm_highlight_plan: Dict[str, Any],
    story_highlights: List[Dict[str, Any]],
    script_items: List[Dict[str, Any]],
    highlight_only: bool,
    highlight_selectivity: str = "balanced",
) -> List[str]:
    issues: List[str] = []

    highlight_selectivity = _resolve_highlight_selectivity(highlight_selectivity)
    highlight_windows = list(full_subtitle_understanding.get("highlight_windows") or [])
    highlight_windows_backfilled = bool(full_subtitle_understanding.get("highlight_windows_backfilled"))
    subtitle_input_mode = str(full_subtitle_understanding.get("subtitle_input_mode") or "").strip()
    subtitle_chunk_summaries = list(full_subtitle_understanding.get("subtitle_chunk_summaries") or [])
    selected_segment_ids = list(llm_highlight_plan.get("selected_segment_ids") or [])
    raw_voice_segment_ids = set(str(x) for x in (llm_highlight_plan.get("raw_voice_segment_ids") or []) if x)
    has_highlight_signals = bool(highlight_windows or selected_segment_ids or story_highlights)
    if subtitle_input_mode in ("", "timeline_digest") and not highlight_windows_backfilled and not has_highlight_signals:
        issues.append("整字幕理解未真正使用整字幕全文或分块结果")
    if subtitle_input_mode == "chunked_full_subtitle" and not subtitle_chunk_summaries and not has_highlight_signals:
        issues.append("整字幕分块理解失败，未产出有效的分块摘要")
    highlight_signal_count = max(
        len(highlight_windows),
        len(selected_segment_ids),
        len(script_items),
    )
    min_required_story_highlights = 0
    if highlight_signal_count > 0:
        if highlight_selectivity == "loose":
            min_required_story_highlights = 1
        elif highlight_selectivity == "strict":
            min_required_story_highlights = 2 if highlight_signal_count >= 2 else 1
        else:
            min_required_story_highlights = 1 if highlight_signal_count <= 4 else 2

    if not highlight_windows and not selected_segment_ids and not story_highlights:
        issues.append("整字幕理解未产出高光窗口")
    if not selected_segment_ids and not highlight_windows and not story_highlights:
        issues.append("精细段高光选择未产出入选结果")
    if len(story_highlights) < 2:
        issues.append("最终高光片段过少")

    if len(story_highlights) >= min_required_story_highlights:
        issues = [issue for issue in issues if issue != "\u6700\u7ec8\u9ad8\u5149\u7247\u6bb5\u8fc7\u5c11"]

    for item in story_highlights:
        if float(item.get("end", 0.0) or 0.0) <= float(item.get("start", 0.0) or 0.0):
            issues.append(f"高光片段时间非法: {item.get('highlight_id')}")
        if not item.get("scene_group_ranges") and item.get("scene_align_mode") != "semantic_keep":
            issues.append(f"高光片段未形成有效场景组: {item.get('highlight_id')}")

    if not highlight_only:
        if not script_items:
            issues.append("最终脚本为空")
        for item in script_items:
            seg_id = str(item.get("segment_id") or "")
            nv = item.get("narration_validation") or {}
            if nv.get("status") == "reject":
                issues.append(f"脚本包含被拒绝的解说文案: {seg_id or item.get('_id')}")
            if not item.get("llm_highlight_selected") and not item.get("highlight_filter_selected"):
                issues.append(f"脚本包含未通过高光选择的片段: {seg_id or item.get('_id')}")
            if int(item.get("OST", 2) or 2) == 1 and seg_id and seg_id not in raw_voice_segment_ids and not bool(item.get("llm_raw_voice_keep")):
                issues.append(f"原声片段未经LLM高光许可: {seg_id}")

    deduped: List[str] = []
    for issue in issues:
        if issue not in deduped:
            deduped.append(issue)
    return deduped


def _build_story_audit_payload(
    *,
    video_path: str,
    subtitle_result: Dict[str, Any],
    highlight_only_mode: bool,
    full_subtitle_understanding: Dict[str, Any],
    global_summary: Dict[str, Any],
    plot_chunks: List[Dict[str, Any]],
    selected_scene_evidence: List[Dict[str, Any]],
    story_highlights: List[Dict[str, Any]],
    highlight_narration_segments: List[Dict[str, Any]],
    llm_highlight_plan: Dict[str, Any],
    script_items: List[Dict[str, Any]],
    scene_cut_points: List[float],
    video_boundary_candidates: List[Dict[str, Any]],
    frame_records: List[Dict[str, Any]],
    highlight_frame_records: List[Dict[str, Any]],
    quality_issues: List[str],
    warnings: List[str],
) -> Dict[str, Any]:
    return {
        "pipeline": "subtitle_first_movie_story",
        "highlight_only_mode": highlight_only_mode,
        "video_path": video_path,
        "subtitle": {
            "source": subtitle_result.get("source", "none"),
            "backend": subtitle_result.get("backend", ""),
            "subtitle_path": subtitle_result.get("subtitle_path", ""),
            "original_subtitle_path": subtitle_result.get("original_subtitle_path", ""),
            "raw_subtitle_path": subtitle_result.get("raw_subtitle_path", ""),
            "clean_subtitle_path": subtitle_result.get("clean_subtitle_path", ""),
            "subtitle_segments_path": subtitle_result.get("subtitle_segments_path", ""),
        },
        "full_subtitle_understanding": full_subtitle_understanding,
        "global_summary": global_summary,
        "plot_chunks": plot_chunks,
        "selected_scene_evidence": selected_scene_evidence,
        "story_highlights": story_highlights,
        "highlight_narration_segments": highlight_narration_segments,
        "llm_highlight_plan": llm_highlight_plan,
        "script_items": script_items,
        "scene_cut_points": scene_cut_points,
        "video_boundary_candidates": video_boundary_candidates,
        "frame_records": frame_records,
        "highlight_frame_records": highlight_frame_records,
        "quality_issues": quality_issues,
        "warnings": warnings,
    }


def _parse_prompt_time(raw: Any) -> float | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return round(float(utils.time_to_seconds(text)), 3)
    except Exception:
        return None


def _coerce_highlight_time(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 3)
    return _parse_prompt_time(raw)


def _normalize_prompt_highlight_window(
    item: Dict[str, Any],
    *,
    default_category: str = "",
    default_importance: str = "medium",
    default_raw_voice_priority: str = "low",
    default_reason: str = "llm_highlight_window",
) -> Dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    start = _coerce_highlight_time(item.get("start"))
    end = _coerce_highlight_time(item.get("end"))
    if start is None or end is None or end <= start:
        return None

    importance = str(item.get("importance") or default_importance or "medium").strip().lower()
    if importance not in {"high", "medium", "low"}:
        importance = default_importance
    raw_voice_priority = str(
        item.get("raw_voice_priority") or default_raw_voice_priority or "low"
    ).strip().lower()
    if raw_voice_priority not in {"high", "medium", "low"}:
        raw_voice_priority = default_raw_voice_priority

    category = str(item.get("category") or item.get("label") or default_category or "信息揭露").strip()
    reason = str(item.get("reason") or item.get("label") or category or default_reason).strip()
    return {
        "start": utils.format_time(start),
        "end": utils.format_time(end),
        "category": category,
        "importance": importance,
        "raw_voice_priority": raw_voice_priority,
        "reason": reason,
    }


def _dedupe_prompt_highlight_windows(windows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    ordered = sorted(
        (item for item in windows if isinstance(item, dict)),
        key=lambda x: (_coerce_highlight_time(x.get("start")) or 0.0, _coerce_highlight_time(x.get("end")) or 0.0),
    )
    for item in ordered:
        key = (
            item.get("start"),
            item.get("end"),
            str(item.get("category") or ""),
            str(item.get("importance") or ""),
            str(item.get("raw_voice_priority") or ""),
            str(item.get("reason") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _resolve_highlight_category(
    reasons: List[str] | None,
    plot_functions: List[str] | None = None,
) -> str:
    candidates: List[str] = [str(x).strip() for x in (plot_functions or []) if str(x or "").strip()]
    for reason in reasons or []:
        text = str(reason or "").strip()
        if not text:
            continue
        if text.startswith("plot:"):
            candidates.insert(0, text.split(":", 1)[1].strip())
        else:
            candidates.append(text)

    for cue in ("反转", "情感爆发", "冲突升级", "信息揭露", "高潮", "结局收束", "结尾"):
        for item in candidates:
            if cue and cue in item:
                return cue
    return candidates[0] if candidates else ""


def _build_prompt_highlight_windows_from_story_highlights(
    story_highlights: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    for item in story_highlights or []:
        reason_parts = [str(x).strip() for x in (item.get("highlight_reasons") or []) if str(x or "").strip()]
        importance = str(item.get("importance_level") or "medium").strip().lower()
        if importance not in {"high", "medium", "low"}:
            importance = "medium"
        raw_voice_priority = "high" if bool(item.get("raw_voice_retain")) else ("medium" if importance == "high" else "low")
        category = _resolve_highlight_category(reason_parts, list(item.get("plot_functions") or []))
        normalized = _normalize_prompt_highlight_window(
            {
                "start": item.get("start"),
                "end": item.get("end"),
                "category": category,
                "importance": importance,
                "raw_voice_priority": raw_voice_priority,
                "reason": " / ".join(reason_parts[:3]) or category or "story_highlights_fallback",
            },
            default_category=category or "信息揭露",
            default_importance=importance,
            default_raw_voice_priority=raw_voice_priority,
            default_reason="story_highlights_fallback",
        )
        if normalized:
            windows.append(normalized)
    return _dedupe_prompt_highlight_windows(windows)


def _ensure_full_subtitle_highlight_windows(
    *,
    full_subtitle_understanding: Dict[str, Any],
    llm_highlight_plan: Dict[str, Any],
    story_highlights: List[Dict[str, Any]],
) -> Dict[str, Any]:
    updated = dict(full_subtitle_understanding or {})
    existing_windows = _dedupe_prompt_highlight_windows(
        [
            normalized
            for normalized in (
                _normalize_prompt_highlight_window(item)
                for item in list(updated.get("highlight_windows") or [])
            )
            if normalized
        ]
    )
    if existing_windows:
        updated["highlight_windows"] = existing_windows
        updated.setdefault("highlight_windows_backfilled", False)
        updated["highlight_windows_source"] = str(updated.get("highlight_windows_source") or "llm_or_existing")
        return updated

    llm_plan_windows = _dedupe_prompt_highlight_windows(
        [
            normalized
            for normalized in (
                _normalize_prompt_highlight_window(
                    item,
                    default_importance="high",
                    default_raw_voice_priority="medium",
                    default_reason="llm_must_keep_range",
                )
                for item in list(llm_highlight_plan.get("must_keep_ranges") or [])
            )
            if normalized
        ]
    )
    if llm_plan_windows:
        updated["highlight_windows"] = llm_plan_windows
        updated["highlight_windows_backfilled"] = True
        updated["highlight_windows_source"] = "llm_plan_must_keep_ranges"
        return updated

    story_windows = _build_prompt_highlight_windows_from_story_highlights(story_highlights)
    if story_windows:
        updated["highlight_windows"] = story_windows
        updated["highlight_windows_backfilled"] = True
        updated["highlight_windows_source"] = "story_highlights_fallback"
        return updated

    updated.setdefault("highlight_windows", [])
    updated.setdefault("highlight_windows_backfilled", False)
    updated["highlight_windows_source"] = str(updated.get("highlight_windows_source") or "none")
    return updated


def _is_meaningful_speech_segment(item: Dict[str, Any]) -> bool:
    text = str(item.get("text") or item.get("subtitle_text") or "").strip()
    if not text or _PROLOGUE_CUE_ONLY_RE.match(text):
        return False
    core = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    if len(core) >= 2:
        return True
    start = float(item.get("start", 0.0) or 0.0)
    end = float(item.get("end", start) or start)
    return (end - start) >= 0.8


def _infer_first_speech_time(subtitle_segments: List[Dict[str, Any]]) -> float | None:
    for item in sorted(subtitle_segments or [], key=lambda x: float(x.get("start", 0.0) or 0.0)):
        if _is_meaningful_speech_segment(item):
            return round(float(item.get("start", 0.0) or 0.0), 3)
    return None


def _normalize_tail_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _score_tail_preview_marker(text: str, position_ratio: float) -> float:
    if not text:
        return 0.0

    score = 0.0
    for cue, weight in _TAIL_PREVIEW_CUES.items():
        if cue in text:
            score += weight

    if "预告" in text and any(cue in text for cue in ("下集", "下期", "下回", "次集", "下一集")):
        score += 2.5
    if _TAIL_BRACKET_RE.match(text) and "预告" in text:
        score += 1.2
    if position_ratio >= 0.92:
        score += 1.2
    elif position_ratio >= 0.84:
        score += 0.7
    return round(score, 3)


def _score_tail_credits_marker(text: str, position_ratio: float) -> float:
    if not text:
        return 0.0

    score = 0.0
    for cue, weight in _TAIL_CREDITS_CUES.items():
        if cue in text:
            score += weight

    if _TAIL_BRACKET_RE.match(text) and ("片尾" in text or "片尾曲" in text):
        score += 1.5
    if _PROLOGUE_CUE_ONLY_RE.match(text) and position_ratio >= 0.9:
        score += 0.8
    if position_ratio >= 0.9:
        score += 0.9
    elif position_ratio >= 0.82:
        score += 0.4
    return round(score, 3)


def _merge_tail_marker_runs(markers: List[Dict[str, Any]], gap_threshold: float = 8.0) -> List[Dict[str, Any]]:
    if not markers:
        return []

    ordered = sorted(markers, key=lambda x: (float(x.get("start", 0.0) or 0.0), -float(x.get("score", 0.0) or 0.0)))
    merged: List[Dict[str, Any]] = [dict(ordered[0])]
    for item in ordered[1:]:
        current = dict(item)
        prev = merged[-1]
        same_type = str(prev.get("type") or "") == str(current.get("type") or "")
        close_enough = float(current.get("start", 0.0) or 0.0) <= float(prev.get("end", 0.0) or 0.0) + gap_threshold
        if not (same_type and close_enough):
            merged.append(current)
            continue

        prev["end"] = round(max(float(prev.get("end", 0.0) or 0.0), float(current.get("end", 0.0) or 0.0)), 3)
        prev["score"] = round(max(float(prev.get("score", 0.0) or 0.0), float(current.get("score", 0.0) or 0.0)), 3)
        prev["source_segment_ids"] = list(
            dict.fromkeys(list(prev.get("source_segment_ids") or []) + list(current.get("source_segment_ids") or []))
        )
        prev["reason"] = " / ".join(
            dict.fromkeys(
                [str(x).strip() for x in [prev.get("reason"), current.get("reason")] if str(x or "").strip()]
            )
        )
    return merged


def _detect_tail_markers(subtitle_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(subtitle_segments or [], key=lambda x: float(x.get("start", 0.0) or 0.0))
    if not ordered:
        return {
            "story_end_seconds": None,
            "story_end_source": "none",
            "credits_start_seconds": None,
            "preview_start_seconds": None,
            "tail_markers": [],
        }

    total_duration = max(float(ordered[-1].get("end", ordered[-1].get("start", 0.0)) or 0.0), 0.0)
    if total_duration <= 0.0:
        return {
            "story_end_seconds": None,
            "story_end_source": "none",
            "credits_start_seconds": None,
            "preview_start_seconds": None,
            "tail_markers": [],
        }

    candidates: List[Dict[str, Any]] = []
    for seg in ordered:
        start = round(float(seg.get("start", 0.0) or 0.0), 3)
        end = round(float(seg.get("end", start) or start), 3)
        if end <= start:
            end = round(start + 0.5, 3)
        position_ratio = start / max(total_duration, 1.0)
        if position_ratio < 0.72:
            continue

        text = _normalize_tail_text(seg.get("text") or seg.get("subtitle_text") or "")
        if not text:
            continue

        preview_score = _score_tail_preview_marker(text, position_ratio)
        credits_score = _score_tail_credits_marker(text, position_ratio)
        if preview_score < 4.0 and credits_score < 4.2:
            continue

        marker_type = "preview" if preview_score >= credits_score else "credits"
        score = max(preview_score, credits_score)
        reason = "tail_preview_cue" if marker_type == "preview" else "tail_credits_cue"
        candidates.append(
            {
                "type": marker_type,
                "start": start,
                "end": end,
                "score": round(score, 3),
                "reason": reason,
                "source_segment_ids": [str(seg.get("seg_id") or seg.get("id") or "")],
            }
        )

    markers = _merge_tail_marker_runs(candidates)
    preview_marker = next((item for item in markers if str(item.get("type") or "") == "preview"), None)
    credits_candidates = [item for item in markers if str(item.get("type") or "") == "credits"]
    if preview_marker is not None:
        credits_candidates = [
            item for item in credits_candidates if float(item.get("start", 0.0) or 0.0) <= float(preview_marker.get("start", 0.0) or 0.0) + 1.0
        ]
    credits_marker = credits_candidates[0] if credits_candidates else None

    story_end_candidates = [
        float(item.get("start", 0.0) or 0.0)
        for item in (credits_marker, preview_marker)
        if item is not None
    ]
    story_end_seconds = min(story_end_candidates) if story_end_candidates else None
    story_end_source_parts: List[str] = []
    if credits_marker is not None:
        story_end_source_parts.append("credits_auto")
    if preview_marker is not None:
        story_end_source_parts.append("preview_auto")

    return {
        "story_end_seconds": round(float(story_end_seconds), 3) if story_end_seconds is not None else None,
        "story_end_source": "+".join(story_end_source_parts) if story_end_source_parts else "none",
        "credits_start_seconds": round(float(credits_marker.get("start", 0.0) or 0.0), 3) if credits_marker is not None else None,
        "preview_start_seconds": round(float(preview_marker.get("start", 0.0) or 0.0), 3) if preview_marker is not None else None,
        "tail_markers": markers,
    }


def _resolve_story_end_from_tail_markers(
    *,
    full_subtitle_understanding: Dict[str, Any],
    subtitle_segments: List[Dict[str, Any]],
) -> tuple[Dict[str, Any], List[str]]:
    detected = _detect_tail_markers(subtitle_segments)
    updated = dict(full_subtitle_understanding or {})
    story_end_seconds = detected.get("story_end_seconds")
    credits_start_seconds = detected.get("credits_start_seconds")
    preview_start_seconds = detected.get("preview_start_seconds")

    updated["tail_markers"] = list(detected.get("tail_markers") or [])
    updated["resolved_story_end_source"] = str(detected.get("story_end_source") or "none")
    updated["resolved_story_end_seconds"] = story_end_seconds
    updated["story_end_time"] = utils.format_time(float(story_end_seconds)) if story_end_seconds is not None else ""
    updated["credits_start_time"] = utils.format_time(float(credits_start_seconds)) if credits_start_seconds is not None else ""
    updated["preview_start_time"] = utils.format_time(float(preview_start_seconds)) if preview_start_seconds is not None else ""
    return updated, []


def _resolve_prologue_end_from_strategy(
    *,
    full_subtitle_understanding: Dict[str, Any],
    subtitle_segments: List[Dict[str, Any]],
    scene_overrides: Dict[str, Any],
) -> tuple[Dict[str, Any], List[str]]:
    strategy = str(scene_overrides.get("prologue_strategy") or "speech_first").strip().lower()
    manual_time = str(scene_overrides.get("manual_prologue_end_time") or "").strip()
    llm_time = _parse_prompt_time(full_subtitle_understanding.get("prologue_end_time"))
    first_speech_time = _infer_first_speech_time(subtitle_segments)
    warnings: List[str] = []

    resolved_time = llm_time
    resolved_source = "llm_auto"

    if strategy == "manual_time":
        manual_seconds = _parse_prompt_time(manual_time)
        if manual_seconds is not None:
            resolved_time = manual_seconds
            resolved_source = "manual_time"
        else:
            warnings.append("manual_prologue_end_time_invalid")
            if first_speech_time is not None:
                resolved_time = first_speech_time
                resolved_source = "manual_invalid_fallback_first_speech"
            elif llm_time is not None:
                resolved_time = llm_time
                resolved_source = "manual_invalid_fallback_llm"
            else:
                resolved_source = "manual_invalid_no_boundary"
    elif strategy == "llm_auto":
        resolved_time = llm_time
        resolved_source = "llm_auto" if llm_time is not None else "llm_auto_empty"
    else:
        if first_speech_time is not None:
            resolved_time = first_speech_time
            resolved_source = "first_speech"
        elif llm_time is not None:
            resolved_time = llm_time
            resolved_source = "first_speech_fallback_llm"
        else:
            resolved_source = "first_speech_no_boundary"

    updated = dict(full_subtitle_understanding or {})
    updated["prologue_strategy"] = strategy
    updated["manual_prologue_end_time"] = manual_time
    updated["first_speech_time"] = first_speech_time
    updated["llm_prologue_end_time"] = full_subtitle_understanding.get("prologue_end_time", "")
    updated["resolved_prologue_end_source"] = resolved_source
    updated["resolved_prologue_end_seconds"] = resolved_time
    updated["prologue_end_time"] = (
        utils.format_time(float(resolved_time))
        if resolved_time is not None
        else str(full_subtitle_understanding.get("prologue_end_time") or "").strip()
    )
    return updated, warnings


def _ranges_overlap(start_a: float, end_a: float, start_b: float, end_b: float, slack: float = 1.5) -> bool:
    return max(start_a, start_b) <= min(end_a, end_b) + slack


def _clip_range_after_prologue(
    start: float,
    end: float,
    prologue_end: float | None,
    *,
    min_duration: float = 0.5,
) -> tuple[float, float, bool]:
    safe_start = round(float(start or 0.0), 3)
    safe_end = round(float(end or safe_start), 3)
    if safe_end <= safe_start:
        safe_end = round(safe_start + min_duration, 3)
    if prologue_end is None or safe_start >= prologue_end or safe_end <= prologue_end + min_duration:
        return safe_start, safe_end, False

    trimmed_start = round(max(safe_start, prologue_end), 3)
    if trimmed_start >= safe_end - min_duration:
        return safe_start, safe_end, False
    return trimmed_start, safe_end, trimmed_start > safe_start


def _build_prologue_metrics(start: float, end: float, prologue_end: float | None) -> Dict[str, Any]:
    safe_start = round(float(start or 0.0), 3)
    safe_end = round(float(end or safe_start), 3)
    if safe_end <= safe_start:
        safe_end = round(safe_start + 0.5, 3)
    duration = max(safe_end - safe_start, 0.1)

    if prologue_end is None:
        return {
            "before_prologue_end": False,
            "crosses_prologue_boundary": False,
            "prologue_overlap_duration": 0.0,
            "prologue_overlap_ratio": 0.0,
        }

    overlap = max(0.0, min(safe_end, prologue_end) - safe_start)
    return {
        "before_prologue_end": bool(safe_end <= prologue_end + 0.5),
        "crosses_prologue_boundary": bool(safe_start < prologue_end - 0.05 and safe_end > prologue_end + 0.05),
        "prologue_overlap_duration": round(overlap, 3),
        "prologue_overlap_ratio": round(min(overlap / duration, 1.0), 3),
    }


def _annotate_prologue_state(
    item: Dict[str, Any],
    prologue_end: float | None,
    *,
    trim_crossing: bool = False,
) -> Dict[str, Any]:
    cur = dict(item)
    start = float(cur.get("start", 0.0) or 0.0)
    end = float(cur.get("end", start) or start)
    original_metrics = _build_prologue_metrics(start, end, prologue_end)

    cur.setdefault("prologue_trimmed", False)
    if trim_crossing:
        trimmed_start, trimmed_end, trimmed = _clip_range_after_prologue(start, end, prologue_end)
        if trimmed:
            cur["prologue_trimmed"] = True
            cur["prologue_original_start"] = round(start, 3)
            cur["prologue_original_end"] = round(end, 3)
            cur["prologue_original_overlap_duration"] = original_metrics["prologue_overlap_duration"]
            cur["prologue_original_overlap_ratio"] = original_metrics["prologue_overlap_ratio"]
            cur["prologue_original_before_prologue_end"] = original_metrics["before_prologue_end"]
            cur["prologue_original_crosses_boundary"] = original_metrics["crosses_prologue_boundary"]
            cur["start"] = trimmed_start
            cur["end"] = trimmed_end

    start = float(cur.get("start", start) or start)
    end = float(cur.get("end", end) or end)
    cur.update(_build_prologue_metrics(start, end, prologue_end))
    cur["prologue_end"] = round(float(prologue_end), 3) if prologue_end is not None else None
    return cur


def _clip_range_before_story_end(
    start: float,
    end: float,
    story_end: float | None,
    *,
    min_duration: float = 0.5,
) -> tuple[float, float, bool]:
    safe_start = round(float(start or 0.0), 3)
    safe_end = round(float(end or safe_start), 3)
    if safe_end <= safe_start:
        safe_end = round(safe_start + min_duration, 3)
    if story_end is None or safe_end <= story_end or safe_start >= story_end - min_duration:
        return safe_start, safe_end, False

    trimmed_end = round(min(safe_end, story_end), 3)
    if trimmed_end <= safe_start + min_duration:
        return safe_start, safe_end, False
    return safe_start, trimmed_end, trimmed_end < safe_end


def _build_story_end_metrics(start: float, end: float, story_end: float | None) -> Dict[str, Any]:
    safe_start = round(float(start or 0.0), 3)
    safe_end = round(float(end or safe_start), 3)
    if safe_end <= safe_start:
        safe_end = round(safe_start + 0.5, 3)
    duration = max(safe_end - safe_start, 0.1)

    if story_end is None:
        return {
            "after_story_end": False,
            "crosses_story_end_boundary": False,
            "story_end_overlap_duration": 0.0,
            "story_end_overlap_ratio": 0.0,
        }

    overlap = max(0.0, safe_end - max(safe_start, story_end))
    return {
        "after_story_end": bool(safe_start >= story_end - 0.05),
        "crosses_story_end_boundary": bool(safe_start < story_end - 0.05 and safe_end > story_end + 0.05),
        "story_end_overlap_duration": round(overlap, 3),
        "story_end_overlap_ratio": round(min(overlap / duration, 1.0), 3),
    }


def _annotate_story_end_state(
    item: Dict[str, Any],
    story_end: float | None,
    *,
    trim_crossing: bool = False,
) -> Dict[str, Any]:
    cur = dict(item)
    start = float(cur.get("start", 0.0) or 0.0)
    end = float(cur.get("end", start) or start)
    original_metrics = _build_story_end_metrics(start, end, story_end)

    cur.setdefault("story_end_trimmed", False)
    if trim_crossing:
        trimmed_start, trimmed_end, trimmed = _clip_range_before_story_end(start, end, story_end)
        if trimmed:
            cur["story_end_trimmed"] = True
            cur["story_end_original_start"] = round(start, 3)
            cur["story_end_original_end"] = round(end, 3)
            cur["story_end_original_overlap_duration"] = original_metrics["story_end_overlap_duration"]
            cur["story_end_original_overlap_ratio"] = original_metrics["story_end_overlap_ratio"]
            cur["story_end_original_after_story_end"] = original_metrics["after_story_end"]
            cur["story_end_original_crosses_boundary"] = original_metrics["crosses_story_end_boundary"]
            cur["start"] = trimmed_start
            cur["end"] = trimmed_end

    start = float(cur.get("start", start) or start)
    end = float(cur.get("end", end) or end)
    cur.update(_build_story_end_metrics(start, end, story_end))
    cur["story_end"] = round(float(story_end), 3) if story_end is not None else None
    return cur


def _collect_highlight_ranges(range_items: List[Dict[str, Any]], prologue_end: float | None) -> List[Dict[str, Any]]:
    highlight_ranges = []
    for item in range_items or []:
        if not isinstance(item, dict):
            continue
        start = _parse_prompt_time(item.get("start"))
        end = _parse_prompt_time(item.get("end"))
        if start is None or end is None or end <= start:
            continue
        if prologue_end is not None:
            if end <= prologue_end + 0.5:
                continue
            if start < prologue_end:
                start = round(prologue_end, 3)
        highlight_ranges.append(
            {
                "start": start,
                "end": end,
                "reason": str(item.get("reason") or item.get("category") or "llm_highlight_window"),
                "category": str(item.get("category") or ""),
                "importance": str(item.get("importance") or "medium"),
                "raw_voice_priority": str(item.get("raw_voice_priority") or "low"),
            }
        )
    return highlight_ranges


def _clip_highlight_ranges_to_story_window(
    highlight_ranges: List[Dict[str, Any]],
    story_end: float | None,
) -> List[Dict[str, Any]]:
    if story_end is None:
        return list(highlight_ranges or [])

    clipped: List[Dict[str, Any]] = []
    for item in highlight_ranges or []:
        start = round(float(item.get("start", 0.0) or 0.0), 3)
        end = round(float(item.get("end", start) or start), 3)
        if start >= story_end - 0.05:
            continue
        end = round(min(end, story_end), 3)
        if end <= start:
            continue
        cur = dict(item)
        cur["start"] = start
        cur["end"] = end
        clipped.append(cur)
    return clipped


def _apply_full_subtitle_plan_to_chunks(
    plot_chunks: List[Dict[str, Any]],
    full_subtitle_understanding: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not plot_chunks:
        return []

    prologue_end = _parse_prompt_time(full_subtitle_understanding.get("prologue_end_time"))
    story_end = _parse_prompt_time(full_subtitle_understanding.get("story_end_time"))
    highlight_ranges = _collect_highlight_ranges(
        list(full_subtitle_understanding.get("highlight_windows") or []),
        prologue_end,
    )
    highlight_ranges = _clip_highlight_ranges_to_story_window(highlight_ranges, story_end)

    annotated: List[Dict[str, Any]] = []
    keep_indices = set()
    total = len(plot_chunks)
    for idx, chunk in enumerate(plot_chunks):
        cur = _annotate_prologue_state(chunk, prologue_end, trim_crossing=True)
        cur = _annotate_story_end_state(cur, story_end, trim_crossing=True)
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)
        overlaps = [r for r in highlight_ranges if _ranges_overlap(start, end, r["start"], r["end"], 2.0)]
        cur["llm_window_selected"] = bool(overlaps)
        cur["llm_window_reasons"] = [r["reason"] for r in overlaps]
        cur["llm_window_categories"] = [r["category"] for r in overlaps if r["category"]]
        cur["llm_chunk_boost"] = 1.0 if overlaps else 0.0
        if cur.get("after_story_end"):
            cur["llm_window_selected"] = False
            cur["llm_window_reasons"] = ["suppressed_by_story_end_boundary"]
            cur["llm_window_categories"] = []
            cur["llm_chunk_boost"] = 0.0
        if overlaps:
            if any(r.get("raw_voice_priority") == "high" for r in overlaps):
                cur["raw_voice_retain_suggestion"] = True
            if any(r.get("importance") == "high" for r in overlaps):
                cur["importance_level"] = "high"
        annotated.append(cur)

    for idx, chunk in enumerate(annotated):
        importance = str(chunk.get("importance_level") or "medium")
        plot_role = str(chunk.get("plot_role") or "")
        if chunk.get("after_story_end"):
            continue
        keep = bool(chunk.get("llm_window_selected"))
        if not keep and not chunk.get("before_prologue_end") and importance == "high":
            keep = True
        if not keep and plot_role == "ending":
            keep = True
        if keep:
            keep_indices.add(idx)
            if idx > 0:
                prev = annotated[idx - 1]
                if not prev.get("after_story_end"):
                    keep_indices.add(idx - 1)
            if idx + 1 < total:
                nxt = annotated[idx + 1]
                if not nxt.get("after_story_end"):
                    keep_indices.add(idx + 1)

    filtered = []
    for idx, chunk in enumerate(annotated):
        if chunk.get("after_story_end"):
            continue
        if idx in keep_indices or not highlight_ranges:
            filtered.append(chunk)

    non_tail = [chunk for chunk in annotated if not chunk.get("after_story_end")]
    return filtered or non_tail or annotated


def _apply_llm_highlight_plan(
    scene_evidence: List[Dict[str, Any]],
    full_subtitle_understanding: Dict[str, Any],
    llm_highlight_plan: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not scene_evidence:
        return []

    selected_ids = set(str(x) for x in (llm_highlight_plan.get("selected_segment_ids") or []) if x)
    rejected_ids = set(str(x) for x in (llm_highlight_plan.get("rejected_segment_ids") or []) if x)
    raw_voice_ids = set(str(x) for x in (llm_highlight_plan.get("raw_voice_segment_ids") or []) if x)
    selection_notes = {
        str(item.get("segment_id") or ""): str(item.get("reason") or "")
        for item in (llm_highlight_plan.get("selection_notes") or [])
        if isinstance(item, dict) and item.get("segment_id")
    }

    prologue_end = _parse_prompt_time(full_subtitle_understanding.get("prologue_end_time"))
    story_end = _parse_prompt_time(full_subtitle_understanding.get("story_end_time"))
    highlight_ranges = _collect_highlight_ranges(
        list(full_subtitle_understanding.get("highlight_windows") or []) + list(llm_highlight_plan.get("must_keep_ranges") or []),
        prologue_end,
    )
    highlight_ranges = _clip_highlight_ranges_to_story_window(highlight_ranges, story_end)

    enriched: List[Dict[str, Any]] = []
    for pkg in scene_evidence:
        cur = _annotate_prologue_state(pkg, prologue_end, trim_crossing=True)
        cur = _annotate_story_end_state(cur, story_end, trim_crossing=True)
        seg_id = str(cur.get("segment_id") or "")
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)

        overlapping = [r for r in highlight_ranges if _ranges_overlap(start, end, r["start"], r["end"])]
        llm_selected = seg_id in selected_ids or bool(overlapping)
        llm_rejected = seg_id in rejected_ids
        if llm_rejected and seg_id not in selected_ids:
            llm_selected = False

        raw_voice_keep = seg_id in raw_voice_ids
        if not raw_voice_keep and overlapping:
            raw_voice_keep = any(r.get("raw_voice_priority") == "high" for r in overlapping)

        if cur.get("before_prologue_end"):
            llm_selected = False
            raw_voice_keep = False
        if cur.get("after_story_end"):
            llm_selected = False
            raw_voice_keep = False

        cur["llm_highlight_selected"] = llm_selected
        cur["llm_highlight_rejected"] = llm_rejected
        if cur.get("before_prologue_end"):
            cur["llm_highlight_reason"] = "suppressed_by_prologue_boundary"
        elif cur.get("after_story_end"):
            cur["llm_highlight_reason"] = "suppressed_by_story_end_boundary"
        else:
            cur["llm_highlight_reason"] = selection_notes.get(seg_id) or "; ".join(r["reason"] for r in overlapping[:3])
        cur["llm_highlight_window_count"] = len(overlapping)
        cur["llm_raw_voice_keep"] = raw_voice_keep
        enriched.append(cur)

    return enriched


def _final_story_score(pkg: Dict, index: int, total: int) -> float:
    score = 0.0
    importance = str(pkg.get("importance_level") or "medium")
    plot_function = str(pkg.get("plot_function") or "")
    block_type = str(pkg.get("block_type") or "dialogue")
    boundary_confidence = str(pkg.get("boundary_confidence") or "medium")
    validator = pkg.get("story_validation") or {}
    validator_status = str(validator.get("validator_status") or "pass")
    duration = max(float(pkg.get("end", 0.0) or 0.0) - float(pkg.get("start", 0.0) or 0.0), 0.0)
    text = str(pkg.get("subtitle_text") or pkg.get("main_text_evidence") or "")

    if importance == "high":
        score += 3.0
    elif importance == "medium":
        score += 1.4
    else:
        score -= 0.8

    if plot_function in {"\u53cd\u8f6c", "\u60c5\u611f\u7206\u53d1", "\u7ed3\u5c40\u6536\u675f", "\u51b2\u7a81\u5347\u7ea7"}:
        score += 1.8
    elif plot_function in {"\u4fe1\u606f\u63ed\u9732"}:
        score += 0.8
    elif plot_function in {"\u94fa\u57ab", "\u8282\u594f\u7f13\u51b2"}:
        score -= 1.0

    if block_type in {"action", "emotion", "visual"}:
        score += 0.8
    elif block_type == "transition":
        score -= 1.0

    if boundary_confidence == "high":
        score += 0.5
    elif boundary_confidence == "low":
        score -= 0.8

    if validator_status == "pass":
        score += 0.4
    elif validator_status == "review":
        score -= 0.3
    elif validator_status == "risky":
        score -= 1.2

    if pkg.get("raw_voice_retain_suggestion"):
        score += 0.5
    if pkg.get("need_visual_verify"):
        score += 0.2
    if pkg.get("llm_highlight_selected"):
        score += 2.2
    if pkg.get("llm_highlight_rejected"):
        score -= 2.5
    if pkg.get("llm_raw_voice_keep"):
        score += 0.8
    if pkg.get("before_prologue_end") and not pkg.get("llm_highlight_selected"):
        score -= 2.0
    if pkg.get("after_story_end"):
        score -= 3.0

    if duration >= 40.0:
        score -= 0.6
    elif 4.0 <= duration <= 24.0:
        score += 0.3

    if len(text.strip()) < 10:
        score -= 0.5
    if index <= max(1, int(total * 0.12)) and plot_function == "\u94fa\u57ab":
        score -= 1.5

    return round(score, 3)


def _select_final_story_evidence(scene_evidence: List[Dict]) -> List[Dict]:
    if not scene_evidence:
        return []

    total = len(scene_evidence)
    scored: List[Dict] = []
    keep_indices = set()

    for idx, item in enumerate(scene_evidence):
        cur = dict(item)
        cur["final_story_score"] = _final_story_score(cur, idx + 1, total)
        scored.append(cur)

    for idx, item in enumerate(scored):
        importance = str(item.get("importance_level") or "medium")
        plot_function = str(item.get("plot_function") or "")
        validator_status = str((item.get("story_validation") or {}).get("validator_status") or "pass")
        block_type = str(item.get("block_type") or "dialogue")
        score = float(item.get("final_story_score", 0.0) or 0.0)

        hard_keep = (
            importance == "high"
            or plot_function in {"\u53cd\u8f6c", "\u60c5\u611f\u7206\u53d1", "\u7ed3\u5c40\u6536\u675f"}
            or item.get("raw_voice_retain_suggestion")
            or item.get("llm_highlight_selected")
        )
        should_drop = (
            score < 0.9
            and importance == "low"
            and plot_function in {"\u94fa\u57ab", "\u8282\u594f\u7f13\u51b2"}
            and block_type in {"transition", "dialogue"}
        )
        if item.get("before_prologue_end") and not item.get("llm_highlight_selected"):
            hard_keep = False
        if item.get("after_story_end"):
            hard_keep = False
        if validator_status == "risky" and importance != "high":
            should_drop = True
        if item.get("llm_highlight_rejected") and importance != "high":
            should_drop = True
        if item.get("before_prologue_end") and not item.get("llm_highlight_selected"):
            should_drop = True
        if item.get("after_story_end"):
            should_drop = True

        selected = hard_keep or (score >= 1.6 and not should_drop)
        item["selected_for_final_story"] = selected
        item["final_story_drop_reason"] = "" if selected else "low_value_or_risky_segment"

    for idx, item in enumerate(scored):
        if not item.get("selected_for_final_story"):
            continue
        keep_indices.add(idx)

        # Preserve a bit of local context so transitions don't become incomprehensible.
        if idx > 0:
            prev = scored[idx - 1]
            if (
                not prev.get("before_prologue_end")
                and not prev.get("prologue_original_before_prologue_end")
                and not prev.get("after_story_end")
                and str(prev.get("importance_level") or "low") != "low"
                and str((prev.get("story_validation") or {}).get("validator_status") or "pass") != "risky"
            ):
                keep_indices.add(idx - 1)
        if idx + 1 < total:
            nxt = scored[idx + 1]
            if (
                not nxt.get("before_prologue_end")
                and not nxt.get("prologue_original_before_prologue_end")
                and not nxt.get("after_story_end")
                and str(nxt.get("importance_level") or "low") != "low"
                and str((nxt.get("story_validation") or {}).get("validator_status") or "pass") != "risky"
            ):
                keep_indices.add(idx + 1)

    selected: List[Dict] = []
    for idx, item in enumerate(scored):
        if item.get("before_prologue_end") and not item.get("llm_highlight_selected"):
            continue
        if item.get("after_story_end"):
            continue
        if idx in keep_indices:
            item["selected_for_final_story"] = True
            item["final_story_drop_reason"] = ""
            selected.append(item)

    if len(selected) < min(3, total):
        fallback_candidates = [
            item
            for item in scored
            if (
                not item.get("before_prologue_end")
                and not item.get("prologue_original_before_prologue_end")
                and not item.get("after_story_end")
            )
        ]
        if not fallback_candidates:
            fallback_candidates = [
                item for item in scored if not item.get("before_prologue_end") and not item.get("after_story_end")
            ]
        fallback = sorted(
            fallback_candidates,
            key=lambda x: float(x.get("final_story_score", 0.0) or 0.0),
            reverse=True,
        )[: min(5, len(fallback_candidates))]
        if fallback:
            selected = sorted(
                fallback,
                key=lambda x: float(x.get("start", 0.0) or 0.0),
            )
            for item in selected:
                item["selected_for_final_story"] = True
                item["final_story_drop_reason"] = ""

    if not selected:
        relaxed_fallback = [item for item in scored if not item.get("after_story_end")]
        if not relaxed_fallback:
            relaxed_fallback = list(scored)
        relaxed_fallback = sorted(
            relaxed_fallback,
            key=lambda x: (
                bool(x.get("llm_highlight_selected")),
                bool(x.get("raw_voice_retain_suggestion")),
                float(x.get("final_story_score", 0.0) or 0.0),
            ),
            reverse=True,
        )[: min(max(3, min(5, total)), len(relaxed_fallback))]
        selected = sorted(
            relaxed_fallback,
            key=lambda x: float(x.get("start", 0.0) or 0.0),
        )
        for item in selected:
            item["selected_for_final_story"] = True
            item["final_story_drop_reason"] = ""
        logger.warning(
            "\u6700\u7ec8\u8bc1\u636e\u7b5b\u9009\u89e6\u53d1\u653e\u5bbd\u5160\u5e95: raw=%s, selected=%s",
            total,
            len(selected),
        )

    logger.info(
        "\u6700\u7ec8\u8bc1\u636e\u7b5b\u9009\u5b8c\u6210: raw=%s, selected=%s, dropped=%s",
        total,
        len(selected),
        max(total - len(selected), 0),
    )
    return selected


def _run(
    video_path: str,
    subtitle_path: str,
    text_api_key: str,
    text_base_url: str,
    text_model: str,
    style: str,
    output_script_path: str,
    generation_mode: str,
    visual_mode: str,
    scene_overrides: Dict[str, Any],
    progress: Callable[[int, str], None],
    asr_backend: str,
    regenerate_subtitle: bool,
) -> Dict[str, Any]:
    # 确保 LLM 配置就绪（从参数或配置读取）
    text_api_key, text_base_url, text_model = _ensure_llm_ready(text_api_key, text_base_url, text_model)
    asr_backend = str(asr_backend or "faster-whisper").strip() or "faster-whisper"
    target_minutes = _resolve_target_minutes(generation_mode, scene_overrides)
    effective_visual_mode = _resolve_visual_mode(visual_mode or scene_overrides.get("visual_mode", "auto"))
    highlight_only = bool(scene_overrides.get("highlight_only", False))
    highlight_selectivity = _resolve_highlight_selectivity(scene_overrides.get("highlight_selectivity", "balanced"))
    narrative_strategy = str(scene_overrides.get("narrative_strategy") or "chronological")
    accuracy_priority = str(scene_overrides.get("accuracy_priority") or "high")
    video_title = str(scene_overrides.get("video_title") or scene_overrides.get("short_name") or "").strip()

    progress(10, "字幕解析与标准化...")
    
    # 启动一个后台线程来模拟字幕识别进度（因为 build_subtitle_segments 没有进度回调）
    import threading
    import time
    
    stop_progress_simulator = threading.Event()
    def simulate_subtitle_progress():
        """模拟字幕识别进度，从 10% 到 16%"""
        for i in range(11, 17):  # 11% 到 16%
            if stop_progress_simulator.wait(2):  # 每 2 秒更新一次
                break
            progress(i, f"字幕识别中... ({i}%)")
    
    # 启动进度模拟线程
    progress_thread = threading.Thread(target=simulate_subtitle_progress)
    progress_thread.start()
    
    try:
        sub_result = build_subtitle_segments(
            video_path=video_path,
            explicit_subtitle_path=subtitle_path,
            regenerate=regenerate_subtitle,
            backend_override=asr_backend,
        )
    finally:
        # 停止进度模拟
        stop_progress_simulator.set()
        progress_thread.join(timeout=1)
    
    segments = sub_result.get("segments") or []
    if not segments:
        raise ValueError(f"无法获取有效字幕 (source={sub_result.get('source')}, error={sub_result.get('error', '')})")

    logger.info(
        "影视解说 M1 完成: source={}, backend={}, regenerate={}, segments={}, subtitle_path={}",
        sub_result.get("source"),
        sub_result.get("backend"),
        sub_result.get("regenerate"),
        len(segments),
        sub_result.get("subtitle_path", ""),
    )

    progress(18, "整字幕剧情理解与高光规划...")
    full_subtitle_understanding = build_full_subtitle_understanding(
        segments,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
    )
    full_subtitle_understanding, prologue_warnings = _resolve_prologue_end_from_strategy(
        full_subtitle_understanding=full_subtitle_understanding,
        subtitle_segments=segments,
        scene_overrides=scene_overrides,
    )
    full_subtitle_understanding, tail_warnings = _resolve_story_end_from_tail_markers(
        full_subtitle_understanding=full_subtitle_understanding,
        subtitle_segments=segments,
    )

    progress(22, "检测视频候选边界...")
    video_boundary_candidates: List[Dict[str, Any]] = []
    if effective_visual_mode != "off":
        video_boundary_candidates = build_video_boundary_candidates(
            video_path=video_path,
            subtitle_segments=segments,
            threshold=float(scene_overrides.get("scene_threshold", 27.0) or 27.0),
            min_scene_len=float(scene_overrides.get("min_scene_len", 2.0) or 2.0),
            merge_window_sec=float(scene_overrides.get("boundary_merge_window_sec", 2.0) or 2.0),
        )

    progress(28, "字幕粗分段与剧情块规划...")
    plot_chunks = build_plot_chunks_from_subtitles(
        segments,
        target_duration_minutes=target_minutes,
        narrative_strategy=narrative_strategy,
        accuracy_priority=accuracy_priority,
        highlight_selectivity=highlight_selectivity,
        video_candidates=video_boundary_candidates,
        refine_chunks=True,
    )
    if not plot_chunks:
        raise ValueError("剧情块规划失败，未生成任何剧情块")
    logger.info("影视解说 M2 完成: {} 个剧情块", len(plot_chunks))

    progress(36, "整剧理解...")
    global_summary = build_global_summary(
        plot_chunks,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
    )
    global_summary.update(
        {
            "target_duration_minutes": target_minutes,
            "narrative_strategy": narrative_strategy,
            "accuracy_priority": accuracy_priority,
            "video_title": video_title,
            "full_subtitle_understanding": full_subtitle_understanding,
        }
    )

    progress(46, "剧情边界吸附...")
    subtitle_boundaries = collect_candidate_boundaries(segments)
    candidate_boundaries = list(subtitle_boundaries) + list(video_boundary_candidates)
    plot_chunks = align_story_boundaries(
        plot_chunks,
        candidate_boundaries=candidate_boundaries,
        snap_window=float(scene_overrides.get("boundary_merge_window_sec", 2.0) or 2.0),
    )
    plot_chunks = _apply_full_subtitle_plan_to_chunks(plot_chunks, full_subtitle_understanding)

    progress(56, "按剧情块抽取代表帧...")
    frame_output_dir = os.path.join(utils.temp_dir("story_frames"), utils.md5(video_path))
    os.makedirs(frame_output_dir, exist_ok=True)

    frame_records: List[Dict[str, Any]] = []
    if effective_visual_mode != "off":
        frame_records = extract_representative_frames_for_scenes(
            video_path=video_path,
            scenes=plot_chunks,
            visual_mode=effective_visual_mode,
            output_dir=frame_output_dir,
            max_frames_dialogue=1,
            max_frames_visual_only=3,
            max_frames_long_scene=3,
            long_scene_threshold=25.0,
        )
    logger.info("影视解说 M3 完成: {} 张代表帧", len(frame_records))

    progress(68, "构建剧情证据与局部理解...")
    scene_evidence = fuse_scene_evidence(
        scenes=plot_chunks,
        frame_records=frame_records,
        visual_observations={},
    )
    _enrich_evidence(scene_evidence, plot_chunks, global_summary)
    scene_evidence = add_local_understanding(
        scene_evidence,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
    )
    logger.info("影视解说 M4 完成: evidence={}", len(scene_evidence))

    progress(78, "剧情核对...")
    scene_evidence = validate_story_segments(
        scene_evidence,
        global_summary=global_summary,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
    )
    llm_highlight_plan = plan_story_highlights(
        scene_evidence,
        global_summary=global_summary,
        full_subtitle_summary=full_subtitle_understanding,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
    )
    scene_evidence = _apply_llm_highlight_plan(scene_evidence, full_subtitle_understanding, llm_highlight_plan)
    scene_evidence = _select_final_story_evidence(scene_evidence)
    scene_cut_points: List[float] = []
    if effective_visual_mode != "off":
        scene_cut_points = _collect_scene_cut_points(video_path, segments, scene_overrides)
    story_highlights = _extract_story_highlights(
        scene_evidence,
        scene_cut_points,
        highlight_selectivity=highlight_selectivity,
    )
    highlight_frame_records: List[Dict[str, Any]] = []
    if highlight_only and story_highlights and effective_visual_mode != "off":
        progress(84, "为高光片段抽取代表帧...")
        highlight_frame_output_dir = os.path.join(utils.temp_dir("story_highlight_frames"), utils.md5(video_path))
        os.makedirs(highlight_frame_output_dir, exist_ok=True)
        highlight_frame_records = extract_representative_frames_for_scenes(
            video_path=video_path,
            scenes=_prepare_highlight_frame_targets(story_highlights),
            visual_mode=effective_visual_mode,
            output_dir=highlight_frame_output_dir,
            max_frames_dialogue=3,
            max_frames_visual_only=4,
            max_frames_long_scene=4,
            long_scene_threshold=18.0,
        )
        logger.info("高光片段代表帧抽取完成: {} 张", len(highlight_frame_records))
    highlight_narration_segments = _build_highlight_narration_segments(
        story_highlights=story_highlights,
        scene_evidence=scene_evidence,
        highlight_frame_records=highlight_frame_records,
        global_summary=global_summary,
    )
    full_subtitle_understanding = _ensure_full_subtitle_highlight_windows(
        full_subtitle_understanding=full_subtitle_understanding,
        llm_highlight_plan=llm_highlight_plan,
        story_highlights=story_highlights,
    )
    global_summary["full_subtitle_understanding"] = full_subtitle_understanding
    if full_subtitle_understanding.get("highlight_windows_backfilled"):
        logger.warning(
            "整字幕高光窗口缺失，已使用后续链路结果回填: source={}, count={}",
            full_subtitle_understanding.get("highlight_windows_source"),
            len(full_subtitle_understanding.get("highlight_windows") or []),
        )

    progress(88, "生成影视解说脚本..." if not highlight_only else "生成高光验证脚本...")
    if highlight_only:
        script_items = _build_highlight_only_script(highlight_narration_segments)
    else:
        script_items = generate_narration_from_scene_evidence(
            scene_evidence=scene_evidence,
            api_key=text_api_key,
            base_url=text_base_url,
            model=text_model,
            style=style or "general",
            video_title=video_title,
        )
    if not script_items:
        raise ValueError("未生成有效脚本片段")

    if effective_visual_mode != "off":
        script_items = _align_script_items_to_scene_cuts(script_items, scene_cut_points)

    script_items = ensure_script_shape(script_items)
    script_items = _filter_script_items_by_highlights(script_items, story_highlights)
    script_items = ensure_script_shape(script_items)

    quality_issues = _validate_pipeline_quality(
        full_subtitle_understanding=full_subtitle_understanding,
        llm_highlight_plan=llm_highlight_plan,
        story_highlights=story_highlights,
        script_items=script_items,
        highlight_only=highlight_only,
        highlight_selectivity=highlight_selectivity,
    )

    warnings: List[str] = list(prologue_warnings) + list(tail_warnings)
    if full_subtitle_understanding.get("highlight_windows_backfilled"):
        warnings.append(f"highlight_windows_backfilled:{full_subtitle_understanding.get('highlight_windows_source')}")
    try:
        validate_script_items(script_items)
    except PreflightError as exc:
        warnings.append(str(exc))
        logger.warning("影视解说脚本预检警告: {}", exc)

    progress(96, "保存脚本文件...")
    if not output_script_path:
        video_hash = utils.md5(video_path + str(os.path.getmtime(video_path)))
        output_script_path = os.path.join(utils.script_dir(), f"{video_hash}_movie_story.json")

    os.makedirs(os.path.dirname(output_script_path), exist_ok=True)
    with open(output_script_path, "w", encoding="utf-8") as f:
        json.dump(script_items, f, ensure_ascii=False, indent=2)

    highlights_path = output_script_path.replace(".json", "_highlights.json")
    with open(highlights_path, "w", encoding="utf-8") as f:
        json.dump(story_highlights, f, ensure_ascii=False, indent=2)

    highlight_script_path = output_script_path.replace(".json", "_highlight_script.json")
    with open(highlight_script_path, "w", encoding="utf-8") as f:
        json.dump(script_items, f, ensure_ascii=False, indent=2)

    highlight_narration_segments_path = output_script_path.replace(".json", "_highlight_narration_segments.json")
    with open(highlight_narration_segments_path, "w", encoding="utf-8") as f:
        json.dump(highlight_narration_segments, f, ensure_ascii=False, indent=2)

    audit_path = output_script_path.replace(".json", "_audit.json")
    audit_payload = _build_story_audit_payload(
        video_path=video_path,
        subtitle_result=sub_result,
        highlight_only_mode=highlight_only,
        full_subtitle_understanding=full_subtitle_understanding,
        global_summary=global_summary,
        plot_chunks=plot_chunks,
        selected_scene_evidence=scene_evidence,
        story_highlights=story_highlights,
        highlight_narration_segments=highlight_narration_segments,
        llm_highlight_plan=llm_highlight_plan,
        script_items=script_items,
        scene_cut_points=scene_cut_points,
        video_boundary_candidates=video_boundary_candidates,
        frame_records=frame_records,
        highlight_frame_records=highlight_frame_records,
        quality_issues=quality_issues,
        warnings=warnings,
    )
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_payload, f, ensure_ascii=False, indent=2)

    if quality_issues:
        raise ValueError("；".join(quality_issues))

    progress(100, "影视解说主链完成")
    return {
        "script_items": script_items,
        "script_path": output_script_path,
        "composition_script_path": highlight_script_path,
        "highlights_path": highlights_path,
        "highlight_script_path": highlight_script_path,
        "highlight_narration_segments_path": highlight_narration_segments_path,
        "highlight_only_ready": True,
        "highlight_only_mode": highlight_only,
        "audit_path": audit_path,
        "evidence": scene_evidence,
        "selected_scene_evidence": scene_evidence,
        "story_highlights": story_highlights,
        "highlight_narration_segments": highlight_narration_segments,
        "full_subtitle_understanding": full_subtitle_understanding,
        "llm_highlight_plan": llm_highlight_plan,
        "global_summary": global_summary,
        "generation_mode": generation_mode,
        "visual_mode": effective_visual_mode,
        "subtitle_path": sub_result.get("subtitle_path", ""),
        "original_subtitle_path": sub_result.get("original_subtitle_path", ""),
        "raw_subtitle_path": sub_result.get("raw_subtitle_path", ""),
        "clean_subtitle_path": sub_result.get("clean_subtitle_path", ""),
        "subtitle_segments_path": sub_result.get("subtitle_segments_path", ""),
        "subtitle_source": sub_result.get("source", "none"),
        "subtitle_backend": sub_result.get("backend", ""),
        "subtitle_regenerate": sub_result.get("regenerate", False),
        "subtitle_segments": len(segments),
        "generated_saved_subtitle_path": sub_result.get("generated_saved_path", ""),
        "generated_temp_subtitle_path": sub_result.get("generated_temp_path", ""),
        "plot_chunks": plot_chunks,
        "selected_plot_chunks": [
            chunk for chunk in plot_chunks
            if any((pkg.get("scene_id") == chunk.get("scene_id")) for pkg in scene_evidence)
        ],
        "scene_cut_points": scene_cut_points,
        "video_boundary_candidates": video_boundary_candidates,
        "video_boundary_candidate_count": len(video_boundary_candidates),
        "frame_records": frame_records,
        "highlight_frame_records": highlight_frame_records,
        "story_validation": [x.get("story_validation") for x in scene_evidence if x.get("story_validation")],
        "warnings": warnings,
        "success": True,
        "error": "",
    }


def _enrich_evidence(evidence: List[Dict], chunks: List[Dict], global_summary: Dict) -> None:
    scene_map = {s["scene_id"]: s for s in chunks}
    for pkg in evidence:
        aligned = scene_map.get(pkg.get("scene_id") or pkg.get("segment_id"), {})
        aligned_text = aligned.get("aligned_subtitle_text", "")
        if aligned_text:
            pkg["subtitle_text"] = aligned_text
        pkg["main_text_evidence"] = aligned_text
        pkg["visual_only"] = aligned.get("visual_only", False)
        pkg["evidence_mode"] = "movie_story"
        pkg["plot_role"] = aligned.get("plot_role")
        pkg["plot_function"] = aligned.get("plot_function")
        pkg["block_type"] = aligned.get("block_type")
        pkg["importance_level"] = aligned.get("importance_level")
        pkg["attraction_level"] = aligned.get("attraction_level")
        pkg["planned_char_budget"] = aligned.get("planned_char_budget")
        pkg["audio_strategy"] = aligned.get("audio_strategy")
        pkg["narration_level"] = aligned.get("narration_level")
        pkg["target_duration_minutes"] = aligned.get("target_duration_minutes")
        pkg["narrative_strategy"] = aligned.get("narrative_strategy")
        pkg["accuracy_priority"] = aligned.get("accuracy_priority")
        pkg["surface_dialogue_meaning"] = aligned.get("surface_dialogue_meaning")
        pkg["real_narrative_state"] = aligned.get("real_narrative_state")
        pkg["need_visual_verify"] = aligned.get("need_visual_verify", False)
        pkg["boundary_source"] = aligned.get("boundary_source")
        pkg["boundary_confidence"] = aligned.get("boundary_confidence")
        pkg["boundary_reasons"] = aligned.get("boundary_reasons") or []
        pkg["narrative_risk_flags"] = aligned.get("narrative_risk_flags") or []
        pkg["raw_voice_retain_suggestion"] = aligned.get("raw_voice_retain_suggestion", False)
        pkg["_global_summary"] = global_summary
