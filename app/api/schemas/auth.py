from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=6, max_length=128)


class UserInfo(BaseModel):
    name: str
    email: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserInfo


class MeResponse(BaseModel):
    user: UserInfo


class LogoutResponse(BaseModel):
    success: bool


class JobHistoryItem(BaseModel):
    task_id: str
    job_type: str
    status: str
    progress: int
    message: str
    error: str
    task_dir: str
    created_at: str
    updated_at: str


class JobHistoryResponse(BaseModel):
    items: list[JobHistoryItem]
