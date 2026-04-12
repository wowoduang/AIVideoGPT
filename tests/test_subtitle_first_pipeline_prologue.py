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


def _time_to_seconds(value: str) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    if text.replace(".", "", 1).isdigit():
        return float(text)
    time_part, ms_part = (text.split(",", 1) + ["0"])[:2]
    hh, mm, ss = [int(piece) for piece in time_part.split(":")]
    return hh * 3600 + mm * 60 + ss + int(ms_part.ljust(3, "0")[:3]) / 1000.0


def _format_time(seconds: float) -> str:
    total_ms = int(round(max(float(seconds or 0.0), 0.0) * 1000))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _load_subtitle_first_pipeline():
    loguru_module = _stub_module("loguru", logger=_Logger())
    utils_module = _stub_module(
        "app.utils.utils",
        time_to_seconds=_time_to_seconds,
        format_time=_format_time,
        temp_dir=lambda *_args, **_kwargs: ".",
        md5=lambda value: f"md5-{value}",
        script_dir=lambda: ".",
    )
    app_utils_module = _stub_module("app.utils", utils=utils_module)

    stubbed_modules = {
        "loguru": loguru_module,
        "app.utils": app_utils_module,
        "app.utils.utils": utils_module,
        "app.services.evidence_fuser": _stub_module("app.services.evidence_fuser", fuse_scene_evidence=lambda **kwargs: []),
        "app.services.generate_narration_script_clean": _stub_module(
            "app.services.generate_narration_script_clean",
            generate_narration_from_scene_evidence=lambda **kwargs: [],
        ),
        "app.services.plot_chunker": _stub_module(
            "app.services.plot_chunker",
            build_plot_chunks_from_subtitles=lambda *args, **kwargs: [],
        ),
        "app.services.scene_builder": _stub_module(
            "app.services.scene_builder",
            build_video_boundary_candidates=lambda *args, **kwargs: [],
            detect_scenes_from_video=lambda *args, **kwargs: [],
        ),
        "app.services.plot_understanding_clean": _stub_module(
            "app.services.plot_understanding_clean",
            add_local_understanding=lambda evidence, **kwargs: evidence,
            build_full_subtitle_understanding=lambda *args, **kwargs: {},
            build_global_summary=lambda *args, **kwargs: {},
            plan_story_highlights=lambda *args, **kwargs: {},
        ),
        "app.services.preflight_check": _stub_module(
            "app.services.preflight_check",
            PreflightError=RuntimeError,
            validate_script_items=lambda *args, **kwargs: None,
        ),
        "app.services.representative_frames": _stub_module(
            "app.services.representative_frames",
            extract_representative_frames_for_scenes=lambda **kwargs: [],
        ),
        "app.services.script_fallback": _stub_module(
            "app.services.script_fallback",
            ensure_script_shape=lambda items: items,
        ),
        "app.services.story_boundary_aligner": _stub_module(
            "app.services.story_boundary_aligner",
            align_story_boundaries=lambda items, **kwargs: items,
            collect_candidate_boundaries=lambda *_args, **_kwargs: [],
        ),
        "app.services.story_validator_clean": _stub_module(
            "app.services.story_validator_clean",
            validate_story_segments=lambda scene_evidence, **kwargs: scene_evidence,
        ),
        "app.services.subtitle_pipeline": _stub_module(
            "app.services.subtitle_pipeline",
            build_subtitle_segments=lambda **kwargs: {"segments": []},
        ),
    }
    with patch.dict(sys.modules, stubbed_modules):
        sys.modules.pop("app.services.subtitle_first_pipeline", None)
        return importlib.import_module("app.services.subtitle_first_pipeline")


