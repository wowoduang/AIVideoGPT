from __future__ import annotations

import json
import os
import subprocess
from typing import Dict

from loguru import logger

from app.utils import ffmpeg_utils, utils


WORKING_COPY_CACHE_VERSION = "2026-04-08-hevc-repair-v1"
_HEVC_CODEC_NAMES = {"hevc", "h265", "h.265"}


def probe_primary_video_stream(video_path: str) -> Dict[str, str]:
    if not video_path or not os.path.isfile(video_path):
        return {}

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,duration",
        video_path,
    ]
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout or "{}")
        streams = payload.get("streams") or []
        if streams and isinstance(streams[0], dict):
            return dict(streams[0])
    except Exception as exc:
        logger.debug(f"video_working_copy: failed to probe video stream for {video_path}: {exc}")
    return {}


def should_create_working_copy(video_path: str) -> bool:
    stream = probe_primary_video_stream(video_path)
    codec_name = str(stream.get("codec_name", "") or "").strip().lower()
    return codec_name in _HEVC_CODEC_NAMES


def ensure_working_video_copy(video_path: str, *, purpose: str = "general", force: bool = False) -> str:
    if not video_path or not os.path.isfile(video_path):
        return video_path

    if not force and not should_create_working_copy(video_path):
        return video_path

    working_copy_path = _build_working_copy_path(video_path)
    if os.path.isfile(working_copy_path) and os.path.getsize(working_copy_path) > 0:
        return working_copy_path

    _remove_file_if_exists(working_copy_path)

    logger.info(
        "video_working_copy: preparing H.264 working copy for {} (purpose={})",
        os.path.basename(video_path),
        purpose,
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        *ffmpeg_utils.get_resilient_decode_input_args(
            ignore_decode_errors=True,
            discard_corrupt=True,
        ),
        "-i",
        video_path,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-sn",
        "-dn",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-max_muxing_queue_size",
        "2048",
        working_copy_path,
    ]

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode == 0 and os.path.isfile(working_copy_path) and os.path.getsize(working_copy_path) > 0:
        logger.info(
            "video_working_copy: generated H.264 working copy for {}",
            os.path.basename(video_path),
        )
        return working_copy_path

    _remove_file_if_exists(working_copy_path)
    logger.warning(
        "video_working_copy: failed to generate working copy for {}: {}",
        os.path.basename(video_path),
        _summarize_process_error(completed.stderr),
    )
    return video_path


def _build_working_copy_path(video_path: str) -> str:
    cache_key = utils.md5(
        "|".join(
            [
                os.path.abspath(video_path),
                str(os.path.getmtime(video_path)),
                str(os.path.getsize(video_path)),
                WORKING_COPY_CACHE_VERSION,
            ]
        )
    )
    return os.path.join(utils.temp_dir("video_working_copy"), f"{cache_key}.mp4")


def _remove_file_if_exists(file_path: str) -> None:
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def _summarize_process_error(stderr: str, max_lines: int = 4, max_chars: int = 400) -> str:
    lines = [line.strip() for line in str(stderr or "").splitlines() if line.strip()]
    if not lines:
        return "unknown error"
    summary = " | ".join(lines[-max_lines:])
    if len(summary) > max_chars:
        summary = summary[-max_chars:]
    return summary
