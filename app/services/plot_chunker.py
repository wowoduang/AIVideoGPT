from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from loguru import logger


SPLIT_CUES = ("突然", "这时", "另一边", "与此同时", "后来", "随后", "最后", "最终", "原来", "然而", "可是")
ACTION_CUES = ("打", "冲", "追", "跑", "撞", "救", "杀", "逃", "爆炸", "开枪")
EMOTION_CUES = ("哭", "笑", "怒", "害怕", "惊", "沉默", "崩溃", "委屈", "紧张")
REVEAL_CUES = ("真相", "原来", "终于", "没想到", "居然", "结局", "最后", "反转")
TRANSITION_CUES = ("然后", "接着", "之后", "另一边", "与此同时", "第二天", "后来")


@dataclass
class ChunkPlan:
    target_duration_minutes: int = 8
    narrative_strategy: str = "chronological"
    accuracy_priority: str = "high"


def _seg_text(seg: Dict) -> str:
    return str(seg.get("text") or seg.get("content") or "").strip()


def _sorted_unique_strings(values: Sequence[str]) -> List[str]:
    return [
        value
        for value in dict.fromkeys(str(item or "").strip() for item in (values or []) if str(item or "").strip())
    ]


def _speaker_sequence_from_bucket(bucket: Sequence[Dict]) -> List[str]:
    return [
        speaker
        for speaker in (str(seg.get("speaker", "") or "").strip() for seg in (bucket or []))
        if speaker
    ]


def _speaker_exchange_pairs(speaker_sequence: Sequence[str]) -> List[str]:
    compact = [
        speaker
        for speaker in (str(item or "").strip() for item in (speaker_sequence or []))
        if speaker
    ]
    if not compact:
        return []

    turns: List[str] = []
    for speaker in compact:
        if not turns or speaker != turns[-1]:
            turns.append(speaker)

    pairs: List[str] = []
    for left, right in zip(turns, turns[1:]):
        if left and right and left != right:
            pairs.append(f"{left}->{right}")
    return pairs


def _duration(start: float, end: float) -> float:
    return max(float(end or 0.0) - float(start or 0.0), 0.0)


def _contains_any(text: str, cues) -> bool:
    return any(c in (text or "") for c in cues)


def _guess_block_type(text: str, visual_only: bool = False) -> str:
    if visual_only:
        return "visual"
    if _contains_any(text, ACTION_CUES):
        return "action"
    if _contains_any(text, EMOTION_CUES):
        return "emotion"
    if _contains_any(text, TRANSITION_CUES):
        return "transition"
    return "dialogue"


def _guess_plot_function(text: str, index: int, total: int) -> str:
    pos = index / max(total - 1, 1) if total > 1 else 0.0
    if pos <= 0.12:
        return "铺垫"
    if pos >= 0.88:
        return "结局收束"
    if _contains_any(text, REVEAL_CUES):
        return "反转"
    if _contains_any(text, EMOTION_CUES):
        return "情感爆发"
    if _contains_any(text, ACTION_CUES):
        return "冲突升级"
    if _contains_any(text, TRANSITION_CUES):
        return "节奏缓冲"
    return "信息揭露" if "说" in text or "告诉" in text else "铺垫"


def _guess_plot_role(plot_function: str) -> str:
    mapping = {
        "铺垫": "setup",
        "冲突升级": "conflict",
        "反转": "twist",
        "情感爆发": "conflict",
        "信息揭露": "development",
        "悬念制造": "twist",
        "节奏缓冲": "development",
        "结局收束": "ending",
    }
    return mapping.get(plot_function, "development")


def _importance_score(text: str, plot_function: str, duration: float) -> int:
    score = 1
    if _contains_any(text, REVEAL_CUES):
        score += 3
    if _contains_any(text, ACTION_CUES):
        score += 2
    if _contains_any(text, EMOTION_CUES):
        score += 2
    if plot_function in {"反转", "情感爆发", "结局收束"}:
        score += 2
    if duration > 25:
        score += 1
    return score


