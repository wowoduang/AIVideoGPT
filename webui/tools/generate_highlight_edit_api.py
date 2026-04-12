from __future__ import annotations

import traceback
from typing import Any, Dict

import streamlit as st
from loguru import logger

from app.services.subtitle_text import decode_subtitle_bytes
from app.services.upload_validation import InputValidationError, ensure_existing_file
from webui.services.job_execution import extract_job_result, poll_job_until_complete
from webui.utils import job_runner


VALID_VIDEO_EXTS = (".mp4", ".mov", ".avi", ".flv", ".mkv")


def _sync_highlight_subtitle_state(subtitle_result: Dict[str, Any]) -> None:
    subtitle_path = str((subtitle_result or {}).get("subtitle_path") or "").strip()
    if not subtitle_path:
        return

    st.session_state["subtitle_path"] = subtitle_path
    st.session_state["highlight_subtitle_path"] = subtitle_path

    try:
        with open(subtitle_path, "rb") as file_obj:
            decoded = decode_subtitle_bytes(file_obj.read())
        st.session_state["subtitle_content"] = decoded.text
        st.session_state["highlight_subtitle_content"] = decoded.text
    except Exception as exc:
        logger.warning("failed to sync highlight subtitle content from {}: {}", subtitle_path, exc)


def _build_highlight_request(video_path: str) -> Dict[str, Any]:
    return {
        "video_path": video_path,
        "mode": str(st.session_state.get("highlight_edit_mode", "highlight_recut") or "highlight_recut"),
        "target_duration_seconds": int(st.session_state.get("highlight_target_minutes", 8) * 60),
        "movie_title": str(st.session_state.get("highlight_movie_title", "") or ""),
        "highlight_profile": str(st.session_state.get("highlight_movie_genre", "auto") or "auto"),
        "subtitle_path": str(st.session_state.get("highlight_subtitle_path", "") or ""),
        "narration_text": str(st.session_state.get("highlight_narration_text", "") or ""),
        "narration_audio_path": "",
        "prefer_raw_audio": bool(st.session_state.get("highlight_prefer_raw_audio", True)),
        "visual_mode": str(st.session_state.get("highlight_visual_mode", "auto") or "auto"),
        "regenerate_subtitle": st.session_state.get("highlight_subtitle_source_mode") == "auto_subtitle",
        "subtitle_backend": str(st.session_state.get("subtitle_asr_backend", "faster-whisper") or "faster-whisper"),
    }


def _apply_highlight_pipeline_success(pipeline_result: Dict[str, Any]) -> None:
    st.session_state["video_clip_json"] = pipeline_result.get("script_items", [])
    st.session_state["video_clip_json_path"] = pipeline_result.get("script_path", "")
    st.session_state["highlight_edit_composition_plan"] = pipeline_result.get("composition_plan", {})
    st.session_state["highlight_edit_composition_plan_path"] = pipeline_result.get("composition_plan_path", "")
    st.session_state["highlight_edit_candidate_clips"] = pipeline_result.get("candidate_clips", [])
    st.session_state["highlight_edit_plot_candidate_clips"] = pipeline_result.get("plot_candidate_clips", [])
    st.session_state["highlight_edit_scene_candidate_clips"] = pipeline_result.get("scene_candidate_clips", [])
    st.session_state["highlight_edit_candidate_stats"] = pipeline_result.get("candidate_stats", {})
    st.session_state["highlight_edit_selected_clips"] = pipeline_result.get("selected_clips", [])
    st.session_state["highlight_edit_plot_chunks"] = pipeline_result.get("plot_chunks", [])
    st.session_state["highlight_edit_narration_units"] = pipeline_result.get("narration_units", [])
    st.session_state["highlight_edit_narration_matches"] = pipeline_result.get("narration_matches", [])
    st.session_state["highlight_edit_profile"] = pipeline_result.get("highlight_profile", {})
    st.session_state["highlight_edit_capabilities"] = pipeline_result.get("highlight_capabilities", {})
    _sync_highlight_subtitle_state(pipeline_result.get("subtitle_result") or {})


def _handle_highlight_job_success(pipeline_result: Dict[str, Any]) -> None:
    _apply_highlight_pipeline_success(pipeline_result)
    st.success(f"已生成 {len(pipeline_result.get('script_items', []))} 段精彩粗剪脚本")
    if pipeline_result.get("script_path"):
        st.caption(f"脚本文件: {pipeline_result['script_path']}")
    if pipeline_result.get("composition_plan_path"):
        st.caption(f"粗剪规划文件: {pipeline_result['composition_plan_path']}")


def generate_highlight_edit(tr, params) -> None:
    try:
        video_path = getattr(params, "video_origin_path", None)
        if not video_path or not str(video_path).strip():
            st.error("请先选择视频文件")
            return

        try:
            video_path = ensure_existing_file(
                str(video_path),
                label="视频",
                allowed_exts=VALID_VIDEO_EXTS,
            )
        except InputValidationError as exc:
            st.error(str(exc))
            return

        request = _build_highlight_request(video_path)
        if request["mode"] == "narrated_highlight_edit" and not str(request["narration_text"]).strip():
            st.error(tr("Narrated highlight mode requires narration text"))
            return

        with st.spinner("正在生成精彩粗剪脚本..."):
            job = job_runner.start_highlight_script_job(request)
        poll_job_until_complete(
            tr=tr,
            job=job,
            ui=st,
            fetch_status=job_runner.get_job_status,
            on_complete=_handle_highlight_job_success,
            extract_result=lambda task: extract_job_result(
                task,
                ("script_items", "composition_plan", "candidate_clips", "selected_clips"),
            ),
            completion_status_text="精彩粗剪主链完成",
            empty_result_error="高光脚本任务已完成，但没有返回可用结果",
            failure_prefix="精彩粗剪主链执行失败",
            query_failure_prefix="任务状态获取失败",
        )

    except Exception as err:
        st.error(f"生成过程中发生错误: {err}")
        logger.exception("[highlight_edit_api] failed to generate script\n{}", traceback.format_exc())
