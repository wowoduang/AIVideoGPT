import json
import time
import traceback

import streamlit as st
from loguru import logger

from app.config import config
from app.services.plot_first_pipeline import run_plot_first_pipeline
from app.services.subtitle_pipeline import build_subtitle_segments, resolve_explicit_subtitle_path
from app.services.upload_validation import InputValidationError, ensure_existing_file
from app.utils import utils


VALID_VIDEO_EXTS = (".mp4", ".mov", ".avi", ".flv", ".mkv")
VALID_SUBTITLE_EXTS = (".srt", ".ass", ".ssa", ".vtt")


def _prepare_subtitle_input(params):
    """Resolve optional subtitle input for short-drama mode.

    Policy:
    1. 有字幕文件就优先使用
    2. 没有字幕文件就允许后端自动生成
    3. 用户提供了无效路径时，不直接终止，回退到自动生成
    """
    explicit_subtitle_path = resolve_explicit_subtitle_path(params, st.session_state)
    explicit_subtitle_path = str(explicit_subtitle_path or "").strip()
    if not explicit_subtitle_path:
        return "", "auto"

    try:
        valid_path = ensure_existing_file(
            explicit_subtitle_path,
            label="字幕",
            allowed_exts=VALID_SUBTITLE_EXTS,
        )
        return valid_path, "provided"
    except InputValidationError as e:
        logger.warning(f"[短剧模式] 字幕文件不可用，将回退为自动生成字幕: {e}")
        st.warning(f"字幕文件不可用，将改为自动生成字幕：{e}")
        return "", "fallback_auto"


