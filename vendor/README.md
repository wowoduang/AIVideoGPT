# Vendor Policy

> Updated on 2026-04-11.
> `vendor/` keeps third-party source only. Virtual environments, `AppData`, `work-dir`, ffmpeg caches, pytest caches, and similar runtime debris belong in the external workspace instead.

Recommended layout:

- Source: `vendor/<tool-name>/`
- Runtime: `workspace/runtime/third_party/<tool-name>/`
- Cache: `workspace/cache/<tool-name>/`

`vendor/` 只放第三方源码，不放运行时产物。

## 应该放这里

- 需要一起维护或打补丁的第三方源码
- 对主项目有直接依赖、希望固定版本的本地 vendor 副本

## 不应该放这里

- `.venv` / `.runtime_venv`
- `AppData`
- `work-dir`
- ffmpeg/pytest 临时缓存
- 运行期日志和中间文件

## 推荐搭配

- 第三方源码：`vendor/<tool-name>/`
- 第三方运行时：`workspace/runtime/third_party/<tool-name>/`
- 第三方缓存：`workspace/cache/<tool-name>/`
