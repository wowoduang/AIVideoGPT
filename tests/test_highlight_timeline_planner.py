import unittest

from app.services.highlight_timeline_planner import plan_highlight_timeline


class HighlightTimelinePlannerTests(unittest.TestCase):
    def test_opening_and_ending_anchors_drive_trim_direction(self):
        planned = plan_highlight_timeline(
            [
                {
                    "clip_id": "opening_anchor_clip",
                    "start": 0.0,
                    "end": 24.0,
                    "duration": 24.0,
                    "total_score": 0.62,
                    "story_score": 0.58,
                    "emotion_score": 0.34,
                    "energy_score": 0.4,
                    "raw_audio_worthy": False,
                    "selection_reason": ["coverage_anchor", "opening_anchor"],
                    "tags": [],
                },
                {
                    "clip_id": "ending_anchor_clip",
                    "start": 48.0,
                    "end": 72.0,
                    "duration": 24.0,
                    "total_score": 0.66,
                    "story_score": 0.6,
                    "emotion_score": 0.4,
                    "energy_score": 0.46,
                    "raw_audio_worthy": False,
                    "selection_reason": ["coverage_anchor", "ending_anchor"],
                    "tags": ["ending"],
                },
            ],
            target_duration_seconds=30,
        )

        self.assertEqual(len(planned), 2)
        planned_by_id = {clip["clip_id"]: clip for clip in planned}
        self.assertEqual(planned_by_id["opening_anchor_clip"]["trim_strategy"], "head")
        self.assertEqual(planned_by_id["ending_anchor_clip"]["trim_strategy"], "tail")

    def test_peak_window_can_expand_trim_bounds(self):
        planned = plan_highlight_timeline(
            [
                {
                    "clip_id": "peak_window_clip",
                    "start": 20.0,
                    "end": 23.0,
                    "duration": 3.0,
                    "total_score": 0.84,
                    "story_score": 0.8,
                    "emotion_score": 0.72,
                    "energy_score": 0.7,
                    "raw_audio_worthy": True,
                    "selection_reason": ["peak_window", "story_peak"],
                    "tags": ["conflict", "audio_peak"],
                    "peak_window_start": 18.0,
                    "peak_window_end": 26.0,
                    "peak_window_duration": 8.0,
                    "peak_window_strength": 1.08,
                    "peak_window_clip_ids": ["w1", "w2", "w3"],
                },
            ],
            target_duration_seconds=8,
        )

        self.assertEqual(len(planned), 1)
        clip = planned[0]
        self.assertEqual(clip["original_start"], 20.0)
        self.assertEqual(clip["original_end"], 23.0)
        self.assertEqual(clip["start"], 18.0)
        self.assertEqual(clip["end"], 26.0)
        self.assertEqual(clip["duration"], 8.0)
        self.assertEqual(clip["planned_duration"], 8.0)


if __name__ == "__main__":
    unittest.main()
