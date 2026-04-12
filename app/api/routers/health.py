from __future__ import annotations

from fastapi import APIRouter

from app.config import config


router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck():
    return {
        "ok": True,
        "service": config.project_name,
        "version": config.project_version,
    }
