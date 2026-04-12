from __future__ import annotations

import glob
import importlib
import json
import os
import traceback

import streamlit as st
from loguru import logger

from app.config import config
from app.models.schema import VideoAspect
from app.services.subtitle_text import decode_subtitle_bytes
from app.services.timeline_allocator import fit_check
from app.utils import utils
from webui.components.subtitle_first_mode_panel import render_subtitle_first_mode_panel
from webui.services.script_persistence import save_script_with_validation
from webui.services.script_actions import (
    MODE_FILE,
    MODE_HIGHLIGHT_EDIT,
    MODE_SHORT,
    MODE_SHORT_SUMMARY,
    MODE_SUBTITLE_FIRST,
    get_script_action_label,
    run_script_action,
)
from webui.utils import file_utils

PENDING_SUBTITLE_SOURCE_MODE_KEY = "_pending_subtitle_source_mode"

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
        elif mode == MODE_HIGHLIGHT_EDIT:
            render_highlight_edit_options(tr)

        render_script_buttons(tr)


def _normalize_legacy_mode():
    current = st.session_state.get("video_clip_json_path", "")
    if not current:
        st.session_state["video_clip_json_path"] = MODE_FILE


def _apply_pending_subtitle_source_mode(tr):
    pending_mode = st.session_state.pop(PENDING_SUBTITLE_SOURCE_MODE_KEY, "")
    if not pending_mode:
        return

    subtitle_source_options = {
        tr("Select Existing Subtitle"): "existing_subtitle",
        tr("Upload New Subtitle"): "upload_subtitle",
        tr("Auto Generate Subtitle"): "auto_subtitle",
    }

    selected_label = next(
        (label for label, value in subtitle_source_options.items() if value == pending_mode),
        tr("Select Existing Subtitle"),
    )
    st.session_state["subtitle_source_mode"] = pending_mode
    st.session_state["subtitle_source_selection"] = selected_label


def render_script_mode(tr):
    mode_options = {
        tr("Select/Upload Script"): MODE_FILE,
        tr("短剧混剪"): MODE_SHORT,
        tr("短剧解说"): MODE_SHORT_SUMMARY,
        tr("字幕优先生成"): MODE_SUBTITLE_FIRST,
    }
    mode_options[tr("精彩粗剪")] = MODE_HIGHLIGHT_EDIT
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

                    script_file_path = file_utils.save_json_file(
                        json_data,
                        script_dir,
                        uploaded_file.name,
                        ensure_ascii=False,
                        indent=2,
                        default_stem="script",
                        default_ext=".json",
                    )
                    if not script_file_path:
                        raise RuntimeError(tr("Upload failed"))

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

    st.info(
        tr(
            "Browser upload of very large videos may fail even if the configured limit is 30G. "
            "Streamlit buffers uploads in memory. For very large files, copy them to "
            "the workspace videos directory and then use Select Existing Video."
        )
        + f" ({utils.video_dir()})"
    )

    uploaded_file = st.file_uploader(
        tr("Upload Video File"),
        type=["mp4", "mov", "avi", "flv", "mkv"],
        accept_multiple_files=False,
        key="upload_video_file",
    )
    if uploaded_file is not None:
        current_fp = _uploaded_file_fingerprint(uploaded_file)
        if current_fp != st.session_state.get("_last_uploaded_video_fp", ""):
            video_file_path = file_utils.save_uploaded_file(
                uploaded_file,
                utils.video_dir(),
                allowed_types=[".mp4", ".mov", ".avi", ".flv", ".mkv"],
                default_stem="video",
            )
            if video_file_path:
                st.session_state["_last_uploaded_video_fp"] = current_fp
                st.session_state["video_origin_path"] = video_file_path
                st.success(tr("File Uploaded Successfully"))
            else:
                st.error(tr("Upload failed"))


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
        subtitle_dir = utils.subtitle_dir()
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
                    decoded = decode_subtitle_bytes(subtitle_file.getvalue())
                    subtitle_content = decoded.text
                    detected_encoding = decoded.encoding

                    if not subtitle_content:
                        st.error(tr("Unable to read subtitle file, please check encoding"))
                        st.stop()

                    subtitle_dir = utils.subtitle_dir()

                    subtitle_file_path = file_utils.save_text_file(
                        subtitle_content,
                        subtitle_dir,
                        subtitle_file.name,
                        encoding="utf-8",
                        default_stem="subtitle",
                        default_ext=".srt",
                    )
                    if not subtitle_file_path:
                        raise RuntimeError(tr("Upload failed"))

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


