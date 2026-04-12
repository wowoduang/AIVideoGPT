from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, Optional

from loguru import logger

from app.config import config
from app.utils import workspace

try:
    import winreg  # type: ignore
except ImportError:  # pragma: no cover - non-Windows runtime
    winreg = None


_BACKEND_ALIASES = {
    "videocaptioner": "videocaptioner_shell",
    "videocaptioner-shell": "videocaptioner_shell",
    "videocaptioner_shell": "videocaptioner_shell",
    "videolingo": "videolingo_shell",
    "videolingo-shell": "videolingo_shell",
    "videolingo_shell": "videolingo_shell",
}

_BACKEND_COMMAND_KEYS = {
    "videocaptioner_shell": ("videocaptioner_command", "NARRATO_VIDEOCAPTIONER_COMMAND"),
    "videolingo_shell": ("videolingo_command", "NARRATO_VIDEOLINGO_COMMAND"),
}


def _config_root_dir() -> str:
    candidate = getattr(config, "root_dir", "")
    if isinstance(candidate, str) and candidate.strip():
        return candidate
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _config_workspace_root() -> str:
    app_cfg = getattr(config, "app", {})
    if isinstance(app_cfg, dict):
        return str(app_cfg.get("workspace_root", "") or "")
    return ""


def normalize_external_backend(backend: str) -> str:
    return _BACKEND_ALIASES.get(str(backend or "").strip().lower(), "")


def is_external_backend(backend: str) -> bool:
    return bool(normalize_external_backend(backend))


def _command_template(backend: str) -> str:
    normalized = normalize_external_backend(backend)
    if not normalized:
        return ""
    config_key, env_key = _BACKEND_COMMAND_KEYS[normalized]
    return str(os.getenv(env_key) or config.whisper.get(config_key, "") or "").strip()


def _quote(value: str) -> str:
    return '"' + str(value or "").replace('"', '\\"') + '"'


def _build_context(video_file: str, audio_file: str, subtitle_file: str) -> Dict[str, str]:
    subtitle_root, _ = os.path.splitext(subtitle_file)
    clean_subtitle_file = f"{subtitle_root}_clean.srt"
    raw_subtitle_file = f"{subtitle_root}_raw.srt"
    segments_json_file = f"{subtitle_root}_segments.json"
    values = {
        "video_file": os.path.abspath(video_file),
        "audio_file": os.path.abspath(audio_file),
        "subtitle_file": os.path.abspath(subtitle_file),
        "clean_subtitle_file": os.path.abspath(clean_subtitle_file),
        "raw_subtitle_file": os.path.abspath(raw_subtitle_file),
        "segments_json_file": os.path.abspath(segments_json_file),
        "subtitle_dir": os.path.abspath(os.path.dirname(subtitle_file)),
        "subtitle_root": os.path.abspath(subtitle_root),
        "video_stem": os.path.splitext(os.path.basename(video_file))[0],
    }
    quoted = {f"{key}_q": _quote(value) for key, value in values.items()}
    values.update(quoted)
    return values


def _find_repo_candidate(name: str) -> str:
    key_base = str(name or "").strip().lower()
    root_dir = _config_root_dir()
    raw_candidates = [
        str(config.whisper.get(f"{key_base}_repo_dir", "") or "").strip(),
        str(os.getenv(f"NARRATO_{key_base.upper()}_REPO_DIR") or "").strip(),
        workspace.vendor_dir(name, root_dir=root_dir),
        os.path.join(os.path.dirname(root_dir), name),
        os.path.join(os.path.dirname(root_dir), name.replace("Captioner", "captioner")),
    ]
    for candidate in raw_candidates:
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)
    return ""


def _read_windows_registry_path(scope) -> str:
    if winreg is None:
        return ""
    try:
        subkey = r"Environment" if scope == winreg.HKEY_CURRENT_USER else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        with winreg.OpenKey(scope, subkey) as key:
            value, _ = winreg.QueryValueEx(key, "Path")
            return str(value or "").strip()
    except Exception:
        return ""


