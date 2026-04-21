# 阿里云百炼 ASR 使用说明

## 简介

NarratoAI 现已支持阿里云百炼平台的云端 ASR 服务：
- **Qwen3-ASR-Flash**: 短音频同步识别（最长 5 分钟，最大 10MB）
- **Qwen3-ASR-Flash-Filetrans**: 长音频异步识别（最长 12 小时，最大 2GB）
- **Fun-ASR**: 阿里通义语音识别大模型

## 配置方法

### 1. 获取 API Key

1. 登录 [阿里云百炼平台](https://bailian.console.aliyun.com/)
2. 创建 API Key
3. 复制 Key 用于配置

### 2. 配置 API Key

**方式一：环境变量（推荐）**
```bash
set DASHSCOPE_API_KEY=your-api-key-here
```

**方式二：config.toml**
```toml
[tts_qwen]
api_key = "your-api-key-here"
```

### 3. 选择 ASR 后端

编辑 `config.toml`：

```toml
[whisper]
# 使用百炼 ASR
backend = "bailian"

# 选择模型
bailian_model = "qwen3-asr-flash"  # 短音频快速识别
# bailian_model = "qwen3-asr-flash-filetrans"  # 长音频异步识别
# bailian_model = "fun-asr"  # Fun-ASR 大模型
```

## 使用方式

### WebUI 界面

在 WebUI 的字幕设置中选择：
- 字幕来源: "自动识别"
- ASR 后端会自动使用配置的 backend

### API 调用

```python
from app.services.subtitle import create

# 使用百炼 ASR 生成字幕
subtitle_file = create(
    audio_file="path/to/audio.wav",
    backend_override="bailian",
    model_override="qwen3-asr-flash"  # 可选
)
```

### 直接使用百炼服务

```python
from app.services.asr_bailian import recognize_with_bailian

segments = recognize_with_bailian(
    audio_path="path/to/audio.wav",
    model="qwen3-asr-flash",
    language="zh"
)

for seg in segments:
    print(f"[{seg['start']:.2f} - {seg['end']:.2f}] {seg['text']}")
```

## 模型对比

| 模型 | 时长限制 | 特点 | 适用场景 |
|------|----------|------|----------|
| qwen3-asr-flash | ≤5分钟 | 同步返回，速度快 | 短视频、实时字幕 |
| qwen3-asr-flash-filetrans | ≤12小时 | 异步处理，精度高 | 长视频、电影 |
| fun-asr | ≤5分钟 | 多语言、方言支持好 | 多语种内容 |

## 大文件处理（GB 级视频）

对于 GB 级别的大视频文件，系统支持**自动分片识别**：

### 自动分片流程

1. **音频提取**: 从视频中提取音频轨道
2. **智能分片**: 按 5 分钟一段分割（每段 < 10MB）
3. **并行识别**: 逐段调用百炼 ASR 接口
4. **结果合并**: 自动合并时间戳，输出完整字幕

### 使用方式

无需额外配置，直接使用即可：

```python
from app.services.subtitle import create

# 传入大视频文件，自动分片处理
subtitle_file = create(
    audio_file="path/to/large_video.mp4",  # 可以是 GB 级视频
    backend_override="bailian"
)
```

### 依赖要求

需要安装 ffmpeg：

```bash
# Windows
choco install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### 性能参考

| 视频时长 | 文件大小 | 预估处理时间 |
|----------|----------|--------------|
| 30 分钟 | 500MB | 3-5 分钟 |
| 1 小时 | 1GB | 6-10 分钟 |
| 2 小时 | 2GB | 12-20 分钟 |

*处理时间取决于网络速度和视频内容复杂度*

## 注意事项

1. **文件大小**: 单段限制 10MB，大文件会自动分片
2. **网络要求**: 需要能访问阿里云百炼服务
3. **费用**: 按调用量计费，分片后每段都计费
4. **ffmpeg**: 大文件处理需要系统安装 ffmpeg

## 故障排查

### API Key 错误
```
ValueError: 百炼 API Key 未配置
```
解决方案：配置 `DASHSCOPE_API_KEY` 环境变量或在 config.toml 中设置

### 文件过大错误（旧版本）
```
ValueError: 文件大小 X.XXMB 超过 10MB 限制
```
解决方案：更新到最新代码，已支持自动分片

### ffmpeg 未找到
```
RuntimeError: 无法获取音频时长
```
解决方案：安装 ffmpeg 并添加到系统 PATH

### 网络错误
```
requests.exceptions.RequestException
```
解决方案：检查网络连接，确认能访问阿里云百炼服务
