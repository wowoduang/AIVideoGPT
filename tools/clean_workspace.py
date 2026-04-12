from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

from app.utils import workspace


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _allowed_roots(*, workspace_root: str = "") -> List[Path]:
    resolved_workspace_root = Path(workspace.storage_dir(workspace_root=workspace_root)).resolve()
    return [ROOT.resolve(), resolved_workspace_root]


def _dedupe_existing(paths: Iterable[str]) -> List[Path]:
    unique: List[Path] = []
    seen = set()
    for raw in paths:
        candidate = Path(raw).resolve()
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _validate_targets(paths: Sequence[Path], *, workspace_root: str = "") -> List[Path]:
    allowed = _allowed_roots(workspace_root=workspace_root)
    safe: List[Path] = []
    for path in paths:
        if any(_is_within(base, path) for base in allowed):
            safe.append(path)
    return safe


def _remove_path(path: Path, *, apply: bool) -> str:
    if not path.exists():
        return "missing"
    if not apply:
        return "planned"

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return "removed"


def _build_targets(args: argparse.Namespace) -> List[Path]:
    groups = workspace.cleanup_target_groups(
        include_tasks=args.include_tasks,
        include_runtime=args.include_runtime,
        include_state=args.include_state,
        include_repo_junk=True,
        include_vendor_runtime=args.include_vendor_runtime,
        include_model_vcs=args.include_model_vcs,
        workspace_root=args.workspace_root,
    )
    ordered: List[str] = []
    for name in ("temp", "cache", "repo_junk", "model_vcs", "runtime", "state", "tasks", "vendor_runtime"):
        ordered.extend(groups.get(name, []))
    return _validate_targets(_dedupe_existing(ordered), workspace_root=args.workspace_root)


def _print_targets(paths: Sequence[Path], *, apply: bool, workspace_root: str = "") -> None:
    mode = "APPLY" if apply else "DRY RUN"
    print(f"[clean-workspace] mode={mode}")
    print(f"workspace_root={workspace.storage_dir(workspace_root=workspace_root)}")
    if not paths:
        print("No cleanup targets found.")
        return
    for path in paths:
        print(f"- {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean external workspace caches, runtime debris, and optional legacy repo junk.")
    parser.add_argument("--apply", action="store_true", help="Actually delete the resolved targets.")
    parser.add_argument(
        "--workspace-root",
        default="",
        help="Override the workspace root for this run, for example D:/AIVideoGPT-workspace.",
    )
    parser.add_argument("--include-runtime", action="store_true", help="Also clear workspace/runtime.")
    parser.add_argument("--include-state", action="store_true", help="Also clear workspace/state.")
    parser.add_argument("--include-tasks", action="store_true", help="Also clear workspace/tasks.")
    parser.add_argument(
        "--include-vendor-runtime",
        action="store_true",
        help="Also clear vendored third-party runtime junk such as .venv/AppData/work-dir.",
    )
    parser.add_argument(
        "--include-model-vcs",
        action="store_true",
        help="Also clear cloned model VCS metadata such as .git/.gitattributes under app/models or workspace/models.",
    )
    args = parser.parse_args()

    targets = _build_targets(args)
    _print_targets(targets, apply=args.apply, workspace_root=args.workspace_root)
    if not targets:
        return 0

    results = {"planned": 0, "removed": 0, "missing": 0}
    for path in targets:
        status = _remove_path(path, apply=args.apply)
        results[status] = results.get(status, 0) + 1
        print(f"[{status}] {path}")

    print(
        "Summary: "
        f"planned={results.get('planned', 0)} "
        f"removed={results.get('removed', 0)} "
        f"missing={results.get('missing', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
