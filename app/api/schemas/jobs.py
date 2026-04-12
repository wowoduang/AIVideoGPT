from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.models.schema import VideoClipParams


class VideoJobCreateRequest(BaseModel):
    params: VideoClipParams
    task_id: str = Field(default="", description="Optional custom task id for local orchestration.")


class HighlightScriptRequest(BaseModel):
    video_path: str
    mode: str = "highlight_recut"
    target_duration_seconds: int = 480
    movie_title: str = ""
    highlight_profile: str = "auto"
    subtitle_path: str = ""
    narration_text: str = ""
    narration_audio_path: str = ""
    prefer_raw_audio: bool = True
    visual_mode: str = "auto"
    regenerate_subtitle: bool = False
    subtitle_backend: str = ""


class HighlightJobCreateRequest(BaseModel):
    request: HighlightScriptRequest
    task_id: str = Field(default="", description="Optional custom task id for local orchestration.")


class MovieStoryScriptRequest(BaseModel):
    video_path: str
    subtitle_path: str = ""
    video_theme: str = ""
    temperature: float = 0.7
    text_api_key: str = ""
    text_model: str = ""
    text_base_url: str = ""
    narration_style: str = "general"
    generation_mode: str = "balanced"
    visual_mode: str = "auto"
    target_duration_minutes: int = 8
    narrative_strategy: str = "chronological"
    accuracy_priority: str = "high"
    highlight_only: bool = False
    highlight_selectivity: str = "balanced"
    asr_backend: str = ""
    cache_mode: str = "clear_and_regenerate"
    prologue_strategy: str = "speech_first"
    manual_prologue_end_time: str = ""


class MovieStoryJobCreateRequest(BaseModel):
    request: MovieStoryScriptRequest
    task_id: str = Field(default="", description="Optional custom task id for local orchestration.")


class JobAcceptedResponse(BaseModel):
    task_id: str
    job_type: str
    status: str
    progress: int
    task_dir: str


class JobStatusResponse(BaseModel):
    task_id: str
    job_type: str
    status: str
    state: int
    progress: int
    message: str = ""
    error: str = ""
    task_dir: str
    videos: List[str] = Field(default_factory=list)
    combined_videos: List[str] = Field(default_factory=list)
    is_running: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceInfoResponse(BaseModel):
    project_root: str
    workspace_root: str
    config_file: str
    project_version: str
    layout: Dict[str, str]
    task_root: str
