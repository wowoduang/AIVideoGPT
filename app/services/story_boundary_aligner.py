from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple


def collect_candidate_boundaries(subtitle_segments: Sequence[Dict]) -> List[Dict]:
    candidates: List[Dict] = []
    for seg in subtitle_segments or []:
        for key, kind in (("start", "subtitle_start"), ("end", "subtitle_end")):
            try:
                value = float(seg.get(key, 0.0) or 0.0)
            except Exception:
                value = 0.0
            candidates.append(
                {
                    "time": round(max(0.0, value), 3),
                    "source": "subtitle",
                    "type": kind,
                    "score": 0.55,
                    "reason": "字幕边界候选",
                }
            )
    return merge_boundary_candidates(candidates, merge_window_sec=0.12)


def normalize_boundary_candidates(candidate_boundaries: Sequence) -> List[Dict]:
    normalized: List[Dict] = []
    for item in candidate_boundaries or []:
        if isinstance(item, (int, float)):
            normalized.append(
                {
                    "time": round(float(item), 3),
                    "source": "unknown",
                    "sources": ["unknown"],
                    "type": "generic",
                    "score": 0.5,
                    "reason": "通用边界候选",
                    "reasons": ["通用边界候选"],
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        try:
            time_value = float(item.get("time", item.get("timestamp", 0.0)) or 0.0)
        except Exception:
            continue
        source = str(item.get("source") or "unknown")
        reason = str(item.get("reason") or item.get("boundary_reason") or "候选边界").strip() or "候选边界"
        raw_sources = item.get("sources") or [source]
        if isinstance(raw_sources, str):
            raw_sources = [raw_sources]
        normalized.append(
            {
                "time": round(max(0.0, time_value), 3),
                "source": source,
                "sources": sorted({str(x) for x in raw_sources if x}),
                "type": str(item.get("type") or "generic"),
                "score": float(item.get("score", 0.5) or 0.5),
                "reason": reason,
                "reasons": list(dict.fromkeys([reason] + list(item.get("reasons") or []))),
            }
        )
    return normalized


def merge_boundary_candidates(candidate_boundaries: Sequence, merge_window_sec: float = 0.8) -> List[Dict]:
    items = sorted(normalize_boundary_candidates(candidate_boundaries), key=lambda x: x["time"])
    if not items:
        return []

    merged: List[Dict] = []
    current = dict(items[0])
    current.setdefault("sources", [current.get("source", "unknown")])
    current.setdefault("reasons", [current.get("reason", "候选边界")])

    for item in items[1:]:
        if abs(float(item["time"]) - float(current["time"])) <= merge_window_sec:
            all_times = [float(current["time"]), float(item["time"])]
            current["time"] = round(sum(all_times) / len(all_times), 3)
            current["score"] = max(float(current.get("score", 0.5)), float(item.get("score", 0.5)))
            current["sources"] = sorted(set(list(current.get("sources") or []) + list(item.get("sources") or [])))
            current["reasons"] = list(dict.fromkeys(list(current.get("reasons") or []) + list(item.get("reasons") or [])))
            if current["source"] != item["source"]:
                current["source"] = "+".join(current["sources"])
        else:
            merged.append(current)
            current = dict(item)
            current.setdefault("sources", [current.get("source", "unknown")])
            current.setdefault("reasons", [current.get("reason", "候选边界")])
    merged.append(current)
    return merged


def _snap_time(target: float, candidates: Sequence[Dict], window: float) -> Tuple[float, float, Dict | None]:
    if not candidates:
        return round(target, 3), 999.0, None
    best = min(candidates, key=lambda x: abs(float(x["time"]) - target))
    distance = abs(float(best["time"]) - target)
    if distance <= window:
        return round(float(best["time"]), 3), round(distance, 3), best
    return round(target, 3), round(distance, 3), None


def _boundary_confidence(boundary_score: float, start_dist: float, end_dist: float) -> str:
    adjusted = boundary_score
    if max(start_dist, end_dist) <= 0.5:
        adjusted += 0.08
    elif max(start_dist, end_dist) > 2.5:
        adjusted -= 0.08
    if adjusted >= 0.82:
        return "high"
    if adjusted >= 0.62:
        return "medium"
    return "low"


def _candidate_score(*candidates: Dict | None) -> float:
    scores = [float(c.get("score", 0.5)) for c in candidates if c]
    if not scores:
        return 0.5
    if len(scores) == 1:
        return scores[0]
    return min(1.0, sum(scores) / len(scores) + 0.08)


def _summarize_sources(*candidates: Dict | None) -> Tuple[List[str], str]:
    sources: List[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        sources.extend(candidate.get("sources") or [candidate.get("source") or "unknown"])
    deduped = sorted({x for x in sources if x})
    if not deduped:
        return ["unknown"], "unknown"
    if len(deduped) == 1:
        only = deduped[0]
        return deduped, f"{only}_only"
    return deduped, "+".join(deduped)


def align_story_boundaries(
    story_segments: Sequence[Dict],
    candidate_boundaries: Sequence,
    snap_window: float = 2.0,
) -> List[Dict]:
    candidates = merge_boundary_candidates(candidate_boundaries, merge_window_sec=min(max(snap_window / 2.0, 0.2), 1.0))
    results: List[Dict] = []

    for seg in story_segments or []:
        item = dict(seg)
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start + 1.0) or (start + 1.0))

        aligned_start, start_dist, start_hit = _snap_time(start, candidates, snap_window)
        aligned_end, end_dist, end_hit = _snap_time(end, candidates, snap_window)
        if aligned_end <= aligned_start:
            aligned_end = max(aligned_start + 0.5, end)

        boundary_sources, boundary_source = _summarize_sources(start_hit, end_hit)
        boundary_score = _candidate_score(start_hit, end_hit)
        boundary_confidence = _boundary_confidence(boundary_score, start_dist, end_dist)

        reasons = list(item.get("boundary_reasons") or [])
        if start_hit:
            reasons.extend(start_hit.get("reasons") or [])
            reasons.append(f"start_snap={start:.3f}->{aligned_start:.3f} (dist={start_dist:.3f})")
        else:
            reasons.append(f"start_keep={start:.3f}")
        if end_hit:
            reasons.extend(end_hit.get("reasons") or [])
            reasons.append(f"end_snap={end:.3f}->{aligned_end:.3f} (dist={end_dist:.3f})")
        else:
            reasons.append(f"end_keep={end:.3f}")
        reasons = list(dict.fromkeys(reasons))

        item["start_hint"] = round(start, 3)
        item["end_hint"] = round(end, 3)
        item["start"] = round(aligned_start, 3)
        item["end"] = round(aligned_end, 3)
        item["boundary_sources"] = boundary_sources
        item["boundary_source"] = boundary_source
        item["boundary_score"] = round(boundary_score, 3)
        item["boundary_confidence"] = boundary_confidence
        item["boundary_reasons"] = reasons
        item["boundary_snap_distance"] = {"start": round(start_dist, 3), "end": round(end_dist, 3)}
        results.append(item)
    return results
