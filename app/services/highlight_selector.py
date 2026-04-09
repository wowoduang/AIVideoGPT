from __future__ import annotations

import re
from typing import Dict, List


_ACTION_MARKERS = ["走", "跑", "冲", "追", "打", "开门", "推开", "回头", "转身", "拿起", "扑", "躲开", "盯着", "跪下"]
_REACTION_MARKERS = ["沉默", "犹豫", "停顿", "愣住", "愣了", "眼神", "神情", "表情", "看着", "迟疑", "发愣", "不说话"]
_INNER_STATE_MARKERS = ["心里", "内心", "意识到", "明白", "怀疑", "后悔", "不敢", "盘算", "决定", "觉得", "以为", "终于明白"]
_RELATION_MARKERS = ["两人", "两个人", "关系", "信任", "背叛", "和解", "联手", "疏远", "对立", "反目", "互相", "对方"]
_OVERVIEW_MARKERS = ["原来", "其实", "直到这时", "说白了", "本质上", "整个", "这一刻", "最终", "最后"]


def _story_stage_from_plot(plot_function: str, plot_role: str, story_position: float) -> str:
    plot_function = str(plot_function or "").strip()
    plot_role = str(plot_role or "").strip().lower()
    if plot_function == "结局收束" or plot_role == "ending" or story_position >= 0.88:
        return "ending"
    if plot_function == "反转" or plot_role == "twist":
        return "turning_point"
    if plot_function == "情感爆发":
        return "climax"
    if plot_function == "冲突升级" or plot_role == "conflict":
        return "conflict"
    if plot_function == "信息揭露":
        return "reveal"
    if plot_function in {"铺垫", "节奏缓冲"} or plot_role == "setup":
        return "opening" if story_position <= 0.12 else "setup"
    return "setup"


def _normalize_level(value: str) -> float:
    mapping = {
        "critical": 1.0,
        "high": 0.9,
        "core": 0.9,
        "strong": 0.8,
        "medium": 0.6,
        "normal": 0.5,
        "low": 0.25,
        "brief": 0.2,
    }
    return mapping.get(str(value or "").strip().lower(), 0.0)


def _score_clip(clip: Dict) -> Dict:
    tags = set(clip.get("tags") or [])
    story_score = float(clip.get("story_score", 0.0) or 0.0)
    emotion_score = float(clip.get("emotion_score", 0.0) or 0.0)
    energy_score = float(clip.get("energy_score", 0.0) or 0.0)
    audio_signal_score = float(clip.get("audio_signal_score", 0.0) or 0.0)
    audio_dynamic_score = float(clip.get("audio_dynamic_score", 0.0) or 0.0)
    audio_onset_score = float(clip.get("audio_onset_score", 0.0) or 0.0)

    if "reveal" in tags or "twist" in tags:
        story_score += 0.2
    if "conflict" in tags or "emotion_peak" in tags:
        emotion_score += 0.15
    if clip.get("raw_audio_worthy"):
        energy_score += 0.1
    if audio_signal_score > 0.0:
        energy_score = max(energy_score, energy_score * 0.58 + audio_signal_score * 0.52)
    if audio_dynamic_score >= 0.45:
        emotion_score += min(audio_dynamic_score * 0.14, 0.1)
    if audio_onset_score >= 0.48:
        energy_score += min(audio_onset_score * 0.08, 0.06)

    clip["story_score"] = round(min(story_score, 1.2), 3)
    clip["emotion_score"] = round(min(emotion_score, 1.2), 3)
    clip["energy_score"] = round(min(energy_score, 1.2), 3)
    clip["total_score"] = round(
        clip["story_score"] * 0.5 + clip["emotion_score"] * 0.3 + clip["energy_score"] * 0.2,
        3,
    )
    return clip


def _clip_haystack(clip: Dict) -> str:
    return " ".join(
        [
            str(clip.get("subtitle_text", "") or ""),
            str(clip.get("scene_summary", "") or ""),
            str(clip.get("plot_function", "") or ""),
            str(clip.get("plot_role", "") or ""),
            " ".join(str(item) for item in (clip.get("tags") or [])),
        ]
    )