def _importance_level(score: int) -> str:
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _frame_budget(block_type: str, importance: str, duration: float) -> int:
    if block_type == "visual":
        return 3
    if importance == "high":
        return 3 if duration >= 18 else 2
    if importance == "medium":
        return 2 if duration >= 12 else 1
    return 1


def _audio_strategy(block_type: str, importance: str) -> str:
    if block_type in {"action", "visual"} and importance != "low":
        return "keep"
    return "duck"


def _build_candidate_times(start: float, end: float, count: int) -> List[float]:
    count = max(int(count or 1), 1)
    duration = max(end - start, 0.2)
    if count == 1:
        return [round(start + duration * 0.5, 3)]
    points = []
    for i in range(count):
        ratio = (i + 1) / (count + 1)
        points.append(round(start + duration * ratio, 3))
    return points


def _should_split(prev_seg: Dict, seg: Dict, bucket: List[Dict], bucket_text: str) -> bool:
    if not bucket:
        return False
    gap = float(seg.get("start", 0.0)) - float(prev_seg.get("end", 0.0))
    if gap > 2.8:
        return True
    text = _seg_text(seg)
    total_duration = float(seg.get("end", 0.0)) - float(bucket[0].get("start", 0.0))
    total_chars = len(bucket_text) + len(text)
    if total_duration >= 55:
        return True
    if total_chars >= 260:
        return True
    if len(bucket) >= 8 and _contains_any(text, SPLIT_CUES):
        return True
    if _contains_any(text, REVEAL_CUES) and total_duration >= 15:
        return True
    return False


def _merge_micro_chunks(chunks: List[Dict]) -> List[Dict]:
    if len(chunks) <= 1:
        return chunks
    merged: List[Dict] = [dict(chunks[0])]
    for chunk in chunks[1:]:
        duration = _duration(chunk["start"], chunk["end"])
        text = chunk.get("aligned_subtitle_text", "")
        if duration < 4.0 or len(text) < 14:
            prev = merged[-1]
            prev["end"] = chunk["end"]
            prev["subtitle_ids"].extend(chunk.get("subtitle_ids", []))
            prev["subtitle_texts"].extend(chunk.get("subtitle_texts", []))
            prev["speaker_sequence"] = list(prev.get("speaker_sequence") or []) + list(chunk.get("speaker_sequence") or [])
            prev["speaker_names"] = _sorted_unique_strings(
                list(prev.get("speaker_names") or []) + list(chunk.get("speaker_names") or [])
            )
            prev["speaker_turns"] = len(list(prev.get("speaker_sequence") or []))
            prev["exchange_pairs"] = _speaker_exchange_pairs(prev.get("speaker_sequence") or [])
            prev["aligned_subtitle_text"] = " ".join(x for x in prev["subtitle_texts"] if x).strip()
            prev["boundary_reasons"].append("merged_micro_chunk")
        else:
            merged.append(dict(chunk))
    return merged


def _flush_bucket(bucket: List[Dict], texts: List[str], *, boundary_source: str = "subtitle_only", boundary_sources: List[str] | None = None, boundary_reasons: List[str] | None = None, stage: str = "coarse", coarse_segment_id: str = "") -> Dict:
    subtitle_ids = [str(x.get("seg_id") or x.get("id") or "") for x in bucket]
    start = float(bucket[0].get("start", 0.0))
    end = float(bucket[-1].get("end", start + 1.0))
    joined = " ".join(x for x in texts if x).strip()
    speaker_sequence = _speaker_sequence_from_bucket(bucket)
    speaker_names = _sorted_unique_strings(speaker_sequence)
    speaker_turns = len(speaker_sequence)
    exchange_pairs = _speaker_exchange_pairs(speaker_sequence)
    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "subtitle_ids": subtitle_ids,
        "subtitle_texts": texts[:],
        "speaker_sequence": speaker_sequence,
        "speaker_names": speaker_names,
        "speaker_turns": speaker_turns,
        "exchange_pairs": exchange_pairs,
        "aligned_subtitle_text": joined,
        "subtitle_source": bucket[0].get("subtitle_source", bucket[0].get("source", "generated_srt")),
        "surface_dialogue_meaning": joined[:160],
        "real_narrative_state": joined[:160],
        "boundary_source": boundary_source,
        "boundary_sources": boundary_sources or [boundary_source],
        "boundary_confidence": "medium",
        "boundary_reasons": boundary_reasons or ["由连续字幕片段按规则合并得到"],
        "narrative_risk_flags": [],
        "need_visual_verify": False,
        "raw_voice_retain_suggestion": False,
        "segment_stage": stage,
        "coarse_segment_id": coarse_segment_id or "",
    }


