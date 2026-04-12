from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from app.models.schema import VideoClipParams
from app.services.local_job_runner import (
    get_task_snapshot,
    start_local_highlight_script_job,
    start_local_movie_story_script_job,
    start_local_video_job,
)
from webui.utils import local_api_client


TRANSPORT_LOCAL_API = "local_api"
TRANSPORT_IN_PROCESS = "in_process"


def _build_job_dispatch_result(task_id: str, transport: str, task_dir: str = "") -> Dict[str, Any]:
    return {
        "task_id": str(task_id or ""),
        "transport": transport,
        "task_dir": str(task_dir or ""),
    }


def _get_in_process_task_dir(task_id: str) -> str:
    snapshot = get_task_snapshot(task_id) or {}
    return str(snapshot.get("task_dir", ""))


def start_video_job(params: VideoClipParams) -> Dict[str, Any]:
    if local_api_client.is_local_api_available():
        response = local_api_client.submit_video_job(params)
        logger.info(f"video job dispatched through local api: {response.get('task_id', '')}")
        return _build_job_dispatch_result(
            task_id=str(response.get("task_id", "")),
            transport=TRANSPORT_LOCAL_API,
            task_dir=str(response.get("task_dir", "")),
        )

    task_id = start_local_video_job(params)
    logger.info(f"video job dispatched in-process: {task_id}")
    return _build_job_dispatch_result(
        task_id=task_id,
        transport=TRANSPORT_IN_PROCESS,
        task_dir=_get_in_process_task_dir(task_id),
    )


def start_highlight_script_job(request: Dict[str, Any]) -> Dict[str, Any]:
    if local_api_client.is_local_api_available():
        response = local_api_client.submit_highlight_script_job(request)
        logger.info(f"highlight script job dispatched through local api: {response.get('task_id', '')}")
        return _build_job_dispatch_result(
            task_id=str(response.get("task_id", "")),
            transport=TRANSPORT_LOCAL_API,
            task_dir=str(response.get("task_dir", "")),
        )

    task_id = start_local_highlight_script_job(request)
    logger.info(f"highlight script job dispatched in-process: {task_id}")
    return _build_job_dispatch_result(
        task_id=task_id,
        transport=TRANSPORT_IN_PROCESS,
        task_dir=_get_in_process_task_dir(task_id),
    )


def start_movie_story_script_job(request: Dict[str, Any]) -> Dict[str, Any]:
    if local_api_client.is_local_api_available():
        response = local_api_client.submit_movie_story_script_job(request)
        logger.info(f"movie story script job dispatched through local api: {response.get('task_id', '')}")
        return _build_job_dispatch_result(
            task_id=str(response.get("task_id", "")),
            transport=TRANSPORT_LOCAL_API,
            task_dir=str(response.get("task_dir", "")),
        )

    task_id = start_local_movie_story_script_job(request)
    logger.info(f"movie story script job dispatched in-process: {task_id}")
    return _build_job_dispatch_result(
        task_id=task_id,
        transport=TRANSPORT_IN_PROCESS,
        task_dir=_get_in_process_task_dir(task_id),
    )


def get_job_status(task_id: str, transport: str) -> Dict[str, Any]:
    if transport == TRANSPORT_LOCAL_API:
        return local_api_client.get_job_status(task_id)

    snapshot = get_task_snapshot(task_id)
    if not snapshot:
        raise RuntimeError("task_not_found")
    return snapshot


def get_video_job_status(task_id: str, transport: str) -> Dict[str, Any]:
    return get_job_status(task_id, transport)