def generate_script_short(tr, params, custom_clips=5):
    """生成短剧解说脚本（剧情优先完整链路版）

    当前目标：一次跑通并落盘一整条可测链路
    1. 有字幕就用字幕文件；没有就自动生成字幕
    2. 标准化字幕 -> 剧情块
    3. 按剧情块回抽代表帧
    4. 融合证据并生成解说文案
    5. 落盘分析 JSON + 脚本 JSON，方便你直接测试
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(progress: int, message: str = ""):
        progress_bar.progress(progress)
        status_text.text(f"{progress}% - {message}" if message else f"进度: {progress}%")

    try:
        with st.spinner("正在生成脚本..."):
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

            explicit_subtitle_path, subtitle_input_mode = _prepare_subtitle_input(params)
            if subtitle_input_mode == "provided":
                logger.info(f"[短剧模式] 使用显式字幕文件: {explicit_subtitle_path}")
            elif subtitle_input_mode == "fallback_auto":
                logger.info("[短剧模式] 字幕无效，改为自动生成字幕")
            else:
                logger.info("[短剧模式] 未提供字幕文件，将自动生成字幕")

            text_provider = config.app.get("text_llm_provider", "gemini").lower()
            text_api_key = config.app.get(f"text_{text_provider}_api_key")
            text_model = config.app.get(f"text_{text_provider}_model_name")
            text_base_url = config.app.get(f"text_{text_provider}_base_url")

            pipeline_result = run_plot_first_pipeline(
                video_path=video_path,
                subtitle_path=explicit_subtitle_path,
                text_api_key=text_api_key,
                text_base_url=text_base_url,
                text_model=text_model,
                style="short_drama",
                visual_mode="boost",
                progress_callback=update_progress,
            )
            if not pipeline_result.get("success"):
                st.error(f"剧情优先链路执行失败: {pipeline_result.get('error', 'unknown_error')}")
                st.stop()

            subtitle_result = pipeline_result.get("subtitle_result") or {}
            subtitle_segments = subtitle_result.get("segments") or []
            actual_subtitle_path = subtitle_result.get("subtitle_path", "")
            subtitle_source = subtitle_result.get("source", "none")
            source_text = pipeline_result.get("subtitle_source_text", subtitle_source or "未知来源")

            plot_chunks = pipeline_result.get("plot_chunks") or []
            frame_records = pipeline_result.get("frame_records") or []
            script_items = pipeline_result.get("script_items") or []
            analysis_path = pipeline_result.get("analysis_path", "")
            script_path = pipeline_result.get("script_path", "")
            warnings = pipeline_result.get("warnings") or []

            st.session_state["subtitle_path"] = actual_subtitle_path
            st.session_state["short_drama_subtitle_path"] = actual_subtitle_path
            st.session_state["short_drama_subtitle_source"] = subtitle_source
            st.session_state["short_drama_subtitle_segments"] = subtitle_segments
            st.session_state["short_drama_plot_chunks"] = plot_chunks
            st.session_state["short_drama_frame_records"] = frame_records
            st.session_state["short_drama_analysis_path"] = analysis_path
            st.session_state["video_clip_json"] = script_items
            st.session_state["video_clip_json_path"] = script_path

            logger.info(
                "[短剧模式] 完整链路完成: subtitles={}, plot_chunks={}, frames={}, scripts={}, script_path={}",
                len(subtitle_segments),
                len(plot_chunks),
                len(frame_records),
                len(script_items),
                script_path,
            )
            logger.info(f"[短剧模式] 脚本内容: {json.dumps(script_items, ensure_ascii=False, indent=2)}")

            st.success(f"✅ 字幕准备完成，共 {len(subtitle_segments)} 段（{source_text}）")
            st.info(
                f"已生成 {len(plot_chunks)} 个剧情块、{len(frame_records)} 张代表帧、{len(script_items)} 段解说。"
            )
            if analysis_path:
                st.caption(f"分析结果: {analysis_path}")
            if script_path:
                st.caption(f"脚本文件: {script_path}")
            if warnings:
                for warning in warnings:
                    st.warning(warning)

        time.sleep(0.1)
        progress_bar.progress(100)
        status_text.text("剧情优先链路完成！")
        st.success("✅ 短剧脚本生成成功！")

    except Exception as err:
        progress_bar.progress(100)
        st.error(f"生成过程中发生错误: {str(err)}")
        logger.exception(f"[短剧模式] 生成脚本时发生错误\n{traceback.format_exc()}")


# ============ Legacy 模式切换（可选）============
def generate_script_short_legacy(tr, params, custom_clips=5):
    """
    生成短视频脚本 - Legacy 模式（使用原有 SDP 管道）

    保留此函数以便在需要时切换回原有实现。
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(progress: float, message: str = ""):
        progress_bar.progress(progress)
        if message:
            status_text.text(f"{progress}% - {message}")
        else:
            status_text.text(f"进度: {progress}%")

    try:
        with st.spinner("正在生成脚本..."):
            # ========== 严格验证：必须上传视频和字幕（与短剧解说保持一致）==========
            # 1. 验证视频文件
            video_path = getattr(params, "video_origin_path", None)
            if not video_path or not str(video_path).strip():
                st.error("请先选择视频文件")
                st.stop()

            try:
                ensure_existing_file(
                    str(video_path),
                    label="视频",
                    allowed_exts=VALID_VIDEO_EXTS,
                )
            except InputValidationError as e:
                st.error(str(e))
                st.stop()

            # 2. 字幕输入：优先使用现成字幕，否则自动生成字幕文件
            subtitle_path, subtitle_input_mode = _prepare_subtitle_input(params)
            if subtitle_input_mode == "provided":
                logger.info(f"使用用户提供的字幕文件: {subtitle_path}")
            else:
                logger.info("未提供可用字幕文件，将自动生成字幕")
                subtitle_result = build_subtitle_segments(
                    video_path=str(video_path),
                    explicit_subtitle_path="",
                )
                subtitle_path = subtitle_result.get("subtitle_path", "")
                if not subtitle_result.get("segments") or not subtitle_path:
                    st.error(f"自动生成字幕失败: {subtitle_result.get('error', 'unknown_error')}")
                    st.stop()
                st.session_state["subtitle_path"] = subtitle_path
                st.session_state["short_drama_subtitle_source"] = subtitle_result.get("source", "generated_srt")
                logger.info(f"自动生成字幕成功: {subtitle_path}")

            # ========== 获取 LLM 配置 ==========
            text_provider = config.app.get('text_llm_provider', 'gemini').lower()
            text_api_key = config.app.get(f'text_{text_provider}_api_key')
            text_model = config.app.get(f'text_{text_provider}_model_name')
            text_base_url = config.app.get(f'text_{text_provider}_base_url')

            update_progress(20, "开始准备生成脚本")

            # ========== 调用后端生成脚本 ==========
            from app.services.SDP.generate_script_short import generate_script_result

            output_path = utils.script_dir() + "/merged_subtitle.json"

            subtitle_content = st.session_state.get("subtitle_content")
            subtitle_kwargs = (
                {"subtitle_content": str(subtitle_content)}
                if subtitle_content is not None and str(subtitle_content).strip()
                else {"subtitle_file_path": subtitle_path}
            )

            result = generate_script_result(
                api_key=text_api_key,
                model_name=text_model,
                output_path=output_path,
                base_url=text_base_url,
                custom_clips=custom_clips,
                provider=text_provider,
                **subtitle_kwargs,
            )

            if result.get("status") != "success":
                st.error(result.get("message", "生成脚本失败，请检查日志"))
                st.stop()

            script = result.get("script")
            logger.info(f"脚本生成完成 {json.dumps(script, ensure_ascii=False, indent=4)}")

            if isinstance(script, list):
                st.session_state['video_clip_json'] = script
            elif isinstance(script, str):
                st.session_state['video_clip_json'] = json.loads(script)

            update_progress(80, "脚本生成完成")

        time.sleep(0.1)
        progress_bar.progress(100)
        status_text.text("脚本生成完成！")
        st.success("视频脚本生成成功！")

    except Exception as err:
        progress_bar.progress(100)
        st.error(f"生成过程中发生错误: {str(err)}")
        logger.exception(f"生成脚本时发生错误\n{traceback.format_exc()}")
