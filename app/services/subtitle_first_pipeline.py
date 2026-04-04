from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.services.evidence_fuser import fuse_scene_evidence
from app.services.generate_narration_script import generate_narration_from_scene_evidence
from app.services.plot_chunker import build_plot_chunks_from_subtitles
from app.services.plot_understanding import add_local_understanding, build_global_summary
from app.services.preflight_check import PreflightError, validate_script_items
from app.services.representative_frames import extract_representative_frames_for_scenes
from app.services.script_fallback import ensure_script_shape
from app.services.story_boundary_aligner import align_story_boundaries, collect_candidate_boundaries
from app.services.story_validator import validate_story_segments
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
    target_minutes = _resolve_target_minutes(generation_mode, scene_overrides)
    effective_visual_mode = _resolve_visual_mode(visual_mode or scene_overrides.get("visual_mode", "auto"))
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

    progress(24, "字幕粗分段与剧情块规划...")
    plot_chunks = build_plot_chunks_from_subtitles(
        segments,
        target_duration_minutes=target_minutes,
        narrative_strategy=narrative_strategy,
        accuracy_priority=accuracy_priority,
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
        }
    )

    progress(46, "剧情边界吸附...")
    subtitle_boundaries = collect_candidate_boundaries(segments)
    plot_chunks = align_story_boundaries(
        plot_chunks,
        candidate_boundaries=subtitle_boundaries,
        snap_window=8.0,
    )

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

    progress(88, "生成影视解说脚本...")
    script_items = generate_narration_from_scene_evidence(
        scene_evidence=scene_evidence,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
        style=style or "general",
    )
    if not script_items:
        raise ValueError("未生成有效脚本片段")

    script_items = ensure_script_shape(script_items)

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

    progress(100, "影视解说主链完成")
    return {
        "script_items": script_items,
        "script_path": output_script_path,
        "evidence": scene_evidence,
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
