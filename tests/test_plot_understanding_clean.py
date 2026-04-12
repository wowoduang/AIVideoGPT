import importlib
import sys
import types
import unittest
from unittest.mock import patch


class _Logger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class _PromptManager:
    @staticmethod
    def get_prompt(*args, **kwargs):
        return "prompt"


def _load_plot_understanding_clean():
    stubbed_modules = {
        "loguru": _stub_module("loguru", logger=_Logger()),
        "app.services.llm_text_completion": _stub_module(
            "app.services.llm_text_completion",
            call_text_chat_completion=lambda *args, **kwargs: "",
        ),
        "app.services.prompts": _stub_module("app.services.prompts", PromptManager=_PromptManager),
    }
    with patch.dict(sys.modules, stubbed_modules):
        sys.modules.pop("app.services.plot_understanding_clean", None)
        return importlib.import_module("app.services.plot_understanding_clean")


class PlotUnderstandingCleanTests(unittest.TestCase):
    def test_build_full_subtitle_understanding_preserves_chunk_context_when_final_parse_fails(self):
        module = _load_plot_understanding_clean()
        subtitle_segments = [
            {"start": 10.0, "end": 14.0, "text": "剧情开始反转"},
            {"start": 15.0, "end": 18.0, "text": "角色情绪爆发"},
        ]
        chunk_json = (
            '{"chunk_index": 1, "window_summary": "第一段", '
            '"highlight_windows": [{"start": "00:00:10,000", "end": "00:00:18,000", '
            '"category": "反转", "raw_voice_priority": "high", "reason": "关键冲突"}]}'
        )

        with patch.object(module, "_build_full_subtitle_text", return_value="x" * 20001), patch.object(
            module,
            "_split_subtitle_segments_for_llm",
            return_value=["chunk-1"],
        ), patch.object(
            module,
            "_call_chat_completion",
            side_effect=[chunk_json, "not-json"],
        ):
            result = module.build_full_subtitle_understanding(
                subtitle_segments,
                api_key="test-key",
                model="test-model",
            )

        self.assertEqual("chunked_full_subtitle", result["subtitle_input_mode"])
        self.assertTrue(str(result["subtitle_understanding_status"]).startswith("parse_failed"))
        self.assertEqual("chunk_summaries_fallback", result["highlight_windows_source"])
        self.assertEqual(1, len(result["subtitle_chunk_summaries"]))
        self.assertEqual(1, len(result["highlight_windows"]))
        self.assertEqual("00:00:10,000", result["highlight_windows"][0]["start"])
        self.assertEqual("00:00:18,000", result["highlight_windows"][0]["end"])


if __name__ == "__main__":
    unittest.main()
