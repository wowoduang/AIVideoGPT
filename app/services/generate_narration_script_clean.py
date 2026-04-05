from __future__ import annotations

import json
from typing import Dict, List

from loguru import logger

from app.services.prompts import PromptManager
from app.services.timeline_allocator import apply_timeline_budget, estimate_char_budget, fit_check, trim_text_to_budget
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
    "general": "自然口语化，信息清晰，像真人解说。",
    "analysis": "偏剧情分析，强调人物关系与因果，不要空话。",
    "short_video": "节奏更紧，句子更短，要有钩子但不能编造。",
    "default": "自然口语化，信息清晰，避免空话。",
}

STYLE_EXAMPLES = {
    "documentary": [
        "镜头推进到这里，人物关系已经开始悄悄失衡，后面的冲突其实早就埋下了伏笔。",
        "表面上这只是一场普通对话，但真正推动剧情的，是角色态度在这一刻发生了变化。",
    ],
    "short_drama": [
        "谁都没想到，这句看似随口的话，反而把真正的矛盾彻底撕开了。",
        "镜头一转，局面马上变了，前面还在硬撑的人，这下终于藏不住了。",
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
        url += "/chat/completions"
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
            return json.loads(raw[start : end + 1])
        except Exception:
            return None
    return None


def _validate_generated_narration(
    pkg: Dict,
    narration: str,
    raw_voice_keep: bool,
    api_key: str,
    base_url: str,
    model: str,
) -> Dict:
    fallback = {
        "status": "pass",
        "issues": [],
        "safe_rewrite_hint": "",
        "raw_voice_keep": raw_voice_keep,
    }
    if not (requests and api_key and base_url and model and narration.strip()):
        return fallback

    prompt = PromptManager.get_prompt(
        "movie_story_narration",
        "narration_validation",
        parameters={
            "segment_json": json.dumps(
                {
                    "segment_id": pkg.get("segment_id"),
                    "plot_function": pkg.get("plot_function"),
                    "importance_level": pkg.get("importance_level"),
                    "surface_dialogue_meaning": pkg.get("surface_dialogue_meaning"),
                    "real_narrative_state": pkg.get("real_narrative_state"),
                    "story_validation": pkg.get("story_validation"),
                    "local_understanding": pkg.get("local_understanding"),
                    "main_text_evidence": pkg.get("main_text_evidence") or pkg.get("subtitle_text"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "generated_narration": narration.strip(),
        },
    )
    raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
    parsed = _extract_json_obj(raw)
    if isinstance(parsed, dict):
        result = dict(fallback)
        result.update({k: v for k, v in parsed.items() if v not in (None, "", [], {})})
        result["raw_voice_keep"] = bool(parsed.get("raw_voice_keep", raw_voice_keep))
        return result
    return fallback


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

    raw_voice_keep = bool(pkg.get("llm_raw_voice_keep"))
    if isinstance(pkg.get("story_validation"), dict):
        raw_voice_keep = bool(pkg["story_validation"].get("raw_voice_keep", raw_voice_keep))
    if not raw_voice_keep:
        raw_voice_keep = bool(
            pkg.get("raw_voice_retain_suggestion")
            and str(pkg.get("importance_level") or "") == "high"
            and str(pkg.get("plot_function") or "") in {"反转", "情感爆发", "结局收束"}
        )

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
    if pkg.get("llm_raw_voice_keep"):
        return 1
    strategy = pkg.get("audio_strategy") or "duck"
    if strategy == "keep" and str(pkg.get("importance_level") or "") == "high" and str(pkg.get("plot_function") or "") in {"反转", "情感爆发", "结局收束"}:
        return 1
    if pkg.get("block_type") == "visual" and pkg.get("importance_level") == "high" and pkg.get("llm_highlight_selected"):
        return 1
    return 2


def _normalize_generated_narration(narration: str, pkg: Dict, char_budget: int) -> str:
    text = (narration or "").strip()
    plot_function = str(pkg.get("plot_function") or "")
    importance = str(pkg.get("importance_level") or "medium")
    validator_status = str((pkg.get("story_validation") or {}).get("validator_status") or "pass")

    effective_budget = int(char_budget)
    if plot_function in {"铺垫", "节奏缓冲"}:
        effective_budget = max(12, int(char_budget * 0.72))
    elif importance == "low":
        effective_budget = max(12, int(char_budget * 0.8))

    if validator_status == "review":
        effective_budget = max(12, min(effective_budget, char_budget - 4))

    return trim_text_to_budget(text, effective_budget)


def _should_merge_context_items(left: Dict, right: Dict) -> bool:
    left_end = float(left.get("end", 0.0) or 0.0)
    right_start = float(right.get("start", left_end) or left_end)
    gap = right_start - left_end
    if gap > 0.8:
        return False

    left_importance = str(left.get("importance_level") or "medium")
    right_importance = str(right.get("importance_level") or "medium")
    left_plot = str(left.get("plot_function") or "")
    right_plot = str(right.get("plot_function") or "")
    left_duration = float(left.get("duration", 0.0) or 0.0)
    right_duration = float(right.get("duration", 0.0) or 0.0)
    same_ost = int(left.get("OST", 2) or 2) == int(right.get("OST", 2) or 2)

    weak_left = left_importance == "low" or left_plot in {"铺垫", "节奏缓冲"}
    weak_right = right_importance == "low" or right_plot in {"铺垫", "节奏缓冲"}
    short_pair = left_duration <= 10.0 and right_duration <= 10.0
    return weak_left and weak_right and short_pair and same_ost


def _merge_script_items(left: Dict, right: Dict) -> Dict:
    merged = dict(left)
    merged_end = round(float(right.get("end", merged.get("end", 0.0)) or merged.get("end", 0.0)), 3)
    merged["end"] = merged_end
    merged["duration"] = round(max(merged_end - float(merged.get("start", 0.0) or 0.0), 0.1), 3)
    merged["timestamp"] = f"{utils.format_time(float(merged.get('start', 0.0) or 0.0))}-{utils.format_time(merged_end)}"
    merged["source_timestamp"] = merged["timestamp"]
    merged["picture"] = (str(merged.get("picture") or "") + "；" + str(right.get("picture") or "")).strip("；")[:80]
    merged["narration"] = trim_text_to_budget(
        f"{str(merged.get('narration') or '').strip()}，{str(right.get('narration') or '').strip()}".strip("，"),
        max(int(merged.get("char_budget") or 0) + int(right.get("char_budget") or 0), 20),
    )
    merged["evidence_refs"] = list(dict.fromkeys(list(merged.get("evidence_refs") or []) + list(right.get("evidence_refs") or [])))
    merged["segment_id"] = f"{merged.get('segment_id')}+{right.get('segment_id')}"
    merged["scene_id"] = merged["segment_id"]
    if str(right.get("importance_level") or "") == "high":
        merged["plot_function"] = right.get("plot_function")
        merged["importance_level"] = right.get("importance_level")
    elif "medium" in {str(merged.get("importance_level") or ""), str(right.get("importance_level") or "")}:
        merged["importance_level"] = "medium"
    if "review" in {str(merged.get("validator_status") or ""), str(right.get("validator_status") or "")}:
        merged["validator_status"] = "review"
    return merged


def _postprocess_script_items(items: List[Dict]) -> List[Dict]:
    if not items:
        return []

    ordered = sorted((dict(item) for item in items), key=lambda x: (float(x.get("start", 0.0) or 0.0), int(x.get("_id", 0) or 0)))
    merged: List[Dict] = []
    for item in ordered:
        if merged and _should_merge_context_items(merged[-1], item):
            merged[-1] = _merge_script_items(merged[-1], item)
        else:
            merged.append(item)

    for idx, item in enumerate(merged, start=1):
        item["_id"] = idx

    return apply_timeline_budget(merged, auto_trim=True)


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
        "narration": _normalize_generated_narration((narration or "").strip(), pkg, char_budget),
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
        "llm_highlight_selected": bool(pkg.get("llm_highlight_selected")),
        "llm_raw_voice_keep": bool(pkg.get("llm_raw_voice_keep")),
        "semantic_timestamp": pkg.get("semantic_timestamp") or pkg.get("timestamp") or canonical_timestamp,
        "narration_validation": generation_result.get("narration_validation") or {},
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
        else:
            validation = _validate_generated_narration(
                pkg,
                generation_result.get("narration", ""),
                bool(generation_result.get("raw_voice_keep")),
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            generation_result["narration_validation"] = validation
            if validation.get("status") == "reject":
                generation_result = _fallback_narration(pkg, style, char_budget)
                generation_result["risk_note"] = (
                    f"{generation_result.get('risk_note', '')}；"
                    f"narration_rejected:{';'.join(validation.get('issues') or [])}"
                ).strip("；")
            elif validation.get("status") == "review":
                safer = str(validation.get("safe_rewrite_hint") or "").strip()
                if safer:
                    generation_result["narration"] = trim_text_to_budget(safer, char_budget)
                else:
                    generation_result["narration"] = trim_text_to_budget(
                        generation_result.get("narration", ""),
                        max(12, int(char_budget * 0.82)),
                    )
                generation_result["raw_voice_keep"] = bool(validation.get("raw_voice_keep", generation_result.get("raw_voice_keep")))
                generation_result["risk_note"] = (
                    f"{generation_result.get('risk_note', '')}；"
                    f"narration_review:{';'.join(validation.get('issues') or [])}"
                ).strip("；")

        picture = pkg.get("picture") or "；".join(x.get("desc", "") for x in (pkg.get("visual_summary") or [])[:2])
        script_items.append(_build_script_item(idx, pkg, generation_result, picture, global_summary or {}))

    return _postprocess_script_items(script_items)
