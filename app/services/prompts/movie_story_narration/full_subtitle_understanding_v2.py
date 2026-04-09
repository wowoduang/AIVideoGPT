#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class FullSubtitleUnderstandingV2Prompt(ParameterizedPrompt):
    """整字幕剧情理解提示词 v2"""

    def __init__(self):
        metadata = PromptMetadata(
            name="full_subtitle_understanding_v2",
            category="movie_story_narration",
            version="v2.0",
            description="基于整部电影字幕全文、时间摘要或分块摘要，生成全片剧情结构与高光规划",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "整字幕", "剧情理解", "高光规划"],
            parameters=["subtitle_timeline_digest", "full_subtitle_text", "subtitle_chunk_summaries_json"],
        )
        super().__init__(
            metadata,
            required_parameters=["subtitle_timeline_digest", "full_subtitle_text", "subtitle_chunk_summaries_json"],
        )
        self._system_prompt = (
            "你是严格、保守的中文电影剧情分析助手。"
            "你只负责理解剧情阶段和高光分布，不负责写解说稿。"
            "你必须优先依据完整字幕全文；若字幕过长，则结合分块摘要和时间摘要做全片判断。"
            "你不能编造画面和情节。"
        )

    def get_template(self) -> str:
        return """# 任务
你会看到按时间顺序整理的整部电影字幕信息：
1. 优先使用“完整字幕全文”
2. 如果完整字幕过长或为空，再使用“字幕分块理解摘要”
3. 最后用“字幕时间线摘要”辅助全局排序

# 重要约束
1. 只做剧情理解和高光规划，不写解说文案
2. 输出的是“语义时间范围”，不是精确镜头切点
3. 证据不足时必须保守
4. 片头铺垫、环境介绍、日常寒暄、普通主角出场，不应误判为高光
5. 真正值得保留原声的，通常是情感爆发、强冲突、重大揭露、结尾收束
6. 只输出 JSON

# 输出 JSON 结构
{
  "story_arc": "全片主线概括，120字以内",
  "prologue_end_time": "HH:MM:SS,mmm 或空字符串",
  "major_turning_points": [
    {
      "label": "转折/冲突/揭露/高潮/结尾",
      "start": "HH:MM:SS,mmm",
      "end": "HH:MM:SS,mmm",
      "reason": "为什么这段重要"
    }
  ],
  "highlight_windows": [
    {
      "start": "HH:MM:SS,mmm",
      "end": "HH:MM:SS,mmm",
      "category": "冲突升级/反转/情感爆发/信息揭露/高潮/结尾",
      "importance": "high/medium",
      "raw_voice_priority": "high/medium/low",
      "reason": "这段为什么可能是高光"
    }
  ],
  "selection_policy": {
    "must_keep_categories": ["反转", "情感爆发"],
    "avoid_categories": ["片头铺垫", "弱过渡", "日常寒暄"]
  },
  "narrative_risk_flags": ["如果存在时间线理解风险，写在这里"]
}

# 完整字幕全文
${full_subtitle_text}

# 字幕分块理解摘要
${subtitle_chunk_summaries_json}

# 字幕时间线摘要
${subtitle_timeline_digest}
"""
