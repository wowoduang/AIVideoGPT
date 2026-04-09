# 粗剪编排主链代码设计

## 目标

把当前“字幕优先影视解说链路”升级为更通用的“粗剪编排主链”。

这个主链不把字幕当唯一入口，而是把字幕、视频分镜、已有解说词都视为可选信号源，最终统一产出可直接进入合成阶段的粗剪脚本。

适配两类核心场景：

1. 无解说精彩剪辑
2. 有解说的智能粗剪

## 核心原则

1. 主链以“粗剪编排”作为第一职责，不以“生成解说文案”作为第一职责。
2. 字幕是增强信息源，不是唯一主链。
3. 有解说和无解说最终都落到同一种时间轴脚本结构。
4. 优先生成“可继续编辑的粗剪结果”，不追求逐句语义强对齐。
5. 先保证时长、节奏、可看性，再逐步增强理解精度。

## 新架构

建议把系统主入口抽象为：

`highlight_edit_pipeline`

它下面包含两个主要模式：

1. `highlight_recut`
2. `narrated_highlight_edit`

以及三个可选输入分支：

1. `subtitle_signal_branch`
2. `visual_signal_branch`
3. `narration_signal_branch`

## 主链总流程

统一流程：

`输入 -> 信号抽取 -> 片段候选 -> 高光筛选 -> 时长分配 -> 粗剪脚本生成 -> 音频策略 -> 最终合成`

建议代码侧拆成下面这些阶段。

### E1 输入归一化

输入对象统一为 `EditRequest`：

```python
{
  "video_path": "原片路径",
  "mode": "highlight_recut | narrated_highlight_edit",
  "target_duration_seconds": 480,
  "movie_title": "电影名，可选",
  "subtitle_path": "字幕路径，可选",
  "subtitle_text": "字幕文本，可选",
  "narration_text": "外部解说词，可选",
  "narration_audio_path": "现成配音，可选",
  "prefer_raw_audio": True,
  "visual_mode": "off | auto | boost",
  "alignment_mode": "loose",
  "source_hints": {
    "use_subtitle": True,
    "use_visual": True,
    "use_external_narration": False
  }
}
```

这一层只做参数收敛，不做内容理解。

### E2 信号抽取

统一产出 `SignalPack`，供后续所有编排阶段消费。

```python
{
  "subtitle_segments": [],
  "scene_segments": [],
  "audio_beats": [],
  "speech_segments": [],
  "external_narration": {
    "text": "",
    "audio_path": ""
  },
  "metadata": {}
}
```

各分支职责：

1. `subtitle_signal_branch`
   使用已有 `build_subtitle_segments`，输出字幕段、对白密度、剧情文本线索。
2. `visual_signal_branch`
   复用 `detect_scenes_from_video`、`build_video_boundary_candidates` 等能力，输出镜头边界、场景区间、代表帧。
3. `narration_signal_branch`
   接收豆包生成的解说词、用户提供的文案，或后续系统内部生成的文案。

### E3 候选片段构建

统一生成 `CandidateClip` 列表。

```python
{
  "clip_id": "clip_001",
  "start": 12.3,
  "end": 28.4,
  "duration": 16.1,
  "source": "subtitle|scene|hybrid",
  "subtitle_text": "...",
  "scene_summary": "...",
  "energy_score": 0.0,
  "story_score": 0.0,
  "emotion_score": 0.0,
  "raw_audio_worthy": False,
  "tags": ["conflict", "reveal"]
}
```

这一步的重点不是写解说，而是把“可剪的片段池”建立起来。

建议：

1. 无解说模式下，候选片段以视频分段和字幕剧情块融合得到。
2. 有解说模式下，候选片段依然先独立生成，后面再跟解说段做弱匹配。

### E4 高光筛选

统一生成 `SelectedClip`。

筛选信号优先级建议：

1. 冲突升级
2. 反转揭示
3. 情绪爆发
4. 关键人物关系变化
5. 高信息密度对白
6. 明显低价值铺垫剔除

输出结构：

```python
{
  "clip_id": "clip_001",
  "selected": True,
  "score": 0.91,
  "selection_reason": ["reveal", "emotion_peak"],
  "suggested_audio_mode": "raw|ducked_raw|narration"
}
```

### E5 时长预算与压缩

这一步是粗剪系统最关键的编排层。

输入：

1. 候选高光片段
2. 目标总时长
3. 模式配置

输出：

1. 最终保留片段
2. 每段分配后的目标时长
3. 顺序与节奏

建议增加独立模块：

`app/services/highlight_timeline_planner.py`

职责：

1. 根据总时长决定保留多少段
2. 合并相邻高价值片段
3. 压缩低价值上下文
4. 为高潮段保留更长时长

