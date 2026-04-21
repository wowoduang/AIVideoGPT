from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class ScriptBindingsPayload(BaseModel):
    bindings: Dict[int, str] = Field(default_factory=dict)


class RepairActionPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class TimelineFixPayload(BaseModel):
    track_name: str = Field(..., min_length=1, max_length=100)


LogLevel = Literal["info", "warn", "error"]


class TaskLogItem(BaseModel):
    id: str
    level: LogLevel
    time: str
    message: str


class TaskLogResponse(BaseModel):
    items: List[TaskLogItem] = Field(default_factory=list)


class ApiMessage(BaseModel):
    success: bool = True
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
