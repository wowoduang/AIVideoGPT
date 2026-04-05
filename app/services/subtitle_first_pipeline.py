from __future__ import annotations

import json
import os
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
from app.services.story_boundary_aligner import align_story_boundaries, collect_candidate_boundaries
from app.services.story_validator_clean import validate_story_segments
from app.services.subtitle_pipeline import build_subtitle_segments
from app.utils import utils


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


def _ensure_llm_ready(api_key: str, base_url: str, model: str) -> None:
    missing = []
    if not str(api_key or "").strip():
        missing.append("text_api_key")
    if not str(base_url or "").strip():
        missing.append("text_base_url")
    if not str(model or "").strip():
        missing.append("text_model")
    if missing:
        raise ValueError(f"字幕优先影视解说链需要完整的 LLM 配置，缺少: {', '.join(missing)}")


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
) -> Dict[str, Any]:
    semantic_start = round(float(start or 0.0), 3)
    semantic_end = round(float(end or semantic_start), 3)
    if semantic_end <= semantic_start:
        semantic_end = round(semantic_start + 0.5, 3)

    intervals = _build_scene_intervals(cut_points)
    if not intervals:
        return {
            "start": semantic_start,
            "end": semantic_end,
            "scene_group_count": 0,
            "scene_group_ranges": [],
            "scene_group_mode": "semantic_keep",
        }

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
        return {
            "start": snapped_start,
            "end": snapped_end,
            "scene_group_count": 0,
            "scene_group_ranges": [],
            "scene_group_mode": "cut_snap_fallback",
        }

    aligned_start = round(min(x[0] for x in overlapping), 3)
    aligned_end = round(max(x[1] for x in overlapping), 3)
    return {
        "start": aligned_start,
        "end": aligned_end,
        "scene_group_count": len(overlapping),
        "scene_group_ranges": [[round(left, 3), round(right, 3)] for left, right in overlapping],
        "scene_group_mode": "scene_group",
    }


def _align_script_items_to_scene_cuts(
    script_items: List[Dict],
    cut_points: List[float],
    *,
    narration_window: float = 2.0,
    raw_voice_window: float = 8.0,
) -> List[Dict]:
    if not script_items:
        return []

    aligned: List[Dict] = []
    for item in script_items:
        cur = dict(item)
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)
        ost = int(cur.get("OST", 2) or 2)
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
) -> List[Dict[str, Any]]:
    if not scene_evidence:
        return []

    raw: List[Dict[str, Any]] = []
    for pkg in scene_evidence:
        score = float(pkg.get("final_story_score", 0.0) or 0.0)
        importance = str(pkg.get("importance_level") or "medium")
        plot_function = str(pkg.get("plot_function") or "")
        block_type = str(pkg.get("block_type") or "dialogue")
        validator_status = str((pkg.get("story_validation") or {}).get("validator_status") or "pass")
        attraction = str(pkg.get("attraction_level") or "")

        if validator_status == "risky" and importance != "high":
            continue
        if score < 1.6 and importance != "high" and plot_function not in {"反转", "情感爆发", "结局收束", "冲突升级"}:
            continue

        semantic_start = round(float(pkg.get("start", 0.0) or 0.0), 3)
        semantic_end = round(float(pkg.get("end", semantic_start) or semantic_start), 3)
        raw_voice_keep = bool(pkg.get("llm_raw_voice_keep")) or (
            bool(pkg.get("raw_voice_retain_suggestion"))
            and plot_function in {"情感爆发", "反转", "结局收束"}
            and importance == "high"
        )
        snap_window = 8.0 if raw_voice_keep else (4.0 if importance == "high" else 2.5)
        grouped = _align_range_to_scene_group(
            semantic_start,
            semantic_end,
            cut_points,
            lead_window=snap_window,
            tail_window=snap_window,
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
        if attraction in {"高", "high"}:
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
        seg_id = str(cur.get("segment_id") or "")
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)
        semantic_start = float(cur.get("semantic_start", start) or start)
        semantic_end = float(cur.get("semantic_end", end) or end)

        keep = seg_id in allowed_segment_ids
        if not keep:
            keep = any(
                _ranges_overlap(start, end, left, right, overlap_slack)
                or _ranges_overlap(semantic_start, semantic_end, left, right, overlap_slack)
                for left, right in allowed_ranges
            )

        if keep:
            kept.append(cur)

    if not kept:
        return script_items

    for idx, item in enumerate(kept, start=1):
        item["_id"] = idx
    return kept


