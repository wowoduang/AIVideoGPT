import os
import tomli
from loguru import logger
from typing import Dict, Any, Optional
from dataclasses import dataclass

def get_version_from_file():
    """从project_version文件中读取版本号"""
    try:
        version_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "project_version"
        )
        if os.path.isfile(version_file):
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        return "0.1.0"  # 默认版本号
    except Exception as e:
        logger.error(f"读取版本号文件失败: {str(e)}")
        return "0.1.0"  # 默认版本号

@dataclass
class WebUIConfig:
    """WebUI配置类"""
    # UI配置
    ui: Dict[str, Any] = None
    # 代理配置
    proxy: Dict[str, str] = None
    # 应用配置
    app: Dict[str, Any] = None
    # Azure配置
    azure: Dict[str, str] = None
    # 项目版本
    project_version: str = get_version_from_file()
    # 项目根目录
    root_dir: str = None
    # Gemini API Key
    gemini_api_key: str = ""
    # 每批处理的图片数量
    vision_batch_size: int = 5
    # 提示词
    vision_prompt: str = """..."""

    def __post_init__(self):
        """初始化默认值"""
        self.ui = self.ui or {}
        self.proxy = self.proxy or {}
        self.app = self.app or {}
        self.azure = self.azure or {}
        self.root_dir = self.root_dir or os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _normalize_path(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(str(path or "").strip()))
    return os.path.abspath(expanded) if expanded else ""


def _default_workspace_root() -> str:
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
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


def _legacy_webui_config_file() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".streamlit",
        "webui.toml"
    )


def resolve_config_path(config_path: Optional[str] = None) -> str:
    raw_path = str(config_path or os.getenv("NARRATO_WEBUI_CONFIG_FILE", "") or "").strip()
    if raw_path:
        resolved = _normalize_path(raw_path)
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if not os.path.isabs(raw_path):
            resolved = os.path.abspath(os.path.join(root_dir, raw_path))
        return resolved
    return os.path.join(_default_workspace_root(), "state", "webui.toml")


def load_config(config_path: Optional[str] = None) -> WebUIConfig:
    """加载配置文件
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
    Returns:
        WebUIConfig: 配置对象
    """
    try:
        config_path = resolve_config_path(config_path)
        
        # 如果配置文件不存在，使用示例配置
        if not os.path.exists(config_path):
            legacy_config = _legacy_webui_config_file()
            if legacy_config != config_path and os.path.exists(legacy_config):
                config_path = legacy_config

        if not os.path.exists(config_path):
            example_config = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config.example.toml"
            )
            if os.path.exists(example_config):
                config_path = example_config
            else:
                logger.warning(f"配置文件不存在: {config_path}")
                return WebUIConfig()
        
        # 读取配置文件
        with open(config_path, "rb") as f:
            config_dict = tomli.load(f)
            
        # 创建配置对象，使用从文件读取的版本号
        config = WebUIConfig(
            ui=config_dict.get("ui", {}),
            proxy=config_dict.get("proxy", {}),
            app=config_dict.get("app", {}),
            azure=config_dict.get("azure", {}),
            # 不再从配置文件中获取project_version
        )
        
        return config
    
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return WebUIConfig()

def save_config(config: WebUIConfig, config_path: Optional[str] = None) -> bool:
    """保存配置到文件
    Args:
        config: 配置对象
        config_path: 配置文件路径，如果为None则使用默认路径
    Returns:
        bool: 是否保存成功
    """
    try:
        config_path = resolve_config_path(config_path)

        config_dict = {
            "ui": config.ui,
            "proxy": config.proxy,
            "app": config.app,
            "azure": config.azure
        }

        for target_path in (config_path, _legacy_webui_config_file()):
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    import tomli_w
                    tomli_w.dump(config_dict, f)
                return True
            except OSError as err:
                logger.warning(f"保存 WebUI 配置失败: {target_path}, 尝试兼容回落: {err}")
        return False
    
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return False

def get_config() -> WebUIConfig:
    """获取全局配置对象
    Returns:
        WebUIConfig: 配置对象
    """
    if not hasattr(get_config, "_config"):
        get_config._config = load_config()
    return get_config._config

def update_config(config_dict: Dict[str, Any]) -> bool:
    """更新配置
    Args:
        config_dict: 配置字典
    Returns:
        bool: 是否更新成功
    """
    try:
        config = get_config()
        
        # 更新配置
        if "ui" in config_dict:
            config.ui.update(config_dict["ui"])
        if "proxy" in config_dict:
            config.proxy.update(config_dict["proxy"])
        if "app" in config_dict:
            config.app.update(config_dict["app"])
        if "azure" in config_dict:
            config.azure.update(config_dict["azure"])
        # 不再从配置字典更新project_version
        
        # 保存配置
        return save_config(config)
    
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return False

# 导出全局配置对象
config = get_config() 
