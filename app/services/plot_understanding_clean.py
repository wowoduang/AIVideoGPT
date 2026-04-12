from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Sequence

from loguru import logger

from app.services.llm_text_completion import call_text_chat_completion
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
    return call_text_chat_completion(
        prompt,
        api_key=api_key,
        model=model,
        base_url=base_url,
        system_prompt="你是严格、保守的中文影视剧情理解助手。",
        temperature=0.2,
        timeout=120,
        log_label="剧情理解 LLM",
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


def _coerce_ts(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 3)
    return _parse_ts(str(raw))


def _normalize_highlight_windows(
    items: Sequence[Dict] | None,
    *,
    default_category: str = "",
    default_importance: str = "medium",
    default_raw_voice_priority: str = "low",
) -> List[Dict]:
    normalized: List[Dict] = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        start = _coerce_ts(item.get("start"))
        end = _coerce_ts(item.get("end"))
        if start is None or end is None or end <= start:
            continue
        category = str(item.get("category") or item.get("label") or default_category or "信息揭露").strip()
        importance = str(item.get("importance") or default_importance or "medium").strip().lower()
        if importance not in {"high", "medium", "low"}:
            importance = default_importance
        raw_voice_priority = str(
            item.get("raw_voice_priority") or default_raw_voice_priority or "low"
        ).strip().lower()
        if raw_voice_priority not in {"high", "medium", "low"}:
            raw_voice_priority = default_raw_voice_priority
        reason = str(item.get("reason") or item.get("label") or category or "剧情高光候选").strip()
        dedupe_key = (round(start, 3), round(end, 3), category, importance, raw_voice_priority, reason)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "start": _format_ts(start),
                "end": _format_ts(end),
                "category": category,
                "importance": importance,
                "raw_voice_priority": raw_voice_priority,
                "reason": reason,
            }
        )
    normalized.sort(key=lambda x: (_coerce_ts(x.get("start")) or 0.0, _coerce_ts(x.get("end")) or 0.0))
    return normalized


def _derive_highlight_windows(parsed: Dict | None, chunk_summaries: Sequence[Dict] | None) -> tuple[List[Dict], str]:
    parsed = parsed or {}

    direct_windows = _normalize_highlight_windows(parsed.get("highlight_windows"))
    if direct_windows:
        return direct_windows, "llm_highlight_windows"

    turning_point_windows = _normalize_highlight_windows(
        parsed.get("major_turning_points"),
        default_importance="high",
        default_raw_voice_priority="medium",
    )
    if turning_point_windows:
        return turning_point_windows, "llm_turning_points_fallback"

    chunk_highlight_windows: List[Dict] = []
    for chunk in chunk_summaries or []:
        chunk_highlight_windows.extend(
            _normalize_highlight_windows(
                chunk.get("highlight_windows"),
                default_importance="medium",
                default_raw_voice_priority="medium",
            )
        )
    if chunk_highlight_windows:
        return chunk_highlight_windows, "chunk_summaries_fallback"

    chunk_major_event_windows: List[Dict] = []
    for chunk in chunk_summaries or []:
        chunk_major_event_windows.extend(
            _normalize_highlight_windows(
                chunk.get("major_events"),
                default_importance="medium",
                default_raw_voice_priority="low",
            )
        )
    if chunk_major_event_windows:
        return chunk_major_event_windows, "chunk_major_events_fallback"

    return [], "none"


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


def _build_full_subtitle_text(
    segments: Sequence[Dict],
    *,
    max_line_chars: int = 180,
    max_segments: int = 0,
) -> str:
    lines: List[str] = []
    for idx, seg in enumerate(segments or [], start=1):
        text = re.sub(r"\s+", " ", str(seg.get("text") or "")).strip()
        if not text:
            continue
        if max_line_chars > 0 and len(text) > max_line_chars:
            text = text[: max_line_chars - 1].rstrip() + "…"
        start = _format_ts(float(seg.get("start", 0.0) or 0.0))
        end = _format_ts(float(seg.get("end", seg.get("start", 0.0)) or 0.0))
        lines.append(f"{idx}. [{start}-{end}] {text}")
        if max_segments and len(lines) >= max_segments:
            break
    return "\n".join(lines)


