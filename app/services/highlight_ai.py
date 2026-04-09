from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Sequence

from loguru import logger

from app.config import config
from app.services.llm_text_completion import call_text_chat_completion


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


def _resolve_text_llm_settings(
    *,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> Dict[str, str]:
    resolved = {
        "api_key": str(api_key or config.app.get("text_litellm_api_key", "") or "").strip(),
        "model": str(model or config.app.get("text_litellm_model_name", "") or "").strip(),
        "base_url": str(base_url or config.app.get("text_litellm_base_url", "") or "").strip(),
    }
    if not (resolved["api_key"] and resolved["model"]):
        return {}
    return resolved


def _compact_text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _clip_stage(clip: Dict[str, Any]) -> str:
    stage = str(clip.get("story_stage_hint", "") or "").strip().lower()
    return stage or "unknown"


def _clip_score_value(clip: Dict[str, Any]) -> float:
    if clip.get("profile_total_score") not in (None, ""):
        try:
            return float(clip.get("profile_total_score", 0.0) or 0.0)
        except Exception:
            pass
    return float(clip.get("total_score", 0.0) or 0.0)


def _clip_priority(clip: Dict[str, Any]) -> float:
    stage = _clip_stage(clip)
    tags = {str(tag).strip().lower() for tag in (clip.get("tags") or []) if str(tag).strip()}
    reasons = {str(reason).strip().lower() for reason in (clip.get("selection_reason") or []) if str(reason).strip()}
    score = _clip_score_value(clip)
    bonus = 0.0

    if stage in {"reveal", "climax", "conflict", "turning_point", "ending"}:
        bonus += 0.18
    if stage in {"opening", "setup"}:
        bonus -= 0.1
    if tags & {"reveal", "twist", "conflict", "emotion_peak", "ending"}:
        bonus += 0.12
    if clip.get("raw_audio_worthy"):
        bonus += 0.06
    if "coverage_anchor" in reasons or "opening_anchor" in reasons:
        bonus -= 0.08
    return round(score + bonus, 4)


def _build_candidate_card(clip: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "clip_id": str(clip.get("clip_id", "") or ""),
        "start": round(float(clip.get("start", 0.0) or 0.0), 3),
        "end": round(float(clip.get("end", 0.0) or 0.0), 3),
        "duration": round(float(clip.get("duration", 0.0) or 0.0), 3),
        "stage": _clip_stage(clip),
        "source": str(clip.get("source", "") or ""),
        "story_position": round(float(clip.get("story_position", 0.5) or 0.5), 3),
        "total_score": round(_clip_score_value(clip), 3),
        "base_total_score": round(float(clip.get("base_total_score", clip.get("total_score", 0.0)) or 0.0), 3),
        "profile_total_score": round(float(clip.get("profile_total_score", _clip_score_value(clip)) or 0.0), 3),
        "profile_fit_score": round(float(clip.get("profile_fit_score", 0.0) or 0.0), 3),
        "intro_risk_score": round(float(clip.get("intro_risk_score", 0.0) or 0.0), 3),
        "profile_intro_penalty": round(float(clip.get("profile_intro_penalty", 0.0) or 0.0), 3),
        "highlight_profile_id": str(clip.get("highlight_profile_id", "") or ""),
        "story_score": round(float(clip.get("story_score", 0.0) or 0.0), 3),
        "emotion_score": round(float(clip.get("emotion_score", 0.0) or 0.0), 3),
        "energy_score": round(float(clip.get("energy_score", 0.0) or 0.0), 3),
        "audio_signal_score": round(float(clip.get("audio_signal_score", 0.0) or 0.0), 3),
        "audio_peak_score": round(float(clip.get("audio_peak_score", 0.0) or 0.0), 3),
        "audio_dynamic_score": round(float(clip.get("audio_dynamic_score", 0.0) or 0.0), 3),
        "visible_action_score": round(float(clip.get("visible_action_score", 0.0) or 0.0), 3),
        "reaction_score": round(float(clip.get("reaction_score", 0.0) or 0.0), 3),
        "inner_state_support": round(float(clip.get("inner_state_support", 0.0) or 0.0), 3),
        "relation_score": round(float(clip.get("relation_score", 0.0) or 0.0), 3),
        "group_reaction_score": round(float(clip.get("group_reaction_score", 0.0) or 0.0), 3),
        "dialogue_exchange_score": round(float(clip.get("dialogue_exchange_score", 0.0) or 0.0), 3),
        "raw_audio_worthy": bool(clip.get("raw_audio_worthy")),
        "tags": list(clip.get("tags") or [])[:6],
        "character_names": list(clip.get("character_names") or [])[:8],
        "speaker_names": list(clip.get("speaker_names") or [])[:6],
        "subtitle_text": _compact_text(clip.get("subtitle_text", "")),
        "scene_summary": _compact_text(clip.get("scene_summary", "")),
        "shot_role": str(clip.get("shot_role", "") or ""),
        "primary_evidence": str(clip.get("primary_evidence", "") or ""),
    }


def _compact_profile(profile: Dict[str, Any] | None) -> Dict[str, Any]:
    current = dict(profile or {})
    return {
        "id": str(current.get("id", "") or ""),
        "label": str(current.get("label", "") or ""),
        "description": _compact_text(current.get("description", ""), 140),
        "selection_priorities": list(current.get("selection_priorities") or [])[:6],
        "avoid_priorities": list(current.get("avoid_priorities") or [])[:6],
        "preferred_story_stages": list(current.get("preferred_story_stages") or [])[:6],
        "discouraged_story_stages": list(current.get("discouraged_story_stages") or [])[:6],
        "narration_focus": str(current.get("narration_focus", "") or ""),
        "visual_strategy": str(current.get("visual_strategy", "") or ""),
        "editor_note": _compact_text(current.get("editor_note", ""), 140),
        "source": str(current.get("source", "") or ""),
        "confidence": round(float(current.get("confidence", 0.0) or 0.0), 3),
    }


def ai_select_highlight_candidates(
    candidate_clips: Sequence[Dict[str, Any]],
    *,
    target_duration_seconds: int,
    movie_title: str = "",
    mode: str = "highlight_recut",
    highlight_profile: Dict[str, Any] | None = None,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> Dict[str, Any]:
    settings = _resolve_text_llm_settings(api_key=api_key, model=model, base_url=base_url)
    if not settings:
        return {"used_ai": False, "selected_clip_ids": [], "selection_notes": []}

    ranked = sorted((dict(item) for item in (candidate_clips or [])), key=_clip_priority, reverse=True)
    if not ranked:
        return {"used_ai": False, "selected_clip_ids": [], "selection_notes": []}

    max_candidates = max(min(int(math.ceil(target_duration_seconds / 20.0)), 36), 14)
    shortlist = ranked[:max_candidates]
    candidate_cards = [_build_candidate_card(clip) for clip in shortlist]
    profile_payload = _compact_profile(highlight_profile)
    prompt = (
        "You are selecting the truly valuable highlight clips for a film recap rough cut.\n"
        "Return JSON only.\n\n"
        "Goals:\n"
        "- Prefer conflict, reveal, twist, climax, emotional payoff, ending payoff.\n"
        "- Reject low-value setup, prologue, routine exposition, and ordinary dialogue.\n"
        "- Do not keep opening/setup clips unless they are necessary and clearly high-value.\n"
        "- intro_risk_score is a penalty hint for prologue/setup contamination. Treat high intro_risk_score as a strong reason to reject a clip unless it has undeniable payoff.\n"
        "- Select clips that can form a compelling rough cut near the target duration.\n\n"
        "Audio matters:\n"
        "- Higher audio_signal_score / audio_peak_score usually means stronger raw soundtrack, impact, or emotional lift.\n"
        "- Do not select by loudness alone, but use strong audio as supporting evidence when it matches the scene payoff.\n\n"
        "Adapt your decisions to the supplied highlight profile. If the profile says action, prioritize kinetic payoff.\n"
        "If the profile says suspense, prioritize reveal, suspicion, pressure, and truth payoff.\n"
        "If the profile says drama or romance, prioritize emotional or relationship payoff over generic action.\n\n"
        "Output schema:\n"
        "{\n"
        '  "selected_clip_ids": ["clip_001"],\n'
        '  "raw_audio_clip_ids": ["clip_001"],\n'
        '  "selection_notes": [{"clip_id": "clip_001", "decision": "keep", "reason": "short reason"}]\n'
        "}\n\n"
        f"mode: {mode}\n"
        f"movie_title: {_compact_text(movie_title, 80)}\n"
        f"target_duration_seconds: {int(target_duration_seconds)}\n"
        f"highlight_profile_json: {json.dumps(profile_payload, ensure_ascii=False)}\n"
        f"candidate_clips_json: {json.dumps(candidate_cards, ensure_ascii=False)}"
    )
    raw = call_text_chat_completion(
        prompt,
        api_key=settings["api_key"],
        model=settings["model"],
        base_url=settings["base_url"],
        system_prompt="You are a careful film editor. Be conservative and select only real highlights. Return JSON only.",
        temperature=0.1,
        timeout=90,
        log_label="AI highlight selector",
    )
    parsed = _extract_json_obj(raw)
    if not isinstance(parsed, dict):
        return {"used_ai": False, "selected_clip_ids": [], "selection_notes": []}

    valid_ids = {card["clip_id"] for card in candidate_cards if card.get("clip_id")}
    selected_ids = [str(value) for value in (parsed.get("selected_clip_ids") or []) if str(value) in valid_ids]
    raw_audio_ids = [str(value) for value in (parsed.get("raw_audio_clip_ids") or []) if str(value) in valid_ids]
    notes = []
    for item in parsed.get("selection_notes") or []:
        if not isinstance(item, dict):
            continue
        clip_id = str(item.get("clip_id", "") or "")
        if clip_id not in valid_ids:
            continue
        notes.append(
            {
                "clip_id": clip_id,
                "decision": str(item.get("decision", "") or ""),
                "reason": _compact_text(item.get("reason", ""), 120),
            }
        )
    if not selected_ids:
        return {"used_ai": False, "selected_clip_ids": [], "selection_notes": notes}
    return {
        "used_ai": True,
        "selected_clip_ids": selected_ids,
        "raw_audio_clip_ids": raw_audio_ids,
        "selection_notes": notes,
        "model": settings["model"],
    }


def _unit_keyword_overlap(unit: Dict[str, Any], clip: Dict[str, Any]) -> float:
    keywords = {str(value).strip() for value in (unit.get("keywords") or []) if str(value).strip()}
    if not keywords:
        return 0.0
    bag = " ".join(
        [
            str(clip.get("subtitle_text", "") or ""),
            str(clip.get("scene_summary", "") or ""),
            " ".join(str(tag) for tag in (clip.get("tags") or [])),
        ]
    )
    return min(sum(1 for keyword in keywords if keyword in bag), 4) * 0.18


def _unit_character_overlap(unit: Dict[str, Any], clip: Dict[str, Any]) -> float:
    wanted = {str(value).strip() for value in (unit.get("character_names") or []) if str(value).strip()}
    if not wanted:
        return 0.0
    have = {str(value).strip() for value in (clip.get("character_names") or []) if str(value).strip()}
    if not have:
        return 0.0
    overlap = len(wanted & have)
    return min(overlap, 3) * 0.22


def _unit_position_score(unit: Dict[str, Any], clip: Dict[str, Any]) -> float:
    desired = float(unit.get("position_hint", 0.5) or 0.5)
    current = float(clip.get("story_position", 0.5) or 0.5)
    return max(0.0, 0.2 - abs(desired - current) * 0.35)


def _unit_stage_score(unit: Dict[str, Any], clip: Dict[str, Any]) -> float:
    unit_stage = str(unit.get("story_stage", "") or "").strip().lower()
    clip_stage = _clip_stage(clip)
    if not unit_stage or not clip_stage:
        return 0.0
    if unit_stage == clip_stage:
        return 0.24
    nearby = {
        ("reveal", "turning_point"),
        ("turning_point", "reveal"),
        ("conflict", "climax"),
        ("climax", "conflict"),
        ("ending", "reveal"),
        ("reveal", "ending"),
        ("setup", "opening"),
        ("opening", "setup"),
    }
    return 0.1 if (unit_stage, clip_stage) in nearby else 0.0


def _build_unit_candidate_shortlist(unit: Dict[str, Any], candidate_clips: Sequence[Dict[str, Any]], top_k: int = 14) -> List[Dict[str, Any]]:
    scored = []
    for clip in candidate_clips or []:
        score = _clip_score_value(clip)
        score += _unit_keyword_overlap(unit, clip)
        score += _unit_character_overlap(unit, clip)
        score += _unit_position_score(unit, clip)
        score += _unit_stage_score(unit, clip)
        scored.append((round(score, 4), dict(clip)))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[: max(int(top_k or 0), 6)]]


def ai_match_narration_units_to_candidates(
    narration_units: Sequence[Dict[str, Any]],
    candidate_clips: Sequence[Dict[str, Any]],
    *,
    movie_title: str = "",
    highlight_profile: Dict[str, Any] | None = None,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> List[Dict[str, Any]]:
    settings = _resolve_text_llm_settings(api_key=api_key, model=model, base_url=base_url)
    if not settings or not narration_units or not candidate_clips:
        return []

    clip_lookup = {str(clip.get("clip_id", "") or ""): dict(clip) for clip in candidate_clips if clip.get("clip_id")}
    matches: List[Dict[str, Any]] = []
    profile_payload = _compact_profile(highlight_profile)

    for unit in narration_units:
        shortlist = _build_unit_candidate_shortlist(unit, candidate_clips, top_k=12)
        if not shortlist:
            continue
        cards = [_build_candidate_card(clip) for clip in shortlist]
        prompt = (
            "You are matching one narration sentence to the best film clip.\n"
            "Preserve the original sentence boundary. Select exactly one best clip_id.\n"
            "Return JSON only.\n\n"
            "Use audio evidence only as a secondary hint. Prefer semantically correct scenes first.\n\n"
            "Output schema:\n"
            "{\n"
            '  "selected_clip_id": "clip_001",\n'
            '  "backup_clip_ids": ["clip_002"],\n'
            '  "reason": "short reason",\n'
            '  "confidence": 0.0\n'
            "}\n\n"
            f"movie_title: {_compact_text(movie_title, 80)}\n"
            f"highlight_profile_json: {json.dumps(profile_payload, ensure_ascii=False)}\n"
            f"narration_unit_json: {json.dumps({k: unit.get(k) for k in ('unit_id', 'text', 'story_stage', 'narration_type', 'match_focus', 'keywords', 'character_names', 'position_hint')}, ensure_ascii=False)}\n"
            f"candidate_clips_json: {json.dumps(cards, ensure_ascii=False)}"
        )
        raw = call_text_chat_completion(
            prompt,
            api_key=settings["api_key"],
            model=settings["model"],
            base_url=settings["base_url"],
            system_prompt="You are a film recap editor. Match the sentence to the best visual evidence. Return JSON only.",
            temperature=0.1,
            timeout=75,
            log_label="AI narration matcher",
        )
        parsed = _extract_json_obj(raw)
        if not isinstance(parsed, dict):
            continue
        selected_clip_id = str(parsed.get("selected_clip_id", "") or "")
        if selected_clip_id not in clip_lookup:
            backup_ids = [str(value) for value in (parsed.get("backup_clip_ids") or []) if str(value) in clip_lookup]
            selected_clip_id = backup_ids[0] if backup_ids else ""
        if not selected_clip_id:
            continue

        clip = dict(clip_lookup[selected_clip_id])
        reason = _compact_text(parsed.get("reason", ""), 120)
        if reason:
            clip["selection_reason"] = list(dict.fromkeys(list(clip.get("selection_reason") or []) + [f"ai_match:{reason}"]))
        matches.append(
            {
                "unit_id": unit.get("unit_id"),
                "text": unit.get("text", ""),
                "target_seconds": unit.get("target_seconds", 0.0),
                "story_stage": unit.get("story_stage", ""),
                "narration_type": unit.get("narration_type", "omniscient_summary"),
                "match_focus": unit.get("match_focus", "narrative_overview"),
                "shot_template": unit.get("shot_template", "narrative_montage"),
                "keywords": list(unit.get("keywords") or []),
                "character_names": list(unit.get("character_names") or []),
                "subject_character_names": list(unit.get("subject_character_names") or []),
                "directed_target_names": list(unit.get("directed_target_names") or []),
                "focus_character_names": list(unit.get("focus_character_names") or []),
                "collective_target_names": list(unit.get("collective_target_names") or []),
                "collective_signal": bool(unit.get("collective_signal")),
                "rhythm_profile": unit.get("rhythm_profile", "balanced"),
                "rhythm_config": dict(unit.get("rhythm_config") or {}),
                "clip_id": selected_clip_id,
                "match_score": round(float(parsed.get("confidence", 0.0) or 0.0), 3),
                "match_strategy": "ai_semantic",
                "desired_position": round(float(unit.get("position_hint", 0.5) or 0.5), 3),
                "clip": clip,
                "clip_group": [dict(clip)],
                "clip_ids": [selected_clip_id],
                "group_start": round(float(clip.get("start", 0.0) or 0.0), 3),
                "group_end": round(float(clip.get("end", 0.0) or 0.0), 3),
                "preserve_sentence_boundary": True,
                "ai_reason": reason,
            }
        )

    return matches
