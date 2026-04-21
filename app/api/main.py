from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import auth, health, jobs, system, uploads
from app.api.route_registry import register_workbench_routes
from app.config import config
from app.utils import utils


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

    app.include_router(health, prefix="/api/v1")
    app.include_router(system, prefix="/api/v1")
    app.include_router(jobs, prefix="/api/v1")
    app.include_router(auth, prefix="/api/v1")
    app.include_router(uploads, prefix="/api/v1")
    
    # 注册 workbench 相关路由
    register_workbench_routes(app)
    
    # 挂载上传文件目录为静态文件服务
    upload_root = Path(utils.workspace_dir()) / "frontend_uploads"
    if upload_root.exists():
        app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")

    # 前端运行时配置接口（供 /api/config 使用）
    @app.get("/api/config")
    def runtime_config():
        host = config.app.get("local_api_host", "127.0.0.1")
        port = config.app.get("local_api_port", 18000)
        return {
            "API_BASE_URL": f"http://{host}:{port}",
            "project_name": config.project_name,
            "project_version": config.project_version,
        }

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
