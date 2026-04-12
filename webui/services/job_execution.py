from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, Optional

import streamlit as st
from loguru import logger

from webui.utils import job_runner


def transport_label(transport: str) -> str:
    return "Local API" if transport == job_runner.TRANSPORT_LOCAL_API else "In-Process"


def extract_job_result(task: Dict[str, Any], fallback_keys: Iterable[str]) -> Dict[str, Any]:
    payload = task.get("payload")
    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, dict) and result:
            return result

    result = task.get("result")
    if isinstance(result, dict) and result:
        return result

    fallback_keys = tuple(fallback_keys or ())
    if any(key in task for key in fallback_keys):
        return dict(task)
    return {}


def poll_job_until_complete(
    *,
    tr: Callable[[str], str],
    job: Dict[str, Any],
    ui=None,
    fetch_status: Callable[[str, str], Dict[str, Any]] = job_runner.get_job_status,
    on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
    extract_result: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    processing_prefix: str = "Processing...",
    completion_status_text: str = "",
    completion_success_text: str = "",
    empty_result_error: str = "Task completed but returned no result",
    failure_prefix: str = "Task failed",
    query_failure_prefix: str = "Failed to fetch task status",
    poll_interval_seconds: float = 0.5,
) -> bool:
    ui = ui or st
    progress_bar = ui.progress(0)
    status_text = ui.empty()

    task_id = str(job.get("task_id", "") or "")
    transport = str(job.get("transport", job_runner.TRANSPORT_IN_PROCESS) or job_runner.TRANSPORT_IN_PROCESS)
    label = transport_label(transport)
    ui.caption(f"Task ID: {task_id} | Transport: {label}")

    while True:
        try:
            task = fetch_status(task_id, transport)
        except Exception as exc:
            logger.error("failed to query job status: {}", exc)
            ui.error(f"{query_failure_prefix}: {exc}")
            return False

        progress = int(task.get("progress", 0) or 0)
        status = str(task.get("status", "processing") or "processing")
        message = str(task.get("message", "") or "")

        progress_bar.progress(max(0.0, min(progress, 100)) / 100.0)
        status_suffix = f" - {message}" if message and message != "queued" else ""
        status_text.text(f"{processing_prefix} {progress}% ({label}){status_suffix}")

        if status == "complete":
            result = extract_result(task) if extract_result else dict(task)
            if extract_result and not result:
                ui.error(empty_result_error)
                return False

            if on_complete:
                on_complete(result)
            progress_bar.progress(1.0)
            if completion_status_text:
                status_text.text(completion_status_text)
            if completion_success_text:
                ui.success(completion_success_text)
            return True

        if status == "failed":
            error_message = str(task.get("error", "") or task.get("message", "") or "Unknown error")
            ui.error(f"{failure_prefix}: {error_message}")
            return False

        time.sleep(poll_interval_seconds)
