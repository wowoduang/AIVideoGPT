# 字幕优先影视解说主链实施规范

## 目标

在不虚构剧情的前提下，基于字幕优先完成一条可稳定产出“可看、可用、具备高光感”的影视解说视频主链。

核心要求：

1. 先保证准确，再追求精彩。
2. 不按原片顺序机械复述，不把低价值铺垫、长过渡、片头空转段直接带入成片。
3. 最终脚本和视频片段必须只来自“经过校核后被选中的剧情高价值段”。
4. 任意一段若存在高风险边界、剧情理解歧义、字幕表层与真实叙事状态冲突，必须保守处理。

## 总体流程

### M1 字幕获取与标准化

输入：

1. 原视频
2. 可选外挂字幕
3. ASR 后端

输出：

1. 标准化字幕段 `segments`
2. `raw/clean/final subtitle` 相关文件

必须保证：

1. 不能把明显无效、空白、纯静默标记、纯情绪标签作为有效剧情字幕。
2. 时间轴必须尽量与字幕文本对齐。
3. 当前阶段优先使用 `faster-whisper` 作为主后端。

当前入口：

1. `app/services/subtitle_pipeline.py`
2. `app/services/subtitle.py`

### M2 剧情块粗分段与边界候选

输入：

1. 标准化字幕段
2. 视频场景候选边界

输出：

1. 粗分段剧情块
2. 视频边界候选
3. 字幕边界候选

必须保证：

1. 不能把明显跨事件的内容粗暴并到同一块。
2. 不能因为时间连续就默认属于同一剧情动作。
3. 要记录边界来源、边界原因、边界置信度。

当前入口：

1. `app/services/plot_chunker.py`
2. `app/services/scene_builder.py`
3. `app/services/story_boundary_aligner.py`

### M3 整剧理解

输入：

1. 初版剧情块

输出：

1. `global_summary`
2. 主角、主线、冲突、整体弧线、风险标记

必须保证：

1. 不能写解说文案。
2. 不能补写字幕或画面中没有证据支持的事实。
3. 要明确可能的叙事风险，比如回忆、插叙、误导对白、表层对白不等于真实剧情状态。

当前入口：

1. `app/services/plot_understanding_clean.py`
2. `app/services/prompts/movie_story_narration/global_understanding.py`

### M4 单段结构化理解

输入：

1. 剧情块
2. 全局剧情理解
3. 代表帧和局部视觉摘要

输出：

1. `plot_function`
2. `importance_level`
3. `surface_dialogue_meaning`
4. `real_narrative_state`
5. `need_visual_verify`
6. `raw_voice_retain_suggestion`
7. `boundary_confidence`
8. `boundary_reasons`

必须保证：

1. 必须把“字幕表层含义”和“真实叙事状态”拆开。
2. 必须给出是否需要视觉核对。
3. 不能把字段只当展示信息，后续筛选必须消费这些字段。

当前入口：

1. `app/services/plot_understanding_clean.py`
2. `app/services/prompts/movie_story_narration/segment_structuring.py`

### M5 高光筛选

输入：

1. 已结构化剧情块

输出：

1. 高光优先剧情块集合
2. 被剔除段的原因

必须保证：

1. 不限制总时长，但必须主动剔除低价值内容。
2. 应优先保留：
   `反转 / 冲突升级 / 情感爆发 / 信息揭露 / 结局收束 / 高重要度段`
3. 应优先剔除：
   `片头低价值铺垫 / 弱过渡 / 长说明 / 重复信息 / 高风险且低价值段`
4. 对被保留的强剧情段，可以保留少量上下文，但上下文不能反客为主。

当前入口：

1. `app/services/plot_chunker.py`
2. `app/services/subtitle_first_pipeline.py`

### M6 剧情校核

输入：

1. 经过初筛的剧情证据包
2. 全局剧情理解

输出：

1. `story_validation`
2. `validator_status = pass / review / risky`
3. 是否建议保留原声

必须保证：

1. 若同一事件被切碎、不同事件被误并、边界可信度低、表层对白与真实剧情状态冲突，应标记风险。
2. `risky` 片段不能直接进入最终文案生成，除非它是高重要度核心段并且经过保守处理。

当前入口：

1. `app/services/story_validator_clean.py`
2. `app/services/prompts/movie_story_narration/story_validation.py`

### M7 最终证据筛选

输入：

1. 已经完成校核的剧情证据包

输出：

1. 最终允许进入文案生成的证据包

必须保证：

1. 最终文案生成阶段不允许再吃“全部剧情块”。
2. 只能吃“最终证据筛选通过”的剧情段。
3. `risky + low importance` 段默认剔除。
4. `setup / transition / low importance` 段必须满足足够高分或承担上下文职责，才能被保留。

当前入口：

1. `app/services/subtitle_first_pipeline.py`

### M8 文案生成

输入：

1. 通过最终筛选的剧情证据包
2. 全局剧情理解
3. 风格说明与示例

输出：

1. 最终脚本项 `script_items`

必须保证：

1. 不得虚构。
2. 铺垫和缓冲段必须更简。
3. 反转、爆发、揭露、结尾段可以重点展开。
4. 若建议保留原声，要在脚本层体现为更保守的音频策略。

当前入口：

1. `app/services/generate_narration_script_clean.py`
2. `app/services/prompts/movie_story_narration/narration_generation.py`

### M9 最终合成

输入：

1. 最终脚本
2. 原视频
3. TTS / OST / 字幕

输出：

1. 解说成片

必须保证：

1. 最终裁剪必须只根据最终入选脚本进行。
2. 不能再把被剔除的低价值段带回成片。
3. 不能默认“按原片顺序完整复述”。

当前入口：

1. `app/services/task.py`
2. `app/services/clip_video.py`
3. `app/services/generate_video.py`

## 当前实现对齐要求

后续所有与字幕优先影视解说相关的改动，统一按以下原则执行：

1. 先补文字规范，再补代码实现。
2. 新增字段若不能影响最终筛选或合成，不视为完成。
3. 任何“高光设计”若没有进入 `最终证据筛选` 或 `最终合成`，都算未完整实现。
4. 当前阶段优先目标是“先做出可用成片”，因此默认 ASR 主路径使用 `faster-whisper`。

## 当前阶段的最低验收标准

1. 片头和纯铺垫段显著减少，不再机械复述原片前奏。
2. 成片主体应集中在冲突、反转、情绪点、信息揭露和结局推进。
3. 最终脚本来源必须是筛选后的证据包，而不是所有剧情块。
4. 如果字幕质量足够好，成片应明显比原片顺叙更紧凑、更像解说视频。
