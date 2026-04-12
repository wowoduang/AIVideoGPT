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


def _load_highlight_ai_module(completion_result):
    config_module = _stub_module(
        "app.config.config",
        app={
            "text_litellm_api_key": "test-key",
            "text_litellm_model_name": "test-model",
            "text_litellm_base_url": "https://example.com/v1",
        },
    )
    app_config_module = _stub_module("app.config", config=config_module)
    llm_module = _stub_module(
        "app.services.llm_text_completion",
        call_text_chat_completion=lambda *args, **kwargs: completion_result,
    )
    loguru_module = _stub_module(
        "loguru",
        logger=types.SimpleNamespace(warning=lambda *args, **kwargs: None),
    )

    with patch.dict(
        sys.modules,
        {
            "app.config": app_config_module,
            "app.config.config": config_module,
            "app.services.llm_text_completion": llm_module,
            "loguru": loguru_module,
        },
    ):
        sys.modules.pop("app.services.highlight_ai", None)
        return importlib.import_module("app.services.highlight_ai")


class HighlightAITests(unittest.TestCase):
    def test_ai_select_highlight_candidates_filters_unknown_ids(self):
        module = _load_highlight_ai_module(
            '{"selected_clip_ids":["clip_b","missing"],"raw_audio_clip_ids":["clip_b"],'
            '"selection_notes":[{"clip_id":"clip_b","decision":"keep","reason":"real payoff"}]}'
        )
        result = module.ai_select_highlight_candidates(
            [
                {"clip_id": "clip_a", "start": 0.0, "end": 5.0, "duration": 5.0, "story_stage_hint": "opening", "total_score": 0.4},
                {"clip_id": "clip_b", "start": 50.0, "end": 58.0, "duration": 8.0, "story_stage_hint": "reveal", "total_score": 0.9},
            ],
            target_duration_seconds=60,
            movie_title="Demo",
        )

        self.assertTrue(result["used_ai"])
        self.assertEqual(result["selected_clip_ids"], ["clip_b"])
        self.assertEqual(result["raw_audio_clip_ids"], ["clip_b"])
        self.assertEqual(result["selection_notes"][0]["clip_id"], "clip_b")

    def test_ai_match_narration_units_to_candidates_preserves_one_sentence_per_match(self):
        module = _load_highlight_ai_module(
            '{"selected_clip_id":"clip_002","backup_clip_ids":["clip_001"],"reason":"best semantic fit","confidence":0.88}'
        )
        matches = module.ai_match_narration_units_to_candidates(
            [
                {
                    "unit_id": "n_001",
                    "text": "张三这时已经开始怀疑李四。",
                    "target_seconds": 3.8,
                    "story_stage": "reveal",
                    "narration_type": "inner_state",
                    "match_focus": "psychological_support",
                    "keywords": ["张三", "怀疑", "李四"],
                    "character_names": ["张三", "李四"],
                    "position_hint": 0.6,
                }
            ],
            [
                {
                    "clip_id": "clip_001",
                    "start": 10.0,
                    "end": 14.0,
                    "duration": 4.0,
                    "story_stage_hint": "setup",
                    "total_score": 0.5,
                    "character_names": ["张三"],
                    "subtitle_text": "先铺垫一下",
                    "scene_summary": "普通对话",
                },
                {
                    "clip_id": "clip_002",
                    "start": 42.0,
                    "end": 46.0,
                    "duration": 4.0,
                    "story_stage_hint": "reveal",
                    "total_score": 0.82,
                    "character_names": ["张三", "李四"],
                    "subtitle_text": "张三沉默地看着李四",
                    "scene_summary": "张三已经开始动摇并怀疑李四",
                },
            ],
            movie_title="Demo",
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["clip_id"], "clip_002")
        self.assertTrue(matches[0]["preserve_sentence_boundary"])
        self.assertEqual(matches[0]["clip_ids"], ["clip_002"])
        self.assertEqual(len(matches[0]["clip_group"]), 1)


if __name__ == "__main__":
    unittest.main()
