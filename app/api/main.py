from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, health, jobs, system
from app.config import config


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{config.project_name} Local API",
        version=config.project_version,
        description="Local-first API for the next-generation NarratoAI frontend.",
    )

    allow_origins = [origin.strip() for origin in str(os.getenv("NARRATO_API_CORS_ORIGINS", "")).split(",") if origin.strip()]
    allow_origin_regex = os.getenv(
        "NARRATO_API_CORS_ORIGIN_REGEX",
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")

    @app.get("/")
    def root():
        return {
            "service": config.project_name,
            "version": config.project_version,
            "docs": "/docs",
            "api_base": "/api/v1",
        }

    return app


app = create_app()
