from __future__ import annotations

import json
from typing import Dict, List

from loguru import logger

from app.services.prompts import PromptManager
from app.services.timeline_allocator import estimate_char_budget, fit_check, trim_text_to_budget
from app.utils import utils

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from app.services.llm.migration_adapter import generate_narration as legacy_generate_narration
except Exception:  # pragma: no cover
    legacy_generate_narration = None


STYLE_GUIDE = {
    "documentary": "客观、清楚、偏影视旁白口吻，避免夸张。",
    "short_drama": "更有悬念感和戏剧张力，但不能改事实。",
    "general": "自然口语化，信息清楚，像真人解说。",
    "analysis": "偏剧情分析，强调人物关系与因果，不要空话。",
    "short_video": "节奏更紧，句子更短，要有钩子但不能编造。",
    "default": "自然口语化，信息清楚，避免空话。",
}

STYLE_EXAMPLES = {
    "documentary": [
        "镜头推进到这里，人物关系已经开始悄悄失衡，后面的冲突其实早就埋下了伏笔。",
        "表面上这只是一次普通对话，但真正推动剧情的，是角色态度在这一刻出现了变化。",
    ],
    "short_drama": [
        "谁都没想到，这句看似随口的话，反而把真正的矛盾彻底撕开了。",
        "镜头一转，局面马上变了，前面还在强撑的人，这下终于藏不住了。",
    ],
    "general": [
        "这一段最关键的，不是台词本身，而是人物立场已经开始发生变化。",
        "表面上事情还没彻底爆发，但观众这时候已经能感觉到，后面的冲突躲不掉了。",
    ],
    "analysis": [
        "这一幕承担的叙事功能更像是信息揭露，它把前面隐约存在的矛盾正式摆到了台面上。",
        "如果把整段剧情放在一起看，这里其实是人物关系转向的第一处明确信号。",
    ],
    "short_video": [
        "别看这一段表面平静，真正的转折点，其实已经到了。",
        "一句话就把局势带偏了，后面会怎么炸开，观众这时候已经有预感了。",
    ],
}


def generate_narration(markdown_content: str, api_key: str, base_url: str, model: str) -> str:
    if legacy_generate_narration:
        return legacy_generate_narration(markdown_content, api_key, base_url, model)
    return ""


def _call_chat_completion(prompt: str, api_key: str, base_url: str, model: str) -> str:
    if not requests or not api_key or not base_url or not model:
        return ""
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.25,
        "messages": [
            {"role": "system", "content": "你是一个严格、可靠的中文影视解说助手。"},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("LLM 调用失败，回退规则文案: {}", exc)
        return ""


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
            return json.loads(raw[start:end + 1])
        except Exception:
            return None
    return None


def _fallback_narration(pkg: Dict, style: str, char_budget: int) -> Dict:
    real_state = (pkg.get("real_narrative_state") or "").strip()
    surface = (pkg.get("surface_dialogue_meaning") or "").strip()
    core = real_state or surface or (pkg.get("main_text_evidence") or pkg.get("subtitle_text") or "").strip()
    core = trim_text_to_budget(core or "这一段剧情继续推进。", char_budget)

    if style == "short_drama":
        if pkg.get("plot_function") in {"反转", "情感爆发"}:
            narration = f"关键时刻到了，{core}"
        else:
            narration = f"镜头一转，{core}"
    elif style == "analysis":
        narration = f"这一段更重要的是，{core}"
    else:
        narration = core

    risk_flags = pkg.get("narrative_risk_flags") or []
    if risk_flags:
        narration = narration.replace("一定", "像是").replace("就是", "似乎是")

    raw_voice_keep = bool(pkg.get("raw_voice_retain_suggestion"))
    if isinstance(pkg.get("story_validation"), dict):
        raw_voice_keep = bool(pkg["story_validation"].get("raw_voice_keep", raw_voice_keep))

    return {
        "narration": trim_text_to_budget(narration, char_budget),
        "raw_voice_keep": raw_voice_keep,
        "tone": pkg.get("emotion_hint") or "平静",
        "opening_type": "过渡",
        "risk_note": "；".join(risk_flags[:2]) if risk_flags else "",
    }


def _pick_ost(pkg: Dict, generation_result: Dict) -> int:
    if generation_result.get("raw_voice_keep"):
        return 1
    strategy = pkg.get("audio_strategy") or "duck"
    if strategy == "keep":
        return 1
    if pkg.get("block_type") == "visual" and pkg.get("importance_level") == "high":
        return 1
    return 2


def _build_script_item(idx: int, pkg: Dict, generation_result: Dict, picture: str, global_summary: Dict) -> Dict:
    narration = generation_result.get("narration") or ""
    start = float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0)
    end = float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or 0.0)
    if end <= start:
        end = start + 1.0
    duration = end - start
    planned_budget = int(pkg.get("planned_char_budget") or 0)
    base_budget = estimate_char_budget(duration)
    char_budget = max(planned_budget, min(base_budget + 12, int(base_budget * 1.25))) if planned_budget else base_budget
    canonical_timestamp = f"{utils.format_time(start)}-{utils.format_time(end)}"
    item = {
        "_id": idx,
        "timestamp": canonical_timestamp,
        "source_timestamp": pkg.get("timestamp") or canonical_timestamp,
        "picture": (picture or "").strip()[:80] or "画面推进",
        "narration": trim_text_to_budget((narration or "").strip(), char_budget),
        "OST": _pick_ost(pkg, generation_result),
        "evidence_refs": list(pkg.get("subtitle_ids") or []) + [pkg.get("segment_id")],
        "char_budget": char_budget,
        "emotion": pkg.get("emotion_hint") or "平静",
        "segment_id": pkg.get("segment_id"),
        "scene_id": pkg.get("scene_id"),
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(duration, 3),
        "plot_role": pkg.get("plot_role"),
        "plot_function": pkg.get("plot_function"),
        "attraction_level": pkg.get("attraction_level"),
        "importance_level": pkg.get("importance_level"),
        "narration_level": pkg.get("narration_level"),
        "confidence": pkg.get("confidence"),
        "global_arc": global_summary.get("arc"),
        "risk_note": generation_result.get("risk_note", ""),
        "validator_status": (pkg.get("story_validation") or {}).get("validator_status"),
    }
    item["fit_check"] = fit_check(item["narration"], duration)
    return item


