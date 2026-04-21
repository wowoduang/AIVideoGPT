from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas.jobs import WorkspaceInfoResponse
from app.config import config
from app.utils import utils
from app.utils import workspace


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/workspace", response_model=WorkspaceInfoResponse)
def get_workspace_info():
    return WorkspaceInfoResponse(
        project_root=config.root_dir,
        workspace_root=utils.workspace_dir(),
        config_file=config.config_file,
        project_version=config.project_version,
        layout=workspace.workspace_layout_paths(create=False),
        task_root=utils.task_dir(),
    )


@router.get("/config")
def get_runtime_config():
    """
    获取运行时配置（供前端使用）
    """
    host = config.app.get("local_api_host", "127.0.0.1")
    port = config.app.get("local_api_port", 18000)
    return {
        "API_BASE_URL": f"http://{host}:{port}",
        "project_name": config.project_name,
        "project_version": config.project_version,
    }