def apply_duration_plan(chunks: Sequence[Dict], plan: ChunkPlan) -> List[Dict]:
    items = [dict(x) for x in (chunks or [])]
    if not items:
        return []
    movie_minutes = max(float(items[-1].get("end", 0.0)) / 60.0, 1.0)
    target_minutes = max(int(plan.target_duration_minutes or 8), 1)
    ratio = target_minutes / movie_minutes

    for item in items:
        importance = item.get("importance_level", "medium")
        plot_function = item.get("plot_function", "信息揭露")
        if ratio <= 0.08:
            level = "focus" if importance == "high" or plot_function in {"反转", "结局收束"} else "brief"
        elif ratio <= 0.14:
            level = "focus" if importance == "high" else ("standard" if importance == "medium" else "brief")
        else:
            level = "standard" if importance != "low" else "brief"
        if plan.accuracy_priority == "high" and item.get("block_type") == "transition":
            level = "brief"
        item["narration_level"] = level

        duration = _duration(item["start"], item["end"])
        base_chars = max(int(duration * 3.0), 10)
        if level == "focus":
            planned_chars = max(int(base_chars * 1.15), 26)
        elif level == "standard":
            planned_chars = max(base_chars, 18)
        else:
            planned_chars = max(int(base_chars * 0.55), 10)
        item["planned_char_budget"] = planned_chars
    return items


def _tokenize_for_overlap(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]", text or "")
    return {t for t in tokens if t.strip()}


def _text_overlap(text_a: str, text_b: str) -> float:
    a = _tokenize_for_overlap(text_a)
    b = _tokenize_for_overlap(text_b)
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _find_nearest_video_candidate(target_time: float, video_candidates: Sequence[Dict], window: float = 1.6) -> Dict | None:
    best = None
    best_dist = None
    for item in video_candidates or []:
        try:
            t = float(item.get("time", 0.0) or 0.0)
        except Exception:
            continue
        dist = abs(t - target_time)
        if dist <= window and (best is None or dist < best_dist):
            best = item
            best_dist = dist
    return best


def _boundary_score(prev_seg: Dict, next_seg: Dict, video_candidates: Sequence[Dict]) -> Tuple[float, List[str], List[str]]:
    prev_text = _seg_text(prev_seg)
    next_text = _seg_text(next_seg)
    gap = float(next_seg.get("start", 0.0) or 0.0) - float(prev_seg.get("end", 0.0) or 0.0)
    split_time = round((float(prev_seg.get("end", 0.0)) + float(next_seg.get("start", 0.0))) / 2.0, 3)

    score = 0.0
    reasons: List[str] = []
    sources = {"subtitle"}

    if gap >= 1.6:
        score += 0.28
        reasons.append("相邻字幕存在明显时间间隙")
    elif gap >= 0.8:
        score += 0.14
        reasons.append("相邻字幕存在短停顿")

    overlap = _text_overlap(prev_text, next_text)
    if overlap < 0.15:
        score += 0.18
        reasons.append("字幕语义连续性较弱")
    elif overlap < 0.28:
        score += 0.10

    if _contains_any(next_text, SPLIT_CUES) or _contains_any(next_text, TRANSITION_CUES):
        score += 0.18
        reasons.append("检测到转场/切段提示词")
    if _contains_any(next_text, REVEAL_CUES):
        score += 0.20
        reasons.append("检测到揭露/反转提示词")
    if prev_seg.get("speaker") and next_seg.get("speaker") and prev_seg.get("speaker") != next_seg.get("speaker"):
        score += 0.10
        reasons.append("说话人发生变化")

    video_hit = _find_nearest_video_candidate(split_time, video_candidates, window=1.6)
    if video_hit:
        score += max(float(video_hit.get("score", 0.6) or 0.6) * 0.42, 0.22)
        reasons.extend(video_hit.get("reasons") or [video_hit.get("reason") or "视觉候选边界"])
        sources.add("video")

    return round(min(score, 1.0), 3), list(dict.fromkeys(reasons)), sorted(sources)



