#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class NarrationGenerationPrompt(ParameterizedPrompt):
    """影视解说文案生成提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="narration_generation",
            category="movie_story_narration",
            version="v1.0",
            description="基于已校核剧情段与风格样本生成单段影视解说文案",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "影视解说", "文案生成", "风格样本"],
            parameters=["segment_json", "global_summary_json", "style_guide", "style_examples", "char_budget"],
        )
        super().__init__(
            metadata,
            required_parameters=["segment_json", "global_summary_json", "style_guide", "style_examples", "char_budget"],
        )
        self._system_prompt = (
            "你是影视解说文案助手。"
            "你的任务是根据已校核的剧情片段写出可口播、但不虚构的解说句。"
        )

    def get_template(self) -> str:
        return """# 任务
你需要根据“已校核剧情片段”生成一段适合口播的影视解说。

# 关键原则
1. 不得编造未被剧情理解层确认的信息
2. plot_function 为“铺垫/节奏缓冲”的段落简写
3. plot_function 为“反转/情感爆发/信息揭露”的段落可以重点展开
4. 当 raw_voice_retain_suggestion=true 或 validator 明确建议保留原声时，必须保守
5. 风格优先参考样本文案，而不是自己发明口吻
6. 只输出 JSON，不要额外解释

# 输出 JSON 结构
{
  "narration": "最终口播文案",
  "raw_voice_keep": false,
  "tone": "一句话概括语气",
  "opening_type": "悬念 / 直叙 / 情绪推进 / 过渡",
  "risk_note": "如果证据不足，这里说明为何保守表达"
}

# 全局剧情摘要
${global_summary_json}

# 当前剧情片段
${segment_json}

# 风格说明
${style_guide}

# 风格样本
${style_examples}

# 字数上限
${char_budget}
"""
