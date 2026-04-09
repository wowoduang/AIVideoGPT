from __future__ import annotations

from typing import Dict, List

from app.utils import utils


def is_composition_plan(payload) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("segments"), list)


def _build_picture_fallback(item: Dict, idx: int) -> str:
    picture = str(item.get("picture", "") or "").strip()
    if picture:
        return picture

    for field in ("scene_summary", "subtitle_text", "narration_text"):
        value = str(item.get(field, "") or "").strip()
        if value:
            return value[:80]

    reasons = [str(reason).strip() for reason in (item.get("selection_reason") or []) if str(reason).strip()]
    if reasons:
        return f"高光画面：{' / '.join(reasons[:2])}"[:80]

    source_id = (
        str(item.get("source_scene_id", "") or "").strip()
        or str(item.get("source_clip_id", "") or "").strip()
        or str(item.get("segment_id", "") or "").strip()
    )
    if source_id:
        return f"高光片段 {source_id}"[:80]

    return f"高光片段 {idx}"


def composition_plan_to_script_items(plan: Dict) -> List[Dict]:
    segments = list(plan.get("segments") or [])
    result: List[Dict] = []

    for idx, item in enumerate(segments, start=1):
        video_start = float(item.get("video_start", 0.0) or 0.0)
        video_end = float(item.get("video_end", video_start) or video_start)
        if video_end <= video_start:
            video_end = video_start + 0.5

        audio_mode = str(item.get("audio_mode", "raw") or "raw").strip().lower()
        narration_text = str(item.get("narration_text", "") or "").strip()

        if audio_mode == "raw":
            ost = 1
        elif audio_mode == "mute" and narration_text:
            ost = 0
        elif audio_mode in {"ducked_raw", "tts", "mute"} and not narration_text:
            # Fallback to pure raw to avoid invalid empty-narration OST=2 segments.
            ost = 1
        else:
            ost = 2
        raw_audio_keep = bool(item.get("raw_audio_worthy")) or audio_mode in {"raw", "ducked_raw"} or ost == 1

        result.append(
            {
                "_id": idx,
                "segment_id": item.get("segment_id") or f"seg_{idx:04d}",
                "timestamp": f"{utils.format_time(video_start)}-{utils.format_time(video_end)}",
                "start": round(video_start, 3),
                "end": round(video_end, 3),
                "duration": round(max(video_end - video_start, 0.5), 3),
                "picture": _build_picture_fallback(item, idx),
                "narration": narration_text,
                "OST": ost,
                "highlight_id": item.get("source_clip_id") or f"clip_{idx:04d}",
                "highlight_reasons": list(item.get("selection_reason") or []),
                "llm_highlight_selected": True,
                "llm_raw_voice_keep": raw_audio_keep,
                "raw_voice_retain_suggestion": raw_audio_keep,
                "fit_check": {
                    "status": "composition_plan",
                    "target_chars": 0,
                    "actual_chars": len(narration_text),
                },
                "composition_audio_mode": audio_mode,
                "composition_audio_strategy": str(item.get("audio_strategy", "") or ""),
                "composition_timeline_start": item.get("timeline_start"),
                "composition_timeline_end": item.get("timeline_end"),
                "composition_narration_audio_path": item.get("narration_audio_path", ""),
                "composition_clip_source": str(item.get("clip_source", "") or ""),
                "composition_source_scene_id": str(item.get("source_scene_id", "") or ""),
                "composition_trim_strategy": str(item.get("trim_strategy", "") or ""),
                "composition_original_duration": item.get("original_duration"),
                "composition_planned_duration": item.get("planned_duration"),
            }
        )

    return result
