from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.utils import workspace


def _history_dir() -> str:
    return workspace.state_dir("jobs", create=True)


def _history_path() -> str:
    return os.path.join(_history_dir(), "history.json")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_data() -> Dict[str, List[Dict]]:
    path = _history_path()
    if not os.path.exists(path):
        return {"items": []}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        payload = {"items": []}
    if not isinstance(payload, dict):
        return {"items": []}
    items = payload.get("items", [])
    return {"items": list(items) if isinstance(items, list) else []}


def _write_data(data: Dict[str, List[Dict]]) -> None:
    with open(_history_path(), "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def record_job(
    *,
    owner: str,
    task_id: str,
    job_type: str,
    task_dir: str,
    status: str = "processing",
    progress: int = 0,
    message: str = "",
    error: str = "",
    created_at: Optional[str] = None,
) -> Dict:
    payload = _read_data()
    created_at = created_at or _now_iso()
    item = {
        "owner": owner,
        "task_id": task_id,
        "job_type": job_type,
        "task_dir": task_dir,
        "status": status,
        "progress": int(progress),
        "message": message,
        "error": error,
        "created_at": created_at,
        "updated_at": created_at,
    }
    payload["items"].insert(0, item)
    _write_data(payload)
    return item


def update_job(
    *,
    task_id: str,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[Dict]:
    payload = _read_data()
    updated = None
    for item in payload["items"]:
        if item.get("task_id") != task_id:
            continue
        if status is not None:
            item["status"] = status
        if progress is not None:
            item["progress"] = int(progress)
        if message is not None:
            item["message"] = message
        if error is not None:
            item["error"] = error
        item["updated_at"] = _now_iso()
        updated = item
        break
    if updated is not None:
        _write_data(payload)
    return updated


def list_jobs(owner: str, limit: int = 60) -> List[Dict]:
    payload = _read_data()
    items = [item for item in payload["items"] if item.get("owner") == owner]
    return items[: max(1, limit)]