def generate_narration_from_scene_evidence(
    scene_evidence: List[Dict],
    api_key: str,
    base_url: str,
    model: str,
    style: str = "documentary",
) -> List[Dict]:
    if not scene_evidence:
        return []

    global_summary = {}
    if scene_evidence and isinstance(scene_evidence[0].get("_global_summary"), dict):
        global_summary = scene_evidence[0]["_global_summary"]

    style_guide = STYLE_GUIDE.get(style, STYLE_GUIDE["default"])
    style_examples = "\n".join(f"- {x}" for x in STYLE_EXAMPLES.get(style, STYLE_EXAMPLES["general"]))

    script_items: List[Dict] = []
    for idx, pkg in enumerate(scene_evidence, start=1):
        start = float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0)
        end = float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or 0.0)
        duration = max(end - start, 0.1)
        char_budget = int(pkg.get("planned_char_budget") or estimate_char_budget(duration))
        pkg["char_budget"] = char_budget

        generation_result = {}
        if api_key and base_url and model:
            prompt = PromptManager.get_prompt(
                "movie_story_narration",
                "narration_generation",
                parameters={
                    "segment_json": json.dumps(
                        {
                            "segment_id": pkg.get("segment_id"),
                            "plot_function": pkg.get("plot_function"),
                            "importance_level": pkg.get("importance_level"),
                            "surface_dialogue_meaning": pkg.get("surface_dialogue_meaning"),
                            "real_narrative_state": pkg.get("real_narrative_state"),
                            "local_understanding": pkg.get("local_understanding"),
                            "story_validation": pkg.get("story_validation"),
                            "raw_voice_retain_suggestion": pkg.get("raw_voice_retain_suggestion"),
                            "emotion_hint": pkg.get("emotion_hint"),
                            "main_text_evidence": pkg.get("main_text_evidence") or pkg.get("subtitle_text"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "global_summary_json": json.dumps(global_summary or {}, ensure_ascii=False, indent=2),
                    "style_guide": style_guide,
                    "style_examples": style_examples,
                    "char_budget": char_budget,
                },
            )
            raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
            parsed = _extract_json_obj(raw)
            if isinstance(parsed, dict):
                generation_result = parsed

        if not generation_result:
            generation_result = _fallback_narration(pkg, style, char_budget)

        picture = pkg.get("picture") or "；".join(
            x.get("desc", "") for x in (pkg.get("visual_summary") or [])[:2]
        )
        script_items.append(_build_script_item(idx, pkg, generation_result, picture, global_summary or {}))

    return script_items