def _marker_overlap_score(haystack: str, markers: List[str]) -> float:
    valid_markers = [marker for marker in (markers or []) if str(marker or "").strip()]
    if not valid_markers:
        return 0.0
    matched = sum(1 for marker in valid_markers if marker in haystack)
    return matched / max(len(valid_markers), 1)


def _marker_match_count(haystack: str, markers: List[str]) -> int:
    return sum(1 for marker in (markers or []) if str(marker or "").strip() and marker in haystack)


def _speaker_turn_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{1,8}[：:]", str(text or "")))


def _clamp_score(value: float) -> float:
    return round(max(min(float(value or 0.0), 1.0), 0.0), 3)


def _speaker_turn_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{1,8}[\uFF1A:]", str(text or "")))


def _normalize_name_list(values) -> List[str]:
    return [
        value
        for value in dict.fromkeys(str(item or "").strip() for item in (values or []) if str(item or "").strip())
    ]


def _extract_speaker_names_from_text(text: str) -> List[str]:
    return _normalize_name_list(re.findall(r"([\u4e00-\u9fffA-Za-z0-9]{1,8})[\uFF1A:]", str(text or "")))


def _derive_interaction_targets(character_names: List[str], speaker_names: List[str]) -> List[str]:
    character_set = [name for name in (character_names or []) if name]
    speaker_set = {name for name in (speaker_names or []) if name}
    targets = [name for name in character_set if name not in speaker_set]
    if targets:
        return _normalize_name_list(targets)
    if len(speaker_names or []) >= 2:
        return _normalize_name_list(list(speaker_names or [])[1:])
    return []


def _normalize_exchange_pairs(values) -> List[str]:
    pairs: List[str] = []
    for item in (values or []):
        raw = str(item or "").strip()
        if not raw or "->" not in raw:
            continue
        left, right = (part.strip() for part in raw.split("->", 1))
        if not left or not right or left == right:
            continue
        pairs.append(f"{left}->{right}")
    return pairs


def _derive_exchange_pairs(speaker_sequence: List[str]) -> List[str]:
    turns: List[str] = []
    for item in (speaker_sequence or []):
        speaker = str(item or "").strip()
        if not speaker:
            continue
        if not turns or speaker != turns[-1]:
            turns.append(speaker)
    pairs: List[str] = []
    for left, right in zip(turns, turns[1:]):
        if left and right and left != right:
            pairs.append(f"{left}->{right}")
    return pairs


def _derive_targets_from_pairs(exchange_pairs: List[str], fallback_targets: List[str]) -> List[str]:
    targets: List[str] = []
    for pair in _normalize_exchange_pairs(exchange_pairs):
        _, right = pair.split("->", 1)
        if right and right not in targets:
            targets.append(right)
    if targets:
        return targets
    return _normalize_name_list(fallback_targets)


def _derive_pressure_direction(
    exchange_pairs: List[str],
    speaker_sequence: List[str],
    speaker_names: List[str],
) -> tuple[List[str], List[str]]:
    incoming_sources: Dict[str, List[str]] = {}
    for pair in _normalize_exchange_pairs(exchange_pairs):
        left, right = pair.split("->", 1)
        if left and right and left != right:
            incoming_sources.setdefault(right, []).append(left)

    pressure_targets = [
        target
        for target, sources in incoming_sources.items()
        if len(_normalize_name_list(sources)) >= 2
    ]
    if not pressure_targets:
        return [], []

    ordered_speakers = _normalize_name_list(list(speaker_sequence or []) + list(speaker_names or []))
    pressure_sources: List[str] = []
    for pair in _normalize_exchange_pairs(exchange_pairs):
        left, right = pair.split("->", 1)
        if right in pressure_targets and left not in pressure_targets and left not in pressure_sources:
            pressure_sources.append(left)
    if not pressure_sources:
        pressure_sources = [name for name in ordered_speakers if name not in pressure_targets]
    return _normalize_name_list(pressure_sources), _normalize_name_list(pressure_targets)


