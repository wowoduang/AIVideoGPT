import os
import re
from typing import Dict, List, Optional, Tuple

from loguru import logger


# ── Oral filler words to strip (Chinese) ──────────────────────────
ORAL_FILLERS_ZH = [
    "嗯嗯", "嗯", "啊啊", "啊", "呃", "额", "哦", "噢",
    "那个", "就是说", "就是", "然后呢", "然后",
    "对对对", "对对", "是吧", "你知道吗", "怎么说呢",
]
_ORAL_FILLER_RE = re.compile(
    "|".join(re.escape(w) for w in sorted(ORAL_FILLERS_ZH, key=len, reverse=True))
)

# ── Speaker label patterns ────────────────────────────────────────
_SPEAKER_RE = re.compile(
    r"^\s*"
    r"(?:"
    r"\[(?P<s1>[^\]]+)\]"
    r"|【(?P<s2>[^】]+)】"
    r"|(?P<s3>[A-Za-z\u4e00-\u9fff]+\d*)"
    r")"
    r"\s*[:：]\s*"
)

SRT_TIME_RE = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
)
ASS_DIALOGUE_RE = re.compile(
    r"Dialogue:\s*\d+,"
    r"(?P<sh>\d+):(?P<sm>\d{2}):(?P<ss>\d{2})\.(?P<scs>\d{2}),"
    r"(?P<eh>\d+):(?P<em>\d{2}):(?P<es>\d{2})\.(?P<ecs>\d{2}),"
    r"[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,"
    r"(?P<text>.+)"
)
VTT_TIME_RE = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2})[.,](?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2})[.,](?P<ems>\d{3})"
)

PUNCT_END = set("。！？!?；;…")
_MAJOR_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;…])\s*")
_MINOR_SENTENCE_SPLIT_RE = re.compile(r"(?<=[，,、：:])\s*")


