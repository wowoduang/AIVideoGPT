#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class NarrationValidationPrompt(ParameterizedPrompt):
    """解说文案校核提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="narration_validation",
            category="movie_story_narration",
            version="v1.0",
            description="校核单段解说文案是否超出剧情证据或表述失真",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "解说校核", "事实校核"],
            parameters=["segment_json", "generated_narration"],
        )
        super().__init__(metadata, required_parameters=["segment_json", "generated_narration"])
        self._system_prompt = (
            "你是严格保守的影视解说事实校核助手。"
            "你只负责判断解说词是否超出证据、是否把剧情说偏。"
            "如果有不确定，就倾向于保守。"
        )

    def get_template(self) -> str:
        return """# 任务
请根据剧情证据，校核这段影视解说是否准确、保守、没有编造。

# 校核重点
1. 是否添加了证据里没有明确支持的新事实
2. 是否把表层对白误说成确定剧情
3. 是否把情绪、动机、因果说得过满
4. 是否出现了和证据明显不一致的表述
5. 是否适合作为最终口播

# 输出 JSON 结构
{
  "status": "pass / review / reject",
  "issues": ["问题1", "问题2"],
  "safe_rewrite_hint": "如果需要更保守，可以怎么写",
  "raw_voice_keep": false
}

# 剧情证据
${segment_json}

# 已生成解说
${generated_narration}
"""