def _build_highlight_only_script(story_highlights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for idx, item in enumerate(story_highlights, start=1):
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start) or start)
        if end <= start:
            end = start + 0.5
        reasons = " / ".join(item.get("highlight_reasons") or [])
        picture = reasons[:80] or "高光片段"
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
                "segment_id": "+".join(item.get("segment_ids") or []) or item.get("highlight_id"),
                "scene_id": item.get("highlight_id"),
                "plot_function": ",".join(item.get("plot_functions") or []),
                "importance_level": item.get("importance_level", "high"),
                "llm_highlight_selected": True,
                "llm_raw_voice_keep": bool(item.get("raw_voice_retain")),
                "scene_align_mode": item.get("scene_align_mode"),
                "scene_group_count": item.get("scene_group_count", 0),
                "scene_group_ranges": item.get("scene_group_ranges", []),
                "scene_group_mode": item.get("scene_group_mode", ""),
                "highlight_id": item.get("highlight_id"),
                "highlight_rank": item.get("highlight_rank"),
                "highlight_reasons": item.get("highlight_reasons") or [],
                "char_budget": 0,
                "fit_check": {"status": "highlight_only", "target_chars": 0, "actual_chars": 0},
                "narration_validation": {"status": "skip", "issues": [], "safe_rewrite_hint": "", "raw_voice_keep": True},
            }
        )
    return items


def _validate_pipeline_quality(
    *,
    full_subtitle_understanding: Dict[str, Any],
    llm_highlight_plan: Dict[str, Any],
    story_highlights: List[Dict[str, Any]],
    script_items: List[Dict[str, Any]],
    highlight_only: bool,
) -> List[str]:
    issues: List[str] = []

    highlight_windows = list(full_subtitle_understanding.get("highlight_windows") or [])
    selected_segment_ids = list(llm_highlight_plan.get("selected_segment_ids") or [])
    raw_voice_segment_ids = set(str(x) for x in (llm_highlight_plan.get("raw_voice_segment_ids") or []) if x)

    if not highlight_windows:
        issues.append("整字幕理解未产出高光窗口")
    if not selected_segment_ids and not highlight_windows:
        issues.append("精细段高光选择未产出入选结果")
    if len(story_highlights) < 2:
        issues.append("最终高光片段过少")

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
            if not item.get("llm_highlight_selected"):
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
    llm_highlight_plan: Dict[str, Any],
    script_items: List[Dict[str, Any]],
    scene_cut_points: List[float],
    video_boundary_candidates: List[Dict[str, Any]],
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
        "llm_highlight_plan": llm_highlight_plan,
        "script_items": script_items,
        "scene_cut_points": scene_cut_points,
        "video_boundary_candidates": video_boundary_candidates,
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


def _ranges_overlap(start_a: float, end_a: float, start_b: float, end_b: float, slack: float = 1.5) -> bool:
    return max(start_a, start_b) <= min(end_a, end_b) + slack


