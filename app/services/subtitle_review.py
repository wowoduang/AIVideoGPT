from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Dict, List

from loguru import logger

from app.utils import utils


SUSPICIOUS_REPLY_CHARS = {"不", "对", "嗯", "啊", "哦", "诶", "哎", "欸", "唉"}
_LEADING_PUNCT_RE = re.compile(r"^[，。！？；：、,.!?;:]+")
_FILLER_RE = re.compile(r"^[啊哦嗯哎诶欸唉哈呵呃噢]+[。！？、，,.!?]*$")


def _core_text(text: str) -> str:
    return re.sub(r"[，。！？；：、“”‘’《》、,.!?;:\-\—~…·\s]", "", text or "")


def _format_srt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds or 0.0))
    ms = int(round((seconds - int(seconds)) * 1000))
    total_seconds = int(seconds)
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    if ms >= 1000:
        s += 1
        ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _segments_to_srt(segments: List[Dict]) -> str:
    lines: List[str] = []
    for idx, seg in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_srt_time(seg['start'])} --> {_format_srt_time(seg['end'])}")
        lines.append(str(seg["text"]))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _derive_review_paths(subtitle_path: str) -> Dict[str, str]:
    root, _ = os.path.splitext(subtitle_path)
    return {
        "overrides": f"{root}_review_overrides.json",
        "final_srt": f"{root}_final.srt",
        "final_segments": f"{root}_final_segments.json",
    }


def _merge_for_llm(left: str, right: str) -> str:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left:
        return right
    if not right:
        return left
    if _LEADING_PUNCT_RE.match(right):
        right = _LEADING_PUNCT_RE.sub("", right, count=1).strip()
    if _core_text(left) in SUSPICIOUS_REPLY_CHARS and not left.endswith(("，", "。", "！", "？", ",", ".", "!", "?")):
        return f"{left}，{right}"
    return f"{left}{right}"


def _reason_label(reason: str) -> str:
    mapping = {
        "single_char_prefix": "单字回应，建议与后句合并审核",
        "leading_punct_fragment": "前导标点残片，建议并入后句",
        "filler_prefix": "语气词残片，建议与后句一起审核",
        "short_prefix": "超短前缀片段，建议与后句合并审核",
    }
    return mapping.get(reason, reason)


def detect_suspicious_groups(segments: List[Dict], max_candidates: int = 20) -> List[Dict]:
    candidates: List[Dict] = []
    used_ids = set()

    normalized = []
    for idx, seg in enumerate(segments or [], start=1):
        cur = dict(seg)
        cur["seg_id"] = cur.get("seg_id") or f"sub_{idx:04d}"
        cur["text"] = str(cur.get("text", "") or "").strip()
        if not cur["text"]:
            continue
        normalized.append(cur)

    for idx, seg in enumerate(normalized):
        if len(candidates) >= max_candidates:
            break
        seg_id = seg["seg_id"]
        if seg_id in used_ids:
            continue

        text = seg["text"]
        core = _core_text(text)
        next_seg = normalized[idx + 1] if idx + 1 < len(normalized) else None
        reason = None
        related = None

        if next_seg is None:
            continue

        if _LEADING_PUNCT_RE.match(text):
            reason = "leading_punct_fragment"
            related = [seg, next_seg]
        elif _FILLER_RE.match(text):
            reason = "filler_prefix"
            related = [seg, next_seg]
        elif len(core) <= 1 and core in SUSPICIOUS_REPLY_CHARS:
            reason = "single_char_prefix"
            related = [seg, next_seg]
        elif len(core) <= 2 and not text.endswith(("。", "！", "？", ".", "!", "?")):
            reason = "short_prefix"
            related = [seg, next_seg]

        if not reason or not related:
            continue

        related_ids = [item["seg_id"] for item in related]
        if any(x in used_ids for x in related_ids):
            continue

        start = min(float(item.get("start", 0.0) or 0.0) for item in related)
        end = max(float(item.get("end", start) or start) for item in related)
        suggested_text = related[0]["text"]
        for item in related[1:]:
            suggested_text = _merge_for_llm(suggested_text, item["text"])

        candidate = {
            "candidate_id": f"cand_{len(candidates) + 1:03d}",
            "reason": reason,
            "reason_label": _reason_label(reason),
            "related_segment_ids": related_ids,
            "start": start,
            "end": end,
            "time_range": f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
            "raw_text": seg["text"],
            "context_text": " ｜ ".join(item["text"] for item in related),
            "suggested_text": suggested_text,
            "frame_path": "",
        }
        candidates.append(candidate)
        used_ids.update(related_ids)

    return candidates


