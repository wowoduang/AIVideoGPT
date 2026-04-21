from pathlib import Path

from app.repositories.workbench_state_repository import WorkbenchStateRepository
from app.schemas.workbench_state import TaskLogItem


def test_script_bindings_roundtrip(tmp_path: Path) -> None:
    repo = WorkbenchStateRepository(base_dir=tmp_path)
    repo.save_script_bindings({0: "clip-001", 1: "clip-002"})
    assert repo.load_script_bindings() == {0: "clip-001", 1: "clip-002"}


def test_task_logs_append_and_load(tmp_path: Path) -> None:
    repo = WorkbenchStateRepository(base_dir=tmp_path)
    repo.append_task_log(
        TaskLogItem(
            id="log-1",
            level="info",
            time="12:00:00",
            message="test log",
        )
    )
    loaded = repo.load_task_logs()
    assert len(loaded) == 1
    assert loaded[0].message == "test log"