def _pick_shot_role(role_scores: Dict[str, float]) -> str:
    priority = {
        "single_focus": 5,
        "dialogue_exchange": 4,
        "ensemble_relation": 3,
        "action_follow": 2,
        "narrative_bridge": 1,
    }
    return max(
        role_scores,
        key=lambda key: (float(role_scores.get(key, 0.0) or 0.0), priority.get(key, 0), key),
    )


def enrich_candidate_evidence(clip: Dict) -> Dict:
    enriched = dict(clip or {})
    haystack = _clip_haystack(enriched)
    subtitle_text = str(enriched.get("subtitle_text", "") or "")
    tags = set(str(item) for item in (enriched.get("tags") or []))
    source = str(enriched.get("source", "") or "")
    duration = float(enriched.get("duration", 0.0) or 0.0)
    emotion_score = min(float(enriched.get("emotion_score", 0.0) or 0.0), 1.0)
    story_stage = str(enriched.get("story_stage_hint", "") or "")
    raw_audio = bool(enriched.get("raw_audio_worthy"))
    explicit_speaker_names = _normalize_name_list(enriched.get("speaker_names") or [])
    inferred_speaker_names = _extract_speaker_names_from_text(subtitle_text)
    explicit_speaker_sequence = [
        str(item or "").strip()
        for item in (enriched.get("speaker_sequence") or [])
        if str(item or "").strip()
    ]
    speaker_sequence = list(explicit_speaker_sequence or inferred_speaker_names or explicit_speaker_names)
    speaker_names = _normalize_name_list(explicit_speaker_names + inferred_speaker_names)
    if speaker_sequence:
        speaker_names = _normalize_name_list(list(speaker_names) + list(speaker_sequence))
    character_names = _normalize_name_list(list(enriched.get("character_names") or []) + speaker_names)
    explicit_exchange_pairs = _normalize_exchange_pairs(enriched.get("exchange_pairs") or [])
    exchange_pairs = list(explicit_exchange_pairs or _derive_exchange_pairs(speaker_sequence))
    interaction_target_names = _normalize_name_list(enriched.get("interaction_target_names") or [])
    if not interaction_target_names:
        interaction_target_names = _derive_interaction_targets(character_names, speaker_names)
    interaction_target_names = _derive_targets_from_pairs(exchange_pairs, interaction_target_names)
    explicit_pressure_sources = _normalize_name_list(enriched.get("pressure_source_names") or [])
    explicit_pressure_targets = _normalize_name_list(enriched.get("pressure_target_names") or [])
    derived_pressure_sources, derived_pressure_targets = _derive_pressure_direction(
        exchange_pairs,
        speaker_sequence,
        speaker_names,
    )
    pressure_source_names = list(explicit_pressure_sources or derived_pressure_sources)
    pressure_target_names = list(explicit_pressure_targets or derived_pressure_targets)
    action_marker_count = _marker_match_count(haystack, _ACTION_MARKERS)
    reaction_marker_count = _marker_match_count(haystack, _REACTION_MARKERS)
    inner_marker_count = _marker_match_count(haystack, _INNER_STATE_MARKERS)
    relation_marker_count = _marker_match_count(haystack, _RELATION_MARKERS)
    overview_marker_count = _marker_match_count(haystack, _OVERVIEW_MARKERS)
    explicit_speaker_turns = int(enriched.get("speaker_turns", 0) or 0)
    speaker_turns = explicit_speaker_turns if explicit_speaker_turns > 0 else len(speaker_sequence) or _speaker_turn_count(subtitle_text)
    exchange_pair_count = len(exchange_pairs)
    exchange_participants = _normalize_name_list(
        [name for pair in exchange_pairs for name in pair.split("->", 1)]
    )
    relation_context = relation_marker_count > 0 or len(character_names) >= 2 or speaker_turns >= 2

    visible_action_score = 0.12 + _marker_overlap_score(haystack, _ACTION_MARKERS) * 0.34
    if action_marker_count >= 2:
        visible_action_score += 0.16
    elif action_marker_count == 1:
        visible_action_score += 0.08
    if source == "scene":
        visible_action_score += 0.08
    if raw_audio:
        visible_action_score += 0.06
    if 1.2 <= duration <= 6.5:
        visible_action_score += 0.08
    if {"conflict", "emotion_peak"} & tags:
        visible_action_score += 0.08

    reaction_score = 0.12 + emotion_score * 0.28 + _marker_overlap_score(haystack, _REACTION_MARKERS) * 0.22
    if reaction_marker_count >= 2:
        reaction_score += 0.08
    elif reaction_marker_count == 1:
        reaction_score += 0.04
    if source == "scene":
        reaction_score += 0.06
    if raw_audio:
        reaction_score += 0.05
    if 1.1 <= duration <= 4.6:
        reaction_score += 0.06

    inner_state_support = 0.1 + emotion_score * 0.2 + _marker_overlap_score(haystack, _INNER_STATE_MARKERS) * 0.28
    if inner_marker_count >= 2:
        inner_state_support += 0.12
    elif inner_marker_count == 1:
        inner_state_support += 0.06
    if source == "scene":
        inner_state_support += 0.1
    if raw_audio:
        inner_state_support += 0.08
    if len(character_names) <= 1:
        inner_state_support += 0.06
    if story_stage in {"turning_point", "reveal", "climax", "ending"}:
        inner_state_support += 0.08

    relation_score = 0.12 + _marker_overlap_score(haystack, _RELATION_MARKERS) * 0.28
    if relation_marker_count >= 2:
        relation_score += 0.12
    elif relation_marker_count == 1:
        relation_score += 0.06
    if len(character_names) >= 2:
        relation_score += 0.24
    elif len(character_names) == 1:
        relation_score += 0.04
    if speaker_turns >= 2:
        relation_score += 0.12
    elif speaker_turns == 1:
        relation_score += 0.04
    if exchange_pair_count >= 2:
        relation_score += 0.12
    elif exchange_pair_count == 1:
        relation_score += 0.06
    if len(exchange_participants) >= 3:
        relation_score += 0.06
    if source == "scene":
        relation_score += 0.08
    if {"conflict", "reveal"} & tags and relation_context:
        relation_score += 0.08
    if story_stage in {"conflict", "turning_point", "reveal", "ending"} and relation_context:
        relation_score += 0.08

    narrative_overview_score = 0.12 + _marker_overlap_score(haystack, _OVERVIEW_MARKERS) * 0.22
    if overview_marker_count >= 2:
        narrative_overview_score += 0.08
    elif overview_marker_count == 1:
        narrative_overview_score += 0.04
    if source in {"scene", "hybrid"}:
        narrative_overview_score += 0.08
    if 2.0 <= duration <= 8.0:
        narrative_overview_score += 0.08
    if enriched.get("plot_function"):
        narrative_overview_score += 0.1
    if story_stage in {"reveal", "ending", "turning_point"}:
        narrative_overview_score += 0.06

    group_reaction_score = 0.08 + reaction_score * 0.16 + relation_score * 0.18 + narrative_overview_score * 0.14
    if len(character_names) >= 3:
        group_reaction_score += 0.18
    elif len(character_names) == 2:
        group_reaction_score += 0.06
    if len(exchange_participants) >= 3:
        group_reaction_score += 0.14
    elif exchange_pair_count >= 2:
        group_reaction_score += 0.06
    if len(pressure_target_names) == 1 and len(pressure_source_names) >= 2:
        group_reaction_score += 0.18
    if speaker_turns >= 3:
        group_reaction_score += 0.12
    elif speaker_turns == 2:
        group_reaction_score += 0.05
    if source == "scene":
        group_reaction_score += 0.06
    if raw_audio:
        group_reaction_score += 0.04
    if relation_context:
        group_reaction_score += 0.06

    evidence_scores = {
        "visible_action_score": _clamp_score(visible_action_score),
        "reaction_score": _clamp_score(reaction_score),
        "inner_state_support": _clamp_score(inner_state_support),
        "relation_score": _clamp_score(relation_score),
        "narrative_overview_score": _clamp_score(narrative_overview_score),
    }
    solo_focus_score = 0.08 + evidence_scores["reaction_score"] * 0.14 + evidence_scores["inner_state_support"] * 0.26
    if len(character_names) <= 1:
        solo_focus_score += 0.22
    if len(speaker_names) <= 1:
        solo_focus_score += 0.06
    if len(interaction_target_names) <= 1:
        solo_focus_score += 0.04
    if speaker_turns == 0:
        solo_focus_score += 0.08
    elif speaker_turns == 1:
        solo_focus_score += 0.04
    if source == "scene":
        solo_focus_score += 0.06
    if raw_audio:
        solo_focus_score += 0.06
    if 1.1 <= duration <= 4.8:
        solo_focus_score += 0.06
    if reaction_marker_count > 0 or inner_marker_count > 0:
        solo_focus_score += 0.08

    dialogue_exchange_score = 0.08 + evidence_scores["relation_score"] * 0.26 + evidence_scores["reaction_score"] * 0.08
    if speaker_turns >= 2:
        dialogue_exchange_score += 0.26
    elif speaker_turns == 1:
        dialogue_exchange_score += 0.08
    if len(speaker_names) >= 2:
        dialogue_exchange_score += 0.18
    elif len(speaker_names) == 1:
        dialogue_exchange_score += 0.05
    if exchange_pair_count >= 2:
        dialogue_exchange_score += 0.14
    elif exchange_pair_count == 1:
        dialogue_exchange_score += 0.08
    if len(character_names) >= 2:
        dialogue_exchange_score += 0.18
    elif len(character_names) == 1:
        dialogue_exchange_score += 0.04
    if interaction_target_names:
        dialogue_exchange_score += 0.08
    if raw_audio:
        dialogue_exchange_score += 0.05
    if source == "scene":
        dialogue_exchange_score += 0.05
    if 1.3 <= duration <= 5.5:
        dialogue_exchange_score += 0.06
    if relation_context:
        dialogue_exchange_score += 0.06

    ensemble_scene_score = 0.08 + evidence_scores["relation_score"] * 0.22 + evidence_scores["narrative_overview_score"] * 0.14
    if len(character_names) >= 2:
        ensemble_scene_score += 0.2
    elif len(character_names) == 1:
        ensemble_scene_score += 0.05
    if len(exchange_participants) >= 3:
        ensemble_scene_score += 0.16
    elif exchange_pair_count >= 2:
        ensemble_scene_score += 0.08
    if len(interaction_target_names) >= 1:
        ensemble_scene_score += 0.08
    if speaker_turns >= 2:
        ensemble_scene_score += 0.1
    if source == "scene":
        ensemble_scene_score += 0.06
    if 2.0 <= duration <= 7.0:
        ensemble_scene_score += 0.06
    if relation_context:
        ensemble_scene_score += 0.08

    priority = {
        "inner_state_support": 5,
        "relation_score": 4,
        "visible_action_score": 3,
        "narrative_overview_score": 2,
        "reaction_score": 1,
    }
    enriched.update(evidence_scores)
    enriched["character_names"] = character_names
    enriched["speaker_sequence"] = speaker_sequence
    enriched["speaker_names"] = speaker_names
    enriched["exchange_pairs"] = exchange_pairs
    enriched["interaction_target_names"] = interaction_target_names
    enriched["pressure_source_names"] = pressure_source_names
    enriched["pressure_target_names"] = pressure_target_names
    enriched["group_reaction_score"] = _clamp_score(group_reaction_score)
    enriched["speaker_turns"] = int(speaker_turns)
    enriched["solo_focus_score"] = _clamp_score(solo_focus_score)
    enriched["dialogue_exchange_score"] = _clamp_score(dialogue_exchange_score)
    enriched["ensemble_scene_score"] = _clamp_score(ensemble_scene_score)
    enriched["primary_evidence"] = max(
        evidence_scores,
        key=lambda key: (float(evidence_scores.get(key, 0.0) or 0.0), priority.get(key, 0), key),
    )
    role_scores = {
        "action_follow": _clamp_score(
            evidence_scores["visible_action_score"] * 0.8
            + (0.14 if action_marker_count >= 2 else 0.08 if action_marker_count == 1 else 0.0)
            + (0.06 if speaker_turns == 0 else 0.02 if speaker_turns == 1 else -0.04)
            + (0.06 if len(character_names) <= 1 else 0.0)
            + (0.05 if enriched["primary_evidence"] == "visible_action_score" else 0.0)
        ),
        "single_focus": _clamp_score(
            enriched["solo_focus_score"]
            + (0.04 if enriched["primary_evidence"] in {"inner_state_support", "reaction_score"} else 0.0)
        ),
        "dialogue_exchange": _clamp_score(
            enriched["dialogue_exchange_score"] + (0.04 if speaker_turns >= 2 else 0.0)
        ),
        "ensemble_relation": _clamp_score(
            enriched["ensemble_scene_score"] + (0.04 if len(character_names) >= 2 else 0.0)
        ),
        "narrative_bridge": _clamp_score(
            evidence_scores["narrative_overview_score"]
            + (0.06 if source in {"scene", "hybrid"} else 0.0)
            + (0.04 if story_stage in {"opening", "ending", "reveal"} else 0.0)
        ),
    }
    enriched["shot_role"] = _pick_shot_role(role_scores)
    return enriched


