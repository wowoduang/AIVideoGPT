from __future__ import annotations

import glob
import importlib
import json
import os
import time
import traceback

import streamlit as st
from loguru import logger

from app.config import config
from app.models.schema import VideoAspect, VideoClipParams
from app.services.subtitle_text import decode_subtitle_bytes
from app.services.timeline_allocator import fit_check
from app.utils import check_script, utils
from webui.components.subtitle_first_mode_panel import render_subtitle_first_mode_panel
from webui.tools.generate_short_summary import generate_script_short_sunmmary

MODE_FILE = "file_selection"
MODE_SHORT = "short"
MODE_SHORT_SUMMARY = "short_summary"
MODE_SUBTITLE_FIRST = "summary"

OST_OPTIONS = [0, 1, 2]
OST_LABELS = {
    0: "TTS配音",
    1: "保留原声",
    2: "TTS+原声混合",
}


def get_script_params() -> dict:
    return {
        "video_clip_json": st.session_state.get("video_clip_json", []),
        "video_clip_json_path": st.session_state.get("video_clip_json_path", ""),
        "video_origin_path": st.session_state.get("video_origin_path", ""),
        "video_aspect": st.session_state.get("video_aspect", VideoAspect.portrait.value),
        "video_language": st.session_state.get("video_language", "zh-CN"),
        "voice_name": st.session_state.get("voice_name", "zh-CN-YunjianNeural"),
        "voice_volume": float(st.session_state.get("voice_volume", 1.0)),
        "voice_rate": float(st.session_state.get("voice_rate", 1.0)),
        "voice_pitch": float(st.session_state.get("voice_pitch", 1.0)),
        "tts_engine": st.session_state.get("tts_engine", ""),
        "bgm_name": st.session_state.get("bgm_name", "random"),
        "bgm_type": st.session_state.get("bgm_type", "random"),
        "bgm_file": st.session_state.get("bgm_file", ""),
        "subtitle_enabled": bool(st.session_state.get("subtitle_enabled", True)),
        "font_name": st.session_state.get("font_name", "SimHei"),
        "font_size": int(st.session_state.get("font_size", 36)),
        "text_fore_color": st.session_state.get("text_fore_color", "white"),
        "text_back_color": st.session_state.get("text_back_color"),
        "stroke_color": st.session_state.get("stroke_color", "black"),
        "stroke_width": float(st.session_state.get("stroke_width", 1.5)),
        "subtitle_position": st.session_state.get("subtitle_position", "bottom"),
        "custom_position": float(st.session_state.get("custom_position", 70.0)),
        "n_threads": int(st.session_state.get("n_threads", 16)),
        "tts_volume": float(st.session_state.get("tts_volume", 1.0)),
        "original_volume": float(st.session_state.get("original_volume", 1.2)),
        "bgm_volume": float(st.session_state.get("bgm_volume", 0.3)),
    }