class SubtitleFirstPipelinePrologueTests(unittest.TestCase):
    def test_resolve_prologue_end_prefers_first_speech(self):
        module = _load_subtitle_first_pipeline()
        updated, warnings = module._resolve_prologue_end_from_strategy(
            full_subtitle_understanding={"prologue_end_time": "00:00:18,000"},
            subtitle_segments=[
                {"start": 0.0, "end": 0.5, "text": "[BGM]"},
                {"start": 12.4, "end": 14.2, "text": "终于开口说话"},
            ],
            scene_overrides={"prologue_strategy": "speech_first"},
        )

        self.assertEqual(updated["resolved_prologue_end_source"], "first_speech")
        self.assertEqual(updated["resolved_prologue_end_seconds"], 12.4)
        self.assertEqual(updated["prologue_end_time"], "00:00:12,400")
        self.assertEqual(warnings, [])

    def test_resolve_prologue_end_manual_time_overrides_llm(self):
        module = _load_subtitle_first_pipeline()
        updated, warnings = module._resolve_prologue_end_from_strategy(
            full_subtitle_understanding={"prologue_end_time": "00:00:18,000"},
            subtitle_segments=[
                {"start": 12.4, "end": 14.2, "text": "终于开口说话"},
            ],
            scene_overrides={
                "prologue_strategy": "manual_time",
                "manual_prologue_end_time": "00:00:09,500",
            },
        )

        self.assertEqual(updated["resolved_prologue_end_source"], "manual_time")
        self.assertEqual(updated["resolved_prologue_end_seconds"], 9.5)
        self.assertEqual(updated["prologue_end_time"], "00:00:09,500")
        self.assertEqual(warnings, [])

    def test_resolve_prologue_end_invalid_manual_falls_back_to_first_speech(self):
        module = _load_subtitle_first_pipeline()
        updated, warnings = module._resolve_prologue_end_from_strategy(
            full_subtitle_understanding={"prologue_end_time": "00:00:18,000"},
            subtitle_segments=[
                {"start": 11.0, "end": 12.0, "text": "说话了"},
            ],
            scene_overrides={
                "prologue_strategy": "manual_time",
                "manual_prologue_end_time": "not-a-time",
            },
        )

        self.assertEqual(updated["resolved_prologue_end_source"], "manual_invalid_fallback_first_speech")
        self.assertEqual(updated["resolved_prologue_end_seconds"], 11.0)
        self.assertEqual(warnings, ["manual_prologue_end_time_invalid"])

    def test_resolve_story_end_detects_credits_and_preview_tail(self):
        module = _load_subtitle_first_pipeline()
        updated, warnings = module._resolve_story_end_from_tail_markers(
            full_subtitle_understanding={},
            subtitle_segments=[
                {"seg_id": "seg_001", "start": 0.0, "end": 5.0, "text": "正文开场"},
                {"seg_id": "seg_090", "start": 2398.0, "end": 2409.5, "text": "真正结尾"},
                {"seg_id": "seg_091", "start": 2410.0, "end": 2413.0, "text": "[片尾曲]"},
                {"seg_id": "seg_092", "start": 2420.0, "end": 2434.0, "text": "下集预告"},
            ],
        )

        self.assertEqual([], warnings)
        self.assertEqual("00:40:10,000", updated["story_end_time"])
        self.assertEqual("00:40:10,000", updated["credits_start_time"])
        self.assertEqual("00:40:20,000", updated["preview_start_time"])
        self.assertEqual("credits_auto+preview_auto", updated["resolved_story_end_source"])
        self.assertEqual(2, len(updated["tail_markers"]))

    def test_align_script_items_to_scene_cuts_keeps_trimmed_start_after_prologue(self):
        module = _load_subtitle_first_pipeline()
        script_items = [
            {
                "_id": 1,
                "segment_id": "seg_001",
                "start": 13.0,
                "end": 16.0,
                "OST": 1,
                "prologue_end": 13.0,
                "prologue_trimmed": True,
                "prologue_original_before_prologue_end": True,
            }
        ]

        aligned = module._align_script_items_to_scene_cuts(script_items, [0.0, 20.0, 30.0])

        self.assertEqual(aligned[0]["start"], 13.0)
        self.assertEqual(aligned[0]["scene_group_ranges"][0], [13.0, 20.0])

    def test_align_script_items_to_scene_cuts_respects_story_end_ceiling(self):
        module = _load_subtitle_first_pipeline()
        script_items = [
            {
                "_id": 1,
                "segment_id": "plot_end",
                "start": 2398.0,
                "end": 2410.0,
                "OST": 1,
                "story_end": 2410.0,
                "story_end_trimmed": True,
            }
        ]

        aligned = module._align_script_items_to_scene_cuts(script_items, [2395.0, 2405.0, 2412.0, 2420.0])

        self.assertEqual(2410.0, aligned[0]["end"])
        self.assertEqual([2405.0, 2410.0], aligned[0]["scene_group_ranges"][-1])

    def test_select_final_story_evidence_does_not_restore_prologue_as_context(self):
        module = _load_subtitle_first_pipeline()
        scene_evidence = [
            {
                "segment_id": "seg_prologue",
                "start": 0.0,
                "end": 12.0,
                "importance_level": "high",
                "plot_function": "信息披露",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "before_prologue_end": True,
                "llm_highlight_selected": False,
                "llm_highlight_rejected": False,
                "llm_raw_voice_keep": False,
                "raw_voice_retain_suggestion": False,
                "need_visual_verify": False,
                "subtitle_text": "序幕",
            },
            {
                "segment_id": "seg_main",
                "start": 13.0,
                "end": 18.0,
                "importance_level": "high",
                "plot_function": "反转",
                "block_type": "emotion",
                "story_validation": {"validator_status": "pass"},
                "before_prologue_end": False,
                "llm_highlight_selected": True,
                "llm_highlight_rejected": False,
                "llm_raw_voice_keep": False,
                "raw_voice_retain_suggestion": False,
                "need_visual_verify": False,
                "subtitle_text": "正文",
            },
        ]

        selected = module._select_final_story_evidence(scene_evidence)
        selected_ids = {item["segment_id"] for item in selected}

        self.assertIn("seg_main", selected_ids)
        self.assertNotIn("seg_prologue", selected_ids)

    def test_select_final_story_evidence_fallback_skips_prologue_segments(self):
        module = _load_subtitle_first_pipeline()
        scene_evidence = [
            {
                "segment_id": "seg_prologue",
                "start": 0.0,
                "end": 12.0,
                "importance_level": "high",
                "plot_function": "信息披露",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "before_prologue_end": True,
                "llm_highlight_selected": False,
                "llm_highlight_rejected": False,
                "llm_raw_voice_keep": False,
                "raw_voice_retain_suggestion": False,
                "need_visual_verify": False,
                "subtitle_text": "序幕",
            },
            {
                "segment_id": "seg_a",
                "start": 13.0,
                "end": 16.0,
                "importance_level": "low",
                "plot_function": "铺垫",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "before_prologue_end": False,
                "llm_highlight_selected": False,
                "llm_highlight_rejected": False,
                "llm_raw_voice_keep": False,
                "raw_voice_retain_suggestion": False,
                "need_visual_verify": False,
                "subtitle_text": "A",
            },
            {
                "segment_id": "seg_b",
                "start": 18.0,
                "end": 21.0,
                "importance_level": "low",
                "plot_function": "铺垫",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "before_prologue_end": False,
                "llm_highlight_selected": False,
                "llm_highlight_rejected": False,
                "llm_raw_voice_keep": False,
                "raw_voice_retain_suggestion": False,
                "need_visual_verify": False,
                "subtitle_text": "B",
            },
            {
                "segment_id": "seg_c",
                "start": 24.0,
                "end": 27.0,
                "importance_level": "low",
                "plot_function": "铺垫",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "before_prologue_end": False,
                "llm_highlight_selected": False,
                "llm_highlight_rejected": False,
                "llm_raw_voice_keep": False,
                "raw_voice_retain_suggestion": False,
                "need_visual_verify": False,
                "subtitle_text": "C",
            },
        ]

        selected = module._select_final_story_evidence(scene_evidence)
        selected_ids = {item["segment_id"] for item in selected}

        self.assertNotIn("seg_prologue", selected_ids)
        self.assertTrue({"seg_a", "seg_b", "seg_c"} & selected_ids)

    def test_apply_full_subtitle_plan_to_chunks_trims_story_end_and_drops_preview(self):
        module = _load_subtitle_first_pipeline()
        filtered = module._apply_full_subtitle_plan_to_chunks(
            [
                {
                    "segment_id": "plot_090",
                    "scene_id": "plot_090",
                    "start": 2398.0,
                    "end": 2414.0,
                    "importance_level": "high",
                    "plot_role": "ending",
                },
                {
                    "segment_id": "plot_091",
                    "scene_id": "plot_091",
                    "start": 2420.0,
                    "end": 2434.0,
                    "importance_level": "medium",
                    "plot_role": "ending",
                },
            ],
            {
                "prologue_end_time": "",
                "story_end_time": "00:40:10,000",
                "highlight_windows": [
                    {"start": "00:39:58,000", "end": "00:40:24,000", "reason": "ending"},
                ],
            },
        )

        self.assertEqual(1, len(filtered))
        self.assertEqual("plot_090", filtered[0]["segment_id"])
        self.assertEqual(2410.0, filtered[0]["end"])
        self.assertTrue(filtered[0]["story_end_trimmed"])
        self.assertFalse(filtered[0]["after_story_end"])

    def test_highlight_filter_marks_overlap_kept_context_as_selected(self):
        module = _load_subtitle_first_pipeline()
        script_items = [
            {
                "_id": 1,
                "segment_id": "plot_017",
                "start": 20.2,
                "end": 24.0,
                "semantic_start": 20.0,
                "semantic_end": 24.0,
                "llm_highlight_selected": False,
                "OST": 2,
                "narration_validation": {"status": "pass"},
            }
        ]
        story_highlights = [
            {"start": 8.0, "end": 12.0, "segment_ids": ["plot_005"]},
            {"start": 19.5, "end": 24.5, "segment_ids": ["plot_016"]},
        ]

        filtered = module._filter_script_items_by_highlights(script_items, story_highlights)
        self.assertEqual(1, len(filtered))
        self.assertTrue(filtered[0]["highlight_filter_selected"])

        issues = module._validate_pipeline_quality(
            full_subtitle_understanding={
                "highlight_windows": [{"start": 8.0, "end": 12.0}, {"start": 19.5, "end": 24.5}],
                "subtitle_input_mode": "chunked_full_subtitle",
                "subtitle_chunk_summaries": [{"chunk_id": "c1"}],
            },
            llm_highlight_plan={
                "selected_segment_ids": ["plot_016"],
                "raw_voice_segment_ids": [],
            },
            story_highlights=story_highlights,
            script_items=filtered,
            highlight_only=False,
        )

        self.assertFalse(any("未通过高光选择的片段" in issue for issue in issues))


    def test_extract_story_highlights_loose_keeps_borderline_segment(self):
        module = _load_subtitle_first_pipeline()
        scene_evidence = [
            {
                "segment_id": "plot_001",
                "scene_id": "plot_001",
                "start": 15.0,
                "end": 19.0,
                "final_story_score": 1.1,
                "importance_level": "medium",
                "plot_function": "setup",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "attraction_level": "medium",
                "subtitle_text": "关键线索开始出现",
            }
        ]

        balanced = module._extract_story_highlights(scene_evidence, [], highlight_selectivity="balanced")
        loose = module._extract_story_highlights(scene_evidence, [], highlight_selectivity="loose")

        self.assertEqual([], balanced)
        self.assertEqual(1, len(loose))
        self.assertEqual("plot_001", loose[0]["segment_ids"][0])

    def test_extract_story_highlights_skips_tail_preview_and_clips_to_story_end(self):
        module = _load_subtitle_first_pipeline()
        scene_evidence = [
            {
                "segment_id": "plot_end",
                "scene_id": "plot_end",
                "start": 2398.0,
                "end": 2410.0,
                "final_story_score": 3.4,
                "importance_level": "high",
                "plot_function": "结局收束",
                "block_type": "emotion",
                "story_validation": {"validator_status": "pass"},
                "attraction_level": "high",
                "subtitle_text": "真正结尾",
                "llm_highlight_selected": True,
                "llm_highlight_reason": "ending",
                "boundary_confidence": "high",
                "story_end": 2410.0,
                "story_end_trimmed": True,
            },
            {
                "segment_id": "plot_preview",
                "scene_id": "plot_preview",
                "start": 2420.0,
                "end": 2434.0,
                "final_story_score": 4.0,
                "importance_level": "high",
                "plot_function": "结局收束",
                "block_type": "dialogue",
                "story_validation": {"validator_status": "pass"},
                "attraction_level": "high",
                "subtitle_text": "下集预告",
                "after_story_end": True,
                "story_end": 2410.0,
            },
        ]

        highlights = module._extract_story_highlights(
            scene_evidence,
            [2395.0, 2405.0, 2412.0, 2420.0],
            highlight_selectivity="balanced",
        )

        self.assertEqual(1, len(highlights))
        self.assertEqual("plot_end", highlights[0]["segment_ids"][0])
        self.assertEqual(2410.0, highlights[0]["end"])

    def test_build_highlight_narration_segments_collects_time_and_frames(self):
        module = _load_subtitle_first_pipeline()
        segments = module._build_highlight_narration_segments(
            story_highlights=[
                {
                    "highlight_id": "highlight_001",
                    "highlight_rank": 1,
                    "start": 12.0,
                    "end": 20.0,
                    "highlight_reasons": ["plot:反转", "llm_highlight_selected"],
                    "plot_functions": ["反转"],
                    "importance_level": "high",
                    "raw_voice_retain": True,
                    "segment_ids": ["plot_001"],
                    "scene_ids": ["plot_001"],
                    "evidence_ids": ["plot_001"],
                    "scene_group_ranges": [[12.0, 20.0]],
                    "scene_group_mode": "highlight_scene_group",
                }
            ],
            scene_evidence=[
                {
                    "segment_id": "plot_001",
                    "scene_id": "plot_001",
                    "start": 12.0,
                    "end": 20.0,
                    "main_text_evidence": "朱重八终于发现了关键真相",
                    "subtitle_text": "朱重八终于发现了关键真相",
                    "surface_dialogue_meaning": "他确认了敌人身份",
                    "real_narrative_state": "剧情从这里开始反转",
                    "speaker_names": ["朱重八"],
                    "speaker_turns": 1,
                    "exchange_pairs": [{"speaker": "朱重八", "text": "原来是你"}],
                    "visual_summary": [{"frame": "fallback.jpg", "desc": "人物神情震动"}],
                    "frame_paths": ["fallback.jpg"],
                    "local_understanding": {
                        "core_event": "发现真相",
                        "emotion": "紧张",
                        "characters": ["朱重八"],
                        "narrative_risk_flags": [],
                    },
                    "story_validation": {"validator_status": "pass", "validator_hints": ["ok"]},
                    "plot_role": "development",
                    "plot_function": "反转",
                    "attraction_level": "high",
                    "confidence": "srt",
                }
            ],
            highlight_frame_records=[
                {
                    "scene_id": "highlight_001",
                    "segment_id": "highlight_001",
                    "frame_path": "frame_a.jpg",
                    "timestamp_seconds": 13.5,
                    "rank": 1,
                },
                {
                    "scene_id": "highlight_001",
                    "segment_id": "highlight_001",
                    "frame_path": "frame_b.jpg",
                    "timestamp_seconds": 17.0,
                    "rank": 2,
                },
            ],
            global_summary={"arc": "development"},
        )

        self.assertEqual(1, len(segments))
        self.assertEqual("highlight_001", segments[0]["highlight_id"])
        self.assertEqual("00:00:12,000-00:00:20,000", segments[0]["timestamp"])
        self.assertEqual(["frame_a.jpg", "frame_b.jpg"], segments[0]["frame_paths"])
        self.assertEqual(2, len(segments[0]["representative_frames"]))
        self.assertEqual("00:00:13,500", segments[0]["representative_frames"][0]["timestamp"])
        self.assertEqual("朱重八终于发现了关键真相", segments[0]["main_text_evidence"])

    def test_build_highlight_only_script_keeps_frame_metadata(self):
        module = _load_subtitle_first_pipeline()
        script = module._build_highlight_only_script(
            [
                {
                    "highlight_id": "highlight_001",
                    "highlight_rank": 1,
                    "segment_id": "plot_001",
                    "start": 12.0,
                    "end": 20.0,
                    "picture": "人物神情震动",
                    "plot_function": "反转",
                    "importance_level": "high",
                    "highlight_reasons": ["plot:反转"],
                    "frame_paths": ["frame_a.jpg", "frame_b.jpg"],
                    "visual_summary": [{"frame": "frame_a.jpg", "desc": "人物神情震动"}],
                    "representative_frames": [
                        {"frame_path": "frame_a.jpg", "timestamp": "00:00:13,500", "desc": "人物神情震动"}
                    ],
                    "source_segment_ids": ["plot_001"],
                    "source_scene_ids": ["plot_001"],
                    "source_evidence_ids": ["plot_001"],
                    "main_text_evidence": "朱重八终于发现了关键真相",
                }
            ]
        )

        self.assertEqual(1, len(script))
        self.assertEqual(["frame_a.jpg", "frame_b.jpg"], script[0]["frame_paths"])
        self.assertEqual("朱重八终于发现了关键真相", script[0]["main_text_evidence"])
        self.assertEqual("00:00:12,000-00:00:20,000", script[0]["timestamp"])
        self.assertEqual("highlight_001", script[0]["highlight_id"])

    def test_ensure_full_subtitle_highlight_windows_backfills_from_story_highlights(self):
        module = _load_subtitle_first_pipeline()
        updated = module._ensure_full_subtitle_highlight_windows(
            full_subtitle_understanding={
                "subtitle_input_mode": "full_subtitle_text",
                "highlight_windows": [],
            },
            llm_highlight_plan={"must_keep_ranges": []},
            story_highlights=[
                {
                    "highlight_id": "highlight_001",
                    "start": 12.0,
                    "end": 18.5,
                    "importance_level": "high",
                    "raw_voice_retain": True,
                    "plot_functions": ["反转"],
                    "highlight_reasons": ["plot:反转", "llm_highlight_selected"],
                }
            ],
        )

        self.assertTrue(updated["highlight_windows_backfilled"])
        self.assertEqual("story_highlights_fallback", updated["highlight_windows_source"])
        self.assertEqual(1, len(updated["highlight_windows"]))
        self.assertEqual("00:00:12,000", updated["highlight_windows"][0]["start"])
        self.assertEqual("00:00:18,500", updated["highlight_windows"][0]["end"])
        self.assertEqual("反转", updated["highlight_windows"][0]["category"])
        self.assertEqual("high", updated["highlight_windows"][0]["raw_voice_priority"])

    def test_validate_pipeline_quality_loose_allows_single_highlight(self):
        module = _load_subtitle_first_pipeline()
        story_highlights = [
            {
                "highlight_id": "highlight_001",
                "segment_ids": ["plot_001"],
                "start": 12.0,
                "end": 16.0,
                "scene_group_ranges": [],
                "scene_align_mode": "semantic_keep",
            }
        ]
        script_items = [
            {
                "_id": 1,
                "segment_id": "plot_001",
                "start": 12.0,
                "end": 16.0,
                "llm_highlight_selected": True,
                "OST": 2,
                "narration_validation": {"status": "pass"},
            }
        ]
        full_subtitle_understanding = {
            "highlight_windows": [
                {"start": 1.0, "end": 4.0},
                {"start": 5.0, "end": 8.0},
                {"start": 9.0, "end": 12.0},
                {"start": 13.0, "end": 16.0},
                {"start": 17.0, "end": 20.0},
            ],
            "subtitle_input_mode": "chunked_full_subtitle",
            "subtitle_chunk_summaries": [{"chunk_id": "c1"}],
        }
        llm_highlight_plan = {
            "selected_segment_ids": ["plot_001", "plot_002", "plot_003", "plot_004", "plot_005"],
            "raw_voice_segment_ids": [],
        }

        loose_issues = module._validate_pipeline_quality(
            full_subtitle_understanding=full_subtitle_understanding,
            llm_highlight_plan=llm_highlight_plan,
            story_highlights=story_highlights,
            script_items=script_items,
            highlight_only=False,
            highlight_selectivity="loose",
        )
        strict_issues = module._validate_pipeline_quality(
            full_subtitle_understanding=full_subtitle_understanding,
            llm_highlight_plan=llm_highlight_plan,
            story_highlights=story_highlights,
            script_items=script_items,
            highlight_only=False,
            highlight_selectivity="strict",
        )

        self.assertEqual([], loose_issues)
        self.assertEqual(1, len(strict_issues))

    def test_validate_pipeline_quality_accepts_backfilled_highlight_windows(self):
        module = _load_subtitle_first_pipeline()
        story_highlights = [
            {
                "highlight_id": "highlight_001",
                "segment_ids": ["plot_001"],
                "start": 12.0,
                "end": 18.0,
                "scene_group_ranges": [[12.0, 18.0]],
                "scene_align_mode": "highlight_scene_group",
            }
        ]
        script_items = [
            {
                "_id": 1,
                "segment_id": "plot_001",
                "start": 12.0,
                "end": 18.0,
                "llm_highlight_selected": True,
                "OST": 2,
                "narration_validation": {"status": "pass"},
            }
        ]

        issues = module._validate_pipeline_quality(
            full_subtitle_understanding={
                "highlight_windows": [],
                "highlight_windows_backfilled": True,
                "subtitle_input_mode": "timeline_digest",
                "subtitle_chunk_summaries": [],
            },
            llm_highlight_plan={
                "selected_segment_ids": ["plot_001"],
                "raw_voice_segment_ids": [],
            },
            story_highlights=story_highlights,
            script_items=script_items,
            highlight_only=False,
            highlight_selectivity="loose",
        )

        self.assertEqual([], issues)


if __name__ == "__main__":
    unittest.main()
