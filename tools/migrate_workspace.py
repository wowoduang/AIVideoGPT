from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

from app.utils import workspace


MovePair = Tuple[Path, Path]


def _move_pairs(*, workspace_root: str = "") -> List[MovePair]:
    project = ROOT
    return [
        (project / "resource" / "videos", Path(workspace.storage_dir("videos", workspace_root=workspace_root))),
        (project / "resource" / "srt", Path(workspace.storage_dir("subtitles", workspace_root=workspace_root))),
        (project / "resource" / "scripts", Path(workspace.storage_dir("scripts", workspace_root=workspace_root))),
        (project / "resource" / "fonts", Path(workspace.storage_dir("fonts", workspace_root=workspace_root))),
        (project / "resource" / "songs", Path(workspace.storage_dir("songs", workspace_root=workspace_root))),
        (project / "storage" / "tasks", Path(workspace.task_dir(workspace_root=workspace_root))),
        (project / "storage" / "temp", Path(workspace.temp_dir(workspace_root=workspace_root))),
        (project / "storage" / "runtime", Path(workspace.runtime_dir(workspace_root=workspace_root))),
        (project / "storage" / "tts_cache", Path(workspace.cache_dir("tts_cache", workspace_root=workspace_root))),
        (project / "storage" / "user_settings", Path(workspace.state_dir("user_settings", workspace_root=workspace_root))),
        (project / "config.toml", Path(workspace.state_dir(workspace_root=workspace_root)) / "config.toml"),
        (project / ".streamlit" / "webui.toml", Path(workspace.state_dir(workspace_root=workspace_root)) / "webui.toml"),
        (project / "storage" / "json", Path(workspace.analysis_dir("json", workspace_root=workspace_root))),
        (project / "storage" / "drama_analysis", Path(workspace.analysis_dir("drama_analysis", workspace_root=workspace_root))),
        (project / "storage" / "narration_scripts", Path(workspace.analysis_dir("narration_scripts", workspace_root=workspace_root))),
        (Path(workspace.workspace_dir("json", workspace_root=workspace_root)), Path(workspace.analysis_dir("json", workspace_root=workspace_root))),
        (Path(workspace.workspace_dir("drama_analysis", workspace_root=workspace_root)), Path(workspace.analysis_dir("drama_analysis", workspace_root=workspace_root))),
        (Path(workspace.workspace_dir("narration_scripts", workspace_root=workspace_root)), Path(workspace.analysis_dir("narration_scripts", workspace_root=workspace_root))),
        (project / "app" / "models" / "faster-whisper-large-v2", Path(workspace.model_dir("faster-whisper-large-v2", workspace_root=workspace_root))),
        (project / "app" / "models" / "faster-whisper-large-v3", Path(workspace.model_dir("faster-whisper-large-v3", workspace_root=workspace_root))),
        (project / "app" / "models" / "bert", Path(workspace.model_dir("bert", workspace_root=workspace_root))),
    ]


def _iter_children(path: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    return list(path.iterdir())


def _merge_directory(src: Path, dst: Path, *, apply: bool) -> None:
    if not src.exists():
        return
    if not apply:
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in list(src.iterdir()):
        target = dst / child.name
        if child.is_dir():
            _merge_directory(child, target, apply=apply)
            if child.exists() and not any(child.iterdir()):
                child.rmdir()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = _dedupe_target(target)
            shutil.move(str(child), str(target))
    if src.exists() and not any(src.iterdir()):
        src.rmdir()


def _dedupe_target(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    candidate = path
    while candidate.exists():
        candidate = parent / f"{stem}__migrated_{counter}{suffix}"
        counter += 1
    return candidate


def _move_path(src: Path, dst: Path, *, apply: bool) -> str:
    if not src.exists():
        return "missing"
    if src.resolve() == dst.resolve():
        return "same"
    if not apply:
        return "planned"
    _merge_directory(src, dst, apply=True)
    return "moved"


def _print_pair(src: Path, dst: Path) -> None:
    print(f"- {src} -> {dst}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy repo-generated files into the external workspace.")
    parser.add_argument("--apply", action="store_true", help="Actually move the files instead of previewing.")
    parser.add_argument(
        "--workspace-root",
        default="",
        help="Override the workspace root for this run, for example D:/AIVideoGPT-workspace.",
    )
    args = parser.parse_args()

    pairs = _move_pairs(workspace_root=args.workspace_root)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[migrate-workspace] mode={mode}")
    print(f"workspace_root={workspace.storage_dir(workspace_root=args.workspace_root)}")
    for src, dst in pairs:
        _print_pair(src, dst)

    results = {"planned": 0, "moved": 0, "missing": 0, "same": 0}
    for src, dst in pairs:
        status = _move_path(src, dst, apply=args.apply)
        results[status] = results.get(status, 0) + 1
        print(f"[{status}] {src} -> {dst}")

    print(
        "Summary: "
        f"planned={results.get('planned', 0)} "
        f"moved={results.get('moved', 0)} "
        f"missing={results.get('missing', 0)} "
        f"same={results.get('same', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
