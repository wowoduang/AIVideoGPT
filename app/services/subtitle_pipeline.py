from __future__ import annotations

import json
import os
import shutil
from typing import Dict, List, Tuple

from loguru import logger

from app.services import subtitle
from app.services.subtitle_normalizer import dump_segments_to_srt, normalize_segments, parse_subtitle_file
from app.utils import utils


CANDIDATE_SUBTITLE_ATTRS = [
    "subtitle_path",
    "subtitle_file",
    "subtitle_origin_path",
    "video_subtitle_path",
]

AUTO_SUBTITLE_CACHE_VERSION = "2026-04-04-review-flow-v1"


def resolve_explicit_subtitle_path(params=None, session_state=None) -> str:
    if params is not None:
        for attr in CANDIDATE_SUBTITLE_ATTRS:
            value = getattr(params, attr, None)
            if value:
                return value
    if session_state:
        for attr in CANDIDATE_SUBTITLE_ATTRS:
            value = session_state.get(attr)
            if value:
                return value
    return ""


def _detect_subtitle_source(path: str) -> str:
    ext = os.path.splitext(path or "")[1].lower()
    if ext in {".ass", ".ssa"}:
        return "external_ass"
    if ext == ".vtt":
        return "external_vtt"
    if ext == ".srt":
        return "external_srt"
    return "external_subtitle"


def _safe_mtime(path: str) -> str:
    try:
        return str(os.path.getmtime(path))
    except Exception:
        return "0"


def _safe_size(path: str) -> str:
    try:
        return str(os.path.getsize(path))
    except Exception:
        return "0"


def _derive_family_paths(base_srt_path: str) -> Dict[str, str]:
    root, ext = os.path.splitext(base_srt_path)
    if not ext:
        ext = ".srt"
        base_srt_path = root + ext
    return {
        "main": base_srt_path,
        "raw": f"{root}_raw.srt",
        "clean": f"{root}_clean.srt",
        "segments": f"{root}_segments.json",
    }


def _backend_cache_key(backend_override: str = "") -> str:
    value = str(backend_override or getattr(subtitle, "CURRENT_BACKEND", "default")).strip().lower()
    if "sensevoice" in value:
        return "sensevoice"
    if "whisper" in value:
        return "faster-whisper"
    if "funasr" in value or "paraformer" in value:
        return "funasr"
    return value or "default"


def _build_generated_subtitle_paths(video_path: str, backend_override: str = "") -> Tuple[str, str, str]:
    signature = "|".join(
        [
            os.path.abspath(video_path),
            _safe_mtime(video_path),
            _safe_size(video_path),
            f"backend={_backend_cache_key(backend_override)}",
            f"cache_version={AUTO_SUBTITLE_CACHE_VERSION}",
        ]
    )
    video_hash = utils.md5(signature)

    subtitle_dir = utils.temp_dir("subtitles")
    os.makedirs(subtitle_dir, exist_ok=True)
    temp_path = os.path.join(subtitle_dir, f"{video_hash}.srt")

    persistent_dir = utils.subtitle_dir()
    os.makedirs(persistent_dir, exist_ok=True)

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    safe_video_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in video_name).strip("_") or "video"
    persistent_name = f"{safe_video_name}__{_backend_cache_key(backend_override)}__auto_{video_hash[:12]}.srt"
    persistent_path = os.path.join(persistent_dir, persistent_name)
    return video_hash, temp_path, persistent_path


def _copy_if_exists(src: str, dst: str) -> str:
    if not src or not os.path.exists(src):
        return ""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def _persist_generated_family(temp_main_path: str, persistent_main_path: str) -> Dict[str, str]:
    temp_family = _derive_family_paths(temp_main_path)
    persistent_family = _derive_family_paths(persistent_main_path)
    return {
        "main": _copy_if_exists(temp_family["main"], persistent_family["main"]),
        "raw": _copy_if_exists(temp_family["raw"], persistent_family["raw"]),
        "clean": _copy_if_exists(temp_family["clean"], persistent_family["clean"]),
        "segments": _copy_if_exists(temp_family["segments"], persistent_family["segments"]),
    }


