from __future__ import annotations

import time
import traceback

import streamlit as st
from loguru import logger

from app.services.highlight_edit_pipeline import run_highlight_edit_pipeline
from app.services.subtitle_text import decode_subtitle_bytes
from app.services.upload_validation import InputValidationError, ensure_existing_file


VALID_VIDEO_EXTS = (".mp4", ".mov", ".avi", ".flv", ".mkv")


def _sync_highlight_subtitle_state(subtitle_result):
    subtitle_path = str((subtitle_result or {}).get("subtitle_path") or "").strip()
    if not subtitle_path:
        return

    st.session_state["subtitle_path"] = subtitle_path
    st.session_state["highlight_subtitle_path"] = subtitle_path

    try:
        with open(subtitle_path, "rb") as f:
            decoded = decode_subtitle_bytes(f.read())
        st.session_state["subtitle_content"] = decoded.text
        st.session_state["highlight_subtitle_content"] = decoded.text
    except Exception as exc:
        logger.warning("Failed to sync highlight subtitle content from {}: {}", subtitle_path, exc)


def generate_highlight_edit(tr, params):
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(progress: int, message: str = ""):
        progress_bar.progress(progress)
        status_text.text(f"{progress}% - {message}" if message else f"进度: {progress}%")

    try:
        with st.spinner("正在生成精彩粗剪脚本..."):
            video_path = getattr(params, "video_origin_path", None)
            if not video_path or not str(video_path).strip():
                st.error("请先选择视频文件")
                st.stop()

            try:
                video_path = ensure_existing_file(
                    str(video_path),
                    label="视频",
                    allowed_exts=VALID_VIDEO_EXTS,
                )
            except InputValidationError as e:
                st.error(str(e))
                st.stop()

            mode = st.session_state.get("highlight_edit_mode", "highlight_recut")
            narration_text = str(st.session_state.get("highlight_narration_text", "") or "")
            if mode == "narrated_highlight_edit" and not narration_text.strip():
                st.error(tr("Narrated highlight mode requires narration text"))
                st.stop()

            pipeline_result = run_highlight_edit_pipeline(
                video_path=video_path,
                mode=mode,
                target_duration_seconds=int(st.session_state.get("highlight_target_minutes", 8) * 60),
                movie_title=st.session_state.get("highlight_movie_title", ""),
                highlight_profile=st.session_state.get("highlight_movie_genre", "auto"),
                subtitle_path=st.session_state.get("highlight_subtitle_path", ""),
                narration_text=narration_text,
                prefer_raw_audio=bool(st.session_state.get("highlight_prefer_raw_audio", True)),
                visual_mode=st.session_state.get("highlight_visual_mode", "auto"),
                regenerate_subtitle=st.session_state.get("highlight_subtitle_source_mode") == "auto_subtitle",
                subtitle_backend=st.session_state.get("subtitle_asr_backend", "faster-whisper"),
                progress_callback=update_progress,
            )
            if not pipeline_result.get("success"):
                st.error(f"精彩粗剪主链执行失败: {pipeline_result.get('error', 'unknown_error')}")
                st.stop()

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

            subtitle_result = pipeline_result.get("subtitle_result") or {}
            _sync_highlight_subtitle_state(subtitle_result)

            st.success(f"已生成 {len(pipeline_result.get('script_items', []))} 段精彩粗剪脚本")
            if pipeline_result.get("script_path"):
                st.caption(f"脚本文件: {pipeline_result['script_path']}")
            if pipeline_result.get("composition_plan_path"):
                st.caption(f"粗剪规划文件: {pipeline_result['composition_plan_path']}")

        time.sleep(0.1)
        progress_bar.progress(100)
        status_text.text("精彩粗剪主链完成")

    except Exception as err:
        progress_bar.progress(100)
        st.error(f"生成过程中发生错误: {str(err)}")
        logger.exception(f"[精彩粗剪] 生成脚本时发生错误\n{traceback.format_exc()}")