def _extract_character_candidates(text: str) -> List[str]:
    content = str(text or "").strip()
    if not content:
        return []
    candidates = re.findall(r"[\u4e00-\u9fff]{2,4}", content)
    blacklist = {
        "他们", "她们", "你们", "我们", "这里", "那里", "因为", "所以", "如果", "但是",
        "最后", "开始", "事情", "时候", "自己", "已经", "一个", "这个", "那个",
    }
    result: List[str] = []
    for item in candidates:
        if item in blacklist:
            continue
        if item not in result:
            result.append(item)
    return result[:6]


def build_candidate_from_plot_chunk(chunk: Dict, index: int, total: int = 0) -> Dict:
    start = float(chunk.get("start", 0.0) or 0.0)
    end = float(chunk.get("end", start) or start)
    if end <= start:
        end = start + 0.5

    importance = _normalize_level(chunk.get("importance_level"))
    attraction = _normalize_level(chunk.get("attraction_level"))
    level = _normalize_level(chunk.get("narration_level"))
    raw_audio = bool(
        chunk.get("raw_voice_retain_suggestion")
        or chunk.get("audio_strategy") == "raw_voice"
    )

    plot_function_raw = str(chunk.get("plot_function", "") or "").strip()
    plot_function = plot_function_raw.lower()
    plot_role = str(chunk.get("plot_role", "") or "").strip()
    importance_level = str(chunk.get("importance_level", "") or "").strip()
    attraction_level = str(chunk.get("attraction_level", "") or "").strip()
    narration_level = str(chunk.get("narration_level", "") or "").strip()
    story_position = round((index - 1) / max(total - 1, 1), 3) if total > 1 else 0.5
    tags: List[str] = []
    if any(key in plot_function for key in ("reveal", "twist", "truth")) or plot_function_raw in {"反转", "信息揭露"}:
        tags.append("reveal")
    if any(key in plot_function for key in ("conflict", "fight", "crisis")) or plot_function_raw == "冲突升级":
        tags.append("conflict")
    if any(key in plot_function for key in ("emotion", "break", "climax")) or plot_function_raw == "情感爆发":
        tags.append("emotion_peak")
    if plot_function_raw == "结局收束":
        tags.append("ending")
    if raw_audio:
        tags.append("raw_audio")

    story_score = max(
        float(chunk.get("highlight_score", 0.0) or 0.0),
        importance,
        attraction,
    )
    emotion_score = max(attraction, level)
    energy_score = 0.65 if raw_audio else 0.35

    clip = {
        "clip_id": f"clip_{index:04d}",
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(max(end - start, 0.5), 3),
        "source": "hybrid",
        "story_index": index,
        "story_position": story_position,
        "story_stage_hint": _story_stage_from_plot(plot_function_raw, plot_role, story_position),
        "plot_function": plot_function_raw,
        "plot_role": plot_role,
        "importance_level": importance_level,
        "attraction_level": attraction_level,
        "narration_level": narration_level,
        "subtitle_text": str(chunk.get("aligned_subtitle_text", "") or ""),
        "scene_summary": str(chunk.get("real_narrative_state", "") or chunk.get("surface_dialogue_meaning", "") or ""),
        "energy_score": energy_score,
        "story_score": story_score,
        "emotion_score": emotion_score,
        "raw_audio_worthy": raw_audio,
        "tags": tags,
        "source_scene_id": str(chunk.get("scene_id", "") or ""),
        "source_segment_ids": list(chunk.get("subtitle_ids") or []),
        "speaker_sequence": list(chunk.get("speaker_sequence") or []),
        "speaker_names": _normalize_name_list(chunk.get("speaker_names") or []),
        "speaker_turns": int(chunk.get("speaker_turns", 0) or 0),
        "exchange_pairs": _normalize_exchange_pairs(chunk.get("exchange_pairs") or []),
        "interaction_target_names": _normalize_name_list(chunk.get("interaction_target_names") or []),
        "pressure_source_names": _normalize_name_list(chunk.get("pressure_source_names") or []),
        "pressure_target_names": _normalize_name_list(chunk.get("pressure_target_names") or []),
        "character_names": _extract_character_candidates(
            " ".join(
                [
                    str(chunk.get("aligned_subtitle_text", "") or ""),
                    str(chunk.get("real_narrative_state", "") or ""),
                    str(chunk.get("surface_dialogue_meaning", "") or ""),
                ]
            )
        ),
        "selection_reason": [],
    }
    return enrich_candidate_evidence(_score_clip(clip))


