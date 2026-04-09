from __future__ import annotations

import json
from typing import Dict, List, Sequence

from app.services.llm_text_completion import call_text_chat_completion
from app.services.prompts import PromptManager


def _call_chat_completion(prompt: str, api_key: str = "", base_url: str = "", model: str = "") -> str:
    return call_text_chat_completion(
        prompt,
        api_key=api_key,
        model=model,
        base_url=base_url,
        system_prompt="你是严格、保守的影视剧情校核助手。",
        temperature=0.2,
        timeout=120,
        log_label="剧情校核 LLM",
    )


def _extract_json_obj(raw: str):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            return None
    return None


def _heuristic_review(pkg: Dict) -> Dict:
    flags = list(pkg.get("narrative_risk_flags") or [])
    issues: List[str] = []
    recommendations: List[str] = []

    if pkg.get("need_visual_verify"):
        issues.append("该段需要视觉核对")
        recommendations.append("优先查看代表帧确认人物与动作是否匹配")

    if flags:
        issues.append("字幕表层含义与真实剧情状态可能不一致")
        recommendations.append("生成解说时避免使用过度确定的表达")

    if pkg.get("plot_function") in {"情感爆发", "反转"} and pkg.get("importance_level") == "high":
        recommendations.append("可考虑保留部分原声增强情绪")

    if pkg.get("boundary_confidence") == "low":
        issues.append("边界置信度较低")
        recommendations.append("必要时扩大时间窗并二次核对边界")

    status = "pass"
    if issues:
        status = "review"
    if len(issues) >= 2:
        status = "risky"

    raw_voice_keep = bool(pkg.get("raw_voice_retain_suggestion")) or (
        pkg.get("plot_function") in {"情感爆发", "反转"} and pkg.get("importance_level") == "high"
    )
    return {
        "segment_id": pkg.get("segment_id"),
        "validator_status": status,
        "issues": issues,
        "recommendations": recommendations,
        "raw_voice_keep": raw_voice_keep,
    }


def validate_story_segments(
    scene_evidence: Sequence[Dict],
    global_summary: Dict,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> List[Dict]:
    items = [dict(x) for x in (scene_evidence or [])]
    if not items:
        return []

    light_segments = []
    for pkg in items:
        light_segments.append(
            {
                "segment_id": pkg.get("segment_id"),
                "start": pkg.get("start"),
                "end": pkg.get("end"),
                "plot_function": pkg.get("plot_function"),
                "importance_level": pkg.get("importance_level"),
                "surface_dialogue_meaning": pkg.get("surface_dialogue_meaning"),
                "real_narrative_state": pkg.get("real_narrative_state"),
                "boundary_confidence": pkg.get("boundary_confidence"),
                "narrative_risk_flags": pkg.get("narrative_risk_flags"),
                "raw_voice_retain_suggestion": pkg.get("raw_voice_retain_suggestion"),
            }
        )

    llm_reviews = {}
    if api_key and model:
        prompt = PromptManager.get_prompt(
            "movie_story_narration",
            "story_validation",
            parameters={
                "segments_json": json.dumps(light_segments, ensure_ascii=False, indent=2),
                "global_summary_json": json.dumps(global_summary or {}, ensure_ascii=False, indent=2),
            },
        )
        raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
        data = _extract_json_obj(raw)
        if isinstance(data, dict):
            for item in data.get("segment_reviews", []) or []:
                seg_id = item.get("segment_id")
                if seg_id:
                    llm_reviews[seg_id] = item

    for pkg in items:
        heuristic = _heuristic_review(pkg)
        llm_review = llm_reviews.get(pkg.get("segment_id"), {})
        merged = {
            "segment_id": pkg.get("segment_id"),
            "validator_status": llm_review.get("validator_status") or heuristic["validator_status"],
            "issues": list(dict.fromkeys((heuristic.get("issues") or []) + (llm_review.get("issues") or []))),
            "recommendations": list(
                dict.fromkeys((heuristic.get("recommendations") or []) + (llm_review.get("recommendations") or []))
            ),
            "raw_voice_keep": bool(llm_review.get("raw_voice_keep", heuristic.get("raw_voice_keep", False))),
        }
        pkg["story_validation"] = merged
        if merged["raw_voice_keep"]:
            pkg["raw_voice_retain_suggestion"] = True
        if merged["validator_status"] == "risky" and pkg.get("boundary_confidence") == "high":
            pkg["boundary_confidence"] = "medium"

    return items
