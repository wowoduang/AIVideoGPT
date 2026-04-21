"""
LLM 配置统一读取模块

新 UI 架构下，所有 LLM 配置统一从 config.app 读取
不再通过前端传递参数
"""

from typing import Dict, Any, Optional
from app.config import config


def get_text_llm_config() -> Dict[str, str]:
    """
    获取文本 LLM 配置
    
    Returns:
        Dict 包含 api_key, model, base_url
    """
    provider = config.app.get('text_llm_provider', 'litellm').lower()
    
    # 根据提供商类型读取对应配置
    if provider == 'litellm':
        return {
            'api_key': config.app.get('text_litellm_api_key', ''),
            'model': config.app.get('text_litellm_model_name', ''),
            'base_url': config.app.get('text_litellm_base_url', ''),
            'provider': provider,
        }
    else:
        # 其他提供商使用通用命名模式
        return {
            'api_key': config.app.get(f'text_{provider}_api_key', ''),
            'model': config.app.get(f'text_{provider}_model_name', ''),
            'base_url': config.app.get(f'text_{provider}_base_url', ''),
            'provider': provider,
        }


def get_vision_llm_config() -> Dict[str, str]:
    """
    获取视觉 LLM 配置
    
    Returns:
        Dict 包含 api_key, model, base_url
    """
    provider = config.app.get('vision_llm_provider', 'litellm').lower()
    
    if provider == 'litellm':
        return {
            'api_key': config.app.get('vision_litellm_api_key', ''),
            'model': config.app.get('vision_litellm_model_name', ''),
            'base_url': config.app.get('vision_litellm_base_url', ''),
            'provider': provider,
        }
    else:
        return {
            'api_key': config.app.get(f'vision_{provider}_api_key', ''),
            'model': config.app.get(f'vision_{provider}_model_name', ''),
            'base_url': config.app.get(f'vision_{provider}_base_url', ''),
            'provider': provider,
        }


def ensure_text_llm_config() -> None:
    """
    确保文本 LLM 配置完整，否则抛出异常
    
    Raises:
        ValueError: 配置不完整时
    """
    cfg = get_text_llm_config()
    missing = []
    if not cfg.get('api_key'):
        missing.append('text_llm api_key')
    if not cfg.get('model'):
        missing.append('text_llm model')
    
    if missing:
        raise ValueError(f"LLM 配置不完整，缺少: {', '.join(missing)}")
