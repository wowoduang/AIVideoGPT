from __future__ import annotations

import copy
import importlib.util
import re
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence, Tuple


_PROFILE_LIBRARY: Dict[str, Dict[str, Any]] = {
    "auto": {
        "label": "Auto Detect",
        "description": "Infer a workable highlight profile from subtitles, candidate evidence, and narration.",
        "selection_priorities": ["真实冲突", "反转揭示", "高潮兑现"],
        "avoid_priorities": ["片头铺垫", "普通寒暄", "纯说明对白"],
        "preferred_story_stages": ["conflict", "turning_point", "reveal", "climax", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.32,
            "emotion": 0.18,
            "energy": 0.12,
            "visible_action": 0.1,
            "reaction": 0.08,
            "inner_state": 0.07,
            "relation": 0.06,
            "group_reaction": 0.04,
            "dialogue_exchange": 0.03,
        },
        "tag_bias": {"reveal": 0.08, "conflict": 0.08, "emotion_peak": 0.08, "ending": 0.06},
        "shot_role_bias": {"dialogue_exchange": 0.03, "single_focus": 0.03, "action_follow": 0.03},
        "raw_audio_bias": 0.05,
        "opening_penalty": 0.08,
        "narration_focus": "balanced",
        "visual_strategy": "mixed",
        "editor_note": "Favor real plot payoff over chronological coverage.",
    },
    "general": {
        "label": "General / Mixed",
        "description": "General-purpose recap profile for mixed-genre films.",
        "selection_priorities": ["冲突推进", "反转揭示", "情绪爆发", "结尾回收"],
        "avoid_priorities": ["片头序幕", "低信息对白", "日常铺垫"],
        "preferred_story_stages": ["conflict", "turning_point", "reveal", "climax", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.34,
            "emotion": 0.18,
            "energy": 0.1,
            "visible_action": 0.08,
            "reaction": 0.08,
            "inner_state": 0.07,
            "relation": 0.07,
            "group_reaction": 0.05,
            "dialogue_exchange": 0.03,
        },
        "tag_bias": {"reveal": 0.08, "conflict": 0.07, "emotion_peak": 0.07, "ending": 0.06},
        "shot_role_bias": {"dialogue_exchange": 0.03, "single_focus": 0.03},
        "raw_audio_bias": 0.04,
        "opening_penalty": 0.08,
        "narration_focus": "balanced",
        "visual_strategy": "mixed",
        "editor_note": "Keep the most meaningful beats, not evenly sampled coverage.",
    },
    "action": {
        "label": "Action / War",
        "description": "Prioritize combat, chase, mission, crisis escalation, and visceral payoff.",
        "selection_priorities": ["动作爆发", "追逐对决", "任务危机", "高能原声"],
        "avoid_priorities": ["静态铺垫", "弱解释段", "低动势普通对白"],
        "preferred_story_stages": ["conflict", "climax", "turning_point", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.26,
            "emotion": 0.12,
            "energy": 0.18,
            "visible_action": 0.18,
            "reaction": 0.05,
            "inner_state": 0.03,
            "relation": 0.04,
            "group_reaction": 0.08,
            "dialogue_exchange": 0.02,
        },
        "tag_bias": {"conflict": 0.11, "emotion_peak": 0.07, "ending": 0.05},
        "shot_role_bias": {"action_follow": 0.08, "ensemble_relation": 0.03},
        "raw_audio_bias": 0.08,
        "opening_penalty": 0.1,
        "narration_focus": "event_driven",
        "visual_strategy": "kinetic",
        "editor_note": "Explosive action and crisis escalation beat ordinary exposition.",
    },
    "suspense": {
        "label": "Suspense / Thriller",
        "description": "Prioritize suspicion, investigation, reveal, pressure, and payoff of hidden information.",
        "selection_priorities": ["悬念铺压", "怀疑试探", "反转揭示", "真相兑现"],
        "avoid_priorities": ["普通说明段", "弱关系闲聊", "无信息环境镜头"],
        "preferred_story_stages": ["reveal", "turning_point", "conflict", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.34,
            "emotion": 0.14,
            "energy": 0.08,
            "visible_action": 0.04,
            "reaction": 0.1,
            "inner_state": 0.1,
            "relation": 0.1,
            "group_reaction": 0.05,
            "dialogue_exchange": 0.05,
        },
        "tag_bias": {"reveal": 0.12, "conflict": 0.06, "ending": 0.08},
        "shot_role_bias": {"single_focus": 0.05, "dialogue_exchange": 0.04, "narrative_bridge": 0.03},
        "raw_audio_bias": 0.04,
        "opening_penalty": 0.08,
        "narration_focus": "mystery",
        "visual_strategy": "tension",
        "editor_note": "Suspicion, reversal, and hidden-truth beats outrank plain setup.",
    },
    "drama": {
        "label": "Drama / Emotion",
        "description": "Prioritize emotional performance, relationship turns, and character inner-state payoff.",
        "selection_priorities": ["情绪爆发", "关系转折", "心理变化", "表演张力"],
        "avoid_priorities": ["无情绪信息对白", "纯行动填充", "低价值过场"],
        "preferred_story_stages": ["turning_point", "climax", "reveal", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.28,
            "emotion": 0.18,
            "energy": 0.05,
            "visible_action": 0.02,
            "reaction": 0.12,
            "inner_state": 0.12,
            "relation": 0.12,
            "group_reaction": 0.05,
            "dialogue_exchange": 0.04,
        },
        "tag_bias": {"emotion_peak": 0.11, "reveal": 0.06, "ending": 0.06},
        "shot_role_bias": {"single_focus": 0.06, "dialogue_exchange": 0.04, "ensemble_relation": 0.03},
        "raw_audio_bias": 0.05,
        "opening_penalty": 0.07,
        "narration_focus": "emotion",
        "visual_strategy": "performance",
        "editor_note": "Character emotion and relationship rupture beat plot summary.",
    },
    "comedy": {
        "label": "Comedy",
        "description": "Prioritize punchlines, awkward reaction, ensemble interplay, and comic payoff.",
        "selection_priorities": ["笑点兑现", "尴尬反应", "群戏互动", "节奏反差"],
        "avoid_priorities": ["平淡交代", "冗长说明", "低节奏铺垫"],
        "preferred_story_stages": ["conflict", "turning_point", "climax", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.22,
            "emotion": 0.16,
            "energy": 0.1,
            "visible_action": 0.05,
            "reaction": 0.12,
            "inner_state": 0.04,
            "relation": 0.1,
            "group_reaction": 0.1,
            "dialogue_exchange": 0.08,
        },
        "tag_bias": {"emotion_peak": 0.07, "conflict": 0.05, "ending": 0.04},
        "shot_role_bias": {"dialogue_exchange": 0.06, "ensemble_relation": 0.05, "single_focus": 0.03},
        "raw_audio_bias": 0.05,
        "opening_penalty": 0.07,
        "narration_focus": "rhythm",
        "visual_strategy": "reaction",
        "editor_note": "Reaction, banter, and payoff timing matter more than broad coverage.",
    },
    "romance": {
        "label": "Romance",
        "description": "Prioritize chemistry, longing, relationship beats, and emotional confession.",
        "selection_priorities": ["关系推进", "情感确认", "误会反转", "亲密张力"],
        "avoid_priorities": ["无关动作段", "普通事务对白", "低信息过渡"],
        "preferred_story_stages": ["turning_point", "reveal", "climax", "ending"],
        "discouraged_story_stages": ["opening", "setup"],
        "evidence_weights": {
            "story": 0.26,
            "emotion": 0.16,
            "energy": 0.04,
            "visible_action": 0.01,
            "reaction": 0.12,
            "inner_state": 0.11,
            "relation": 0.16,
            "group_reaction": 0.04,
            "dialogue_exchange": 0.06,
        },
        "tag_bias": {"emotion_peak": 0.1, "reveal": 0.06, "ending": 0.06},
        "shot_role_bias": {"single_focus": 0.05, "dialogue_exchange": 0.05, "ensemble_relation": 0.02},
        "raw_audio_bias": 0.04,
        "opening_penalty": 0.06,
        "narration_focus": "relationship",
        "visual_strategy": "intimate",
        "editor_note": "Chemistry and relationship change should outrank generic plot coverage.",
    },
}

