#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class NarrationGenerationPrompt(ParameterizedPrompt):
    """影视解说文案生成提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="narration_generation",
            category="movie_story_narration",
            version="v1.1",
            description="基于剧情证据、影片上下文与风格样本生成单段影视解说文案",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["电影", "影视解说", "文案生成", "风格样本"],
            parameters=[
                "segment_json",
                "global_summary_json",
                "project_context_json",
                "style_guide",
                "style_examples",
                "char_budget",
            ],
        )
        super().__init__(
            metadata,
            required_parameters=[
                "segment_json",
                "global_summary_json",
                "project_context_json",
                "style_guide",
                "style_examples",
                "char_budget",
            ],
        )
        self._system_prompt = (
            "你是中文影视解说文案助手。"
            "你要根据剧情证据、影片题材提示和解说风格，写出适合口播的单段解说。"
            "允许概括总结，不需要逐句复述字幕，但不能说反主线事实、人物关系和因果方向。"
        )

    def get_template(self) -> str:
        return """# 任务
你需要根据“已校核剧情片段”和“项目上下文”生成一段适合口播的影视解说。

# 关键原则
1. 不得编造未被剧情理解层确认的信息。
2. 允许对片段做概括总结，不要求逐句复述字幕；只要主线事实、人物关系、因果方向不说反即可。
3. 如果你熟悉 `${project_context_json}` 中这部影片，可以利用对影片本身的既有知识帮助辨认角色、身份和场面，但必须严格受当前时间窗限制，不能提前写到后续情节。
4. 如果 `is_opening_segment=true`，第一句必须先交代开场局势、人物或场面，不能整段零开场。
5. 只有 `speaker_attribution_confidence=single_explicit` 时，才可以写成“某人说/某人命令”；否则要用“有人/对方/现场/这番话”等中性说法，避免乱认说话人。
6. `plot_function` 为“铺垫/节奏缓冲”的段落简短，`plot_function` 为“反转/情感爆发/信息揭露”的段落可以重点展开。
7. 输出长度要服从 `char_budget`，因为它直接决定配音时长和视频匹配节奏。
8. 原声保留只适用于短促、情绪强、现场感强的片段；长段默认仍以解说为主。
9. 风格优先参考样本文案，而不是自己发明口吻。
10. `segment_json` / `project_context_json` 中如果给了 `timestamp`、`start/end`、`visual_summary`、`representative_frames`，要把它们当作当前片段的时间窗和画面证据使用。
11. 只输出 JSON，不要额外解释。

# 输出 JSON 结构
{
  "narration": "最终口播文案，首段要有开场感",
  "raw_voice_keep": false,
  "tone": "一句话概括语气",
  "opening_type": "悬念 / 直叙 / 情绪推进 / 过渡",
  "risk_note": "如果证据不足，这里说明为何保守表达"
}

# 项目上下文
${project_context_json}

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
