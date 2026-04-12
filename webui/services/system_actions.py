from __future__ import annotations

import os
import shutil
from typing import List, Tuple

from loguru import logger

from app.utils import workspace


def get_workspace_layout_rows() -> List[Tuple[str, str]]:
    layout = workspace.workspace_layout_paths(create=False)
    return [(relative_path, layout[relative_path]) for relative_path in workspace.WORKSPACE_LAYOUT_DIRS]


def clear_directory(dir_path: str) -> Tuple[str, str]:
    if not os.path.exists(dir_path):
        return "warning", "Directory does not exist"

    try:
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as exc:
                logger.error("failed to delete {}: {}", item_path, exc)
        logger.info("cleared directory: {}", dir_path)
        return "success", "Directory cleared"
    except Exception as exc:
        logger.error("failed to clear directory {}: {}", dir_path, exc)
        return "error", f"Failed to clear directory: {exc}"