_PROFILE_ALIASES = {
    "auto_detect": "auto",
    "mixed": "general",
    "generic": "general",
    "action_war": "action",
    "thriller": "suspense",
    "suspense_thriller": "suspense",
    "drama_emotion": "drama",
    "emotion": "drama",
    "romantic": "romance",
}

_PROFILE_KEYWORDS = {
    "action": [
        "战斗",
        "战争",
        "追逐",
        "爆炸",
        "枪战",
        "厮杀",
        "营救",
        "任务",
        "对决",
        "突袭",
        "fight",
        "battle",
        "war",
        "chase",
        "mission",
    ],
    "suspense": [
        "悬疑",
        "凶手",
        "真相",
        "怀疑",
        "秘密",
        "调查",
        "案件",
        "线索",
        "阴谋",
        "反转",
        "mystery",
        "thriller",
        "secret",
        "truth",
    ],
    "drama": [
        "亲情",
        "家庭",
        "人生",
        "命运",
        "绝望",
        "崩溃",
        "原谅",
        "告别",
        "牺牲",
        "emotion",
        "family",
        "drama",
    ],
    "comedy": [
        "喜剧",
        "搞笑",
        "荒诞",
        "尴尬",
        "爆笑",
        "闹剧",
        "误会",
        "funny",
        "comedy",
        "joke",
    ],
    "romance": [
        "爱情",
        "恋爱",
        "表白",
        "心动",
        "分手",
        "暧昧",
        "恋人",
        "romance",
        "love",
    ],
}


