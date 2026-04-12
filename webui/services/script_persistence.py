from __future__ import annotations

import json
import traceback
from typing import Any, List

import streamlit as st
from loguru import logger

from app.utils import check_script, utils
from webui.utils import file_utils


def normalize_script_payload(data: Any) -> List[dict]:
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if not isinstance(data, list):
        raise ValueError("Invalid script format")
    return data


def load_script(tr, script_path: str) -> bool:
    try:
        with open(script_path, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        items = normalize_script_payload(data)
        st.session_state["video_clip_json"] = items
        st.success(tr("Script loaded successfully"))
        return True
    except ValueError:
        st.error(tr("Invalid script format"))
        return False
    except Exception as exc:
        st.error(f"{tr('Load script failed')}: {exc}")
        logger.error(traceback.format_exc())
        return False


def save_script_with_validation(tr, video_clip_json_details) -> str:
    items = video_clip_json_details or st.session_state.get("video_clip_json", [])
    if not items:
        st.warning(tr("No script content to save"))
        return ""

    try:
        format_result = check_script.check_format(items)
        if not format_result.get("success"):
            st.warning(
                f"{tr('Script format warning')}: "
                f"{format_result.get('message', 'unknown')} | {format_result.get('details', '')}"
            )

        save_path = file_utils.save_json_file(
            items,
            utils.script_dir(),
            "script.json",
            ensure_ascii=False,
            indent=2,
            default_stem="script",
            default_ext=".json",
        )
        if not save_path:
            raise RuntimeError(tr("Save script failed"))

        st.session_state["video_clip_json_path"] = save_path
        st.session_state["video_clip_json_path_selected"] = save_path
        st.success(f"{tr('Script saved successfully')}: {save_path}")
        return save_path
    except Exception as exc:
        st.error(f"{tr('Save script failed')}: {exc}")
        logger.error(traceback.format_exc())
        return ""