def _make_refined_chunks(coarse_chunk: Dict, subs: List[Dict], video_candidates: Sequence[Dict]) -> List[Dict]:
    if len(subs) <= 2:
        return [dict(coarse_chunk)]
    coarse_duration = _duration(coarse_chunk.get("start", 0.0), coarse_chunk.get("end", 0.0))
    if coarse_duration < 14.0 and len(subs) <= 4:
        return [dict(coarse_chunk)]

    cut_indices: List[int] = []
    for idx in range(1, len(subs)):
        left = subs[:idx]
        right = subs[idx:]
        left_duration = _duration(left[0]["start"], left[-1]["end"])
        right_duration = _duration(right[0]["start"], right[-1]["end"])
        if left_duration < 4.0 or right_duration < 4.0:
            continue
        score, reasons, sources = _boundary_score(subs[idx - 1], subs[idx], video_candidates)
        threshold = 0.64 if "video" in sources else 0.78
        if score >= threshold:
            cut_indices.append(idx)

    if not cut_indices:
        return [dict(coarse_chunk)]

    refined: List[Dict] = []
    start_idx = 0
    cut_points = cut_indices + [len(subs)]
    for ordinal, cut_idx in enumerate(cut_points, start=1):
        bucket = subs[start_idx:cut_idx]
        if not bucket:
            start_idx = cut_idx
            continue
        if start_idx == 0:
            boundary_reasons = ["粗分段后进入精分段评估"]
            boundary_source = coarse_chunk.get("boundary_source", "subtitle_only")
            boundary_sources = list(coarse_chunk.get("boundary_sources") or [boundary_source])
        else:
            score, reasons, sources = _boundary_score(subs[start_idx - 1], subs[start_idx], video_candidates)
            boundary_reasons = reasons or ["精分段切点"]
            boundary_source = "subtitle+video" if "video" in sources and "subtitle" in sources else (f"{sources[0]}_only" if sources else "subtitle_only")
            boundary_sources = sources or ["subtitle"]
        refined.append(
            _flush_bucket(
                bucket,
                [_seg_text(x) for x in bucket],
                boundary_source=boundary_source,
                boundary_sources=boundary_sources,
                boundary_reasons=boundary_reasons,
                stage="fine",
                coarse_segment_id=coarse_chunk.get("segment_id") or coarse_chunk.get("coarse_segment_id") or "",
            )
        )
        start_idx = cut_idx

    if len(refined) <= 1:
        return [dict(coarse_chunk)]
    return refined


def _annotate_chunks(chunks: List[Dict], *, target_duration_minutes: int, narrative_strategy: str, accuracy_priority: str) -> List[Dict]:
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        text = chunk.get("aligned_subtitle_text", "")
        duration = _duration(chunk["start"], chunk["end"])
        plot_function = _guess_plot_function(text, idx - 1, total)
        role = _guess_plot_role(plot_function)
        block_type = _guess_block_type(text)
        score = _importance_score(text, plot_function, duration)
        importance = _importance_level(score)
        frame_budget = _frame_budget(block_type, importance, duration)
        need_visual_verify = block_type in {"action", "visual"} or plot_function in {"反转", "情感爆发"} or "video" in str(chunk.get("boundary_source", ""))

        chunk.update({
            "scene_id": f"plot_{idx:03d}",
            "segment_id": f"plot_{idx:03d}",
            "plot_role": role,
            "plot_function": plot_function,
            "block_type": block_type,
            "importance_score": score,
            "importance_level": importance,
            "attraction_level": "高" if importance == "high" else ("中" if importance == "medium" else "低"),
            "audio_strategy": _audio_strategy(block_type, importance),
            "frame_budget": frame_budget,
            "keyframe_candidates": _build_candidate_times(chunk["start"], chunk["end"], frame_budget),
            "target_duration_minutes": int(target_duration_minutes or 8),
            "narrative_strategy": narrative_strategy or "chronological",
            "accuracy_priority": accuracy_priority or "high",
            "visual_only": False,
            "need_visual_verify": need_visual_verify,
            "raw_voice_retain_suggestion": bool(importance == "high" and plot_function in {"情感爆发", "反转"}),
            "surface_dialogue_meaning": text[:160],
            "real_narrative_state": text[:160],
        })
    return chunks


