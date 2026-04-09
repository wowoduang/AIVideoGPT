from __future__ import annotations

import re
from typing import Dict, List


_STAGE_KEYWORDS = {
    "opening": ["开始", "开场", "起初", "一开始", "最初"],
    "setup": ["介绍", "铺垫", "表面", "原本", "原来"],
    "conflict": ["冲突", "对抗", "危机", "麻烦", "追杀", "威胁", "矛盾"],
    "turning_point": ["没想到", "突然", "结果", "反而", "这才", "转折", "反转"],
    "reveal": ["真相", "发现", "揭开", "原来", "秘密", "暴露"],
    "climax": ["决战", "爆发", "最关键", "高潮", "彻底", "终于"],
    "ending": ["结局", "最后", "最终", "结尾", "收场"],
}
_PLOT_STAGE_MAP = {
    "铺垫": "setup",
    "节奏缓冲": "setup",
    "信息揭露": "reveal",
    "冲突升级": "conflict",
    "反转": "turning_point",
    "情感爆发": "climax",
    "结局收束": "ending",
}
_STAGE_ORDER = ["opening", "setup", "conflict", "turning_point", "reveal", "climax", "ending"]
_NARRATION_TYPE_PRIORITY = ["inner_state", "relation_change", "emotion_state", "visible_action", "omniscient_summary"]
_NARRATION_TYPE_KEYWORDS = {
    "visible_action": ["走", "跑", "冲", "追", "打", "推开", "拿起", "回头", "转身", "跪", "站起", "开门", "扑", "躲开", "盯着"],
    "emotion_state": ["愤怒", "紧张", "害怕", "崩溃", "失望", "高兴", "痛苦", "绝望", "委屈", "慌了", "激动", "冷静", "愧疚", "压抑"],
    "inner_state": ["心里", "内心", "意识到", "明白", "怀疑", "后悔", "不敢", "以为", "盘算", "决定", "觉得", "知道", "猜到", "终于明白"],
    "relation_change": ["两人", "两个人", "关系", "信任", "背叛", "和解", "联手", "疏远", "对立", "反目", "依赖", "对方", "互相"],
    "omniscient_summary": ["其实", "原来", "直到这时", "从这一刻", "也就是说", "换句话说", "这意味着", "整个", "此时的", "说白了", "本质上"],
}
_NARRATION_TYPE_MATCH_FOCUS = {
    "visible_action": "visible_action",
    "emotion_state": "emotion_reaction",
    "inner_state": "psychological_support",
    "relation_change": "relationship_dynamic",
    "omniscient_summary": "narrative_overview",
}
_NARRATION_TYPE_TEMPLATE = {
    "visible_action": "action_chain",
    "emotion_state": "reaction_focus",
    "inner_state": "inner_reaction",
    "relation_change": "relation_crosscut",
    "omniscient_summary": "narrative_montage",
}
_NON_NAME_FRAGMENTS = {
    "表面", "其实", "心里", "内心", "关系", "这一", "一刻", "彻底", "反转", "开始", "最后", "最终", "突然",
    "明白", "知道", "觉得", "以为", "怀疑", "后悔", "沉默", "眼神", "神情", "态度", "情绪", "看起", "起来",
    "已经", "没有", "因为", "所以", "如果", "但是", "整个", "此时", "本质", "意味", "慌了", "镇定", "所有", "众人", "大家", "盯着", "看向", "逼问", "质问",
}
_COLLECTIVE_CUES = (
    "\u6240\u6709\u4eba",
    "\u5927\u5bb6",
    "\u4f17\u4eba",
    "\u96c6\u4f53",
    "\u4e00\u8d77",
    "\u7eb7\u7eb7",
    "\u90fd\u5f00\u59cb",
)
_PRESSURE_TARGET_CUES = (
    "\u6000\u7591",
    "\u76ef\u7740",
    "\u770b\u5411",
    "\u6307\u5411",
    "\u56f4\u7740",
    "\u56f4\u4f4f",
    "\u903c\u95ee",
    "\u8d28\u95ee",
    "\u77db\u5934",
    "\u538b\u529b",
    "\u9488\u5bf9",
)
_DIRECTIONAL_CUES = (
    "\u770b\u7740",
    "\u76ef\u7740",
    "\u770b\u5411",
    "\u671b\u5411",
    "\u5bf9\u7740",
    "\u51b2\u7740",
    "\u671d\u7740",
    "\u8ffd\u7740",
    "\u903c\u95ee",
    "\u8d28\u95ee",
    "\u6000\u7591",
    "\u63d0\u9632",
    "\u76ef\u4e0a",
    "\u6307\u5411",
    "\u9488\u5bf9",
)


def split_narration_units(text: str, clip_count: int) -> List[Dict]:
    raw = str(text or "").strip()
    if not raw:
        return []

    normalized = raw.replace("\r", "\n")
    has_explicit_breaks = "\n" in normalized
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    sentence_lines = _split_sentences(raw) if not has_explicit_breaks else []
    if not lines or (sentence_lines and len(sentence_lines) > len(lines)):
        lines = sentence_lines
    if not lines:
        return []

    chunks = list(lines) if has_explicit_breaks else _merge_micro_units(lines, clip_count)
    units: List[Dict] = []
    total = len(chunks)
    for idx, line in enumerate(chunks, start=1):
        story_stage = infer_story_stage(line)
        character_names = extract_character_names(line)
        narration_type = classify_narration_type(line, character_names)
        directional_roles = infer_directional_roles(line, character_names, narration_type=narration_type)
        focus_signals = infer_focus_signals(line, character_names, narration_type=narration_type)
        rhythm = infer_rhythm_profile(line, narration_type=narration_type, story_stage=story_stage)
        units.append(
            {
                "unit_id": f"n_{idx:03d}",
                "text": line,
                "target_seconds": _estimate_seconds(line),
                "story_stage": story_stage,
                "narration_type": narration_type,
                "match_focus": infer_match_focus(narration_type),
                "shot_template": infer_shot_template(narration_type),
                "keywords": extract_keywords(line),
                "character_names": character_names,
                "subject_character_names": list(directional_roles["subject_character_names"]),
                "directed_target_names": list(directional_roles["directed_target_names"]),
                "focus_character_names": list(focus_signals["focus_character_names"]),
                "collective_target_names": list(focus_signals["collective_target_names"]),
                "collective_signal": bool(focus_signals["collective_signal"]),
                "rhythm_profile": rhythm["profile"],
                "rhythm_config": rhythm,
                "position_hint": round((idx - 1) / max(total - 1, 1), 3) if total > 1 else 0.5,
            }
        )
    return units


def fit_narration_units_to_target(units: List[Dict], target_duration_seconds: int) -> List[Dict]:
    fitted = [dict(item) for item in (units or [])]
    if not fitted:
        return []

    target_total = max(float(target_duration_seconds or 0.0), 0.0)
    if target_total <= 0.0:
        return fitted

    original_total = sum(max(float(item.get("target_seconds", 0.0) or 0.0), 1.0) for item in fitted)
    if original_total <= 0.0:
        return fitted

    scale = min(max(target_total / original_total, 0.45), 1.85)
    for item in fitted:
        text = str(item.get("text", "") or "")
        floor = 1.4 if len(text) <= 12 else 1.8
        duration = max(float(item.get("target_seconds", 0.0) or 0.0) * scale, floor)
        item["target_seconds"] = round(duration, 2)
        item["duration_scale"] = round(scale, 3)

    adjusted_total = sum(float(item.get("target_seconds", 0.0) or 0.0) for item in fitted)
    delta = round(target_total - adjusted_total, 2)
    if fitted and abs(delta) >= 0.15:
        last = fitted[-1]
        last_floor = 1.4 if len(str(last.get("text", "") or "")) <= 12 else 1.8
        last["target_seconds"] = round(max(float(last.get("target_seconds", 0.0) or 0.0) + delta, last_floor), 2)
    return fitted


def map_narration_units_to_clips(narration_units: List[Dict], selected_clips: List[Dict]) -> List[Dict]:
    if not narration_units or not selected_clips:
        return []

    available = _annotate_clip_positions(selected_clips)
    global_alignment = _align_units_to_clips_globally(narration_units, available)
    mapped: List[Dict] = []
    usage_counts: Dict[str, int] = {}
    last_start = -1.0
    total_units = len(narration_units)

    for idx, unit in enumerate(narration_units, start=1):
        desired_position = _as_float(
            unit.get("position_hint", round((idx - 1) / max(total_units - 1, 1), 3) if total_units > 1 else 0.5),
            0.5,
        )
        best = dict(global_alignment[idx - 1]) if idx - 1 < len(global_alignment) and global_alignment[idx - 1] else None
        best_score = -1.0
        match_strategy = "global_alignment" if best else "semantic"
        if best is not None:
            best_score = _score_unit_clip(
                unit,
                best,
                usage_count=usage_counts.get(_clip_usage_key(best), 0),
                last_start=last_start,
                desired_position=desired_position,
            )

        if best is None or best_score < 0.46:
            semantic_clip, semantic_score = _pick_semantic_best_clip(
                unit,
                available,
                usage_counts,
                last_start,
                desired_position,
            )
            if semantic_clip is not None and semantic_score >= best_score + 0.06:
                best = semantic_clip
                best_score = semantic_score
                match_strategy = "semantic"

        if best is None or best_score < 0.4:
            best = _pick_chronology_fallback(available, usage_counts, desired_position, last_start)
            if best is None:
                continue
            best_score = _score_unit_clip(
                unit,
                best,
                usage_count=usage_counts.get(_clip_usage_key(best), 0),
                last_start=last_start,
                desired_position=desired_position,
            )
            match_strategy = "chronology_fallback"

        clip_id = str(best.get("clip_id", "") or "")
        clip_group = _build_clip_group(best, available, unit, usage_counts, desired_position)
        if not clip_group:
            clip_group = [dict(best)]
        for group_clip in clip_group:
            group_clip_id = str(group_clip.get("clip_id", "") or "")
            if group_clip_id:
                usage_key = _clip_usage_key(group_clip)
                usage_counts[usage_key] = usage_counts.get(usage_key, 0) + 1
        last_start = float(clip_group[-1].get("start", best.get("start", 0.0)) or 0.0)
        mapped.append(
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
                "clip_id": clip_id,
                "match_score": round(best_score, 3),
                "match_strategy": match_strategy,
                "desired_position": round(desired_position, 3),
                "clip": dict(best),
                "clip_group": [dict(item) for item in clip_group],
                "clip_ids": [str(item.get("clip_id", "") or "") for item in clip_group],
                "group_start": round(float(clip_group[0].get("start", 0.0) or 0.0), 3),
                "group_end": round(float(clip_group[-1].get("end", 0.0) or 0.0), 3),
            }
        )
    return mapped


