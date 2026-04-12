#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class NarrationValidationPrompt(ParameterizedPrompt):
    """解说文案校核提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="narration_validation",
            category="movie_story_narration",
            version="v1.1",
            description="校核单段解说文案是否超出剧情证据或表述失真",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "解说校核", "事实校核"],
            parameters=["segment_json", "project_context_json", "generated_narration"],
        )
        super().__init__(metadata, required_parameters=["segment_json", "project_context_json", "generated_narration"])
        self._system_prompt = (
            "你是影视解说事实校核助手。"
            "你只负责判断解说词是否明显超出证据、是否把剧情主线说偏。"
            "允许概括性表达，不要求逐句复述字幕。"
            "只有在出现明显事实错误、人物关系说反、因果硬编、或在说话人证据不足时乱认说话人，才给 reject。"
        )

    def get_template(self) -> str:
        return """# 任务
请根据剧情证据，校核这段影视解说是否准确、保守、没有编造。
允许概括和压缩表达，不要求逐字贴合原字幕。

# 校核重点
1. 是否添加了证据里没有明确支持的新事实
2. 是否把表层对白误说成确定剧情
3. 是否把情绪、动机、因果说得过满
4. 是否出现了和证据明显不一致的表述
5. 如果 `speaker_attribution_confidence` 不是 `single_explicit`，是否错误地把台词强行归给具体人物或身份
6. 如果 `is_opening_segment=true`，这段解说是否完全没有开场交代
7. 是否适合作为最终口播
8. 轻微概括、措辞不够严谨但主线没错时，优先给 review，不要轻易给 reject
9. 如果证据里提供了 `timestamp`、`start/end`、`visual_summary`、`representative_frames`，要把它们当作当前片段的时间窗和画面证据，避免写出错位画面

# 输出 JSON 结构
{
  "status": "pass / review / reject",
  "issues": ["问题1", "问题2"],
  "safe_rewrite_hint": "直接给出可口播的最终改写句子，不要加“如果需要更保守”之类解释",
  "raw_voice_keep": false
}

# 项目上下文
${project_context_json}

# 剧情证据
${segment_json}

# 已生成解说
${generated_narration}
"""
