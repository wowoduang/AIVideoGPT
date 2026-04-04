from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

PRESETS: Dict[str, Dict[str, Any]] = {
    "fast": {
        "mode": "fast",
        "label": "快速",
        "scene_threshold": 30.0,
        "min_scene_len": 1.2,
        "max_scene_duration": 8.0,
        "max_gap": 0.8,
        "force_split_gap": 3.0,
        "micro_threshold": 1.5,
        "min_scene_duration": 1.0,
        "topic_split_min_subs": 8,
        "topic_shift_overlap_threshold": 0.18,
        "merge_low_info": False,
        "visual_mode": "off",
        "visual_max_frames_dialogue": 0,
        "visual_max_frames_visual_only": 0,
        "visual_max_frames_long_scene": 0,
    },
    "balanced": {
        "mode": "balanced",
        "label": "标准",
        "scene_threshold": 27.0,
        "min_scene_len": 2.0,
        "max_scene_duration": 12.0,
        "max_gap": 1.2,
        "force_split_gap": 4.5,
        "micro_threshold": 2.0,
        "min_scene_duration": 1.5,
        "topic_split_min_subs": 6,
        "topic_shift_overlap_threshold": 0.12,
        "merge_low_info": True,
        "visual_mode": "auto",
        "visual_max_frames_dialogue": 1,
        "visual_max_frames_visual_only": 3,
        "visual_max_frames_long_scene": 3,
    },
    "quality": {
        "mode": "quality",
        "label": "高质量",
        "scene_threshold": 24.0,
        "min_scene_len": 2.0,
        "max_scene_duration": 16.0,
        "max_gap": 1.6,
        "force_split_gap": 5.5,
        "micro_threshold": 2.5,
        "min_scene_duration": 2.0,
        "topic_split_min_subs": 5,
        "topic_shift_overlap_threshold": 0.08,
        "merge_low_info": True,
        "visual_mode": "auto",
        "visual_max_frames_dialogue": 1,
        "visual_max_frames_visual_only": 3,
        "visual_max_frames_long_scene": 3,
    },
}

ALIASES = {
    "standard": "balanced",
    "default": "balanced",
    "normal": "balanced",
    "high": "quality",
}


def resolve_subtitle_mode_preset(
    mode: str = "balanced",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = (mode or "balanced").strip().lower()
    normalized = ALIASES.get(normalized, normalized)
    if normalized not in PRESETS:
        normalized = "balanced"

    preset = deepcopy(PRESETS[normalized])
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                preset[key] = value
    return preset


def resolve_visual_mode(
    requested_visual_mode: str = "",
    preset: Optional[Dict[str, Any]] = None,
) -> str:
    if requested_visual_mode:
        mode = requested_visual_mode.strip().lower()
        if mode in {"off", "auto", "boost"}:
            return mode
    if preset and preset.get("visual_mode"):
        return str(preset["visual_mode"]).strip().lower()
    return "auto"