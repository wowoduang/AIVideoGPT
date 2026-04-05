#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import annotations

import json
import os
import re
import time
import traceback

import streamlit as st
from loguru import logger

from app.config import config
from app.services.subtitle_first_pipeline import run_subtitle_first_pipeline
from app.services.subtitle_pipeline import build_subtitle_segments
from app.services.subtitle_review_clean import apply_review_overrides, prepare_subtitle_review
from app.services.subtitle_text import read_subtitle_text

import app.services.llm  # noqa: F401


REVIEW_REQUEST_KEY = "subtitle_review_request"
REVIEW_STATE_KEY = "subtitle_review_state"
PENDING_SUBTITLE_SOURCE_MODE_KEY = "_pending_subtitle_source_mode"


def parse_and_fix_json(json_string):
    if not json_string or not json_string.strip():
        return None

    json_string = json_string.strip()

    try:
        return json.loads(json_string)
    except Exception:
        pass

    try:
        fixed_braces = json_string.replace("{{", "{").replace("}}", "}")
        return json.loads(fixed_braces)
    except Exception:
        pass

    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", json_string, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1).strip())
    except Exception:
        pass

    return None


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
        "asr_backend": _resolve_asr_backend(),
        "cache_mode": _resolve_cache_mode(),
        "review_mode": _resolve_review_mode(),
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
            logger.warning("读取生成后的字幕文本失败")

    if pipeline_result.get("raw_subtitle_path"):
        st.session_state["subtitle_raw_path"] = pipeline_result["raw_subtitle_path"]
    if pipeline_result.get("clean_subtitle_path"):
        st.session_state["subtitle_clean_path"] = pipeline_result["clean_subtitle_path"]
    if pipeline_result.get("subtitle_segments_path"):
        st.session_state["subtitle_segments_json_path"] = pipeline_result["subtitle_segments_path"]

    # Delay subtitle source mode updates until the next rerun, before widgets
    # with the same keys are instantiated again.
    st.session_state[PENDING_SUBTITLE_SOURCE_MODE_KEY] = "existing_subtitle"


def _run_pipeline_from_request(request: dict, subtitle_path: str, progress_callback):
    regenerate_subtitle = request.get("cache_mode") == "clear_and_regenerate"
    return run_subtitle_first_pipeline(
        video_path=request["video_path"],
        subtitle_path=subtitle_path,
        text_api_key=request["text_api_key"],
        text_base_url=request["text_base_url"],
        text_model=request["text_model"],
        style=request["narration_style"],
        generation_mode=request["generation_mode"],
        visual_mode=request["visual_mode"],
        scene_overrides={
            "target_duration_minutes": request["target_duration_minutes"],
            "narrative_strategy": request["narrative_strategy"],
            "accuracy_priority": request["accuracy_priority"],
            "highlight_only": request["highlight_only"],
            "video_title": request["video_theme"],
            "short_name": request["video_theme"],
            "temperature": request["temperature"],
        },
        progress_callback=progress_callback,
        asr_backend=request.get("asr_backend", ""),
        regenerate_subtitle=regenerate_subtitle,
    )


@st.dialog("字幕可疑片段审核", width="large")
def _subtitle_review_dialog():
    review_state = st.session_state.get(REVIEW_STATE_KEY)
    request = st.session_state.get(REVIEW_REQUEST_KEY)

    if not review_state or not request:
        st.warning("没有待审核的字幕。")
        return

    candidates = review_state.get("candidates") or []
    if not candidates:
        st.info("当前没有可疑字幕。")
        return

    st.caption("系统已先跑一遍自动字幕，并标出可疑点。请一次性修订后提交，系统会继续生成最终字幕并进入影视解说主链。")

    with st.form("subtitle_review_form"):
        for idx, cand in enumerate(candidates, start=1):
            st.markdown(f"#### 可疑点 {idx}")
            cols = st.columns([1, 2])
            with cols[0]:
                if cand.get("frame_path") and os.path.exists(cand["frame_path"]):
                    st.image(cand["frame_path"], caption=cand["time_range"], use_container_width=True)
                else:
                    st.caption(cand["time_range"])
            with cols[1]:
                st.caption(cand["reason_label"])
                st.text_area(
                    f"原始片段_{cand['candidate_id']}",
                    value=cand["context_text"],
                    height=90,
                    disabled=True,
                    key=f"review_raw_{cand['candidate_id']}",
                )
                st.text_area(
                    f"修订为_{cand['candidate_id']}",
                    value=cand["suggested_text"],
                    height=100,
                    key=f"review_edit_{cand['candidate_id']}",
                )

        submit = st.form_submit_button("确认提交并继续生成", use_container_width=True)

    cols = st.columns(2)
    skip_review = cols[0].button("跳过人工审核，直接继续", use_container_width=True)
    cancel_review = cols[1].button("取消本次审核", use_container_width=True)

    if cancel_review:
        st.session_state.pop(REVIEW_STATE_KEY, None)
        st.session_state.pop(REVIEW_REQUEST_KEY, None)
        st.rerun()

    if submit:
        overrides = {}
        for cand in candidates:
            edited = str(st.session_state.get(f"review_edit_{cand['candidate_id']}", "") or "").strip()
            overrides[cand["candidate_id"]] = edited or cand["suggested_text"]

        final_result = apply_review_overrides(
            review_state["subtitle_result"],
            candidates,
            overrides,
        )
        review_state["final_result"] = final_result

        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(progress: float, message: str = ""):
            progress_bar.progress(min(int(progress), 100))
            status_text.text(f"{progress}% - {message}" if message else f"进度: {progress}%")

        with st.spinner("正在用最终字幕继续生成影视解说脚本..."):
            pipeline_result = _run_pipeline_from_request(
                request,
                final_result["final_subtitle_path"],
                update_progress,
            )

        if not pipeline_result.get("success"):
            st.error(f"影视解说主链失败: {pipeline_result.get('error', 'unknown error')}")
            return

        _save_pipeline_success(pipeline_result)
        st.session_state["subtitle_final_path"] = final_result["final_subtitle_path"]
        st.session_state["subtitle_final_segments_path"] = final_result["final_segments_path"]
        st.session_state["subtitle_review_overrides_path"] = final_result["overrides_path"]
        st.session_state.pop(REVIEW_STATE_KEY, None)
        st.session_state.pop(REVIEW_REQUEST_KEY, None)
        st.rerun()

    if skip_review:
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(progress: float, message: str = ""):
            progress_bar.progress(min(int(progress), 100))
            status_text.text(f"{progress}% - {message}" if message else f"进度: {progress}%")

        with st.spinner("跳过审核，继续生成影视解说脚本..."):
            pipeline_result = _run_pipeline_from_request(
                request,
                review_state.get("prepared_subtitle_path") or request.get("subtitle_path") or "",
                update_progress,
            )

        if not pipeline_result.get("success"):
            st.error(f"影视解说主链失败: {pipeline_result.get('error', 'unknown error')}")
            return

        _save_pipeline_success(pipeline_result)
        st.session_state.pop(REVIEW_STATE_KEY, None)
        st.session_state.pop(REVIEW_REQUEST_KEY, None)
        st.rerun()


