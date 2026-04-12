from __future__ import annotations

import os
from typing import Callable, Optional

import streamlit as st

from app.models.schema import VideoClipParams
from webui.services.script_persistence import load_script
from webui.tools.generate_highlight_edit_api import generate_highlight_edit
from webui.tools.generate_short_summary_api import generate_script_short_sunmmary


MODE_FILE = "file_selection"
MODE_SHORT = "short"
MODE_SHORT_SUMMARY = "short_summary"
MODE_SUBTITLE_FIRST = "summary"
MODE_HIGHLIGHT_EDIT = "highlight_edit"


def get_script_action_label(tr, script_mode: str) -> str:
    if script_mode == MODE_SHORT:
        return tr("Generate Short Video Script")
    if script_mode == MODE_SHORT_SUMMARY:
        return tr("Generate Short Drama Summary Script")
    if script_mode == MODE_SUBTITLE_FIRST:
        if st.session_state.get("subtitle_source_mode") == "auto_subtitle":
            return tr("Auto Generate Subtitle and Script")
        return tr("Generate Subtitle-First Script")
    if script_mode == MODE_HIGHLIGHT_EDIT:
        return tr("Generate Highlight Edit Script")
    if isinstance(script_mode, str) and script_mode.endswith("json"):
        return tr("Load Video Script")
    return tr("Please Select Script File")


def build_script_action_params(script_mode: str) -> VideoClipParams:
    params = VideoClipParams()
    params.video_clip_json_path = script_mode
    params.video_origin_path = st.session_state.get("video_origin_path", "")
    return params


def run_script_action(
    tr,
    script_mode: str,
    *,
    lazy_import_short_mix_generator: Callable[[Callable[[str], str]], Optional[Callable]],
) -> None:
    params = build_script_action_params(script_mode)

    if script_mode == MODE_SHORT:
        subtitle_mode = st.session_state.get("short_subtitle_source_mode", "existing_subtitle")
        subtitle_path = st.session_state.get("short_subtitle_path", "")
        st.session_state["subtitle_path"] = subtitle_path
        st.session_state["subtitle_content"] = st.session_state.get("short_subtitle_content")
        if subtitle_mode != "auto_subtitle" and (not subtitle_path or not os.path.exists(subtitle_path)):
            st.error(tr("Short mix requires subtitle input or auto subtitle"))
            return

        generate_script_short = lazy_import_short_mix_generator(tr)
        if generate_script_short is None:
            return

        generate_script_short(
            tr,
            params,
            custom_clips=int(st.session_state.get("short_custom_clips", 5)),
        )
        return

    if script_mode == MODE_SHORT_SUMMARY:
        subtitle_path = st.session_state.get("short_summary_subtitle_path", "")
        if not subtitle_path or not os.path.exists(subtitle_path):
            st.error(tr("Short drama summary requires subtitle file"))
            return
        st.session_state["subtitle_path"] = subtitle_path
        st.session_state["subtitle_content"] = st.session_state.get("short_summary_subtitle_content")
        generate_script_short_sunmmary(
            params,
            subtitle_path,
            st.session_state.get("short_summary_name", ""),
            float(st.session_state.get("short_summary_temperature", 0.7)),
        )
        return

    if script_mode == MODE_SUBTITLE_FIRST:
        subtitle_mode = st.session_state.get("subtitle_source_mode", "existing_subtitle")
        subtitle_path = st.session_state.get("subtitle_path", "")
        if subtitle_mode != "auto_subtitle" and (not subtitle_path or not os.path.exists(subtitle_path)):
            st.error(tr("Subtitle file does not exist"))
            return

        video_theme = st.session_state.get("short_name") or st.session_state.get("video_theme", "")
        temperature = st.session_state.get("temperature", 0.7)
        generate_script_short_sunmmary(params, subtitle_path, video_theme, temperature)
        return

    if script_mode == MODE_HIGHLIGHT_EDIT:
        subtitle_mode = st.session_state.get("highlight_subtitle_source_mode", "existing_subtitle")
        subtitle_path = st.session_state.get("highlight_subtitle_path", "")
        if subtitle_mode != "auto_subtitle" and subtitle_path and not os.path.exists(subtitle_path):
            st.error(tr("Subtitle file does not exist"))
            return
        st.session_state["subtitle_path"] = subtitle_path
        st.session_state["subtitle_content"] = st.session_state.get("highlight_subtitle_content")
        generate_highlight_edit(tr, params)
        return

    load_script(tr, script_mode)