def _load_segments_json(path: str) -> List[Dict]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning(f"读取 subtitle_segments.json 失败: {exc}")
        return []

    if not isinstance(data, list):
        return []

    cleaned: List[Dict] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or "").strip()
        if not text:
            continue
        start = float(item.get("start", 0.0) or 0.0)
        end = float(item.get("end", start) or start)
        if end <= start:
            end = start + 0.5
        cleaned.append(
            {
                "seg_id": item.get("seg_id") or item.get("id") or f"sub_{idx:04d}",
                "start": start,
                "end": end,
                "text": text,
                "source": item.get("source", "subtitle_segments_json"),
                "backend": item.get("backend", ""),
                "confidence": item.get("confidence"),
            }
        )
    return cleaned


def _ensure_seg_ids(segments: List[Dict]) -> List[Dict]:
    fixed = []
    for idx, item in enumerate(segments or [], start=1):
        cur = dict(item)
        cur["seg_id"] = cur.get("seg_id") or f"sub_{idx:04d}"
        fixed.append(cur)
    return fixed


def _write_clean_sidecars_for_explicit(subtitle_path: str, normalized: List[Dict]):
    family = _derive_family_paths(subtitle_path)
    clean_path = family["clean"]
    segments_path = family["segments"]

    try:
        dump_segments_to_srt(normalized, clean_path)
    except Exception as exc:
        logger.warning(f"写入 clean_srt 失败: {exc}")

    try:
        payload = []
        for idx, seg in enumerate(normalized, start=1):
            payload.append(
                {
                    "id": idx,
                    "seg_id": seg.get("seg_id") or f"sub_{idx:04d}",
                    "start": float(seg.get("start", 0.0) or 0.0),
                    "end": float(seg.get("end", 0.0) or 0.0),
                    "text": str(seg.get("text", "") or ""),
                    "source": seg.get("source", "external_clean"),
                    "backend": seg.get("backend", ""),
                    "confidence": seg.get("confidence"),
                }
            )
        os.makedirs(os.path.dirname(segments_path), exist_ok=True)
        with open(segments_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning(f"写入 subtitle_segments.json 失败: {exc}")

    return {
        "clean": clean_path if os.path.exists(clean_path) else "",
        "segments": segments_path if os.path.exists(segments_path) else "",
    }


def build_subtitle_segments(
    video_path: str,
    explicit_subtitle_path: str = "",
    regenerate: bool = False,
    backend_override: str = "",
) -> Dict:
    subtitle_path = explicit_subtitle_path or ""
    source = "none"
    error = ""

    original_subtitle_path = ""
    raw_subtitle_path = ""
    clean_subtitle_path = ""
    subtitle_segments_path = ""
    generated_temp_path = ""
    generated_saved_path = ""

    if subtitle_path and os.path.exists(subtitle_path):
        original_subtitle_path = subtitle_path
        source = _detect_subtitle_source(subtitle_path)
        family = _derive_family_paths(subtitle_path)
        raw_subtitle_path = family["raw"] if os.path.exists(family["raw"]) else ""
        clean_subtitle_path = family["clean"] if os.path.exists(family["clean"]) else ""
        subtitle_segments_path = family["segments"] if os.path.exists(family["segments"]) else ""
        logger.info(f"使用显式字幕: {subtitle_path} (format={source})")
    else:
        cache_hash, temp_path, persistent_path = _build_generated_subtitle_paths(video_path, backend_override=backend_override)
        generated_temp_path = temp_path

        temp_family = _derive_family_paths(temp_path)
        persistent_family = _derive_family_paths(persistent_path)

        selected_main = ""
        if not regenerate:
            if os.path.exists(persistent_family["main"]):
                selected_main = persistent_family["main"]
                logger.info(
                    f"检测到已保存的自动字幕，直接复用: {selected_main} "
                    f"(cache_hash={cache_hash[:12]}, backend={_backend_cache_key(backend_override)}, cache_version={AUTO_SUBTITLE_CACHE_VERSION})"
                )
            elif os.path.exists(temp_family["main"]):
                persisted = _persist_generated_family(temp_family["main"], persistent_family["main"])
                selected_main = persisted["main"] or temp_family["main"]
                logger.info(
                    f"检测到缓存字幕，直接复用: {selected_main} "
                    f"(cache_hash={cache_hash[:12]}, backend={_backend_cache_key(backend_override)}, cache_version={AUTO_SUBTITLE_CACHE_VERSION})"
                )

        if not selected_main:
            logger.info(
                "未检测到可复用的自动字幕，开始从视频自动生成字幕 "
                f"(regenerate={regenerate}, backend={_backend_cache_key(backend_override)}, cache_version={AUTO_SUBTITLE_CACHE_VERSION}, cache_hash={cache_hash[:12]})"
            )
            generated = subtitle.extract_audio_and_create_subtitle(
                video_file=video_path,
                subtitle_file=temp_path,
                backend_override=backend_override,
            )
            if generated and os.path.exists(generated):
                persisted = _persist_generated_family(generated, persistent_family["main"])
                selected_main = persisted["main"] or generated
            else:
                error = "auto_subtitle_failed"

        original_subtitle_path = selected_main
        source = "generated_srt" if original_subtitle_path and os.path.exists(original_subtitle_path) else "none"

        raw_subtitle_path = persistent_family["raw"] if os.path.exists(persistent_family["raw"]) else (
            temp_family["raw"] if os.path.exists(temp_family["raw"]) else ""
        )
        clean_subtitle_path = persistent_family["clean"] if os.path.exists(persistent_family["clean"]) else (
            temp_family["clean"] if os.path.exists(temp_family["clean"]) else ""
        )
        subtitle_segments_path = persistent_family["segments"] if os.path.exists(persistent_family["segments"]) else (
            temp_family["segments"] if os.path.exists(temp_family["segments"]) else ""
        )
        generated_saved_path = persistent_family["main"] if os.path.exists(persistent_family["main"]) else ""

    preferred_subtitle_path = clean_subtitle_path or original_subtitle_path

    segments = _load_segments_json(subtitle_segments_path)
    if not segments and preferred_subtitle_path and os.path.exists(preferred_subtitle_path):
        parsed = parse_subtitle_file(preferred_subtitle_path)
        normalized = normalize_segments(parsed)
        segments = _ensure_seg_ids(normalized)

        if original_subtitle_path and source.startswith("external"):
            sidecars = _write_clean_sidecars_for_explicit(original_subtitle_path, segments)
            clean_subtitle_path = sidecars.get("clean") or clean_subtitle_path
            subtitle_segments_path = sidecars.get("segments") or subtitle_segments_path
            preferred_subtitle_path = clean_subtitle_path or preferred_subtitle_path
        else:
            try:
                if clean_subtitle_path:
                    dump_segments_to_srt(segments, clean_subtitle_path)
                if original_subtitle_path and original_subtitle_path.lower().endswith(".srt"):
                    dump_segments_to_srt(segments, original_subtitle_path)
            except Exception as exc:
                logger.warning(f"回写 clean_srt 失败: {exc}")

    if not segments and not error and source == "generated_srt":
        error = "empty_subtitle_segments"

    logger.info(
        "字幕流水线完成: source={}, backend={}, regenerate={}, segments={}, subtitle_path={}",
        source,
        _backend_cache_key(backend_override),
        regenerate,
        len(segments),
        preferred_subtitle_path or "NONE",
    )

    return {
        "subtitle_path": preferred_subtitle_path if preferred_subtitle_path and os.path.exists(preferred_subtitle_path) else "",
        "original_subtitle_path": original_subtitle_path if original_subtitle_path and os.path.exists(original_subtitle_path) else "",
        "raw_subtitle_path": raw_subtitle_path if raw_subtitle_path and os.path.exists(raw_subtitle_path) else "",
        "clean_subtitle_path": clean_subtitle_path if clean_subtitle_path and os.path.exists(clean_subtitle_path) else (
            preferred_subtitle_path if preferred_subtitle_path and os.path.exists(preferred_subtitle_path) else ""
        ),
        "subtitle_segments_path": subtitle_segments_path if subtitle_segments_path and os.path.exists(subtitle_segments_path) else "",
        "segments": segments,
        "source": source,
        "success": bool(segments),
        "error": error,
        "generated_temp_path": generated_temp_path if generated_temp_path and os.path.exists(generated_temp_path) else "",
        "generated_saved_path": generated_saved_path if generated_saved_path and os.path.exists(generated_saved_path) else "",
        "cache_version": AUTO_SUBTITLE_CACHE_VERSION,
        "backend": _backend_cache_key(backend_override),
        "regenerate": regenerate,
    }