def render_highlight_edit_options(tr):
    subtitle_info = _render_subtitle_source_panel("highlight", tr, allow_auto=True)

    mode_options = {
        tr("Highlight Recut"): "highlight_recut",
        tr("Narrated Highlight Edit"): "narrated_highlight_edit",
    }
    reverse_mode_options = {value: label for label, value in mode_options.items()}
    current_mode = st.session_state.get("highlight_edit_mode", "highlight_recut")
    default_mode_label = reverse_mode_options.get(current_mode, tr("Highlight Recut"))
    selected_mode_label = st.segmented_control(
        tr("Highlight Edit Mode"),
        options=list(mode_options.keys()),
        default=default_mode_label,
        key="highlight_edit_mode_selection",
    )
    if not selected_mode_label:
        selected_mode_label = default_mode_label
    selected_mode = mode_options[selected_mode_label]
    st.session_state["highlight_edit_mode"] = selected_mode

    st.text_input(
        tr("Movie Title"),
        value=st.session_state.get("highlight_movie_title", ""),
        key="highlight_movie_title",
    )
    genre_options = {
        tr("Auto Detect Genre"): "auto",
        tr("General / Mixed"): "general",
        tr("Action / War"): "action",
        tr("Suspense / Thriller"): "suspense",
        tr("Drama / Emotion"): "drama",
        tr("Comedy"): "comedy",
        tr("Romance"): "romance",
    }
    reverse_genre_options = {value: label for label, value in genre_options.items()}
    current_genre = st.session_state.get("highlight_movie_genre", "auto")
    default_genre_label = reverse_genre_options.get(current_genre, tr("Auto Detect Genre"))
    selected_genre_label = st.selectbox(
        tr("Highlight Movie Genre"),
        options=list(genre_options.keys()),
        index=list(genre_options.keys()).index(default_genre_label),
        key="highlight_movie_genre_selection",
    )
    st.session_state["highlight_movie_genre"] = genre_options[selected_genre_label]
    st.number_input(
        tr("Target Minutes"),
        min_value=1,
        max_value=60,
        value=int(st.session_state.get("highlight_target_minutes", 8)),
        key="highlight_target_minutes",
    )
    visual_mode_options = {
        tr("Visual Off"): "off",
        tr("Visual Auto"): "auto",
        tr("Visual Boost"): "boost",
    }
    reverse_visual_mode_options = {value: label for label, value in visual_mode_options.items()}
    current_visual_mode = st.session_state.get("highlight_visual_mode", "auto")
    default_visual_mode_label = reverse_visual_mode_options.get(current_visual_mode, tr("Visual Auto"))
    selected_visual_mode_label = st.segmented_control(
        tr("Highlight Visual Mode"),
        options=list(visual_mode_options.keys()),
        default=default_visual_mode_label,
        key="highlight_visual_mode_selection",
    )
    if not selected_visual_mode_label:
        selected_visual_mode_label = default_visual_mode_label
    st.session_state["highlight_visual_mode"] = visual_mode_options[selected_visual_mode_label]

    st.checkbox(
        tr("Prefer Raw Audio"),
        value=bool(st.session_state.get("highlight_prefer_raw_audio", True)),
        key="highlight_prefer_raw_audio",
    )

    if selected_mode == "narrated_highlight_edit":
        st.text_area(
            tr("Highlight Narration Text"),
            value=st.session_state.get("highlight_narration_text", ""),
            key="highlight_narration_text",
            height=140,
        )
        if not str(st.session_state.get("highlight_narration_text", "") or "").strip():
            st.caption(tr("Narrated highlight mode requires narration text"))
    elif str(st.session_state.get("highlight_narration_text", "") or "").strip():
        st.caption(tr("Narration text is ignored in highlight recut mode"))

    if subtitle_info["subtitle_path"]:
        st.caption(f"{tr('Subtitle Ready')}: {os.path.basename(subtitle_info['subtitle_path'])}")