### E6 粗匹配编排

这一层决定“解说怎么铺，画面怎么配”。

#### 模式 A：无解说精彩剪辑

直接生成画面时间轴：

```python
{
  "track_type": "video",
  "start": 120.0,
  "end": 136.0,
  "audio_mode": "raw"
}
```

只需要保证：

1. 片段顺序合理
2. 时长符合目标
3. 原声保留策略合理

#### 模式 B：有解说智能粗剪

先把解说文案拆成 `NarrationUnit`：

```python
{
  "unit_id": "n_01",
  "text": "主角原以为事情已经结束",
  "target_seconds": 4.2,
  "story_stage": "turning_point"
}
```

然后把 `NarrationUnit` 和 `SelectedClip` 做弱匹配：

1. 按剧情阶段匹配
2. 按人物/事件关键词匹配
3. 匹配不上时允许回退到通用高光镜头
4. 不做逐句严格对齐

建议增加模块：

`app/services/narrated_highlight_mapper.py`

输出统一的 `CompositionPlan`。

## 统一输出脚本

不管有无解说，最终都建议统一为 `CompositionPlan`：

```python
{
  "mode": "highlight_recut|narrated_highlight_edit",
  "video_path": "原片路径",
  "target_duration_seconds": 480,
  "segments": [
    {
      "segment_id": "seg_001",
      "video_start": 120.0,
      "video_end": 132.5,
      "timeline_start": 0.0,
      "timeline_end": 12.5,
      "audio_mode": "raw|ducked_raw|tts|mute",
      "narration_text": "",
      "narration_audio_path": "",
      "selection_reason": ["reveal"],
      "source_clip_id": "clip_001"
    }
  ],
  "audio_tracks": {
    "bgm_path": "",
    "narration_path": "",
    "keep_raw_audio": True
  }
}
```

这样后面的合成层就不需要关心“这是字幕链、剧情链还是解说链”。

## 与现有代码的映射

### 可以直接复用

1. `app/services/subtitle_pipeline.py`
   作为 `subtitle_signal_branch`
2. `app/services/scene_builder.py`
   作为 `visual_signal_branch`
3. `app/services/plot_chunker.py`
   用于从字幕和边界构建剧情候选块
4. `app/services/representative_frames.py`
   作为视觉摘要支撑
5. `app/services/video.py`
   继续作为最终合成执行层
6. `app/services/task.py`
   继续作为任务编排层，但输入建议逐步切换为 `CompositionPlan`

### 不再适合作为唯一总线

1. `app/services/subtitle_first_pipeline.py`

它更适合降级为：

`highlight_edit_pipeline` 的一个实现分支，名称上可理解为：

`highlight_edit_from_subtitles`

### 建议新增模块

1. `app/services/highlight_edit_pipeline.py`
   新总入口，负责模式分发和统一输出
2. `app/services/highlight_signal_builder.py`
   汇总字幕、分镜、音频、外部解说等信号
3. `app/services/highlight_selector.py`
   统一高光筛选
4. `app/services/highlight_timeline_planner.py`
   做总时长预算、压缩、合并、节奏分配
5. `app/services/narrated_highlight_mapper.py`
   解说段到视频段的弱匹配
6. `app/models/highlight_edit_schema.py`
   放 `EditRequest`、`SignalPack`、`CandidateClip`、`CompositionPlan`

## 推荐实现顺序

### 第一步

先做无解说精彩剪辑主链：

`video -> scene/subtitle signals -> selected clips -> timeline planner -> composition plan -> export`

原因：

1. 不依赖 TTS
2. 不依赖文案生成
3. 更适合你说的“精彩原片压缩”
4. 更容易先验证高光筛选和时长控制是否有效

### 第二步

再接有解说粗剪：

`narration text -> narration units -> loose clip mapping -> composition plan -> export`

这样豆包生成解说词就可以直接接进来。

### 第三步

最后才补强匹配质量：

1. 人物识别增强
2. 情节阶段理解增强
3. 句级对齐增强
4. 自动避错镜头增强

## MVP 定义

### MVP-1 无解说粗剪

必须做到：

1. 输入原片视频
2. 自动找到一批高光片段
3. 按目标时长输出精彩版粗剪脚本
4. 保留原声并可直接导出

### MVP-2 有解说粗剪

必须做到：

1. 输入原片视频和现成解说词
2. 自动拆分解说节奏
3. 给每段解说找到大致可用的原片镜头
4. 输出能直接合成的视频脚本

## 一句话结论

后续代码设计不应继续围绕“字幕优先主链”展开，而应围绕“粗剪编排主链”展开；字幕链、剧情链、外部解说链都只是它的输入分支，最终统一落到同一种粗剪合成脚本结构。