def _augment_env_with_windows_paths(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    merged = dict(env or os.environ)
    path_parts = []
    seen = set()

    def _append_path(raw: str):
        candidate = str(raw or "").strip().strip('"')
        if not candidate:
            return
        if candidate.lower().endswith("ffmpeg.exe"):
            candidate = os.path.dirname(candidate)
        if not candidate:
            return
        candidate = os.path.abspath(candidate)
        if candidate not in seen and os.path.isdir(candidate):
            seen.add(candidate)
            path_parts.append(candidate)

    for chunk in str(merged.get("PATH", "") or "").split(os.pathsep):
        _append_path(chunk)
    if winreg is not None:
        for chunk in _read_windows_registry_path(winreg.HKEY_CURRENT_USER).split(";"):
            _append_path(chunk)
        for chunk in _read_windows_registry_path(winreg.HKEY_LOCAL_MACHINE).split(";"):
            _append_path(chunk)
    _append_path(config.app.get("ffmpeg_path", ""))

    merged["PATH"] = os.pathsep.join(path_parts)
    return merged


def _clear_proxy_env(env: Dict[str, str]) -> Dict[str, str]:
    cleaned = dict(env)
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        cleaned.pop(key, None)
    return cleaned


def _videocaptioner_runtime_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    merged = _clear_proxy_env(_augment_env_with_windows_paths(env))
    root_dir = _config_root_dir()
    runtime_root = workspace.third_party_runtime_dir(
        "videocaptioner",
        create=True,
        root_dir=root_dir,
        workspace_root=_config_workspace_root(),
    )
    local_appdata = os.path.join(runtime_root, "LocalAppData")
    roaming_appdata = os.path.join(runtime_root, "AppData")
    os.makedirs(local_appdata, exist_ok=True)
    os.makedirs(roaming_appdata, exist_ok=True)
    merged["LOCALAPPDATA"] = local_appdata
    merged["APPDATA"] = roaming_appdata
    return merged


def _videocaptioner_command_prefix() -> tuple[list[str], dict[str, str] | None, str | None]:
    repo_dir = _find_repo_candidate("VideoCaptioner")
    if repo_dir:
        env = _videocaptioner_runtime_env()
        python_candidates = []
        root_dir = _config_root_dir()
        external_runtime_root = workspace.third_party_runtime_dir(
            "videocaptioner",
            root_dir=root_dir,
            workspace_root=_config_workspace_root(),
        )
        if os.name == "nt":
            for venv_name in (".runtime_venv", ".venv"):
                python_candidates.append(os.path.join(external_runtime_root, venv_name, "Scripts", "python.exe"))
            for venv_name in (".runtime_venv", ".venv"):
                python_candidates.append(os.path.join(repo_dir, venv_name, "Scripts", "python.exe"))
        else:
            for venv_name in (".runtime_venv", ".venv"):
                python_candidates.append(os.path.join(external_runtime_root, venv_name, "bin", "python"))
            for venv_name in (".runtime_venv", ".venv"):
                python_candidates.append(os.path.join(repo_dir, venv_name, "bin", "python"))
        pythonpath_parts = []
        src_dir = os.path.join(repo_dir, "src")
        if os.path.isdir(src_dir):
            pythonpath_parts.append(src_dir)
        pythonpath_parts.append(repo_dir)
        if env.get("PYTHONPATH"):
            pythonpath_parts.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
        for embedded_python in python_candidates:
            if os.path.isfile(embedded_python):
                return [embedded_python, "-m", "videocaptioner"], env, repo_dir
        return [sys.executable, "-m", "videocaptioner"], env, repo_dir

    cli = shutil.which("videocaptioner")
    if cli:
        return [cli], _videocaptioner_runtime_env(), None

    if importlib.util.find_spec("videocaptioner") is not None:
        return [sys.executable, "-m", "videocaptioner"], _videocaptioner_runtime_env(), None

    return [], None, None


def _run_command_shell(command: str, *, normalized: str) -> Optional[str]:
    logger.info("调用外部字幕后端 shell: backend={}, command={}", normalized, command)
    proc = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_augment_env_with_windows_paths(),
    )
    if proc.returncode != 0:
        logger.warning(
            "外部字幕后端执行失败: backend={}, code={}, stdout={}, stderr={}",
            normalized,
            proc.returncode,
            (proc.stdout or "").strip()[:800],
            (proc.stderr or "").strip()[:1200],
        )
        return None
    return (proc.stdout or "").strip()