def apply_audio_signal_scores(clip: Dict, audio_metrics: Dict) -> Dict:
    enriched = dict(clip or {})
    metrics = dict(audio_metrics or {})
    if not metrics:
        return enrich_candidate_evidence(_score_clip(enriched))

    audio_signal_score = float(metrics.get("audio_signal_score", 0.0) or 0.0)
    audio_peak_score = float(metrics.get("audio_peak_score", 0.0) or 0.0)
    audio_dynamic_score = float(metrics.get("audio_dynamic_score", 0.0) or 0.0)
    audio_onset_score = float(metrics.get("audio_onset_score", 0.0) or 0.0)
    audio_rms_score = float(metrics.get("audio_rms_score", 0.0) or 0.0)

    enriched["audio_rms_score"] = round(audio_rms_score, 3)
    enriched["audio_onset_score"] = round(audio_onset_score, 3)
    enriched["audio_dynamic_score"] = round(audio_dynamic_score, 3)
    enriched["audio_signal_score"] = round(audio_signal_score, 3)
    enriched["audio_peak_score"] = round(audio_peak_score, 3)

    tags = list(dict.fromkeys(list(enriched.get("tags") or [])))
    if audio_signal_score >= 0.55:
        tags.append("audio_signal")
    if audio_peak_score >= 0.7:
        tags.append("audio_peak")
    if audio_dynamic_score >= 0.48:
        tags.append("audio_dynamic")
    if audio_signal_score >= 0.58 or audio_peak_score >= 0.72:
        enriched["raw_audio_worthy"] = True
    enriched["tags"] = tags

    reasons = list(dict.fromkeys(list(enriched.get("selection_reason") or [])))
    if audio_signal_score >= 0.62:
        reasons.append("audio_signal_peak")
    if audio_dynamic_score >= 0.52:
        reasons.append("audio_dynamic_peak")
    enriched["selection_reason"] = reasons
    return enrich_candidate_evidence(_score_clip(enriched))


def select_highlight_clips(candidate_clips: List[Dict], top_k: int = 12) -> List[Dict]:
    if not candidate_clips:
        return []

    ordered = sorted(
        (_score_clip(dict(item)) for item in candidate_clips),
        key=lambda x: (float(x.get("total_score", 0.0) or 0.0), float(x.get("duration", 0.0) or 0.0)),
        reverse=True,
    )
    selected = ordered[:max(int(top_k), 1)]
    for item in selected:
        reasons: List[str] = []
        if float(item.get("story_score", 0.0) or 0.0) >= 0.8:
            reasons.append("story_peak")
        if float(item.get("emotion_score", 0.0) or 0.0) >= 0.7:
            reasons.append("emotion_peak")
        if item.get("raw_audio_worthy"):
            reasons.append("raw_audio_keep")
        item["selection_reason"] = reasons or ["highlight"]
    return sorted(selected, key=lambda x: float(x.get("start", 0.0) or 0.0))
