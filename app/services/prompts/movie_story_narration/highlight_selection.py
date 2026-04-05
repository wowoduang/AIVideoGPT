#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class HighlightSelectionPrompt(ParameterizedPrompt):
    """高光入选提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="highlight_selection",
            category="movie_story_narration",
            version="v1.0",
            description="基于整片剧情理解和精细剧情段证据，决定最终高光片段入选",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "高光筛选", "剧情段", "时间范围"],
            parameters=["global_summary_json", "full_subtitle_summary_json", "scene_candidates_json"],
        )
        super().__init__(metadata, required_parameters=["global_summary_json", "full_subtitle_summary_json", "scene_candidates_json"])
        self._system_prompt = (
            "你是保守但专业的电影高光筛选助手。"
            "你的任务是从候选剧情段中找出真正值得进入最终视频的高光片段。"
            "你不能因为主角出场或普通对白就判定为高光。"
        )

    def get_template(self) -> str:
        return """# 任务
请根据整片剧情理解、整字幕高光规划、以及精细剧情段候选，选出最终应该保留的高光片段。

# 筛选原则
1. 优先保留：反转、重大揭露、强冲突、情感爆发、高潮、结尾收束
2. 不要把片头铺垫、人物日常寒暄、纯信息交代、弱过渡、普通对白误判为高光
3. “主角出现”本身不是保留理由，必须有剧情事件价值
4. 只有强情绪或强戏剧张力片段才建议保留原声
5. 如果片段风险高、边界不清、剧情意义弱，应排除
6. 只输出 JSON

# 输出 JSON 结构
{
  "selected_segment_ids": ["plot_003", "plot_009"],
  "rejected_segment_ids": ["plot_001"],
  "raw_voice_segment_ids": ["plot_009"],
  "must_keep_ranges": [
    {
      "start": "HH:MM:SS,mmm",
      "end": "HH:MM:SS,mmm",
      "reason": "为什么必须保留"
    }
  ],
  "selection_notes": [
    {
      "segment_id": "plot_003",
      "decision": "keep/reject/raw_voice",
      "reason": "简要理由"
    }
  ]
}

# 全局剧情理解
${global_summary_json}

# 整字幕高光规划
${full_subtitle_summary_json}

# 精细剧情段候选
${scene_candidates_json}
"""
