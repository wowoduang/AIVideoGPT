#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class GlobalUnderstandingPrompt(ParameterizedPrompt):
    """整剧理解提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="global_understanding",
            category="movie_story_narration",
            version="v1.0",
            description="根据 final subtitle / plot chunks 生成整剧剧情理解摘要",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "整剧理解", "剧情摘要", "影视解说"],
            parameters=["subtitle_digest"],
        )
        super().__init__(metadata, required_parameters=["subtitle_digest"])
        self._system_prompt = (
            "你是严格、保守的中文影视剧情理解助手。"
            "你只负责剧情理解，不负责写解说文案。"
            "不得编造未被证据支持的人物动机、道具、地点和事件。"
        )

    def get_template(self) -> str:
        return """# 任务
你将看到一组按时间顺序整理好的剧情块摘要。你的任务是输出整部影片的全局剧情理解结果。

# 重要约束
1. 只能根据输入内容理解剧情，不能补写画面中未出现的事实
2. 字幕字面意思不一定等于真实剧情状态
3. 当出现撒谎、试探、反讽、旁白、回忆、闪回、蒙太奇等风险时，必须写入 narrative_risk_flags
4. 不要写影视解说文案，不要用夸张口吻
5. 只输出 JSON，不要额外解释

# 输出 JSON 结构
{
  "protagonist": "主角姓名或角色身份",
  "main_storyline": "用 80 字以内概括整部片子的故事主线",
  "character_relations": [
    {"a": "角色A", "relation": "关系", "b": "角色B"}
  ],
  "core_conflicts": ["核心冲突1", "核心冲突2"],
  "timeline_progression": ["阶段1", "阶段2", "阶段3"],
  "unresolved_tensions": ["悬念或未解决张力"],
  "narrative_risk_flags": ["字幕表层与真实剧情可能不一致的风险点"],
  "key_segments": ["plot_001", "plot_005"],
  "entity_map": {"别称": "标准称呼"},
  "arc": "故事整体弧线总结"
}

# 输入剧情块
${subtitle_digest}
"""
