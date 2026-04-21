from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from loguru import logger

from app.models import const
from app.models.schema import VideoClipParams
from app.services import state as sm
from app.services import task
from app.services.highlight_edit_pipeline import run_highlight_edit_pipeline
from app.services.subtitle_first_pipeline import run_subtitle_first_pipeline
from app.utils import utils


_JOB_THREADS: Dict[str, threading.Thread] = {}
_JOB_THREADS_LOCK = threading.Lock()


def _task_status_name(state_value: int) -> str:
    if state_value == const.TASK_STATE_COMPLETE:
        return "complete"
    if state_value == const.TASK_STATE_FAILED:
        return "failed"
    return "processing"


def _cleanup_dead_threads() -> None:
    with _JOB_THREADS_LOCK:
        dead_ids = [task_id for task_id, thread in _JOB_THREADS.items() if not thread.is_alive()]
        for task_id in dead_ids:
            _JOB_THREADS.pop(task_id, None)


def _track_thread(task_id: str, thread: threading.Thread) -> None:
    _cleanup_dead_threads()
    with _JOB_THREADS_LOCK:
        _JOB_THREADS[task_id] = thread


def _update_processing_state(task_id: str, job_type: str, progress: int, message: str = "", **extra: Any) -> None:
    existing = sm.state.get_task(task_id) or {}
    payload = dict(existing)
    payload.update(extra)
    sm.state.update_task(
        task_id,
        state=const.TASK_STATE_PROCESSING,
        progress=int(progress),
        job_type=job_type,
        status="processing",
        message=message or str(payload.get("message", "") or ""),
        task_dir=str(payload.get("task_dir", utils.task_dir(task_id))),
        **{k: v for k, v in payload.items() if k not in {"state", "progress", "status", "message", "job_type"}},
    )


def _mark_job_failed(task_id: str, job_type: str, err: Exception, **extra: Any) -> None:
    logger.exception(f"local {job_type} job failed: {task_id}")
    existing = sm.state.get_task(task_id) or {}
    payload = dict(existing)
    payload.update(extra)
    task_dir = str(payload.get("task_dir", utils.task_dir(task_id)))
    sm.state.update_task(
        task_id,
        state=const.TASK_STATE_FAILED,
        progress=int(existing.get("progress", 0) or 0),
        job_type=job_type,
        status="failed",
        message=str(err),
        error=str(err),
        task_dir=task_dir,
        **{k: v for k, v in payload.items() if k not in {"state", "progress", "status", "message", "error", "job_type", "task_dir"}},
    )


def _mark_job_complete(task_id: str, job_type: str, *, message: str = "complete", **extra: Any) -> None:
    task_dir = str((extra.get("task_dir") or utils.task_dir(task_id)))
    # 构建 payload，排除已单独处理的字段
    payload = {
        k: v
        for k, v in extra.items()
        if k not in {"state", "progress", "status", "message", "job_type", "task_dir"}
    }
    sm.state.update_task(
        task_id,
        state=const.TASK_STATE_COMPLETE,
        progress=100,
        job_type=job_type,
        status="complete",
        message=message,
        task_dir=task_dir,
        **payload,
    )


def _run_threaded_job(
    task_id: str,
    *,
    job_type: str,
    runner: Callable[[], Dict[str, Any]],
) -> None:
    try:
        result = runner() or {}
        _mark_job_complete(task_id, job_type, result=result, **result)
    except Exception as err:
        _mark_job_failed(task_id, job_type, err)
    finally:
        _cleanup_dead_threads()


def _start_job_thread(
    *,
    task_id: str,
    job_type: str,
    runner: Callable[[], Dict[str, Any]],
) -> str:
    task_dir = utils.task_dir(task_id)
    sm.state.update_task(
        task_id,
        state=const.TASK_STATE_PROCESSING,
        progress=0,
        job_type=job_type,
        status="processing",
        message="queued",
        task_dir=task_dir,
    )

    thread = threading.Thread(
        target=_run_threaded_job,
        kwargs={
            "task_id": task_id,
            "job_type": job_type,
            "runner": runner,
        },
        daemon=True,
        name=f"narrato-{job_type}-{task_id}",
    )
    thread.start()
    _track_thread(task_id, thread)
    logger.info(f"local {job_type} job started: {task_id}")
    return task_id


def _run_video_job(task_id: str, params: VideoClipParams) -> Dict[str, Any]:
    task.start_subclip_unified(task_id=task_id, params=params)
    return sm.state.get_task(task_id) or {}