def infer_story_stage(text: str) -> str:
    content = str(text or "").strip()
    if not content:
        return "setup"
    priority = ["ending", "opening", "reveal", "turning_point", "climax", "conflict", "setup"]
    for stage in priority:
        keywords = _STAGE_KEYWORDS.get(stage, [])
        if any(word in content for word in keywords):
            return stage
    return "setup"


def classify_narration_type(text: str, character_names: List[str] | None = None) -> str:
    content = str(text or "").strip()
    if not content:
        return "omniscient_summary"

    names = [name for name in (character_names or []) if _looks_like_character_name(name)]
    scores = {key: 0.0 for key in _NARRATION_TYPE_PRIORITY}
    for narration_type, keywords in _NARRATION_TYPE_KEYWORDS.items():
        scores[narration_type] += sum(0.24 for keyword in keywords if keyword and keyword in content)

    if len(names) >= 2:
        scores["relation_change"] += 0.34
    elif len(names) == 1:
        scores["emotion_state"] += 0.05
        scores["inner_state"] += 0.04

    if any(token in content for token in ["表面", "嘴上", "看起来", "但其实"]):
        scores["inner_state"] += 0.18
        scores["omniscient_summary"] += 0.08
    if any(token in content for token in ["心里", "内心", "意识到", "怀疑", "不敢", "后悔", "盘算", "决定", "觉得", "明白"]):
        scores["inner_state"] += 0.26
    if any(token in content for token in ["互相", "彼此", "站到一起", "站在一起", "对他", "对她", "对方"]):
        scores["relation_change"] += 0.18
    if any(token in content for token in ["沉默", "犹豫", "停顿", "迟疑", "眼神", "神情"]):
        scores["emotion_state"] += 0.12
        scores["inner_state"] += 0.12
    if any(token in content for token in ["其实", "原来", "直到这时", "换句话说", "本质上"]):
        scores["omniscient_summary"] += 0.2
    if len(content) >= 22:
        scores["omniscient_summary"] += 0.08
    if len(content) <= 12 and any(token in content for token in _NARRATION_TYPE_KEYWORDS["visible_action"]):
        scores["visible_action"] += 0.08

    return max(
        _NARRATION_TYPE_PRIORITY,
        key=lambda narration_type: (scores.get(narration_type, 0.0), -_NARRATION_TYPE_PRIORITY.index(narration_type)),
    )


def infer_match_focus(narration_type: str) -> str:
    return _NARRATION_TYPE_MATCH_FOCUS.get(str(narration_type or "").strip(), "narrative_overview")


def infer_shot_template(narration_type: str) -> str:
    return _NARRATION_TYPE_TEMPLATE.get(str(narration_type or "").strip(), "narrative_montage")


def extract_keywords(text: str) -> List[str]:
    content = str(text or "").strip()
    if not content:
        return []
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", content)
    blacklist = {"他们", "自己", "这个", "那个", "因为", "所以", "然后", "就是", "一个", "最后", "已经"}
    seen: List[str] = []
    for token in tokens:
        if token in blacklist:
            continue
        if token not in seen:
            seen.append(token)
    return seen[:8]


def extract_character_names(text: str) -> List[str]:
    content = str(text or "").strip()
    if not content:
        return []
    candidates = re.findall(r"[\u4e00-\u9fff]{2,4}", content)
    blacklist = {
        "他们", "她们", "你们", "我们", "这里", "那里", "因为", "所以", "如果", "但是",
        "最后", "开始", "事情", "时候", "自己", "已经", "一个", "这个", "那个", "主角",
    }
    result: List[str] = []
    for item in candidates:
        normalized = _normalize_character_candidate(item)
        if normalized in blacklist:
            continue
        if not _looks_like_character_name(normalized):
            continue
        if normalized not in result:
            result.append(normalized)
    return result[:5]


def _looks_like_character_name(value: str) -> bool:
    raw = str(value or "").strip()
    if len(raw) < 2 or len(raw) > 4:
        return False
    if any(fragment in raw for fragment in _NON_NAME_FRAGMENTS):
        return False
    if raw[0] in {"他", "她", "它", "这", "那"} and len(raw) > 2:
        return False
    return True


def _normalize_character_candidate(value: str) -> str:
    raw = str(value or "").strip()
    prefixes = ("只有", "就连", "只剩", "还在", "正在", "已经", "一直")
    suffixes = ("还在", "正在", "已经", "一下", "一眼", "看着", "盯着", "望向", "怀疑", "质问", "逼问")
    for prefix in prefixes:
        if raw.startswith(prefix) and 2 <= len(raw) - len(prefix) <= 4:
            raw = raw[len(prefix):]
            break
    for suffix in suffixes:
        if raw.endswith(suffix) and 2 <= len(raw) - len(suffix) <= 4:
            raw = raw[: -len(suffix)]
            break
    return raw


def _contains_collective_signal(text: str) -> bool:
    content = str(text or "").strip()
    return any(cue in content for cue in _COLLECTIVE_CUES) if content else False


def _find_closest_name_before(text: str, names: List[str], boundary: int) -> str:
    best_name = ""
    best_index = -1
    for name in names:
        index = text.rfind(name, 0, max(boundary, 0))
        if index > best_index:
            best_name = name
            best_index = index
    return best_name


def _find_closest_name_after(text: str, names: List[str], start: int) -> str:
    best_name = ""
    best_index = len(text) + 1
    for name in names:
        index = text.find(name, max(start, 0))
        if index >= 0 and index < best_index:
            best_name = name
            best_index = index
    return best_name


def infer_directional_roles(text: str, character_names: List[str] | None = None, narration_type: str = "") -> Dict:
    content = str(text or "").strip()
    names = [name for name in (character_names or []) if _looks_like_character_name(name)]
    if not names:
        return {"subject_character_names": [], "directed_target_names": []}

    narration_type = str(narration_type or classify_narration_type(content, names) or "omniscient_summary")
    subject_names: List[str] = []
    target_names: List[str] = []

    passive_index = content.find("被")
    if passive_index >= 0:
        for cue in _DIRECTIONAL_CUES:
            cue_index = content.find(cue, passive_index + 1)
            if cue_index < 0:
                continue
            subject = _find_closest_name_before(content, names, passive_index)
            target = _find_closest_name_after(content, names, passive_index + 1)
            if subject and target and subject != target:
                subject_names = [subject]
                target_names = [target]
                break

    if not subject_names:
        for cue in _DIRECTIONAL_CUES:
            cue_index = content.find(cue)
            if cue_index < 0:
                continue
            subject = _find_closest_name_before(content, names, cue_index)
            target = _find_closest_name_after(content, names, cue_index + len(cue))
            if subject and target and subject != target:
                subject_names = [subject]
                target_names = [target]
                break

    if not subject_names and narration_type in {"inner_state", "emotion_state", "visible_action"}:
        subject_names = names[:1]
    elif not subject_names and narration_type == "relation_change":
        subject_names = names[:1]
        target_names = names[1:2]
    elif not subject_names:
        subject_names = names[:1]

    return {
        "subject_character_names": list(dict.fromkeys(subject_names)),
        "directed_target_names": list(dict.fromkeys(target_names)),
    }


def infer_focus_signals(text: str, character_names: List[str] | None = None, narration_type: str = "") -> Dict:
    content = str(text or "").strip()
    names = [name for name in (character_names or []) if _looks_like_character_name(name)]
    collective_signal = _contains_collective_signal(content)
    if not names:
        return {
            "focus_character_names": [],
            "collective_target_names": [],
            "collective_signal": collective_signal,
        }

    narration_type = str(narration_type or classify_narration_type(content, names) or "omniscient_summary")
    directional_roles = infer_directional_roles(content, names, narration_type=narration_type)
    subject_names = list(directional_roles["subject_character_names"])
    directed_target_names = list(directional_roles["directed_target_names"])
    pressure_signal = any(cue in content for cue in _PRESSURE_TARGET_CUES)
    explicit_pressure_target = _infer_pressure_target_name(content, names) if pressure_signal else ""

    collective_target_names: List[str] = []
    if len(names) == 1 and (collective_signal or pressure_signal):
        collective_target_names = [names[0]]
    elif len(names) >= 2 and (collective_signal or (len(names) >= 3 and pressure_signal)):
        collective_target_names = [explicit_pressure_target or names[-1]]

    if collective_target_names:
        focus_character_names = list(collective_target_names)
    elif narration_type in {"inner_state", "emotion_state", "visible_action"} and subject_names:
        focus_character_names = list(subject_names)
    elif narration_type == "relation_change" and (subject_names or directed_target_names):
        focus_character_names = list(subject_names) + list(directed_target_names)
    elif narration_type in {"inner_state", "emotion_state", "visible_action"}:
        focus_character_names = names[:1]
    elif narration_type == "relation_change":
        focus_character_names = names if len(names) <= 2 else names[:2]
    else:
        focus_character_names = names if len(names) <= 2 else names[:2]

    return {
        "focus_character_names": list(dict.fromkeys(focus_character_names)),
        "collective_target_names": list(dict.fromkeys(collective_target_names)),
        "collective_signal": collective_signal or bool(collective_target_names),
    }


