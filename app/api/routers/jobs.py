from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.jobs import (
    HighlightJobCreateRequest,
    JobAcceptedResponse,
    JobStatusResponse,
    MovieStoryJobCreateRequest,
    VideoJobCreateRequest,
)
from app.services.local_job_runner import (
    get_task_snapshot,
    start_local_highlight_script_job,
    start_local_movie_story_script_job,
    start_local_video_job,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _accepted_response(task_id: str) -> JobAcceptedResponse:
    snapshot = get_task_snapshot(task_id)
    if not snapshot:
        raise HTTPException(status_code=500, detail="job_created_but_state_missing")
    return JobAcceptedResponse(
        task_id=task_id,
        job_type=str(snapshot.get("job_type", "video")),
        status=str(snapshot.get("status", "processing")),
        progress=int(snapshot.get("progress", 0) or 0),
        task_dir=str(snapshot.get("task_dir", "")),
    )


@router.post("/video", response_model=JobAcceptedResponse, status_code=202)
def create_video_job(payload: VideoJobCreateRequest):
    task_id = start_local_video_job(params=payload.params, task_id=payload.task_id)
    return _accepted_response(task_id)


@router.post("/highlight-script", response_model=JobAcceptedResponse, status_code=202)
def create_highlight_script_job(payload: HighlightJobCreateRequest):
    task_id = start_local_highlight_script_job(request=payload.request.model_dump(), task_id=payload.task_id)
    return _accepted_response(task_id)


@router.post("/movie-story-script", response_model=JobAcceptedResponse, status_code=202)
def create_movie_story_script_job(payload: MovieStoryJobCreateRequest):
    task_id = start_local_movie_story_script_job(request=payload.request.model_dump(), task_id=payload.task_id)
    return _accepted_response(task_id)


@router.get("/{task_id}", response_model=JobStatusResponse)
def get_job_status(task_id: str):
    snapshot = get_task_snapshot(task_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="task_not_found")

    payload = dict(snapshot)
    return JobStatusResponse(
        task_id=task_id,
        job_type=str(payload.pop("job_type", "video")),
        status=str(payload.pop("status", "processing")),
        state=int(payload.pop("state", 0) or 0),
        progress=int(payload.pop("progress", 0) or 0),
        message=str(payload.get("message", "") or ""),
        error=str(payload.get("error", "") or ""),
        task_dir=str(payload.get("task_dir", "") or ""),
        videos=list(payload.get("videos", []) or []),
        combined_videos=list(payload.get("combined_videos", []) or []),
        is_running=bool(payload.pop("is_running", False)),
        payload=payload,
    )