def _highlight_priority(chunk: Dict, index: int, total: int) -> float:
    score = 0.0
    importance = str(chunk.get("importance_level") or "medium")
    plot_role = str(chunk.get("plot_role") or "development")
    block_type = str(chunk.get("block_type") or "dialogue")
    duration = _duration(chunk.get("start", 0.0), chunk.get("end", 0.0))
    text = str(chunk.get("aligned_subtitle_text") or "")
    boundary_source = str(chunk.get("boundary_source") or "")

    if importance == "high":
        score += 3.0
    elif importance == "medium":
        score += 1.4
    else:
        score -= 0.6

    if plot_role in {"twist", "conflict", "ending"}:
        score += 1.8
    elif plot_role == "development":
        score += 0.6
    elif plot_role == "setup":
        score -= 0.8

    if block_type in {"action", "emotion", "visual"}:
        score += 1.0
    elif block_type == "transition":
        score -= 1.2

    if "video" in boundary_source:
        score += 0.5
    if chunk.get("need_visual_verify"):
        score += 0.4
    if chunk.get("raw_voice_retain_suggestion"):
        score += 0.6

    if 4.0 <= duration <= 28.0:
        score += 0.4
    elif duration >= 45.0:
        score -= 0.8

    if len(text) < 12:
        score -= 0.5
    if index <= max(1, int(total * 0.12)) and plot_role == "setup":
        score -= 1.8
    if index >= max(1, int(total * 0.88)) and plot_role == "ending":
        score += 0.5

    return round(score, 3)


def _resolve_highlight_selectivity(value: str) -> str:
    normalized = str(value or "balanced").strip().lower()
    if normalized in {"loose", "balanced", "strict"}:
        return normalized
    return "balanced"


def _select_story_highlights(chunks: List[Dict], highlight_selectivity: str = "balanced") -> List[Dict]:
    if not chunks:
        return []

    highlight_selectivity = _resolve_highlight_selectivity(highlight_selectivity)
    total = len(chunks)
    scored: List[Dict] = []
    keep_indices = set()
    soft_keep_threshold = {
        "loose": 1.2,
        "balanced": 1.9,
        "strict": 2.4,
    }[highlight_selectivity]
    should_drop_threshold = {
        "loose": 0.1,
        "balanced": 1.0,
        "strict": 1.3,
    }[highlight_selectivity]
    fallback_target = {
        "loose": min(5, total),
        "balanced": min(4, total),
        "strict": min(3, total),
    }[highlight_selectivity]
    minimum_selected = {
        "loose": min(3, total),
        "balanced": min(3, total),
        "strict": min(2, total),
    }[highlight_selectivity]

    for idx, chunk in enumerate(chunks):
        current = dict(chunk)
        priority = _highlight_priority(current, idx + 1, total)
        current["highlight_priority"] = priority

        importance = str(current.get("importance_level") or "medium")
        plot_role = str(current.get("plot_role") or "development")
        block_type = str(current.get("block_type") or "dialogue")

        hard_keep = (
            importance == "high"
            or plot_role in {"twist", "ending"}
            or current.get("raw_voice_retain_suggestion")
        )
        soft_keep = priority >= soft_keep_threshold
        should_drop = (
            priority < should_drop_threshold
            and importance == "low"
            and (plot_role == "setup" or block_type == "transition")
        )

        current["selected_for_story"] = hard_keep or (soft_keep and not should_drop)
        current["story_drop_reason"] = ""
        if not current["selected_for_story"]:
            current["story_drop_reason"] = "low_priority_setup_or_transition"
        scored.append(current)

    for idx, chunk in enumerate(scored):
        if not chunk.get("selected_for_story"):
            continue
        keep_indices.add(idx)

        # Keep minimal context around strong beats so narration stays accurate.
        if idx > 0:
            prev = scored[idx - 1]
            if (
                str(prev.get("importance_level") or "low") != "low"
                or str(prev.get("plot_role") or "") in {"setup", "development"}
            ):
                keep_indices.add(idx - 1)
        if idx + 1 < total:
            nxt = scored[idx + 1]
            if str(nxt.get("importance_level") or "low") != "low" or str(nxt.get("plot_role") or "") == "ending":
                keep_indices.add(idx + 1)

    selected = []
    for idx, chunk in enumerate(scored):
        if idx in keep_indices:
            chunk["selected_for_story"] = True
            chunk["story_drop_reason"] = ""
            selected.append(chunk)

    if len(selected) < minimum_selected:
        fallback = sorted(scored, key=lambda x: x.get("highlight_priority", 0.0), reverse=True)[:fallback_target]
        fallback_ids = {item.get("segment_id") for item in fallback}
        selected = [chunk for chunk in scored if chunk.get("segment_id") in fallback_ids]
        for chunk in selected:
            chunk["selected_for_story"] = True
            chunk["story_drop_reason"] = ""

    logger.info(
        "高光筛选完成: raw_chunks=%s, selected=%s, dropped=%s",
        total,
        len(selected),
        max(total - len(selected), 0),
    )
    return selected


