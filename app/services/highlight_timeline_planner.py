from __future__ import annotations

from typing import Dict, List


_MIN_CLIP_SECONDS = 1.0
_MERGE_GAP_SECONDS = 1.0
_TARGET_FILL_RATIO = 1.05


def _sorted_unique(values: List) -> List:
    return sorted(
        dict.fromkeys(value for value in (values or []) if value not in (None, "")),
        key=lambda value: str(value),
    )


def _ordered_unique(values: List) -> List:
    return list(dict.fromkeys(value for value in (values or []) if value not in (None, "")))


def _merge_if_close(items: List[Dict], gap_threshold: float = _MERGE_GAP_SECONDS) -> List[Dict]:
    if not items:
        return []

    ordered = sorted(items, key=lambda item: float(item.get("start", 0.0) or 0.0))
    merged = [dict(ordered[0])]
    for item in ordered[1:]:
        current = dict(item)
        prev = merged[-1]
        prev_end = float(prev.get("end", 0.0) or 0.0)
        current_start = float(current.get("start", 0.0) or 0.0)
        if prev.get("prevent_merge") or current.get("prevent_merge"):
            merged.append(current)
            continue
        if current_start - prev_end > gap_threshold:
            merged.append(current)
            continue

        prev["end"] = round(max(prev_end, float(current.get("end", prev_end) or prev_end)), 3)
        prev["duration"] = round(float(prev["end"]) - float(prev.get("start", 0.0) or 0.0), 3)
        prev["total_score"] = round(
            max(float(prev.get("total_score", 0.0) or 0.0), float(current.get("total_score", 0.0) or 0.0)),
            3,
        )
        prev["story_score"] = round(
            max(float(prev.get("story_score", 0.0) or 0.0), float(current.get("story_score", 0.0) or 0.0)),
            3,
        )
        prev["emotion_score"] = round(
            max(float(prev.get("emotion_score", 0.0) or 0.0), float(current.get("emotion_score", 0.0) or 0.0)),
            3,
        )
        prev["energy_score"] = round(
            max(float(prev.get("energy_score", 0.0) or 0.0), float(current.get("energy_score", 0.0) or 0.0)),
            3,
        )
        for field in (
            "visible_action_score",
            "reaction_score",
            "inner_state_support",
            "relation_score",
            "narrative_overview_score",
            "group_reaction_score",
            "solo_focus_score",
            "dialogue_exchange_score",
            "ensemble_scene_score",
            "speaker_turns",
        ):
            if current.get(field) in (None, ""):
                continue
            prev_value = prev.get(field)
            if prev_value in (None, ""):
                prev[field] = current.get(field)
                continue
            try:
                prev[field] = round(max(float(prev_value), float(current.get(field))), 3)
            except (TypeError, ValueError):
                prev[field] = prev_value
        prev["raw_audio_worthy"] = bool(prev.get("raw_audio_worthy") or current.get("raw_audio_worthy"))
        prev["selection_reason"] = _sorted_unique(
            list(prev.get("selection_reason") or []) + list(current.get("selection_reason") or [])
        )
        prev["source_segment_ids"] = _sorted_unique(
            list(prev.get("source_segment_ids") or []) + list(current.get("source_segment_ids") or [])
        )
        prev["tags"] = _sorted_unique(list(prev.get("tags") or []) + list(current.get("tags") or []))
        prev["character_names"] = _sorted_unique(
            list(prev.get("character_names") or []) + list(current.get("character_names") or [])
        )
        prev["speaker_names"] = _sorted_unique(
            list(prev.get("speaker_names") or []) + list(current.get("speaker_names") or [])
        )
        prev["speaker_sequence"] = list(prev.get("speaker_sequence") or []) + list(current.get("speaker_sequence") or [])
        prev["exchange_pairs"] = _ordered_unique(
            list(prev.get("exchange_pairs") or []) + list(current.get("exchange_pairs") or [])
        )
        prev["interaction_target_names"] = _sorted_unique(
            list(prev.get("interaction_target_names") or []) + list(current.get("interaction_target_names") or [])
        )
        prev["pressure_source_names"] = _sorted_unique(
            list(prev.get("pressure_source_names") or []) + list(current.get("pressure_source_names") or [])
        )
        prev["pressure_target_names"] = _sorted_unique(
            list(prev.get("pressure_target_names") or []) + list(current.get("pressure_target_names") or [])
        )
        prev["prevent_merge"] = bool(prev.get("prevent_merge") or current.get("prevent_merge"))
        if not prev.get("primary_evidence") and current.get("primary_evidence"):
            prev["primary_evidence"] = current.get("primary_evidence")
        prev_role = str(prev.get("shot_role", "") or "")
        current_role = str(current.get("shot_role", "") or "")
        if prev_role and current_role and prev_role != current_role:
            prev["shot_role"] = "mixed"
        elif not prev_role and current_role:
            prev["shot_role"] = current_role
        if len(str(current.get("scene_summary", "") or "")) > len(str(prev.get("scene_summary", "") or "")):
            prev["scene_summary"] = str(current.get("scene_summary", "") or "")
        if len(str(current.get("subtitle_text", "") or "")) > len(str(prev.get("subtitle_text", "") or "")):
            prev["subtitle_text"] = str(current.get("subtitle_text", "") or "")
    return merged


