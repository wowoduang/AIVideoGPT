from __future__ import annotations

import json
import re
from typing import Dict, List, Sequence

from loguru import logger

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

from app.services.prompts import PromptManager


NAME_PATTERNS = [
    re.compile(r"[《“\"]([^》”\"]{1,10})[》”\"]"),
    re.compile(r"\b[A-Z][a-z]{1,20}\b"),
]
EMOTION_CUES = {
    "愤怒": ["恨", "滚", "闭嘴", "骗子", "混蛋"],
    "悲伤": ["哭", "泪", "难过", "别走", "对不起"],
    "喜悦": ["笑", "高兴", "终于", "太好了", "成功了"],
    "紧张": ["快", "危险", "小心", "糟了", "来不及"],
    "惊讶": ["什么", "怎么会", "居然", "没想到", "不可能"],
    "恐惧": ["别过来", "救命", "害怕", "不要", "快跑"],
}


def _call_chat_completion(prompt: str, api_key: str = "", base_url: str = "", model: str = "") -> str:
    if not (requests and api_key and base_url and model):
        return ""
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "你是严格、保守的中文影视剧情理解助手。"},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.warning("剧情理解 LLM 调用失败，回退规则摘要: {}", exc)
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


def _extract_names(text: str) -> List[str]:
    found: List[str] = []
    for pattern in NAME_PATTERNS:
        for item in pattern.findall(text or ""):
            if item and item not in found:
                found.append(item)
    return found[:8]


def _format_ts(seconds: float) -> str:
    total_ms = int(round(max(float(seconds or 0.0), 0.0) * 1000.0))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _parse_ts(raw: str) -> float | None:
    text = str(raw or "").strip()
    if not text:
        return None
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})(?:,(\d{1,3}))?$", text)
    if not m:
        return None
    hh, mm, ss, ms = m.groups()
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int((ms or "0").ljust(3, "0")) / 1000.0


