import importlib
import sys
import types
import unittest
from unittest.mock import patch


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_composition_plan_adapter_module():
    utils_module = _stub_module(
        "app.utils.utils",
        format_time=lambda seconds: f"00:00:{int(seconds):02d}",
    )
    app_utils_module = _stub_module("app.utils", utils=utils_module)

    with patch.dict(sys.modules, {"app.utils": app_utils_module, "app.utils.utils": utils_module}):
        sys.modules.pop("app.services.composition_plan_adapter", None)
        return importlib.import_module("app.services.composition_plan_adapter")


class CompositionPlanAdapterTests(unittest.TestCase):
    def test_raw_segments_keep_raw_audio_flags(self):
        module = _load_composition_plan_adapter_module()
        plan = {
            "segments": [
                {
                    "segment_id": "seg_0001",
                    "video_start": 10.0,
                    "video_end": 15.0,
                    "audio_mode": "raw",
                    "picture": "冲突升级",
                    "source_clip_id": "clip_001",
                    "clip_source": "scene",
                    "source_scene_id": "scene_001",
                    "raw_audio_worthy": True,
                    "trim_strategy": "tail",
                    "original_duration": 8.0,
                    "planned_duration": 5.0,
                }
            ]
        }

        items = module.composition_plan_to_script_items(plan)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["OST"], 1)
        self.assertTrue(items[0]["llm_raw_voice_keep"])
        self.assertTrue(items[0]["raw_voice_retain_suggestion"])
        self.assertEqual(items[0]["composition_clip_source"], "scene")
        self.assertEqual(items[0]["composition_source_scene_id"], "scene_001")
        self.assertEqual(items[0]["composition_trim_strategy"], "tail")

    def test_empty_ducked_raw_segment_falls_back_to_raw_and_keeps_flags(self):
        module = _load_composition_plan_adapter_module()
        plan = {
            "segments": [
                {
                    "segment_id": "seg_0002",
                    "video_start": 1.0,
                    "video_end": 3.0,
                    "audio_mode": "ducked_raw",
                    "narration_text": "",
                    "picture": "反转镜头",
                    "source_clip_id": "clip_002",
                }
            ]
        }

        items = module.composition_plan_to_script_items(plan)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["OST"], 1)
        self.assertTrue(items[0]["llm_raw_voice_keep"])
        self.assertTrue(items[0]["raw_voice_retain_suggestion"])
        self.assertEqual(items[0]["composition_audio_mode"], "ducked_raw")

    def test_missing_picture_uses_non_empty_fallback(self):
        module = _load_composition_plan_adapter_module()
        plan = {
            "segments": [
                {
                    "segment_id": "seg_0003",
                    "video_start": 20.0,
                    "video_end": 24.0,
                    "audio_mode": "raw",
                    "picture": "",
                    "selection_reason": ["reveal", "audio:raw_follow"],
                    "source_clip_id": "clip_003",
                }
            ]
        }

        items = module.composition_plan_to_script_items(plan)

        self.assertEqual(len(items), 1)
        self.assertTrue(isinstance(items[0]["picture"], str))
        self.assertTrue(items[0]["picture"].strip())
        self.assertIn("高光画面", items[0]["picture"])


if __name__ == "__main__":
    unittest.main()
