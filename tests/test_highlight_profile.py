import unittest

from app.services import highlight_profile as profile


class HighlightProfileTests(unittest.TestCase):
    def test_resolve_explicit_profile_preserves_user_selection(self):
        resolved = profile.resolve_highlight_profile(
            requested_profile="action",
            movie_title="Demo",
            capabilities={"scenedetect_ready": True},
        )

        self.assertEqual(resolved["id"], "action")
        self.assertEqual(resolved["source"], "user_selected")
        self.assertEqual(resolved["confidence"], 1.0)
        self.assertEqual(resolved["reasons"], ["user_selected"])
        self.assertTrue(resolved["capabilities"]["scenedetect_ready"])

    def test_resolve_profile_adapts_to_dialogue_dense_signal(self):
        base = profile.get_highlight_profile("general")
        resolved = profile.resolve_highlight_profile(
            requested_profile="general",
            subtitle_segments=[
                {"text": "I know what you did last night."},
                {"text": "Then say it to my face."},
                {"text": "No more pretending between us."},
            ],
            plot_chunks=[
                {
                    "real_narrative_state": "A tense verbal confrontation exposes the hidden betrayal.",
                    "surface_dialogue_meaning": "They finally confront each other.",
                }
            ],
            candidate_clips=[
                {
                    "dialogue_exchange_score": 0.84,
                    "relation_score": 0.72,
                    "reaction_score": 0.66,
                    "inner_state_support": 0.52,
                    "group_reaction_score": 0.08,
                    "visible_action_score": 0.12,
                    "energy_score": 0.22,
                    "emotion_score": 0.7,
                    "story_score": 0.68,
                    "speaker_turns": 1,
                    "speaker_names": ["Ava"],
                    "shot_role": "dialogue_exchange",
                    "subtitle_text": "I know what you did last night.",
                    "scene_summary": "The accusation lands hard.",
                },
                {
                    "dialogue_exchange_score": 0.8,
                    "relation_score": 0.78,
                    "reaction_score": 0.62,
                    "inner_state_support": 0.48,
                    "group_reaction_score": 0.12,
                    "visible_action_score": 0.1,
                    "energy_score": 0.18,
                    "emotion_score": 0.68,
                    "story_score": 0.64,
                    "speaker_turns": 1,
                    "speaker_names": ["Ben"],
                    "shot_role": "dialogue_exchange",
                    "subtitle_text": "Then say it to my face.",
                    "scene_summary": "He pushes back without moving an inch.",
                },
            ],
        )

        self.assertEqual(resolved["id"], "general")
        self.assertEqual(resolved["signal_route"], "dialogue_driven")
        self.assertIn("dialogue_driven", resolved["signal_modifiers"])
        self.assertGreater(resolved["signal_metrics"]["speech_density"], 0.55)
        self.assertGreater(
            resolved["evidence_weights"]["dialogue_exchange"],
            base["evidence_weights"]["dialogue_exchange"],
        )

    def test_resolve_profile_adapts_explicit_action_to_low_text_kinetic_signal(self):
        base = profile.get_highlight_profile("action")
        resolved = profile.resolve_highlight_profile(
            requested_profile="action",
            subtitle_segments=[],
            plot_chunks=[],
            candidate_clips=[
                {
                    "dialogue_exchange_score": 0.08,
                    "relation_score": 0.1,
                    "reaction_score": 0.12,
                    "inner_state_support": 0.06,
                    "group_reaction_score": 0.22,
                    "visible_action_score": 0.92,
                    "energy_score": 0.9,
                    "emotion_score": 0.42,
                    "story_score": 0.62,
                    "raw_audio_worthy": True,
                    "audio_signal_score": 0.82,
                    "audio_peak_score": 0.88,
                    "shot_role": "action_follow",
                    "tags": ["conflict", "audio_peak"],
                    "scene_summary": "",
                    "subtitle_text": "",
                }
            ],
        )

        self.assertEqual(resolved["id"], "action")
        self.assertEqual(resolved["source"], "user_selected")
        self.assertEqual(resolved["signal_route"], "visual_audio_fallback")
        self.assertIn("kinetic", resolved["signal_modifiers"])
        self.assertIn("low_text", resolved["signal_modifiers"])
        self.assertGreater(resolved["raw_audio_bias"], base["raw_audio_bias"])
        self.assertGreater(
            resolved["evidence_weights"]["visible_action"],
            base["evidence_weights"]["visible_action"],
        )

    def test_apply_highlight_profile_boosts_action_clip_for_action_profile(self):
        resolved = profile.resolve_highlight_profile(requested_profile="action")
        profiled = profile.apply_highlight_profile(
            [
                {
                    "clip_id": "dialogue_clip",
                    "story_stage_hint": "setup",
                    "total_score": 0.72,
                    "story_score": 0.74,
                    "emotion_score": 0.42,
                    "energy_score": 0.22,
                    "visible_action_score": 0.08,
                    "reaction_score": 0.2,
                    "inner_state_support": 0.22,
                    "relation_score": 0.36,
                    "group_reaction_score": 0.2,
                    "dialogue_exchange_score": 0.58,
                    "story_position": 0.1,
                    "tags": ["setup"],
                    "shot_role": "dialogue_exchange",
                    "raw_audio_worthy": False,
                    "scene_summary": "Two people explain the plan.",
                },
                {
                    "clip_id": "action_clip",
                    "story_stage_hint": "conflict",
                    "total_score": 0.68,
                    "story_score": 0.7,
                    "emotion_score": 0.5,
                    "energy_score": 0.86,
                    "visible_action_score": 0.88,
                    "reaction_score": 0.26,
                    "inner_state_support": 0.12,
                    "relation_score": 0.18,
                    "group_reaction_score": 0.62,
                    "dialogue_exchange_score": 0.14,
                    "story_position": 0.58,
                    "tags": ["conflict", "emotion_peak"],
                    "shot_role": "action_follow",
                    "raw_audio_worthy": True,
                    "scene_summary": "Gunfire erupts and the squad charges forward.",
                },
            ],
            resolved,
        )

        by_id = {item["clip_id"]: item for item in profiled}
        self.assertEqual(by_id["action_clip"]["highlight_profile_id"], "action")
        self.assertGreater(by_id["action_clip"]["profile_total_score"], by_id["dialogue_clip"]["profile_total_score"])
        self.assertGreater(by_id["action_clip"]["profile_fit_score"], by_id["dialogue_clip"]["profile_fit_score"])

    def test_apply_highlight_profile_penalizes_intro_risk_setup_clip(self):
        resolved = profile.resolve_highlight_profile(requested_profile="general")
        profiled = profile.apply_highlight_profile(
            [
                {
                    "clip_id": "opening_setup",
                    "story_stage_hint": "opening",
                    "story_position": 0.04,
                    "total_score": 0.86,
                    "story_score": 0.78,
                    "emotion_score": 0.28,
                    "energy_score": 0.16,
                    "visible_action_score": 0.08,
                    "reaction_score": 0.12,
                    "inner_state_support": 0.14,
                    "relation_score": 0.1,
                    "group_reaction_score": 0.08,
                    "dialogue_exchange_score": 0.12,
                    "tags": [],
                    "shot_role": "narrative_bridge",
                    "raw_audio_worthy": False,
                    "scene_summary": "A calm introduction to the setting.",
                    "subtitle_text": "People casually greet each other.",
                },
                {
                    "clip_id": "mid_conflict",
                    "story_stage_hint": "conflict",
                    "story_position": 0.48,
                    "total_score": 0.74,
                    "story_score": 0.74,
                    "emotion_score": 0.62,
                    "energy_score": 0.48,
                    "visible_action_score": 0.42,
                    "reaction_score": 0.5,
                    "inner_state_support": 0.28,
                    "relation_score": 0.36,
                    "group_reaction_score": 0.34,
                    "dialogue_exchange_score": 0.3,
                    "tags": ["conflict"],
                    "shot_role": "dialogue_exchange",
                    "raw_audio_worthy": True,
                    "scene_summary": "The confrontation suddenly escalates.",
                    "subtitle_text": "They stop pretending and start accusing each other.",
                },
            ],
            resolved,
        )

        by_id = {item["clip_id"]: item for item in profiled}
        self.assertGreater(by_id["opening_setup"]["intro_risk_score"], 0.6)
        self.assertGreater(by_id["opening_setup"]["profile_intro_penalty"], 0.08)
        self.assertLess(by_id["opening_setup"]["profile_total_score"], by_id["mid_conflict"]["profile_total_score"])
        self.assertIn("intro_penalized", by_id["opening_setup"]["selection_reason"])


if __name__ == "__main__":
    unittest.main()
