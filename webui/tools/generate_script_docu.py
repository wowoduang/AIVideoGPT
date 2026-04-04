import asyncio
import json
import os
import time
import traceback
from datetime import datetime

import streamlit as st
from loguru import logger

from app.config import config
from app.services.cost_guard import cap_frame_records
from app.services.evidence_fuser import fuse_scene_evidence, parse_visual_analysis_results
from app.services.frame_selector import select_representative_frames
from app.services.generate_narration_script import generate_narration_from_scene_evidence
from app.services.scene_builder import build_fallback_scenes_from_keyframes, build_scenes_from_subtitles
from app.services.script_fallback import ensure_script_shape
from app.services.subtitle_pipeline import build_subtitle_segments, resolve_explicit_subtitle_path
from app.utils import utils, video_processor
from webui.tools.base import create_vision_analyzer


def generate_script_docu(params):
    """字幕优先的视频脚本生成：字幕/ASR 做主理解，视觉补充可选。"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    def update_progress(progress: float, message: str = ""):
        progress_bar.progress(progress)
        status_text.text(f"🎬 {message}" if message else f"📊 进度: {progress}%")

    try:
        with st.spinner("正在生成脚本..."):
            if not params.video_origin_path:
                st.error("请先选择视频文件")
                return

            update_progress(10, "正在准备字幕/转写...")
            subtitle_result = build_subtitle_segments(
                video_path=params.video_origin_path,
                explicit_subtitle_path=resolve_explicit_subtitle_path(params, st.session_state),
            )
            subtitle_segments = subtitle_result.get("segments", [])
            subtitle_success = bool(subtitle_segments)
            enable_visual_supplement = bool(
                st.session_state.get("enable_visual_supplement", config.app.get("enable_visual_supplement", False))
            )

            if subtitle_success:
                st.success(f"✅ 已获得字幕，共 {len(subtitle_segments)} 段，进入字幕优先模式")
                if enable_visual_supplement:
                    st.info("🖼️ 已启用视觉补充：将在字幕主理解基础上分析少量代表帧")
                else:
                    st.info("💰 已关闭视觉补充：将只基于字幕生成脚本（更省 token）")
            else:
                error = subtitle_result.get("error") or "auto_subtitle_failed"
                st.warning(f"⚠️ 未获得字幕（{error}），将退回视觉主导模式（成本更高，准确性较低）")

            update_progress(30, "正在构建场景段...")
            if subtitle_success:
                scenes = build_scenes_from_subtitles(subtitle_segments)
            else:
                update_progress(20, "正在准备关键帧...")
                keyframe_files = _prepare_keyframes(params.video_origin_path)
                if not keyframe_files:
                    raise Exception("未提取到任何关键帧文件")
                fallback_interval = st.session_state.get("frame_interval_input") or config.frames.get("skip_seconds", 3)
                scenes = build_fallback_scenes_from_keyframes(keyframe_files[:8], fallback_interval=fallback_interval)

            frame_records = []
            visual_observations = {}
            results = []
            budget_meta = {"estimated_tokens": 0, "estimated_cost_cny": 0.0, "capped": 0, "original": 0}

            if (not subtitle_success) or enable_visual_supplement:
                update_progress(45, "正在准备代表帧...")
                keyframe_files = _prepare_keyframes(params.video_origin_path)
                if not keyframe_files:
                    raise Exception("未提取到任何关键帧文件")

                frames_per_scene = 1 if subtitle_success else int(st.session_state.get("frames_per_scene") or 2)
                frame_records = select_representative_frames(scenes, keyframe_files, frames_per_scene=frames_per_scene)
                max_total_frames = 12 if subtitle_success else int(st.session_state.get('max_total_frames') or 24)
                frame_records, budget_meta = cap_frame_records(frame_records, max_total_frames=max_total_frames)
                selected_frame_paths = [record["frame_path"] for record in frame_records]
                if selected_frame_paths:
                    update_progress(60, f"正在分析代表帧，共 {len(selected_frame_paths)} 张（预计输入token≈{budget_meta.get('estimated_tokens',0)}）...")
                    results = _analyze_selected_frames(selected_frame_paths)
                    visual_observations = parse_visual_analysis_results(results, frame_records)
            else:
                st.caption("当前未启用视觉补充：跳过代表帧分析")

            update_progress(75, "正在融合字幕与画面证据...")
            scene_evidence = fuse_scene_evidence(scenes, frame_records, visual_observations)
            for scene in scene_evidence:
                scene['visual_budget_meta'] = budget_meta
                scene['evidence_mode'] = 'subtitle+visual' if (subtitle_success and enable_visual_supplement) else ('subtitle_only' if subtitle_success else 'visual_only')
            analysis_json_path = _save_analysis(scene_evidence, results)
            logger.info(f"分析结果已保存到: {analysis_json_path}")

            update_progress(88, "正在生成解说文案...")
            text_provider = config.app.get('text_llm_provider', 'gemini').lower()
            text_api_key = config.app.get(f'text_{text_provider}_api_key')
            text_model = config.app.get(f'text_{text_provider}_model_name')
            text_base_url = config.app.get(f'text_{text_provider}_base_url')
            narration_items = generate_narration_from_scene_evidence(
                scene_evidence=scene_evidence,
                api_key=text_api_key,
                base_url=text_base_url,
                model=text_model,
            )
            narration_items = ensure_script_shape(narration_items)

            if not narration_items:
                raise Exception("未生成有效脚本片段")

            st.session_state['video_clip_json'] = narration_items
            update_progress(100, "脚本生成完成")
            time.sleep(0.1)
            progress_bar.progress(100)
            status_text.text("🎉 脚本生成完成！")
            st.success("✅ 视频脚本生成成功！")
    except Exception as err:
        st.error(f"❌ 生成过程中发生错误: {str(err)}")
        logger.exception(f"生成脚本时发生错误\n{traceback.format_exc()}")
    finally:
        time.sleep(2)
        progress_bar.empty()
        status_text.empty()


def _prepare_keyframes(video_origin_path: str):
    keyframes_dir = os.path.join(utils.temp_dir(), "keyframes")
    video_hash = utils.md5(video_origin_path + str(os.path.getmtime(video_origin_path)))
    video_keyframes_dir = os.path.join(keyframes_dir, video_hash)
    keyframe_files = []
    if os.path.exists(video_keyframes_dir):
        keyframe_files = [os.path.join(video_keyframes_dir, f) for f in sorted(os.listdir(video_keyframes_dir)) if f.endswith('.jpg')]
        if keyframe_files:
            logger.info(f"使用已缓存的关键帧: {video_keyframes_dir}")
            return keyframe_files

    os.makedirs(video_keyframes_dir, exist_ok=True)
    processor = video_processor.VideoProcessor(video_origin_path)
    processor.extract_frames_by_interval_ultra_compatible(
        output_dir=video_keyframes_dir,
        interval_seconds=st.session_state.get('frame_interval_input') or config.frames.get('skip_seconds', 3),
    )
    keyframe_files = [os.path.join(video_keyframes_dir, f) for f in sorted(os.listdir(video_keyframes_dir)) if f.endswith('.jpg')]
    logger.info(f"关键帧提取完成，共 {len(keyframe_files)} 帧")
    return keyframe_files


def _analyze_selected_frames(selected_frame_paths):
    vision_llm_provider = (st.session_state.get('vision_llm_provider') or config.app.get('vision_llm_provider', 'litellm')).lower()
    vision_api_key = st.session_state.get(f'vision_{vision_llm_provider}_api_key') or config.app.get(f'vision_{vision_llm_provider}_api_key')
    vision_model = st.session_state.get(f'vision_{vision_llm_provider}_model_name') or config.app.get(f'vision_{vision_llm_provider}_model_name')
    vision_base_url = st.session_state.get(f'vision_{vision_llm_provider}_base_url') or config.app.get(f'vision_{vision_llm_provider}_base_url', '')

    analyzer = create_vision_analyzer(
        provider=vision_llm_provider,
        api_key=vision_api_key,
        model=vision_model,
        base_url=vision_base_url,
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        prompt = (
            '你将收到一组按时间顺序排列的代表帧。请逐帧观察，并输出 JSON：'
            '{"frame_observations":[{"frame_number":1,"observation":"..."}],'
            '"overall_activity_summary":"..."}。'
            '请只返回JSON。'
        )
        vision_batch_size = int(st.session_state.get('vision_batch_size') or config.frames.get('vision_batch_size', 3))
        return loop.run_until_complete(
            analyzer.analyze_images(images=selected_frame_paths, prompt=prompt, batch_size=max(1, vision_batch_size))
        )
    finally:
        loop.close()


def _save_analysis(scene_evidence, raw_results):
    analysis_dir = os.path.join(utils.storage_dir(), "temp", "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(analysis_dir, f"scene_evidence_{now}.json")
    payload = {"scene_evidence": scene_evidence, "raw_results": raw_results}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
