from __future__ import annotations

import hashlib
import json
import os
import shutil
from typing import Dict, List, Tuple

from loguru import logger

from app.utils import utils
from app.services.media_duration import probe_media_duration


CACHE_DIR_NAME = "tts_cache"


def _cache_root() -> str:
    root = os.path.join(utils.storage_dir(), CACHE_DIR_NAME)
    os.makedirs(root, exist_ok=True)
    return root


def build_tts_cache_key(item: Dict, voice_name: str, voice_rate: float, voice_pitch: float, tts_engine: str) -> str:
    payload = {
        "text": item.get("narration", ""),
        "voice_name": voice_name,
        "voice_rate": voice_rate,
        "voice_pitch": voice_pitch,
        "tts_engine": tts_engine,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _target_paths(task_id: str, item: Dict) -> Tuple[str, str]:
    output_dir = utils.task_dir(task_id)
    timestamp = str(item.get("timestamp", "segment")).replace(":", "_")
    return (
        os.path.join(output_dir, f"audio_{timestamp}.mp3"),
        os.path.join(output_dir, f"subtitle_{timestamp}.srt"),
    )


def load_cached_tts_results(
    task_id: str,
    list_script: List[Dict],
    voice_name: str,
    voice_rate: float,
    voice_pitch: float,
    tts_engine: str,
) -> Tuple[List[Dict], List[Dict]]:
    cached_results: List[Dict] = []
    missing_items: List[Dict] = []
    root = _cache_root()

    for item in list_script or []:
        if item.get("OST") not in [0, 2]:
            continue
        cache_key = build_tts_cache_key(item, voice_name, voice_rate, voice_pitch, tts_engine)
        cache_dir = os.path.join(root, cache_key)
        meta_file = os.path.join(cache_dir, "meta.json")
        audio_src = os.path.join(cache_dir, "audio.mp3")
        subtitle_src = os.path.join(cache_dir, "subtitle.srt")
        if os.path.exists(meta_file) and os.path.exists(audio_src):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                audio_dst, subtitle_dst = _target_paths(task_id, item)
                os.makedirs(os.path.dirname(audio_dst), exist_ok=True)
                shutil.copy2(audio_src, audio_dst)
                subtitle_file = ""
                if os.path.exists(subtitle_src):
                    shutil.copy2(subtitle_src, subtitle_dst)
                    subtitle_file = subtitle_dst
                cached_results.append(
                    {
                        "_id": item.get("_id"),
                        "timestamp": item.get("timestamp"),
                        "audio_file": audio_dst,
                        "subtitle_file": subtitle_file,
                        "duration": meta.get("duration", 0) or probe_media_duration(audio_dst),
                        "text": item.get("narration", ""),
                        "cached": True,
                    }
                )
                continue
            except Exception as e:
                logger.warning(f"读取TTS缓存失败，将重新生成: {e}")
        missing_items.append(item)

    if cached_results:
        logger.info(f"TTS 缓存命中: {len(cached_results)} 段, 待生成: {len(missing_items)} 段")
    return cached_results, missing_items


def store_tts_results(
    list_script: List[Dict],
    tts_results: List[Dict],
    voice_name: str,
    voice_rate: float,
    voice_pitch: float,
    tts_engine: str,
) -> None:
    if not tts_results:
        return
    item_map = {item.get("_id"): item for item in list_script or []}
    root = _cache_root()
    for result in tts_results:
        item = item_map.get(result.get("_id"))
        audio_file = result.get("audio_file")
        if not item or not audio_file or not os.path.exists(audio_file):
            continue
        cache_key = build_tts_cache_key(item, voice_name, voice_rate, voice_pitch, tts_engine)
        cache_dir = os.path.join(root, cache_key)
        os.makedirs(cache_dir, exist_ok=True)
        shutil.copy2(audio_file, os.path.join(cache_dir, "audio.mp3"))
        subtitle_file = result.get("subtitle_file")
        if subtitle_file and os.path.exists(subtitle_file):
            shutil.copy2(subtitle_file, os.path.join(cache_dir, "subtitle.srt"))
        duration = result.get("duration", 0) or probe_media_duration(audio_file)
        meta = {"duration": duration, "timestamp": item.get("timestamp")}
        with open(os.path.join(cache_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
