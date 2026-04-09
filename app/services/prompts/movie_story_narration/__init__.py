#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
@Project: NarratoAI
@File   : __init__.py
@Description: 影视剧情分段与解说提示词模块
"""

from .global_understanding import GlobalUnderstandingPrompt
from .full_subtitle_understanding import FullSubtitleUnderstandingPrompt
from .full_subtitle_understanding_v2 import FullSubtitleUnderstandingV2Prompt
from .subtitle_chunk_understanding import SubtitleChunkUnderstandingPrompt
from .highlight_selection import HighlightSelectionPrompt
from .segment_structuring import SegmentStructuringPrompt
from .story_validation import StoryValidationPrompt
from .narration_generation import NarrationGenerationPrompt
from .narration_validation import NarrationValidationPrompt
from ..manager import PromptManager


def register_prompts():
    PromptManager.register_prompt(GlobalUnderstandingPrompt(), is_default=True)
    PromptManager.register_prompt(FullSubtitleUnderstandingPrompt(), is_default=True)
    PromptManager.register_prompt(FullSubtitleUnderstandingV2Prompt(), is_default=True)
    PromptManager.register_prompt(SubtitleChunkUnderstandingPrompt(), is_default=True)
    PromptManager.register_prompt(HighlightSelectionPrompt(), is_default=True)
    PromptManager.register_prompt(SegmentStructuringPrompt(), is_default=True)
    PromptManager.register_prompt(StoryValidationPrompt(), is_default=True)
    PromptManager.register_prompt(NarrationGenerationPrompt(), is_default=True)
    PromptManager.register_prompt(NarrationValidationPrompt(), is_default=True)


__all__ = [
    "GlobalUnderstandingPrompt",
    "FullSubtitleUnderstandingPrompt",
    "FullSubtitleUnderstandingV2Prompt",
    "SubtitleChunkUnderstandingPrompt",
    "HighlightSelectionPrompt",
    "SegmentStructuringPrompt",
    "StoryValidationPrompt",
    "NarrationGenerationPrompt",
    "NarrationValidationPrompt",
    "register_prompts",
]
