import os
import re
from typing import Dict, List, Optional, Tuple

from loguru import logger


# ── Oral filler words to strip (Chinese) ──────────────────────────
# Common meaningless fillers in spoken Chinese subtitles.
ORAL_FILLERS_ZH = [
    "嗯嗯", "嗯", "啊啊", "啊", "呃", "额", "哦", "噢",
    "那个", "就是说", "就是", "然后呢", "然后",
    "对对对", "对对", "是吧", "你知道吗", "怎么说呢",
]
# Build a regex pattern – match fillers at word boundaries.
# Longer fillers first so "嗯嗯" is tried before "嗯".
_ORAL_FILLER_RE = re.compile(
    "|".join(re.escape(w) for w in sorted(ORAL_FILLERS_ZH, key=len, reverse=True))
)

# ── Speaker label patterns ────────────────────────────────────────
# Matches patterns like "[A]:" or "【说话人1】:" or "Speaker1:" at the
# beginning of a subtitle line.
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

# ASS/SSA Dialogue line regex
# Format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
ASS_DIALOGUE_RE = re.compile(
    r"Dialogue:\s*\d+,"
    r"(?P<sh>\d+):(?P<sm>\d{2}):(?P<ss>\d{2})\.(?P<scs>\d{2}),"
    r"(?P<eh>\d+):(?P<em>\d{2}):(?P<es>\d{2})\.(?P<ecs>\d{2}),"
    r"[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,"
    r"(?P<text>.+)"
)

# VTT timestamp regex (supports both . and , as ms separator)
VTT_TIME_RE = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2})[.,](?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2})[.,](?P<ems>\d{3})"
)


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
    """Parse ASS/SSA subtitle file into normalized segments.

    Handles standard ASS Dialogue lines. Override/drawing tags
    (e.g. {\\pos(...)}, {\\an8}) are stripped from the text.
    """
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
        # Strip ASS override tags like {\pos(320,50)}
        raw_text = re.sub(r"\{[^}]*\}", "", raw_text)
        # Replace \N and \n (ASS line breaks) with space
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
    """Parse WebVTT subtitle file into normalized segments.

    Handles standard WebVTT cues. HTML tags (e.g. <b>, <i>) and
    voice tags (e.g. <v Speaker>) are stripped.
    """
    if not filename or not os.path.isfile(filename):
        return []

    with open(filename, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")

    # Remove WEBVTT header and any metadata blocks
    # Split by double newlines to get cue blocks
    blocks = re.split(r"\n\s*\n", text.strip())
    segments: List[Dict] = []
    idx = 0

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        # Skip WEBVTT header block
        if lines[0].startswith("WEBVTT"):
            continue
        # Skip NOTE blocks
        if lines[0].startswith("NOTE"):
            continue
        # Skip STYLE blocks
        if lines[0].startswith("STYLE"):
            continue

        # Find the timestamp line
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

        # Text is everything after the timestamp line
        content_lines = lines[time_line_idx + 1:]
        raw_text = " ".join(content_lines).strip()
        # Strip HTML tags (e.g. <b>, </b>, <i>, <v Speaker>)
        raw_text = re.sub(r"<[^>]+>", "", raw_text)
        raw_text = raw_text.strip()
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
    """Auto-detect subtitle format and parse into normalized segments.

    Supports SRT, ASS/SSA, and WebVTT formats. Detection is based on
    file extension with content-based fallback.
    """
    if not filename or not os.path.isfile(filename):
        return []

    ext = os.path.splitext(filename)[1].lower()
    if ext in (".ass", ".ssa"):
        return parse_ass_file(filename)
    elif ext == ".vtt":
        return parse_vtt_file(filename)
    elif ext == ".srt":
        return parse_srt_file(filename)

    # Fallback: try to detect format from content
    with open(filename, "r", encoding="utf-8") as f:
        head = f.read(512)

    if "WEBVTT" in head:
        return parse_vtt_file(filename)
    if "[Script Info]" in head or "[V4+ Styles]" in head or "[V4 Styles]" in head:
        return parse_ass_file(filename)
    # Default to SRT
    return parse_srt_file(filename)


def _extract_speaker(text: str) -> Tuple[str, str]:
    """Extract speaker label from the beginning of subtitle text.

    Returns (speaker, remaining_text).  If no speaker label is found,
    returns ("", original_text).
    """
    if not text:
        return "", ""
    m = _SPEAKER_RE.match(text)
    if not m:
        return "", text
    speaker = (m.group("s1") or m.group("s2") or m.group("s3") or "").strip()
    remaining = text[m.end():].strip()
    return speaker, remaining


def _strip_oral_fillers(text: str) -> str:
    """Remove oral filler words from text (optional cleaning step)."""
    if not text:
        return ""
    cleaned = _ORAL_FILLER_RE.sub("", text)
    # Collapse multiple spaces introduced by removal
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[，。！？、,.!?]+|[，。！？、,.!?]+$", "", text)
    return text.strip()


PUNCT_END = set("。！？!?；;…")


def normalize_segments(
    segments: List[Dict],
    max_chars: int = 42,
    max_duration: float = 8.0,
    min_duration: float = 0.35,
    merge_gap: float = 0.45,
    strip_fillers: bool = True,
    detect_speaker: bool = True,
) -> List[Dict]:
    """Normalize subtitle segments.

    Parameters
    ----------
    segments : list
        Raw parsed subtitle segments.
    max_chars : int
        Max characters per segment before forcing a split.
    max_duration : float
        Max duration (seconds) per segment.
    min_duration : float
        Minimum duration; shorter segments are extended.
    merge_gap : float
        Adjacent segments with gap <= this value may be merged.
    strip_fillers : bool
        If True, remove common oral filler words (e.g. 嗯, 那个).
    detect_speaker : bool
        If True, extract speaker labels from text (e.g. [A]: ...).
    """
    cleaned: List[Dict] = []
    for item in segments or []:
        raw_text = item.get("text", "")

        # Speaker extraction (optional)
        speaker = ""
        if detect_speaker:
            speaker, raw_text = _extract_speaker(raw_text)

        text = _clean_text(raw_text)

        # Oral filler removal (optional)
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
        # Propagate confidence from ASR results if present
        if "confidence" in item:
            seg_dict["confidence"] = float(item["confidence"])
        cleaned.append(seg_dict)

    if not cleaned:
        return []

    merged: List[Dict] = []
    current = cleaned[0].copy()
    for item in cleaned[1:]:
        gap = item["start"] - current["end"]
        current_len = len(current["text"])
        current_duration = current["end"] - current["start"]
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
            current["text"] = f"{current['text']} {item['text']}".strip()
            current["end"] = max(current["end"], item["end"])
        else:
            merged.append(current)
            current = item.copy()
    merged.append(current)

    normalized: List[Dict] = []
    for idx, item in enumerate(merged, start=1):
        duration = item["end"] - item["start"]
        if duration < min_duration:
            item["end"] = item["start"] + min_duration
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
            f.write(f"{seg.get('text','').strip()}\n\n")
    return output_file
