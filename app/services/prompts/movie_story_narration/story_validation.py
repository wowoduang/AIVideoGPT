#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class StoryValidationPrompt(ParameterizedPrompt):
    """剧情设计核对提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="story_validation",
            category="movie_story_narration",
            version="v1.0",
            description="对已生成的剧情段进行叙事合理性与风险核对",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "剧情校核", "叙事风险", "边界检查"],
            parameters=["segments_json", "global_summary_json"],
        )
        super().__init__(metadata, required_parameters=["segments_json", "global_summary_json"])
        self._system_prompt = (
            "你是影视剧情设计核对助手。"
            "你不负责改写文案，只负责指出剧情划分和理解的风险。"
        )

    def get_template(self) -> str:
        return """# 任务
请检查下列剧情段设计是否存在明显风险。

# 重点检查
1. 是否把同一事件切碎
2. 是否把不同事件误合并
3. 是否存在回忆/闪回/蒙太奇被当成线性叙事
4. 是否出现字幕字面意思和真实剧情状态冲突
5. 是否有更适合保留原声的高情绪片段

# 输出 JSON 结构
{
  "global_warnings": ["全局风险提示"],
  "segment_reviews": [
    {
      "segment_id": "plot_001",
      "validator_status": "pass / review / risky",
      "issues": ["问题1", "问题2"],
      "recommendations": ["建议1", "建议2"],
      "raw_voice_keep": false
    }
  ]
}

# 全局剧情摘要
${global_summary_json}

# 剧情段列表
${segments_json}
"""