def _run_videocaptioner(video_file: str, subtitle_file: str) -> Optional[str]:
    command_prefix, env, cwd = _videocaptioner_command_prefix()
    if not command_prefix:
        logger.warning(
            "未找到 VideoCaptioner CLI。可选做法：1) pip install videocaptioner 2) 配置 whisper.videocaptioner_repo_dir 3) 手填 whisper.videocaptioner_command"
        )
        return None

    asr_backend = str(config.whisper.get("videocaptioner_asr", "bijian") or "bijian").strip() or "bijian"
    language = str(config.whisper.get("videocaptioner_language", "auto") or "auto").strip() or "auto"
    cmd = list(command_prefix) + [
        "transcribe",
        os.path.abspath(video_file),
        "--asr",
        asr_backend,
        "--language",
        language,
        "--format",
        "srt",
        "-o",
        os.path.abspath(subtitle_file),
        "--quiet",
    ]

    logger.info("调用 VideoCaptioner: {}", " ".join(_quote(part) for part in cmd))
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=cwd,
    )
    if proc.returncode != 0:
        stderr_text = (proc.stderr or "").strip()
        missing_module = ""
        match = re.search(r"No module named '([^']+)'", stderr_text)
        if match:
            missing_module = match.group(1)
        logger.warning(
            "VideoCaptioner 转字幕失败: code={}, stdout={}, stderr={}",
            proc.returncode,
            (proc.stdout or "").strip()[:800],
            stderr_text[:1200],
        )
        if missing_module:
            logger.warning(
                "VideoCaptioner 运行环境缺少依赖模块: {}。请同步安装 requirements.txt 后重启服务；Docker 场景下如非挂载代码目录，请重新构建镜像。",
                missing_module,
            )
        return None

    stdout = (proc.stdout or "").strip()
    candidate_paths = [os.path.abspath(subtitle_file)]
    if stdout:
        candidate_paths.extend(line.strip() for line in stdout.splitlines() if line.strip())
    for candidate in reversed(candidate_paths):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _copy_main_srt_if_needed(context: Dict[str, str]) -> Optional[str]:
    main_srt = context["subtitle_file"]
    clean_srt = context["clean_subtitle_file"]
    raw_srt = context["raw_subtitle_file"]

    if not os.path.exists(main_srt):
        if os.path.exists(clean_srt):
            os.makedirs(os.path.dirname(main_srt), exist_ok=True)
            shutil.copyfile(clean_srt, main_srt)
        elif os.path.exists(raw_srt):
            os.makedirs(os.path.dirname(main_srt), exist_ok=True)
            shutil.copyfile(raw_srt, main_srt)

    if os.path.exists(main_srt):
        return main_srt
    return None


def run_external_subtitle_backend(
    backend: str,
    *,
    video_file: str,
    audio_file: str,
    subtitle_file: str,
) -> Optional[str]:
    normalized = normalize_external_backend(backend)
    if not normalized:
        return None

    context = _build_context(video_file=video_file, audio_file=audio_file, subtitle_file=subtitle_file)
    template = _command_template(normalized)
    if normalized == "videocaptioner_shell" and not template:
        result_path = _run_videocaptioner(video_file=video_file, subtitle_file=subtitle_file)
        if result_path and os.path.isfile(result_path):
            return os.path.abspath(result_path)
        result_path = _copy_main_srt_if_needed(context)
        if result_path:
            return os.path.abspath(result_path)
        logger.warning("VideoCaptioner 未产出可用字幕文件: expected={}", context["subtitle_file"])
        return None

    template = _command_template(normalized)
    if not template:
        logger.warning(
            "外部字幕后端未配置命令模板: backend={}, expected_config_key={}",
            normalized,
            _BACKEND_COMMAND_KEYS[normalized][0],
        )
        return None

    context = _build_context(video_file=video_file, audio_file=audio_file, subtitle_file=subtitle_file)
    try:
        command = template.format(**context)
    except Exception as exc:
        logger.warning("外部字幕后端命令模板格式化失败: backend={}, error={}", normalized, exc)
        return None

    logger.info("调用外部字幕后端: backend={}, command={}", normalized, command)
    proc = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        logger.warning(
            "外部字幕后端执行失败: backend={}, code={}, stdout={}, stderr={}",
            normalized,
            proc.returncode,
            (proc.stdout or "").strip()[:800],
            (proc.stderr or "").strip()[:800],
        )
        return None

    main_srt = context["subtitle_file"]
    clean_srt = context["clean_subtitle_file"]
    raw_srt = context["raw_subtitle_file"]

    if not os.path.exists(main_srt):
        if os.path.exists(clean_srt):
            os.makedirs(os.path.dirname(main_srt), exist_ok=True)
            shutil.copyfile(clean_srt, main_srt)
        elif os.path.exists(raw_srt):
            os.makedirs(os.path.dirname(main_srt), exist_ok=True)
            shutil.copyfile(raw_srt, main_srt)

    if os.path.exists(main_srt):
        return main_srt

    logger.warning("外部字幕后端未产出可用字幕文件: backend={}, expected={}", normalized, main_srt)
    return None
