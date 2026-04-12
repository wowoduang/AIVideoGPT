from __future__ import annotations

import os

import streamlit as st
from loguru import logger

from app.config import config
from app.services.subtitle_text import read_subtitle_text


PENDING_SUBTITLE_SOURCE_MODE_KEY = "_pending_subtitle_source_mode"


def _normalize_subtitle_mode() -> str:
    mode = st.session_state.get("subtitle_source_mode", "existing_subtitle")
    return str(mode or "existing_subtitle").strip()


def _normalize_subtitle_path(subtitle_path: str, subtitle_mode: str) -> str:
    value = str(subtitle_path or "").strip()
    if value.upper() == "AUTO":
        return ""
    if subtitle_mode == "auto_subtitle":
        return ""
    return value


def _resolve_asr_backend() -> str:
    return str(st.session_state.get("subtitle_asr_backend", "faster-whisper") or "faster-whisper").strip()


def _resolve_cache_mode() -> str:
    return str(st.session_state.get("subtitle_cache_mode", "clear_and_regenerate") or "clear_and_regenerate").strip()


def _resolve_review_mode() -> str:
    return str(st.session_state.get("subtitle_review_mode", "review_suspicious") or "review_suspicious").strip()


def _resolve_prologue_strategy() -> str:
    return str(st.session_state.get("prologue_strategy", "speech_first") or "speech_first").strip()


def _resolve_manual_prologue_end_time() -> str:
    return str(st.session_state.get("manual_prologue_end_time", "") or "").strip()


def _resolve_highlight_selectivity() -> str:
    return str(st.session_state.get("highlight_selectivity", "balanced") or "balanced").strip()


def _build_request(params, subtitle_path: str, video_theme: str, temperature: float) -> dict:
    text_provider = config.app.get("text_llm_provider", "gemini").lower()
    return {
        "video_path": params.video_origin_path,
        "subtitle_path": subtitle_path,
        "video_theme": video_theme,
        "temperature": temperature,
        "text_api_key": config.app.get(f"text_{text_provider}_api_key", ""),
        "text_model": config.app.get(f"text_{text_provider}_model_name", ""),
        "text_base_url": config.app.get(f"text_{text_provider}_base_url", ""),
        "generation_mode": st.session_state.get("generation_mode", "balanced"),
        "visual_mode": st.session_state.get("visual_mode", "auto"),
        "narration_style": st.session_state.get("narration_style", "general"),
        "target_duration_minutes": st.session_state.get("target_duration_minutes", 8),
        "narrative_strategy": st.session_state.get("narrative_strategy", "chronological"),
        "accuracy_priority": st.session_state.get("accuracy_priority", "high"),
        "highlight_only": bool(st.session_state.get("highlight_only_mode", False)),
        "highlight_selectivity": _resolve_highlight_selectivity(),
        "asr_backend": _resolve_asr_backend(),
        "cache_mode": _resolve_cache_mode(),
        "review_mode": _resolve_review_mode(),
        "prologue_strategy": _resolve_prologue_strategy(),
        "manual_prologue_end_time": _resolve_manual_prologue_end_time(),
    }


def _save_pipeline_success(pipeline_result: dict):
    st.session_state["video_clip_json"] = pipeline_result["script_items"]
    st.session_state["subtitle_first_evidence"] = pipeline_result.get("evidence", [])
    st.session_state["subtitle_first_global_summary"] = pipeline_result.get("global_summary", {})
    st.session_state["subtitle_first_highlights"] = pipeline_result.get("story_highlights", [])
    st.session_state["subtitle_first_full_understanding"] = pipeline_result.get("full_subtitle_understanding", {})
    st.session_state["subtitle_first_llm_highlight_plan"] = pipeline_result.get("llm_highlight_plan", {})
    st.session_state["video_clip_json_path"] = pipeline_result.get(
        "composition_script_path",
        pipeline_result.get("script_path", st.session_state.get("video_clip_json_path", "")),
    )
    if pipeline_result.get("highlight_script_path"):
        st.session_state["subtitle_first_highlight_script_path"] = pipeline_result.get("highlight_script_path")
    if pipeline_result.get("highlights_path"):
        st.session_state["subtitle_first_highlights_path"] = pipeline_result.get("highlights_path")
    if pipeline_result.get("audit_path"):
        st.session_state["subtitle_first_audit_path"] = pipeline_result.get("audit_path")
    st.session_state["movie_story_plot_chunks"] = pipeline_result.get("plot_chunks", [])
    st.session_state["movie_story_frame_records"] = pipeline_result.get("frame_records", [])
    st.session_state["movie_story_highlight_frame_records"] = pipeline_result.get("highlight_frame_records", [])
    st.session_state["subtitle_first_highlight_narration_segments"] = pipeline_result.get("highlight_narration_segments", [])
    if pipeline_result.get("highlight_narration_segments_path"):
        st.session_state["subtitle_first_highlight_narration_segments_path"] = pipeline_result.get(
            "highlight_narration_segments_path"
        )

    final_path = (
        pipeline_result.get("generated_saved_subtitle_path")
        or pipeline_result.get("clean_subtitle_path")
        or pipeline_result.get("subtitle_path", "")
    )
    if final_path and os.path.exists(final_path):
        st.session_state["subtitle_path"] = final_path
        st.session_state["last_generated_subtitle_path"] = final_path
        try:
            subtitle_obj = read_subtitle_text(final_path)
            st.session_state["subtitle_content"] = subtitle_obj.text if subtitle_obj else ""
        except Exception:
            logger.warning("failed to read generated subtitle text")

    if pipeline_result.get("raw_subtitle_path"):
        st.session_state["subtitle_raw_path"] = pipeline_result["raw_subtitle_path"]
    if pipeline_result.get("clean_subtitle_path"):
        st.session_state["subtitle_clean_path"] = pipeline_result["clean_subtitle_path"]
    if pipeline_result.get("subtitle_segments_path"):
        st.session_state["subtitle_segments_json_path"] = pipeline_result["subtitle_segments_path"]

    st.session_state[PENDING_SUBTITLE_SOURCE_MODE_KEY] = "existing_subtitle"