def _apply_full_subtitle_plan_to_chunks(
    plot_chunks: List[Dict[str, Any]],
    full_subtitle_understanding: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not plot_chunks:
        return []

    prologue_end = _parse_prompt_time(full_subtitle_understanding.get("prologue_end_time"))
    highlight_ranges = []
    for item in full_subtitle_understanding.get("highlight_windows") or []:
        if not isinstance(item, dict):
            continue
        start = _parse_prompt_time(item.get("start"))
        end = _parse_prompt_time(item.get("end"))
        if start is None or end is None or end <= start:
            continue
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

    annotated: List[Dict[str, Any]] = []
    keep_indices = set()
    total = len(plot_chunks)
    for idx, chunk in enumerate(plot_chunks):
        cur = dict(chunk)
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)
        overlaps = [r for r in highlight_ranges if _ranges_overlap(start, end, r["start"], r["end"], 2.0)]
        cur["llm_window_selected"] = bool(overlaps)
        cur["llm_window_reasons"] = [r["reason"] for r in overlaps]
        cur["llm_window_categories"] = [r["category"] for r in overlaps if r["category"]]
        cur["before_prologue_end"] = bool(prologue_end is not None and end <= prologue_end + 0.5)
        cur["llm_chunk_boost"] = 1.0 if overlaps else 0.0
        if overlaps:
            if any(r.get("raw_voice_priority") == "high" for r in overlaps):
                cur["raw_voice_retain_suggestion"] = True
            if any(r.get("importance") == "high" for r in overlaps):
                cur["importance_level"] = "high"
        annotated.append(cur)

    for idx, chunk in enumerate(annotated):
        importance = str(chunk.get("importance_level") or "medium")
        plot_role = str(chunk.get("plot_role") or "")
        keep = bool(chunk.get("llm_window_selected"))
        if not keep and not chunk.get("before_prologue_end") and importance == "high":
            keep = True
        if not keep and plot_role == "ending":
            keep = True
        if keep:
            keep_indices.add(idx)
            if idx > 0:
                keep_indices.add(idx - 1)
            if idx + 1 < total:
                keep_indices.add(idx + 1)

    filtered = []
    for idx, chunk in enumerate(annotated):
        if idx in keep_indices or not highlight_ranges:
            filtered.append(chunk)

    return filtered or annotated


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

    highlight_ranges = []
    for item in (full_subtitle_understanding.get("highlight_windows") or []) + (llm_highlight_plan.get("must_keep_ranges") or []):
        if not isinstance(item, dict):
            continue
        start = _parse_prompt_time(item.get("start"))
        end = _parse_prompt_time(item.get("end"))
        if start is None or end is None or end <= start:
            continue
        highlight_ranges.append(
            {
                "start": start,
                "end": end,
                "reason": str(item.get("reason") or item.get("category") or "llm_highlight_window"),
                "raw_voice_priority": str(item.get("raw_voice_priority") or "low"),
            }
        )

    prologue_end = _parse_prompt_time(full_subtitle_understanding.get("prologue_end_time"))

    enriched: List[Dict[str, Any]] = []
    for pkg in scene_evidence:
        cur = dict(pkg)
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

        cur["llm_highlight_selected"] = llm_selected
        cur["llm_highlight_rejected"] = llm_rejected
        cur["llm_highlight_reason"] = selection_notes.get(seg_id) or "; ".join(r["reason"] for r in overlapping[:3])
        cur["llm_highlight_window_count"] = len(overlapping)
        cur["llm_raw_voice_keep"] = raw_voice_keep
        cur["before_prologue_end"] = bool(prologue_end is not None and end <= prologue_end + 0.5)
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

    if plot_function in {"反转", "情感爆发", "结局收束", "冲突升级"}:
        score += 1.8
    elif plot_function in {"信息揭露"}:
        score += 0.8
    elif plot_function in {"铺垫", "节奏缓冲"}:
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

    if duration >= 40.0:
        score -= 0.6
    elif 4.0 <= duration <= 24.0:
        score += 0.3

    if len(text.strip()) < 10:
        score -= 0.5
    if index <= max(1, int(total * 0.12)) and plot_function == "铺垫":
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
            or plot_function in {"反转", "情感爆发", "结局收束"}
            or item.get("raw_voice_retain_suggestion")
            or item.get("llm_highlight_selected")
        )
        should_drop = (
            score < 0.9
            and importance == "low"
            and plot_function in {"铺垫", "节奏缓冲"}
            and block_type in {"transition", "dialogue"}
        )
        if validator_status == "risky" and importance != "high":
            should_drop = True
        if item.get("llm_highlight_rejected") and importance != "high":
            should_drop = True
        if item.get("before_prologue_end") and not item.get("llm_highlight_selected"):
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
                str(prev.get("importance_level") or "low") != "low"
                and str((prev.get("story_validation") or {}).get("validator_status") or "pass") != "risky"
            ):
                keep_indices.add(idx - 1)
        if idx + 1 < total:
            nxt = scored[idx + 1]
            if (
                str(nxt.get("importance_level") or "low") != "low"
                and str((nxt.get("story_validation") or {}).get("validator_status") or "pass") != "risky"
            ):
                keep_indices.add(idx + 1)

    selected = []
    for idx, item in enumerate(scored):
        if idx in keep_indices:
            item["selected_for_final_story"] = True
            item["final_story_drop_reason"] = ""
            selected.append(item)

    if len(selected) < min(3, total):
        fallback = sorted(scored, key=lambda x: x.get("final_story_score", 0.0), reverse=True)[: min(5, total)]
        selected_ids = {x.get("segment_id") for x in fallback}
        selected = [item for item in scored if item.get("segment_id") in selected_ids]
        for item in selected:
            item["selected_for_final_story"] = True
            item["final_story_drop_reason"] = ""

    logger.info(
        "最终证据筛选完成: raw=%s, selected=%s, dropped=%s",
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
    _ensure_llm_ready(text_api_key, text_base_url, text_model)
    asr_backend = str(asr_backend or "faster-whisper").strip() or "faster-whisper"
    target_minutes = _resolve_target_minutes(generation_mode, scene_overrides)
    effective_visual_mode = _resolve_visual_mode(visual_mode or scene_overrides.get("visual_mode", "auto"))
    highlight_only = bool(scene_overrides.get("highlight_only", False))
    narrative_strategy = str(scene_overrides.get("narrative_strategy") or "chronological")
    accuracy_priority = str(scene_overrides.get("accuracy_priority") or "high")
    video_title = str(scene_overrides.get("video_title") or scene_overrides.get("short_name") or "").strip()

    progress(10, "字幕解析与标准化...")
    sub_result = build_subtitle_segments(
        video_path=video_path,
        explicit_subtitle_path=subtitle_path,
        regenerate=regenerate_subtitle,
        backend_override=asr_backend,
    )
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
    story_highlights = _extract_story_highlights(scene_evidence, scene_cut_points)

    progress(88, "生成影视解说脚本..." if not highlight_only else "生成高光验证脚本...")
    if highlight_only:
        script_items = _build_highlight_only_script(story_highlights)
    else:
        script_items = generate_narration_from_scene_evidence(
            scene_evidence=scene_evidence,
            api_key=text_api_key,
            base_url=text_base_url,
            model=text_model,
            style=style or "general",
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
    )

    warnings: List[str] = []
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
        llm_highlight_plan=llm_highlight_plan,
        script_items=script_items,
        scene_cut_points=scene_cut_points,
        video_boundary_candidates=video_boundary_candidates,
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
        "highlight_only_ready": True,
        "highlight_only_mode": highlight_only,
        "audit_path": audit_path,
        "evidence": scene_evidence,
        "selected_scene_evidence": scene_evidence,
        "story_highlights": story_highlights,
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
