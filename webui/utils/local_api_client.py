from __future__ import annotations

from typing import Any, Dict

import requests

from app.config import config
from app.models.schema import VideoClipParams


DEFAULT_HEALTH_TIMEOUT = 1.5
DEFAULT_REQUEST_TIMEOUT = 10


def _normalize_base_url() -> str:
    explicit_base_url = str(config.app.get("local_api_base_url", "") or "").strip()
    if explicit_base_url:
        return explicit_base_url.rstrip("/")

    host = str(config.app.get("local_api_host", "127.0.0.1") or "127.0.0.1").strip()
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    port = int(config.app.get("local_api_port", 18000) or 18000)
    return f"http://{host}:{port}"


def _model_to_json_dict(params: VideoClipParams) -> Dict[str, Any]:
    if hasattr(params, "model_dump"):
        return params.model_dump(mode="json")
    if hasattr(params, "dict"):
        return params.dict()
    raise TypeError("unsupported_video_clip_params_model")


def _parse_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
    except Exception:
        pass
    return response.text.strip() or f"http_{response.status_code}"


def _post_json(path: str, payload: Dict[str, Any], timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    response = requests.post(
        f"{get_local_api_base_url()}{path}",
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(_parse_error_message(response))
    return response.json()


def _get_json(path: str, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    response = requests.get(
        f"{get_local_api_base_url()}{path}",
        timeout=timeout,
    )
    if not response.ok:
        raise RuntimeError(_parse_error_message(response))
    return response.json()


def get_local_api_base_url() -> str:
    return _normalize_base_url()


def is_local_api_available(timeout: float = DEFAULT_HEALTH_TIMEOUT) -> bool:
    try:
        response = requests.get(f"{get_local_api_base_url()}/api/v1/health", timeout=timeout)
        return response.ok
    except Exception:
        return False


def submit_video_job(params: VideoClipParams, task_id: str = "", timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    return _post_json(
        "/api/v1/jobs/video",
        {
            "params": _model_to_json_dict(params),
            "task_id": str(task_id or ""),
        },
        timeout=timeout,
    )


def submit_highlight_script_job(request: Dict[str, Any], task_id: str = "", timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    return _post_json(
        "/api/v1/jobs/highlight-script",
        {
            "request": dict(request or {}),
            "task_id": str(task_id or ""),
        },
        timeout=timeout,
    )


def submit_movie_story_script_job(request: Dict[str, Any], task_id: str = "", timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    return _post_json(
        "/api/v1/jobs/movie-story-script",
        {
            "request": dict(request or {}),
            "task_id": str(task_id or ""),
        },
        timeout=timeout,
    )


def get_job_status(task_id: str, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Dict[str, Any]:
    return _get_json(f"/api/v1/jobs/{task_id}", timeout=timeout)
