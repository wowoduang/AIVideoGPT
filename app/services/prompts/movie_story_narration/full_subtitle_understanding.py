#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class FullSubtitleUnderstandingPrompt(ParameterizedPrompt):
    """整字幕剧情理解提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="full_subtitle_understanding",
            category="movie_story_narration",
            version="v1.0",
            description="基于整部影片字幕时序摘要，生成全片剧情结构、高光阶段和前奏结束提示",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "整字幕", "剧情理解", "高光规划"],
            parameters=["subtitle_timeline_digest"],
        )
        super().__init__(metadata, required_parameters=["subtitle_timeline_digest"])
        self._system_prompt = (
            "你是严格、保守的中文影视剧情分析助手。"
            "你只负责理解剧情阶段和高光分布，不负责写解说稿。"
            "你必须依据输入字幕时序进行判断，不能编造画面和情节。"
        )

    def get_template(self) -> str:
        return """# 任务
你会看到按时间顺序整理的整部影片字幕时间线摘要。
请输出全片剧情阶段、高光窗口、前奏结束时间和需要重点关注的剧情段类型。

# 重要约束
1. 你只做剧情理解和高光规划，不要写解说文案
2. 你输出的是“语义时间范围”，不是精确镜头切点
3. 如果证据不足，必须保守
4. 片头铺垫、环境介绍、人物出场寒暄不应被误判为高光
5. 真正值得保留原声的，通常是情感爆发、强冲突、重大揭露、结局收束
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

# 整字幕时间线摘要
${subtitle_timeline_digest}
"""
