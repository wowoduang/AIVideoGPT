# Project Layout

> Updated on 2026-04-12.
> Canonical rule: the repository keeps source code and static assets only. Generated videos, subtitles, scripts, caches, runtime files, and task outputs must go to the external workspace.
> The workspace root can live on any drive and can be set by `app.workspace_root`, `NARRATO_WORKSPACE_ROOT`, or the `--workspace-root` flag on `tools/clean_workspace.py` and `tools/migrate_workspace.py`.

Quick reference:

- Source code: `app/`, `webui/`, `tools/`, `vendor/`, `tests/`, static files under `resource/`
- UI service layer: `webui/services/` keeps Streamlit-side orchestration helpers out of page layout files
- Script persistence helpers: `webui/services/script_persistence.py` centralizes script load/save behavior outside page files
- Local API entrypoint: `local_api.py`, backed by `app/api/`
- Local API default address: `http://127.0.0.1:18000` unless overridden by `app.local_api_base_url` or `app.local_api_host` / `app.local_api_port`
- External workspace: `models/`, `videos/`, `subtitles/`, `scripts/`, `analysis/`, `fonts/`, `songs/`, `temp/`, `cache/`, `runtime/`, `state/`, `tasks/`
- Local config files: prefer `workspace/state/config.toml` and `workspace/state/webui.toml`; legacy repo-root `config.toml` and `.streamlit/webui.toml` are compatibility fallbacks only
- Third-party runtime: `workspace/runtime/third_party/<tool-name>/`
- Third-party cache: `workspace/cache/<tool-name>/`

Model placement:

- Local model weights should live in `workspace/models/`, not in `app/models/`.
- Runtime lookup already prefers `workspace/models/<model-name>` and keeps `app/models/<model-name>` only as a compatibility fallback.
- Move legacy model folders with `python tools/migrate_workspace.py --apply`.
- If a cloned model directory carries its own `.git` history, clean that metadata with `python tools/clean_workspace.py --apply --include-model-vcs`.

Analysis placement:

- Analysis artifacts should live in `workspace/analysis/`, not at the workspace root.
- Recommended subfolders: `workspace/analysis/json/`, `workspace/analysis/narration_scripts/`, `workspace/analysis/drama_analysis/`.
- `tools/migrate_workspace.py --apply` will also move legacy `json/`, `narration_scripts/`, and `drama_analysis/` folders into `analysis/`.

`AIVideoGPT` 现在按“源码 / 第三方源码 / 工作区产物”三层来整理，后面重做 UI 时也建议继续沿用这个边界。

## 目录职责

- `app/`
  - 业务服务、模型、配置与底层能力。
  - 后续新 UI 应尽量直接复用这里的服务层，而不是自己拼路径或维护缓存。
- `webui/`
  - 当前 Streamlit 界面层。
  - 尽量保持薄，不再承担运行时目录规划这类基础设施职责。
- `vendor/`
  - 第三方源码统一放这里。
  - 这里只放源码，不放 `.venv`、`AppData`、`work-dir`、ffmpeg 临时缓存等运行时垃圾。
- `tools/`
  - 仓库维护脚本统一放这里，例如清理工作区、迁移脚本、诊断脚本。
- `resource/`
  - 只保留项目静态资源与源码级资源。
  - 用户视频、字幕、脚本、字体、歌曲等工作数据不再建议放这里。
- `storage/`
  - 旧版仓库内工作区。
  - 现在默认工作区已改为项目同级目录 `../AIVideoGPT-workspace`，也可通过 `app.workspace_root` 或环境变量 `NARRATO_WORKSPACE_ROOT` 覆盖。

## 工作区结构

默认工作区会拆成这些子目录：

- `../AIVideoGPT-workspace/videos/`
  - 输入视频与下载视频素材。
- `../AIVideoGPT-workspace/subtitles/`
  - 输入字幕和持久化字幕产物。
- `../AIVideoGPT-workspace/scripts/`
  - 剧本、规划结果、审计脚本等产物。
- `../AIVideoGPT-workspace/fonts/`
  - 本地字体资源。
- `../AIVideoGPT-workspace/songs/`
  - 本地 BGM 资源。
- `../AIVideoGPT-workspace/temp/`
  - 短期临时文件，可直接清理。
- `../AIVideoGPT-workspace/cache/`
  - 可重建缓存，例如 TTS 缓存、素材下载缓存。
- `../AIVideoGPT-workspace/runtime/`
  - 运行时状态与第三方工具运行目录，例如 `VideoCaptioner` 的 `AppData`。
- `../AIVideoGPT-workspace/state/`
  - 本地用户状态，例如 UI 配置快照。
- `../AIVideoGPT-workspace/tasks/`
  - 任务输出与阶段产物，是否清理要按业务需要决定。
- `../AIVideoGPT-workspace/models/`
  - 本地模型权重，例如 `faster-whisper-large-v2` / `faster-whisper-large-v3`。

## 当前整理约定

- `VideoCaptioner` 的运行时目录不再塞进源码目录，统一走 `../AIVideoGPT-workspace/runtime/third_party/videocaptioner/`。
- TTS 缓存改到 `../AIVideoGPT-workspace/cache/tts_cache/`。
- 下载素材缓存改到 `../AIVideoGPT-workspace/cache/materials/`。
- 用户设置改到 `../AIVideoGPT-workspace/state/user_settings/`。
- `videos / subtitles / scripts / fonts / songs` 默认都走项目外工作区。
- 大模型权重也应放在 `workspace/models/`，不再放在 `app/models/` 里混着源码。
- 根目录遗留的 `AppData/`、`MagicMock/`、`pytest-cache-files-*` 视为待清理脏目录。

## 清理方式

使用顶层脚本：

```powershell
python tools/clean_workspace.py
python tools/clean_workspace.py --apply
python tools/clean_workspace.py --apply --include-vendor-runtime
python tools/clean_workspace.py --apply --include-tasks
python tools/migrate_workspace.py
python tools/migrate_workspace.py --apply
```

默认只预览，不会删除文件。

## 后续建议

- 重做 UI 时，把新 UI 当成独立展示层，只调 `app/services`，不要再在 UI 里散落路径规则。
- 如果决定长期维护某个第三方工具，优先把源码放到 `vendor/`，运行时环境放到 `workspace/runtime/third_party/`。
- 对“效果好的版本”除了打 Git tag，也建议同时保存对应 `subtitle/script/audit` 产物，形成可回放 baseline。
