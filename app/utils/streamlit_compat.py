from __future__ import annotations

import os
from types import ModuleType
from typing import Callable


def collect_module_paths_without_side_effects(
    module: ModuleType,
    is_valid_path: Callable[[object], bool],
) -> set[str]:
    """Collect module paths without touching module __getattr__ hooks.

    Streamlit's source watcher probes ``__path__`` with ``hasattr`` which can
    trigger side effects on dynamic modules such as ``torch.classes``.
    Reading directly from ``module.__dict__`` avoids that code path.
    """

    module_dict = getattr(module, "__dict__", {}) or {}
    potential_paths: list[object] = []

    file_path = module_dict.get("__file__")
    if file_path:
        potential_paths.append(file_path)

    spec = module_dict.get("__spec__")
    origin = getattr(spec, "origin", None) if spec is not None else None
    if origin:
        potential_paths.append(origin)

    namespace_path = module_dict.get("__path__")
    if type(namespace_path).__name__ == "_NamespacePath":
        raw_paths = getattr(namespace_path, "_path", None)
        if raw_paths:
            try:
                potential_paths.extend(list(raw_paths))
            except Exception:
                pass

    resolved: set[str] = set()
    for candidate in potential_paths:
        try:
            if is_valid_path(candidate):
                resolved.add(os.path.realpath(str(candidate)))
        except Exception:
            continue
    return resolved


def patch_streamlit_torch_watcher() -> bool:
    """Patch Streamlit watcher to avoid probing torch.classes dynamically."""

    try:
        from streamlit.watcher import local_sources_watcher as lsw
    except Exception:
        return False

    if getattr(lsw, "_narrato_safe_module_paths_patch", False):
        return True

    def _patched_get_module_paths(module: ModuleType) -> set[str]:
        return collect_module_paths_without_side_effects(module, lsw._is_valid_path)

    lsw.get_module_paths = _patched_get_module_paths
    lsw._narrato_safe_module_paths_patch = True
    return True