def _split_subtitle_segments_for_llm(
    segments: Sequence[Dict],
    *,
    max_chars: int = 14000,
    max_segments: int = 140,
) -> List[str]:
    chunks: List[str] = []
    bucket: List[str] = []
    bucket_chars = 0
    bucket_count = 0

    for seg in segments or []:
        text = re.sub(r"\s+", " ", str(seg.get("text") or "")).strip()
        if not text:
            continue
        start = _format_ts(float(seg.get("start", 0.0) or 0.0))
        end = _format_ts(float(seg.get("end", seg.get("start", 0.0)) or 0.0))
        line = f"[{start}-{end}] {text}"
        projected = bucket_chars + len(line) + 1
        if bucket and (projected > max_chars or bucket_count >= max_segments):
            chunks.append("\n".join(bucket))
            bucket = []
            bucket_chars = 0
            bucket_count = 0
        bucket.append(line)
        bucket_chars += len(line) + 1
        bucket_count += 1

    if bucket:
        chunks.append("\n".join(bucket))
    return chunks


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
    full_subtitle_text = _build_full_subtitle_text(subtitle_segments)
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
        "subtitle_input_mode": "timeline_digest",
        "subtitle_chunk_summaries": [],
    }
    if not (api_key and model and (digest or full_subtitle_text)):
        return fallback

    chunk_summaries: List[Dict] = []
    subtitle_input_mode = "full_subtitle_text"
    prompt_subtitle_text = full_subtitle_text
    if len(full_subtitle_text) > 18000:
        subtitle_input_mode = "chunked_full_subtitle"
        prompt_subtitle_text = ""
        subtitle_chunks = _split_subtitle_segments_for_llm(subtitle_segments)
        for idx, chunk_text in enumerate(subtitle_chunks, start=1):
            chunk_prompt = PromptManager.get_prompt(
                "movie_story_narration",
                "subtitle_chunk_understanding",
                parameters={
                    "chunk_index": idx,
                    "chunk_count": len(subtitle_chunks),
                    "subtitle_chunk_text": chunk_text,
                },
            )
            raw_chunk = _call_chat_completion(chunk_prompt, api_key=api_key, base_url=base_url, model=model)
            parsed_chunk = _extract_json_obj(raw_chunk)
            if isinstance(parsed_chunk, dict):
                parsed_chunk.setdefault("chunk_index", idx)
                chunk_summaries.append(parsed_chunk)
            else:
                chunk_summaries.append(
                    {
                        "chunk_index": idx,
                        "window_summary": chunk_text[:300],
                        "major_events": [],
                        "highlight_windows": [],
                        "risk_flags": ["chunk_parse_failed"],
                    }
                )

    prompt = PromptManager.get_prompt(
        "movie_story_narration",
        "full_subtitle_understanding_v2",
        parameters={
            "subtitle_timeline_digest": digest,
            "full_subtitle_text": prompt_subtitle_text,
            "subtitle_chunk_summaries_json": json.dumps(chunk_summaries, ensure_ascii=False, indent=2),
        },
    )
    raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
    parsed = _extract_json_obj(raw)
    merged = dict(fallback)
    merged["subtitle_timeline_digest"] = digest
    merged["subtitle_input_mode"] = subtitle_input_mode
    merged["subtitle_chunk_summaries"] = chunk_summaries
    if isinstance(parsed, dict):
        merged.update({k: v for k, v in parsed.items() if v not in (None, "", [], {})})
        merged["subtitle_understanding_status"] = "ok"
    else:
        merged["subtitle_understanding_status"] = "parse_failed"
        logger.warning(
            "整字幕剧情理解解析失败: input_mode={}, chunk_summaries={}, raw_preview={}",
            subtitle_input_mode,
            len(chunk_summaries),
            str(raw or "").replace("\n", " ")[:240],
        )

    highlight_windows, highlight_source = _derive_highlight_windows(parsed if isinstance(parsed, dict) else {}, chunk_summaries)
    if highlight_windows:
        merged["highlight_windows"] = highlight_windows
        merged["highlight_windows_source"] = highlight_source
        if merged.get("subtitle_understanding_status") == "parse_failed":
            merged["subtitle_understanding_status"] = f"parse_failed_{highlight_source}"
    else:
        merged["highlight_windows_source"] = highlight_source
    return merged


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
        local_understanding = dict(pkg.get("local_understanding") or {})
        story_validation = dict(pkg.get("story_validation") or {})
        candidates.append(
            {
                "segment_id": pkg.get("segment_id"),
                "start": _format_ts(float(pkg.get("start", 0.0) or 0.0)),
                "end": _format_ts(float(pkg.get("end", 0.0) or 0.0)),
                "plot_function": pkg.get("plot_function"),
                "importance_level": pkg.get("importance_level"),
                "boundary_confidence": pkg.get("boundary_confidence"),
                "validator_status": story_validation.get("validator_status", "pass"),
                "raw_voice_retain_suggestion": bool(pkg.get("raw_voice_retain_suggestion")),
                "need_visual_verify": bool(pkg.get("need_visual_verify")),
                "text": text[:260],
                "surface_dialogue_meaning": str(pkg.get("surface_dialogue_meaning") or "")[:180],
                "real_narrative_state": str(pkg.get("real_narrative_state") or "")[:180],
                "core_event": str(local_understanding.get("core_event") or "")[:120],
                "emotion": local_understanding.get("emotion") or "",
                "characters": list(local_understanding.get("characters") or [])[:8],
                "narrative_risk_flags": list(local_understanding.get("narrative_risk_flags") or [])[:8],
                "validator_hints": list(story_validation.get("validator_hints") or [])[:6],
                "raw_voice_keep": bool(story_validation.get("raw_voice_keep")),
                "visual_summary": [str(item.get("desc") or "")[:60] for item in list(pkg.get("visual_summary") or [])[:4]],
            }
        )

    if not (api_key and model):
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
        if api_key and model and text:
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
