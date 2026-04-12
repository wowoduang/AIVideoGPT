from __future__ import annotations

from typing import Callable, Iterable

import streamlit as st
from loguru import logger

from app.models.schema import VideoClipParams
from webui.services.job_execution import poll_job_until_complete
from webui.utils import job_runner


def build_video_clip_params(
    *,
    script_params: dict,
    video_params: dict,
    audio_params: dict,
    subtitle_params: dict,
) -> VideoClipParams:
    all_params = {
        **script_params,
        **video_params,
        **audio_params,
        **subtitle_params,
    }
    return VideoClipParams(**all_params)


def run_video_generation(tr, params: VideoClipParams, *, render_generated_videos: Callable[[Iterable[str]], None]) -> None:
    try:
        job = job_runner.start_video_job(params)
    except Exception as exc:
        logger.error("failed to start video job: {}", exc)
        st.error(f"{tr('Task start failed')}: {exc}")
        return

    poll_job_until_complete(
        tr=tr,
        job=job,
        ui=st,
        fetch_status=job_runner.get_job_status,
        on_complete=lambda task: render_generated_videos(list(task.get("videos", []) or [])),
        completion_status_text=tr("Video generation completed"),
        completion_success_text=tr("Video generation completed"),
        failure_prefix=tr("Task failed"),
        query_failure_prefix=tr("Failed to fetch task status"),
    )
