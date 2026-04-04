from __future__ import annotations

import json
import os
from typing import Dict, Optional

from loguru import logger

from app.config import config
from app.utils import utils


SETTINGS_DIR_NAME = "user_settings"
DEFAULT_PROFILE = os.environ.get("NARRATOAI_PROFILE", "default")
ALLOWED_APP_KEYS = {
    "vision_llm_provider",
    "vision_litellm_model_name",
    "vision_litellm_api_key",
    "vision_litellm_base_url",
    "text_llm_provider",
    "text_litellm_model_name",
    "text_litellm_api_key",
    "text_litellm_base_url",
    "tts_engine",
    "voice_name",
    "voice_rate",
    "voice_pitch",
    "enable_visual_supplement",
}
ALLOWED_UI_KEYS = {"language"}
ALLOWED_PROXY_KEYS = {"enabled", "http", "https"}
SESSION_KEY_MAP = {
    "vision_litellm_model_name": "vision_litellm_model_name",
    "vision_litellm_api_key": "vision_litellm_api_key",
    "vision_litellm_base_url": "vision_litellm_base_url",
    "text_litellm_model_name": "text_litellm_model_name",
    "text_litellm_api_key": "text_litellm_api_key",
    "text_litellm_base_url": "text_litellm_base_url",
    "enable_visual_supplement": "enable_visual_supplement",
    "ui_language": ("ui", "language"),
}


def _settings_root() -> str:
    root = os.path.join(utils.storage_dir(), SETTINGS_DIR_NAME)
    os.makedirs(root, exist_ok=True)
    return root


def get_active_profile(session_state: Optional[dict] = None) -> str:
    if session_state and session_state.get("user_settings_profile"):
        return str(session_state["user_settings_profile"])
    return DEFAULT_PROFILE


def _settings_file(profile: str) -> str:
    safe_profile = profile.replace("/", "_").replace("\\", "_")
    return os.path.join(_settings_root(), f"{safe_profile}.json")


def load_user_settings(profile: Optional[str] = None) -> Dict:
    profile = profile or DEFAULT_PROFILE
    file_path = _settings_file(profile)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.warning(f"读取用户配置失败，将忽略: {e}")
    return {}


def _snapshot_from_runtime(session_state: Optional[dict] = None) -> Dict:
    app_cfg = {key: config.app.get(key) for key in ALLOWED_APP_KEYS if key in config.app}
    ui_cfg = {key: config.ui.get(key) for key in ALLOWED_UI_KEYS if key in config.ui}
    proxy_cfg = {key: config.proxy.get(key) for key in ALLOWED_PROXY_KEYS if key in config.proxy}

    if session_state:
        for session_key, target in SESSION_KEY_MAP.items():
            if session_key not in session_state:
                continue
            value = session_state.get(session_key)
            if isinstance(target, tuple):
                section, key = target
                if section == "ui":
                    ui_cfg[key] = value
            else:
                app_cfg[target] = value

    payload = {
        "profile": get_active_profile(session_state),
        "app": app_cfg,
        "ui": ui_cfg,
        "proxy": proxy_cfg,
    }
    return payload


def save_runtime_settings(session_state: Optional[dict] = None) -> str:
    payload = _snapshot_from_runtime(session_state)
    profile = payload["profile"]
    file_path = _settings_file(profile)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"用户配置已保存: {file_path}")
    return file_path


def apply_user_settings_to_config(session_state: Optional[dict] = None, profile: Optional[str] = None) -> Dict:
    profile = profile or get_active_profile(session_state)
    payload = load_user_settings(profile)
    if not payload:
        return {}

    for key, value in (payload.get("app") or {}).items():
        config.app[key] = value
        if session_state is not None:
            session_state.setdefault(key, value)
    for key, value in (payload.get("ui") or {}).items():
        config.ui[key] = value
        if session_state is not None and key == "language":
            session_state.setdefault("ui_language", value)
    for key, value in (payload.get("proxy") or {}).items():
        config.proxy[key] = value

    if session_state is not None:
        session_state.setdefault("user_settings_profile", profile)
    logger.info(f"已加载用户配置: profile={profile}")
    return payload
