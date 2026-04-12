from __future__ import annotations

import glob
import os
import re
from typing import Dict, List

from app.config import config


WORKSPACE_LAYOUT_DIRS = (
    "videos",
    "subtitles",
    "scripts",
    "analysis",
    "analysis/json",
    "analysis/narration_scripts",
    "analysis/drama_analysis",
    "fonts",
    "songs",
    "models",
    "temp",
    "cache",
    "runtime",
    "state",
    "tasks",
)


def _normalize_candidate(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(str(path or "").strip()))
    return os.path.abspath(expanded) if expanded else ""


def _ensure_directory(path: str, create: bool) -> str:
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def _join(base: str, sub_dir: str = "", create: bool = False) -> str:
    path = base
    if sub_dir:
        path = os.path.join(base, str(sub_dir).strip("\\/"))
    return _ensure_directory(os.path.abspath(path), create)


def _configured_workspace_root(*, root_dir: str = "", workspace_root: str = "") -> str:
    project = project_root(root_dir=root_dir)
    configured = (
        str(workspace_root or "").strip()
        or str(os.getenv("NARRATO_WORKSPACE_ROOT") or "").strip()
        or str(config.app.get("workspace_root", "") or "").strip()
    )
    if configured:
        resolved = _normalize_candidate(configured)
        if not os.path.isabs(configured):
            resolved = os.path.abspath(os.path.join(project, configured))
        return resolved
    project_parent = os.path.dirname(project)
    project_name = os.path.basename(project.rstrip("\\/")) or "AIVideoGPT"
    return os.path.join(project_parent, f"{project_name}-workspace")


def _safe_name(name: str, *, lowercase: bool = True) -> str:
    normalized = str(name or "").strip()
    normalized = normalized.lower() if lowercase else normalized
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", normalized)
    normalized = normalized.strip("._-")
    return normalized or "default"


def _expand_patterns(patterns: List[str]) -> List[str]:
    expanded: List[str] = []
    seen = set()
    for pattern in patterns:
        for candidate in glob.glob(pattern, recursive=True):
            absolute = os.path.abspath(candidate)
            if absolute not in seen:
                seen.add(absolute)
                expanded.append(absolute)
    return expanded


def project_root(*, root_dir: str = "") -> str:
    return _normalize_candidate(root_dir) or os.path.abspath(config.root_dir)


def storage_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = _configured_workspace_root(root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, sub_dir, create=create)


def workspace_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    return storage_dir(
        sub_dir=sub_dir,
        create=create,
        root_dir=root_dir,
        workspace_root=workspace_root,
    )


def cache_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("cache", sub_dir) if sub_dir else "cache", create=create)


def runtime_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("runtime", sub_dir) if sub_dir else "runtime", create=create)


def state_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("state", sub_dir) if sub_dir else "state", create=create)


def temp_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("temp", sub_dir) if sub_dir else "temp", create=create)


def task_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("tasks", sub_dir) if sub_dir else "tasks", create=create)


def model_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("models", sub_dir) if sub_dir else "models", create=create)


def analysis_dir(
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return _join(base, os.path.join("analysis", sub_dir) if sub_dir else "analysis", create=create)


def resource_dir(sub_dir: str = "", create: bool = False, *, root_dir: str = "") -> str:
    base = os.path.join(project_root(root_dir=root_dir), "resource")
    return _join(base, sub_dir, create=create)


def vendor_dir(sub_dir: str = "", create: bool = False, *, root_dir: str = "") -> str:
    base = os.path.join(project_root(root_dir=root_dir), "vendor")
    return _join(base, sub_dir, create=create)


def tools_dir(sub_dir: str = "", create: bool = False, *, root_dir: str = "") -> str:
    base = os.path.join(project_root(root_dir=root_dir), "tools")
    return _join(base, sub_dir, create=create)


def third_party_runtime_dir(
    name: str,
    sub_dir: str = "",
    create: bool = False,
    *,
    root_dir: str = "",
    workspace_root: str = "",
) -> str:
    namespace = os.path.join("third_party", _safe_name(name))
    if sub_dir:
        namespace = os.path.join(namespace, sub_dir)
    return runtime_dir(namespace, create=create, root_dir=root_dir, workspace_root=workspace_root)


def workspace_layout_paths(
    *,
    create: bool = False,
    root_dir: str = "",
    workspace_root: str = "",
) -> Dict[str, str]:
    base = storage_dir(create=create, root_dir=root_dir, workspace_root=workspace_root)
    return {
        relative: _join(base, relative, create=create)
        for relative in WORKSPACE_LAYOUT_DIRS
    }


def cleanup_target_groups(
    *,
    include_tasks: bool = False,
    include_runtime: bool = False,
    include_state: bool = False,
    include_repo_junk: bool = True,
    include_vendor_runtime: bool = False,
    include_model_vcs: bool = False,
    root_dir: str = "",
    workspace_root: str = "",
) -> Dict[str, List[str]]:
    project = project_root(root_dir=root_dir)
    vendor_root = vendor_dir(root_dir=project)
    resolved_workspace_root = storage_dir(root_dir=project, workspace_root=workspace_root)

    groups: Dict[str, List[str]] = {
        "temp": [temp_dir(root_dir=project, workspace_root=workspace_root)],
        "cache": [cache_dir(root_dir=project, workspace_root=workspace_root)],
    }
    if include_runtime:
        groups["runtime"] = [runtime_dir(root_dir=project, workspace_root=workspace_root)]
    if include_state:
        groups["state"] = [state_dir(root_dir=project, workspace_root=workspace_root)]
    if include_tasks:
        groups["tasks"] = [task_dir(root_dir=project, workspace_root=workspace_root)]
    if include_repo_junk:
        groups["repo_junk"] = _expand_patterns(
            [
                os.path.join(project, "AppData"),
                os.path.join(project, "MagicMock"),
                os.path.join(project, ".pytest_cache"),
                os.path.join(project, "pytest-cache-files-*"),
                os.path.join(project, "logs"),
            ]
        )
    if include_vendor_runtime:
        groups["vendor_runtime"] = _expand_patterns(
            [
                os.path.join(vendor_root, "**", ".venv"),
                os.path.join(vendor_root, "**", ".runtime_venv"),
                os.path.join(vendor_root, "**", "AppData"),
                os.path.join(vendor_root, "**", "work-dir"),
                os.path.join(vendor_root, "**", ".pytest_cache"),
                os.path.join(vendor_root, "**", "pytest-cache-files-*"),
                os.path.join(vendor_root, "**", "ffcache*"),
                os.path.join(vendor_root, "**", "__pycache__"),
            ]
        )
    if include_model_vcs:
        groups["model_vcs"] = _expand_patterns(
            [
                os.path.join(project, "app", "models", "*", ".git"),
                os.path.join(project, "app", "models", "*", ".gitattributes"),
                os.path.join(project, "app", "models", "*", ".gitignore"),
                os.path.join(project, "app", "models", "*", ".gitmodules"),
                os.path.join(resolved_workspace_root, "models", "*", ".git"),
                os.path.join(resolved_workspace_root, "models", "*", ".gitattributes"),
                os.path.join(resolved_workspace_root, "models", "*", ".gitignore"),
                os.path.join(resolved_workspace_root, "models", "*", ".gitmodules"),
            ]
        )

    return {name: [os.path.abspath(path) for path in paths if path] for name, paths in groups.items()}
