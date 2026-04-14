from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from app.api.schemas.auth import (
    AuthResponse,
    JobHistoryResponse,
    LoginRequest,
    LogoutResponse,
    MeResponse,
    RegisterRequest,
    UserInfo,
)
from app.services import auth_store, job_history

router = APIRouter(tags=["auth"])


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _user_info(user: auth_store.StoredUser) -> UserInfo:
    return UserInfo(name=user.name, email=user.email, created_at=user.created_at)


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_token")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="invalid_token")
    return authorization.split(" ", 1)[1].strip()


def _validate_email(value: str) -> None:
    if "@" not in value or "." not in value:
        raise HTTPException(status_code=400, detail="invalid_email")


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    _validate_email(payload.email)
    created_at = _now_iso()
    try:
        user = auth_store.register_user(
            name=payload.name,
            email=payload.email,
            password=payload.password,
            created_at=created_at,
        )
    except ValueError as exc:
        if str(exc) == "email_exists":
            raise HTTPException(status_code=409, detail="email_exists") from exc
        raise
    token = auth_store.create_session(user.email, created_at)
    return AuthResponse(token=token, user=_user_info(user))


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    _validate_email(payload.email)
    user = auth_store.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    created_at = _now_iso()
    token = auth_store.create_session(user.email, created_at)
    return AuthResponse(token=token, user=_user_info(user))


@router.get("/auth/me", response_model=MeResponse)
def me(authorization: Optional[str] = Header(default=None)) -> MeResponse:
    token = _extract_token(authorization)
    user = auth_store.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_token")
    auth_store.touch_session(token, _now_iso())
    return MeResponse(user=_user_info(user))


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(authorization: Optional[str] = Header(default=None)) -> LogoutResponse:
    token = _extract_token(authorization)
    auth_store.revoke_token(token)
    return LogoutResponse(success=True)


@router.get("/auth/jobs", response_model=JobHistoryResponse)
def list_jobs(authorization: Optional[str] = Header(default=None)) -> JobHistoryResponse:
    token = _extract_token(authorization)
    user = auth_store.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_token")
    items = job_history.list_jobs(user.email)
    return JobHistoryResponse(items=items)