def _normalized_profile_id(value: Any) -> str:
    raw = str(value or "auto").strip().lower().replace(" ", "_").replace("-", "_")
    if raw in _PROFILE_LIBRARY:
        return raw
    return _PROFILE_ALIASES.get(raw, "auto")


def list_highlight_profile_ids(include_auto: bool = True) -> List[str]:
    ids = list(_PROFILE_LIBRARY.keys())
    if not include_auto:
        ids = [item for item in ids if item != "auto"]
    return ids


def get_highlight_profile(profile_id: str) -> Dict[str, Any]:
    normalized = _normalized_profile_id(profile_id)
    if normalized not in _PROFILE_LIBRARY:
        normalized = "general"
    payload = copy.deepcopy(_PROFILE_LIBRARY[normalized])
    payload["id"] = normalized
    return payload


def summarize_highlight_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    current = dict(profile or {})
    return {
        "id": str(current.get("id", "general") or "general"),
        "label": str(current.get("label", "") or ""),
        "description": str(current.get("description", "") or ""),
        "selection_priorities": list(current.get("selection_priorities") or [])[:6],
        "avoid_priorities": list(current.get("avoid_priorities") or [])[:6],
        "preferred_story_stages": list(current.get("preferred_story_stages") or [])[:6],
        "discouraged_story_stages": list(current.get("discouraged_story_stages") or [])[:6],
        "narration_focus": str(current.get("narration_focus", "") or ""),
        "visual_strategy": str(current.get("visual_strategy", "") or ""),
        "editor_note": str(current.get("editor_note", "") or ""),
        "source": str(current.get("source", "") or ""),
        "confidence": round(float(current.get("confidence", 0.0) or 0.0), 3),
        "reasons": list(current.get("reasons") or [])[:6],
        "signal_route": str(current.get("signal_route", "") or ""),
        "signal_modifiers": list(current.get("signal_modifiers") or [])[:6],
        "signal_reasons": list(current.get("signal_reasons") or [])[:6],
        "signal_metrics": {
            key: _clamp_unit(value) for key, value in dict(current.get("signal_metrics") or {}).items()
        },
    }


def _config_app() -> Dict[str, Any]:
    try:
        from app.config import config

        return dict(getattr(config, "app", {}) or {})
    except Exception:
        return {}


def detect_highlight_capabilities() -> Dict[str, Any]:
    app_config = _config_app()

    def _has_module(module_name: str) -> bool:
        try:
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    text_llm_ready = bool(
        str(app_config.get("text_litellm_api_key", "") or "").strip()
        and str(app_config.get("text_litellm_model_name", "") or "").strip()
    )
    vision_llm_ready = bool(
        str(app_config.get("vision_litellm_api_key", "") or "").strip()
        and str(app_config.get("vision_litellm_model_name", "") or "").strip()
    )

    return {
        "opencv_ready": _has_module("cv2"),
        "scenedetect_ready": _has_module("scenedetect"),
        "librosa_ready": _has_module("librosa"),
        "torch_ready": _has_module("torch"),
        "text_llm_ready": text_llm_ready,
        "vision_llm_ready": vision_llm_ready,
        "scene_detection_backend": "scenedetect" if _has_module("scenedetect") else "",
        "audio_signal_backend": "librosa" if _has_module("librosa") else "",
    }


def _take_text_samples(values: Iterable[Any], limit: int = 10, each_limit: int = 120) -> List[str]:
    samples: List[str] = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            continue
        samples.append(text[:each_limit])
        if len(samples) >= limit:
            break
    return samples