def start_local_video_job(params: VideoClipParams, task_id: str = "") -> str:
    task_id = str(task_id or uuid4())
    return _start_job_thread(
        task_id=task_id,
        job_type="video",
        runner=lambda: _run_video_job(task_id, params),
    )


def start_local_highlight_script_job(request: Dict[str, Any], task_id: str = "") -> str:
    task_id = str(task_id or uuid4())

    def runner() -> Dict[str, Any]:
        def progress_callback(progress: int, message: str = "") -> None:
            _update_processing_state(task_id, "highlight_script", int(progress), message)

        result = run_highlight_edit_pipeline(
            video_path=str(request.get("video_path", "") or ""),
            mode=str(request.get("mode", "highlight_recut") or "highlight_recut"),
            target_duration_seconds=int(request.get("target_duration_seconds", 480) or 480),
            movie_title=str(request.get("movie_title", "") or ""),
            highlight_profile=str(request.get("highlight_profile", "auto") or "auto"),
            subtitle_path=str(request.get("subtitle_path", "") or ""),
            narration_text=str(request.get("narration_text", "") or ""),
            narration_audio_path=str(request.get("narration_audio_path", "") or ""),
            prefer_raw_audio=bool(request.get("prefer_raw_audio", True)),
            visual_mode=str(request.get("visual_mode", "auto") or "auto"),
            regenerate_subtitle=bool(request.get("regenerate_subtitle", False)),
            subtitle_backend=str(request.get("subtitle_backend", "") or ""),
            progress_callback=progress_callback,
        )
        if not result.get("success"):
            raise RuntimeError(str(result.get("error", "highlight_script_failed")))
        return result

    return _start_job_thread(
        task_id=task_id,
        job_type="highlight_script",
        runner=runner,
    )


def start_local_movie_story_script_job(request: Dict[str, Any], task_id: str = "") -> str:
    task_id = str(task_id or uuid4())

    def runner() -> Dict[str, Any]:
        def progress_callback(progress: int, message: str = "") -> None:
            _update_processing_state(task_id, "movie_story_script", int(progress), message)

        regenerate_subtitle = str(request.get("cache_mode", "clear_and_regenerate") or "").strip() == "clear_and_regenerate"
        result = run_subtitle_first_pipeline(
            video_path=str(request.get("video_path", "") or ""),
            subtitle_path=str(request.get("subtitle_path", "") or ""),
            text_api_key=str(request.get("text_api_key", "") or ""),
            text_base_url=str(request.get("text_base_url", "") or ""),
            text_model=str(request.get("text_model", "") or ""),
            style=str(request.get("narration_style", "general") or "general"),
            generation_mode=str(request.get("generation_mode", "balanced") or "balanced"),
            visual_mode=str(request.get("visual_mode", "auto") or "auto"),
            scene_overrides={
                "target_duration_minutes": int(request.get("target_duration_minutes", 8) or 8),
                "narrative_strategy": str(request.get("narrative_strategy", "chronological") or "chronological"),
                "accuracy_priority": str(request.get("accuracy_priority", "high") or "high"),
                "highlight_only": bool(request.get("highlight_only", False)),
                "highlight_selectivity": str(request.get("highlight_selectivity", "balanced") or "balanced"),
                "video_title": str(request.get("video_theme", "") or ""),
                "short_name": str(request.get("video_theme", "") or ""),
                "temperature": float(request.get("temperature", 0.7) or 0.7),
                "prologue_strategy": str(request.get("prologue_strategy", "speech_first") or "speech_first"),
                "manual_prologue_end_time": str(request.get("manual_prologue_end_time", "") or ""),
            },
            progress_callback=progress_callback,
            asr_backend=str(request.get("asr_backend", "") or ""),
            regenerate_subtitle=regenerate_subtitle,
        )
        if not result.get("success"):
            raise RuntimeError(str(result.get("error", "movie_story_script_failed")))
        return result

    return _start_job_thread(
        task_id=task_id,
        job_type="movie_story_script",
        runner=runner,
    )


def get_task_snapshot(task_id: str) -> Optional[Dict]:
    task_data = sm.state.get_task(task_id)
    if not task_data:
        return None

    snapshot = dict(task_data)
    snapshot["task_id"] = task_id
    snapshot.setdefault("job_type", "video")
    snapshot.setdefault("task_dir", utils.task_dir(task_id))
    snapshot["status"] = _task_status_name(int(snapshot.get("state", const.TASK_STATE_PROCESSING) or 0))

    with _JOB_THREADS_LOCK:
        thread = _JOB_THREADS.get(task_id)
    snapshot["is_running"] = bool(thread and thread.is_alive())
    return snapshot
