from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.services.composition_plan_adapter import composition_plan_to_script_items
from app.services.highlight_selector import (
    apply_audio_signal_scores,
    build_candidate_from_plot_chunk,
    enrich_candidate_evidence,
    select_highlight_clips,
)
from app.services.highlight_timeline_planner import plan_highlight_timeline
from app.services.narrated_highlight_mapper import (
    fit_narration_units_to_target,
    map_narration_units_to_clips,
    split_narration_units,
)
from app.services.plot_chunker import build_plot_chunks_from_subtitles
from app.services.scene_builder import build_scenes, build_video_boundary_candidates
from app.services.subtitle_pipeline import build_subtitle_segments
from app.utils import utils


_VISUAL_SIGNAL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "off": {
        "enabled": False,
        "boundary_args": {},
        "scene_preset": {},
    },
    "auto": {
        "enabled": True,
        "boundary_args": {
            "threshold": 27.0,
            "min_scene_len": 2.0,
            "force_split_gap": 4.0,
            "micro_threshold": 2.0,
            "min_scene_duration": 1.5,
            "merge_window_sec": 2.0,
        },
        "scene_preset": {
            "scene_threshold": 27.0,
            "min_scene_len": 2.0,
            "max_scene_duration": 12.0,
            "max_gap": 1.2,
            "force_split_gap": 4.0,
            "micro_threshold": 2.0,
            "min_scene_duration": 1.5,
        },
    },
    "boost": {
        "enabled": True,
        "boundary_args": {
            "threshold": 24.5,
            "min_scene_len": 1.2,
            "force_split_gap": 3.2,
            "micro_threshold": 1.2,
            "min_scene_duration": 1.0,
            "merge_window_sec": 1.25,
        },
        "scene_preset": {
            "scene_threshold": 24.5,
            "min_scene_len": 1.2,
            "max_scene_duration": 8.5,
            "max_gap": 0.9,
            "force_split_gap": 3.2,
            "micro_threshold": 1.2,
            "min_scene_duration": 1.0,
        },
    },
}


def _resolve_visual_signal_config(visual_mode: str) -> Dict[str, Any]:
    normalized = str(visual_mode or "auto").strip().lower()
    if normalized not in _VISUAL_SIGNAL_CONFIGS:
        normalized = "auto"
    config = _VISUAL_SIGNAL_CONFIGS[normalized]
    return {
        "mode": normalized,
        "enabled": bool(config.get("enabled")),
        "boundary_args": dict(config.get("boundary_args") or {}),
        "scene_preset": dict(config.get("scene_preset") or {}),
    }


