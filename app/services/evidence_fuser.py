from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

from loguru import logger


def _simple_entities(text: str) -> Dict[str, List[str]]:
    text = (text or "").strip()
    english_names = re.findall(r"\b[A-Z][a-z]{1,20}\b", text)
    quoted = re.findall(r"[《“\"]([^》”\"]{1,12})[》”\"]", text)
    chars = []
    for item in english_names + quoted:
        if item not in chars:
            chars.append(item)
    return {"characters": chars[:6], "locations": [], "props": []}


def _emotion_from_text(text: str, visual_summary: List[Dict]) -> str:
    joined = (text or "") + " " + " ".join(x.get("desc", "") for x in visual_summary)
    cues = {
        "愤怒": ["生气", "愤怒", "怒", "吼", "骂"],
        "悲伤": ["哭", "难过", "伤心", "泪", "沉默"],
        "喜悦": ["笑", "开心", "高兴", "兴奋"],
        "紧张": ["紧张", "小心", "快", "别动", "危险"],
        "惊讶": ["什么", "怎么", "居然", "突然", "惊讶"],
        "恐惧": ["害怕", "恐惧", "别过来", "救命"],
    }
    for label, words in cues.items():
        if any(w in joined for w in words):
            return label
    return "平静"


def _build_context_window(index: int, scenes: List[Dict], prev_n: int, next_n: int) -> Dict[str, List[str]]:
    prev_items = []
    next_items = []
    for item in scenes[max(0, index - prev_n): index]:
        prev_items.append((item.get("aligned_subtitle_text") or item.get("subtitle_text") or "")[:60])
    for item in scenes[index + 1: index + 1 + next_n]:
        next_items.append((item.get("aligned_subtitle_text") or item.get("subtitle_text") or "")[:60])
    return {"prev": prev_items, "next": next_items}


def _guess_confidence(scene: Dict) -> str:
    if scene.get("visual_only"):
        return "visual_only"
    source = (scene.get("subtitle_source") or "").lower()
    if "srt" in source or "ass" in source or "vtt" in source:
        return "srt"
    if scene.get("low_confidence"):
        return "asr_low"
    return "asr_high"


def _default_visual_desc(frame_path: str, rank: int) -> str:
    name = os.path.basename(frame_path)
    return f"第{rank}张代表帧，来自{name}"


