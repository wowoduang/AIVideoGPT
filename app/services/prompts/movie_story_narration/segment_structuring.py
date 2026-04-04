#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class SegmentStructuringPrompt(ParameterizedPrompt):
    """剧情段精理解提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="segment_structuring",
            category="movie_story_narration",
            version="v1.0",
            description="对单个剧情段做结构化理解，分离字幕表层含义和真实叙事状态",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "剧情段", "精分段", "剧情理解"],
            parameters=["segment_meta_json", "segment_text", "global_summary_json"],
        )
        super().__init__(metadata, required_parameters=["segment_meta_json", "segment_text", "global_summary_json"])
        self._system_prompt = (
            "你是严谨的影视剧情片段分析助手。"
            "你要把“字幕表层含义”和“真实剧情状态”分开。"
            "遇到证据不足时，必须保守。"
        )

    def get_template(self) -> str:
        return """# 任务
你需要分析一个剧情片段，并输出结构化 JSON。

# 分析目标
1. 识别这个片段在剧情中的真实作用
2. 区分表层对白含义与真实叙事状态
3. 判断是否需要视觉核对
4. 给出边界可信度与原因
5. 判断是否更适合保留原声

# 允许的 plot_function
铺垫 / 冲突升级 / 反转 / 情感爆发 / 信息揭露 / 悬念制造 / 节奏缓冲 / 结局收束

# 输出 JSON 结构
{
  "surface_dialogue_meaning": "字幕字面意思，40字以内",
  "real_narrative_state": "真实叙事状态，60字以内",
  "plot_function": "从允许值中选择一个",
  "importance_level": "high / medium / low",
  "emotion": "片段主情绪",
  "need_visual_verify": true,
  "raw_voice_retain_suggestion": false,
  "boundary_confidence": "high / medium / low",
  "boundary_reasons": ["说明为何这么判断边界"],
  "narrative_risk_flags": ["例如：角色可能在撒谎", "可能存在闪回"],
  "validator_hints": ["后续校核时应该重点确认的点"],
  "characters": ["涉及人物"],
  "key_dialogue": ["代表性短句1", "代表性短句2"]
}

# 全局剧情摘要
${global_summary_json}

# 当前片段元信息
${segment_meta_json}

# 当前片段字幕
${segment_text}
"""