def _infer_pressure_target_name(text: str, character_names: List[str]) -> str:
    content = str(text or "").strip()
    names = [name for name in (character_names or []) if name]
    if not content or not names:
        return ""

    cue_positions = [content.find(cue) for cue in _PRESSURE_TARGET_CUES if cue in content]
    if not cue_positions:
        return ""
    cue_index = min(cue_positions)

    after_candidates = sorted(
        (content.find(name), name)
        for name in names
        if content.find(name) >= cue_index
    )
    if after_candidates:
        return after_candidates[0][1]

    before_candidates = sorted(
        ((content.find(name), name) for name in names if content.find(name) >= 0),
        reverse=True,
    )
    if before_candidates:
        return before_candidates[0][1]
    return ""


def infer_rhythm_profile(text: str, narration_type: str = "", story_stage: str = "") -> Dict:
    content = str(text or "").strip()
    stage = str(story_stage or infer_story_stage(content) or "setup")
    narration_type = str(narration_type or classify_narration_type(content) or "omniscient_summary")
    length = len(content)

    if narration_type == "inner_state":
        return {
            "profile": "steady" if stage in {"opening", "setup"} else "resolve",
            "preferred_group_size": 2 if length < 18 else 3,
            "max_shot_seconds": 3.8,
            "min_shot_seconds": 1.5,
            "target_flex": 1.2,
        }
    if narration_type == "relation_change":
        return {
            "profile": "pivot" if stage not in {"opening", "setup"} else "balanced",
            "preferred_group_size": 3 if length >= 14 else 2,
            "max_shot_seconds": 3.0,
            "min_shot_seconds": 1.0,
            "target_flex": 1.18,
        }
    if narration_type == "omniscient_summary":
        return {
            "profile": "balanced" if stage not in {"ending"} else "resolve",
            "preferred_group_size": 2 if length < 20 else 3,
            "max_shot_seconds": 3.4,
            "min_shot_seconds": 1.2,
            "target_flex": 1.22,
        }
    if narration_type == "emotion_state":
        return {
            "profile": "pivot" if stage in {"reveal", "turning_point", "ending"} else "balanced",
            "preferred_group_size": 2 if length < 18 else 3,
            "max_shot_seconds": 3.0,
            "min_shot_seconds": 1.1,
            "target_flex": 1.16,
        }
    if stage in {"climax", "conflict"} or length <= 14:
        return {
            "profile": "fast",
            "preferred_group_size": 3 if length >= 10 else 2,
            "max_shot_seconds": 2.2,
            "min_shot_seconds": 0.9,
            "target_flex": 1.1,
        }
    if stage in {"reveal", "turning_point"}:
        return {
            "profile": "pivot",
            "preferred_group_size": 2 if length < 18 else 3,
            "max_shot_seconds": 2.8,
            "min_shot_seconds": 1.1,
            "target_flex": 1.15,
        }
    if stage in {"opening", "setup"}:
        return {
            "profile": "steady",
            "preferred_group_size": 1 if length < 16 else 2,
            "max_shot_seconds": 4.0,
            "min_shot_seconds": 1.6,
            "target_flex": 1.25,
        }
    if stage == "ending":
        return {
            "profile": "resolve",
            "preferred_group_size": 2 if length >= 18 else 1,
            "max_shot_seconds": 3.6,
            "min_shot_seconds": 1.4,
            "target_flex": 1.2,
        }
    return {
        "profile": "balanced",
        "preferred_group_size": 2,
        "max_shot_seconds": 3.0,
        "min_shot_seconds": 1.2,
        "target_flex": 1.15,
    }


def infer_clip_story_stage(clip: Dict) -> str:
    stage = str(clip.get("story_stage_hint", "") or "").strip()
    if stage in _STAGE_ORDER:
        return stage

    plot_function = str(clip.get("plot_function", "") or "").strip()
    if plot_function in _PLOT_STAGE_MAP:
        return _PLOT_STAGE_MAP[plot_function]

    plot_role = str(clip.get("plot_role", "") or "").strip().lower()
    if plot_role == "ending":
        return "ending"
    if plot_role == "twist":
        return "turning_point"
    if plot_role == "conflict":
        return "conflict"
    if plot_role == "setup":
        return "setup"

    tags = set(str(x) for x in (clip.get("tags") or []))
    if "ending" in tags:
        return "ending"
    if "reveal" in tags:
        return "reveal"
    if "emotion_peak" in tags:
        return "climax"
    if "conflict" in tags:
        return "conflict"

    story_position = _as_float(clip.get("story_position", 0.5), 0.5)
    if story_position <= 0.12:
        return "opening"
    if story_position <= 0.3:
        return "setup"
    if story_position <= 0.58:
        return "conflict"
    if story_position <= 0.76:
        return "turning_point"
    if story_position <= 0.9:
        return "climax"
    return "ending"


def _annotate_clip_positions(selected_clips: List[Dict]) -> List[Dict]:
    ordered = sorted((dict(item) for item in (selected_clips or [])), key=lambda x: float(x.get("start", 0.0) or 0.0))
    total = len(ordered)
    annotated: List[Dict] = []
    for idx, clip in enumerate(ordered, start=1):
        if not clip.get("story_index"):
            clip["story_index"] = idx
        if clip.get("story_position") is None:
            clip["story_position"] = round((idx - 1) / max(total - 1, 1), 3) if total > 1 else 0.5
        clip["story_stage_hint"] = infer_clip_story_stage(clip)
        annotated.append(clip)
    return annotated


def _join_text_units(left: str, right: str) -> str:
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left:
        return right
    if not right:
        return left
    if left[-1] in "，,；;。！？!?":
        return f"{left}{right}"
    return f"{left}，{right}"


def _merge_micro_units(chunks: List[str], clip_count: int) -> List[str]:
    target_hint = max(int(clip_count or 0), 0)
    merged: List[str] = []
    buffer = ""
    for chunk in (str(item or "").strip() for item in (chunks or [])):
        if not chunk:
            continue
        if not buffer:
            buffer = chunk
            continue

        buffer_short = len(buffer) <= 8 or _estimate_seconds(buffer) < 2.2
        chunk_short = len(chunk) <= 6 or _estimate_seconds(chunk) < 1.8
        too_many_units = target_hint > 0 and len(merged) + 2 < len(chunks) and len(chunks) > target_hint * 2
        if buffer_short or (chunk_short and too_many_units):
            buffer = _join_text_units(buffer, chunk)
            continue

        merged.append(buffer)
        buffer = chunk

    if buffer:
        merged.append(buffer)

    normalized: List[str] = []
    for item in merged:
        if normalized and (len(item) <= 6 or _estimate_seconds(item) < 1.7):
            normalized[-1] = _join_text_units(normalized[-1], item)
        else:
            normalized.append(item)
    return normalized


def _split_sentences(text: str) -> List[str]:
    buffer = str(text or "")
    for splitter in ["。", "！", "？", ".", "!", "?", "；", ";"]:
        buffer = buffer.replace(splitter, splitter + "\n")
    return [line.strip() for line in buffer.splitlines() if line.strip()]


def _estimate_seconds(text: str) -> float:
    length = len(str(text or "").strip())
    return round(max(length / 4.5, 2.0), 2)


