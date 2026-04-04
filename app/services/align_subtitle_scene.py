from __future__ import annotations

from typing import Dict, List

from loguru import logger



def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))



def _topic_shift(text_a: str, text_b: str) -> bool:
    a_tokens = set((text_a or "").replace("，", " ").replace("。", " ").split())
    b_tokens = set((text_b or "").replace("，", " ").replace("。", " ").split())
    if not a_tokens or not b_tokens:
        return False
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return (inter / max(union, 1)) < 0.15



def _build_segment(scene: Dict, subs: List[Dict], ordinal: int) -> Dict:
    if not subs:
        return {
            "segment_id": f"seg_{ordinal:03d}",
            "segment_type": "visual_only",
            "start": round(float(scene["start"]), 3),
            "end": round(float(scene["end"]), 3),
            "scene_id": scene["scene_id"],
            "subtitle_ids": [],
            "aligned_subtitle_ids": [],
            "aligned_subtitle_text": "",
            "frame_paths": [],
            "visual_only": True,
        }
    start = float(subs[0]["start"])
    end = max(float(s["end"]) for s in subs)
    texts = [s.get("text", "").strip() for s in subs if s.get("text")]
    ids = [s.get("seg_id") for s in subs if s.get("seg_id")]
    return {
        "segment_id": f"seg_{ordinal:03d}",
        "segment_type": "dialogue",
        "start": round(start, 3),
        "end": round(end, 3),
        "scene_id": scene["scene_id"],
        "subtitle_ids": ids,
        "aligned_subtitle_ids": ids,
        "aligned_subtitle_text": " ".join(texts).strip(),
        "frame_paths": [],
        "visual_only": False,
    }



def align_subtitles_to_scenes(
    subtitle_segments: List[Dict],
    scenes: List[Dict],
) -> List[Dict]:
    if not scenes:
        return []

    aligned: List[Dict] = []
    ordinal = 1
    for scene in scenes:
        scene_start = float(scene["start"])
        scene_end = float(scene["end"])
        overlapping = []
        for sub in subtitle_segments:
            if _overlap(scene_start, scene_end, float(sub["start"]), float(sub["end"])) > 0:
                overlapping.append(sub)
        if not overlapping:
            aligned.append(_build_segment(scene, [], ordinal))
            ordinal += 1
            continue

        # If a scene contains too many subtitles, split by topic shift / long gap.
        bucket: List[Dict] = [overlapping[0]]
        for prev, cur in zip(overlapping[:-1], overlapping[1:]):
            gap = float(cur["start"]) - float(prev["end"])
            too_many = len(bucket) >= 5
            topic_shift = _topic_shift(prev.get("text", ""), cur.get("text", ""))
            if gap > 1.8 or (too_many and topic_shift):
                aligned.append(_build_segment(scene, bucket, ordinal))
                ordinal += 1
                bucket = [cur]
            else:
                bucket.append(cur)
        if bucket:
            aligned.append(_build_segment(scene, bucket, ordinal))
            ordinal += 1

    # Merge adjacent short dialogue segments when they are too fragmented.
    merged: List[Dict] = []
    for seg in aligned:
        if not merged:
            merged.append(seg)
            continue
        prev = merged[-1]
        prev_duration = float(prev["end"]) - float(prev["start"])
        seg_duration = float(seg["end"]) - float(seg["start"])
        can_merge = (
            prev["segment_type"] == seg["segment_type"] == "dialogue"
            and prev["scene_id"] == seg["scene_id"]
            and prev_duration < 2.0
            and seg_duration < 2.5
        )
        if can_merge:
            prev["end"] = seg["end"]
            prev["subtitle_ids"].extend(seg["subtitle_ids"])
            prev["aligned_subtitle_ids"].extend(seg["aligned_subtitle_ids"])
            prev["aligned_subtitle_text"] = (
                (prev.get("aligned_subtitle_text") or "") + " " + (seg.get("aligned_subtitle_text") or "")
            ).strip()
            continue
        merged.append(seg)

    for idx, seg in enumerate(merged, start=1):
        seg["segment_id"] = f"seg_{idx:03d}"
    logger.info("字幕-场景对齐完成: {} 个 segment", len(merged))
    return merged
