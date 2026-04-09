#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class SubtitleChunkUnderstandingPrompt(ParameterizedPrompt):
    """整字幕分块理解提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="subtitle_chunk_understanding",
            category="movie_story_narration",
            version="v1.0",
            description="对超长电影字幕按时间窗口做分块剧情理解，提炼剧情推进与高光候选",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "整字幕", "分块理解", "高光"],
            parameters=["chunk_index", "chunk_count", "subtitle_chunk_text"],
        )
        super().__init__(metadata, required_parameters=["chunk_index", "chunk_count", "subtitle_chunk_text"])
        self._system_prompt = (
            "你是严格、保守的中文电影剧情分析助手。"
            "你只负责理解当前字幕时间窗口里的剧情推进、高光候选和风险，不负责写解说词。"
            "你不能编造画面、人物行为或超出字幕证据的内容。"
        )

    def get_template(self) -> str:
        return """# 任务
你会看到整部电影字幕中的第 ${chunk_index}/${chunk_count} 个时间窗口。
请基于这个窗口里的完整字幕内容，提炼这段的剧情推进、高光候选和理解风险。

# 重要约束
1. 只分析当前窗口，不要猜测窗口外剧情
2. 输出的是剧情理解结果，不是解说文案
3. 时间范围必须基于输入里已有的字幕时间
4. 证据不足时必须保守
5. 只输出 JSON

# 输出 JSON 结构
{
  "chunk_index": ${chunk_index},
  "window_summary": "当前窗口剧情概括，80字以内",
  "major_events": [
    {
      "label": "冲突/揭露/转折/铺垫/高潮/结尾",
      "start": "HH:MM:SS,mmm",
      "end": "HH:MM:SS,mmm",
      "reason": "为什么这样判断"
    }
  ],
  "highlight_windows": [
    {
      "start": "HH:MM:SS,mmm",
      "end": "HH:MM:SS,mmm",
      "category": "冲突升级/反转/情感爆发/信息揭露/高潮/结尾",
      "raw_voice_priority": "high/medium/low",
      "reason": "为什么可能值得保留"
    }
  ],
  "risk_flags": ["若当前窗口存在理解风险，在这里写明"]
}

# 当前字幕窗口
${subtitle_chunk_text}
"""
