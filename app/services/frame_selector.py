from __future__ import annotations

import os
from typing import Dict, List

from loguru import logger


def parse_keyframe_timestamp(path: str) -> float:
    filename = os.path.basename(path)
    parts = filename.split("_")
    raw = parts[-1].split(".")[0] if parts else ""
    if raw.isdigit() and len(raw) >= 9:
        h = int(raw[0:2])
        m = int(raw[2:4])
        s = int(raw[4:6])
        ms = int(raw[6:9])
        return h * 3600 + m * 60 + s + ms / 1000.0
    try:
        return int(raw) / 1000.0
    except Exception:
        return 0.0



def select_representative_frames(
    scenes: List[Dict],
    keyframe_files: List[str],
    frames_per_scene: int = 2,
) -> List[Dict]:
    """Backward-compatible selector for externally extracted keyframes."""
    if not scenes or not keyframe_files:
        return []

    indexed = [
        {"frame_path": p, "timestamp_seconds": parse_keyframe_timestamp(p)}
        for p in keyframe_files
    ]
    records: List[Dict] = []
    for scene in scenes:
        start = float(scene.get("start", 0.0) or 0.0)
        end = float(scene.get("end", 0.0) or 0.0)
        scene_id = scene.get("scene_id") or scene.get("segment_id") or "scene_000"
        seg_id = scene.get("segment_id") or scene_id
        scene_frames = [f for f in indexed if start <= f["timestamp_seconds"] <= end]
        if not scene_frames:
            continue
        if len(scene_frames) <= frames_per_scene:
            selected = scene_frames
        else:
            step = max(len(scene_frames) / float(frames_per_scene), 1.0)
            selected = [scene_frames[min(int(i * step), len(scene_frames) - 1)] for i in range(frames_per_scene)]
        for rank, frame in enumerate(selected, start=1):
            records.append(
                {
                    "scene_id": scene_id,
                    "segment_id": seg_id,
                    "frame_path": frame["frame_path"],
                    "timestamp_seconds": frame["timestamp_seconds"],
                    "rank": rank,
                }
            )
    logger.info("外部关键帧选择完成: {} 张", len(records))
    return records