def _extract_frame_ffmpeg(video_path: str, timestamp: float, image_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(max(0.0, float(timestamp))),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            image_path,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return proc.returncode == 0 and os.path.exists(image_path)
    except Exception:
        return False


def extract_review_frames(video_path: str, candidates: List[Dict], output_dir: str = "") -> List[Dict]:
    if not video_path or not os.path.exists(video_path):
        return candidates
    output_dir = output_dir or os.path.join(utils.temp_dir("subtitle_review_frames"), utils.md5(video_path))
    os.makedirs(output_dir, exist_ok=True)

    for cand in candidates:
        midpoint = (float(cand["start"]) + float(cand["end"])) / 2.0
        frame_path = os.path.join(output_dir, f"{cand['candidate_id']}.jpg")
        if os.path.exists(frame_path) or _extract_frame_ffmpeg(video_path, midpoint, frame_path):
            cand["frame_path"] = frame_path
    return candidates


def prepare_subtitle_review(video_path: str, subtitle_result: Dict, max_candidates: int = 20) -> Dict:
    subtitle_path = (
        subtitle_result.get("clean_subtitle_path")
        or subtitle_result.get("subtitle_path")
        or subtitle_result.get("original_subtitle_path")
        or ""
    )
    segments = subtitle_result.get("segments") or []
    candidates = detect_suspicious_groups(segments, max_candidates=max_candidates)
    candidates = extract_review_frames(video_path, candidates)

    paths = _derive_review_paths(subtitle_path or os.path.join(utils.temp_dir("subtitles"), "review"))
    return {
        "subtitle_result": subtitle_result,
        "prepared_subtitle_path": subtitle_path,
        "candidates": candidates,
        "overrides_path": paths["overrides"],
        "final_subtitle_path": paths["final_srt"],
        "final_segments_path": paths["final_segments"],
    }


def _write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def apply_review_overrides(subtitle_result: Dict, review_candidates: List[Dict], overrides: Dict[str, str]) -> Dict:
    original_segments = [dict(seg) for seg in (subtitle_result.get("segments") or [])]
    normalized = []
    for idx, seg in enumerate(original_segments, start=1):
        cur = dict(seg)
        cur["seg_id"] = cur.get("seg_id") or f"sub_{idx:04d}"
        cur["text"] = str(cur.get("text", "") or "").strip()
        if cur["text"]:
            normalized.append(cur)

    id_to_index = {seg["seg_id"]: idx for idx, seg in enumerate(normalized)}
    group_by_start: Dict[int, Dict] = {}
    review_records = []

    for cand in review_candidates:
        related_ids = [x for x in cand.get("related_segment_ids", []) if x in id_to_index]
        if not related_ids:
            continue
        idxs = sorted(id_to_index[x] for x in related_ids)
        start_idx = idxs[0]
        end_idx = idxs[-1]
        corrected_text = str(overrides.get(cand["candidate_id"], "") or "").strip() or cand["suggested_text"]
        group_by_start[start_idx] = {
            "end_idx": end_idx,
            "corrected_text": corrected_text,
            "candidate": cand,
        }
        review_records.append(
            {
                "candidate_id": cand["candidate_id"],
                "reason": cand["reason"],
                "reason_label": cand["reason_label"],
                "time_range": cand["time_range"],
                "context_text": cand["context_text"],
                "suggested_text": cand["suggested_text"],
                "final_text": corrected_text,
                "related_segment_ids": related_ids,
            }
        )

    final_segments: List[Dict] = []
    idx = 0
    while idx < len(normalized):
        if idx in group_by_start:
            group = group_by_start[idx]
            merged_items = normalized[idx : group["end_idx"] + 1]
            start = min(float(item.get("start", 0.0) or 0.0) for item in merged_items)
            end = max(float(item.get("end", start) or start) for item in merged_items)
            final_segments.append(
                {
                    "id": len(final_segments) + 1,
                    "seg_id": f"final_{len(final_segments) + 1:04d}",
                    "start": start,
                    "end": end,
                    "text": group["corrected_text"],
                    "source": "review_final",
                    "backend": merged_items[0].get("backend", ""),
                    "confidence": None,
                }
            )
            idx = group["end_idx"] + 1
            continue

        seg = normalized[idx]
        final_segments.append(
            {
                "id": len(final_segments) + 1,
                "seg_id": f"final_{len(final_segments) + 1:04d}",
                "start": float(seg.get("start", 0.0) or 0.0),
                "end": float(seg.get("end", 0.0) or 0.0),
                "text": seg["text"],
                "source": seg.get("source", "auto_clean"),
                "backend": seg.get("backend", ""),
                "confidence": seg.get("confidence"),
            }
        )
        idx += 1

    subtitle_path = (
        subtitle_result.get("clean_subtitle_path")
        or subtitle_result.get("subtitle_path")
        or subtitle_result.get("original_subtitle_path")
        or os.path.join(utils.temp_dir("subtitles"), "review.srt")
    )
    paths = _derive_review_paths(subtitle_path)

    _write_json(
        paths["overrides"],
        {
            "review_records": review_records,
            "final_subtitle_path": paths["final_srt"],
            "final_segments_path": paths["final_segments"],
        },
    )
    with open(paths["final_srt"], "w", encoding="utf-8") as f:
        f.write(_segments_to_srt(final_segments))
    _write_json(paths["final_segments"], final_segments)

    logger.info(
        "人工审核后的最终字幕已生成: final_srt={}, final_segments={}, reviewed={}",
        paths["final_srt"],
        paths["final_segments"],
        len(review_records),
    )

    return {
        "final_subtitle_path": paths["final_srt"],
        "final_segments_path": paths["final_segments"],
        "overrides_path": paths["overrides"],
        "final_segments": final_segments,
        "review_records": review_records,
    }