def _safe_load_visual_input(data: Any) -> Any:
    """
    兼容几种输入：
    1. 已经是 Python dict/list
    2. JSON 字符串
    3. JSON 文件路径
    """
    if data is None:
        return None

    if isinstance(data, (dict, list)):
        return data

    if isinstance(data, str):
        raw = data.strip()
        if not raw:
            return None

        if os.path.exists(raw):
            try:
                with open(raw, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("读取视觉分析文件失败: {}", e)
                return None

        try:
            return json.loads(raw)
        except Exception:
            return None

    return None


def parse_visual_analysis_results(results: Any) -> Dict[str, List[Dict]]:
    """
    兼容旧 WebUI 的导入接口。
    输出统一格式：
    {
        "segment_xxx": [
            {
                "frame_path": "...jpg",
                "observation": "人物站在门口，神情紧张",
                "model": "gemini/qwen/unknown"
            }
        ]
    }

    支持输入：
    - dict
    - list
    - JSON 字符串
    - JSON 文件路径
    """
    data = _safe_load_visual_input(results)
    parsed: Dict[str, List[Dict]] = {}

    if not data:
        return parsed

    # 情况1：已经是目标格式
    # {segment_id: [{frame_path, observation}, ...]}
    if isinstance(data, dict):
        # 1a. 顶层就是 segment_id -> list[dict]
        all_values_are_lists = all(isinstance(v, list) for v in data.values()) if data else False
        if all_values_are_lists:
            for seg_id, items in data.items():
                bucket = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    frame_path = item.get("frame_path") or item.get("image") or item.get("path") or ""
                    observation = (
                        item.get("observation")
                        or item.get("desc")
                        or item.get("description")
                        or item.get("summary")
                        or ""
                    )
                    bucket.append(
                        {
                            "frame_path": frame_path,
                            "observation": observation,
                            "model": item.get("model", "unknown"),
                        }
                    )
                if bucket:
                    parsed[str(seg_id)] = bucket
            return parsed

        # 1b. 常见包装结构
        for key in ["results", "data", "items", "frames", "analyses"]:
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # 1c. 单条记录 dict
            data = [data]

    # 情况2：list[dict]
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue

            seg_id = (
                item.get("segment_id")
                or item.get("scene_id")
                or item.get("clip_id")
                or item.get("id")
            )
            if not seg_id:
                seg_id = "global"

            frame_path = item.get("frame_path") or item.get("image") or item.get("path") or ""
            observation = (
                item.get("observation")
                or item.get("desc")
                or item.get("description")
                or item.get("summary")
                or item.get("caption")
                or ""
            )

            # 有些结果把多帧分析放在 children / frames
            children = item.get("frames") or item.get("children")
            if isinstance(children, list) and children:
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    child_frame = child.get("frame_path") or child.get("image") or child.get("path") or frame_path
                    child_obs = (
                        child.get("observation")
                        or child.get("desc")
                        or child.get("description")
                        or child.get("summary")
                        or observation
                    )
                    parsed.setdefault(str(seg_id), []).append(
                        {
                            "frame_path": child_frame,
                            "observation": child_obs,
                            "model": child.get("model") or item.get("model", "unknown"),
                        }
                    )
            else:
                parsed.setdefault(str(seg_id), []).append(
                    {
                        "frame_path": frame_path,
                        "observation": observation,
                        "model": item.get("model", "unknown"),
                    }
                )

    return parsed


def fuse_scene_evidence(
    scenes: List[Dict],
    frame_records: List[Dict],
    visual_observations: Dict[str, List[Dict]],
    context_prev: int = 2,
    context_next: int = 1,
) -> List[Dict]:
    """Construct evidence packages from aligned scenes and frame data."""
    frame_map: Dict[str, List[Dict]] = {}
    for rec in frame_records or []:
        segment_id = rec.get("segment_id")
        scene_id = rec.get("scene_id")
        key = segment_id or scene_id
        if not key:
            continue
        frame_map.setdefault(key, []).append(rec)

    evidence: List[Dict] = []
    for idx, scene in enumerate(scenes or []):
        segment_id = scene.get("segment_id") or scene.get("scene_id")
        scene_id = scene.get("scene_id") or segment_id
        subtitle_text = (scene.get("aligned_subtitle_text") or scene.get("subtitle_text") or "").strip()

        records = sorted(
            frame_map.get(segment_id, []) + frame_map.get(scene_id, []),
            key=lambda x: x.get("rank", 0)
        )

        seen = set()
        unique_records = []
        for rec in records:
            fp = rec.get("frame_path")
            if not fp or fp in seen:
                continue
            seen.add(fp)
            unique_records.append(rec)

        visual_summary = []
        obs_lookup = visual_observations.get(segment_id) or visual_observations.get(scene_id) or []
        obs_by_path = {x.get("frame_path"): x for x in obs_lookup if x.get("frame_path")}

        for rank, rec in enumerate(unique_records, start=1):
            fp = rec.get("frame_path")
            observation = obs_by_path.get(fp, {}).get("observation") or _default_visual_desc(fp, rank)
            visual_summary.append({"frame": fp, "desc": observation})

        evidence.append(
            {
                "segment_id": segment_id,
                "scene_id": scene_id,
                "time_window": [
                    round(float(scene.get("start", 0.0) or 0.0), 3),
                    round(float(scene.get("end", 0.0) or 0.0), 3),
                ],
                "timestamp": scene.get("timestamp", ""),
                "main_text_evidence": subtitle_text,
                "subtitle_text": subtitle_text,
                "subtitle_ids": list(scene.get("subtitle_ids") or scene.get("aligned_subtitle_ids") or []),
                "visual_summary": visual_summary,
                "frame_paths": [x.get("frame") for x in visual_summary],
                "entities": _simple_entities(subtitle_text),
                "emotion_hint": _emotion_from_text(subtitle_text, visual_summary),
                "confidence": _guess_confidence(scene),
                "context_window": _build_context_window(idx, scenes, context_prev, context_next),
                "visual_only": bool(scene.get("visual_only")),
                "segment_type": scene.get("segment_type") or ("visual_only" if scene.get("visual_only") else "dialogue"),
                "picture": "；".join(x["desc"] for x in visual_summary[:2]) or subtitle_text[:20] or "画面推进",
                "start": round(float(scene.get("start", 0.0) or 0.0), 3),
                "end": round(float(scene.get("end", 0.0) or 0.0), 3),
            }
        )

    logger.info("证据包构建完成: {} 个", len(evidence))
    return evidence