def _build_text_corpus(
    *,
    movie_title: str,
    narration_text: str,
    subtitle_segments: Sequence[Dict[str, Any]],
    plot_chunks: Sequence[Dict[str, Any]],
    candidate_clips: Sequence[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if str(movie_title or "").strip():
        parts.append(str(movie_title).strip())
    if str(narration_text or "").strip():
        parts.extend(_take_text_samples(str(narration_text).splitlines(), limit=6, each_limit=80))
    parts.extend(_take_text_samples((item.get("text", "") for item in (subtitle_segments or [])[:18]), limit=10))
    parts.extend(_take_text_samples((item.get("real_narrative_state", "") for item in (plot_chunks or [])[:12]), limit=8))
    parts.extend(_take_text_samples((item.get("scene_summary", "") for item in (candidate_clips or [])[:12]), limit=8))
    return " ".join(parts)


def _keyword_scores(text_corpus: str) -> Dict[str, float]:
    text = str(text_corpus or "").lower()
    scores = {profile_id: 0.0 for profile_id in _PROFILE_KEYWORDS}
    for profile_id, keywords in _PROFILE_KEYWORDS.items():
        matched = sum(1 for keyword in keywords if keyword.lower() in text)
        if matched:
            scores[profile_id] += min(matched, 5) * 0.18
    return scores


def _mean_value(items: Sequence[Dict[str, Any]], key: str) -> float:
    values = []
    for item in items or []:
        try:
            values.append(float(item.get(key, 0.0) or 0.0))
        except Exception:
            continue
    return float(mean(values)) if values else 0.0


def _ratio(items: Sequence[Dict[str, Any]], predicate) -> float:
    values = [1.0 if predicate(item) else 0.0 for item in (items or [])]
    return float(mean(values)) if values else 0.0


def _clamp_unit(value: float) -> float:
    return round(max(min(float(value or 0.0), 1.0), 0.0), 3)


def _normalize_weight_map(weights: Dict[str, Any]) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    for key, value in (weights or {}).items():
        try:
            normalized[str(key)] = max(float(value or 0.0), 0.0)
        except Exception:
            normalized[str(key)] = 0.0
    total = sum(normalized.values())
    if total <= 0.0001:
        return {key: 0.0 for key in normalized}
    return {key: round(value / total, 3) for key, value in normalized.items()}


def _signal_metrics(
    *,
    subtitle_segments: Sequence[Dict[str, Any]],
    plot_chunks: Sequence[Dict[str, Any]],
    candidate_clips: Sequence[Dict[str, Any]],
) -> Dict[str, float]:
    subtitle_items = list(subtitle_segments or [])
    plot_items = list(plot_chunks or [])
    clip_items = list(candidate_clips or [])
    subtitle_texts = [str(item.get("text", "") or "").strip() for item in subtitle_items]
    non_empty_subtitles = [text for text in subtitle_texts if text]
    subtitle_coverage = len(non_empty_subtitles) / max(len(subtitle_items), 1) if subtitle_items else 0.0
    avg_subtitle_length = mean((len(text) for text in non_empty_subtitles)) if non_empty_subtitles else 0.0
    subtitle_quality = _clamp_unit(subtitle_coverage * 0.65 + min(avg_subtitle_length / 26.0, 1.0) * 0.35)

    multi_speaker_ratio = _ratio(
        clip_items,
        lambda clip: int(clip.get("speaker_turns", 0) or 0) >= 2 or len(list(clip.get("speaker_names") or [])) >= 2,
    )
    single_focus_ratio = _ratio(clip_items, lambda clip: str(clip.get("shot_role", "") or "") == "single_focus")
    ensemble_ratio = _ratio(
        clip_items,
        lambda clip: str(clip.get("shot_role", "") or "") in {"dialogue_exchange", "ensemble_relation"},
    )
    audio_peak_ratio = _ratio(
        clip_items,
        lambda clip: float(clip.get("audio_signal_score", 0.0) or 0.0) >= 0.56
        or float(clip.get("audio_peak_score", 0.0) or 0.0) >= 0.72,
    )
    plot_summary_ratio = _ratio(
        plot_items,
        lambda chunk: bool(
            str(chunk.get("real_narrative_state", "") or "").strip()
            or str(chunk.get("surface_dialogue_meaning", "") or "").strip()
        ),
    )

    evidence = _evidence_scores(clip_items)
    speech_density = _clamp_unit(
        evidence["dialogue_exchange"] * 0.44
        + evidence["relation"] * 0.14
        + subtitle_quality * 0.22
        + multi_speaker_ratio * 0.2
    )
    kinetic_signal = _clamp_unit(
        evidence["visible_action"] * 0.34
        + evidence["energy"] * 0.24
        + evidence["raw_audio_ratio"] * 0.18
        + audio_peak_ratio * 0.16
        + evidence["conflict_ratio"] * 0.08
    )
    ensemble_signal = _clamp_unit(
        evidence["group_reaction"] * 0.32
        + evidence["dialogue_exchange"] * 0.2
        + evidence["relation"] * 0.12
        + ensemble_ratio * 0.2
        + multi_speaker_ratio * 0.16
    )
    inner_state_signal = _clamp_unit(
        evidence["inner_state"] * 0.44
        + evidence["reaction"] * 0.24
        + single_focus_ratio * 0.2
        + evidence["emotion"] * 0.12
    )
    text_reliability = _clamp_unit(subtitle_quality * 0.72 + plot_summary_ratio * 0.28)

    return {
        "subtitle_quality": subtitle_quality,
        "speech_density": speech_density,
        "kinetic_signal": kinetic_signal,
        "ensemble_signal": ensemble_signal,
        "inner_state_signal": inner_state_signal,
        "text_reliability": text_reliability,
        "multi_speaker_ratio": _clamp_unit(multi_speaker_ratio),
        "single_focus_ratio": _clamp_unit(single_focus_ratio),
        "audio_peak_ratio": _clamp_unit(audio_peak_ratio),
        "plot_summary_ratio": _clamp_unit(plot_summary_ratio),
    }


def _route_signal_profile(signal_metrics: Dict[str, float]) -> Tuple[str, List[str], List[str]]:
    metrics = dict(signal_metrics or {})
    modifiers: List[str] = []
    reasons: List[str] = []
    subtitle_quality = float(metrics.get("subtitle_quality", 0.0) or 0.0)
    speech_density = float(metrics.get("speech_density", 0.0) or 0.0)
    kinetic_signal = float(metrics.get("kinetic_signal", 0.0) or 0.0)
    ensemble_signal = float(metrics.get("ensemble_signal", 0.0) or 0.0)
    inner_state_signal = float(metrics.get("inner_state_signal", 0.0) or 0.0)
    text_reliability = float(metrics.get("text_reliability", 0.0) or 0.0)
    multi_speaker_ratio = float(metrics.get("multi_speaker_ratio", 0.0) or 0.0)

    if text_reliability <= 0.3:
        modifiers.append("low_text")
        reasons.append("subtitle_or_plot_text_weak")
    if speech_density >= 0.52 and subtitle_quality >= 0.42:
        modifiers.append("dialogue_driven")
        reasons.append("dialogue_dense")
    if kinetic_signal >= 0.58:
        modifiers.append("kinetic")
        reasons.append("kinetic_signal_strong")
    if ensemble_signal >= 0.54 and multi_speaker_ratio >= 0.3:
        modifiers.append("ensemble_conflict")
        reasons.append("multi_speaker_exchange")
    if inner_state_signal >= 0.54:
        modifiers.append("performance_reaction")
        reasons.append("reaction_inner_state_strong")

    route = "balanced_mixed"
    if "low_text" in modifiers and "kinetic" in modifiers:
        route = "visual_audio_fallback"
    elif "dialogue_driven" in modifiers and "ensemble_conflict" in modifiers:
        route = "ensemble_conflict"
    elif "dialogue_driven" in modifiers:
        route = "dialogue_driven"
    elif "performance_reaction" in modifiers and text_reliability >= 0.4:
        route = "performance_reaction"
    elif "kinetic" in modifiers:
        route = "kinetic_visual"
    elif "low_text" in modifiers:
        route = "visual_audio_fallback"

    if not modifiers:
        modifiers = ["balanced"]
        reasons = ["balanced_signal_mix"]

    return route, modifiers, list(dict.fromkeys(reasons))[:6]


def _adapt_profile_to_signal_route(
    profile: Dict[str, Any],
    *,
    signal_route: str,
    signal_modifiers: Sequence[str],
    signal_metrics: Dict[str, float],
    signal_reasons: Sequence[str],
) -> Dict[str, Any]:
    adapted = copy.deepcopy(profile or {})
    weights = dict(adapted.get("evidence_weights") or {})
    shot_role_bias = dict(adapted.get("shot_role_bias") or {})
    tag_bias = dict(adapted.get("tag_bias") or {})
    raw_audio_bias = float(adapted.get("raw_audio_bias", 0.0) or 0.0)

    def bump_weight(key: str, delta: float) -> None:
        weights[key] = float(weights.get(key, 0.0) or 0.0) + float(delta or 0.0)

    def bump_bias(mapping: Dict[str, Any], key: str, delta: float) -> None:
        mapping[key] = round(float(mapping.get(key, 0.0) or 0.0) + float(delta or 0.0), 3)

    modifiers = set(str(item or "").strip() for item in (signal_modifiers or []))
    if "dialogue_driven" in modifiers:
        bump_weight("dialogue_exchange", 0.065)
        bump_weight("relation", 0.04)
        bump_weight("reaction", 0.03)
        bump_weight("inner_state", 0.025)
        bump_weight("visible_action", -0.03)
        bump_weight("energy", -0.02)
        bump_bias(shot_role_bias, "dialogue_exchange", 0.04)
        bump_bias(shot_role_bias, "single_focus", 0.025)
    if "kinetic" in modifiers:
        bump_weight("visible_action", 0.075)
        bump_weight("energy", 0.06)
        bump_weight("group_reaction", 0.02)
        bump_weight("dialogue_exchange", -0.02)
        bump_bias(shot_role_bias, "action_follow", 0.05)
        bump_bias(shot_role_bias, "ensemble_relation", 0.02)
        bump_bias(tag_bias, "conflict", 0.03)
        raw_audio_bias += 0.03
    if "ensemble_conflict" in modifiers:
        bump_weight("group_reaction", 0.06)
        bump_weight("relation", 0.04)
        bump_weight("dialogue_exchange", 0.04)
        bump_weight("inner_state", 0.01)
        bump_bias(shot_role_bias, "dialogue_exchange", 0.035)
        bump_bias(shot_role_bias, "ensemble_relation", 0.05)
    if "performance_reaction" in modifiers:
        bump_weight("inner_state", 0.055)
        bump_weight("reaction", 0.04)
        bump_weight("relation", 0.015)
        bump_weight("visible_action", -0.02)
        bump_bias(shot_role_bias, "single_focus", 0.05)
    if "low_text" in modifiers:
        bump_weight("story", -0.045)
        bump_weight("relation", -0.02)
        bump_weight("dialogue_exchange", -0.03)
        bump_weight("visible_action", 0.04)
        bump_weight("energy", 0.04)
        raw_audio_bias += 0.025

    adapted["evidence_weights"] = _normalize_weight_map(weights)
    adapted["shot_role_bias"] = {key: round(float(value or 0.0), 3) for key, value in shot_role_bias.items()}
    adapted["tag_bias"] = {key: round(float(value or 0.0), 3) for key, value in tag_bias.items()}
    adapted["raw_audio_bias"] = round(max(raw_audio_bias, 0.0), 3)
    adapted["signal_route"] = str(signal_route or "balanced_mixed")
    adapted["signal_modifiers"] = list(dict.fromkeys(str(item) for item in (signal_modifiers or []) if str(item)))
    adapted["signal_metrics"] = {key: _clamp_unit(value) for key, value in (signal_metrics or {}).items()}
    adapted["signal_reasons"] = list(dict.fromkeys(str(item) for item in (signal_reasons or []) if str(item)))[:6]
    return adapted


def _evidence_scores(candidate_clips: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    items = list(candidate_clips or [])
    return {
        "story": _mean_value(items, "story_score"),
        "emotion": _mean_value(items, "emotion_score"),
        "energy": _mean_value(items, "energy_score"),
        "visible_action": _mean_value(items, "visible_action_score"),
        "reaction": _mean_value(items, "reaction_score"),
        "inner_state": _mean_value(items, "inner_state_support"),
        "relation": _mean_value(items, "relation_score"),
        "group_reaction": _mean_value(items, "group_reaction_score"),
        "dialogue_exchange": _mean_value(items, "dialogue_exchange_score"),
        "raw_audio_ratio": _ratio(items, lambda clip: bool(clip.get("raw_audio_worthy"))),
        "reveal_ratio": _ratio(items, lambda clip: "reveal" in set(str(tag) for tag in (clip.get("tags") or []))),
        "conflict_ratio": _ratio(items, lambda clip: "conflict" in set(str(tag) for tag in (clip.get("tags") or []))),
        "emotion_peak_ratio": _ratio(items, lambda clip: "emotion_peak" in set(str(tag) for tag in (clip.get("tags") or []))),
    }


def _infer_profile_from_signals(
    *,
    movie_title: str,
    narration_text: str,
    subtitle_segments: Sequence[Dict[str, Any]],
    plot_chunks: Sequence[Dict[str, Any]],
    candidate_clips: Sequence[Dict[str, Any]],
) -> Tuple[str, List[str], float]:
    text_corpus = _build_text_corpus(
        movie_title=movie_title,
        narration_text=narration_text,
        subtitle_segments=subtitle_segments,
        plot_chunks=plot_chunks,
        candidate_clips=candidate_clips,
    )
    keyword_scores = _keyword_scores(text_corpus)
    evidence = _evidence_scores(candidate_clips)
    signal_metrics = _signal_metrics(
        subtitle_segments=subtitle_segments,
        plot_chunks=plot_chunks,
        candidate_clips=candidate_clips,
    )
    scores: Dict[str, float] = {"general": 0.4}

    scores["action"] = keyword_scores.get("action", 0.0)
    scores["action"] += evidence["visible_action"] * 0.42 + evidence["energy"] * 0.26
    scores["action"] += evidence["conflict_ratio"] * 0.22 + evidence["raw_audio_ratio"] * 0.12
    scores["action"] += signal_metrics["kinetic_signal"] * 0.18 + (1.0 - signal_metrics["text_reliability"]) * 0.04

    scores["suspense"] = keyword_scores.get("suspense", 0.0)
    scores["suspense"] += evidence["story"] * 0.24 + evidence["inner_state"] * 0.22
    scores["suspense"] += evidence["reaction"] * 0.18 + evidence["reveal_ratio"] * 0.26
    scores["suspense"] += signal_metrics["text_reliability"] * 0.08 + signal_metrics["inner_state_signal"] * 0.07

    scores["drama"] = keyword_scores.get("drama", 0.0)
    scores["drama"] += evidence["emotion"] * 0.24 + evidence["relation"] * 0.24
    scores["drama"] += evidence["inner_state"] * 0.22 + evidence["emotion_peak_ratio"] * 0.2
    scores["drama"] += signal_metrics["inner_state_signal"] * 0.12 + signal_metrics["speech_density"] * 0.06

    scores["comedy"] = keyword_scores.get("comedy", 0.0)
    scores["comedy"] += evidence["reaction"] * 0.24 + evidence["dialogue_exchange"] * 0.24
    scores["comedy"] += evidence["group_reaction"] * 0.22 + evidence["emotion"] * 0.08
    scores["comedy"] += signal_metrics["ensemble_signal"] * 0.08 + signal_metrics["speech_density"] * 0.08

    scores["romance"] = keyword_scores.get("romance", 0.0)
    scores["romance"] += evidence["relation"] * 0.3 + evidence["inner_state"] * 0.16
    scores["romance"] += evidence["reaction"] * 0.14 + evidence["emotion_peak_ratio"] * 0.14
    scores["romance"] += signal_metrics["inner_state_signal"] * 0.1 + signal_metrics["speech_density"] * 0.06

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, winner_score = ordered[0]
    runner_up_score = ordered[1][1] if len(ordered) > 1 else 0.0
    confidence = min(max(winner_score - runner_up_score + 0.45, 0.35), 0.92)

    reasons = []
    if keyword_scores.get(winner, 0.0) >= 0.18:
        reasons.append("title_or_subtitle_keywords")
    if winner == "action" and evidence["visible_action"] >= 0.42:
        reasons.append("visible_action_signal")
    if winner == "suspense" and evidence["reveal_ratio"] >= 0.22:
        reasons.append("reveal_density")
    if winner == "drama" and (evidence["relation"] >= 0.45 or evidence["inner_state"] >= 0.42):
        reasons.append("emotion_relation_density")
    if winner == "comedy" and evidence["dialogue_exchange"] >= 0.4:
        reasons.append("reaction_banter_density")
    if winner == "romance" and evidence["relation"] >= 0.48:
        reasons.append("relationship_density")
    if signal_metrics["text_reliability"] <= 0.3:
        reasons.append("low_text_reliability")
    elif signal_metrics["speech_density"] >= 0.55:
        reasons.append("speech_dense")
    if not reasons:
        reasons.append("fallback_general_signal_mix")
    return winner, reasons, round(confidence, 3)


def resolve_highlight_profile(
    *,
    requested_profile: str = "auto",
    movie_title: str = "",
    narration_text: str = "",
    subtitle_segments: Sequence[Dict[str, Any]] | None = None,
    plot_chunks: Sequence[Dict[str, Any]] | None = None,
    candidate_clips: Sequence[Dict[str, Any]] | None = None,
    capabilities: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized = _normalized_profile_id(requested_profile)
    capabilities = dict(capabilities or detect_highlight_capabilities())
    signal_metrics = _signal_metrics(
        subtitle_segments=subtitle_segments or [],
        plot_chunks=plot_chunks or [],
        candidate_clips=candidate_clips or [],
    )
    signal_route, signal_modifiers, signal_reasons = _route_signal_profile(signal_metrics)
    if normalized != "auto":
        profile = get_highlight_profile(normalized)
        profile["source"] = "user_selected"
        profile["confidence"] = 1.0
        profile["reasons"] = ["user_selected"]
        profile["requested_id"] = normalized
        profile["capabilities"] = capabilities
        return _adapt_profile_to_signal_route(
            profile,
            signal_route=signal_route,
            signal_modifiers=signal_modifiers,
            signal_metrics=signal_metrics,
            signal_reasons=signal_reasons,
        )

    inferred_id, reasons, confidence = _infer_profile_from_signals(
        movie_title=movie_title,
        narration_text=narration_text,
        subtitle_segments=subtitle_segments or [],
        plot_chunks=plot_chunks or [],
        candidate_clips=candidate_clips or [],
    )
    if inferred_id == "auto":
        inferred_id = "general"
    profile = get_highlight_profile(inferred_id)
    profile["source"] = "auto_detected"
    profile["confidence"] = confidence
    profile["reasons"] = reasons
    profile["requested_id"] = "auto"
    profile["capabilities"] = capabilities
    return _adapt_profile_to_signal_route(
        profile,
        signal_route=signal_route,
        signal_modifiers=signal_modifiers,
        signal_metrics=signal_metrics,
        signal_reasons=signal_reasons,
    )


def _clip_intro_risk(item: Dict[str, Any]) -> float:
    stage = str(item.get("story_stage_hint", "") or "").strip().lower()
    story_position = float(item.get("story_position", 0.5) or 0.5)
    tags = {str(tag).strip().lower() for tag in (item.get("tags") or []) if str(tag).strip()}
    if story_position > 0.22:
        return 0.0

    stage_risk = 0.0
    if stage == "opening":
        stage_risk = 0.72
    elif stage == "setup":
        stage_risk = 0.52 if story_position <= 0.18 else 0.22
    elif story_position <= 0.08:
        stage_risk = 0.3

    payoff_tags = {"reveal", "conflict", "emotion_peak", "ending", "twist"}
    if tags & payoff_tags:
        stage_risk -= 0.26

    visible_action = float(item.get("visible_action_score", 0.0) or 0.0)
    reaction = float(item.get("reaction_score", 0.0) or 0.0)
    inner_state = float(item.get("inner_state_support", 0.0) or 0.0)
    relation = float(item.get("relation_score", 0.0) or 0.0)
    audio_signal = float(item.get("audio_signal_score", 0.0) or 0.0)
    audio_peak = float(item.get("audio_peak_score", 0.0) or 0.0)
    emotion = float(item.get("emotion_score", 0.0) or 0.0)
    story = float(item.get("story_score", 0.0) or 0.0)
    payoff_strength = max(
        visible_action,
        reaction,
        inner_state,
        relation,
        min(audio_signal * 0.9 + audio_peak * 0.4, 1.0),
        emotion,
        story * 0.82,
    )
    if payoff_strength >= 0.72:
        stage_risk -= 0.24
    elif payoff_strength >= 0.55:
        stage_risk -= 0.12

    scene_summary = str(item.get("scene_summary", "") or "")
    subtitle_text = str(item.get("subtitle_text", "") or "")
    if len((scene_summary + subtitle_text).strip()) < 8:
        stage_risk += 0.08
    if not (tags & payoff_tags) and not bool(item.get("raw_audio_worthy")):
        stage_risk += 0.06

    return round(max(min(stage_risk, 1.0), 0.0), 3)


def apply_highlight_profile(candidate_clips: Sequence[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    current = dict(profile or {})
    profile_id = str(current.get("id", "general") or "general")
    weights = dict(current.get("evidence_weights") or {})
    tag_bias = dict(current.get("tag_bias") or {})
    shot_role_bias = dict(current.get("shot_role_bias") or {})
    preferred_stages = {str(item).strip().lower() for item in (current.get("preferred_story_stages") or []) if str(item).strip()}
    discouraged_stages = {str(item).strip().lower() for item in (current.get("discouraged_story_stages") or []) if str(item).strip()}
    opening_penalty = float(current.get("opening_penalty", 0.0) or 0.0)
    raw_audio_bias = float(current.get("raw_audio_bias", 0.0) or 0.0)

    profiled: List[Dict[str, Any]] = []
    for clip in candidate_clips or []:
        item = dict(clip)
        base_total = float(item.get("base_total_score", item.get("total_score", 0.0) or 0.0))
        stage = str(item.get("story_stage_hint", "") or "").strip().lower()
        shot_role = str(item.get("shot_role", "") or "").strip()
        tags = {str(tag).strip() for tag in (item.get("tags") or []) if str(tag).strip()}

        fit_score = (
            float(item.get("story_score", 0.0) or 0.0) * float(weights.get("story", 0.0) or 0.0)
            + float(item.get("emotion_score", 0.0) or 0.0) * float(weights.get("emotion", 0.0) or 0.0)
            + float(item.get("energy_score", 0.0) or 0.0) * float(weights.get("energy", 0.0) or 0.0)
            + float(item.get("visible_action_score", 0.0) or 0.0) * float(weights.get("visible_action", 0.0) or 0.0)
            + float(item.get("reaction_score", 0.0) or 0.0) * float(weights.get("reaction", 0.0) or 0.0)
            + float(item.get("inner_state_support", 0.0) or 0.0) * float(weights.get("inner_state", 0.0) or 0.0)
            + float(item.get("relation_score", 0.0) or 0.0) * float(weights.get("relation", 0.0) or 0.0)
            + float(item.get("group_reaction_score", 0.0) or 0.0) * float(weights.get("group_reaction", 0.0) or 0.0)
            + float(item.get("dialogue_exchange_score", 0.0) or 0.0) * float(weights.get("dialogue_exchange", 0.0) or 0.0)
        )

        stage_bonus = 0.08 if stage in preferred_stages else -opening_penalty if stage in discouraged_stages else 0.0
        tag_bonus_value = sum(float(tag_bias.get(tag, 0.0) or 0.0) for tag in tags)
        shot_bonus = float(shot_role_bias.get(shot_role, 0.0) or 0.0)
        audio_bonus = raw_audio_bias if item.get("raw_audio_worthy") else 0.0
        intro_risk = _clip_intro_risk(item)
        intro_penalty = 0.0

        if stage == "opening" and float(item.get("story_position", 0.5) or 0.5) <= 0.12:
            stage_bonus -= opening_penalty
        if not (str(item.get("scene_summary", "") or "").strip() or str(item.get("subtitle_text", "") or "").strip()):
            stage_bonus -= 0.04
        if intro_risk > 0.0:
            intro_penalty = opening_penalty * (0.6 + intro_risk * 1.35)

        profiled_total = max(
            base_total * 0.58 + fit_score * 0.42 + stage_bonus + tag_bonus_value + shot_bonus + audio_bonus - intro_penalty,
            0.0,
        )
        if intro_risk >= 0.7 and stage in {"opening", "setup"}:
            profiled_total = min(profiled_total, max(base_total * 0.72, fit_score * 0.88))

        item["base_total_score"] = round(base_total, 3)
        item["profile_fit_score"] = round(max(fit_score, 0.0), 3)
        item["intro_risk_score"] = round(intro_risk, 3)
        item["profile_intro_penalty"] = round(max(intro_penalty, 0.0), 3)
        item["profile_total_score"] = round(profiled_total, 3)
        item["total_score"] = round(profiled_total, 3)
        item["highlight_profile_id"] = profile_id
        item["highlight_profile_source"] = str(current.get("source", "") or "")
        if intro_penalty >= 0.08:
            item["selection_reason"] = list(dict.fromkeys(list(item.get("selection_reason") or []) + ["intro_penalized"]))
        profiled.append(item)
    return profiled