def render_subtitle_first_generate_panel(tr):
    _apply_pending_subtitle_source_mode(tr)

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
        subtitle_dir = utils.subtitle_dir()
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
                    decoded = decode_subtitle_bytes(subtitle_file.getvalue())
                    subtitle_content = decoded.text
                    detected_encoding = decoded.encoding

                    if not subtitle_content:
                        st.error(tr("Unable to read subtitle file, please check encoding"))
                        st.stop()

                    subtitle_dir = utils.subtitle_dir()

                    subtitle_file_path = file_utils.save_text_file(
                        subtitle_content,
                        subtitle_dir,
                        subtitle_file.name,
                        encoding="utf-8",
                        default_stem="subtitle",
                        default_ext=".srt",
                    )
                    if not subtitle_file_path:
                        raise RuntimeError(tr("Upload failed"))

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
        render_subtitle_first_mode_panel(tr, show_source_mode=False)

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
    button_name = get_script_action_label(tr, script_mode)

    if st.button(button_name, key="script_action", disabled=not script_mode):
        run_script_action(
            tr,
            script_mode,
            lazy_import_short_mix_generator=_lazy_import_short_mix_generator,
        )

    video_clip_json_details = _render_script_editor(tr)
    _render_evidence_preview(tr)

    if st.button(tr("Save Script"), key="save_script", use_container_width=True):
        save_script_with_validation(tr, video_clip_json_details)