def srt_time_to_seconds(value: str) -> float:
    h, m, rest = value.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def seconds_to_srt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    seconds -= h * 3600
    m = int(seconds // 60)
    seconds -= m * 60
    s = int(seconds)
    ms = int(round((seconds - s) * 1000))
    if ms == 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_file(filename: str) -> List[Dict]:
    if not filename or not os.path.isfile(filename):
        return []

    with open(filename, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")

    blocks = re.split(r"\n\s*\n", text.strip())
    segments: List[Dict] = []
    for idx, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue

        time_line = lines[1] if lines[0].isdigit() else lines[0]
        match = SRT_TIME_RE.search(time_line)
        if not match:
            continue

        start = srt_time_to_seconds(
            f"{match.group('sh')}:{match.group('sm')}:{match.group('ss')},{match.group('sms')}"
        )
        end = srt_time_to_seconds(
            f"{match.group('eh')}:{match.group('em')}:{match.group('es')},{match.group('ems')}"
        )
        content_start = 2 if lines[0].isdigit() else 1
        text_value = " ".join(lines[content_start:]).strip()
        segments.append({
            "seg_id": f"sub_{idx:04d}",
            "start": start,
            "end": max(end, start + 0.2),
            "text": text_value,
            "source": "srt",
        })
    return segments


def parse_ass_file(filename: str) -> List[Dict]:
    if not filename or not os.path.isfile(filename):
        return []

    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()

    segments: List[Dict] = []
    idx = 0
    for line in text.splitlines():
        match = ASS_DIALOGUE_RE.match(line.strip())
        if not match:
            continue

        start = (
            int(match.group("sh")) * 3600
            + int(match.group("sm")) * 60
            + int(match.group("ss"))
            + int(match.group("scs")) / 100.0
        )
        end = (
            int(match.group("eh")) * 3600
            + int(match.group("em")) * 60
            + int(match.group("es"))
            + int(match.group("ecs")) / 100.0
        )

        raw_text = match.group("text")
        raw_text = re.sub(r"\{[^}]*\}", "", raw_text)
        raw_text = raw_text.replace("\\N", " ").replace("\\n", " ")
        raw_text = raw_text.strip()
        if not raw_text:
            continue

        idx += 1
        segments.append({
            "seg_id": f"sub_{idx:04d}",
            "start": start,
            "end": max(end, start + 0.2),
            "text": raw_text,
            "source": "ass",
        })
    logger.info(f"ASS字幕解析完成: {len(segments)} 段")
    return segments


def parse_vtt_file(filename: str) -> List[Dict]:
    if not filename or not os.path.isfile(filename):
        return []

    with open(filename, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")

    blocks = re.split(r"\n\s*\n", text.strip())
    segments: List[Dict] = []
    idx = 0

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE") or lines[0].startswith("STYLE"):
            continue

        time_line_idx = -1
        for i, line in enumerate(lines):
            if VTT_TIME_RE.search(line):
                time_line_idx = i
                break
        if time_line_idx < 0:
            continue

        match = VTT_TIME_RE.search(lines[time_line_idx])
        if not match:
            continue

        start = srt_time_to_seconds(
            f"{match.group('sh')}:{match.group('sm')}:{match.group('ss')},{match.group('sms')}"
        )
        end = srt_time_to_seconds(
            f"{match.group('eh')}:{match.group('em')}:{match.group('es')},{match.group('ems')}"
        )

        raw_text = " ".join(lines[time_line_idx + 1:]).strip()
        raw_text = re.sub(r"<[^>]+>", "", raw_text).strip()
        if not raw_text:
            continue

        idx += 1
        segments.append({
            "seg_id": f"sub_{idx:04d}",
            "start": start,
            "end": max(end, start + 0.2),
            "text": raw_text,
            "source": "vtt",
        })
    logger.info(f"VTT字幕解析完成: {len(segments)} 段")
    return segments


def parse_subtitle_file(filename: str) -> List[Dict]:
    if not filename or not os.path.isfile(filename):
        return []

    ext = os.path.splitext(filename)[1].lower()
    if ext in (".ass", ".ssa"):
        return parse_ass_file(filename)
    if ext == ".vtt":
        return parse_vtt_file(filename)
    if ext == ".srt":
        return parse_srt_file(filename)

    with open(filename, "r", encoding="utf-8") as f:
        head = f.read(512)

    if "WEBVTT" in head:
        return parse_vtt_file(filename)
    if "[Script Info]" in head or "[V4+ Styles]" in head or "[V4 Styles]" in head:
        return parse_ass_file(filename)
    return parse_srt_file(filename)


def _extract_speaker(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    m = _SPEAKER_RE.match(text)
    if not m:
        return "", text
    speaker = (m.group("s1") or m.group("s2") or m.group("s3") or "").strip()
    remaining = text[m.end():].strip()
    return speaker, remaining


def _strip_oral_fillers(text: str) -> str:
    if not text:
        return ""
    cleaned = _ORAL_FILLER_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[，。！？、,.!?]+|[，。！？、,.!?]+$", "", text)
    return text.strip()


def _text_units(text: str) -> List[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    major = [x.strip() for x in _MAJOR_SENTENCE_SPLIT_RE.split(cleaned) if x.strip()]
    if len(major) > 1:
        return major

    minor = [x.strip() for x in _MINOR_SENTENCE_SPLIT_RE.split(cleaned) if x.strip()]
    if len(minor) > 1:
        return minor

    if len(cleaned) <= 16:
        return [cleaned]

    # 最后兜底：按长度切，避免整段超长字幕继续保留为一条。
    step = 16 if len(cleaned) > 32 else 12
    return [cleaned[i:i + step].strip() for i in range(0, len(cleaned), step) if cleaned[i:i + step].strip()]


def _pack_text_units(units: List[str], max_chars: int) -> List[str]:
    if not units:
        return []
    packed: List[str] = []
    current = units[0]
    for unit in units[1:]:
        candidate = f"{current}{unit}" if current and current[-1] in PUNCT_END else f"{current} {unit}"
        candidate = candidate.strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            packed.append(current.strip())
            current = unit
    if current:
        packed.append(current.strip())
    return packed


def _split_long_segment(item: Dict, max_chars: int, max_duration: float, min_duration: float) -> List[Dict]:
    text = _clean_text(item.get("text", ""))
    if not text:
        return []

    start = float(item.get("start", 0.0) or 0.0)
    end = float(item.get("end", start + 0.5) or (start + 0.5))
    duration = max(end - start, min_duration)
    should_split = len(text) > max_chars or duration > max_duration
    if not should_split:
        return [dict(item, text=text, start=start, end=end)]

    units = _text_units(text)
    packed = _pack_text_units(units, max_chars=max_chars)
    if len(packed) <= 1 and len(text) > max_chars:
        packed = [text[i:i + max_chars].strip() for i in range(0, len(text), max_chars) if text[i:i + max_chars].strip()]
    if len(packed) <= 1 and duration <= max_duration:
        return [dict(item, text=text, start=start, end=end)]

    total_weight = sum(max(len(x.replace(" ", "")), 1) for x in packed)
    if total_weight <= 0:
        total_weight = len(packed)

    cursor = start
    out: List[Dict] = []
    for idx, piece in enumerate(packed, start=1):
        weight = max(len(piece.replace(" ", "")), 1)
        if idx == len(packed):
            piece_end = end
        else:
            piece_duration = max(duration * (weight / total_weight), min_duration)
            remaining_min = min_duration * (len(packed) - idx)
            piece_end = min(end - remaining_min, cursor + piece_duration)
        piece_end = max(piece_end, cursor + min_duration)
        out.append({
            **item,
            "seg_id": f"{item.get('seg_id') or 'sub'}_{idx:02d}",
            "start": round(cursor, 3),
            "end": round(piece_end, 3),
            "text": piece.strip(),
        })
        cursor = piece_end

    # 纠正最后一段结束时间和可能的倒挂。
    out[-1]["end"] = round(max(end, float(out[-1]["start"]) + min_duration), 3)
    fixed: List[Dict] = []
    for idx, seg in enumerate(out, start=1):
        cur = dict(seg)
        if idx > 1:
            prev = fixed[-1]
            cur["start"] = round(float(prev["end"]), 3)
        if float(cur["end"]) <= float(cur["start"]):
            cur["end"] = round(float(cur["start"]) + min_duration, 3)
        fixed.append(cur)
    return fixed


def normalize_segments(
    segments: List[Dict],
    max_chars: int = 42,
    max_duration: float = 8.0,
    min_duration: float = 0.35,
    merge_gap: float = 0.45,
    strip_fillers: bool = True,
    detect_speaker: bool = True,
) -> List[Dict]:
    cleaned: List[Dict] = []
    for item in segments or []:
        raw_text = item.get("text", "")

        speaker = ""
        if detect_speaker:
            speaker, raw_text = _extract_speaker(raw_text)

        text = _clean_text(raw_text)
        if strip_fillers and text:
            text = _strip_oral_fillers(text)
            text = _clean_text(text)
        if not text:
            continue

        start = float(item.get("start", 0) or 0)
        end = float(item.get("end", start + 0.5) or (start + 0.5))
        if end <= start:
            end = start + 0.5

        seg_dict: Dict = {
            "seg_id": item.get("seg_id") or f"sub_{len(cleaned)+1:04d}",
            "start": start,
            "end": end,
            "text": text,
            "source": item.get("source", "subtitle"),
        }
        if speaker:
            seg_dict["speaker"] = speaker
        if "confidence" in item:
            try:
                seg_dict["confidence"] = float(item["confidence"])
            except Exception:
                seg_dict["confidence"] = item["confidence"]

        cleaned.extend(_split_long_segment(seg_dict, max_chars=max_chars, max_duration=max_duration, min_duration=min_duration))

    if not cleaned:
        return []

    merged: List[Dict] = []
    current = cleaned[0].copy()
    for item in cleaned[1:]:
        gap = float(item["start"]) - float(current["end"])
        current_len = len(current["text"])
        current_duration = float(current["end"]) - float(current["start"])
        should_merge = (
            gap <= merge_gap
            and current_len < max_chars
            and current_duration < max_duration
            and (
                len(item["text"]) < max_chars // 2
                or current["text"][-1] not in PUNCT_END
            )
        )
        if should_merge:
            candidate_text = f"{current['text']} {item['text']}".strip()
            candidate_duration = float(item["end"]) - float(current["start"])
            if len(candidate_text) <= max_chars and candidate_duration <= max_duration:
                current["text"] = candidate_text
                current["end"] = max(float(current["end"]), float(item["end"]))
                continue

        merged.append(current)
        current = item.copy()
    merged.append(current)

    normalized: List[Dict] = []
    for idx, item in enumerate(merged, start=1):
        duration = float(item["end"]) - float(item["start"])
        if duration < min_duration:
            item["end"] = float(item["start"]) + min_duration
        item["text"] = _clean_text(item["text"])
        item["seg_id"] = f"sub_{idx:04d}"
        normalized.append(item)

    logger.info(f"字幕标准化完成: {len(segments or [])} -> {len(normalized)} 段")
    return normalized


def dump_segments_to_srt(segments: List[Dict], output_file: str) -> Optional[str]:
    if not output_file:
        return None
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments or [], start=1):
            f.write(f"{idx}\n")
            f.write(f"{seconds_to_srt_time(seg['start'])} --> {seconds_to_srt_time(seg['end'])}\n")
            f.write(f"{seg.get('text', '').strip()}\n\n")
    return output_file