def _as_float(value, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clip_usage_key(clip: Dict) -> str:
    parent_clip_id = str(clip.get("parent_clip_id", "") or "").strip()
    if parent_clip_id:
        return f"parent:{parent_clip_id}"
    source_scene_id = str(clip.get("source_scene_id", "") or "").strip()
    if source_scene_id:
        return f"scene:{source_scene_id}"
    clip_id = str(clip.get("clip_id", "") or "").strip()
    return f"clip:{clip_id}"


def _pick_semantic_best_clip(
    unit: Dict,
    available: List[Dict],
    usage_counts: Dict[str, int],
    last_start: float,
    desired_position: float,
) -> tuple:
    scored = []
    for clip in available:
        score = _score_unit_clip(
            unit,
            clip,
            usage_count=usage_counts.get(_clip_usage_key(clip), 0),
            last_start=last_start,
            desired_position=desired_position,
        )
        scored.append((score, clip))

    scored.sort(
        key=lambda item: (
            -item[0],
            abs(_as_float(item[1].get("story_position", 0.5), 0.5) - desired_position),
            float(item[1].get("start", 0.0) or 0.0),
        )
    )
    if not scored:
        return None, -1.0
    best_score, best = scored[0]
    return dict(best), float(best_score)


def _align_units_to_clips_globally(narration_units: List[Dict], available: List[Dict]) -> List[Dict]:
    if not narration_units or not available:
        return []

    ordered_clips = sorted((dict(item) for item in available), key=lambda x: float(x.get("start", 0.0) or 0.0))
    clip_count = len(ordered_clips)
    unit_count = len(narration_units)
    negative_inf = -10**9

    base_scores: List[List[float]] = []
    for idx, unit in enumerate(narration_units, start=1):
        desired_position = _as_float(
            unit.get("position_hint", round((idx - 1) / max(unit_count - 1, 1), 3) if unit_count > 1 else 0.5),
            0.5,
        )
        row = [
            _score_unit_clip(unit, clip, usage_count=0, last_start=-1.0, desired_position=desired_position)
            for clip in ordered_clips
        ]
        base_scores.append(row)

    dp = [[negative_inf for _ in range(clip_count)] for _ in range(unit_count)]
    backtrack = [[-1 for _ in range(clip_count)] for _ in range(unit_count)]

    for clip_index, clip in enumerate(ordered_clips):
        opening_bonus = 0.05 if str(clip.get("source", "") or "") == "scene" else 0.0
        dp[0][clip_index] = base_scores[0][clip_index] + opening_bonus

    for unit_index in range(1, unit_count):
        unit = narration_units[unit_index]
        prev_unit = narration_units[unit_index - 1]
        for clip_index, clip in enumerate(ordered_clips):
            best_score = negative_inf
            best_prev_index = -1
            for prev_index, prev_clip in enumerate(ordered_clips):
                if dp[unit_index - 1][prev_index] <= negative_inf / 2:
                    continue
                transition = _alignment_transition_score(prev_unit, prev_clip, unit, clip)
                candidate_score = dp[unit_index - 1][prev_index] + base_scores[unit_index][clip_index] + transition
                if candidate_score > best_score:
                    best_score = candidate_score
                    best_prev_index = prev_index
            dp[unit_index][clip_index] = best_score
            backtrack[unit_index][clip_index] = best_prev_index

    final_index = max(range(clip_count), key=lambda idx: dp[-1][idx])
    if dp[-1][final_index] <= negative_inf / 2:
        return []

    alignment: List[Dict] = [dict(ordered_clips[final_index])]
    cursor = final_index
    for unit_index in range(unit_count - 1, 0, -1):
        cursor = backtrack[unit_index][cursor]
        if cursor < 0:
            return []
        alignment.append(dict(ordered_clips[cursor]))
    alignment.reverse()
    return alignment


def _alignment_transition_score(prev_unit: Dict, prev_clip: Dict, unit: Dict, clip: Dict) -> float:
    prev_start = float(prev_clip.get("start", 0.0) or 0.0)
    current_start = float(clip.get("start", 0.0) or 0.0)
    prev_position = _as_float(prev_clip.get("story_position", 0.5), 0.5)
    current_position = _as_float(clip.get("story_position", 0.5), 0.5)
    prev_stage = infer_clip_story_stage(prev_clip)
    current_stage = infer_clip_story_stage(clip)
    prev_unit_stage = str(prev_unit.get("story_stage", "") or "")
    unit_stage = str(unit.get("story_stage", "") or "")

    score = 0.0
    if current_start < prev_start - 3:
        score -= 0.75
    else:
        gap = current_start - prev_start
        if gap <= 18:
            score += 0.18
        elif gap <= 90:
            score += 0.12
        elif gap <= 240:
            score += 0.04
        else:
            score -= 0.08

    if current_position + 0.04 < prev_position:
        score -= 0.3
    else:
        score += max(0.0, 0.14 - abs(current_position - _as_float(unit.get("position_hint", current_position), current_position)) * 0.18)

    if str(prev_clip.get("clip_id", "") or "") == str(clip.get("clip_id", "") or ""):
        score -= 0.22
    elif _clip_usage_key(prev_clip) == _clip_usage_key(clip):
        score -= 0.16

    if prev_stage in _STAGE_ORDER and current_stage in _STAGE_ORDER:
        stage_delta = _STAGE_ORDER.index(current_stage) - _STAGE_ORDER.index(prev_stage)
        if stage_delta >= 0:
            score += 0.08
        elif stage_delta == -1 and current_stage == unit_stage:
            score += 0.02
        else:
            score -= 0.12

    if prev_unit_stage in _STAGE_ORDER and unit_stage in _STAGE_ORDER:
        desired_delta = _STAGE_ORDER.index(unit_stage) - _STAGE_ORDER.index(prev_unit_stage)
        if desired_delta >= 0 and current_position + 0.02 >= prev_position:
            score += 0.05

    return round(score, 3)


def _pick_chronology_fallback(
    available: List[Dict],
    usage_counts: Dict[str, int],
    desired_position: float,
    last_start: float,
) -> Dict | None:
    ranked = []
    for clip in available:
        usage = usage_counts.get(_clip_usage_key(clip), 0)
        story_position = _as_float(clip.get("story_position", 0.5), 0.5)
        start = float(clip.get("start", 0.0) or 0.0)
        position_gap = abs(story_position - desired_position)
        chronology_penalty = 0.0
        if last_start >= 0 and start < last_start - 12:
            chronology_penalty = 0.35
        ranked.append(
            (
                -(1.0 - min(position_gap, 1.0) + float(clip.get("total_score", 0.0) or 0.0) * 0.35 - usage * 0.12 - chronology_penalty),
                usage,
                position_gap,
                start,
                clip,
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    if not ranked:
        return None
    return dict(ranked[0][4])


def _clip_haystack(clip: Dict) -> str:
    return " ".join(
        [
            str(clip.get("subtitle_text", "") or ""),
            str(clip.get("scene_summary", "") or ""),
            str(clip.get("plot_function", "") or ""),
            str(clip.get("plot_role", "") or ""),
            " ".join(str(x) for x in (clip.get("tags") or [])),
        ]
    )


def _type_markers_for_unit(unit: Dict, narration_type: str) -> List[str]:
    content = str(unit.get("text", "") or "")
    markers = [keyword for keyword in _NARRATION_TYPE_KEYWORDS.get(narration_type, []) if keyword and keyword in content]
    if markers:
        return markers
    return list(_NARRATION_TYPE_KEYWORDS.get(narration_type, []))


def _marker_overlap_score(markers: List[str], haystack: str) -> float:
    valid_markers = [marker for marker in (markers or []) if str(marker or "").strip()]
    if not valid_markers:
        return 0.0
    matched = sum(1 for marker in valid_markers if marker in haystack)
    return min(matched / max(len(valid_markers), 1), 1.0)


def _explicit_clip_score(clip: Dict, key: str):
    try:
        value = clip.get(key)
        if value in (None, ""):
            return None
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return None


def _explicit_int_value(clip: Dict, key: str, default: int = 0) -> int:
    try:
        value = clip.get(key)
        if value in (None, ""):
            return default
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return default


def _cap_type_support(score: float, limit: float = 1.12) -> float:
    return min(round(score, 3), limit)


def _role_bonus(clip: Dict, expected_roles: set[str]) -> float:
    role = str(clip.get("shot_role", "") or "")
    if role in expected_roles:
        return 0.08
    if role == "mixed":
        return 0.03
    return 0.0


def _clip_name_set(clip: Dict, field: str) -> set[str]:
    return {str(name or "").strip() for name in (clip.get(field) or []) if str(name or "").strip()}


def _unit_name_set(unit: Dict, field: str) -> set[str]:
    return {str(name or "").strip() for name in (unit.get(field) or []) if str(name or "").strip()}


def _unit_subject_name_set(unit: Dict) -> set[str]:
    return _unit_name_set(unit, "subject_character_names")


def _unit_directed_target_name_set(unit: Dict) -> set[str]:
    return _unit_name_set(unit, "directed_target_names")


def _unit_focus_name_set(unit: Dict) -> set[str]:
    focus_names = _unit_name_set(unit, "focus_character_names")
    if focus_names:
        return focus_names
    return _unit_name_set(unit, "character_names")


def _clip_exchange_pairs(clip: Dict) -> List[tuple[str, str]]:
    pairs: List[tuple[str, str]] = []
    for item in (clip.get("exchange_pairs") or []):
        raw = str(item or "").strip()
        if "->" not in raw:
            continue
        left, right = (part.strip() for part in raw.split("->", 1))
        if left and right and left != right:
            pairs.append((left, right))
    return pairs


def _clip_speaker_sequence(clip: Dict) -> List[str]:
    return [str(item or "").strip() for item in (clip.get("speaker_sequence") or []) if str(item or "").strip()]


def _name_overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return min(len(left & right) / max(len(left), 1), 1.0)


def _collective_target_bonus(unit: Dict, clip: Dict) -> float:
    if not bool(unit.get("collective_signal")):
        return 0.0
    focus_names = _unit_name_set(unit, "collective_target_names") or _unit_focus_name_set(unit)
    if not focus_names:
        return 0.0
    pressure_targets = _clip_name_set(clip, "pressure_target_names")
    interaction_targets = _clip_name_set(clip, "interaction_target_names")
    pressure_sources = _clip_name_set(clip, "pressure_source_names")
    bonus = _name_overlap_ratio(focus_names, pressure_targets) * 0.16
    bonus += _name_overlap_ratio(focus_names, interaction_targets) * 0.08
    if pressure_targets and len(pressure_sources) >= 2 and (focus_names & pressure_targets):
        bonus += 0.05
    return round(min(bonus, 0.22), 3)


def _directional_role_bonus(unit: Dict, clip: Dict, *, mode: str) -> float:
    subject_names = _unit_subject_name_set(unit)
    target_names = _unit_directed_target_name_set(unit)
    clip_characters = _clip_name_set(clip, "character_names")
    clip_speakers = _clip_name_set(clip, "speaker_names")
    clip_targets = _clip_name_set(clip, "interaction_target_names")
    pressure_sources = _clip_name_set(clip, "pressure_source_names")
    pressure_targets = _clip_name_set(clip, "pressure_target_names")
    exchange_pairs = set(_clip_exchange_pairs(clip))

    if mode == "subject":
        if not subject_names:
            return 0.0
        bonus = _name_overlap_ratio(subject_names, clip_characters) * 0.12
        bonus += _name_overlap_ratio(subject_names, clip_speakers) * 0.06
        bonus += _name_overlap_ratio(subject_names, pressure_targets) * 0.05
        return round(min(bonus, 0.18), 3)

    if mode == "target":
        if not target_names:
            return 0.0
        bonus = _name_overlap_ratio(target_names, clip_targets) * 0.12
        bonus += _name_overlap_ratio(target_names, pressure_targets | pressure_sources) * 0.08
        bonus += _name_overlap_ratio(target_names, clip_characters) * 0.03
        return round(min(bonus, 0.18), 3)

    if not subject_names or not target_names:
        return 0.0
    bonus = 0.0
    if any(left in subject_names and right in target_names for left, right in exchange_pairs):
        bonus += 0.16
    elif any(left in target_names and right in subject_names for left, right in exchange_pairs):
        bonus += 0.08
    if (subject_names & clip_characters) and (target_names & clip_targets):
        bonus += 0.1
    if (subject_names & pressure_sources) and (target_names & pressure_targets):
        bonus += 0.1
    return round(min(bonus, 0.22), 3)


def _speaker_alignment_bonus(unit: Dict, clip: Dict, *, mode: str) -> float:
    unit_names = _unit_name_set(unit, "character_names")
    if not unit_names:
        return 0.0
    focus_names = _unit_focus_name_set(unit)
    collective_targets = _unit_name_set(unit, "collective_target_names")
    subject_names = _unit_subject_name_set(unit)
    directed_targets = _unit_directed_target_name_set(unit)
    target_focus = collective_targets or focus_names or unit_names

    speaker_names = _clip_name_set(clip, "speaker_names")
    target_names = _clip_name_set(clip, "interaction_target_names")
    pressure_sources = _clip_name_set(clip, "pressure_source_names")
    pressure_targets = _clip_name_set(clip, "pressure_target_names")
    character_names = _clip_name_set(clip, "character_names")
    exchange_pairs = _clip_exchange_pairs(clip)
    exchange_participants = {name for pair in exchange_pairs for name in pair}
    speaker_sequence = _clip_speaker_sequence(clip)

    if mode == "target":
        bonus = _name_overlap_ratio(target_focus, target_names) * 0.12
        bonus += _name_overlap_ratio(target_focus, pressure_targets) * 0.1
        bonus += _name_overlap_ratio(target_focus, character_names - speaker_names) * 0.06
        bonus += _name_overlap_ratio(unit_names, speaker_names) * 0.03
        if any(right in target_focus for _, right in exchange_pairs):
            bonus += 0.04
        if pressure_targets and pressure_sources and (target_focus & pressure_targets):
            bonus += 0.04
        return round(min(bonus, 0.24), 3)

    if mode == "dialogue":
        dialogue_names = speaker_names | target_names | pressure_sources | pressure_targets | character_names | exchange_participants
        bonus = _name_overlap_ratio(unit_names, dialogue_names) * 0.12
        if len(unit_names) >= 2 and len(dialogue_names) >= 2 and len(unit_names & dialogue_names) >= 2:
            bonus += 0.06
        if speaker_names and target_names:
            bonus += 0.03
        if pressure_sources and pressure_targets and (focus_names & pressure_sources) and (target_focus & pressure_targets):
            bonus += 0.06
        elif pressure_targets and len(pressure_sources) >= 2 and (target_focus & pressure_targets):
            bonus += 0.04
        if any(left in unit_names and right in unit_names for left, right in exchange_pairs):
            bonus += 0.05
        if len(unit_names & set(speaker_sequence)) >= 2:
            bonus += 0.03
        if subject_names and directed_targets:
            if any(left in subject_names and right in directed_targets for left, right in exchange_pairs):
                bonus += 0.06
            elif any(left in directed_targets and right in subject_names for left, right in exchange_pairs):
                bonus += 0.01
            if (subject_names & speaker_names) and (directed_targets & target_names):
                bonus += 0.04
        return round(min(bonus, 0.26), 3)

    bonus = max(
        _name_overlap_ratio(focus_names or unit_names, speaker_names),
        _name_overlap_ratio(target_focus, target_names),
        _name_overlap_ratio(target_focus, pressure_targets | pressure_sources),
        _name_overlap_ratio(unit_names, character_names | exchange_participants),
    ) * 0.1
    if target_focus & pressure_targets:
        bonus += 0.03
    return round(min(bonus, 0.16), 3)


def _score_weights_for_narration_type(narration_type: str) -> Dict[str, float]:
    mapping = {
        "visible_action": {
            "stage": 0.12,
            "plot": 0.07,
            "text": 0.14,
            "keyword": 0.15,
            "character": 0.08,
            "duration": 0.08,
            "emotion": 0.05,
            "position": 0.08,
            "chronology": 0.09,
            "type_support": 0.14,
            "raw_audio_bonus": 0.06,
        },
        "emotion_state": {
            "stage": 0.12,
            "plot": 0.06,
            "text": 0.09,
            "keyword": 0.08,
            "character": 0.08,
            "duration": 0.07,
            "emotion": 0.12,
            "position": 0.09,
            "chronology": 0.08,
            "type_support": 0.16,
            "raw_audio_bonus": 0.05,
        },
        "inner_state": {
            "stage": 0.11,
            "plot": 0.05,
            "text": 0.07,
            "keyword": 0.07,
            "character": 0.08,
            "duration": 0.08,
            "emotion": 0.10,
            "position": 0.10,
            "chronology": 0.09,
            "type_support": 0.20,
            "raw_audio_bonus": 0.07,
        },
        "relation_change": {
            "stage": 0.11,
            "plot": 0.06,
            "text": 0.08,
            "keyword": 0.08,
            "character": 0.15,
            "duration": 0.07,
            "emotion": 0.07,
            "position": 0.08,
            "chronology": 0.08,
            "type_support": 0.17,
            "raw_audio_bonus": 0.04,
        },
        "omniscient_summary": {
            "stage": 0.16,
            "plot": 0.10,
            "text": 0.06,
            "keyword": 0.06,
            "character": 0.06,
            "duration": 0.07,
            "emotion": 0.05,
            "position": 0.13,
            "chronology": 0.10,
            "type_support": 0.16,
            "raw_audio_bonus": 0.03,
        },
    }
    return dict(mapping.get(narration_type, mapping["omniscient_summary"]))


def _audio_alignment_bonus(unit: Dict, clip: Dict) -> float:
    narration_type = str(unit.get("narration_type", "") or "omniscient_summary")
    audio_signal = float(clip.get("audio_signal_score", 0.0) or 0.0)
    audio_peak = float(clip.get("audio_peak_score", 0.0) or 0.0)
    audio_dynamic = float(clip.get("audio_dynamic_score", 0.0) or 0.0)
    audio_onset = float(clip.get("audio_onset_score", 0.0) or 0.0)
    if max(audio_signal, audio_peak, audio_dynamic, audio_onset) <= 0.0:
        return 0.0

    if narration_type == "visible_action":
        bonus = audio_signal * 0.06 + audio_peak * 0.04 + audio_onset * 0.03
    elif narration_type == "emotion_state":
        bonus = audio_dynamic * 0.05 + audio_signal * 0.025 + audio_peak * 0.015
    elif narration_type == "inner_state":
        bonus = audio_dynamic * 0.03 + audio_signal * 0.012
    elif narration_type == "relation_change":
        bonus = audio_dynamic * 0.028 + audio_signal * 0.018 + audio_peak * 0.01
    else:
        bonus = audio_signal * 0.02 + audio_dynamic * 0.015
    return round(min(max(bonus, 0.0), 0.1), 3)


def _setup_mismatch_penalty(unit: Dict, clip: Dict, desired_position: float) -> float:
    unit_stage = str(unit.get("story_stage", "") or "").strip().lower()
    clip_stage = infer_clip_story_stage(clip)
    clip_position = float(clip.get("story_position", 0.5) or 0.5)
    intro_risk = float(clip.get("intro_risk_score", 0.0) or 0.0)

    if unit_stage in {"opening", "setup"}:
        return 0.0
    if clip_stage not in {"opening", "setup"} and intro_risk <= 0.0:
        return 0.0

    penalty = 0.0
    if clip_stage in {"opening", "setup"}:
        penalty += 0.05
    if clip_position <= 0.18 and desired_position >= 0.3:
        penalty += 0.06
    if intro_risk > 0.0:
        penalty += min(intro_risk * 0.12, 0.12)
    return round(min(penalty, 0.18), 3)


def _visible_action_support_score(unit: Dict, clip: Dict) -> float:
    explicit = _explicit_clip_score(clip, "visible_action_score")
    if explicit is not None:
        score = round(explicit, 3)
    else:
        duration = float(clip.get("duration", 0.0) or 0.0)
        haystack = _clip_haystack(clip)
        score = 0.26
        if str(clip.get("source", "") or "") == "scene":
            score += 0.12
        if clip.get("raw_audio_worthy"):
            score += 0.08
        if 1.4 <= duration <= 6.5:
            score += 0.12
        if {"conflict", "emotion_peak"} & set(str(x) for x in (clip.get("tags") or [])):
            score += 0.06
        score += _marker_overlap_score(_type_markers_for_unit(unit, "visible_action"), haystack) * 0.36
    if str(clip.get("shot_role", "") or "") == "action_follow":
        score += 0.08
    elif str(clip.get("shot_role", "") or "") == "dialogue_exchange":
        score -= 0.04
    score += _directional_role_bonus(unit, clip, mode="subject") * 0.45
    score += _directional_role_bonus(unit, clip, mode="pair") * 0.35
    return _cap_type_support(score)


def _emotion_state_support_score(unit: Dict, clip: Dict) -> float:
    explicit = _explicit_clip_score(clip, "reaction_score")
    if explicit is not None:
        score = round(explicit, 3)
    else:
        duration = float(clip.get("duration", 0.0) or 0.0)
        haystack = _clip_haystack(clip)
        emotion_score = min(float(clip.get("emotion_score", 0.0) or 0.0), 1.0)
        score = 0.18 + emotion_score * 0.42
        if str(clip.get("source", "") or "") == "scene":
            score += 0.08
        if clip.get("raw_audio_worthy"):
            score += 0.06
        if 1.2 <= duration <= 4.8:
            score += 0.08
        score += _marker_overlap_score(_type_markers_for_unit(unit, "emotion_state"), haystack) * 0.24
    score += (_explicit_clip_score(clip, "solo_focus_score") or 0.0) * 0.12
    score += (_explicit_clip_score(clip, "dialogue_exchange_score") or 0.0) * 0.04
    score += _role_bonus(clip, {"single_focus", "dialogue_exchange"})
    score += _speaker_alignment_bonus(unit, clip, mode="general")
    score += _directional_role_bonus(unit, clip, mode="subject") * 0.45
    score += _collective_target_bonus(unit, clip) * 0.35
    return _cap_type_support(score)


def _inner_state_support_score(unit: Dict, clip: Dict) -> float:
    explicit = _explicit_clip_score(clip, "inner_state_support")
    if explicit is not None:
        score = round(explicit, 3)
    else:
        duration = float(clip.get("duration", 0.0) or 0.0)
        haystack = _clip_haystack(clip)
        stage = infer_clip_story_stage(clip)
        clip_character_names = [str(name or "").strip() for name in (clip.get("character_names") or []) if str(name or "").strip()]
        score = 0.18 + min(float(clip.get("emotion_score", 0.0) or 0.0), 1.0) * 0.26
        if str(clip.get("source", "") or "") == "scene":
            score += 0.12
        if clip.get("raw_audio_worthy"):
            score += 0.10
        if 1.5 <= duration <= 5.2:
            score += 0.10
        if len(clip_character_names) <= 1:
            score += 0.08
        if stage in {"turning_point", "reveal", "climax", "ending"}:
            score += 0.08
        score += _marker_overlap_score(_type_markers_for_unit(unit, "inner_state"), haystack) * 0.24
    score += (_explicit_clip_score(clip, "solo_focus_score") or 0.0) * 0.18
    if _explicit_int_value(clip, "speaker_turns", 0) <= 1:
        score += 0.05
    unit_names = _unit_focus_name_set(unit) or _unit_name_set(unit, "character_names")
    subject_names = _unit_subject_name_set(unit)
    directed_targets = _unit_directed_target_name_set(unit)
    pressure_targets = _clip_name_set(clip, "pressure_target_names")
    pressure_sources = _clip_name_set(clip, "pressure_source_names")
    clip_characters = _clip_name_set(clip, "character_names")
    clip_targets = _clip_name_set(clip, "interaction_target_names")
    if pressure_targets:
        score += _name_overlap_ratio(unit_names, pressure_targets) * 0.12
        if len(pressure_sources) >= 2 and (unit_names & pressure_targets):
            score += 0.05
    if subject_names:
        if subject_names & clip_characters:
            score += 0.08
        else:
            score -= 0.06
    if directed_targets and (directed_targets & clip_targets):
        score += 0.04
    score += _role_bonus(clip, {"single_focus"})
    if str(clip.get("shot_role", "") or "") == "dialogue_exchange":
        score -= 0.03
    alignment_mode = "general" if _unit_subject_name_set(unit) else "target"
    score += _speaker_alignment_bonus(unit, clip, mode=alignment_mode)
    score += _directional_role_bonus(unit, clip, mode="subject") * 0.55
    score += _directional_role_bonus(unit, clip, mode="target") * 0.18
    score += _collective_target_bonus(unit, clip) * 0.45
    return _cap_type_support(score)


def _relation_change_support_score(unit: Dict, clip: Dict) -> float:
    explicit = _explicit_clip_score(clip, "relation_score")
    if explicit is not None:
        score = round(explicit, 3)
    else:
        haystack = _clip_haystack(clip)
        clip_names = {str(name or "").strip() for name in (clip.get("character_names") or []) if str(name or "").strip()}
        unit_names = {str(name or "").strip() for name in (unit.get("character_names") or []) if str(name or "").strip()}
        score = 0.2
        if len(clip_names) >= 2:
            score += 0.18
        elif len(clip_names) == 1:
            score += 0.08
        if str(clip.get("source", "") or "") == "scene":
            score += 0.1
        if infer_clip_story_stage(clip) in {"conflict", "turning_point", "reveal", "ending"}:
            score += 0.08
        if unit_names and clip_names:
            overlap = unit_names & clip_names
            if overlap:
                score += min(len(overlap) / max(len(unit_names), 1), 1.0) * 0.18
        score += _marker_overlap_score(_type_markers_for_unit(unit, "relation_change"), haystack) * 0.22
    dialogue_exchange = _explicit_clip_score(clip, "dialogue_exchange_score") or 0.0
    ensemble_scene = _explicit_clip_score(clip, "ensemble_scene_score") or 0.0
    group_reaction = _explicit_clip_score(clip, "group_reaction_score") or 0.0
    exchange_pairs = _clip_exchange_pairs(clip)
    exchange_participants = {name for pair in exchange_pairs for name in pair}
    pressure_sources = _clip_name_set(clip, "pressure_source_names")
    pressure_targets = _clip_name_set(clip, "pressure_target_names")
    unit_names = _unit_name_set(unit, "character_names")
    focus_names = _unit_focus_name_set(unit)
    subject_names = _unit_subject_name_set(unit)
    directed_targets = _unit_directed_target_name_set(unit)
    clip_targets = _clip_name_set(clip, "interaction_target_names")
    score += max(dialogue_exchange, ensemble_scene) * 0.18
    score += min(dialogue_exchange, ensemble_scene) * 0.05
    score += group_reaction * 0.08
    if _explicit_int_value(clip, "speaker_turns", 0) >= 2:
        score += 0.06
    if len(exchange_pairs) >= 2:
        score += 0.08
    elif len(exchange_pairs) == 1:
        score += 0.04
    if len(exchange_participants) >= 3:
        score += 0.06
    if len(pressure_targets) == 1 and len(pressure_sources) >= 2:
        score += 0.1
    if unit_names and pressure_targets and (unit_names & pressure_targets):
        score += 0.05
    if unit_names and pressure_sources and (unit_names & pressure_sources):
        score += 0.03
    if focus_names and pressure_targets and (focus_names & pressure_targets):
        score += 0.05
    if unit_names and pressure_targets and pressure_sources and (unit_names & pressure_targets) and (unit_names & pressure_sources):
        score += 0.05
    if subject_names and directed_targets:
        if any(left in subject_names and right in directed_targets for left, right in exchange_pairs):
            score += 0.1
        elif any(left in directed_targets and right in subject_names for left, right in exchange_pairs):
            score -= 0.08
        if directed_targets & clip_targets:
            score += 0.04
        elif subject_names & clip_targets:
            score -= 0.04
    score += _role_bonus(clip, {"dialogue_exchange", "ensemble_relation"})
    if str(clip.get("shot_role", "") or "") == "single_focus":
        score -= 0.02
    score += _speaker_alignment_bonus(unit, clip, mode="dialogue")
    score += _directional_role_bonus(unit, clip, mode="pair") * 0.55
    score += _directional_role_bonus(unit, clip, mode="subject") * 0.16
    score += _directional_role_bonus(unit, clip, mode="target") * 0.16
    score += _collective_target_bonus(unit, clip) * 0.55
    return _cap_type_support(score)


def _omniscient_summary_support_score(
    unit: Dict,
    clip: Dict,
    *,
    stage_score: float,
    plot_score: float,
    position_score: float,
) -> float:
    explicit = _explicit_clip_score(clip, "narrative_overview_score")
    if explicit is not None:
        score = round(explicit, 3)
    else:
        duration = float(clip.get("duration", 0.0) or 0.0)
        score = 0.18 + stage_score * 0.22 + plot_score * 0.18 + position_score * 0.18
        if str(clip.get("source", "") or "") in {"scene", "hybrid"}:
            score += 0.08
        if 2.0 <= duration <= 8.0:
            score += 0.1
        if clip.get("raw_audio_worthy"):
            score += 0.04
    group_reaction = _explicit_clip_score(clip, "group_reaction_score") or 0.0
    pressure_sources = _clip_name_set(clip, "pressure_source_names")
    pressure_targets = _clip_name_set(clip, "pressure_target_names")
    score += group_reaction * 0.16
    if len(pressure_targets) == 1 and len(pressure_sources) >= 2:
        score += 0.06
    score += (_explicit_clip_score(clip, "ensemble_scene_score") or 0.0) * 0.08
    score += _role_bonus(clip, {"ensemble_relation", "narrative_bridge"})
    score += _collective_target_bonus(unit, clip) * 0.7
    return _cap_type_support(score)


def _narration_type_support_score(
    unit: Dict,
    clip: Dict,
    *,
    stage_score: float,
    plot_score: float,
    position_score: float,
) -> float:
    narration_type = str(unit.get("narration_type", "") or "omniscient_summary")
    if narration_type == "visible_action":
        return _visible_action_support_score(unit, clip)
    if narration_type == "emotion_state":
        return _emotion_state_support_score(unit, clip)
    if narration_type == "inner_state":
        return _inner_state_support_score(unit, clip)
    if narration_type == "relation_change":
        return _relation_change_support_score(unit, clip)
    return _omniscient_summary_support_score(
        unit,
        clip,
        stage_score=stage_score,
        plot_score=plot_score,
        position_score=position_score,
    )


def _directional_match_bonus(unit: Dict, clip: Dict) -> float:
    narration_type = str(unit.get("narration_type", "") or "omniscient_summary")
    if narration_type == "visible_action":
        bonus = _directional_role_bonus(unit, clip, mode="pair") * 0.12
        bonus += _directional_role_bonus(unit, clip, mode="subject") * 0.05
        return round(bonus, 3)
    if narration_type == "emotion_state":
        return round(_directional_role_bonus(unit, clip, mode="subject") * 0.08, 3)
    if narration_type == "inner_state":
        bonus = _directional_role_bonus(unit, clip, mode="subject") * 0.1
        bonus += _directional_role_bonus(unit, clip, mode="target") * 0.03
        return round(bonus, 3)
    if narration_type == "relation_change":
        bonus = _directional_role_bonus(unit, clip, mode="pair") * 0.18
        bonus += _directional_role_bonus(unit, clip, mode="subject") * 0.04
        bonus += _directional_role_bonus(unit, clip, mode="target") * 0.04
        return round(bonus, 3)
    bonus = _collective_target_bonus(unit, clip) * 0.12
    bonus += _directional_role_bonus(unit, clip, mode="target") * 0.03
    return round(bonus, 3)


def _score_unit_clip(
    unit: Dict,
    clip: Dict,
    *,
    usage_count: int,
    last_start: float,
    desired_position: float,
) -> float:
    stage = str(unit.get("story_stage", "") or "")
    narration_type = str(unit.get("narration_type", "") or "omniscient_summary")
    stage_score = _stage_score(stage, clip)
    plot_score = _plot_function_score(stage, clip)
    text_score = _text_match_score(str(unit.get("text", "") or ""), clip)
    keyword_score = _keyword_score(list(unit.get("keywords") or []), clip)
    character_score = _character_score(list(unit.get("character_names") or []), clip)
    duration_score = _duration_score(float(unit.get("target_seconds", 0.0) or 0.0), clip)
    emotion_score = min(float(clip.get("emotion_score", 0.0) or 0.0), 1.0)
    position_score = _position_score(desired_position, clip)
    chronology_score = _chronology_score(last_start, clip)
    type_support = _narration_type_support_score(
        unit,
        clip,
        stage_score=stage_score,
        plot_score=plot_score,
        position_score=position_score,
    )
    directional_bonus = _directional_match_bonus(unit, clip)
    weights = _score_weights_for_narration_type(narration_type)
    raw_audio_bonus = float(weights.get("raw_audio_bonus", 0.04) or 0.04) if clip.get("raw_audio_worthy") else 0.0
    audio_bonus = _audio_alignment_bonus(unit, clip)
    repeat_penalty = min(usage_count * 0.16, 0.38)
    setup_penalty = _setup_mismatch_penalty(unit, clip, desired_position)

    total = (
        stage_score * weights["stage"]
        + plot_score * weights["plot"]
        + text_score * weights["text"]
        + keyword_score * weights["keyword"]
        + character_score * weights["character"]
        + duration_score * weights["duration"]
        + emotion_score * weights["emotion"]
        + position_score * weights["position"]
        + chronology_score * weights["chronology"]
        + type_support * weights["type_support"]
        + directional_bonus
        + raw_audio_bonus
        + audio_bonus
        - repeat_penalty
        - setup_penalty
    )
    return max(round(total, 3), 0.0)


def _stage_score(stage: str, clip: Dict) -> float:
    if not stage:
        return 0.35

    clip_stage = infer_clip_story_stage(clip)
    if clip_stage == stage:
        return 1.0
    if {stage, clip_stage} <= {"reveal", "turning_point"}:
        return 0.84
    if {stage, clip_stage} <= {"conflict", "climax"}:
        return 0.8
    if stage in _STAGE_ORDER and clip_stage in _STAGE_ORDER:
        distance = abs(_STAGE_ORDER.index(stage) - _STAGE_ORDER.index(clip_stage))
        if distance == 1:
            return 0.72
        if distance == 2:
            return 0.5
    return 0.28


def _plot_function_score(stage: str, clip: Dict) -> float:
    plot_function = str(clip.get("plot_function", "") or "").strip()
    plot_role = str(clip.get("plot_role", "") or "").strip().lower()
    summary = str(clip.get("scene_summary", "") or "")
    tags = set(str(x) for x in (clip.get("tags") or []))

    if stage == "turning_point" and (plot_function == "反转" or plot_role == "twist"):
        return 1.0
    if stage == "reveal" and (plot_function == "信息揭露" or "reveal" in tags or "真相" in summary):
        return 1.0
    if stage == "conflict" and (plot_function == "冲突升级" or plot_role == "conflict" or "conflict" in tags):
        return 0.95
    if stage == "climax" and (plot_function == "情感爆发" or "emotion_peak" in tags or "高潮" in summary):
        return 0.95
    if stage == "ending" and (plot_function == "结局收束" or plot_role == "ending" or "ending" in tags):
        return 0.95
    if stage in {"opening", "setup"} and plot_function in {"铺垫", "节奏缓冲"}:
        return 0.9
    return 0.45 if infer_clip_story_stage(clip) == stage else 0.25


def _text_match_score(text: str, clip: Dict) -> float:
    content = str(text or "").strip()
    haystack = " ".join(
        [
            str(clip.get("subtitle_text", "") or ""),
            str(clip.get("scene_summary", "") or ""),
            str(clip.get("plot_function", "") or ""),
            str(clip.get("plot_role", "") or ""),
            " ".join(str(x) for x in (clip.get("tags") or [])),
        ]
    )
    if not content:
        return 0.2
    if not haystack.strip():
        return 0.1

    keywords = extract_keywords(content)
    if not keywords:
        return 0.25

    matched = sum(1 for word in keywords if word and word in haystack)
    coverage = matched / max(len(keywords), 1)
    if len(content) >= 6 and (content[:6] in haystack or content[-6:] in haystack):
        coverage += 0.18
    return min(round(coverage, 3), 1.0)


def _keyword_score(keywords: List[str], clip: Dict) -> float:
    word_set = {str(word or "").strip() for word in (keywords or []) if str(word or "").strip()}
    if not word_set:
        return 0.25
    haystack = " ".join(
        [
            str(clip.get("subtitle_text", "") or ""),
            str(clip.get("scene_summary", "") or ""),
            str(clip.get("plot_function", "") or ""),
            " ".join(str(x) for x in (clip.get("tags") or [])),
        ]
    )
    matched = sum(1 for word in word_set if word in haystack)
    return min(matched / max(len(word_set), 1), 1.0)


def _character_score(character_names: List[str], clip: Dict) -> float:
    character_set = {str(name or "").strip() for name in (character_names or []) if str(name or "").strip()}
    if not character_set:
        return 0.25
    clip_names = {str(x or "").strip() for x in (clip.get("character_names") or []) if str(x or "").strip()}
    if not clip_names:
        return 0.12
    overlap = character_set & clip_names
    if overlap:
        return min(len(overlap) / max(len(character_set), 1), 1.0)
    return 0.0


def _duration_score(target_seconds: float, clip: Dict) -> float:
    clip_duration = float(clip.get("duration", 0.0) or 0.0)
    if target_seconds <= 0.0 or clip_duration <= 0.0:
        return 0.3
    diff = abs(clip_duration - target_seconds)
    if diff <= 1.5:
        return 1.0
    if diff <= 3.0:
        return 0.75
    if diff <= 6.0:
        return 0.5
    return 0.2


def _clip_overlap_ratio(left: Dict, right: Dict) -> float:
    left_start = float(left.get("start", 0.0) or 0.0)
    left_end = float(left.get("end", left_start) or left_start)
    right_start = float(right.get("start", 0.0) or 0.0)
    right_end = float(right.get("end", right_start) or right_start)
    overlap = max(0.0, min(left_end, right_end) - max(left_start, right_start))
    min_duration = max(min(max(left_end - left_start, 0.001), max(right_end - right_start, 0.001)), 0.001)
    return overlap / min_duration


def _position_score(desired_position: float, clip: Dict) -> float:
    actual = _as_float(clip.get("story_position", 0.5), 0.5)
    diff = abs(actual - desired_position)
    if diff <= 0.08:
        return 1.0
    if diff <= 0.18:
        return 0.78
    if diff <= 0.3:
        return 0.56
    return 0.25


def _chronology_score(last_start: float, clip: Dict) -> float:
    current_start = float(clip.get("start", 0.0) or 0.0)
    if last_start < 0:
        return 0.6
    if current_start >= last_start - 3:
        gap = current_start - last_start
        if gap <= 30:
            return 1.0
        if gap <= 120:
            return 0.75
        return 0.45
    back_gap = last_start - current_start
    if back_gap <= 10:
        return 0.35
    return 0.0


def _build_clip_group(
    best_clip: Dict,
    available: List[Dict],
    unit: Dict,
    usage_counts: Dict[str, int],
    desired_position: float,
) -> List[Dict]:
    ordered = sorted((dict(item) for item in available), key=lambda x: float(x.get("start", 0.0) or 0.0))
    best_id = str(best_clip.get("clip_id", "") or "")
    best_index = next((idx for idx, item in enumerate(ordered) if str(item.get("clip_id", "") or "") == best_id), -1)
    if best_index < 0:
        return [dict(best_clip)]

    target_seconds = float(unit.get("target_seconds", 0.0) or 0.0)
    rhythm = dict(unit.get("rhythm_config") or {})
    template_config = _shot_template_group_config(unit, rhythm)
    group = [dict(ordered[best_index])]
    total_duration = float(group[0].get("duration", 0.0) or 0.0)
    max_group_size = max(int(template_config.get("max_group_size", rhythm.get("preferred_group_size", 2)) or 2), 1)

    neighbors: List[Dict] = []
    for offset in template_config.get("offsets") or _neighbor_offsets(str(rhythm.get("profile", "balanced") or "balanced")):
        neighbor_index = best_index + offset
        if 0 <= neighbor_index < len(ordered):
            neighbors.append(dict(ordered[neighbor_index]))

    scored_neighbors = []
    for item in neighbors:
        clip_id = str(item.get("clip_id", "") or "")
        if clip_id == best_id:
            continue
        if _clip_overlap_ratio(best_clip, item) >= 0.68:
            continue
        score = _score_unit_clip(
            unit,
            item,
            usage_count=usage_counts.get(_clip_usage_key(item), 0),
            last_start=float(best_clip.get("start", 0.0) or 0.0),
            desired_position=desired_position,
        )
        score += _template_neighbor_bonus(
            template=str(template_config.get("template", "narrative_montage") or "narrative_montage"),
            unit=unit,
            anchor_clip=best_clip,
            candidate_clip=item,
        )
        proximity = abs(float(item.get("start", 0.0) or 0.0) - float(best_clip.get("start", 0.0) or 0.0))
        scored_neighbors.append((score, usage_counts.get(_clip_usage_key(item), 0), proximity, item))

    scored_neighbors.sort(key=lambda x: (-x[0], x[1], x[2]))
    for score, _, _, item in scored_neighbors:
        if len(group) >= max_group_size:
            break
        duration = float(item.get("duration", 0.0) or 0.0)
        target_flex = float(template_config.get("target_flex", rhythm.get("target_flex", 1.15)) or 1.15)
        if target_seconds > 0 and total_duration >= target_seconds * target_flex:
            break
        if score < float(template_config.get("min_neighbor_score", 0.4) or 0.4):
            continue
        group.append(dict(item))
        total_duration += duration

    group.sort(key=lambda x: float(x.get("start", 0.0) or 0.0))
    return group


def _shot_template_group_config(unit: Dict, rhythm: Dict) -> Dict:
    template = str(unit.get("shot_template", "") or "narrative_montage")
    profile = str(rhythm.get("profile", "balanced") or "balanced")
    preferred_group_size = max(int(rhythm.get("preferred_group_size", 2) or 2), 1)
    relation_span = len({str(name or "").strip() for name in (unit.get("character_names") or []) if str(name or "").strip()})

    configs = {
        "action_chain": {
            "template": template,
            "offsets": [1, 2, -1, 3],
            "max_group_size": max(preferred_group_size, 2),
            "min_neighbor_score": 0.42,
            "target_flex": 1.12,
        },
        "reaction_focus": {
            "template": template,
            "offsets": [-1, 1, 2],
            "max_group_size": max(min(preferred_group_size, 2), 2),
            "min_neighbor_score": 0.37,
            "target_flex": 1.12,
        },
        "inner_reaction": {
            "template": template,
            "offsets": [1, -1, 2],
            "max_group_size": max(min(preferred_group_size, 3), 2),
            "min_neighbor_score": 0.34,
            "target_flex": 1.18,
        },
        "relation_crosscut": {
            "template": template,
            "offsets": [-1, 1, 2, -2, 3],
            "max_group_size": max(min(preferred_group_size + (1 if relation_span >= 3 else 0) + 1, 4), 2),
            "min_neighbor_score": 0.35,
            "target_flex": 1.18,
        },
        "narrative_montage": {
            "template": template,
            "offsets": [1, 2, -1, 3],
            "max_group_size": max(preferred_group_size, 2),
            "min_neighbor_score": 0.31,
            "target_flex": 1.24 if profile != "fast" else 1.16,
        },
    }
    return dict(configs.get(template, configs["narrative_montage"]))


def _template_neighbor_bonus(template: str, unit: Dict, anchor_clip: Dict, candidate_clip: Dict) -> float:
    anchor_scene_id = str(anchor_clip.get("source_scene_id", "") or "")
    candidate_scene_id = str(candidate_clip.get("source_scene_id", "") or "")
    anchor_start = float(anchor_clip.get("start", 0.0) or 0.0)
    candidate_start = float(candidate_clip.get("start", 0.0) or 0.0)
    candidate_duration = float(candidate_clip.get("duration", 0.0) or 0.0)
    candidate_role = str(candidate_clip.get("shot_role", "") or "")
    anchor_names = {str(name or "").strip() for name in (anchor_clip.get("character_names") or []) if str(name or "").strip()}
    candidate_names = {str(name or "").strip() for name in (candidate_clip.get("character_names") or []) if str(name or "").strip()}
    anchor_speakers = _clip_name_set(anchor_clip, "speaker_names")
    candidate_speakers = _clip_name_set(candidate_clip, "speaker_names")
    anchor_targets = _clip_name_set(anchor_clip, "interaction_target_names")
    candidate_targets = _clip_name_set(candidate_clip, "interaction_target_names")
    anchor_pressure_sources = _clip_name_set(anchor_clip, "pressure_source_names")
    candidate_pressure_sources = _clip_name_set(candidate_clip, "pressure_source_names")
    anchor_pressure_targets = _clip_name_set(anchor_clip, "pressure_target_names")
    candidate_pressure_targets = _clip_name_set(candidate_clip, "pressure_target_names")
    anchor_pairs = set(_clip_exchange_pairs(anchor_clip))
    candidate_pairs = set(_clip_exchange_pairs(candidate_clip))

    bonus = 0.0
    if template == "action_chain":
        action_evidence = _explicit_clip_score(candidate_clip, "visible_action_score") or 0.0
        bonus += action_evidence * 0.12
        if candidate_start >= anchor_start:
            bonus += 0.08
        if candidate_clip.get("raw_audio_worthy"):
            bonus += 0.04
        if candidate_scene_id and candidate_scene_id == anchor_scene_id:
            bonus += 0.04
        if str(candidate_clip.get("primary_evidence", "") or "") == "visible_action_score":
            bonus += 0.04
        if candidate_role == "action_follow":
            bonus += 0.06
    elif template == "reaction_focus":
        reaction_evidence = _explicit_clip_score(candidate_clip, "reaction_score") or 0.0
        bonus += reaction_evidence * 0.12
        if candidate_scene_id and candidate_scene_id == anchor_scene_id:
            bonus += 0.12
        if candidate_clip.get("raw_audio_worthy"):
            bonus += 0.04
        if 1.2 <= candidate_duration <= 4.5:
            bonus += 0.06
        if str(candidate_clip.get("primary_evidence", "") or "") == "reaction_score":
            bonus += 0.03
        if candidate_role == "single_focus":
            bonus += 0.08
        elif candidate_role == "dialogue_exchange":
            bonus += 0.03
        if anchor_speakers and candidate_targets and (anchor_speakers & candidate_targets):
            bonus += 0.05
    elif template == "inner_reaction":
        reaction_evidence = _explicit_clip_score(candidate_clip, "reaction_score") or 0.0
        inner_evidence = _explicit_clip_score(candidate_clip, "inner_state_support") or 0.0
        bonus += max(reaction_evidence, inner_evidence) * 0.12
        if candidate_scene_id and candidate_scene_id == anchor_scene_id:
            bonus += 0.14
        if candidate_clip.get("raw_audio_worthy"):
            bonus += 0.08
        if len(candidate_names) <= 1:
            bonus += 0.06
        if 1.4 <= candidate_duration <= 5.0:
            bonus += 0.06
        if str(candidate_clip.get("primary_evidence", "") or "") in {"inner_state_support", "reaction_score"}:
            bonus += 0.04
        if candidate_role == "single_focus":
            bonus += 0.1
        if anchor_speakers and candidate_targets and (anchor_speakers & candidate_targets):
            bonus += 0.06
        if anchor_targets and candidate_pressure_targets and (anchor_targets & candidate_pressure_targets):
            bonus += 0.06
        if anchor_pressure_sources and candidate_pressure_targets and (anchor_pressure_sources & candidate_pressure_targets):
            bonus += 0.06
    elif template == "relation_crosscut":
        relation_evidence = _explicit_clip_score(candidate_clip, "relation_score") or 0.0
        bonus += relation_evidence * 0.14
        bonus += (_explicit_clip_score(candidate_clip, "group_reaction_score") or 0.0) * 0.06
        if candidate_scene_id and candidate_scene_id == anchor_scene_id:
            bonus += 0.06
        if len(candidate_names) >= 2:
            bonus += 0.08
        if anchor_names and candidate_names and anchor_names != candidate_names:
            bonus += 0.06
        if candidate_start >= anchor_start:
            bonus += 0.04
        if str(candidate_clip.get("primary_evidence", "") or "") == "relation_score":
            bonus += 0.04
        if candidate_role == "dialogue_exchange":
            bonus += 0.08
        elif candidate_role == "ensemble_relation":
            bonus += 0.06
        if anchor_speakers and candidate_speakers and anchor_speakers != candidate_speakers:
            bonus += 0.06
        if anchor_targets and candidate_speakers and (anchor_targets & candidate_speakers):
            bonus += 0.04
        if anchor_speakers and candidate_speakers and any(
            (left in anchor_speakers and right in candidate_speakers)
            or (left in candidate_speakers and right in anchor_speakers)
            for left, right in (anchor_pairs | candidate_pairs)
        ):
            bonus += 0.06
        if anchor_pressure_targets and candidate_pressure_sources and (anchor_pressure_targets & candidate_pressure_sources):
            bonus += 0.06
        if anchor_pressure_sources and candidate_pressure_targets and (anchor_pressure_sources & candidate_pressure_targets):
            bonus += 0.06
        if candidate_pressure_targets and len(candidate_pressure_sources) >= 2:
            bonus += 0.04
        if len({name for pair in (anchor_pairs | candidate_pairs) for name in pair}) >= 3:
            bonus += 0.04
    else:
        overview_evidence = _explicit_clip_score(candidate_clip, "narrative_overview_score") or 0.0
        bonus += overview_evidence * 0.1
        bonus += (_explicit_clip_score(candidate_clip, "group_reaction_score") or 0.0) * 0.08
        if candidate_start >= anchor_start:
            bonus += 0.08
        if 2.0 <= candidate_duration <= 7.0:
            bonus += 0.05
        if str(candidate_clip.get("source", "") or "") in {"scene", "hybrid"}:
            bonus += 0.04
        if str(candidate_clip.get("primary_evidence", "") or "") == "narrative_overview_score":
            bonus += 0.03
        if candidate_role == "narrative_bridge":
            bonus += 0.06
        elif candidate_role == "ensemble_relation":
            bonus += 0.04
        if candidate_pressure_targets and len(candidate_pressure_sources) >= 2:
            bonus += 0.04

    bonus += _collective_target_bonus(unit, candidate_clip) * 0.35
    bonus += _directional_role_bonus(unit, candidate_clip, mode="subject") * 0.2
    bonus += _directional_role_bonus(unit, candidate_clip, mode="pair") * 0.2
    if str(unit.get("narration_type", "") or "") == "inner_state" and candidate_clip.get("raw_audio_worthy"):
        bonus += 0.04
    return round(bonus, 3)


def _neighbor_offsets(profile: str) -> List[int]:
    if profile == "fast":
        return [1, 2, -1]
    if profile == "pivot":
        return [1, -1, 2]
    if profile == "steady":
        return [1, -1]
    if profile == "resolve":
        return [1, -1]
    return [1, -1, 2]
