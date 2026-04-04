from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from loguru import logger


DEFAULT_TOKENS_PER_FRAME = 630
DEFAULT_MAX_TOTAL_FRAMES = 24


def estimate_visual_tokens(frame_count: int, tokens_per_frame: int = DEFAULT_TOKENS_PER_FRAME) -> int:
    return max(0, int(frame_count or 0) * int(tokens_per_frame))


def estimate_visual_cost_cny(
    frame_count: int,
    input_price_per_million: float = 0.96,
    tokens_per_frame: int = DEFAULT_TOKENS_PER_FRAME,
) -> float:
    tokens = estimate_visual_tokens(frame_count, tokens_per_frame=tokens_per_frame)
    return round(tokens / 1_000_000 * input_price_per_million, 4)


def cap_frame_records(
    frame_records: List[Dict],
    max_total_frames: int = DEFAULT_MAX_TOTAL_FRAMES,
) -> Tuple[List[Dict], Dict]:
    """Cap selected representative frames to control token spend.

    Strategy:
    - preserve chronological order
    - try to keep at least 1 frame per scene
    - distribute remaining slots proportionally
    """
    if not frame_records:
        return [], {"original": 0, "capped": 0, "estimated_tokens": 0}

    original_count = len(frame_records)
    if original_count <= max_total_frames:
        return list(frame_records), {
            "original": original_count,
            "capped": original_count,
            "estimated_tokens": estimate_visual_tokens(original_count),
        }

    grouped: Dict[str, List[Dict]] = defaultdict(list)
    ordered_scene_ids: List[str] = []
    for rec in frame_records:
        scene_id = rec.get("scene_id", "scene_unknown")
        if scene_id not in grouped:
            ordered_scene_ids.append(scene_id)
        grouped[scene_id].append(rec)

    # Always keep one middle frame per scene first
    selected: List[Dict] = []
    leftovers: List[Dict] = []
    for scene_id in ordered_scene_ids:
        items = sorted(grouped[scene_id], key=lambda x: x.get("timestamp_seconds", 0.0))
        middle_idx = len(items) // 2
        selected.append(items[middle_idx])
        leftovers.extend(items[:middle_idx] + items[middle_idx + 1 :])

    remaining_slots = max(0, max_total_frames - len(selected))
    if remaining_slots > 0 and leftovers:
        leftovers = sorted(leftovers, key=lambda x: x.get("timestamp_seconds", 0.0))
        if remaining_slots >= len(leftovers):
            selected.extend(leftovers)
        else:
            step = (len(leftovers) - 1) / max(1, remaining_slots - 1) if remaining_slots > 1 else 0
            indices = [round(i * step) for i in range(remaining_slots)] if remaining_slots > 1 else [len(leftovers) // 2]
            seen = set()
            for idx in indices:
                idx = max(0, min(len(leftovers) - 1, idx))
                if idx not in seen:
                    selected.append(leftovers[idx])
                    seen.add(idx)
            # backfill if duplicates reduced count
            if len(selected) < max_total_frames:
                for item in leftovers:
                    if len(selected) >= max_total_frames:
                        break
                    if item not in selected:
                        selected.append(item)

    selected = sorted(selected, key=lambda x: (x.get("scene_id", ""), x.get("timestamp_seconds", 0.0)))[:max_total_frames]
    meta = {
        "original": original_count,
        "capped": len(selected),
        "estimated_tokens": estimate_visual_tokens(len(selected)),
        "estimated_cost_cny": estimate_visual_cost_cny(len(selected)),
    }
    logger.info(
        f"视觉预算控制: {original_count} -> {len(selected)} 帧, 预计输入token≈{meta['estimated_tokens']}, 预计成本≈¥{meta['estimated_cost_cny']}"
    )
    return selected, meta
