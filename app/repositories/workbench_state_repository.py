from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.schemas.workbench_state import TaskLogItem


class WorkbenchStateRepository:
    """Simple JSON-backed repository for workbench state.

    This keeps the first backend integration lightweight and easy to replace with
    a real database later.
    """

    def __init__(self, base_dir: str | Path = "workspace/state") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.bindings_file = self.base_dir / "script_bindings.json"
        self.task_logs_file = self.base_dir / "task_logs.json"

    def load_script_bindings(self) -> Dict[int, str]:
        if not self.bindings_file.exists():
            return {}

        raw = json.loads(self.bindings_file.read_text(encoding="utf-8"))
        return {int(key): value for key, value in raw.items()}

    def save_script_bindings(self, bindings: Dict[int, str]) -> None:
        self.bindings_file.write_text(
            json.dumps(bindings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_task_logs(self) -> List[TaskLogItem]:
        if not self.task_logs_file.exists():
            return []

        raw = json.loads(self.task_logs_file.read_text(encoding="utf-8"))
        return [TaskLogItem.model_validate(item) for item in raw]

    def append_task_log(self, item: TaskLogItem) -> None:
        current = self.load_task_logs()
        current.append(item)
        self.task_logs_file.write_text(
            json.dumps([entry.model_dump() for entry in current], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
