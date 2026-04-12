import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_module(session_state=None, text_provider="gemini"):
    streamlit_module = _stub_module("streamlit", session_state=session_state or {})
    config_module = _stub_module("app.config", config=_stub_module("config", app={"text_llm_provider": text_provider}))
    subtitle_text_module = _stub_module("app.services.subtitle_text", read_subtitle_text=lambda path: None)
    loguru_module = _stub_module("loguru", logger=_stub_module("logger", warning=lambda *args, **kwargs: None))

    stubbed_modules = {
        "streamlit": streamlit_module,
        "app.config": config_module,
        "app.services.subtitle_text": subtitle_text_module,
        "loguru": loguru_module,
    }

    with patch.dict(sys.modules, stubbed_modules):
        module_name = "_test_movie_story_script_support"
        sys.modules.pop(module_name, None)
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path("webui/services/movie_story_script_support.py"),
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module


class MovieStoryScriptSupportTests(unittest.TestCase):
    def test_normalize_subtitle_path_handles_auto(self):
        module = _load_module()
        self.assertEqual("", module._normalize_subtitle_path("AUTO", "existing_subtitle"))
        self.assertEqual("", module._normalize_subtitle_path("demo.srt", "auto_subtitle"))

    def test_build_request_collects_runtime_flags(self):
        session_state = {
            "generation_mode": "balanced",
            "visual_mode": "auto",
            "narration_style": "general",
            "target_duration_minutes": 8,
            "narrative_strategy": "chronological",
            "accuracy_priority": "high",
            "highlight_only_mode": True,
            "highlight_selectivity": "balanced",
            "subtitle_asr_backend": "faster-whisper",
            "subtitle_cache_mode": "clear_and_regenerate",
            "subtitle_review_mode": "skip_review",
            "prologue_strategy": "speech_first",
            "manual_prologue_end_time": "00:00:10",
        }
        module = _load_module(session_state=session_state)
        params = types.SimpleNamespace(video_origin_path="demo.mp4")

        request = module._build_request(params, "demo.srt", "Demo", 0.7)

        self.assertEqual("demo.mp4", request["video_path"])
        self.assertEqual("demo.srt", request["subtitle_path"])
        self.assertEqual("Demo", request["video_theme"])
        self.assertTrue(request["highlight_only"])
        self.assertEqual("skip_review", request["review_mode"])


if __name__ == "__main__":
    unittest.main()