def _clip_priority(item: Dict) -> float:
    reasons = set(str(value) for value in (item.get("selection_reason") or []))
    tags = set(str(value) for value in (item.get("tags") or []))
    score = float(item.get("total_score", 0.0) or 0.0)
    duration = float(item.get("duration", 0.0) or 0.0)
    bonus = 0.0

    if "story_peak" in reasons or {"reveal", "twist"} & tags:
        bonus += 0.25
    if "emotion_peak" in reasons or {"conflict", "emotion_peak"} & tags:
        bonus += 0.18
    if "coverage_anchor" in reasons:
        bonus += 0.12
    if "opening_anchor" in reasons or "ending_anchor" in reasons:
        bonus += 0.12
    if "scene_anchor" in reasons:
        bonus += 0.06
    if "chronology_anchor" in reasons:
        bonus += 0.04
    if item.get("raw_audio_worthy") or "raw_audio_keep" in reasons:
        bonus += 0.08
    if 4.0 <= duration <= 18.0:
        bonus += 0.05

    return max(round(score + bonus, 3), 0.12)


def _choose_clips(items: List[Dict], target_duration_seconds: int) -> List[Dict]:
    if not items:
        return []

    ordered = sorted(
        (dict(item) for item in items),
        key=lambda item: (
            _clip_priority(item),
            float(item.get("total_score", 0.0) or 0.0),
            float(item.get("duration", 0.0) or 0.0),
        ),
        reverse=True,
    )

    chosen: List[Dict] = []
    accumulated = 0.0
    threshold = max(
        float(target_duration_seconds) * _TARGET_FILL_RATIO,
        min(float(target_duration_seconds) + 8.0, float(target_duration_seconds) * 1.2),
    )

    for item in ordered:
        chosen.append(dict(item))
        accumulated += max(float(item.get("duration", 0.0) or 0.0), _MIN_CLIP_SECONDS)
        if accumulated >= threshold:
            break

    if not chosen:
        chosen = [dict(ordered[0])]

    return sorted(chosen, key=lambda item: float(item.get("start", 0.0) or 0.0))


def _min_keep_seconds(item: Dict) -> float:
    available = max(float(item.get("duration", 0.0) or 0.0), _MIN_CLIP_SECONDS)
    reasons = set(str(value) for value in (item.get("selection_reason") or []))
    tags = set(str(value) for value in (item.get("tags") or []))
    base = 1.4

    if "story_peak" in reasons or {"reveal", "twist"} & tags:
        base += 1.0
    elif "emotion_peak" in reasons or {"conflict", "emotion_peak"} & tags:
        base += 0.7
    elif item.get("raw_audio_worthy"):
        base += 0.5

    return round(min(available, max(base, _MIN_CLIP_SECONDS)), 3)


def _rebalance_durations(planned: List[float], target_duration_seconds: float, raw_durations: List[float]) -> List[float]:
    adjusted = [
        min(max(float(duration), _MIN_CLIP_SECONDS), max(float(raw), _MIN_CLIP_SECONDS))
        for duration, raw in zip(planned, raw_durations)
    ]
    diff = round(float(target_duration_seconds) - sum(adjusted), 6)

    if diff < 0:
        for idx in sorted(range(len(adjusted)), key=lambda index: adjusted[index], reverse=True):
            if diff >= -0.05:
                break
            reducible = max(adjusted[idx] - _MIN_CLIP_SECONDS, 0.0)
            if reducible <= 0:
                continue
            cut = min(reducible, -diff)
            adjusted[idx] -= cut
            diff += cut
    elif diff > 0:
        for idx in sorted(
            range(len(adjusted)),
            key=lambda index: max(float(raw_durations[index]) - adjusted[index], 0.0),
            reverse=True,
        ):
            if diff <= 0.05:
                break
            room = max(float(raw_durations[idx]) - adjusted[idx], 0.0)
            if room <= 0:
                continue
            add = min(room, diff)
            adjusted[idx] += add
            diff -= add

    return [round(max(min(value, raw), _MIN_CLIP_SECONDS), 3) for value, raw in zip(adjusted, raw_durations)]


