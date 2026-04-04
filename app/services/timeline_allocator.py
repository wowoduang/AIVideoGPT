from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from loguru import logger

_OVERFLOW_WARN_SECONDS = 0.5
_OVERFLOW_ERROR_SECONDS = 1.5


def estimate_char_budget(
    duration: float,
    chars_per_second: float = 4.0,
    reserve_ratio: float = 0.85,
    min_chars: int = 8,
) -> int:
    """Estimate narration character budget for a segment."""
    duration = max(float(duration or 0.0), 0.1)
    cps = max(float(chars_per_second or 0.0), 1.0)
    reserve = min(max(float(reserve_ratio or 0.0), 0.4), 1.0)
    return max(int(min_chars), int(duration * cps * reserve))


def fit_check(
    narration: str,
    duration: float,
    chars_per_second: float = 4.0,
    reserve_ratio: float = 0.85,
) -> Dict:
    """Check whether narration text fits the slot duration."""
    text = (narration or "").strip()
    budget = estimate_char_budget(duration, chars_per_second, reserve_ratio)
    actual = len(text)
    overflow = max(actual - budget, 0)
    overflow_seconds = overflow / max(chars_per_second, 1e-6)

    if overflow <= 0:
        severity = "ok"
    elif overflow_seconds < _OVERFLOW_WARN_SECONDS:
        severity = "warn"
    elif overflow_seconds >= _OVERFLOW_ERROR_SECONDS:
        severity = "error"
    else:
        severity = "warn"

    return {
        "fits": overflow <= 0,
        "budget": budget,
        "actual": actual,
        "overflow": overflow,
        "overflow_seconds": round(overflow_seconds, 3),
        "severity": severity,
    }


def trim_text_to_budget(text: str, budget: int) -> str:
    """Trim text to fit within char budget, preferring punctuation boundaries."""
    raw = (text or "").strip()
    if len(raw) <= budget:
        return raw

    budget = max(int(budget), 1)
    hard = raw[:budget]

    for sep in ("。", "！", "？", "，", ";", ",", " "):
        idx = hard.rfind(sep)
        if idx >= max(6, int(budget * 0.6)):
            return hard[: idx + 1].strip()

    return hard.rstrip("，,；;、 ") + "。"


def apply_timeline_budget(
    items: List[Dict],
    auto_trim: bool = True,
    chars_per_second: float = 4.0,
    reserve_ratio: float = 0.85,
) -> List[Dict]:
    """
    Compatibility function required by script_fallback.py.

    Adds:
    - char_budget
    - fit_check

    And optionally trims narration to fit.
    """
    result: List[Dict] = []
    warn_count = 0
    error_count = 0

    for item in items or []:
        new_item = dict(item)

        duration = float(item.get("duration", 0) or 0)
        if duration <= 0:
            start = float(item.get("start", 0) or 0)
            end = float(item.get("end", 0) or 0)
            if end > start:
                duration = end - start
            else:
                duration = 1.0

        budget = estimate_char_budget(duration, chars_per_second, reserve_ratio)
        new_item["char_budget"] = budget

        narration = str(item.get("narration", "") or "").strip()
        check = fit_check(
            narration,
            duration,
            chars_per_second=chars_per_second,
            reserve_ratio=reserve_ratio,
        )

        if auto_trim and not check["fits"]:
            trimmed = trim_text_to_budget(narration, budget)
            new_item["narration"] = trimmed
            check = fit_check(
                trimmed,
                duration,
                chars_per_second=chars_per_second,
                reserve_ratio=reserve_ratio,
            )
        else:
            new_item["narration"] = narration

        new_item["fit_check"] = check

        if check["severity"] == "warn":
            warn_count += 1
        elif check["severity"] == "error":
            error_count += 1
            logger.warning(
                "严重超预算: scene_id={}, budget={}, actual={}, overflow_seconds={}",
                item.get("scene_id", "unknown"),
                check["budget"],
                check["actual"],
                check["overflow_seconds"],
            )

        result.append(new_item)

    if warn_count or error_count:
        logger.info(
            "时间线预算检查: {} 个轻微溢出, {} 个严重溢出",
            warn_count,
            error_count,
        )

    return result


def allocate_script_budgets(
    items: List[Dict],
    chars_per_second: float = 4.0,
    reserve_ratio: float = 0.85,
) -> List[Dict]:
    """Attach char_budget / fit_check metadata onto final script items."""
    out: List[Dict] = []
    for item in items or []:
        cloned = dict(item)
        start = float(cloned.get("start", 0.0) or 0.0)
        end = float(cloned.get("end", 0.0) or 0.0)

        if end <= start and cloned.get("duration") is not None:
            duration = float(cloned.get("duration") or 0.0)
        else:
            duration = max(end - start, 0.1)

        budget = estimate_char_budget(duration, chars_per_second, reserve_ratio)
        cloned["char_budget"] = budget
        cloned["fit_check"] = fit_check(
            cloned.get("narration", ""),
            duration,
            chars_per_second=chars_per_second,
            reserve_ratio=reserve_ratio,
        )
        out.append(cloned)
    return out


def _actual_duration_seconds(item: Dict) -> Optional[float]:
    for key in ("audio_duration", "tts_duration", "actual_audio_duration"):
        value = item.get(key)
        if value is None:
            continue
        try:
            value = float(value)
            if value > 0:
                return value
        except Exception:
            continue
    return None


def apply_post_tts_fit(
    items: Iterable[Dict],
    chars_per_second: float = 4.0,
    reserve_ratio: float = 0.85,
) -> List[Dict]:
    """
    Second-pass fit check after TTS returns real audio duration.
    This does not regenerate text; it marks segments that should be retried.
    """
    out: List[Dict] = []
    for item in items or []:
        cloned = dict(item)
        start = float(cloned.get("start", 0.0) or 0.0)
        end = float(cloned.get("end", 0.0) or 0.0)
        slot_duration = max(end - start, 0.1)

        budget = cloned.get("char_budget") or estimate_char_budget(
            slot_duration, chars_per_second, reserve_ratio
        )
        actual_audio = _actual_duration_seconds(cloned)

        if actual_audio is None:
            cloned["post_tts_fit"] = fit_check(
                cloned.get("narration", ""),
                slot_duration,
                chars_per_second=chars_per_second,
                reserve_ratio=reserve_ratio,
            )
            out.append(cloned)
            continue

        overflow_seconds = max(actual_audio - slot_duration, 0.0)
        if overflow_seconds <= 0:
            severity = "ok"
        elif overflow_seconds < _OVERFLOW_WARN_SECONDS:
            severity = "warn"
        elif overflow_seconds >= _OVERFLOW_ERROR_SECONDS:
            severity = "error"
        else:
            severity = "warn"

        cloned["post_tts_fit"] = {
            "fits": overflow_seconds <= 0,
            "budget": budget,
            "actual": len((cloned.get("narration") or "").strip()),
            "overflow": max(len((cloned.get("narration") or "").strip()) - int(budget), 0),
            "overflow_seconds": round(overflow_seconds, 3),
            "severity": severity,
            "slot_duration": round(slot_duration, 3),
            "audio_duration": round(actual_audio, 3),
        }
        out.append(cloned)

    return out