def _uploaded_file_fingerprint(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    size = getattr(uploaded_file, "size", None)
    return f"{uploaded_file.name}:{size}"


def _lazy_import_short_mix_generator(tr):
    """
    延时导入短剧混剪模块。
    页面渲染阶段不触发导入，只有真正点击按钮时才尝试加载。
    """
    try:
        module = importlib.import_module("webui.tools.generate_script_short")
        fn = getattr(module, "generate_script_short", None)
        if fn is None:
            st.error(tr("Short mix module is missing generate_script_short"))
            return None
        return fn
    except ModuleNotFoundError as e:
        missing_name = getattr(e, "name", "")
        logger.error(traceback.format_exc())
        if missing_name:
            st.error(f"{tr('Short mix module load failed')}: {missing_name}")
        else:
            st.error(f"{tr('Short mix module load failed')}: {e}")
        return None
    except Exception as e:
        logger.error(traceback.format_exc())
        st.error(f"{tr('Short mix module load failed')}: {e}")
        return None


def render_script_panel(tr):
    with st.container(border=True):
        st.write(tr("Video Script Configuration"))

        _normalize_legacy_mode()
        render_script_mode(tr)
        render_video_file(tr)

        mode = st.session_state.get("video_clip_json_path", MODE_FILE)
        if mode == MODE_SHORT:
            render_short_generate_options(tr)
        elif mode == MODE_SHORT_SUMMARY:
            render_short_drama_summary(tr)
        elif mode == MODE_SUBTITLE_FIRST:
            render_subtitle_first_generate_panel(tr)

        render_script_buttons(tr)


def _normalize_legacy_mode():
    current = st.session_state.get("video_clip_json_path", "")
    if not current:
        st.session_state["video_clip_json_path"] = MODE_FILE


def render_script_mode(tr):
    mode_options = {
        tr("Select/Upload Script"): MODE_FILE,
        tr("短剧混剪"): MODE_SHORT,
        tr("短剧解说"): MODE_SHORT_SUMMARY,
        tr("字幕优先生成"): MODE_SUBTITLE_FIRST,
    }
    reverse_options = {v: k for k, v in mode_options.items()}

    current_mode = st.session_state.get("video_clip_json_path", MODE_FILE)
    if current_mode not in reverse_options:
        current_mode = MODE_FILE

    selected_label = st.segmented_control(
        tr("Script Type"),
        options=list(mode_options.keys()),
        default=reverse_options[current_mode],
        key="script_mode_selection",
    )
    if not selected_label:
        selected_label = reverse_options[current_mode]

    selected_mode = mode_options[selected_label]
    st.session_state["video_clip_json_path"] = selected_mode

    if selected_mode == MODE_FILE:
        render_script_file_selector(tr)


def render_script_file_selector(tr):
    script_list = [(tr("None"), ""), (tr("Upload Script"), "upload_script")]
    script_dir = utils.script_dir()
    files = glob.glob(os.path.join(script_dir, "*.json"))
    file_list = [
        {"name": os.path.basename(file), "file": file, "ctime": os.path.getctime(file)}
        for file in files
    ]
    file_list.sort(key=lambda x: x["ctime"], reverse=True)

    for file in file_list:
        display_name = file["file"].replace(config.root_dir, "")
        script_list.append((display_name, file["file"]))

    saved_script_path = st.session_state.get("video_clip_json_path_selected", "")
    selected_index = 0
    for i, (_, path) in enumerate(script_list):
        if path == saved_script_path:
            selected_index = i
            break

    selected_script_index = st.selectbox(
        tr("Script Files"),
        index=selected_index,
        options=range(len(script_list)),
        format_func=lambda x: script_list[x][0],
        key="script_file_selection",
    )

    script_path = script_list[selected_script_index][1]

    if script_path and script_path != "upload_script":
        st.session_state["video_clip_json_path"] = script_path
        st.session_state["video_clip_json_path_selected"] = script_path

    if script_path == "upload_script":
        uploaded_file = st.file_uploader(
            tr("Upload Script File"),
            type=["json"],
            accept_multiple_files=False,
            key="upload_script_file",
        )
        if uploaded_file is not None:
            current_fp = _uploaded_file_fingerprint(uploaded_file)
            if current_fp != st.session_state.get("_last_uploaded_script_fp", ""):
                try:
                    script_content = uploaded_file.read().decode("utf-8")
                    json_data = json.loads(script_content)

                    safe_filename = os.path.basename(uploaded_file.name)
                    script_file_path = os.path.join(script_dir, safe_filename)
                    file_name, file_extension = os.path.splitext(safe_filename)
                    if os.path.exists(script_file_path):
                        timestamp = time.strftime("%Y%m%d%H%M%S")
                        script_file_path = os.path.join(
                            script_dir,
                            f"{file_name}_{timestamp}{file_extension}",
                        )

                    with open(script_file_path, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)

                    st.session_state["_last_uploaded_script_fp"] = current_fp
                    st.session_state["video_clip_json_path"] = script_file_path
                    st.session_state["video_clip_json_path_selected"] = script_file_path
                    st.success(tr("Script Uploaded Successfully"))
                except json.JSONDecodeError:
                    st.error(tr("Invalid JSON format"))
                except Exception as e:
                    st.error(f"{tr('Upload failed')}: {str(e)}")
                    logger.error(traceback.format_exc())


def render_video_file(tr):
    source_options = {
        tr("Select Existing Video"): "existing_video",
        tr("Upload New Video"): "upload_video",
    }

    current_source = st.session_state.get("video_source_mode", "existing_video")
    reverse_options = {v: k for k, v in source_options.items()}
    default_label = reverse_options.get(current_source, tr("Select Existing Video"))

    selected_source_label = st.segmented_control(
        tr("Video Source"),
        options=list(source_options.keys()),
        default=default_label,
        key="video_source_selection",
    )
    if not selected_source_label:
        selected_source_label = default_label

    source_mode = source_options[selected_source_label]
    st.session_state["video_source_mode"] = source_mode

    if st.session_state.get("video_origin_path"):
        st.caption(f"{tr('Current Video')}: {os.path.basename(st.session_state['video_origin_path'])}")
        if st.button(tr("Clear Current Video"), key="clear_current_video"):
            st.session_state["video_origin_path"] = ""

    if source_mode == "existing_video":
        video_list = [(tr("None"), "")]
        for suffix in ["*.mp4", "*.mov", "*.avi", "*.mkv", "*.flv"]:
            for file in glob.glob(os.path.join(utils.video_dir(), suffix)):
                display_name = file.replace(config.root_dir, "")
                video_list.append((display_name, file))

        saved_video_path = st.session_state.get("video_origin_path", "")
        selected_index = 0
        for i, (_, path) in enumerate(video_list):
            if path == saved_video_path:
                selected_index = i
                break

        selected_video_index = st.selectbox(
            tr("Existing Video Files"),
            index=selected_index,
            options=range(len(video_list)),
            format_func=lambda x: video_list[x][0],
            key="existing_video_selection",
        )

        video_path = video_list[selected_video_index][1]
        if video_path:
            st.session_state["video_origin_path"] = video_path
        return

    uploaded_file = st.file_uploader(
        tr("Upload Video File"),
        type=["mp4", "mov", "avi", "flv", "mkv"],
        accept_multiple_files=False,
        key="upload_video_file",
    )
    if uploaded_file is not None:
        current_fp = _uploaded_file_fingerprint(uploaded_file)
        if current_fp != st.session_state.get("_last_uploaded_video_fp", ""):
            safe_filename = os.path.basename(uploaded_file.name)
            video_file_path = os.path.join(utils.video_dir(), safe_filename)
            file_name, file_extension = os.path.splitext(safe_filename)

            if os.path.exists(video_file_path):
                timestamp = time.strftime("%Y%m%d%H%M%S")
                video_file_path = os.path.join(
                    utils.video_dir(),
                    f"{file_name}_{timestamp}{file_extension}",
                )

            with open(video_file_path, "wb") as f:
                f.write(uploaded_file.read())

            st.session_state["_last_uploaded_video_fp"] = current_fp
            st.session_state["video_origin_path"] = video_file_path
            st.success(tr("File Uploaded Successfully"))


def _render_subtitle_source_panel(prefix: str, tr, allow_auto: bool):
    source_options = {
        tr("Select Existing Subtitle"): "existing_subtitle",
        tr("Upload New Subtitle"): "upload_subtitle",
    }
    if allow_auto:
        source_options[tr("Auto Generate Subtitle")] = "auto_subtitle"

    mode_key = f"{prefix}_subtitle_source_mode"
    path_key = f"{prefix}_subtitle_path"
    content_key = f"{prefix}_subtitle_content"

    current_mode = st.session_state.get(mode_key, "existing_subtitle")
    reverse = {v: k for k, v in source_options.items()}
    default_label = reverse.get(current_mode, tr("Select Existing Subtitle"))

    selected_label = st.segmented_control(
        tr("Subtitle Source"),
        options=list(source_options.keys()),
        default=default_label,
        key=f"{prefix}_subtitle_source_selection",
    )
    if not selected_label:
        selected_label = default_label

    source_mode = source_options[selected_label]
    st.session_state[mode_key] = source_mode

    current_subtitle_path = st.session_state.get(path_key, "")
    if current_subtitle_path:
        st.caption(f"{tr('Current Subtitle')}: {os.path.basename(current_subtitle_path)}")
        if st.button(tr("Clear Current Subtitle"), key=f"{prefix}_clear_current_subtitle"):
            st.session_state[path_key] = ""
            st.session_state[content_key] = None

    if source_mode == "existing_subtitle":
        subtitle_list = [(tr("None"), "")]
        subtitle_dir = utils.subtitle_dir() if hasattr(utils, "subtitle_dir") else utils.temp_dir()
        for suffix in ["*.srt", "*.ass", "*.ssa", "*.vtt"]:
            for file in glob.glob(os.path.join(subtitle_dir, suffix)):
                display_name = file.replace(config.root_dir, "")
                subtitle_list.append((display_name, file))

        saved_subtitle_path = st.session_state.get(path_key, "")
        if not os.path.exists(saved_subtitle_path):
            saved_subtitle_path = ""

        selected_index = 0
        for i, (_, path) in enumerate(subtitle_list):
            if path == saved_subtitle_path:
                selected_index = i
                break

        selected_subtitle_index = st.selectbox(
            tr("Existing Subtitle Files"),
            index=selected_index,
            options=range(len(subtitle_list)),
            format_func=lambda x: subtitle_list[x][0],
            key=f"{prefix}_existing_subtitle_selection",
        )

        subtitle_path = subtitle_list[selected_subtitle_index][1]
        if subtitle_path:
            st.session_state[path_key] = subtitle_path
            try:
                with open(subtitle_path, "rb") as f:
                    decoded = decode_subtitle_bytes(f.read())
                st.session_state[content_key] = decoded.text
            except Exception as e:
                st.error(f"{tr('Failed to read subtitle')}: {str(e)}")

    elif source_mode == "upload_subtitle":
        subtitle_file = st.file_uploader(
            tr("Upload Subtitle File"),
            type=["srt", "ass", "ssa", "vtt"],
            accept_multiple_files=False,
            key=f"{prefix}_subtitle_file_uploader",
        )

        if subtitle_file is not None:
            current_fp = _uploaded_file_fingerprint(subtitle_file)
            fp_key = f"_{prefix}_last_uploaded_subtitle_fp"
            if current_fp != st.session_state.get(fp_key, ""):
                try:
                    safe_filename = os.path.basename(subtitle_file.name)
                    decoded = decode_subtitle_bytes(subtitle_file.getvalue())
                    subtitle_content = decoded.text
                    detected_encoding = decoded.encoding

                    if not subtitle_content:
                        st.error(tr("Unable to read subtitle file, please check encoding"))
                        st.stop()

                    subtitle_dir = utils.subtitle_dir() if hasattr(utils, "subtitle_dir") else utils.temp_dir()
                    os.makedirs(subtitle_dir, exist_ok=True)

                    subtitle_file_path = os.path.join(subtitle_dir, safe_filename)
                    file_name, file_extension = os.path.splitext(safe_filename)
                    if os.path.exists(subtitle_file_path):
                        timestamp = time.strftime("%Y%m%d%H%M%S")
                        subtitle_file_path = os.path.join(
                            subtitle_dir,
                            f"{file_name}_{timestamp}{file_extension}",
                        )

                    with open(subtitle_file_path, "w", encoding="utf-8") as f:
                        f.write(subtitle_content)

                    st.session_state[fp_key] = current_fp
                    st.session_state[path_key] = subtitle_file_path
                    st.session_state[content_key] = subtitle_content
                    st.success(
                        f"{tr('Subtitle Ready')} "
                        f"(encoding: {detected_encoding.upper()}, size: {len(subtitle_content)} chars)"
                    )
                except Exception as e:
                    st.error(f"{tr('Upload failed')}: {str(e)}")
                    logger.error(traceback.format_exc())
    else:
        st.info(tr("Subtitle will be auto-generated from the video before script generation"))

    return {
        "source_mode": st.session_state.get(mode_key, "existing_subtitle"),
        "subtitle_path": st.session_state.get(path_key, ""),
        "subtitle_content": st.session_state.get(content_key),
    }


def render_short_generate_options(tr):
    subtitle_info = _render_subtitle_source_panel("short", tr, allow_auto=True)

    st.text_input(
        tr("Short Drama Name"),
        value=st.session_state.get("short_mix_name", ""),
        key="short_mix_name",
    )
    st.slider(
        tr("Temperature"),
        0.0,
        2.0,
        float(st.session_state.get("short_mix_temperature", 0.7)),
        key="short_mix_temperature",
    )
    st.number_input(
        tr("Custom Clip Count"),
        min_value=1,
        max_value=30,
        value=int(st.session_state.get("short_custom_clips", 5)),
        key="short_custom_clips",
    )
    if subtitle_info["subtitle_path"]:
        st.caption(f"{tr('Short mix subtitle ready')}: {os.path.basename(subtitle_info['subtitle_path'])}")


def render_short_drama_summary(tr):
    subtitle_info = _render_subtitle_source_panel("short_summary", tr, allow_auto=False)
    st.text_input(
        tr("Short Drama Name"),
        value=st.session_state.get("short_summary_name", ""),
        key="short_summary_name",
    )
    st.slider(
        tr("Temperature"),
        0.0,
        2.0,
        float(st.session_state.get("short_summary_temperature", 0.7)),
        key="short_summary_temperature",
    )
    if subtitle_info["subtitle_path"]:
        st.caption(f"{tr('Short summary subtitle ready')}: {os.path.basename(subtitle_info['subtitle_path'])}")


def render_subtitle_first_generate_panel(tr):
    if "subtitle_file_processed" not in st.session_state:
        st.session_state["subtitle_file_processed"] = False
    if "subtitle_source_mode" not in st.session_state:
        st.session_state["subtitle_source_mode"] = "existing_subtitle"

    subtitle_source_options = {
        tr("Select Existing Subtitle"): "existing_subtitle",
        tr("Upload New Subtitle"): "upload_subtitle",
        tr("Auto Generate Subtitle"): "auto_subtitle",
    }

    current_subtitle_path = st.session_state.get("subtitle_path", "")
    default_subtitle_source = st.session_state.get("subtitle_source_mode", "existing_subtitle")
    if default_subtitle_source not in subtitle_source_options.values():
        default_subtitle_source = "existing_subtitle"

    default_label = None
    for label, value in subtitle_source_options.items():
        if value == default_subtitle_source:
            default_label = label
            break
    if default_label is None:
        default_label = tr("Select Existing Subtitle")

    selected_subtitle_source = st.segmented_control(
        tr("Subtitle Source"),
        options=list(subtitle_source_options.keys()),
        default=default_label,
        key="subtitle_source_selection",
    )

    if not selected_subtitle_source:
        selected_subtitle_source = default_label

    subtitle_source_mode = subtitle_source_options[selected_subtitle_source]
    st.session_state["subtitle_source_mode"] = subtitle_source_mode

    if subtitle_source_mode == "existing_subtitle":
        subtitle_list = [(tr("None"), "")]
        subtitle_dir = utils.subtitle_dir() if hasattr(utils, "subtitle_dir") else utils.temp_dir()
        for suffix in ["*.srt", "*.ass", "*.ssa", "*.vtt"]:
            for file in glob.glob(os.path.join(subtitle_dir, suffix)):
                display_name = file.replace(config.root_dir, "")
                subtitle_list.append((display_name, file))

        saved_subtitle_path = current_subtitle_path if current_subtitle_path and os.path.exists(current_subtitle_path) else ""
        selected_index = 0
        for i, (_, path) in enumerate(subtitle_list):
            if path == saved_subtitle_path:
                selected_index = i
                break

        selected_subtitle_index = st.selectbox(
            tr("Existing Subtitle Files"),
            index=selected_index,
            options=range(len(subtitle_list)),
            format_func=lambda x: subtitle_list[x][0],
            key="existing_subtitle_selection",
        )

        subtitle_path = subtitle_list[selected_subtitle_index][1]
        if subtitle_path:
            st.session_state["subtitle_path"] = subtitle_path
            st.session_state["subtitle_file_processed"] = True
            try:
                with open(subtitle_path, "rb") as f:
                    decoded = decode_subtitle_bytes(f.read())
                st.session_state["subtitle_content"] = decoded.text
                st.info(f"{tr('Select subtitle file')}: {os.path.basename(subtitle_path)}")
            except Exception as e:
                st.error(f"{tr('Failed to read subtitle')}: {str(e)}")
        else:
            st.session_state["subtitle_path"] = ""
            st.session_state["subtitle_content"] = None
            st.session_state["subtitle_file_processed"] = False

    elif subtitle_source_mode == "upload_subtitle":
        subtitle_file = st.file_uploader(
            tr("Upload Subtitle File"),
            type=["srt", "ass", "ssa", "vtt"],
            accept_multiple_files=False,
            key="subtitle_file_uploader",
        )

        if subtitle_file is not None:
            current_fp = _uploaded_file_fingerprint(subtitle_file)
            last_fp = st.session_state.get("_last_uploaded_subtitle_fp", "")
            if current_fp != last_fp:
                try:
                    safe_filename = os.path.basename(subtitle_file.name)
                    decoded = decode_subtitle_bytes(subtitle_file.getvalue())
                    subtitle_content = decoded.text
                    detected_encoding = decoded.encoding

                    if not subtitle_content:
                        st.error(tr("Unable to read subtitle file, please check encoding"))
                        st.stop()

                    subtitle_dir = utils.subtitle_dir() if hasattr(utils, "subtitle_dir") else utils.temp_dir()
                    os.makedirs(subtitle_dir, exist_ok=True)

                    subtitle_file_path = os.path.join(subtitle_dir, safe_filename)
                    file_name, file_extension = os.path.splitext(safe_filename)
                    if os.path.exists(subtitle_file_path):
                        timestamp = time.strftime("%Y%m%d%H%M%S")
                        subtitle_file_path = os.path.join(
                            subtitle_dir,
                            f"{file_name}_{timestamp}{file_extension}",
                        )

                    with open(subtitle_file_path, "w", encoding="utf-8") as f:
                        f.write(subtitle_content)

                    st.session_state["subtitle_path"] = subtitle_file_path
                    st.session_state["subtitle_content"] = subtitle_content
                    st.session_state["subtitle_file_processed"] = True
                    st.session_state["_last_uploaded_subtitle_fp"] = current_fp

                    st.success(
                        f"{tr('Subtitle ready, enter subtitle-first mode')} "
                        f"(encoding: {detected_encoding.upper()}, size: {len(subtitle_content)} chars)"
                    )
                except Exception as e:
                    st.error(f"{tr('Upload failed')}: {str(e)}")
                    logger.error(traceback.format_exc())

    else:
        st.session_state["subtitle_path"] = ""
        st.session_state["subtitle_content"] = None
        st.session_state["subtitle_file_processed"] = False
        st.info(tr("Subtitle will be auto-generated from the video before script generation"))

    if st.session_state.get("subtitle_path") or subtitle_source_mode == "auto_subtitle":
        render_subtitle_first_mode_panel(tr)

    st.text_input(
        tr("Short Drama Name"),
        value=st.session_state.get("short_name", ""),
        key="short_name",
    )

    st.slider(
        tr("Temperature"),
        0.0,
        2.0,
        float(st.session_state.get("temperature", 0.7)),
        key="temperature",
    )


def render_script_buttons(tr):
    script_mode = st.session_state.get("video_clip_json_path", "")

    if script_mode == MODE_SHORT:
        button_name = tr("Generate Short Video Script")
    elif script_mode == MODE_SHORT_SUMMARY:
        button_name = tr("Generate Short Drama Summary Script")
    elif script_mode == MODE_SUBTITLE_FIRST:
        if st.session_state.get("subtitle_source_mode") == "auto_subtitle":
            button_name = tr("Auto Generate Subtitle and Script")
        else:
            button_name = tr("Generate Subtitle-First Script")
    elif isinstance(script_mode, str) and script_mode.endswith("json"):
        button_name = tr("Load Video Script")
    else:
        button_name = tr("Please Select Script File")

    if st.button(button_name, key="script_action", disabled=not script_mode):
        params = VideoClipParams()
        params.video_clip_json_path = script_mode
        params.video_origin_path = st.session_state.get("video_origin_path", "")

        if script_mode == MODE_SHORT:
            subtitle_mode = st.session_state.get("short_subtitle_source_mode", "existing_subtitle")
            subtitle_path = st.session_state.get("short_subtitle_path", "")
            st.session_state["subtitle_path"] = subtitle_path
            st.session_state["subtitle_content"] = st.session_state.get("short_subtitle_content")
            st.session_state["short_name"] = st.session_state.get("short_mix_name", "")
            st.session_state["temperature"] = float(st.session_state.get("short_mix_temperature", 0.7))
            if subtitle_mode != "auto_subtitle" and (not subtitle_path or not os.path.exists(subtitle_path)):
                st.error(tr("Short mix requires subtitle input or auto subtitle"))
                return

            generate_script_short = _lazy_import_short_mix_generator(tr)
            if generate_script_short is None:
                return

            generate_script_short(
                tr,
                params,
                custom_clips=int(st.session_state.get("short_custom_clips", 5)),
            )

        elif script_mode == MODE_SHORT_SUMMARY:
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

        elif script_mode == MODE_SUBTITLE_FIRST:
            subtitle_mode = st.session_state.get("subtitle_source_mode", "existing_subtitle")
            subtitle_path = st.session_state.get("subtitle_path", "")
            if subtitle_mode != "auto_subtitle" and (not subtitle_path or not os.path.exists(subtitle_path)):
                st.error(tr("Subtitle file does not exist"))
                return

            video_theme = st.session_state.get("short_name") or st.session_state.get("video_theme", "")
            temperature = st.session_state.get("temperature", 0.7)
            generate_script_short_sunmmary(params, subtitle_path, video_theme, temperature)

        else:
            load_script(tr, script_mode)

    video_clip_json_details = _render_script_editor(tr)
    _render_evidence_preview(tr)

    if st.button(tr("Save Script"), key="save_script", use_container_width=True):
        save_script_with_validation(tr, video_clip_json_details)


def _render_evidence_preview(tr):
    evidence = st.session_state.get("subtitle_first_evidence", [])
    global_summary = st.session_state.get("subtitle_first_global_summary", {})

    if not evidence:
        return

    with st.expander(tr("Evidence Preview"), expanded=False):
        total_chars = sum(len(pkg.get("subtitle_text", "")) for pkg in evidence)
        estimated_tokens = int(total_chars * 1.5)
        st.caption(f"Scenes: {len(evidence)} | Subtitle chars: {total_chars} | Est. tokens: {estimated_tokens}")

        if global_summary:
            st.write("**Global Summary**")
            st.json(global_summary)


def _render_script_editor(tr):
    video_clip_json = st.session_state.get("video_clip_json", [])

    st.write(tr("Video Script"))
    if not video_clip_json:
        with st.container(border=True):
            st.caption(tr("No script yet. Generated script will appear here."))
        return []

    edited_items = []
    for index, item in enumerate(video_clip_json, start=1):
        timestamp = item.get("timestamp", "")
        picture = item.get("picture", "")
        narration = item.get("narration", "")
        raw_ost = int(item.get("OST", 2) or 2)
        if raw_ost not in OST_OPTIONS:
            raw_ost = 2

        with st.container(border=True):
            top_cols = st.columns([1, 3, 2])
            with top_cols[0]:
                st.write(f"#{index}")
            with top_cols[1]:
                st.caption(timestamp)
            with top_cols[2]:
                ost_label_map = {k: tr(v) for k, v in OST_LABELS.items()}
                ost_value = st.selectbox(
                    tr("OST"),
                    options=OST_OPTIONS,
                    index=OST_OPTIONS.index(raw_ost),
                    format_func=lambda x: ost_label_map.get(x, str(x)),
                    key=f"ost_{index}",
                )

            picture_value = st.text_input(
                tr("Picture Description"),
                value=picture,
                key=f"picture_{index}",
            )
            narration_value = st.text_area(
                tr("Narration"),
                value=narration,
                height=120,
                key=f"narration_{index}",
            )

            duration = _estimate_duration_from_timestamp(timestamp)
            if duration > 0 and int(ost_value) in [0, 2]:
                fit = fit_check(narration_value, duration)
                if not fit["fits"]:
                    st.warning(
                        f"字数可能超时: budget={fit['budget']}, actual={fit['actual']}, overflow={fit['overflow']}"
                    )

            edited_item = dict(item)
            edited_item["picture"] = picture_value
            edited_item["narration"] = narration_value
            edited_item["OST"] = int(ost_value)
            edited_items.append(edited_item)

    st.session_state["video_clip_json"] = edited_items
    return edited_items


def _estimate_duration_from_timestamp(timestamp: str) -> float:
    if not timestamp or "-" not in timestamp:
        return 0.0
    try:
        start_text, end_text = timestamp.split("-", 1)
        return _parse_ts(end_text) - _parse_ts(start_text)
    except Exception:
        return 0.0


def _parse_ts(value: str) -> float:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) != 3:
        return 0.0
    h, m, s = parts
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_script(tr, script_path: str):
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "items" in data:
            data = data["items"]

        if not isinstance(data, list):
            st.error(tr("Invalid script format"))
            return

        st.session_state["video_clip_json"] = data
        st.success(tr("Script loaded successfully"))
    except Exception as e:
        st.error(f"{tr('Load script failed')}: {str(e)}")
        logger.error(traceback.format_exc())


def save_script_with_validation(tr, video_clip_json_details):
    try:
        items = video_clip_json_details or st.session_state.get("video_clip_json", [])
        if not items:
            st.warning(tr("No script content to save"))
            return

        try:
            check_script.check_format(items)
        except Exception as e:
            st.warning(f"{tr('Script format warning')}: {str(e)}")

        output_dir = utils.script_dir()
        os.makedirs(output_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d%H%M%S")
        file_name = f"script_{timestamp}.json"
        save_path = os.path.join(output_dir, file_name)

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        st.session_state["video_clip_json_path"] = save_path
        st.session_state["video_clip_json_path_selected"] = save_path
        st.success(f"{tr('Script saved successfully')}: {save_path}")
    except Exception as e:
        st.error(f"{tr('Save script failed')}: {str(e)}")
        logger.error(traceback.format_exc())
