from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.services.evidence_fuser import fuse_scene_evidence
from app.services.generate_narration_script import generate_narration_from_scene_evidence
from app.services.plot_chunker import build_plot_chunks_from_subtitles
from app.services.plot_understanding import add_local_understanding, build_global_summary
from app.services.preflight_check import PreflightError, validate_script_items
from app.services.representative_frames import extract_representative_frames_for_scenes
from app.services.script_fallback import ensure_script_shape
from app.services.subtitle_pipeline import build_subtitle_segments
from app.utils import utils


DEFAULT_SOURCE_TEXT_MAP = {
    "external_srt": "外挂 SRT 字幕",
    "external_ass": "外挂 ASS/SSA 字幕",
    "external_vtt": "外挂 VTT 字幕",
    "generated_srt": "自动生成字幕",
}


def run_plot_first_pipeline(
    video_path: str,
    subtitle_path: str = "",
    *,
    text_api_key: str = "",
    text_base_url: str = "",
    text_model: str = "",
    style: str = "short_drama",
    visual_mode: str = "boost",
    regenerate_subtitle: bool = False,
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
            subtitle_path=subtitle_path,
            text_api_key=text_api_key,
            text_base_url=text_base_url,
            text_model=text_model,
            style=style,
            visual_mode=visual_mode,
            regenerate_subtitle=regenerate_subtitle,
            progress=_progress,
        )
    except Exception as exc:
        logger.exception(f"剧情优先管线执行失败: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "subtitle_result": {},
            "plot_chunks": [],
            "frame_records": [],
            "scene_evidence": [],
            "global_summary": {},
            "script_items": [],
            "script_path": "",
            "analysis_path": "",
            "frame_output_dir": "",
        }


def _run(
    video_path: str,
    subtitle_path: str,
    text_api_key: str,
    text_base_url: str,
    text_model: str,
    style: str,
    visual_mode: str,
    regenerate_subtitle: bool,
    progress: Callable[[int, str], None],
) -> Dict[str, Any]:
    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    video_hash = utils.md5(video_path + str(os.path.getmtime(video_path)))
    output_paths = _build_output_paths(video_hash)

    # 1) 字幕统一入口
    progress(10, "准备字幕...")
    subtitle_result = build_subtitle_segments(
        video_path=video_path,
        explicit_subtitle_path=subtitle_path,
        regenerate=regenerate_subtitle,
    )
    subtitle_segments = subtitle_result.get("segments") or []
    if not subtitle_segments:
        raise ValueError(
            f"无法获取有效字幕 (source={subtitle_result.get('source')}, error={subtitle_result.get('error')})"
        )
    logger.info(
        "剧情优先 M1 完成: source={}, subtitles={}, subtitle_path={}",
        subtitle_result.get("source"),
        len(subtitle_segments),
        subtitle_result.get("subtitle_path"),
    )

    # 2) 字幕 -> 剧情块
    progress(28, "整理剧情块...")
    plot_chunks = build_plot_chunks_from_subtitles(subtitle_segments)
    if not plot_chunks:
        raise ValueError("剧情块构建失败，未生成任何 plot chunk")
    logger.info("剧情优先 M2 完成: {} 个剧情块", len(plot_chunks))

    # 3) 按剧情块回抽代表帧
    progress(45, "按剧情块抽取代表帧...")
    frame_output_dir = output_paths["frame_output_dir"]
    frame_records = extract_representative_frames_for_scenes(
        video_path=video_path,
        scenes=plot_chunks,
        visual_mode=visual_mode,
        output_dir=frame_output_dir,
        max_frames_dialogue=2,
        max_frames_visual_only=3,
        max_frames_long_scene=3,
        long_scene_threshold=25.0,
    )
    logger.info(
        "剧情优先 M3 完成: frames={}, frame_output_dir={}",
        len(frame_records),
        frame_output_dir,
    )

    # 4) 证据融合 + 剧情理解
    progress(60, "构建剧情证据...")
    scene_evidence = fuse_scene_evidence(
        scenes=plot_chunks,
        frame_records=frame_records,
        visual_observations={},
    )
    scene_evidence = add_local_understanding(scene_evidence)
    global_summary = build_global_summary(
        scene_evidence,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
    )
    for pkg in scene_evidence:
        pkg["_global_summary"] = global_summary
        pkg["evidence_mode"] = "plot_first"
        pkg["visual_budget_meta"] = {
            "estimated_tokens": 0,
            "estimated_cost_cny": 0.0,
            "capped": 0,
            "original": len(pkg.get("frame_paths") or []),
        }
    logger.info("剧情优先 M4 完成: evidence={}", len(scene_evidence))

    # 5) 生成脚本
    progress(78, "生成解说脚本...")
    script_items = generate_narration_from_scene_evidence(
        scene_evidence=scene_evidence,
        api_key=text_api_key,
        base_url=text_base_url,
        model=text_model,
        style=style,
    )
    script_items = ensure_script_shape(script_items)
    if not script_items:
        raise ValueError("未生成有效脚本片段")

    warnings: List[str] = []
    try:
        validate_script_items(script_items)
    except PreflightError as exc:
        warnings.append(str(exc))
        logger.warning("剧情优先脚本预检警告: {}", exc)

    # 6) 持久化输出
    progress(90, "保存分析结果与脚本...")
    analysis_payload = {
        "mode": "short_drama_plot_first",
        "subtitle_result": subtitle_result,
        "subtitle_segments": subtitle_segments,
        "plot_chunks": plot_chunks,
        "frame_records": frame_records,
        "scene_evidence": scene_evidence,
        "global_summary": global_summary,
        "script_items": script_items,
        "warnings": warnings,
    }
    _write_json(output_paths["analysis_path"], analysis_payload)
    _write_json(output_paths["script_path"], script_items)
    logger.success(
        "剧情优先 M5 完成: script_items={}, script_path={}",
        len(script_items),
        output_paths["script_path"],
    )

    progress(100, "剧情优先链路完成")
    return {
        "success": True,
        "error": "",
        "subtitle_result": subtitle_result,
        "subtitle_source_text": DEFAULT_SOURCE_TEXT_MAP.get(
            subtitle_result.get("source"), subtitle_result.get("source") or "未知来源"
        ),
        "plot_chunks": plot_chunks,
        "frame_records": frame_records,
        "scene_evidence": scene_evidence,
        "global_summary": global_summary,
        "script_items": script_items,
        "script_path": output_paths["script_path"],
        "analysis_path": output_paths["analysis_path"],
        "frame_output_dir": frame_output_dir,
        "warnings": warnings,
    }


def _build_output_paths(video_hash: str) -> Dict[str, str]:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    analysis_dir = os.path.join(utils.storage_dir(), "temp", "analysis")
    frame_output_dir = os.path.join(utils.temp_dir("plot_frames"), video_hash)
    script_path = os.path.join(utils.script_dir(), f"{video_hash}_plot_first_{now}.json")
    analysis_path = os.path.join(analysis_dir, f"{video_hash}_plot_first_{now}.json")

    os.makedirs(analysis_dir, exist_ok=True)
    os.makedirs(frame_output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(script_path), exist_ok=True)

    return {
        "analysis_path": analysis_path,
        "script_path": script_path,
        "frame_output_dir": frame_output_dir,
    }


def _write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