def _allocate_durations(items: List[Dict], target_duration_seconds: int) -> List[float]:
    raw_durations = [max(float(item.get("duration", 0.0) or 0.0), _MIN_CLIP_SECONDS) for item in items]
    raw_total = sum(raw_durations)
    target = max(float(target_duration_seconds or 0), _MIN_CLIP_SECONDS)

    if raw_total <= target + 0.35:
        return [round(duration, 3) for duration in raw_durations]

    minimums = [_min_keep_seconds(item) for item in items]
    min_total = sum(minimums)

    if min_total >= target:
        scaled = [minimum * (target / min_total) for minimum in minimums]
        return _rebalance_durations(scaled, target, raw_durations)

    planned = list(minimums)
    capacities = [max(raw - planned_duration, 0.0) for raw, planned_duration in zip(raw_durations, planned)]
    weights = [_clip_priority(item) for item in items]
    remaining = target - min_total

    for _ in range(4):
        if remaining <= 0.001:
            break
        available_indices = [idx for idx, capacity in enumerate(capacities) if capacity > 0.001]
        if not available_indices:
            break
        total_weight = sum(weights[idx] for idx in available_indices) or float(len(available_indices))
        spent = 0.0
        for idx in available_indices:
            share = remaining * ((weights[idx] if total_weight > 0 else 1.0) / total_weight)
            addition = min(share, capacities[idx])
            planned[idx] += addition
            capacities[idx] -= addition
            spent += addition
        if spent <= 0.0001:
            break
        remaining -= spent

    return _rebalance_durations(planned, target, raw_durations)


def _trim_strategy(item: Dict) -> str:
    reasons = set(str(value) for value in (item.get("selection_reason") or []))
    tags = set(str(value) for value in (item.get("tags") or []))

    if "ending_anchor" in reasons:
        return "tail"
    if "opening_anchor" in reasons:
        return "head"
    if {"reveal", "twist"} & tags or any(
        marker in reason for reason in reasons for marker in ("match:reveal", "match:ending")
    ):
        return "tail"
    if any(marker in reason for reason in reasons for marker in ("match:opening", "match:setup")):
        return "head"
    return "center"


def _trim_clip(item: Dict, planned_duration: float) -> Dict:
    clip = dict(item)
    original_start = float(clip.get("start", 0.0) or 0.0)
    original_end = float(clip.get("end", original_start) or original_start)
    original_duration = max(original_end - original_start, _MIN_CLIP_SECONDS)
    target_duration = min(max(float(planned_duration or 0.0), _MIN_CLIP_SECONDS), original_duration)
    strategy = _trim_strategy(clip)

    if original_duration - target_duration <= 0.05:
        start = original_start
        end = original_end
        trim_strategy = "keep_full"
    elif strategy == "head":
        start = original_start
        end = original_start + target_duration
        trim_strategy = "head"
    elif strategy == "tail":
        end = original_end
        start = original_end - target_duration
        trim_strategy = "tail"
    else:
        midpoint = (original_start + original_end) / 2.0
        start = max(original_start, midpoint - target_duration / 2.0)
        end = start + target_duration
        if end > original_end:
            end = original_end
            start = end - target_duration
        trim_strategy = "center"

    clip["original_start"] = round(original_start, 3)
    clip["original_end"] = round(original_end, 3)
    clip["original_duration"] = round(original_duration, 3)
    clip["planned_duration"] = round(target_duration, 3)
    clip["trim_strategy"] = trim_strategy
    clip["timeline_weight"] = _clip_priority(clip)
    clip["start"] = round(start, 3)
    clip["end"] = round(end, 3)
    clip["duration"] = round(max(end - start, _MIN_CLIP_SECONDS), 3)
    return clip


def plan_highlight_timeline(selected_clips: List[Dict], target_duration_seconds: int) -> List[Dict]:
    if not selected_clips:
        return []

    target_duration_seconds = max(int(target_duration_seconds or 0), 30)
    merged = _merge_if_close(selected_clips)
    chosen = _choose_clips(merged, target_duration_seconds)
    planned_durations = _allocate_durations(chosen, target_duration_seconds)
    planned = [_trim_clip(item, duration) for item, duration in zip(chosen, planned_durations)]
    return sorted(planned, key=lambda item: float(item.get("start", 0.0) or 0.0))