def _render_evidence_preview(tr):
    evidence = st.session_state.get("subtitle_first_evidence", [])
    global_summary = st.session_state.get("subtitle_first_global_summary", {})
    narration_matches = st.session_state.get("highlight_edit_narration_matches", [])
    candidate_stats = st.session_state.get("highlight_edit_candidate_stats", {})
    selected_clips = st.session_state.get("highlight_edit_selected_clips", [])
    composition_plan = st.session_state.get("highlight_edit_composition_plan", {})

    if not evidence and not narration_matches and not candidate_stats and not selected_clips and not composition_plan:
        return

    with st.expander(tr("Evidence Preview"), expanded=False):
        if narration_matches:
            st.write(f"**{tr('Narration Match Preview')}**")
            for idx, item in enumerate(narration_matches, start=1):
                clip = item.get("clip") or {}
                time_range = f"{clip.get('start', 0.0):.1f}s - {clip.get('end', 0.0):.1f}s"
                stage = item.get("story_stage", "")
                score = item.get("match_score", 0.0)
                rhythm = item.get("rhythm_profile", "")
                narration_type = item.get("narration_type", "")
                match_focus = item.get("match_focus", "")
                shot_template = item.get("shot_template", "")
                target_seconds = item.get("target_seconds", 0.0)
                st.markdown(
                    f"**#{idx}** [{stage}] {time_range} | score={score} | rhythm={rhythm} | "
                    f"type={narration_type} | focus={match_focus} | template={shot_template} | target={target_seconds}s"
                )
                st.caption(str(item.get("text", "") or ""))
                if item.get("character_names") or item.get("keywords"):
                    st.caption(
                        f"chars={', '.join(item.get('character_names') or []) or '-'} | "
                        f"keywords={', '.join(item.get('keywords') or []) or '-'}"
                    )
                if item.get("focus_character_names") or item.get("collective_target_names"):
                    st.caption(
                        f"focus={', '.join(item.get('focus_character_names') or []) or '-'} | "
                        f"collective_target={', '.join(item.get('collective_target_names') or []) or '-'} | "
                        f"collective={bool(item.get('collective_signal'))}"
                    )
                if item.get("subject_character_names") or item.get("directed_target_names"):
                    st.caption(
                        f"subject={', '.join(item.get('subject_character_names') or []) or '-'} | "
                        f"directed_target={', '.join(item.get('directed_target_names') or []) or '-'}"
                    )
                clip_ids = item.get("clip_ids") or []
                if clip_ids:
                    st.caption(f"group clips={', '.join(clip_ids)}")
                subtitle_text = str(clip.get("subtitle_text", "") or "").strip()
                scene_summary = str(clip.get("scene_summary", "") or "").strip()
                if clip.get("character_names"):
                    st.caption(f"clip chars={', '.join(clip.get('character_names') or [])}")
                clip_role = str(clip.get("shot_role", "") or "-")
                clip_turns = int(float(clip.get("speaker_turns", 0) or 0))
                clip_evidence = str(clip.get("primary_evidence", "") or "-")
                st.caption(f"clip role={clip_role} | turns={clip_turns} | evidence={clip_evidence}")
                if clip.get("speaker_names") or clip.get("interaction_target_names"):
                    st.caption(
                        f"speakers={', '.join(clip.get('speaker_names') or []) or '-'} | "
                        f"targets={', '.join(clip.get('interaction_target_names') or []) or '-'}"
                    )
                if clip.get("exchange_pairs"):
                    st.caption(f"pairs={', '.join(clip.get('exchange_pairs') or [])}")
                if clip.get("pressure_source_names") or clip.get("pressure_target_names"):
                    st.caption(
                        f"pressure={', '.join(clip.get('pressure_source_names') or []) or '-'} -> "
                        f"{', '.join(clip.get('pressure_target_names') or []) or '-'} | "
                        f"group={clip.get('group_reaction_score', 0.0)}"
                    )
                if subtitle_text:
                    st.text_area(
                        tr("Matched Subtitle"),
                        value=subtitle_text,
                        height=70,
                        key=f"highlight_match_subtitle_{idx}",
                        disabled=True,
                    )
                if scene_summary:
                    st.text_area(
                        tr("Matched Summary"),
                        value=scene_summary,
                        height=70,
                        key=f"highlight_match_summary_{idx}",
                        disabled=True,
                    )
                clip_group = item.get("clip_group") or []
                if clip_group and len(clip_group) > 1:
                    st.caption(f"group timeline: {item.get('group_start', 0.0):.1f}s - {item.get('group_end', 0.0):.1f}s")
                    for group_idx, group_clip in enumerate(clip_group, start=1):
                        st.markdown(
                            f"{group_idx}. {group_clip.get('clip_id', '')} | "
                            f"{group_clip.get('start', 0.0):.1f}s - {group_clip.get('end', 0.0):.1f}s"
                        )

        if candidate_stats:
            st.write(f"**{tr('Highlight Candidate Pool')}**")
            source_breakdown = candidate_stats.get("source_breakdown") or {}
            source_summary = ", ".join(f"{source}={count}" for source, count in source_breakdown.items()) or "-"
            st.caption(
                f"visual={candidate_stats.get('visual_mode', 'auto')} | "
                f"merged={candidate_stats.get('merged_candidate_count', 0)} | "
                f"scene={candidate_stats.get('scene_candidate_count', 0)} | "
                f"plot={candidate_stats.get('plot_candidate_count', 0)} | "
                f"raw_audio={candidate_stats.get('raw_audio_candidate_count', 0)}"
            )
            st.caption(f"sources: {source_summary}")

        if selected_clips:
            st.write(f"**{tr('Selected Highlight Clips')}**")
            st.caption(f"Clips: {len(selected_clips)}")
            for idx, clip in enumerate(selected_clips[:12], start=1):
                planned_duration = float(clip.get("planned_duration", clip.get("duration", 0.0)) or 0.0)
                original_duration = float(clip.get("original_duration", planned_duration) or planned_duration)
                trim_strategy = str(clip.get("trim_strategy", "keep_full") or "keep_full")
                clip_source = str(clip.get("source", "") or "-")
                story_stage = str(clip.get("story_stage_hint", "") or "-")
                shot_role = str(clip.get("shot_role", "") or "-")
                speaker_turns = int(float(clip.get("speaker_turns", 0) or 0))
                primary_evidence = str(clip.get("primary_evidence", "") or "-")
                st.markdown(
                    f"**#{idx}** {clip.get('start', 0.0):.1f}s - {clip.get('end', 0.0):.1f}s | "
                    f"duration={planned_duration:.1f}s/{original_duration:.1f}s | "
                    f"source={clip_source} | "
                    f"stage={story_stage} | "
                    f"role={shot_role} | "
                    f"turns={speaker_turns} | "
                    f"evidence={primary_evidence} | "
                    f"trim={trim_strategy} | "
                    f"score={clip.get('total_score', 0.0)} | "
                    f"reasons={', '.join(clip.get('selection_reason') or [])}"
                )
                if clip.get("pressure_source_names") or clip.get("pressure_target_names"):
                    st.caption(
                        f"pressure={', '.join(clip.get('pressure_source_names') or []) or '-'} -> "
                        f"{', '.join(clip.get('pressure_target_names') or []) or '-'} | "
                        f"group={clip.get('group_reaction_score', 0.0)}"
                    )

        if composition_plan and composition_plan.get("segments"):
            st.write(f"**{tr('Audio Strategy Plan')}**")
            for idx, segment in enumerate((composition_plan.get("segments") or [])[:20], start=1):
                st.markdown(
                    f"**#{idx}** {segment.get('segment_id', '')} | "
                    f"{segment.get('video_start', 0.0):.1f}s - {segment.get('video_end', 0.0):.1f}s | "
                    f"audio={segment.get('audio_mode', '')} | "
                    f"strategy={segment.get('audio_strategy', '')}"
                )

        if evidence:
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
