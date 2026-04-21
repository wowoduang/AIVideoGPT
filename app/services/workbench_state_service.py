from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.workbench_state_repository import WorkbenchStateRepository
from app.schemas.workbench_state import LogLevel, TaskLogItem


class WorkbenchStateService:
    def __init__(self, repository: WorkbenchStateRepository | None = None) -> None:
        self.repository = repository or WorkbenchStateRepository()

    def get_script_bindings(self) -> dict[int, str]:
        return self.repository.load_script_bindings()

    def save_script_bindings(self, bindings: dict[int, str]) -> None:
        self.repository.save_script_bindings(bindings)
        self._append_log("info", "脚本段落绑定已保存到服务端状态仓库。")

    def get_task_logs(self) -> list[TaskLogItem]:
        return self.repository.load_task_logs()

    def apply_repair_action(self, title: str) -> str:
        self._append_log("info", f"已接收导出修复动作：{title}")
        return f"修复动作已入队：{title}"

    def apply_timeline_fix(self, track_name: str) -> str:
        self._append_log("warn", f"已触发时间线智能修复：{track_name}")
        return f"时间线修复任务已入队：{track_name}"

    def _append_log(self, level: LogLevel, message: str) -> None:
        item = TaskLogItem(
            id=str(uuid4()),
            level=level,
            time=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            message=message,
        )
        self.repository.append_task_log(item)
