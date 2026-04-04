from __future__ import annotations

import json
import os
import subprocess
from typing import Optional

from loguru import logger


def probe_media_duration(file_path: str) -> float:
    if not file_path or not os.path.exists(file_path):
        return 0.0
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_entries", "format=duration",
        file_path,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout or "{}")
        duration = float((payload.get("format") or {}).get("duration") or 0)
        if duration > 0:
            return duration
    except Exception as e:
        logger.debug(f"ffprobe 获取媒体时长失败，将忽略: {e}")
    return 0.0
