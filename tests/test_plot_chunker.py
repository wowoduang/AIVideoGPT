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

    def debug(self, *args, **kwargs):
        return None


def _load_plot_chunker():
    loguru_module = types.ModuleType("loguru")
    loguru_module.logger = _Logger()
    with patch.dict(sys.modules, {"loguru": loguru_module}):
        sys.modules.pop("app.services.plot_chunker", None)
        return importlib.import_module("app.services.plot_chunker")


class PlotChunkerSpeakerTests(unittest.TestCase):
    def test_build_plot_chunks_preserves_speaker_signals(self):
        plot_chunker = _load_plot_chunker()
        subtitle_segments = [
            {
                "seg_id": "sub_001",
                "start": 0.0,
                "end": 2.0,
                "text": "\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60",
                "speaker": "\u5f20\u4e09",
            },
            {
                "seg_id": "sub_002",
                "start": 2.1,
                "end": 4.2,
                "text": "\u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053",
                "speaker": "\u674e\u56db",
            },
            {
                "seg_id": "sub_003",
                "start": 4.3,
                "end": 6.2,
                "text": "\u90a3\u6211\u4eec\u73b0\u5728\u8fd8\u600e\u4e48\u529e",
                "speaker": "\u738b\u4e94",
            },
        ]

        chunks = plot_chunker.build_plot_chunks_from_subtitles(
            subtitle_segments,
            target_duration_minutes=1,
            refine_chunks=False,
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["speaker_names"], ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"])
        self.assertEqual(chunks[0]["speaker_sequence"], ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"])
        self.assertEqual(chunks[0]["exchange_pairs"], ["\u5f20\u4e09->\u674e\u56db", "\u674e\u56db->\u738b\u4e94"])
        self.assertEqual(chunks[0]["speaker_turns"], 3)

    def test_highlight_selectivity_changes_fallback_size(self):
        plot_chunker = _load_plot_chunker()
        chunks = [
            {
                "segment_id": f"plot_{idx:03d}",
                "importance_level": "low",
                "plot_role": "setup",
                "block_type": "transition",
                "start": float(idx * 5),
                "end": float(idx * 5 + 3),
                "aligned_subtitle_text": "\u666e\u901a\u8fc7\u573a\u7247\u6bb5",
                "boundary_source": "subtitle_only",
                "need_visual_verify": False,
                "raw_voice_retain_suggestion": False,
            }
            for idx in range(5)
        ]

        loose = plot_chunker._select_story_highlights(chunks, highlight_selectivity="loose")
        strict = plot_chunker._select_story_highlights(chunks, highlight_selectivity="strict")

        self.assertEqual(5, len(loose))
        self.assertEqual(3, len(strict))


if __name__ == "__main__":
    unittest.main()
