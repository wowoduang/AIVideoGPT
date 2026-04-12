import glob
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class _Logger:
    def exception(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None


def _stub_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def _load_highlight_pipeline_module():
    loguru_module = _stub_module("loguru", logger=_Logger())
    utils_module = _stub_module(
        "app.utils.utils",
        md5=lambda value: "stub-md5",
    )
    app_utils_module = _stub_module("app.utils", utils=utils_module)
    composition_plan_adapter_module = _stub_module(
        "app.services.composition_plan_adapter",
        composition_plan_to_script_items=lambda plan: list(plan.get("segments") or []),
    )
    plot_chunker_module = _stub_module(
        "app.services.plot_chunker",
        build_plot_chunks_from_subtitles=lambda *args, **kwargs: [],
    )
    scene_builder_module = _stub_module(
        "app.services.scene_builder",
        build_scenes=lambda *args, **kwargs: [],
        build_video_boundary_candidates=lambda *args, **kwargs: [],
    )
    subtitle_pipeline_module = _stub_module(
        "app.services.subtitle_pipeline",
        build_subtitle_segments=lambda *args, **kwargs: {"segments": []},
    )

    stubbed_modules = {
        "loguru": loguru_module,
        "app.utils": app_utils_module,
        "app.utils.utils": utils_module,
        "app.services.composition_plan_adapter": composition_plan_adapter_module,
        "app.services.plot_chunker": plot_chunker_module,
        "app.services.scene_builder": scene_builder_module,
        "app.services.subtitle_pipeline": subtitle_pipeline_module,
    }
    with patch.dict(sys.modules, stubbed_modules):
        sys.modules.pop("app.services.highlight_edit_pipeline", None)
        return importlib.import_module("app.services.highlight_edit_pipeline")


def _resolve_test_video_path() -> str:
    video_candidates = []
    for suffix in ("*.mp4", "*.mov", "*.avi", "*.mkv", "*.flv"):
        video_candidates.extend(glob.glob(os.path.join(os.getcwd(), "resource", "videos", suffix)))
    if video_candidates:
        return video_candidates[0]

    temp_dir = os.path.join(tempfile.gettempdir(), "aivideogpt_test_videos")
    os.makedirs(temp_dir, exist_ok=True)
    placeholder_path = os.path.join(temp_dir, "placeholder.mp4")
    if not os.path.exists(placeholder_path):
        with open(placeholder_path, "wb") as handle:
            handle.write(b"")
    return placeholder_path


class HighlightEditPipelineTests(unittest.TestCase):
    def test_visual_config_falls_back_to_auto_for_unknown_mode(self):
        module = _load_highlight_pipeline_module()

        auto_config = module._resolve_visual_signal_config("auto")
        boost_config = module._resolve_visual_signal_config("boost")
        unknown_config = module._resolve_visual_signal_config("mystery")

        self.assertEqual(unknown_config["mode"], "auto")
        self.assertTrue(boost_config["enabled"])
        self.assertLess(boost_config["boundary_args"]["threshold"], auto_config["boundary_args"]["threshold"])
        self.assertLess(boost_config["scene_preset"]["min_scene_len"], auto_config["scene_preset"]["min_scene_len"])

    def test_highlight_recut_selection_uses_merged_scene_candidates(self):
        module = _load_highlight_pipeline_module()
        captured = {}

        def fake_build_subtitle_segments(*args, **kwargs):
            return {
                "segments": [
                    {"seg_id": "sub_001", "start": 0.0, "end": 3.0, "text": "开场对白"},
                ]
            }

        def fake_build_video_boundary_candidates(*args, **kwargs):
            captured["boundary_kwargs"] = dict(kwargs)
            return [{"time": 2.0, "score": 0.8}]

        def fake_build_scenes(*args, **kwargs):
            captured["scene_mode"] = kwargs.get("mode")
            captured["scene_preset"] = dict(kwargs.get("preset") or {})
            return [
                {
                    "scene_id": "scene_001",
                    "start": 1.0,
                    "end": 4.0,
                    "duration": 3.0,
                    "subtitle_ids": ["sub_001"],
                    "subtitle_texts": ["开场对白"],
                    "subtitle_text": "开场对白",
                    "keyframe_candidates": [1.5, 2.5, 3.5],
                }
            ]

        def fake_build_plot_chunks_from_subtitles(*args, **kwargs):
            return [
                {
                    "start": 0.0,
                    "end": 3.0,
                    "highlight_score": 0.42,
                    "importance_level": "medium",
                    "attraction_level": "medium",
                    "narration_level": "brief",
                    "plot_function": "",
                    "plot_role": "",
                    "aligned_subtitle_text": "开场对白",
                    "real_narrative_state": "人物出场",
                    "surface_dialogue_meaning": "人物出场",
                    "raw_voice_retain_suggestion": False,
                    "subtitle_ids": ["sub_001"],
                    "scene_id": "scene_001",
                }
            ]

        def fake_select_highlight_clips(candidate_clips, top_k=12):
            captured["selection_pool_ids"] = [clip.get("clip_id") for clip in candidate_clips]
            return [clip for clip in candidate_clips if str(clip.get("clip_id", "")).startswith("scene_clip_")]

        module.build_subtitle_segments = fake_build_subtitle_segments
        module.build_video_boundary_candidates = fake_build_video_boundary_candidates
        module.build_scenes = fake_build_scenes
        module.build_plot_chunks_from_subtitles = fake_build_plot_chunks_from_subtitles
        module.select_highlight_clips = fake_select_highlight_clips
        module.plan_highlight_timeline = lambda clips, target_duration_seconds: list(clips)
        module._annotate_audio_signal_context = lambda video_path, candidate_clips, audio_context=None: (
            list(candidate_clips),
            {
                "audio_signal_used": False,
                "audio_signal_clip_count": 0,
                "audio_raw_candidate_count": 0,
                "audio_signal_mean": 0.0,
                "audio_peak_mean": 0.0,
            },
        )
        module._write_outputs = lambda *args, **kwargs: {
            "composition_plan_path": "",
            "script_path": "",
        }

        result = module.run_highlight_edit_pipeline(
            video_path=_resolve_test_video_path(),
            mode="highlight_recut",
            target_duration_seconds=60,
            visual_mode="boost",
        )

        self.assertTrue(result["success"])
        self.assertIn("clip_0001", captured["selection_pool_ids"])
        self.assertIn("scene_clip_0001", captured["selection_pool_ids"])
        self.assertEqual(captured["scene_mode"], "boost")
        self.assertLess(captured["boundary_kwargs"]["threshold"], 27.0)
        self.assertEqual(result["candidate_stats"]["visual_mode"], "boost")
        self.assertEqual(result["candidate_stats"]["plot_candidate_count"], 1)
        self.assertEqual(result["candidate_stats"]["scene_candidate_count"], 1)
        self.assertEqual(result["candidate_stats"]["merged_candidate_count"], 2)
        selected_ids = {clip["clip_id"] for clip in result["selected_clips"]}
        self.assertIn("scene_clip_0001", selected_ids)

    def test_highlight_recut_selection_pool_keeps_story_coverage_and_raw_audio_anchor(self):
        module = _load_highlight_pipeline_module()
        candidate_clips = [
            {
                "clip_id": "opening_peak",
                "start": 0.0,
                "end": 6.0,
                "duration": 6.0,
                "source": "hybrid",
                "story_position": 0.02,
                "story_stage_hint": "opening",
                "story_score": 1.0,
                "emotion_score": 0.6,
                "energy_score": 0.5,
                "total_score": 0.83,
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "setup_scene",
                "start": 12.0,
                "end": 18.0,
                "duration": 6.0,
                "source": "scene",
                "story_position": 0.18,
                "story_stage_hint": "setup",
                "story_score": 0.72,
                "emotion_score": 0.42,
                "energy_score": 0.58,
                "total_score": 0.62,
                "raw_audio_worthy": False,
                "tags": ["scene_refined"],
                "selection_reason": [],
            },
            {
                "clip_id": "raw_mid",
                "start": 35.0,
                "end": 42.0,
                "duration": 7.0,
                "source": "scene",
                "story_position": 0.53,
                "story_stage_hint": "climax",
                "story_score": 0.7,
                "emotion_score": 0.76,
                "energy_score": 0.92,
                "total_score": 0.78,
                "raw_audio_worthy": True,
                "tags": ["emotion_peak", "raw_audio"],
                "selection_reason": [],
            },
            {
                "clip_id": "late_reveal",
                "start": 65.0,
                "end": 72.0,
                "duration": 7.0,
                "source": "hybrid",
                "story_position": 0.84,
                "story_stage_hint": "reveal",
                "story_score": 0.68,
                "emotion_score": 0.52,
                "energy_score": 0.45,
                "total_score": 0.62,
                "raw_audio_worthy": False,
                "tags": ["reveal"],
                "selection_reason": [],
            },
            {
                "clip_id": "ending_anchor",
                "start": 86.0,
                "end": 94.0,
                "duration": 8.0,
                "source": "hybrid",
                "story_position": 0.96,
                "story_stage_hint": "ending",
                "story_score": 0.58,
                "emotion_score": 0.44,
                "energy_score": 0.4,
                "total_score": 0.53,
                "raw_audio_worthy": False,
                "tags": ["ending"],
                "selection_reason": [],
            },
        ]

        pool = module._build_highlight_recut_selection_pool(candidate_clips, target_duration_seconds=180)
        pool_by_id = {clip["clip_id"]: clip for clip in pool}

        self.assertIn("opening_peak", pool_by_id)
        self.assertIn("raw_mid", pool_by_id)
        self.assertIn("ending_anchor", pool_by_id)
        self.assertIn("coverage_anchor", pool_by_id["opening_peak"]["selection_reason"])
        self.assertIn("opening_anchor", pool_by_id["opening_peak"]["selection_reason"])
        self.assertIn("raw_audio_anchor", pool_by_id["raw_mid"]["selection_reason"])
        self.assertIn("ending_anchor", pool_by_id["ending_anchor"]["selection_reason"])

    def test_highlight_recut_selection_pool_marks_peak_window_anchor(self):
        module = _load_highlight_pipeline_module()
        candidate_clips = [
            {
                "clip_id": "window_lead_in",
                "start": 10.0,
                "end": 12.0,
                "duration": 2.0,
                "source": "scene",
                "source_scene_id": "scene_peak",
                "story_position": 0.42,
                "story_stage_hint": "conflict",
                "story_score": 0.68,
                "emotion_score": 0.56,
                "energy_score": 0.62,
                "audio_signal_score": 0.58,
                "audio_peak_score": 0.51,
                "total_score": 0.72,
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "window_core",
                "start": 12.2,
                "end": 14.6,
                "duration": 2.4,
                "source": "scene",
                "source_scene_id": "scene_peak",
                "story_position": 0.46,
                "story_stage_hint": "climax",
                "story_score": 0.84,
                "emotion_score": 0.86,
                "energy_score": 0.8,
                "audio_signal_score": 0.71,
                "audio_peak_score": 0.9,
                "total_score": 0.88,
                "raw_audio_worthy": True,
                "tags": ["conflict", "emotion_peak", "audio_peak"],
                "selection_reason": [],
            },
            {
                "clip_id": "window_release",
                "start": 15.0,
                "end": 17.5,
                "duration": 2.5,
                "source": "scene",
                "source_scene_id": "scene_peak",
                "story_position": 0.5,
                "story_stage_hint": "climax",
                "story_score": 0.8,
                "emotion_score": 0.71,
                "energy_score": 0.69,
                "audio_signal_score": 0.63,
                "audio_peak_score": 0.64,
                "total_score": 0.8,
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "far_scene",
                "start": 48.0,
                "end": 52.0,
                "duration": 4.0,
                "source": "hybrid",
                "source_scene_id": "scene_far",
                "story_position": 0.8,
                "story_stage_hint": "reveal",
                "story_score": 0.61,
                "emotion_score": 0.4,
                "energy_score": 0.35,
                "audio_signal_score": 0.2,
                "audio_peak_score": 0.18,
                "total_score": 0.55,
                "raw_audio_worthy": False,
                "tags": ["reveal"],
                "selection_reason": [],
            },
        ]

        pool = module._build_highlight_recut_selection_pool(candidate_clips, target_duration_seconds=90)
        pool_by_id = {clip["clip_id"]: clip for clip in pool}

        self.assertIn("window_core", pool_by_id)
        self.assertIn("peak_window", pool_by_id["window_core"]["selection_reason"])
        self.assertEqual(pool_by_id["window_core"]["peak_window_start"], 10.0)
        self.assertEqual(pool_by_id["window_core"]["peak_window_end"], 17.5)
        self.assertEqual(pool_by_id["window_core"]["peak_window_duration"], 7.5)
        self.assertEqual(
            pool_by_id["window_core"]["peak_window_clip_ids"],
            ["window_lead_in", "window_core", "window_release"],
        )
        self.assertGreater(pool_by_id["window_core"]["peak_window_strength"], 0.95)

    def test_highlight_recut_peak_window_snaps_to_subtitle_and_plot_boundaries(self):
        module = _load_highlight_pipeline_module()
        candidate_clips = [
            {
                "clip_id": "dialogue_a",
                "start": 10.2,
                "end": 12.0,
                "duration": 1.8,
                "source": "scene",
                "source_scene_id": "scene_dialogue",
                "source_segment_ids": ["sub_001"],
                "story_position": 0.38,
                "story_stage_hint": "conflict",
                "story_score": 0.7,
                "emotion_score": 0.66,
                "energy_score": 0.38,
                "audio_signal_score": 0.32,
                "audio_peak_score": 0.28,
                "total_score": 0.72,
                "reaction_score": 0.74,
                "relation_score": 0.78,
                "dialogue_exchange_score": 0.84,
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "dialogue_b",
                "start": 12.1,
                "end": 14.4,
                "duration": 2.3,
                "source": "scene",
                "source_scene_id": "scene_dialogue",
                "source_segment_ids": ["sub_002"],
                "story_position": 0.41,
                "story_stage_hint": "turning_point",
                "story_score": 0.82,
                "emotion_score": 0.84,
                "energy_score": 0.42,
                "audio_signal_score": 0.36,
                "audio_peak_score": 0.34,
                "total_score": 0.88,
                "reaction_score": 0.8,
                "relation_score": 0.82,
                "dialogue_exchange_score": 0.88,
                "raw_audio_worthy": False,
                "tags": ["conflict", "emotion_peak"],
                "selection_reason": [],
            },
            {
                "clip_id": "dialogue_c",
                "start": 14.5,
                "end": 16.8,
                "duration": 2.3,
                "source": "scene",
                "source_scene_id": "scene_dialogue",
                "source_segment_ids": ["sub_003"],
                "story_position": 0.45,
                "story_stage_hint": "climax",
                "story_score": 0.8,
                "emotion_score": 0.76,
                "energy_score": 0.44,
                "audio_signal_score": 0.38,
                "audio_peak_score": 0.36,
                "total_score": 0.82,
                "reaction_score": 0.76,
                "relation_score": 0.8,
                "dialogue_exchange_score": 0.82,
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
        ]
        subtitle_segments = [
            {"seg_id": "sub_001", "start": 9.6, "end": 12.0, "text": "Tell me the truth.", "speaker": "Ava"},
            {"seg_id": "sub_002", "start": 12.0, "end": 14.8, "text": "You already knew everything.", "speaker": "Ben"},
            {"seg_id": "sub_003", "start": 14.8, "end": 17.8, "text": "Then stop lying to me.", "speaker": "Ava"},
        ]
        plot_chunks = [
            {
                "start": 9.4,
                "end": 18.0,
                "highlight_score": 0.81,
                "subtitle_ids": ["sub_001", "sub_002", "sub_003"],
                "real_narrative_state": "A confrontation spirals into a direct accusation.",
            }
        ]
        highlight_profile = {
            "signal_route": "dialogue_driven",
            "signal_metrics": {"text_reliability": 0.84},
        }

        pool = module._build_highlight_recut_selection_pool(
            candidate_clips,
            target_duration_seconds=90,
            subtitle_segments=subtitle_segments,
            plot_chunks=plot_chunks,
            highlight_profile=highlight_profile,
        )
        pool_by_id = {clip["clip_id"]: clip for clip in pool}

        self.assertIn("dialogue_b", pool_by_id)
        self.assertEqual(pool_by_id["dialogue_b"]["peak_window_start"], 9.4)
        self.assertEqual(pool_by_id["dialogue_b"]["peak_window_end"], 18.0)
        self.assertEqual(pool_by_id["dialogue_b"]["peak_window_duration"], 8.6)
        self.assertIn("subtitle_boundary_snap", pool_by_id["dialogue_b"]["selection_reason"])
        self.assertIn("plot_boundary_snap", pool_by_id["dialogue_b"]["selection_reason"])
        self.assertGreater(pool_by_id["dialogue_b"]["peak_window_text_score"], 0.55)
        self.assertGreater(pool_by_id["dialogue_b"]["peak_window_dialogue_score"], 0.46)
        self.assertIn("text_complete_window", pool_by_id["dialogue_b"]["selection_reason"])
        self.assertIn("dialogue_cycle_window", pool_by_id["dialogue_b"]["selection_reason"])

    def test_highlight_recut_peak_window_tracks_main_character_reference(self):
        module = _load_highlight_pipeline_module()
        candidate_clips = [
            {
                "clip_id": "hero_focus_a",
                "start": 40.0,
                "end": 42.2,
                "duration": 2.2,
                "source": "scene",
                "source_scene_id": "scene_hero",
                "source_segment_ids": ["sub_201"],
                "story_position": 0.44,
                "story_stage_hint": "conflict",
                "story_score": 0.72,
                "emotion_score": 0.66,
                "energy_score": 0.42,
                "total_score": 0.76,
                "reaction_score": 0.78,
                "relation_score": 0.62,
                "dialogue_exchange_score": 0.58,
                "character_names": ["Hero"],
                "speaker_names": ["Hero"],
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "hero_focus_b",
                "start": 42.3,
                "end": 45.1,
                "duration": 2.8,
                "source": "scene",
                "source_scene_id": "scene_hero",
                "source_segment_ids": ["sub_202"],
                "story_position": 0.48,
                "story_stage_hint": "turning_point",
                "story_score": 0.84,
                "emotion_score": 0.82,
                "energy_score": 0.5,
                "total_score": 0.88,
                "reaction_score": 0.84,
                "relation_score": 0.74,
                "dialogue_exchange_score": 0.72,
                "character_names": ["Hero", "Villain"],
                "speaker_names": ["Villain"],
                "pressure_target_names": ["Hero"],
                "raw_audio_worthy": True,
                "tags": ["conflict", "emotion_peak"],
                "selection_reason": [],
            },
            {
                "clip_id": "hero_focus_c",
                "start": 45.2,
                "end": 48.1,
                "duration": 2.9,
                "source": "scene",
                "source_scene_id": "scene_hero",
                "source_segment_ids": ["sub_203"],
                "story_position": 0.52,
                "story_stage_hint": "climax",
                "story_score": 0.8,
                "emotion_score": 0.78,
                "energy_score": 0.48,
                "total_score": 0.84,
                "reaction_score": 0.82,
                "relation_score": 0.7,
                "dialogue_exchange_score": 0.64,
                "character_names": ["Hero"],
                "speaker_names": ["Hero"],
                "pressure_target_names": ["Hero"],
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "side_scene",
                "start": 70.0,
                "end": 73.0,
                "duration": 3.0,
                "source": "hybrid",
                "source_scene_id": "scene_side",
                "story_position": 0.8,
                "story_stage_hint": "reveal",
                "story_score": 0.74,
                "emotion_score": 0.52,
                "energy_score": 0.62,
                "total_score": 0.8,
                "reaction_score": 0.32,
                "relation_score": 0.24,
                "dialogue_exchange_score": 0.08,
                "character_names": ["Witness"],
                "speaker_names": ["Witness"],
                "raw_audio_worthy": True,
                "tags": ["reveal", "audio_peak"],
                "selection_reason": [],
            },
        ]
        subtitle_segments = [
            {"seg_id": "sub_201", "start": 39.7, "end": 42.2, "text": "Hero realizes the trap.", "speaker": "Hero"},
            {"seg_id": "sub_202", "start": 42.2, "end": 45.1, "text": "Villain presses Hero into confessing.", "speaker": "Villain"},
            {"seg_id": "sub_203", "start": 45.1, "end": 48.3, "text": "Hero finally snaps back.", "speaker": "Hero"},
        ]
        plot_chunks = [
            {
                "start": 39.6,
                "end": 48.5,
                "highlight_score": 0.86,
                "subtitle_ids": ["sub_201", "sub_202", "sub_203"],
                "real_narrative_state": "Hero is cornered before fighting back.",
            }
        ]
        highlight_profile = {
            "signal_route": "performance_reaction",
            "signal_metrics": {"text_reliability": 0.82},
        }

        pool = module._build_highlight_recut_selection_pool(
            candidate_clips,
            target_duration_seconds=90,
            subtitle_segments=subtitle_segments,
            plot_chunks=plot_chunks,
            highlight_profile=highlight_profile,
        )
        pool_by_id = {clip["clip_id"]: clip for clip in pool}

        self.assertIn("hero_focus_b", pool_by_id)
        self.assertGreater(pool_by_id["hero_focus_b"]["peak_window_character_score"], 0.42)
        self.assertIn("main_character_window", pool_by_id["hero_focus_b"]["selection_reason"])
        self.assertIn("main_character_anchor", pool_by_id["hero_focus_b"]["selection_reason"])

    def test_highlight_recut_peak_window_marks_payoff_arc(self):
        module = _load_highlight_pipeline_module()
        candidate_clips = [
            {
                "clip_id": "payoff_setup",
                "start": 30.0,
                "end": 32.0,
                "duration": 2.0,
                "source": "hybrid",
                "source_scene_id": "scene_payoff",
                "source_segment_ids": ["sub_101"],
                "story_position": 0.52,
                "story_stage_hint": "conflict",
                "story_score": 0.66,
                "emotion_score": 0.48,
                "energy_score": 0.42,
                "audio_signal_score": 0.32,
                "audio_peak_score": 0.3,
                "total_score": 0.68,
                "raw_audio_worthy": False,
                "tags": ["conflict"],
                "selection_reason": [],
            },
            {
                "clip_id": "payoff_peak",
                "start": 32.1,
                "end": 35.0,
                "duration": 2.9,
                "source": "hybrid",
                "source_scene_id": "scene_payoff",
                "source_segment_ids": ["sub_102"],
                "story_position": 0.56,
                "story_stage_hint": "turning_point",
                "story_score": 0.82,
                "emotion_score": 0.8,
                "energy_score": 0.58,
                "audio_signal_score": 0.61,
                "audio_peak_score": 0.75,
                "total_score": 0.86,
                "raw_audio_worthy": True,
                "tags": ["conflict", "emotion_peak", "audio_peak"],
                "selection_reason": [],
            },
            {
                "clip_id": "payoff_reveal",
                "start": 35.2,
                "end": 38.4,
                "duration": 3.2,
                "source": "hybrid",
                "source_scene_id": "scene_payoff",
                "source_segment_ids": ["sub_103"],
                "story_position": 0.6,
                "story_stage_hint": "reveal",
                "story_score": 0.9,
                "emotion_score": 0.76,
                "energy_score": 0.64,
                "audio_signal_score": 0.66,
                "audio_peak_score": 0.82,
                "total_score": 0.91,
                "raw_audio_worthy": True,
                "tags": ["reveal", "emotion_peak", "audio_peak"],
                "selection_reason": [],
            },
        ]
        subtitle_segments = [
            {"seg_id": "sub_101", "start": 29.8, "end": 32.0, "text": "Something feels wrong here."},
            {"seg_id": "sub_102", "start": 32.0, "end": 35.0, "text": "Say it if you know the truth."},
            {"seg_id": "sub_103", "start": 35.0, "end": 38.8, "text": "He admits he was behind everything."},
        ]
        plot_chunks = [
            {
                "start": 29.6,
                "end": 39.0,
                "highlight_score": 0.88,
                "plot_function": "reveal",
                "subtitle_ids": ["sub_101", "sub_102", "sub_103"],
                "real_narrative_state": "The accusation turns into a full confession.",
            }
        ]
        highlight_profile = {
            "signal_route": "performance_reaction",
            "signal_metrics": {"text_reliability": 0.78},
        }

        pool = module._build_highlight_recut_selection_pool(
            candidate_clips,
            target_duration_seconds=90,
            subtitle_segments=subtitle_segments,
            plot_chunks=plot_chunks,
            highlight_profile=highlight_profile,
        )
        pool_by_id = {clip["clip_id"]: clip for clip in pool}

        self.assertIn("payoff_reveal", pool_by_id)
        self.assertGreater(pool_by_id["payoff_reveal"]["peak_window_payoff_score"], 0.42)
        self.assertIn("payoff_window", pool_by_id["payoff_reveal"]["selection_reason"])
        self.assertEqual(pool_by_id["payoff_reveal"]["peak_window_start"], 29.6)
        self.assertEqual(pool_by_id["payoff_reveal"]["peak_window_end"], 39.0)

    def test_pipeline_records_audio_signal_stats_when_audio_annotation_is_available(self):
        module = _load_highlight_pipeline_module()

        module.build_subtitle_segments = lambda *args, **kwargs: {
            "segments": [
                {"seg_id": "sub_001", "start": 0.0, "end": 3.0, "text": "The explosion sends everyone running."},
            ]
        }
        module.build_video_boundary_candidates = lambda *args, **kwargs: []
        module.build_scenes = lambda *args, **kwargs: []
        module.build_plot_chunks_from_subtitles = lambda *args, **kwargs: [
            {
                "start": 0.0,
                "end": 5.0,
                "highlight_score": 0.6,
                "importance_level": "medium",
                "attraction_level": "medium",
                "narration_level": "focus",
                "plot_function": "conflict",
                "plot_role": "conflict",
                "aligned_subtitle_text": "The explosion sends everyone running.",
                "real_narrative_state": "A sudden blast turns the scene into chaos.",
                "surface_dialogue_meaning": "A sudden blast turns the scene into chaos.",
                "raw_voice_retain_suggestion": False,
                "subtitle_ids": ["sub_001"],
                "scene_id": "scene_001",
            }
        ]
        module.plan_highlight_timeline = lambda clips, target_duration_seconds: list(clips)
        module.select_highlight_clips = lambda candidate_clips, top_k=12: list(candidate_clips)[:top_k]
        module._annotate_audio_signal_context = lambda video_path, candidate_clips, audio_context=None: (
            list(candidate_clips),
            {
                "audio_signal_used": False,
                "audio_signal_clip_count": 0,
                "audio_raw_candidate_count": 0,
                "audio_signal_mean": 0.0,
                "audio_peak_mean": 0.0,
            },
        )
        module._write_outputs = lambda *args, **kwargs: {
            "composition_plan_path": "",
            "script_path": "",
        }
        module._annotate_audio_signal_context = lambda video_path, candidate_clips, audio_context=None: (
            [
                dict(
                    item,
                    audio_signal_score=0.76,
                    audio_peak_score=0.84,
                    raw_audio_worthy=True,
                    total_score=round(float(item.get("total_score", 0.0) or 0.0) + 0.12, 3),
                )
                for item in (candidate_clips or [])
            ],
            {
                "audio_signal_used": True,
                "audio_signal_clip_count": len(candidate_clips or []),
                "audio_raw_candidate_count": len(candidate_clips or []),
                "audio_signal_mean": 0.76,
                "audio_peak_mean": 0.84,
                "audio_signal_reason": "ok",
            },
        )

        result = module.run_highlight_edit_pipeline(
            video_path=_resolve_test_video_path(),
            mode="highlight_recut",
            target_duration_seconds=60,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["candidate_stats"]["plot_audio_stats"]["audio_signal_used"])
        self.assertEqual(result["candidate_stats"]["plot_audio_stats"]["audio_signal_mean"], 0.76)
        self.assertGreaterEqual(result["candidate_stats"]["audio_signal_candidate_count"], 1)
        self.assertTrue(any(bool(item.get("raw_audio_worthy")) for item in result["candidate_clips"]))

    def test_pipeline_threads_explicit_highlight_profile_into_ai_and_metadata(self):
        module = _load_highlight_pipeline_module()
        captured = {}

        module.build_subtitle_segments = lambda *args, **kwargs: {
            "segments": [
                {"seg_id": "sub_001", "start": 0.0, "end": 3.0, "text": "Gunfire erupts in the corridor."},
            ]
        }
        module.build_video_boundary_candidates = lambda *args, **kwargs: []
        module.build_scenes = lambda *args, **kwargs: []
        module.build_plot_chunks_from_subtitles = lambda *args, **kwargs: [
            {
                "start": 0.0,
                "end": 6.0,
                "highlight_score": 0.82,
                "importance_level": "high",
                "attraction_level": "high",
                "narration_level": "focus",
                "plot_function": "conflict",
                "plot_role": "conflict",
                "aligned_subtitle_text": "Gunfire erupts and the squad rushes forward.",
                "real_narrative_state": "The team enters a dangerous firefight.",
                "surface_dialogue_meaning": "The team enters a dangerous firefight.",
                "raw_voice_retain_suggestion": True,
                "subtitle_ids": ["sub_001"],
                "scene_id": "scene_001",
            }
        ]
        module.plan_highlight_timeline = lambda clips, target_duration_seconds: list(clips)
        module.select_highlight_clips = lambda candidate_clips, top_k=12: list(candidate_clips)[:top_k]
        module._write_outputs = lambda *args, **kwargs: {
            "composition_plan_path": "",
            "script_path": "",
        }
        module._annotate_audio_signal_context = lambda video_path, candidate_clips, audio_context=None: (
            list(candidate_clips),
            {
                "audio_signal_used": False,
                "audio_signal_clip_count": 0,
                "audio_raw_candidate_count": 0,
                "audio_signal_mean": 0.0,
                "audio_peak_mean": 0.0,
            },
        )
        module._detect_highlight_capabilities = lambda: {
            "scenedetect_ready": True,
            "librosa_ready": True,
        }
        module._resolve_highlight_profile_context = lambda **kwargs: {
            "id": "action",
            "label": "Action / War",
            "source": "user_selected",
            "confidence": 1.0,
            "reasons": ["user_selected"],
            "signal_route": "kinetic_visual",
            "signal_modifiers": ["kinetic"],
            "signal_reasons": ["kinetic_signal_strong"],
            "signal_metrics": {"kinetic_signal": 0.82, "text_reliability": 0.21},
            "capabilities": dict(kwargs.get("capabilities") or {}),
        }
        module._apply_highlight_profile_context = lambda clips, profile: [
            dict(
                item,
                highlight_profile_id=profile["id"],
                profile_total_score=round(float(item.get("total_score", 0.0) or 0.0) + 0.2, 3),
                total_score=round(float(item.get("total_score", 0.0) or 0.0) + 0.2, 3),
            )
            for item in (clips or [])
        ]

        def fake_ai_highlight_selection(candidate_clips, **kwargs):
            captured["highlight_profile"] = dict(kwargs.get("highlight_profile") or {})
            return {"used_ai": False, "selected_clip_ids": [], "selection_notes": []}

        module._try_ai_highlight_selection = fake_ai_highlight_selection

        result = module.run_highlight_edit_pipeline(
            video_path=_resolve_test_video_path(),
            mode="highlight_recut",
            target_duration_seconds=60,
            highlight_profile="action",
        )

        self.assertTrue(result["success"])
        self.assertEqual(captured["highlight_profile"]["id"], "action")
        self.assertEqual(result["candidate_stats"]["highlight_profile_id"], "action")
        self.assertEqual(result["highlight_profile"]["source"], "user_selected")
        self.assertEqual(result["candidate_stats"]["highlight_signal_route"], "kinetic_visual")
        self.assertIn("kinetic", result["candidate_stats"]["highlight_signal_modifiers"])
        self.assertIsInstance(result["candidate_stats"]["main_character_reference"], list)
        self.assertTrue(result["highlight_capabilities"]["librosa_ready"])

    def test_merge_unique_clips_keeps_combined_reasons_and_more_specific_source(self):
        module = _load_highlight_pipeline_module()
        merged = module._merge_unique_clips(
            [
                {
                    "clip_id": "clip_a",
                    "start": 10.0,
                    "end": 16.0,
                    "duration": 6.0,
                    "source": "hybrid",
                    "story_position": 0.4,
                    "story_score": 0.7,
                    "emotion_score": 0.6,
                    "energy_score": 0.5,
                    "total_score": 0.64,
                    "raw_audio_worthy": False,
                    "selection_reason": ["coverage_anchor"],
                    "tags": ["conflict"],
                    "character_names": ["主角"],
                }
            ],
            [
                {
                    "clip_id": "scene_clip_0003",
                    "start": 10.2,
                    "end": 15.8,
                    "duration": 5.6,
                    "source": "scene",
                    "story_position": 0.41,
                    "story_score": 0.74,
                    "emotion_score": 0.62,
                    "energy_score": 0.7,
                    "total_score": 0.71,
                    "raw_audio_worthy": True,
                    "selection_reason": ["scene_anchor", "raw_audio_keep"],
                    "tags": ["scene_refined"],
                    "character_names": ["反派"],
                    "keyframe_candidates": [11.0, 13.0],
                }
            ],
        )

        self.assertEqual(len(merged), 1)
        merged_clip = merged[0]
        self.assertEqual(merged_clip["source"], "scene")
        self.assertTrue(merged_clip["raw_audio_worthy"])
        self.assertIn("coverage_anchor", merged_clip["selection_reason"])
        self.assertIn("scene_anchor", merged_clip["selection_reason"])
        self.assertIn("主角", merged_clip["character_names"])
        self.assertIn("反派", merged_clip["character_names"])
        self.assertEqual(merged_clip["keyframe_candidates"], [11.0, 13.0])

    def test_scene_candidates_collect_speakers_from_subtitle_segments(self):
        module = _load_highlight_pipeline_module()
        scene_candidates = module._build_scene_candidates(
            scene_segments=[
                {
                    "scene_id": "scene_001",
                    "start": 0.0,
                    "end": 6.0,
                    "subtitle_ids": ["sub_001", "sub_002", "sub_003"],
                    "subtitle_texts": [
                        "\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60",
                        "\u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053",
                        "\u90a3\u6211\u4eec\u73b0\u5728\u8fd8\u600e\u4e48\u529e",
                    ],
                    "subtitle_text": "\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60 \u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053 \u90a3\u6211\u4eec\u73b0\u5728\u8fd8\u600e\u4e48\u529e",
                }
            ],
            plot_chunks=[],
            video_boundary_candidates=[],
            subtitle_segments=[
                {"seg_id": "sub_001", "speaker": "\u5f20\u4e09", "text": "\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60"},
                {"seg_id": "sub_002", "speaker": "\u674e\u56db", "text": "\u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053"},
                {"seg_id": "sub_003", "speaker": "\u738b\u4e94", "text": "\u90a3\u6211\u4eec\u73b0\u5728\u8fd8\u600e\u4e48\u529e"},
            ],
        )

        self.assertEqual(len(scene_candidates), 1)
        self.assertEqual(scene_candidates[0]["speaker_names"], ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"])
        self.assertEqual(scene_candidates[0]["speaker_sequence"], ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"])
        self.assertEqual(
            scene_candidates[0]["exchange_pairs"],
            ["\u5f20\u4e09->\u674e\u56db", "\u674e\u56db->\u738b\u4e94"],
        )
        self.assertEqual(scene_candidates[0]["speaker_turns"], 3)
        self.assertEqual(scene_candidates[0]["shot_role"], "dialogue_exchange")

    def test_scene_candidates_derive_pressure_direction_from_subtitle_segments(self):
        module = _load_highlight_pipeline_module()
        scene_candidates = module._build_scene_candidates(
            scene_segments=[
                {
                    "scene_id": "scene_002",
                    "start": 10.0,
                    "end": 16.5,
                    "subtitle_ids": ["sub_101", "sub_102", "sub_103", "sub_104"],
                    "subtitle_texts": [
                        "\u4f60\u8bf4",
                        "\u6211\u6ca1\u4ec0\u4e48\u53ef\u8bf4\u7684",
                        "\u4f60\u8fd8\u60f3\u88c5\u5230\u4ec0\u4e48\u65f6\u5019",
                        "\u6211\u771f\u7684\u6ca1\u9a97\u4f60\u4eec",
                    ],
                    "subtitle_text": "\u4f60\u8bf4 \u6211\u6ca1\u4ec0\u4e48\u53ef\u8bf4\u7684 \u4f60\u8fd8\u60f3\u88c5\u5230\u4ec0\u4e48\u65f6\u5019 \u6211\u771f\u7684\u6ca1\u9a97\u4f60\u4eec",
                }
            ],
            plot_chunks=[],
            video_boundary_candidates=[],
            subtitle_segments=[
                {"seg_id": "sub_101", "speaker": "\u5f20\u4e09", "text": "\u4f60\u8bf4"},
                {"seg_id": "sub_102", "speaker": "\u738b\u4e94", "text": "\u6211\u6ca1\u4ec0\u4e48\u53ef\u8bf4\u7684"},
                {"seg_id": "sub_103", "speaker": "\u674e\u56db", "text": "\u4f60\u8fd8\u60f3\u88c5\u5230\u4ec0\u4e48\u65f6\u5019"},
                {"seg_id": "sub_104", "speaker": "\u738b\u4e94", "text": "\u6211\u771f\u7684\u6ca1\u9a97\u4f60\u4eec"},
            ],
        )

        self.assertEqual(len(scene_candidates), 1)
        self.assertEqual(scene_candidates[0]["pressure_target_names"], ["\u738b\u4e94"])
        self.assertEqual(scene_candidates[0]["pressure_source_names"], ["\u5f20\u4e09", "\u674e\u56db"])
        self.assertGreater(scene_candidates[0]["group_reaction_score"], 0.7)


if __name__ == "__main__":
    unittest.main()
