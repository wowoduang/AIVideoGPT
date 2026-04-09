from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict

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


def probe_primary_stream(file_path: str, stream_selector: str) -> Dict[str, Any]:
    if not file_path or not os.path.exists(file_path):
        return {}

    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-select_streams", stream_selector,
        "-show_entries", "stream=codec_name,width,height,channels,duration",
        file_path,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout or "{}")
        streams = payload.get("streams") or []
        if streams and isinstance(streams[0], dict):
            return dict(streams[0])
    except Exception as e:
        logger.debug(f"ffprobe 鎺㈡祴濯掍綋娴佸け璐ワ紝灏嗗拷鐣? {e}")
    return {}


def inspect_media_file(file_path: str, *, include_audio: bool = False) -> Dict[str, Any]:
    exists = bool(file_path) and os.path.exists(file_path)
    size_bytes = 0
    if exists:
        try:
            size_bytes = int(os.path.getsize(file_path) or 0)
        except OSError:
            size_bytes = 0

    duration = probe_media_duration(file_path)
    video_stream = probe_primary_stream(file_path, "v:0")
    audio_stream = probe_primary_stream(file_path, "a:0") if include_audio else {}
    has_video = bool(str(video_stream.get("codec_name") or "").strip())
    has_audio = bool(str(audio_stream.get("codec_name") or "").strip())

    return {
        "path": file_path,
        "exists": exists,
        "size_bytes": size_bytes,
        "duration": round(float(duration or 0.0), 3),
        "video_stream": video_stream,
        "audio_stream": audio_stream,
        "has_video": has_video,
        "has_audio": has_audio,
        "is_valid_video": bool(exists and has_video and float(duration or 0.0) >= 0.05),
    }


def summarize_media_file(info: Dict[str, Any]) -> str:
    if not info:
        return "unknown"
    if not info.get("exists"):
        return "exists=no"
    parts = [
        f"size={int(info.get('size_bytes') or 0)}B",
        f"duration={float(info.get('duration') or 0.0):.3f}s",
        f"video={'yes' if info.get('has_video') else 'no'}",
    ]
    if "has_audio" in info:
        parts.append(f"audio={'yes' if info.get('has_audio') else 'no'}")
    return ", ".join(parts)
