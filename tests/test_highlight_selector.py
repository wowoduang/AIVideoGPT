import unittest

from app.services.highlight_selector import (
    apply_audio_signal_scores,
    build_candidate_from_plot_chunk,
    enrich_candidate_evidence,
)


class HighlightSelectorEvidenceTests(unittest.TestCase):
    def test_enrich_candidate_evidence_marks_inner_state_scene(self):
        clip = {
            "clip_id": "inner_clip",
            "subtitle_text": "\u4ed6\u6ca1\u6709\u518d\u8bf4\u8bdd",
            "scene_summary": "\u4ed6\u6c89\u9ed8\u5730\u79fb\u5f00\u89c6\u7ebf\uff0c\u5fc3\u91cc\u5df2\u7ecf\u5f00\u59cb\u6000\u7591\u5bf9\u65b9",
            "tags": ["reveal"],
            "source": "scene",
            "duration": 3.2,
            "emotion_score": 0.76,
            "story_stage_hint": "reveal",
            "raw_audio_worthy": True,
            "character_names": ["\u4e3b\u89d2"],
        }

        enriched = enrich_candidate_evidence(clip)

        self.assertEqual(enriched["primary_evidence"], "inner_state_support")
        self.assertEqual(enriched["shot_role"], "single_focus")
        self.assertEqual(enriched["speaker_turns"], 0)
        self.assertEqual(enriched["speaker_names"], [])
        self.assertEqual(enriched["interaction_target_names"], ["\u4e3b\u89d2"])
        self.assertGreater(enriched["inner_state_support"], enriched["reaction_score"])
        self.assertGreater(enriched["solo_focus_score"], enriched["dialogue_exchange_score"])
        self.assertGreater(enriched["inner_state_support"], 0.55)

    def test_enrich_candidate_evidence_marks_relation_scene(self):
        clip = {
            "clip_id": "relation_clip",
            "subtitle_text": "\u5f20\u4e09\uff1a\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60 \u674e\u56db\uff1a\u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053",
            "scene_summary": "\u4e24\u4eba\u9762\u5bf9\u9762\u5bf9\u5cd9\uff0c\u5173\u7cfb\u5f7b\u5e95\u53cd\u8f6c\uff0c\u5f7c\u6b64\u90fd\u4e0d\u518d\u4fe1\u4efb\u5bf9\u65b9",
            "tags": ["conflict", "reveal"],
            "source": "scene",
            "duration": 3.5,
            "emotion_score": 0.68,
            "story_stage_hint": "turning_point",
            "raw_audio_worthy": True,
            "character_names": ["\u5f20\u4e09", "\u674e\u56db"],
        }

        enriched = enrich_candidate_evidence(clip)

        self.assertEqual(enriched["primary_evidence"], "relation_score")
        self.assertEqual(enriched["shot_role"], "dialogue_exchange")
        self.assertEqual(enriched["speaker_turns"], 2)
        self.assertEqual(enriched["speaker_sequence"], ["\u5f20\u4e09", "\u674e\u56db"])
        self.assertEqual(enriched["speaker_names"], ["\u5f20\u4e09", "\u674e\u56db"])
        self.assertEqual(enriched["exchange_pairs"], ["\u5f20\u4e09->\u674e\u56db"])
        self.assertEqual(enriched["interaction_target_names"], ["\u674e\u56db"])
        self.assertGreater(enriched["relation_score"], enriched["reaction_score"])
        self.assertGreater(enriched["dialogue_exchange_score"], enriched["ensemble_scene_score"])
        self.assertGreater(enriched["relation_score"], 0.55)

    def test_enrich_candidate_evidence_derives_pressure_direction(self):
        clip = {
            "clip_id": "pressure_clip",
            "subtitle_text": "\u5f20\u4e09\uff1a\u4f60\u8bf4 \u738b\u4e94\uff1a\u6211\u6ca1\u4ec0\u4e48\u53ef\u8bf4\u7684 \u674e\u56db\uff1a\u4f60\u8fd8\u60f3\u88c5\u5230\u4ec0\u4e48\u65f6\u5019 \u738b\u4e94\uff1a\u6211\u771f\u7684\u6ca1\u9a97\u4f60\u4eec",
            "scene_summary": "\u4e09\u4eba\u5f53\u573a\u5bf9\u5cf0\uff0c\u5f20\u4e09\u548c\u674e\u56db\u4e00\u8d77\u628a\u538b\u529b\u90fd\u7ed9\u5230\u4e86\u738b\u4e94",
            "tags": ["conflict", "reveal"],
            "source": "scene",
            "duration": 5.2,
            "emotion_score": 0.74,
            "story_stage_hint": "conflict",
            "raw_audio_worthy": True,
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "speaker_sequence": ["\u5f20\u4e09", "\u738b\u4e94", "\u674e\u56db", "\u738b\u4e94"],
            "exchange_pairs": ["\u5f20\u4e09->\u738b\u4e94", "\u738b\u4e94->\u674e\u56db", "\u674e\u56db->\u738b\u4e94"],
        }

        enriched = enrich_candidate_evidence(clip)

        self.assertEqual(enriched["pressure_target_names"], ["\u738b\u4e94"])
        self.assertEqual(enriched["pressure_source_names"], ["\u5f20\u4e09", "\u674e\u56db"])
        self.assertGreater(enriched["group_reaction_score"], 0.7)
        self.assertIn("\u738b\u4e94", enriched["interaction_target_names"])

    def test_enrich_candidate_evidence_marks_action_scene(self):
        clip = {
            "clip_id": "action_clip",
            "subtitle_text": "\u5feb\u8ffd",
            "scene_summary": "\u4ed6\u8f6c\u8eab\u51b2\u51fa\u623f\u95f4\uff0c\u63a8\u5f00\u95e8\u8ffd\u4e86\u4e0a\u53bb",
            "tags": ["conflict"],
            "source": "scene",
            "duration": 2.8,
            "emotion_score": 0.35,
            "story_stage_hint": "conflict",
            "raw_audio_worthy": True,
            "character_names": ["\u4e3b\u89d2"],
        }

        enriched = enrich_candidate_evidence(clip)

        self.assertEqual(enriched["primary_evidence"], "visible_action_score")
        self.assertEqual(enriched["shot_role"], "action_follow")
        self.assertEqual(enriched["speaker_turns"], 0)
        self.assertEqual(enriched["speaker_names"], [])
        self.assertEqual(enriched["interaction_target_names"], ["\u4e3b\u89d2"])
        self.assertGreater(enriched["visible_action_score"], enriched["reaction_score"])
        self.assertGreater(enriched["visible_action_score"], enriched["dialogue_exchange_score"])
        self.assertGreater(enriched["visible_action_score"], 0.4)

    def test_build_candidate_from_plot_chunk_keeps_speaker_names(self):
        chunk = {
            "start": 8.0,
            "end": 12.0,
            "highlight_score": 0.7,
            "importance_level": "high",
            "attraction_level": "medium",
            "narration_level": "focus",
            "plot_function": "\u53cd\u8f6c",
            "plot_role": "twist",
            "aligned_subtitle_text": "\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60 \u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053",
            "real_narrative_state": "\u4e24\u4eba\u7684\u5173\u7cfb\u5728\u8fd9\u4e00\u523b\u53cd\u8f6c",
            "surface_dialogue_meaning": "\u4e24\u4eba\u7684\u5173\u7cfb\u5728\u8fd9\u4e00\u523b\u53cd\u8f6c",
            "raw_voice_retain_suggestion": True,
            "subtitle_ids": ["sub_001", "sub_002"],
            "scene_id": "scene_002",
            "speaker_sequence": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "speaker_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "speaker_turns": 3,
            "exchange_pairs": ["\u5f20\u4e09->\u674e\u56db", "\u674e\u56db->\u738b\u4e94"],
        }

        candidate = build_candidate_from_plot_chunk(chunk, 1, 2)

        self.assertEqual(candidate["speaker_names"], ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"])
        self.assertEqual(candidate["speaker_sequence"], ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"])
        self.assertEqual(candidate["exchange_pairs"], ["\u5f20\u4e09->\u674e\u56db", "\u674e\u56db->\u738b\u4e94"])
        self.assertEqual(candidate["speaker_turns"], 3)
        self.assertIn("\u5f20\u4e09", candidate["character_names"])
        self.assertIn("\u674e\u56db", candidate["character_names"])
        self.assertIn("\u738b\u4e94", candidate["character_names"])
        self.assertIn("\u738b\u4e94", candidate["interaction_target_names"])
        self.assertEqual(candidate["shot_role"], "dialogue_exchange")

    def test_apply_audio_signal_scores_promotes_raw_audio_candidate(self):
        clip = {
            "clip_id": "audio_clip",
            "subtitle_text": "\u4ed6\u4eec\u51b2\u8fdb\u623f\u95f4",
            "scene_summary": "\u4e00\u58f0\u7206\u54cd\u540e\uff0c\u4f17\u4eba\u7acb\u523b\u51b2\u4e0a\u53bb",
            "tags": ["conflict"],
            "source": "scene",
            "duration": 3.0,
            "emotion_score": 0.34,
            "story_score": 0.52,
            "energy_score": 0.22,
            "story_stage_hint": "conflict",
            "raw_audio_worthy": False,
            "character_names": ["\u4e3b\u89d2"],
        }

        enriched = apply_audio_signal_scores(
            clip,
            {
                "audio_rms_score": 0.72,
                "audio_onset_score": 0.68,
                "audio_dynamic_score": 0.64,
                "audio_signal_score": 0.74,
                "audio_peak_score": 0.82,
            },
        )

        self.assertTrue(enriched["raw_audio_worthy"])
        self.assertIn("audio_signal", enriched["tags"])
        self.assertIn("audio_peak", enriched["tags"])
        self.assertIn("audio_signal_peak", enriched["selection_reason"])
        self.assertGreater(enriched["energy_score"], 0.5)
        self.assertGreater(enriched["total_score"], 0.5)


if __name__ == "__main__":
    unittest.main()
