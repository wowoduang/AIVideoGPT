#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
@Project: NarratoAI
@File   : __init__.py
@Author : viccy同学
@Date   : 2025/1/7
@Description: 统一提示词管理模块
"""

from .manager import PromptManager
from .base import BasePrompt, VisionPrompt, TextPrompt, ParameterizedPrompt
from .registry import PromptRegistry
from .template import TemplateRenderer
from .validators import PromptOutputValidator
from .exceptions import (
    PromptError,
    PromptNotFoundError,
    PromptValidationError,
    TemplateRenderError
)

__version__ = "1.1.0"
__author__ = "viccy同学"

__all__ = [
    "PromptManager",
    "BasePrompt", "VisionPrompt", "TextPrompt", "ParameterizedPrompt",
    "PromptRegistry", "TemplateRenderer", "PromptOutputValidator",
    "PromptError", "PromptNotFoundError", "PromptValidationError", "TemplateRenderError",
    "__version__", "__author__"
]


def initialize_prompts():
    """初始化提示词模块，注册所有提示词"""
    from . import documentary
    from . import short_drama_editing
    from . import short_drama_narration
    from . import movie_story_narration

    documentary.register_prompts()
    short_drama_editing.register_prompts()
    short_drama_narration.register_prompts()
    movie_story_narration.register_prompts()


initialize_prompts()
