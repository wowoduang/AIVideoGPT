import json
from typing import Any, Dict, List

from loguru import logger

from app.services.generate_narration_script import generate_narration


def build_subtitle_first_markdown(scene_evidence: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# 字幕优先视频理解材料")
    lines.append("以下内容已经按时间顺序切成多个场景。请以字幕内容为主理解剧情，画面帧只做辅助补充。")
    for idx, scene in enumerate(scene_evidence, start=1):
        lines.append(f"\n## 场景 {idx}")
        lines.append(f"- scene_id: {scene['scene_id']}")
        lines.append(f"- 时间范围: {scene['start']:.3f}-{scene['end']:.3f} 秒")
        lines.append(f"- 字幕内容: {scene.get('subtitle_text', '')}")
        frames = scene.get("frames", [])
        if frames:
            brief = ", ".join(f"{f['timestamp_seconds']:.2f}s" for f in frames)
            lines.append(f"- 代表帧时间点: {brief}")
        else:
            lines.append("- 代表帧时间点: 无")
    lines.append(
        "\n请输出严格 JSON，字段必须为 {\"items\": [{\"timestamp\": \"00:00:00,000-00:00:03,000\", \"picture\": \"...\", \"narration\": \"...\"}]}。"
    )
    lines.append("要求：timestamp 对应场景时间范围；narration 以字幕事实为主，语言口语化；picture 简述画面要点。")
    return "\n".join(lines)


def generate_subtitle_first_script(
    scene_evidence: List[Dict[str, Any]],
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> str:
    markdown = build_subtitle_first_markdown(scene_evidence)
    logger.info("使用字幕优先材料生成解说文案")
    return generate_narration(markdown, api_key, base_url, model)
