from __future__ import annotations

from typing import Dict, Iterable, List, Sequence


def collect_candidate_boundaries(subtitle_segments: Sequence[Dict]) -> List[float]:
    points: List[float] = []
    for seg in subtitle_segments or []:
        for key in ("start", "end"):
            try:
                value = float(seg.get(key, 0.0) or 0.0)
            except Exception:
                value = 0.0
            points.append(round(max(0.0, value), 3))
    points = sorted(set(points))
    return points


def _snap_time(target: float, candidates: Sequence[float], window: float) -> tuple[float, float]:
    if not candidates:
        return round(target, 3), 999.0
    best = min(candidates, key=lambda x: abs(x - target))
    distance = abs(best - target)
    if distance <= window:
        return round(best, 3), round(distance, 3)
    return round(target, 3), round(distance, 3)


def _confidence_from_distance(start_dist: float, end_dist: float) -> str:
    worst = max(start_dist, end_dist)
    if worst <= 1.0:
        return "high"
    if worst <= 4.0:
        return "medium"
    return "low"


def align_story_boundaries(
    story_segments: Sequence[Dict],
    candidate_boundaries: Sequence[float],
    snap_window: float = 8.0,
) -> List[Dict]:
    results: List[Dict] = []
    for seg in story_segments or []:
        item = dict(seg)
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start) or start)

        aligned_start, start_dist = _snap_time(start, candidate_boundaries, snap_window)
        aligned_end, end_dist = _snap_time(end, candidate_boundaries, snap_window)

        if aligned_end <= aligned_start:
            aligned_end = max(aligned_start + 0.5, end)

        reasons = list(item.get("boundary_reasons") or [])
        reasons.append(f"start_hint={start:.3f}, aligned_start={aligned_start:.3f}, dist={start_dist:.3f}")
        reasons.append(f"end_hint={end:.3f}, aligned_end={aligned_end:.3f}, dist={end_dist:.3f}")

        item["start_hint"] = round(start, 3)
        item["end_hint"] = round(end, 3)
        item["start"] = round(aligned_start, 3)
        item["end"] = round(aligned_end, 3)
        item["boundary_source"] = "candidate_boundary_snap"
        item["boundary_confidence"] = _confidence_from_distance(start_dist, end_dist)
        item["boundary_reasons"] = reasons
        item["boundary_snap_distance"] = {
            "start": round(start_dist, 3),
            "end": round(end_dist, 3),
        }
        results.append(item)
    return results
