import os
import shutil
import socket

import toml
from loguru import logger

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
version_file = f"{root_dir}/project_version"


def get_version_from_file():
    """从project_version文件中读取版本号"""
    try:
        if os.path.isfile(version_file):
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        return "0.1.0"  # 默认版本号
    except Exception as e:
        logger.error(f"读取版本号文件失败: {str(e)}")
        return "0.1.0"  # 默认版本号
def _normalize_path(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(str(path or "").strip()))
    return os.path.abspath(expanded) if expanded else ""


def _default_workspace_root() -> str:
    configured = (
        str(os.getenv("NARRATO_WORKSPACE_ROOT") or "").strip()
        or str(os.getenv("WORKSPACE_ROOT") or "").strip()
    )
    if configured:
        resolved = _normalize_path(configured)
        if not os.path.isabs(configured):
            resolved = os.path.abspath(os.path.join(root_dir, configured))
        return resolved

    project_parent = os.path.dirname(root_dir)
    project_name = os.path.basename(root_dir.rstrip("\\/")) or "AIVideoGPT"
    return os.path.join(project_parent, f"{project_name}-workspace")


def _workspace_config_file() -> str:
    return os.path.join(_default_workspace_root(), "state", "config.toml")


def _legacy_repo_config_file() -> str:
    return os.path.join(root_dir, "config.toml")


def resolve_config_file(config_path: str = "") -> str:
    raw_path = str(config_path or os.getenv("NARRATO_CONFIG_FILE", "") or "").strip()
    if raw_path:
        resolved = _normalize_path(raw_path)
        if not os.path.isabs(raw_path):
            resolved = os.path.abspath(os.path.join(root_dir, raw_path))
        return resolved
    return _workspace_config_file()


config_file = resolve_config_file()


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _bootstrap_config_file(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path)

    if os.path.isfile(path):
        return

    legacy_file = _legacy_repo_config_file()
    if path != legacy_file and os.path.isfile(legacy_file):
        _ensure_parent_dir(path)
        shutil.copyfile(legacy_file, path)
        logger.info(f"copy repo config.toml to workspace state config: {path}")
        return

    example_file = f"{root_dir}/config.example.toml"
    if os.path.isfile(example_file):
        _ensure_parent_dir(path)
        shutil.copyfile(example_file, path)
        logger.info(f"copy config.example.toml to {path}")


def _select_config_file(config_path: str = "") -> str:
    preferred_path = resolve_config_file(config_path)
    try:
        _bootstrap_config_file(preferred_path)
    except OSError as err:
        logger.warning(f"prepare config file failed: {preferred_path}, fallback enabled: {err}")

    legacy_file = _legacy_repo_config_file()
    example_file = f"{root_dir}/config.example.toml"
    for candidate in (preferred_path, legacy_file, example_file):
        if candidate and os.path.isfile(candidate):
            return candidate
    return preferred_path


def load_config(config_path: str = ""):
    target_config_file = _select_config_file(config_path)
    globals()["config_file"] = target_config_file

    logger.info(f"load config from file: {target_config_file}")

    try:
        _config_ = toml.load(target_config_file)
    except Exception as e:
        logger.warning(f"load config failed: {str(e)}, try to load as utf-8-sig")
        try:
            with open(target_config_file, mode="r", encoding="utf-8-sig") as fp:
                _cfg_content = fp.read()
                _config_ = toml.loads(_cfg_content)
        except Exception as e2:
            logger.error(f"load config failed again: {str(e2)}")
            raise RuntimeError(f"无法加载配置文件: {target_config_file}") from e2
    return _config_


def save_config():
    candidates = []
    for candidate in (resolve_config_file(), _legacy_repo_config_file()):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    last_error = None
    for target_config_file in candidates:
        try:
            _ensure_parent_dir(target_config_file)
            with open(target_config_file, "w", encoding="utf-8") as f:
                _cfg["app"] = app
                _cfg["proxy"] = proxy
                _cfg["azure"] = azure
                _cfg["tencent"] = tencent
                _cfg["soulvoice"] = soulvoice
                _cfg["ui"] = ui
                _cfg["tts_qwen"] = tts_qwen
                _cfg["indextts2"] = indextts2
                f.write(toml.dumps(_cfg))
            globals()["config_file"] = target_config_file
            return
        except OSError as err:
            last_error = err
            logger.warning(f"save config failed: {target_config_file}, trying fallback: {err}")

    if last_error:
        raise last_error


_cfg = load_config(config_file)
app = _cfg.get("app", {})
whisper = _cfg.get("whisper", {})
proxy = _cfg.get("proxy", {})
azure = _cfg.get("azure", {})
tencent = _cfg.get("tencent", {})
soulvoice = _cfg.get("soulvoice", {})
ui = _cfg.get("ui", {})
frames = _cfg.get("frames", {})
tts_qwen = _cfg.get("tts_qwen", {})
indextts2 = _cfg.get("indextts2", {})

hostname = socket.gethostname()

log_level = _cfg.get("log_level", "DEBUG")
listen_host = _cfg.get("listen_host", "0.0.0.0")
listen_port = _cfg.get("listen_port", 8080)
project_name = _cfg.get("project_name", "NarratoAI")
project_description = _cfg.get(
    "project_description",
    "<a href='https://github.com/linyqh/NarratoAI'>https://github.com/linyqh/NarratoAI</a>",
)
# 从文件读取版本号，而不是从配置文件中获取
project_version = get_version_from_file()
reload_debug = False

imagemagick_path = app.get("imagemagick_path", "")
if imagemagick_path and os.path.isfile(imagemagick_path):
    os.environ["IMAGEMAGICK_BINARY"] = imagemagick_path

ffmpeg_path = app.get("ffmpeg_path", "")
if ffmpeg_path and os.path.isfile(ffmpeg_path):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

logger.info(f"{project_name} v{project_version}")