def _build_subtitle_timeline_digest(segments: Sequence[Dict], max_chars: int = 220, max_windows: int = 180) -> str:
    windows: List[str] = []
    bucket: List[str] = []
    start = None
    end = None
    bucket_chars = 0

    for seg in segments or []:
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        seg_start = float(seg.get("start", 0.0) or 0.0)
        seg_end = float(seg.get("end", seg_start) or seg_start)
        piece = text.replace("\n", " ").strip()
        if start is None:
            start = seg_start
        projected = bucket_chars + len(piece)
        if bucket and projected > max_chars:
            windows.append(f"[{_format_ts(start)}-{_format_ts(end or start)}] {' '.join(bucket)}")
            bucket = []
            bucket_chars = 0
            start = seg_start
        bucket.append(piece)
        bucket_chars += len(piece)
        end = seg_end

    if bucket and start is not None:
        windows.append(f"[{_format_ts(start)}-{_format_ts(end or start)}] {' '.join(bucket)}")

    if len(windows) > max_windows:
        stride = max(1, len(windows) // max_windows)
        windows = windows[::stride][:max_windows]
    return "\n".join(windows)


def _key_dialogues(text: str, max_items: int = 2) -> List[str]:
    if not text:
        return []
    pieces = re.split(r"[。！？?\n]", text)
    out = []
    for piece in pieces:
        piece = piece.strip(" ，、；：")
        if len(piece) >= 4:
            out.append(piece[:28])
        if len(out) >= max_items:
            break
    return out


def _emotion(text: str, visual: List[Dict] | None = None) -> str:
    joined = (text or "") + " " + " ".join(x.get("desc", "") for x in (visual or []))
    for label, cues in EMOTION_CUES.items():
        if any(c in joined for c in cues):
            return label
    return "平静"


def _core_event(text: str) -> str:
    dialogs = _key_dialogues(text, max_items=1)
    if dialogs:
        return dialogs[0][:20]
    return (text or "剧情继续推进")[:20]


def _heuristic_global_summary(items: Sequence[Dict]) -> Dict:
    full_text = " ".join(
        (x.get("aligned_subtitle_text") or x.get("subtitle_text") or x.get("main_text_evidence") or "") for x in items
    )
    names = _extract_names(full_text)
    protagonist = names[0] if names else "主角"
    key_segments = [x.get("segment_id") for x in items if x.get("importance_level") == "high"][:10]
    main_events = []
    for item in items[:8]:
        text = (item.get("aligned_subtitle_text") or item.get("subtitle_text") or item.get("main_text_evidence") or "").strip()
        if text:
            main_events.append(_core_event(text))
    return {
        "protagonist": protagonist,
        "main_storyline": "，".join(main_events[:4])[:90] or "故事围绕主角的冲突与转折推进。",
        "character_relations": [{"a": protagonist, "relation": "关联人物", "b": n} for n in names[1:4]],
        "core_conflicts": _key_dialogues(full_text, max_items=4),
        "timeline_progression": main_events[:5],
        "unresolved_tensions": _key_dialogues(full_text, max_items=5),
        "narrative_risk_flags": [],
        "entity_map": {n: n for n in names},
        "arc": items[-1].get("plot_role", "development") if items else "development",
        "key_segments": [x for x in key_segments if x],
    }


def build_global_summary(
    evidence_list: List[Dict],
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> Dict:
    if not evidence_list:
        return {
            "protagonist": "主角",
            "main_storyline": "",
            "character_relations": [],
            "core_conflicts": [],
            "timeline_progression": [],
            "unresolved_tensions": [],
            "narrative_risk_flags": [],
            "entity_map": {},
            "arc": "unknown",
            "key_segments": [],
        }

    summary = _heuristic_global_summary(evidence_list)
    text_lines = []
    for item in evidence_list[:60]:
        text = (item.get("aligned_subtitle_text") or item.get("subtitle_text") or item.get("main_text_evidence") or "").strip()
        if text:
            text_lines.append(
                f"[{item.get('segment_id')}] {item.get('plot_function', '信息揭露')} {item.get('importance_level', 'medium')}: {text[:120]}"
            )

    prompt = PromptManager.get_prompt(
        "movie_story_narration",
        "global_understanding",
        parameters={"subtitle_digest": "\n".join(text_lines)},
    )
    raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
    data = _extract_json_obj(raw)
    if isinstance(data, dict):
        summary.update({k: v for k, v in data.items() if v is not None})

    logger.info("全局剧情理解完成: protagonist={}, key_segments={}", summary.get("protagonist"), len(summary.get("key_segments", [])))
    return summary


def build_full_subtitle_understanding(
    subtitle_segments: List[Dict],
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> Dict:
    digest = _build_subtitle_timeline_digest(subtitle_segments)
    fallback = {
        "story_arc": "",
        "prologue_end_time": "",
        "major_turning_points": [],
        "highlight_windows": [],
        "selection_policy": {
            "must_keep_categories": ["反转", "情感爆发", "冲突升级", "结局收束"],
            "avoid_categories": ["片头铺垫", "弱过渡", "日常寒暄"],
        },
        "narrative_risk_flags": [],
        "subtitle_timeline_digest": digest,
    }
    if not (api_key and base_url and model and digest):
        return fallback

    prompt = PromptManager.get_prompt(
        "movie_story_narration",
        "full_subtitle_understanding",
        parameters={"subtitle_timeline_digest": digest},
    )
    raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
    parsed = _extract_json_obj(raw)
    if isinstance(parsed, dict):
        merged = dict(fallback)
        merged.update({k: v for k, v in parsed.items() if v not in (None, "", [], {})})
        merged["subtitle_timeline_digest"] = digest
        return merged
    return fallback


def plan_story_highlights(
    evidence_list: List[Dict],
    global_summary: Dict,
    full_subtitle_summary: Dict,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> Dict:
    fallback = {
        "selected_segment_ids": [],
        "rejected_segment_ids": [],
        "raw_voice_segment_ids": [],
        "must_keep_ranges": list(full_subtitle_summary.get("highlight_windows") or []),
        "selection_notes": [],
    }
    if not evidence_list:
        return fallback

    candidates = []
    for pkg in evidence_list:
        text = str(pkg.get("subtitle_text") or pkg.get("main_text_evidence") or "").strip()
        candidates.append(
            {
                "segment_id": pkg.get("segment_id"),
                "start": _format_ts(float(pkg.get("start", 0.0) or 0.0)),
                "end": _format_ts(float(pkg.get("end", 0.0) or 0.0)),
                "plot_function": pkg.get("plot_function"),
                "importance_level": pkg.get("importance_level"),
                "boundary_confidence": pkg.get("boundary_confidence"),
                "validator_status": (pkg.get("story_validation") or {}).get("validator_status", "pass"),
                "raw_voice_retain_suggestion": bool(pkg.get("raw_voice_retain_suggestion")),
                "need_visual_verify": bool(pkg.get("need_visual_verify")),
                "text": text[:180],
            }
        )

    if not (api_key and base_url and model):
        return fallback

    prompt = PromptManager.get_prompt(
        "movie_story_narration",
        "highlight_selection",
        parameters={
            "global_summary_json": json.dumps(global_summary or {}, ensure_ascii=False, indent=2),
            "full_subtitle_summary_json": json.dumps(full_subtitle_summary or {}, ensure_ascii=False, indent=2),
            "scene_candidates_json": json.dumps(candidates, ensure_ascii=False, indent=2),
        },
    )
    raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
    parsed = _extract_json_obj(raw)
    if isinstance(parsed, dict):
        merged = dict(fallback)
        merged.update({k: v for k, v in parsed.items() if v not in (None, "", [], {})})
        return merged
    return fallback


def _heuristic_local_understanding(pkg: Dict, global_summary: Dict) -> Dict:
    text = (pkg.get("subtitle_text") or pkg.get("main_text_evidence") or pkg.get("aligned_subtitle_text") or "").strip()
    chars = _extract_names(text)
    plot_function = pkg.get("plot_function") or "信息揭露"
    risk_flags: List[str] = []

    if "回忆" in text or "当年" in text:
        risk_flags.append("可能存在回忆或闪回")
    if "其实" in text or "原来" in text:
        risk_flags.append("可能存在表层信息反转")
    if pkg.get("need_visual_verify"):
        risk_flags.append("需要视觉证据辅助判断")

    return {
        "characters": chars,
        "core_event": _core_event(text),
        "key_dialogue": _key_dialogues(text),
        "emotion": _emotion(text, pkg.get("visual_summary") or []),
        "surface_dialogue_meaning": text[:80],
        "real_narrative_state": text[:80],
        "plot_function": plot_function,
        "importance_level": pkg.get("importance_level", "medium"),
        "need_visual_verify": bool(pkg.get("need_visual_verify")),
        "raw_voice_retain_suggestion": bool(pkg.get("raw_voice_retain_suggestion")),
        "boundary_confidence": pkg.get("boundary_confidence", "medium"),
        "boundary_reasons": list(pkg.get("boundary_reasons") or []),
        "narrative_risk_flags": risk_flags,
        "validator_hints": [],
    }


def add_local_understanding(
    evidence_list: List[Dict],
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> List[Dict]:
    if not evidence_list:
        return []

    global_summary = evidence_list[0].get("_global_summary") if isinstance(evidence_list[0].get("_global_summary"), dict) else {}
    protagonist = global_summary.get("protagonist") or "主角"

    for pkg in evidence_list:
        heuristic = _heuristic_local_understanding(pkg, global_summary)
        llm_data = {}

        text = (pkg.get("subtitle_text") or pkg.get("main_text_evidence") or pkg.get("aligned_subtitle_text") or "").strip()
        if api_key and base_url and model and text:
            prompt = PromptManager.get_prompt(
                "movie_story_narration",
                "segment_structuring",
                parameters={
                    "segment_meta_json": json.dumps(
                        {
                            "segment_id": pkg.get("segment_id"),
                            "start": pkg.get("start"),
                            "end": pkg.get("end"),
                            "plot_function_hint": pkg.get("plot_function"),
                            "importance_level_hint": pkg.get("importance_level"),
                            "boundary_confidence_hint": pkg.get("boundary_confidence"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "segment_text": text,
                    "global_summary_json": json.dumps(global_summary or {}, ensure_ascii=False, indent=2),
                },
            )
            raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
            parsed = _extract_json_obj(raw)
            if isinstance(parsed, dict):
                llm_data = parsed

        understanding = dict(heuristic)
        understanding.update({k: v for k, v in llm_data.items() if v not in (None, "", [], {})})

        pkg["local_understanding"] = understanding
        pkg["emotion_hint"] = pkg.get("emotion_hint") or understanding.get("emotion") or "平静"
        pkg["protagonist_related"] = protagonist in understanding.get("characters", []) or pkg.get("importance_level") == "high"
        pkg["surface_dialogue_meaning"] = understanding.get("surface_dialogue_meaning") or heuristic["surface_dialogue_meaning"]
        pkg["real_narrative_state"] = understanding.get("real_narrative_state") or heuristic["real_narrative_state"]
        pkg["plot_function"] = understanding.get("plot_function") or pkg.get("plot_function")
        pkg["importance_level"] = understanding.get("importance_level") or pkg.get("importance_level")
        pkg["need_visual_verify"] = bool(understanding.get("need_visual_verify", pkg.get("need_visual_verify", False)))
        pkg["raw_voice_retain_suggestion"] = bool(
            understanding.get("raw_voice_retain_suggestion", pkg.get("raw_voice_retain_suggestion", False))
        )
        pkg["boundary_confidence"] = understanding.get("boundary_confidence") or pkg.get("boundary_confidence", "medium")
        pkg["boundary_reasons"] = list(
            dict.fromkeys((pkg.get("boundary_reasons") or []) + (understanding.get("boundary_reasons") or []))
        )
        pkg["narrative_risk_flags"] = list(
            dict.fromkeys((pkg.get("narrative_risk_flags") or []) + (understanding.get("narrative_risk_flags") or []))
        )
        pkg["validator_hints"] = understanding.get("validator_hints") or []

        if pkg["protagonist_related"] and pkg.get("narration_level") == "brief":
            pkg["narration_level"] = "standard"

    return evidence_list
