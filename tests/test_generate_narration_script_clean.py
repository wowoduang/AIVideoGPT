import unittest

import app.services.generate_narration_script_clean as narration_clean


class GenerateNarrationScriptCleanTests(unittest.TestCase):
    def test_pick_ost_forces_opening_segment_to_use_narration(self):
        pkg = {
            "start": 0.0,
            "end": 8.0,
            "importance_level": "high",
            "plot_function": "铺垫",
            "llm_raw_voice_keep": True,
            "audio_strategy": "keep",
            "is_opening_segment": True,
        }

        ost = narration_clean._pick_ost(pkg, {"raw_voice_keep": True})

        self.assertEqual(2, ost)

    def test_pick_ost_prefers_narration_for_long_raw_voice_segments(self):
        pkg = {
            "start": 260.25,
            "end": 305.75,
            "importance_level": "high",
            "plot_function": "信息揭露",
            "llm_raw_voice_keep": True,
            "audio_strategy": "keep",
        }

        ost = narration_clean._pick_ost(pkg, {"raw_voice_keep": True})

        self.assertEqual(2, ost)

    def test_trim_script_overlaps_moves_following_segment_start_forward(self):
        items = [
            {
                "_id": 1,
                "start": 260.25,
                "end": 305.75,
                "timestamp": "00:04:20,250-00:05:05,750",
                "source_timestamp": "00:04:20,250-00:05:05,750",
                "narration": "第一段",
            },
            {
                "_id": 2,
                "start": 279.167,
                "end": 360.5,
                "timestamp": "00:04:39,167-00:06:00,500",
                "source_timestamp": "00:04:39,167-00:06:00,500",
                "narration": "第二段",
            },
        ]

        trimmed = narration_clean._trim_script_overlaps(items)

        self.assertEqual(2, len(trimmed))
        self.assertEqual(305.75, trimmed[1]["start"])
        self.assertEqual(54.75, trimmed[1]["duration"])
        self.assertEqual("00:05:05,750-00:06:00,500", trimmed[1]["timestamp"])

    def test_clean_review_rewrite_hint_strips_meta_prefix(self):
        cleaned = narration_clean._clean_review_rewrite_hint(
            '如果需要更保守，可以修改为：“守城战已经打响，现场一片紧张。”'
        )

        self.assertEqual("守城战已经打响，现场一片紧张。", cleaned)

    def test_resolve_review_narration_text_keeps_original_when_hint_is_meta(self):
        result = narration_clean._resolve_review_narration_text(
            "守城战已经打响，士兵正在死守。",
            {"safe_rewrite_hint": "建议改为：如果想更保守，可以换个说法"},
            40,
        )

        self.assertEqual("守城战已经打响，士兵正在死守。", result)

    def test_soften_uncertain_speaker_attribution_replaces_role_guess(self):
        softened = narration_clean._soften_uncertain_speaker_attribution(
            "皇上说先把人押下去，太监回应得很快。",
            {
                "speaker_names": [],
                "speaker_turns": 2,
            },
        )

        self.assertEqual("有人说先把人押下去，有人回应得很快。", softened)

    def test_postprocess_candidate_narration_adds_opening_prefix(self):
        narration = narration_clean._postprocess_candidate_narration(
            "局势一下子就紧了起来。",
            {
                "is_opening_segment": True,
                "speaker_names": [],
                "speaker_turns": 0,
            },
            40,
            "general",
        )

        self.assertTrue(narration.startswith("故事一开场，"))


if __name__ == "__main__":
    unittest.main()
