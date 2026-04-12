from __future__ import annotations

import os
import traceback
from typing import Any, Dict

import streamlit as st
from loguru import logger

from webui.services.job_execution import extract_job_result, poll_job_until_complete
from webui.services.movie_story_script_support import (
    _build_request,
    _normalize_subtitle_mode,
    _normalize_subtitle_path,
    _resolve_review_mode,
    _save_pipeline_success,
)
from webui.tools.generate_short_summary import generate_script_short_sunmmary as legacy_generate_script_short_sunmmary
from webui.utils import job_runner


def _identity_tr(text: str) -> str:
    return text


def _render_pipeline_success(pipeline_result: Dict[str, Any]) -> None:
    _save_pipeline_success(pipeline_result)
    st.success(
        f"影视解说脚本生成成功，剧情块 {len(pipeline_result.get('plot_chunks', []))} 个，"
        f"脚本片段 {len(pipeline_result.get('script_items', []))} 个"
    )

    with st.expander("字幕产物", expanded=False):
        st.write("主链字幕:", pipeline_result.get("subtitle_path", "") or "NONE")
        st.write("清洗字幕:", pipeline_result.get("clean_subtitle_path", "") or "NONE")
        st.write("原始字幕:", pipeline_result.get("raw_subtitle_path", "") or "NONE")
        st.write("结构化字幕:", pipeline_result.get("subtitle_segments_path", "") or "NONE")
        st.write("最终字幕:", st.session_state.get("subtitle_final_path", "") or "NONE")
        st.write("最终结构化字幕:", st.session_state.get("subtitle_final_segments_path", "") or "NONE")


def generate_script_short_sunmmary(params, subtitle_path, video_theme, temperature) -> None:
    try:
        if not params.video_origin_path:
            st.error("请先选择视频文件")
            return

        subtitle_mode = _normalize_subtitle_mode()
        original_subtitle_path = str(subtitle_path or "").strip()
        actual_subtitle_path = _normalize_subtitle_path(original_subtitle_path, subtitle_mode)
        allow_auto_subtitle = (subtitle_mode == "auto_subtitle") or (original_subtitle_path.upper() == "AUTO")

        if not allow_auto_subtitle and (not actual_subtitle_path or not os.path.exists(actual_subtitle_path)):
            st.error("字幕文件不存在")
            return

        request = _build_request(params, actual_subtitle_path, video_theme, temperature)
        review_mode = _resolve_review_mode()
        if allow_auto_subtitle and review_mode == "review_suspicious":
            legacy_generate_script_short_sunmmary(params, subtitle_path, video_theme, temperature)
            return

        with st.spinner("正在生成脚本..."):
            job = job_runner.start_movie_story_script_job(request)
        poll_job_until_complete(
            tr=_identity_tr,
            job=job,
            ui=st,
            fetch_status=job_runner.get_job_status,
            on_complete=_render_pipeline_success,
            extract_result=lambda task: extract_job_result(
                task,
                ("script_items", "plot_chunks", "global_summary"),
            ),
            completion_status_text="影视解说主链完成",
            completion_success_text="影视解说主链完成",
            empty_result_error="影视解说脚本任务已完成，但没有返回可用结果",
            failure_prefix="影视解说主链失败",
            query_failure_prefix="任务状态获取失败",
        )

    except Exception as err:
        st.error(f"生成过程中发生错误: {err}")
        logger.exception("[movie_story_script_api] failed to generate script\n{}", traceback.format_exc())
