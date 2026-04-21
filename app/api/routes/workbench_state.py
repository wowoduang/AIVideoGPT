from __future__ import annotations

from fastapi import APIRouter

from app.schemas.workbench_state import (
    ApiMessage,
    RepairActionPayload,
    ScriptBindingsPayload,
    TaskLogResponse,
    TimelineFixPayload,
)
from app.services.workbench_state_service import WorkbenchStateService

router = APIRouter(prefix="/api/v1/workbench", tags=["workbench-state"])
service = WorkbenchStateService()


@router.get("/state/script-bindings", response_model=ScriptBindingsPayload)
def get_script_bindings() -> ScriptBindingsPayload:
    return ScriptBindingsPayload(bindings=service.get_script_bindings())


@router.put("/state/script-bindings", response_model=ApiMessage)
def put_script_bindings(payload: ScriptBindingsPayload) -> ApiMessage:
    service.save_script_bindings(payload.bindings)
    return ApiMessage(message="脚本绑定已保存")


@router.get("/task-logs", response_model=TaskLogResponse)
def get_task_logs() -> TaskLogResponse:
    return TaskLogResponse(items=service.get_task_logs())


@router.post("/actions/repair", response_model=ApiMessage)
def post_repair_action(payload: RepairActionPayload) -> ApiMessage:
    message = service.apply_repair_action(payload.title)
    return ApiMessage(message=message)


@router.post("/actions/timeline-fix", response_model=ApiMessage)
def post_timeline_fix(payload: TimelineFixPayload) -> ApiMessage:
    message = service.apply_timeline_fix(payload.track_name)
    return ApiMessage(message=message)