def _try_ai_highlight_selection(
    candidate_clips: List[Dict[str, Any]],
    *,
    target_duration_seconds: int,
    movie_title: str,
    mode: str,
    highlight_profile: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from app.services.highlight_ai import ai_select_highlight_candidates

        return ai_select_highlight_candidates(
            candidate_clips,
            target_duration_seconds=target_duration_seconds,
            movie_title=movie_title,
            mode=mode,
            highlight_profile=highlight_profile,
        )
    except Exception as exc:
        logger.warning("AI highlight selection unavailable, fallback to heuristics: {}", exc)
        return {"used_ai": False, "selected_clip_ids": [], "selection_notes": []}


def _try_ai_narration_matching(
    narration_units: List[Dict[str, Any]],
    candidate_clips: List[Dict[str, Any]],
    *,
    movie_title: str,
    highlight_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    try:
        from app.services.highlight_ai import ai_match_narration_units_to_candidates

        return ai_match_narration_units_to_candidates(
            narration_units,
            candidate_clips,
            movie_title=movie_title,
            highlight_profile=highlight_profile,
        )
    except Exception as exc:
        logger.warning("AI narration matching unavailable, fallback to heuristics: {}", exc)
        return []


def _select_clips_by_ids(
    candidate_clips: List[Dict[str, Any]],
    clip_ids: List[str],
    *,
    raw_audio_clip_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not candidate_clips or not clip_ids:
        return []

    lookup = {str(item.get("clip_id", "") or ""): dict(item) for item in candidate_clips if item.get("clip_id")}
    raw_audio_set = {str(value) for value in (raw_audio_clip_ids or []) if str(value)}
    selected: List[Dict[str, Any]] = []
    for clip_id in clip_ids:
        item = lookup.get(str(clip_id))
        if not item:
            continue
        updated = dict(item)
        updated["selection_reason"] = list(dict.fromkeys(list(updated.get("selection_reason") or []) + ["ai_selected"]))
        if str(clip_id) in raw_audio_set:
            updated["selection_reason"] = list(
                dict.fromkeys(list(updated.get("selection_reason") or []) + ["raw_audio_keep"])
            )
            updated["raw_audio_worthy"] = True
        selected.append(updated)
    return selected


def _refresh_narration_matches_from_planned(
    narration_matches: List[Dict[str, Any]],
    planned_clips: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not narration_matches or not planned_clips:
        return narration_matches

    clip_lookup = {str(item.get("clip_id", "") or ""): dict(item) for item in planned_clips if item.get("clip_id")}
    refreshed: List[Dict[str, Any]] = []
    for match in narration_matches:
        current_clip = dict(match.get("clip") or {})
        clip_id = str(match.get("clip_id", "") or current_clip.get("clip_id", "") or "")
        planned_clip = clip_lookup.get(clip_id)
        if not planned_clip:
            refreshed.append(dict(match))
            continue

        merged_clip = dict(current_clip)
        merged_clip.update(planned_clip)
        updated = dict(match)
        updated["clip"] = merged_clip
        updated["clip_group"] = [dict(merged_clip)]
        updated["clip_ids"] = [clip_id]
        updated["group_start"] = round(float(merged_clip.get("start", 0.0) or 0.0), 3)
        updated["group_end"] = round(float(merged_clip.get("end", 0.0) or 0.0), 3)
        refreshed.append(updated)
    return refreshed


def _selection_duration(clips: List[Dict[str, Any]]) -> float:
    return round(sum(max(float(item.get("duration", 0.0) or 0.0), 0.0) for item in (clips or [])), 3)


def _detect_highlight_capabilities() -> Dict[str, Any]:
    try:
        from app.services.highlight_profile import detect_highlight_capabilities

        return detect_highlight_capabilities()
    except Exception as exc:
        logger.warning("Highlight capability detection unavailable: {}", exc)
        return {}


def _resolve_highlight_profile_context(
    *,
    requested_profile: str,
    movie_title: str,
    narration_text: str,
    subtitle_segments: List[Dict[str, Any]],
    plot_chunks: List[Dict[str, Any]],
    candidate_clips: List[Dict[str, Any]],
    capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from app.services.highlight_profile import resolve_highlight_profile

        return resolve_highlight_profile(
            requested_profile=requested_profile,
            movie_title=movie_title,
            narration_text=narration_text,
            subtitle_segments=subtitle_segments,
            plot_chunks=plot_chunks,
            candidate_clips=candidate_clips,
            capabilities=capabilities,
        )
    except Exception as exc:
        logger.warning("Highlight profile resolution unavailable, fallback to general: {}", exc)
        return {
            "id": "general",
            "label": "General / Mixed",
            "source": "fallback",
            "confidence": 0.0,
            "reasons": ["fallback_general_profile"],
            "capabilities": dict(capabilities or {}),
        }


def _apply_highlight_profile_context(
    candidate_clips: List[Dict[str, Any]],
    highlight_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not candidate_clips:
        return []
    try:
        from app.services.highlight_profile import apply_highlight_profile

        return apply_highlight_profile(candidate_clips, highlight_profile)
    except Exception as exc:
        logger.warning("Highlight profile application unavailable, using raw candidate scores: {}", exc)
        return [dict(item) for item in (candidate_clips or [])]


def _annotate_audio_signal_context(
    video_path: str,
    candidate_clips: List[Dict[str, Any]],
    *,
    audio_context: Optional[Dict[str, Any]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not candidate_clips:
        return [], {
            "audio_signal_used": False,
            "audio_signal_clip_count": 0,
            "audio_raw_candidate_count": 0,
            "audio_signal_mean": 0.0,
            "audio_peak_mean": 0.0,
        }

    try:
        from app.services.highlight_audio import (
            build_audio_signal_context,
            compute_audio_scores_for_clips,
            summarize_audio_scores,
        )
    except Exception as exc:
        logger.warning("Highlight audio analysis unavailable: {}", exc)
        return [dict(item) for item in candidate_clips], {
            "audio_signal_used": False,
            "audio_signal_clip_count": 0,
            "audio_raw_candidate_count": 0,
            "audio_signal_mean": 0.0,
            "audio_peak_mean": 0.0,
        }

    audio_context = dict(audio_context or {}) or build_audio_signal_context(video_path)
    if not audio_context.get("available"):
        return [dict(item) for item in candidate_clips], {
            "audio_signal_used": False,
            "audio_signal_clip_count": 0,
            "audio_raw_candidate_count": 0,
            "audio_signal_mean": 0.0,
            "audio_peak_mean": 0.0,
            "audio_signal_reason": str(audio_context.get("reason", "") or ""),
        }

    audio_scores = compute_audio_scores_for_clips(candidate_clips, audio_context)
    annotated = [
        apply_audio_signal_scores(dict(item), score)
        for item, score in zip(candidate_clips, audio_scores)
    ]
    summary = summarize_audio_scores(audio_scores)
    summary["audio_signal_used"] = True
    summary["audio_signal_reason"] = "ok"
    return annotated, summary


def run_highlight_edit_pipeline(
    video_path: str,
    *,
    mode: str = "highlight_recut",
    target_duration_seconds: int = 480,
    movie_title: str = "",
    highlight_profile: str = "auto",
    subtitle_path: str = "",
    narration_text: str = "",
    narration_audio_path: str = "",
    prefer_raw_audio: bool = True,
    visual_mode: str = "auto",
    regenerate_subtitle: bool = False,
    subtitle_backend: str = "",
    progress_callback: Optional[Callable[[int, str], None]] = None,
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
            mode=mode,
            target_duration_seconds=target_duration_seconds,
            movie_title=movie_title,
            highlight_profile=highlight_profile,
            subtitle_path=subtitle_path,
            narration_text=narration_text,
            narration_audio_path=narration_audio_path,
            prefer_raw_audio=prefer_raw_audio,
            visual_mode=visual_mode,
            regenerate_subtitle=regenerate_subtitle,
            subtitle_backend=subtitle_backend,
            progress=_progress,
        )
    except Exception as exc:
        logger.exception("粗剪编排主链执行失败: {}", exc)
        return {
            "success": False,
            "error": str(exc),
            "composition_plan": {},
            "composition_plan_path": "",
            "script_items": [],
            "script_path": "",
            "candidate_clips": [],
            "selected_clips": [],
        }


def _run(
    *,
    video_path: str,
    mode: str,
    target_duration_seconds: int,
    movie_title: str,
    highlight_profile: str,
    subtitle_path: str,
    narration_text: str,
    narration_audio_path: str,
    prefer_raw_audio: bool,
    visual_mode: str,
    regenerate_subtitle: bool,
    subtitle_backend: str,
    progress: Callable[[int, str], None],
) -> Dict[str, Any]:
    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    target_duration_seconds = max(int(target_duration_seconds or 0), 30)
    video_hash = utils.md5(video_path + str(os.path.getmtime(video_path)))
    visual_config = _resolve_visual_signal_config(visual_mode)

    progress(10, "准备字幕和分镜信号...")
    subtitle_result = build_subtitle_segments(
        video_path=video_path,
        explicit_subtitle_path=subtitle_path,
        regenerate=regenerate_subtitle,
        backend_override=subtitle_backend,
    )
    subtitle_segments = subtitle_result.get("segments") or []

    video_boundary_candidates: List[Dict[str, Any]] = []
    if visual_config["enabled"]:
        video_boundary_candidates = build_video_boundary_candidates(
            video_path=video_path,
            subtitle_segments=subtitle_segments,
            **visual_config["boundary_args"],
        )
    scene_segments = build_scenes(
        subtitle_segments=subtitle_segments,
        video_path=video_path if visual_config["enabled"] else "",
        mode=visual_config["mode"],
        preset=visual_config["scene_preset"],
    )

    progress(30, "构建候选片段...")
    plot_chunks = []
    if subtitle_segments:
        plot_chunks = build_plot_chunks_from_subtitles(
            subtitle_segments,
            target_duration_minutes=max(round(target_duration_seconds / 60), 1),
            video_candidates=video_boundary_candidates,
            refine_chunks=True,
        )

    plot_candidate_clips = _build_candidate_clips(
        plot_chunks=plot_chunks,
        scene_segments=scene_segments,
        subtitle_segments=subtitle_segments,
    )
    scene_candidate_clips = _build_scene_candidates(
        scene_segments=scene_segments,
        plot_chunks=plot_chunks,
        video_boundary_candidates=video_boundary_candidates,
        subtitle_segments=subtitle_segments,
    )
    shared_audio_context: Dict[str, Any] = {}
    try:
        from app.services.highlight_audio import build_audio_signal_context

        shared_audio_context = build_audio_signal_context(video_path)
    except Exception as exc:
        logger.warning("Shared highlight audio analysis unavailable: {}", exc)
        shared_audio_context = {}

    plot_candidate_clips, plot_audio_stats = _annotate_audio_signal_context(
        video_path,
        plot_candidate_clips,
        audio_context=shared_audio_context,
    )
    scene_candidate_clips, scene_audio_stats = _annotate_audio_signal_context(
        video_path,
        scene_candidate_clips,
        audio_context=shared_audio_context,
    )
    raw_candidate_clips = _merge_unique_clips(plot_candidate_clips, scene_candidate_clips)
    highlight_capabilities = _detect_highlight_capabilities()
    highlight_profile_context = _resolve_highlight_profile_context(
        requested_profile=highlight_profile,
        movie_title=movie_title,
        narration_text=narration_text,
        subtitle_segments=subtitle_segments,
        plot_chunks=plot_chunks,
        candidate_clips=raw_candidate_clips,
        capabilities=highlight_capabilities,
    )
    plot_candidate_clips = _apply_highlight_profile_context(plot_candidate_clips, highlight_profile_context)
    scene_candidate_clips = _apply_highlight_profile_context(scene_candidate_clips, highlight_profile_context)
    candidate_clips = _merge_unique_clips(plot_candidate_clips, scene_candidate_clips)
    candidate_stats = _build_candidate_stats(
        subtitle_segments=subtitle_segments,
        plot_chunks=plot_chunks,
        scene_segments=scene_segments,
        plot_candidate_clips=plot_candidate_clips,
        scene_candidate_clips=scene_candidate_clips,
        merged_candidate_clips=candidate_clips,
        visual_mode=visual_config["mode"],
        highlight_profile=highlight_profile_context,
        capabilities=highlight_capabilities,
        plot_audio_stats=plot_audio_stats,
        scene_audio_stats=scene_audio_stats,
    )
    ai_highlight_selection = _try_ai_highlight_selection(
        candidate_clips,
        target_duration_seconds=target_duration_seconds,
        movie_title=movie_title,
        mode=mode,
        highlight_profile=highlight_profile_context,
    )
    candidate_stats["ai_highlight_selection_used"] = bool(ai_highlight_selection.get("used_ai"))
    candidate_stats["ai_highlight_selected_count"] = len(ai_highlight_selection.get("selected_clip_ids") or [])
    candidate_stats["ai_highlight_model"] = str(ai_highlight_selection.get("model", "") or "")

    narration_units: List[Dict[str, Any]] = []
    narration_matches: List[Dict[str, Any]] = []
    selection_top_k = max(round(target_duration_seconds / 35), 4)

    if mode == "narrated_highlight_edit" and str(narration_text or "").strip():
        progress(48, "分析解说结构...")
        narration_units = fit_narration_units_to_target(
            split_narration_units(narration_text, 0),
            target_duration_seconds,
        )
        progress(60, "按解说构建粗匹配候选...")
        narrated_pool = _build_narrated_clip_pool(
            plot_candidate_clips,
            scene_candidate_clips,
            narration_units,
            target_duration_seconds,
        )
        progress(72, "匹配解说和场景...")
        narration_matches = _try_ai_narration_matching(
            narration_units,
            narrated_pool,
            movie_title=movie_title,
            highlight_profile=highlight_profile_context,
        )
        candidate_stats["ai_narration_matching_used"] = bool(narration_matches)
        if not narration_matches:
            narration_matches = map_narration_units_to_clips(narration_units, narrated_pool)
        selected_clips = _merge_unique_clips(
            _collect_matched_clips(narration_matches),
            _select_clips_by_ids(
                candidate_clips,
                ai_highlight_selection.get("selected_clip_ids") or [],
                raw_audio_clip_ids=ai_highlight_selection.get("raw_audio_clip_ids") or [],
            ),
            select_highlight_clips(candidate_clips, top_k=max(selection_top_k, len(narration_units))),
        )
        if not selected_clips:
            selected_clips = select_highlight_clips(
                candidate_clips,
                top_k=max(selection_top_k, len(narration_units), 4),
            )
        progress(80, "规划时间轴...")
        planned_clips = plan_highlight_timeline(selected_clips, target_duration_seconds)
        if any(bool(item.get("preserve_sentence_boundary")) for item in narration_matches):
            narration_matches = _refresh_narration_matches_from_planned(narration_matches, planned_clips or selected_clips)
        else:
            narration_matches = map_narration_units_to_clips(narration_units, planned_clips or selected_clips)
    else:
        progress(55, "筛选高光片段...")
        selected_clips = _select_clips_by_ids(
            candidate_clips,
            ai_highlight_selection.get("selected_clip_ids") or [],
            raw_audio_clip_ids=ai_highlight_selection.get("raw_audio_clip_ids") or [],
        )
        if _selection_duration(selected_clips) < max(min(target_duration_seconds * 0.4, 90.0), 24.0):
            selected_clips = _merge_unique_clips(
                selected_clips,
                _build_highlight_recut_selection_pool(
                    candidate_clips,
                    target_duration_seconds=target_duration_seconds,
                ),
            )
        if not selected_clips:
            selected_clips = _build_highlight_recut_selection_pool(
                candidate_clips,
                target_duration_seconds=target_duration_seconds,
            )
        if not selected_clips:
            selected_clips = select_highlight_clips(
                candidate_clips,
                top_k=selection_top_k,
            )
        progress(72, "规划时间轴...")
        planned_clips = plan_highlight_timeline(selected_clips, target_duration_seconds)

    progress(88, "生成粗剪合成脚本...")
    composition_plan = _build_composition_plan(
        mode=mode,
        video_path=video_path,
        movie_title=movie_title,
        target_duration_seconds=target_duration_seconds,
        visual_mode=visual_config["mode"],
        highlight_profile=highlight_profile_context,
        highlight_capabilities=highlight_capabilities,
        candidate_stats=candidate_stats,
        selected_clips=planned_clips,
        narration_text=narration_text,
        narration_audio_path=narration_audio_path,
        prefer_raw_audio=prefer_raw_audio,
        narration_matches=narration_matches,
    )
    script_items = composition_plan_to_script_items(composition_plan)

    progress(96, "保存粗剪脚本...")
    output_paths = _write_outputs(video_hash, composition_plan, script_items)

    progress(100, "粗剪编排主链完成")
    return {
        "success": True,
        "error": "",
        "mode": mode,
        "subtitle_result": subtitle_result,
        "subtitle_segments": subtitle_segments,
        "scene_segments": scene_segments,
        "video_boundary_candidates": video_boundary_candidates,
        "plot_chunks": plot_chunks,
        "plot_candidate_clips": plot_candidate_clips,
        "candidate_clips": candidate_clips,
        "scene_candidate_clips": scene_candidate_clips,
        "candidate_stats": candidate_stats,
        "highlight_profile": highlight_profile_context,
        "highlight_capabilities": highlight_capabilities,
        "selected_clips": planned_clips,
        "narration_units": narration_units,
        "narration_matches": narration_matches,
        "composition_plan": composition_plan,
        "composition_plan_path": output_paths["composition_plan_path"],
        "script_items": script_items,
        "script_path": output_paths["script_path"],
    }


def _build_candidate_clips(
    *,
    plot_chunks: List[Dict[str, Any]],
    scene_segments: List[Dict[str, Any]],
    subtitle_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    total_plot_chunks = len(plot_chunks or [])
    subtitle_segment_map = _build_subtitle_segment_map(subtitle_segments)

    for idx, chunk in enumerate(plot_chunks or [], start=1):
        candidates.append(build_candidate_from_plot_chunk(chunk, idx, total_plot_chunks))

    if candidates:
        return candidates

    for idx, scene in enumerate(scene_segments or [], start=1):
        start = float(scene.get("start", 0.0) or 0.0)
        end = float(scene.get("end", start) or start)
        if end <= start:
            end = start + 0.5
        story_position = round((idx - 1) / max(len(scene_segments or []) - 1, 1), 3) if len(scene_segments or []) > 1 else 0.5
        dialogue_signals = _collect_scene_dialogue_signals(scene, subtitle_segment_map)
        candidates.append(
            enrich_candidate_evidence(
                {
                "clip_id": f"scene_clip_{idx:04d}",
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "source": "scene",
                "story_index": idx,
                "story_position": story_position,
                "story_stage_hint": "opening" if story_position <= 0.12 else "ending" if story_position >= 0.88 else "setup",
                "plot_function": "",
                "plot_role": "",
                "character_names": [],
                "subtitle_text": "",
                "scene_summary": "",
                "energy_score": 0.45,
                "story_score": 0.35,
                "emotion_score": 0.35,
                "total_score": 0.38,
                "raw_audio_worthy": True,
                "tags": ["scene_fallback"],
                "source_scene_id": str(scene.get("scene_id", "") or ""),
                "source_segment_ids": list(scene.get("subtitle_ids") or []),
                "speaker_sequence": list(dialogue_signals["speaker_sequence"]),
                "speaker_names": list(dialogue_signals["speaker_names"]),
                "speaker_turns": int(dialogue_signals["speaker_turns"]),
                "exchange_pairs": list(dialogue_signals["exchange_pairs"]),
                "selection_reason": ["scene_fallback"],
                }
            )
        )
    return candidates


def _scene_overlap_seconds(scene: Dict[str, Any], chunk: Dict[str, Any]) -> float:
    scene_start = float(scene.get("start", 0.0) or 0.0)
    scene_end = float(scene.get("end", scene_start) or scene_start)
    chunk_start = float(chunk.get("start", 0.0) or 0.0)
    chunk_end = float(chunk.get("end", chunk_start) or chunk_start)
    return max(0.0, min(scene_end, chunk_end) - max(scene_start, chunk_start))


def _scene_center_distance(scene: Dict[str, Any], chunk: Dict[str, Any]) -> float:
    scene_start = float(scene.get("start", 0.0) or 0.0)
    scene_end = float(scene.get("end", scene_start) or scene_start)
    chunk_start = float(chunk.get("start", 0.0) or 0.0)
    chunk_end = float(chunk.get("end", chunk_start) or chunk_start)
    scene_center = (scene_start + scene_end) / 2.0
    chunk_center = (chunk_start + chunk_end) / 2.0
    return abs(scene_center - chunk_center)


def _find_best_plot_chunk_for_scene(scene: Dict[str, Any], plot_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not plot_chunks:
        return {}

    best = None
    best_key = None
    for chunk in plot_chunks:
        overlap = _scene_overlap_seconds(scene, chunk)
        distance = _scene_center_distance(scene, chunk)
        highlight_score = float(chunk.get("highlight_score", 0.0) or 0.0)
        key = (overlap, -distance, highlight_score)
        if best is None or key > best_key:
            best = chunk
            best_key = key

    if best is None:
        return {}
    if float(best_key[0]) > 0.0 or float(-best_key[1]) <= 18.0:
        return dict(best)
    return {}


def _build_subtitle_segment_map(subtitle_segments: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for segment in subtitle_segments or []:
        seg_id = str(segment.get("seg_id", "") or segment.get("id", "") or "").strip()
        if seg_id:
            mapping[seg_id] = dict(segment)
    return mapping


def _collect_scene_dialogue_signals(
    scene: Dict[str, Any],
    subtitle_segment_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    speakers: List[str] = []
    for subtitle_id in scene.get("subtitle_ids") or []:
        segment = subtitle_segment_map.get(str(subtitle_id or "").strip())
        if not segment:
            continue
        speaker = str(segment.get("speaker", "") or "").strip()
        if speaker:
            speakers.append(speaker)
    speaker_names = _sorted_unique_values(speakers)
    exchange_pairs = []
    compact_turns: List[str] = []
    for speaker in speakers:
        if not compact_turns or speaker != compact_turns[-1]:
            compact_turns.append(speaker)
    for left, right in zip(compact_turns, compact_turns[1:]):
        if left and right and left != right:
            exchange_pairs.append(f"{left}->{right}")
    return {
        "speaker_sequence": list(speakers),
        "speaker_names": speaker_names,
        "speaker_turns": len(speakers),
        "exchange_pairs": exchange_pairs,
    }


def _build_scene_candidate(
    scene: Dict[str, Any],
    index: int,
    total: int,
    parent_chunk: Dict[str, Any],
    boundary_candidates: List[float],
    subtitle_segment_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    scene_text = str(scene.get("subtitle_text", "") or " ".join(scene.get("subtitle_texts") or [])).strip()
    start = float(scene.get("start", 0.0) or 0.0)
    end = float(scene.get("end", start) or start)
    duration = max(end - start, 0.5)
    dialogue_signals = _collect_scene_dialogue_signals(scene, subtitle_segment_map)

    if parent_chunk:
        synthetic_chunk = dict(parent_chunk)
        synthetic_chunk["start"] = start
        synthetic_chunk["end"] = end
        synthetic_chunk["scene_id"] = str(scene.get("scene_id", "") or synthetic_chunk.get("scene_id", "") or "")
        synthetic_chunk["subtitle_ids"] = list(scene.get("subtitle_ids") or synthetic_chunk.get("subtitle_ids") or [])
        synthetic_chunk["aligned_subtitle_text"] = scene_text or str(synthetic_chunk.get("aligned_subtitle_text", "") or "")
        synthetic_chunk["real_narrative_state"] = str(
            synthetic_chunk.get("real_narrative_state", "") or synthetic_chunk.get("surface_dialogue_meaning", "") or scene_text
        )
        synthetic_chunk["highlight_score"] = max(float(synthetic_chunk.get("highlight_score", 0.0) or 0.0) * 0.9, 0.36)
        synthetic_chunk["raw_voice_retain_suggestion"] = bool(scene_text) or bool(
            synthetic_chunk.get("raw_voice_retain_suggestion")
        )
        if dialogue_signals["speaker_sequence"]:
            synthetic_chunk["speaker_sequence"] = list(dialogue_signals["speaker_sequence"])
        if dialogue_signals["speaker_names"]:
            synthetic_chunk["speaker_names"] = list(dialogue_signals["speaker_names"])
        if int(dialogue_signals.get("speaker_turns", 0) or 0) > 0:
            synthetic_chunk["speaker_turns"] = int(dialogue_signals.get("speaker_turns", 0) or 0)
        if dialogue_signals["exchange_pairs"]:
            synthetic_chunk["exchange_pairs"] = list(dialogue_signals["exchange_pairs"])
        candidate = build_candidate_from_plot_chunk(synthetic_chunk, index, total)
        candidate["selection_reason"] = list(dict.fromkeys(list(candidate.get("selection_reason") or []) + ["scene_refined"]))
    else:
        story_position = round((index - 1) / max(total - 1, 1), 3) if total > 1 else 0.5
        candidate = {
            "clip_id": f"scene_clip_{index:04d}",
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(duration, 3),
            "source": "scene",
            "story_index": index,
            "story_position": story_position,
            "story_stage_hint": "opening" if story_position <= 0.12 else "ending" if story_position >= 0.88 else "setup",
            "plot_function": "",
            "plot_role": "",
            "character_names": [],
            "subtitle_text": scene_text,
            "scene_summary": scene_text,
            "energy_score": 0.52 if scene_text else 0.4,
            "story_score": 0.42 if scene_text else 0.32,
            "emotion_score": 0.38 if scene_text else 0.3,
            "total_score": 0.45 if scene_text else 0.34,
            "raw_audio_worthy": bool(scene_text) or duration <= 4.5,
            "tags": ["scene_refined" if scene_text else "scene_fallback"],
            "source_scene_id": str(scene.get("scene_id", "") or ""),
            "source_segment_ids": list(scene.get("subtitle_ids") or []),
            "speaker_sequence": list(dialogue_signals["speaker_sequence"]),
            "speaker_names": list(dialogue_signals["speaker_names"]),
            "speaker_turns": int(dialogue_signals["speaker_turns"]),
            "exchange_pairs": list(dialogue_signals["exchange_pairs"]),
            "selection_reason": ["scene_refined" if scene_text else "scene_fallback"],
        }

    candidate["clip_id"] = f"scene_clip_{index:04d}"
    candidate["source"] = "scene"
    candidate["start"] = round(start, 3)
    candidate["end"] = round(end, 3)
    candidate["duration"] = round(duration, 3)
    candidate["subtitle_text"] = scene_text or str(candidate.get("subtitle_text", "") or "")
    candidate["scene_summary"] = str(candidate.get("scene_summary", "") or scene_text or "")
    candidate["raw_audio_worthy"] = bool(candidate.get("raw_audio_worthy")) or bool(scene_text) or duration <= 4.5
    candidate["energy_score"] = round(max(float(candidate.get("energy_score", 0.0) or 0.0), 0.58 if scene_text else 0.42), 3)
    candidate["source_scene_id"] = str(scene.get("scene_id", "") or candidate.get("source_scene_id", "") or "")
    candidate["source_segment_ids"] = list(scene.get("subtitle_ids") or candidate.get("source_segment_ids") or [])
    candidate["speaker_sequence"] = list(dialogue_signals.get("speaker_sequence") or candidate.get("speaker_sequence") or [])
    candidate["speaker_names"] = _sorted_unique_values(
        list(candidate.get("speaker_names") or []) + list(dialogue_signals.get("speaker_names") or [])
    )
    candidate["speaker_turns"] = int(dialogue_signals.get("speaker_turns", 0) or 0) or int(candidate.get("speaker_turns", 0) or 0)
    candidate["exchange_pairs"] = list(dialogue_signals.get("exchange_pairs") or candidate.get("exchange_pairs") or [])
    candidate["keyframe_candidates"] = list(scene.get("keyframe_candidates") or [])
    candidate["boundary_candidates"] = list(boundary_candidates or [])
    if scene_text and "scene_refined" not in list(candidate.get("tags") or []):
        candidate["tags"] = list(dict.fromkeys(list(candidate.get("tags") or []) + ["scene_refined"]))
    return enrich_candidate_evidence(candidate)


def _collect_scene_boundary_candidates(
    scene: Dict[str, Any],
    video_boundary_candidates: List[Dict[str, Any]],
) -> List[float]:
    start = float(scene.get("start", 0.0) or 0.0)
    end = float(scene.get("end", start) or start)
    boundaries = []
    for item in video_boundary_candidates or []:
        timestamp = float(item.get("time", start) or start)
        if start + 0.35 <= timestamp <= end - 0.35:
            boundaries.append(round(timestamp, 3))
    return sorted(dict.fromkeys(boundaries))


def _build_scene_candidates(
    *,
    scene_segments: List[Dict[str, Any]],
    plot_chunks: List[Dict[str, Any]],
    video_boundary_candidates: List[Dict[str, Any]],
    subtitle_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    total = len(scene_segments or [])
    subtitle_segment_map = _build_subtitle_segment_map(subtitle_segments)
    for idx, scene in enumerate(scene_segments or [], start=1):
        parent_chunk = _find_best_plot_chunk_for_scene(scene, plot_chunks)
        boundary_candidates = _collect_scene_boundary_candidates(scene, video_boundary_candidates)
        candidates.append(_build_scene_candidate(scene, idx, total, parent_chunk, boundary_candidates, subtitle_segment_map))
    return candidates


def _build_candidate_stats(
    *,
    subtitle_segments: List[Dict[str, Any]],
    plot_chunks: List[Dict[str, Any]],
    scene_segments: List[Dict[str, Any]],
    plot_candidate_clips: List[Dict[str, Any]],
    scene_candidate_clips: List[Dict[str, Any]],
    merged_candidate_clips: List[Dict[str, Any]],
    visual_mode: str,
    highlight_profile: Dict[str, Any],
    capabilities: Dict[str, Any],
    plot_audio_stats: Dict[str, Any],
    scene_audio_stats: Dict[str, Any],
) -> Dict[str, Any]:
    source_breakdown: Dict[str, int] = {}
    for clip in merged_candidate_clips or []:
        source = str(clip.get("source", "") or "unknown")
        source_breakdown[source] = source_breakdown.get(source, 0) + 1

    return {
        "visual_mode": visual_mode,
        "highlight_profile_id": str(highlight_profile.get("id", "general") or "general"),
        "highlight_profile_label": str(highlight_profile.get("label", "") or ""),
        "highlight_profile_source": str(highlight_profile.get("source", "") or ""),
        "highlight_profile_confidence": round(float(highlight_profile.get("confidence", 0.0) or 0.0), 3),
        "highlight_profile_reasons": list(highlight_profile.get("reasons") or [])[:6],
        "subtitle_segment_count": len(subtitle_segments or []),
        "plot_chunk_count": len(plot_chunks or []),
        "scene_segment_count": len(scene_segments or []),
        "plot_candidate_count": len(plot_candidate_clips or []),
        "scene_candidate_count": len(scene_candidate_clips or []),
        "merged_candidate_count": len(merged_candidate_clips or []),
        "raw_audio_candidate_count": sum(1 for clip in (merged_candidate_clips or []) if clip.get("raw_audio_worthy")),
        "audio_signal_candidate_count": sum(
            1 for clip in (merged_candidate_clips or []) if float(clip.get("audio_signal_score", 0.0) or 0.0) >= 0.5
        ),
        "source_breakdown": source_breakdown,
        "capabilities": dict(capabilities or {}),
        "plot_audio_stats": dict(plot_audio_stats or {}),
        "scene_audio_stats": dict(scene_audio_stats or {}),
    }


def _clip_overlap_ratio(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    left_start = float(left.get("start", 0.0) or 0.0)
    left_end = float(left.get("end", left_start) or left_start)
    right_start = float(right.get("start", 0.0) or 0.0)
    right_end = float(right.get("end", right_start) or right_start)
    overlap = max(0.0, min(left_end, right_end) - max(left_start, right_start))
    min_duration = max(
        min(max(left_end - left_start, 0.001), max(right_end - right_start, 0.001)),
        0.001,
    )
    return overlap / min_duration


def _sorted_unique_values(values: List[Any]) -> List[Any]:
    return sorted(
        dict.fromkeys(value for value in (values or []) if value not in (None, "")),
        key=lambda value: str(value),
    )


def _ordered_unique_values(values: List[Any]) -> List[Any]:
    return list(dict.fromkeys(value for value in (values or []) if value not in (None, "")))


def _clip_specificity_key(clip: Dict[str, Any]) -> tuple:
    source = str(clip.get("source", "") or "")
    source_priority = 2 if source == "scene" else 1
    duration = float(clip.get("duration", 0.0) or 0.0)
    score = float(clip.get("total_score", 0.0) or 0.0)
    return (source_priority, -duration, score)


def _clip_similarity(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    overlap = _clip_overlap_ratio(left, right)
    left_pos = float(left.get("story_position", 0.5) if left.get("story_position") not in (None, "") else 0.5)
    right_pos = float(right.get("story_position", 0.5) if right.get("story_position") not in (None, "") else 0.5)
    position_similarity = max(0.0, 1.0 - abs(left_pos - right_pos) / 0.25)
    left_stage = str(left.get("story_stage_hint", "") or "")
    right_stage = str(right.get("story_stage_hint", "") or "")
    stage_similarity = 1.0 if left_stage and left_stage == right_stage else 0.0
    left_tags = set(str(item) for item in (left.get("tags") or []))
    right_tags = set(str(item) for item in (right.get("tags") or []))
    tag_similarity = 0.0
    if left_tags or right_tags:
        tag_similarity = len(left_tags & right_tags) / max(len(left_tags | right_tags), 1)
    return round(overlap * 0.55 + position_similarity * 0.2 + stage_similarity * 0.15 + tag_similarity * 0.1, 3)


def _clip_relevance_score(clip: Dict[str, Any]) -> float:
    score = float(clip.get("total_score", 0.0) or 0.0)
    if clip.get("raw_audio_worthy"):
        score += 0.05
    if str(clip.get("source", "") or "") == "scene":
        score += 0.06
    if "scene_refined" in set(str(item) for item in (clip.get("tags") or [])):
        score += 0.04
    duration = float(clip.get("duration", 0.0) or 0.0)
    if 2.0 <= duration <= 6.0:
        score += 0.04
    return round(score, 3)


def _select_diverse_clips(candidate_clips: List[Dict[str, Any]], top_k: int, lambda_relevance: float = 0.72) -> List[Dict[str, Any]]:
    pool = [dict(item) for item in (candidate_clips or [])]
    if not pool:
        return []

    target = max(int(top_k or 0), 1)
    ordered = sorted(
        pool,
        key=lambda clip: (_clip_relevance_score(clip), float(clip.get("duration", 0.0) or 0.0)),
        reverse=True,
    )

    selected: List[Dict[str, Any]] = []
    while ordered and len(selected) < target:
        best_index = -1
        best_value = None
        for idx, clip in enumerate(ordered):
            relevance = _clip_relevance_score(clip)
            redundancy = max((_clip_similarity(clip, chosen) for chosen in selected), default=0.0)
            mmr_value = lambda_relevance * relevance - (1.0 - lambda_relevance) * redundancy
            ranking = (mmr_value, relevance, -redundancy, float(clip.get("start", 0.0) or 0.0))
            if best_index < 0 or ranking > best_value:
                best_index = idx
                best_value = ranking
        selected.append(dict(ordered.pop(best_index)))
    return selected


def _append_selection_reasons(clip: Dict[str, Any], *reasons: str) -> Dict[str, Any]:
    updated = dict(clip)
    merged = list(updated.get("selection_reason") or [])
    for reason in reasons:
        normalized = str(reason or "").strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    updated["selection_reason"] = merged
    return updated


def _merge_clip_metadata(preferred: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(preferred)
    alternate = dict(incoming)

    for field in (
        "total_score",
        "story_score",
        "emotion_score",
        "energy_score",
        "story_position",
        "visible_action_score",
        "reaction_score",
        "inner_state_support",
        "relation_score",
        "narrative_overview_score",
        "group_reaction_score",
        "speaker_turns",
        "solo_focus_score",
        "dialogue_exchange_score",
        "ensemble_scene_score",
    ):
        if field in alternate and alternate.get(field) not in (None, ""):
            current = merged.get(field)
            if current in (None, ""):
                merged[field] = alternate.get(field)
            else:
                try:
                    merged[field] = round(max(float(current), float(alternate.get(field))), 3)
                except (TypeError, ValueError):
                    merged[field] = current

    for field in (
        "selection_reason",
        "tags",
        "character_names",
        "speaker_names",
        "interaction_target_names",
        "pressure_source_names",
        "pressure_target_names",
        "source_segment_ids",
        "keyframe_candidates",
        "boundary_candidates",
    ):
        merged[field] = _sorted_unique_values(list(merged.get(field) or []) + list(alternate.get(field) or []))
    merged["speaker_sequence"] = _ordered_unique_values(
        list(merged.get("speaker_sequence") or []) + list(alternate.get("speaker_sequence") or [])
    )
    merged["exchange_pairs"] = _ordered_unique_values(
        list(merged.get("exchange_pairs") or []) + list(alternate.get("exchange_pairs") or [])
    )

    merged["raw_audio_worthy"] = bool(merged.get("raw_audio_worthy") or alternate.get("raw_audio_worthy"))
    merged["prevent_merge"] = bool(merged.get("prevent_merge") or alternate.get("prevent_merge"))

    for field in ("scene_summary", "subtitle_text"):
        merged_value = str(merged.get(field, "") or "")
        incoming_value = str(alternate.get(field, "") or "")
        if len(incoming_value) > len(merged_value):
            merged[field] = incoming_value

    for field in (
        "source_scene_id",
        "plot_function",
        "plot_role",
        "story_stage_hint",
        "source",
        "clip_id",
        "parent_clip_id",
        "subshot_index",
        "primary_evidence",
    ):
        if not merged.get(field) and alternate.get(field) not in (None, ""):
            merged[field] = alternate.get(field)

    merged_role = str(merged.get("shot_role", "") or "")
    alternate_role = str(alternate.get("shot_role", "") or "")
    if merged_role and alternate_role and merged_role != alternate_role:
        merged["shot_role"] = "mixed"
    elif not merged_role and alternate_role:
        merged["shot_role"] = alternate_role

    return merged


def _pick_anchor_clip(
    candidate_clips: List[Dict[str, Any]],
    *,
    story_position_min: Optional[float] = None,
    story_position_max: Optional[float] = None,
    allowed_stages: Optional[set] = None,
    require_raw_audio: bool = False,
) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    for clip in candidate_clips or []:
        story_position = float(clip.get("story_position", 0.5) if clip.get("story_position") not in (None, "") else 0.5)
        if story_position_min is not None and story_position < story_position_min:
            continue
        if story_position_max is not None and story_position > story_position_max:
            continue
        if require_raw_audio and not clip.get("raw_audio_worthy"):
            continue
        if allowed_stages:
            stage = str(clip.get("story_stage_hint", "") or "")
            if stage not in allowed_stages:
                continue
        pool.append(dict(clip))

    if not pool:
        return []
    ordered = sorted(
        pool,
        key=lambda clip: (
            _clip_relevance_score(clip),
            float(clip.get("total_score", 0.0) or 0.0),
            -abs(float(clip.get("story_position", 0.5) if clip.get("story_position") not in (None, "") else 0.5) - 0.5),
        ),
        reverse=True,
    )
    return [ordered[0]]


def _build_highlight_recut_selection_pool(
    candidate_clips: List[Dict[str, Any]],
    target_duration_seconds: int,
) -> List[Dict[str, Any]]:
    if not candidate_clips:
        return []

    selection_top_k = max(round(target_duration_seconds / 35), 4)
    desired_pool = max(selection_top_k * 2, round(target_duration_seconds / 18), 8)
    coverage_count = max(min(selection_top_k, 6), 3)

    strongest = select_highlight_clips(candidate_clips, top_k=max(selection_top_k, 4))
    strongest = [_append_selection_reasons(clip, "score_pick") for clip in strongest]

    hero_clips = _select_diverse_clips(candidate_clips, desired_pool, lambda_relevance=0.76)
    hero_clips = [_append_selection_reasons(clip, "diverse_pick") for clip in hero_clips]

    coverage_clips = _build_coverage_clips(candidate_clips, coverage_count)
    coverage_clips = [_append_selection_reasons(clip, "coverage_anchor") for clip in coverage_clips]

    raw_audio_clips = _select_diverse_clips(
        [dict(item) for item in candidate_clips if item.get("raw_audio_worthy")],
        top_k=max(round(selection_top_k / 2), 2),
        lambda_relevance=0.8,
    )
    raw_audio_clips = [_append_selection_reasons(clip, "raw_audio_keep", "raw_audio_anchor") for clip in raw_audio_clips]

    scene_focus_clips = _select_diverse_clips(
        [dict(item) for item in candidate_clips if str(item.get("source", "") or "") == "scene"],
        top_k=max(round(selection_top_k / 3), 1),
        lambda_relevance=0.74,
    )
    scene_focus_clips = [_append_selection_reasons(clip, "scene_anchor") for clip in scene_focus_clips]

    opening_anchor = [
        _append_selection_reasons(clip, "coverage_anchor", "opening_anchor")
        for clip in _pick_anchor_clip(
            candidate_clips,
            story_position_max=0.18,
            allowed_stages={"opening", "setup"},
        )
    ]
    ending_candidates = _pick_anchor_clip(
        candidate_clips,
        story_position_min=0.82,
        allowed_stages={"ending", "climax"},
    ) or _pick_anchor_clip(
        candidate_clips,
        story_position_min=0.78,
        allowed_stages={"reveal", "climax", "ending", "turning_point"},
    )
    ending_anchor = [_append_selection_reasons(clip, "coverage_anchor", "ending_anchor") for clip in ending_candidates]
    climax_raw_anchor = [
        _append_selection_reasons(clip, "raw_audio_keep", "climax_anchor")
        for clip in _pick_anchor_clip(
            candidate_clips,
            story_position_min=0.45,
            allowed_stages={"conflict", "turning_point", "climax", "ending"},
            require_raw_audio=True,
        )
    ]

    chronology_clips = [
        _append_selection_reasons(dict(clip), "chronology_anchor")
        for clip in sorted(
            (dict(item) for item in candidate_clips),
            key=lambda x: (float(x.get("start", 0.0) or 0.0), -float(x.get("total_score", 0.0) or 0.0)),
        )[: max(selection_top_k, 4)]
    ]

    return _merge_unique_clips(
        strongest,
        hero_clips,
        coverage_clips,
        raw_audio_clips,
        scene_focus_clips,
        opening_anchor,
        ending_anchor,
        climax_raw_anchor,
        chronology_clips,
    )


def _merge_unique_clips(*clip_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for group in clip_groups:
        for clip in group or []:
            item = dict(clip)
            clip_id = str(item.get("clip_id", "") or "")
            if not clip_id:
                clip_id = f"{float(item.get('start', 0.0) or 0.0):.3f}_{float(item.get('end', 0.0) or 0.0):.3f}"
            duplicate_index = next(
                (
                    index
                    for index, existing in enumerate(merged)
                    if str(existing.get("clip_id", "") or "") == clip_id or _clip_overlap_ratio(existing, item) >= 0.82
                ),
                -1,
            )
            if duplicate_index >= 0:
                existing = dict(merged[duplicate_index])
                if _clip_specificity_key(item) > _clip_specificity_key(existing):
                    merged[duplicate_index] = _merge_clip_metadata(item, existing)
                else:
                    merged[duplicate_index] = _merge_clip_metadata(existing, item)
                continue
            merged.append(item)
    return sorted(merged, key=lambda x: float(x.get("start", 0.0) or 0.0))


def _build_coverage_clips(candidate_clips: List[Dict[str, Any]], desired_count: int) -> List[Dict[str, Any]]:
    ordered = sorted((dict(item) for item in (candidate_clips or [])), key=lambda x: float(x.get("start", 0.0) or 0.0))
    if not ordered:
        return []

    selected: List[Dict[str, Any]] = []
    used = set()
    target_count = max(int(desired_count or 0), 1)
    total = len(ordered)
    for idx, clip in enumerate(ordered, start=1):
        if clip.get("story_position") is None:
            clip["story_position"] = round((idx - 1) / max(total - 1, 1), 3) if total > 1 else 0.5

    for slot in range(target_count):
        desired_position = round(slot / max(target_count - 1, 1), 3) if target_count > 1 else 0.5
        best = None
        best_score = -1.0
        for clip in ordered:
            clip_id = str(clip.get("clip_id", "") or "")
            if clip_id in used:
                continue
            position_value = clip.get("story_position", 0.5)
            if position_value in (None, ""):
                position_value = 0.5
            position_gap = abs(float(position_value) - desired_position)
            score = float(clip.get("total_score", 0.0) or 0.0) * 0.65 + (1.0 - min(position_gap, 1.0)) * 0.35
            if score > best_score:
                best = clip
                best_score = score
        if best is None:
            continue
        used.add(str(best.get("clip_id", "") or ""))
        selected.append(dict(best))
    return selected


def _build_narrated_clip_pool(
    candidate_clips: List[Dict[str, Any]],
    scene_candidate_clips: List[Dict[str, Any]],
    narration_units: List[Dict[str, Any]],
    target_duration_seconds: int,
) -> List[Dict[str, Any]]:
    combined_candidates = _merge_unique_clips(candidate_clips, scene_candidate_clips)
    if not combined_candidates:
        return []

    desired_count = max(len(narration_units) * 2, round(target_duration_seconds / 18), 8)
    coverage_count = max(len(narration_units), round(target_duration_seconds / 30), 6)
    hero_clips = _select_diverse_clips(combined_candidates, desired_count)
    coverage_clips = _build_coverage_clips(combined_candidates, coverage_count)
    raw_audio_clips = _select_diverse_clips(
        (dict(item) for item in combined_candidates if item.get("raw_audio_worthy")),
        top_k=max(round(desired_count / 3), 2),
        lambda_relevance=0.78,
    )
    chronology_clips = sorted(
        (dict(item) for item in combined_candidates),
        key=lambda x: (float(x.get("start", 0.0) or 0.0), -float(x.get("total_score", 0.0) or 0.0)),
    )[:desired_count]
    return _merge_unique_clips(hero_clips, coverage_clips, raw_audio_clips, chronology_clips, scene_candidate_clips)


def _collect_matched_clips(narration_matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clips: List[Dict[str, Any]] = []
    for match in narration_matches or []:
        clip_group = list(match.get("clip_group") or [])
        if clip_group:
            for item in clip_group:
                clip = dict(item)
                clip["prevent_merge"] = True
                clips.append(clip)
        elif match.get("clip"):
            clip = dict(match.get("clip") or {})
            clip["prevent_merge"] = True
            clips.append(clip)
    return clips


def _split_text_clauses(text: str) -> List[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    buffer = raw
    for splitter in ["。", "！", "？", ".", "!", "?", "；", ";", "，", ",", "：", ":"]:
        buffer = buffer.replace(splitter, splitter + "\n")
    return [item.strip() for item in buffer.splitlines() if item.strip()]


def _split_narration_text_for_group(text: str, group_size: int) -> List[str]:
    raw = str(text or "").strip()
    if group_size <= 1 or not raw:
        return [raw]

    clauses = _split_text_clauses(raw)
    if not clauses:
        return [raw]

    while len(clauses) < group_size:
        longest_index = max(range(len(clauses)), key=lambda idx: len(clauses[idx]))
        longest = clauses[longest_index]
        if len(longest) <= 10:
            break
        midpoint = max(len(longest) // 2, 1)
        left = longest[:midpoint].strip("，,；;：: ")
        right = longest[midpoint:].strip("，,；;：: ")
        if not left or not right:
            break
        clauses = clauses[:longest_index] + [left, right] + clauses[longest_index + 1 :]

    if len(clauses) <= group_size:
        return clauses + [""] * (group_size - len(clauses))

    parts: List[str] = []
    cursor = 0
    for idx in range(group_size):
        remaining_clauses = len(clauses) - cursor
        remaining_slots = group_size - idx
        take = max((remaining_clauses + remaining_slots - 1) // remaining_slots, 1)
        piece = "".join(clauses[cursor : cursor + take]).strip()
        parts.append(piece)
        cursor += take
    return parts


def _pick_keyframe_centers(clip: Dict[str, Any], desired_count: int) -> List[float]:
    start = float(clip.get("start", 0.0) or 0.0)
    end = float(clip.get("end", start) or start)
    duration = max(end - start, 0.5)
    count = max(min(int(desired_count or 1), max(int(duration / 1.1), 1), 4), 1)

    candidates = []
    for value in clip.get("keyframe_candidates") or []:
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        if start <= timestamp <= end:
            candidates.append(round(timestamp, 3))
    candidates = sorted(dict.fromkeys(candidates))

    if not candidates:
        return [round(start + duration * ((idx + 0.5) / count), 3) for idx in range(count)]
    if len(candidates) <= count:
        return candidates

    selected: List[float] = []
    for slot in range(count):
        target_index = round(slot * (len(candidates) - 1) / max(count - 1, 1))
        selected.append(candidates[target_index])
    return sorted(dict.fromkeys(selected))


def _pick_boundary_points(clip: Dict[str, Any], desired_count: int) -> List[float]:
    start = float(clip.get("start", 0.0) or 0.0)
    end = float(clip.get("end", start) or start)
    raw_points = []
    for value in clip.get("boundary_candidates") or []:
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        if start + 0.35 <= timestamp <= end - 0.35:
            raw_points.append(round(timestamp, 3))
    points = sorted(dict.fromkeys(raw_points))
    target = max(min(int(desired_count or 1) - 1, 3), 0)
    if target <= 0 or not points:
        return []
    if len(points) <= target:
        return points

    selected: List[float] = []
    for slot in range(target):
        desired_position = (slot + 1) / (target + 1)
        best_point = min(points, key=lambda point: abs(((point - start) / max(end - start, 0.001)) - desired_position))
        selected.append(best_point)
    return sorted(dict.fromkeys(selected))


def _build_intra_scene_subshots(clip: Dict[str, Any], desired_count: int) -> List[Dict[str, Any]]:
    start = float(clip.get("start", 0.0) or 0.0)
    end = float(clip.get("end", start) or start)
    duration = max(end - start, 0.5)
    if duration < 3.4:
        return [dict(clip)]

    boundary_points = _pick_boundary_points(clip, desired_count)
    if boundary_points:
        boundaries = [start] + boundary_points + [end]
    else:
        centers = _pick_keyframe_centers(clip, desired_count)
        if len(centers) <= 1:
            return [dict(clip)]
        boundaries = [start]
        for left, right in zip(centers[:-1], centers[1:]):
            boundaries.append(round((left + right) / 2.0, 3))
        boundaries.append(end)

    if len(boundaries) <= 2:
        return [dict(clip)]

    subshots: List[Dict[str, Any]] = []
    for idx, (sub_start, sub_end) in enumerate(zip(boundaries[:-1], boundaries[1:]), start=1):
        if sub_end - sub_start < 0.45:
            continue
        subshot = dict(clip)
        subshot["clip_id"] = f"{str(clip.get('clip_id', 'clip'))}__shot_{idx:02d}"
        subshot["start"] = round(sub_start, 3)
        subshot["end"] = round(sub_end, 3)
        subshot["duration"] = round(max(sub_end - sub_start, 0.5), 3)
        subshot["selection_reason"] = list(
            dict.fromkeys(list(subshot.get("selection_reason") or []) + ["intra_scene_cut"])
        )
        subshot["tags"] = list(dict.fromkeys(list(subshot.get("tags") or []) + ["intra_scene_cut"]))
        subshot["prevent_merge"] = True
        subshot["parent_clip_id"] = clip.get("clip_id", "")
        subshot["subshot_index"] = idx
        subshots.append(subshot)

    return subshots or [dict(clip)]


def _expand_group_with_intra_scene_subshots(match: Dict[str, Any], clip_group: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not clip_group:
        return []
    if len(clip_group) > 1:
        return [dict(item) for item in clip_group]

    rhythm = dict(match.get("rhythm_config") or {})
    preferred_group_size = max(int(rhythm.get("preferred_group_size", 2) or 2), 1)
    anchor = dict(clip_group[0])
    if str(anchor.get("source", "") or "") != "scene":
        return [anchor]
    if preferred_group_size <= 1:
        return [anchor]

    expanded = _build_intra_scene_subshots(anchor, min(preferred_group_size, 3))
    return expanded if len(expanded) > 1 else [anchor]


def _build_composition_plan(
    *,
    mode: str,
    video_path: str,
    movie_title: str,
    target_duration_seconds: int,
    visual_mode: str,
    highlight_profile: Dict[str, Any],
    highlight_capabilities: Dict[str, Any],
    candidate_stats: Dict[str, Any],
    selected_clips: List[Dict[str, Any]],
    narration_text: str,
    narration_audio_path: str,
    prefer_raw_audio: bool,
    narration_matches: List[Dict[str, Any]],
) -> Dict[str, Any]:
    segments: List[Dict[str, Any]] = []
    cursor = 0.0
    if mode == "narrated_highlight_edit" and narration_matches:
        for match_idx, match in enumerate(narration_matches, start=1):
            clip_group = list(match.get("clip_group") or [])
            if not clip_group and match.get("clip"):
                clip_group = [dict(match.get("clip") or {})]
            if bool(match.get("preserve_sentence_boundary")):
                clip_group = [dict(clip_group[0])] if clip_group else []
            else:
                clip_group = _expand_group_with_intra_scene_subshots(match, clip_group)
            narration = str(match.get("text", "") or "")
            group_narrations = _split_narration_text_for_group(narration, len(clip_group))
            shot_durations = _plan_group_shot_durations(match, clip_group)
            for group_idx, (clip, shot_duration) in enumerate(zip(clip_group, shot_durations), start=1):
                shot_narration = group_narrations[group_idx - 1] if group_idx - 1 < len(group_narrations) else ""
                start = round(float(clip.get("start", 0.0) or 0.0), 3)
                original_end = round(float(clip.get("end", start) or start), 3)
                duration = round(max(float(shot_duration or 0.0), 0.5), 3)
                end = round(min(original_end, start + duration), 3)
                duration = round(max(end - start, 0.5), 3)
                audio_plan = _decide_group_audio_plan(
                    match=match,
                    clip=clip,
                    group_idx=group_idx,
                    group_size=len(clip_group),
                    prefer_raw_audio=prefer_raw_audio,
                    has_narration=bool(shot_narration),
                )
                reasons = list(clip.get("selection_reason") or [])
                if match.get("story_stage"):
                    reasons.append(f"match:{match['story_stage']}")
                if match.get("match_strategy"):
                    reasons.append(f"map:{match['match_strategy']}")
                if match.get("rhythm_profile"):
                    reasons.append(f"rhythm:{match['rhythm_profile']}")
                reasons.append(f"audio:{audio_plan['strategy']}")
                if group_idx > 1:
                    reasons.append("group_follow_shot")
                else:
                    reasons.append("group_anchor_shot")

                segments.append(
                    {
                        "segment_id": f"seg_{match_idx:04d}_{group_idx:02d}",
                        "video_start": start,
                        "video_end": end,
                        "timeline_start": round(cursor, 3),
                        "timeline_end": round(cursor + duration, 3),
                        "audio_mode": audio_plan["audio_mode"],
                        "narration_text": shot_narration if audio_plan["carry_narration"] else "",
                        "narration_audio_path": narration_audio_path if shot_narration and audio_plan["carry_narration"] else "",
                        "selection_reason": reasons,
                        "picture": str(clip.get("scene_summary", "") or clip.get("subtitle_text", "") or ""),
                        "audio_strategy": audio_plan["strategy"],
                        "source_clip_id": clip.get("clip_id", f"clip_{match_idx:04d}_{group_idx:02d}"),
                        "clip_source": str(clip.get("source", "") or ""),
                        "source_scene_id": str(clip.get("source_scene_id", "") or ""),
                        "raw_audio_worthy": bool(clip.get("raw_audio_worthy")),
                        "parent_clip_id": clip.get("parent_clip_id", ""),
                        "subshot_index": clip.get("subshot_index"),
                        "trim_strategy": str(clip.get("trim_strategy", "") or ""),
                        "original_duration": clip.get("original_duration", clip.get("duration", duration)),
                        "planned_duration": duration,
                        "match_score": match.get("match_score"),
                        "match_strategy": match.get("match_strategy", ""),
                    }
                )
                cursor += duration
        return {
            "mode": mode,
            "video_path": video_path,
            "movie_title": movie_title,
            "target_duration_seconds": target_duration_seconds,
            "segments": segments,
            "audio_tracks": {
                "bgm_path": "",
                "narration_path": narration_audio_path or "",
                "keep_raw_audio": bool(prefer_raw_audio),
            },
            "metadata": {
                "selected_clip_count": len(selected_clips),
                "generated_at": datetime.now().isoformat(),
                "narrated_match_count": len(narration_matches or []),
                "has_external_narration": bool(str(narration_text or "").strip()),
                "visual_mode": visual_mode,
                "highlight_profile": dict(highlight_profile or {}),
                "highlight_capabilities": dict(highlight_capabilities or {}),
                "candidate_stats": dict(candidate_stats or {}),
                "grouped_match_mode": True,
                "rhythm_shot_mode": True,
            },
        }

    matched_by_clip_id = {
        str(item.get("clip_id") or ""): item for item in (narration_matches or []) if item.get("clip_id")
    }

    for idx, clip in enumerate(selected_clips, start=1):
        start = round(float(clip.get("start", 0.0) or 0.0), 3)
        end = round(float(clip.get("end", start) or start), 3)
        duration = round(max(end - start, 0.5), 3)
        matched = matched_by_clip_id.get(str(clip.get("clip_id", "") or ""))
        narration = str((matched or {}).get("text", "") or "")
        audio_plan = _decide_group_audio_plan(
            match=matched or {},
            clip=clip,
            group_idx=1,
            group_size=1,
            prefer_raw_audio=prefer_raw_audio,
            has_narration=bool(narration),
        )

        if mode == "narrated_highlight_edit":
            audio_mode = audio_plan["audio_mode"]
        else:
            audio_mode = "raw"

        reasons = list(clip.get("selection_reason") or [])
        if matched and matched.get("story_stage"):
            reasons.append(f"match:{matched['story_stage']}")
        if matched and matched.get("match_strategy"):
            reasons.append(f"map:{matched['match_strategy']}")
        if mode == "narrated_highlight_edit":
            reasons.append(f"audio:{audio_plan['strategy']}")

        segments.append(
            {
                "segment_id": f"seg_{idx:04d}",
                "video_start": start,
                "video_end": end,
                "timeline_start": round(cursor, 3),
                "timeline_end": round(cursor + duration, 3),
                "audio_mode": audio_mode,
                "narration_text": narration if audio_plan["carry_narration"] else "",
                "narration_audio_path": narration_audio_path if narration and audio_plan["carry_narration"] else "",
                "selection_reason": reasons,
                "picture": str(clip.get("scene_summary", "") or clip.get("subtitle_text", "") or ""),
                "audio_strategy": audio_plan["strategy"],
                "source_clip_id": clip.get("clip_id", f"clip_{idx:04d}"),
                "clip_source": str(clip.get("source", "") or ""),
                "source_scene_id": str(clip.get("source_scene_id", "") or ""),
                "raw_audio_worthy": bool(clip.get("raw_audio_worthy")),
                "parent_clip_id": clip.get("parent_clip_id", ""),
                "subshot_index": clip.get("subshot_index"),
                "trim_strategy": str(clip.get("trim_strategy", "") or ""),
                "original_duration": clip.get("original_duration", clip.get("duration", duration)),
                "planned_duration": clip.get("planned_duration", duration),
                "match_score": (matched or {}).get("match_score"),
                "match_strategy": (matched or {}).get("match_strategy", ""),
            }
        )
        cursor += duration

    return {
        "mode": mode,
        "video_path": video_path,
        "movie_title": movie_title,
        "target_duration_seconds": target_duration_seconds,
        "segments": segments,
        "audio_tracks": {
            "bgm_path": "",
            "narration_path": narration_audio_path or "",
            "keep_raw_audio": bool(prefer_raw_audio),
        },
        "metadata": {
            "selected_clip_count": len(selected_clips),
            "generated_at": datetime.now().isoformat(),
            "narrated_match_count": len(narration_matches or []),
            "has_external_narration": bool(str(narration_text or "").strip()),
            "visual_mode": visual_mode,
            "highlight_profile": dict(highlight_profile or {}),
            "highlight_capabilities": dict(highlight_capabilities or {}),
            "candidate_stats": dict(candidate_stats or {}),
        },
    }


def _plan_group_shot_durations(match: Dict[str, Any], clip_group: List[Dict[str, Any]]) -> List[float]:
    if not clip_group:
        return []

    rhythm = dict(match.get("rhythm_config") or {})
    profile = str(match.get("rhythm_profile") or rhythm.get("profile") or "balanced")
    target_seconds = float(match.get("target_seconds", 0.0) or 0.0)
    min_shot = float(rhythm.get("min_shot_seconds", 1.2) or 1.2)
    max_shot = float(rhythm.get("max_shot_seconds", 3.0) or 3.0)
    has_scene_refined = any("scene_refined" in set(str(tag) for tag in (clip.get("tags") or [])) for clip in clip_group)
    scene_count = sum(1 for clip in clip_group if str(clip.get("source", "") or "") == "scene")
    if has_scene_refined and len(clip_group) > 1:
        min_shot = min(min_shot, 1.0 if profile in {"fast", "pivot"} else 1.15)
        max_shot = min(max_shot, 2.4 if profile in {"fast", "pivot"} else 2.8)
    available_total = sum(max(float(item.get("duration", 0.0) or 0.0), 0.5) for item in clip_group)
    if target_seconds <= 0.0:
        target_seconds = available_total
    budget = min(available_total, max(target_seconds * (1.0 if has_scene_refined else 1.05), min_shot * len(clip_group)))

    if profile == "fast":
        weights = [0.5, 0.3, 0.2]
    elif profile == "pivot":
        weights = [0.58, 0.27, 0.15]
    elif profile == "steady":
        weights = [0.72, 0.28, 0.0]
    elif profile == "resolve":
        weights = [0.68, 0.32, 0.0]
    else:
        weights = [0.62, 0.24, 0.14]

    weights = weights[: len(clip_group)]
    if not weights:
        weights = [1.0]
    total_weight = sum(weights)
    if total_weight <= 0:
        weights = [1.0 for _ in clip_group]
        total_weight = float(len(weights))
    normalized = [w / total_weight for w in weights]

    if scene_count >= max(1, len(clip_group) - 1) and len(clip_group) > 1:
        clip_weights = []
        for idx, clip in enumerate(clip_group):
            base = normalized[min(idx, len(normalized) - 1)]
            source_bonus = 0.08 if str(clip.get("source", "") or "") == "scene" else -0.04
            score_bonus = min(float(clip.get("total_score", 0.0) or 0.0), 1.0) * 0.08
            clip_weights.append(max(base + source_bonus + score_bonus, 0.05))
        weight_total = sum(clip_weights) or float(len(clip_weights))
        normalized = [weight / weight_total for weight in clip_weights]

    planned: List[float] = []
    for idx, clip in enumerate(clip_group):
        available = max(float(clip.get("duration", 0.0) or 0.0), 0.5)
        weighted = budget * normalized[min(idx, len(normalized) - 1)]
        if available < min_shot:
            planned.append(round(available, 3))
            continue
        duration = min(available, max_shot, max(min_shot, weighted))
        planned.append(round(duration, 3))

    return planned


def _decide_group_audio_plan(
    *,
    match: Dict[str, Any],
    clip: Dict[str, Any],
    group_idx: int,
    group_size: int,
    prefer_raw_audio: bool,
    has_narration: bool,
) -> Dict[str, Any]:
    stage = str(match.get("story_stage", "") or "")
    rhythm = str(match.get("rhythm_profile", "") or "")
    raw_worthy = bool(clip.get("raw_audio_worthy"))
    short_anchor = float(match.get("target_seconds", 0.0) or 0.0) <= 3.0

    if not has_narration:
        return {
            "audio_mode": "raw",
            "carry_narration": False,
            "strategy": "raw_follow",
        }

    if prefer_raw_audio and raw_worthy and (stage in {"conflict", "climax", "reveal", "ending"} or rhythm in {"fast", "pivot"}):
        return {
            "audio_mode": "ducked_raw",
            "carry_narration": True,
            "strategy": "ducked_narration",
        }

    if prefer_raw_audio and raw_worthy and short_anchor and group_size > 1:
        return {
            "audio_mode": "ducked_raw",
            "carry_narration": True,
            "strategy": "keyline_ducked",
        }

    return {
        "audio_mode": "tts",
        "carry_narration": True,
        "strategy": "clean_tts",
    }


def _write_outputs(video_hash: str, composition_plan: Dict[str, Any], script_items: List[Dict[str, Any]]) -> Dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    composition_plan_path = os.path.join(utils.script_dir(), f"{video_hash}_highlight_edit_{timestamp}.json")
    script_path = os.path.join(utils.script_dir(), f"{video_hash}_highlight_edit_script_{timestamp}.json")
    os.makedirs(os.path.dirname(composition_plan_path), exist_ok=True)
    with open(composition_plan_path, "w", encoding="utf-8") as f:
        json.dump(composition_plan, f, ensure_ascii=False, indent=2)
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_items, f, ensure_ascii=False, indent=2)
    return {
        "composition_plan_path": composition_plan_path,
        "script_path": script_path,
    }