def build_plot_chunks_from_subtitles(
    subtitle_segments: Sequence[Dict],
    target_duration_minutes: int = 8,
    narrative_strategy: str = "chronological",
    accuracy_priority: str = "high",
    highlight_selectivity: str = "balanced",
    video_candidates: Sequence[Dict] | None = None,
    refine_chunks: bool = True,
) -> List[Dict]:
    segments = [dict(x) for x in (subtitle_segments or []) if _seg_text(x)]
    if not segments:
        return []

    video_candidates = list(video_candidates or [])

    chunks_raw: List[Dict] = []
    bucket: List[Dict] = []
    bucket_texts: List[str] = []
    prev_seg = None

    for seg in segments:
        text = _seg_text(seg)
        if prev_seg is not None and _should_split(prev_seg, seg, bucket, " ".join(bucket_texts)):
            chunks_raw.append(_flush_bucket(bucket, bucket_texts, boundary_source="subtitle_only", boundary_sources=["subtitle"], boundary_reasons=["字幕连续性下降，触发粗分段"], stage="coarse"))
            bucket = []
            bucket_texts = []
        bucket.append(seg)
        bucket_texts.append(text)
        prev_seg = seg

    if bucket:
        chunks_raw.append(_flush_bucket(bucket, bucket_texts, boundary_source="subtitle_only", boundary_sources=["subtitle"], boundary_reasons=["由连续字幕片段按规则合并得到"], stage="coarse"))

    chunks_raw = _merge_micro_chunks(chunks_raw)

    if refine_chunks:
        seg_map = {str(x.get("seg_id") or x.get("id") or ""): dict(x) for x in segments}
        refined: List[Dict] = []
        for coarse in chunks_raw:
            subs = [seg_map[sid] for sid in coarse.get("subtitle_ids", []) if sid in seg_map]
            if subs:
                refined.extend(_make_refined_chunks(coarse, subs, video_candidates))
            else:
                refined.append(dict(coarse))
        chunks_raw = refined

    chunks_raw = _annotate_chunks(
        chunks_raw,
        target_duration_minutes=target_duration_minutes,
        narrative_strategy=narrative_strategy,
        accuracy_priority=accuracy_priority,
    )
    selected_chunks = _select_story_highlights(chunks_raw, highlight_selectivity=highlight_selectivity)
    planned = apply_duration_plan(selected_chunks, ChunkPlan(target_duration_minutes, narrative_strategy, accuracy_priority))
    logger.info(
        "剧情块构建完成: %s 个剧情块, target_minutes=%s, video_candidates=%s",
        len(planned),
        target_duration_minutes,
        len(video_candidates),
    )
    return planned