def generate_script_short_sunmmary(params, subtitle_path, video_theme, temperature):
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(progress: float, message: str = ""):
        progress_bar.progress(min(int(progress), 100))
        status_text.text(f"{progress}% - {message}" if message else f"进度: {progress}%")

    try:
        with st.spinner("正在生成脚本..."):
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
            st.session_state[REVIEW_REQUEST_KEY] = request

            logger.info(
                "DEBUG subtitle_source_mode={}, subtitle_asr_backend={}, subtitle_cache_mode={}, subtitle_review_mode={}",
                subtitle_mode,
                request["asr_backend"],
                request["cache_mode"],
                request["review_mode"],
            )

            if allow_auto_subtitle:
                update_progress(8, "生成并整理字幕...")
                subtitle_result = build_subtitle_segments(
                    video_path=params.video_origin_path,
                    explicit_subtitle_path=actual_subtitle_path,
                    regenerate=request["cache_mode"] == "clear_and_regenerate",
                    backend_override=request["asr_backend"],
                )
                if not subtitle_result.get("success"):
                    st.error(f"字幕生成失败: {subtitle_result.get('error', 'unknown')}")
                    return

                review_mode = request["review_mode"]
                if review_mode == "review_suspicious":
                    review_state = prepare_subtitle_review(
                        video_path=params.video_origin_path,
                        subtitle_result=subtitle_result,
                        max_candidates=20,
                    )
                    logger.info(
                        "字幕审核预处理完成: source={}, backend={}, subtitle_path={}, candidates={}",
                        subtitle_result.get("source"),
                        subtitle_result.get("backend"),
                        subtitle_result.get("subtitle_path", ""),
                        len(review_state.get("candidates") or []),
                    )
                    if review_state.get("candidates"):
                        st.session_state[REVIEW_STATE_KEY] = review_state
                        st.info(f"已发现 {len(review_state['candidates'])} 处可疑字幕，请在弹窗中一次修订后继续。")
                        _subtitle_review_dialog()
                        return

                prepared_path = subtitle_result.get("clean_subtitle_path") or subtitle_result.get("subtitle_path") or ""
                pipeline_result = _run_pipeline_from_request(request, prepared_path, update_progress)
            else:
                pipeline_result = _run_pipeline_from_request(request, actual_subtitle_path, update_progress)

            if not pipeline_result.get("success"):
                st.error(f"影视解说主链失败: {pipeline_result.get('error', 'unknown error')}")
                return

            _save_pipeline_success(pipeline_result)
            update_progress(100, "脚本生成完成！")
            st.success(
                f"影视解说脚本生成成功！剧情块 {len(pipeline_result.get('plot_chunks', []))} 个，"
                f"脚本片段 {len(pipeline_result.get('script_items', []))} 个。"
            )

            with st.expander("字幕产物", expanded=False):
                st.write("主链字幕:", pipeline_result.get("subtitle_path", "") or "NONE")
                st.write("清洗字幕:", pipeline_result.get("clean_subtitle_path", "") or "NONE")
                st.write("原始字幕:", pipeline_result.get("raw_subtitle_path", "") or "NONE")
                st.write("结构化字幕:", pipeline_result.get("subtitle_segments_path", "") or "NONE")
                st.write("最终字幕:", st.session_state.get("subtitle_final_path", "") or "NONE")
                st.write("最终结构化字幕:", st.session_state.get("subtitle_final_segments_path", "") or "NONE")

    except Exception as err:
        st.error(f"生成过程中发生错误: {str(err)}")
        logger.exception(f"影视解说主链异常\n{traceback.format_exc()}")
    finally:
        time.sleep(0.8)
