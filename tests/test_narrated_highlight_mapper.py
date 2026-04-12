import unittest

from app.services import narrated_highlight_mapper as mapper


class NarratedHighlightMapperTests(unittest.TestCase):
    def test_split_narration_units_preserves_explicit_line_breaks(self):
        units = mapper.split_narration_units(
            "第一句我已经单独断行了。\n第二句也要保留原断句。",
            clip_count=0,
        )

        self.assertEqual([unit["text"] for unit in units], ["第一句我已经单独断行了。", "第二句也要保留原断句。"])

    def test_split_narration_units_assigns_type_and_template(self):
        units = mapper.split_narration_units(
            "他表面镇定，但其实心里已经慌了。\n两人的关系也在这一刻彻底反转。",
            clip_count=0,
        )

        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["narration_type"], "inner_state")
        self.assertEqual(units[0]["shot_template"], "inner_reaction")
        self.assertEqual(units[0]["match_focus"], "psychological_support")
        self.assertEqual(units[1]["narration_type"], "relation_change")
        self.assertEqual(units[1]["shot_template"], "relation_crosscut")

    def test_split_narration_units_extracts_focus_and_collective_target(self):
        units = mapper.split_narration_units(
            "所有人都开始怀疑王五，只有张三还在盯着他。",
            clip_count=0,
        )

        self.assertEqual(len(units), 1)
        self.assertTrue(units[0]["collective_signal"])
        self.assertEqual(units[0]["focus_character_names"], ["王五"])
        self.assertEqual(units[0]["collective_target_names"], ["王五"])

    def test_split_narration_units_extracts_subject_and_directed_target(self):
        units = mapper.split_narration_units(
            "张三看着李四，心里已经开始动摇。",
            clip_count=0,
        )

        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["subject_character_names"], ["张三"])
        self.assertEqual(units[0]["directed_target_names"], ["李四"])
        self.assertEqual(units[0]["focus_character_names"], ["张三"])

    def test_inner_state_scoring_prefers_reaction_style_clip(self):
        unit = {
            "text": "他表面镇定，但其实心里已经慌了",
            "narration_type": "inner_state",
            "story_stage": "turning_point",
            "keywords": mapper.extract_keywords("他表面镇定，但其实心里已经慌了"),
            "character_names": [],
            "target_seconds": 3.2,
        }
        reaction_clip = {
            "clip_id": "scene_reaction",
            "start": 12.0,
            "end": 15.2,
            "duration": 3.2,
            "source": "scene",
            "story_position": 0.52,
            "story_stage_hint": "turning_point",
            "scene_summary": "他沉默地移开视线，明显开始怀疑",
            "subtitle_text": "他没有再说话",
            "emotion_score": 0.74,
            "total_score": 0.72,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": [],
        }
        action_clip = {
            "clip_id": "action_clip",
            "start": 12.0,
            "end": 15.2,
            "duration": 3.2,
            "source": "hybrid",
            "story_position": 0.52,
            "story_stage_hint": "turning_point",
            "scene_summary": "他冲出房间追上对方",
            "subtitle_text": "快追",
            "emotion_score": 0.3,
            "total_score": 0.72,
            "raw_audio_worthy": False,
            "tags": ["conflict"],
            "character_names": [],
        }

        reaction_score = mapper._score_unit_clip(
            unit,
            reaction_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.52,
        )
        action_score = mapper._score_unit_clip(
            unit,
            action_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.52,
        )

        self.assertGreater(reaction_score, action_score)

    def test_relation_change_template_builds_crosscut_group(self):
        unit = {
            "text": "两人的关系在这一刻彻底反转",
            "narration_type": "relation_change",
            "shot_template": "relation_crosscut",
            "story_stage": "reveal",
            "keywords": mapper.extract_keywords("两人的关系在这一刻彻底反转"),
            "character_names": ["张三", "李四"],
            "target_seconds": 6.0,
            "rhythm_config": {
                "profile": "pivot",
                "preferred_group_size": 3,
                "target_flex": 1.18,
            },
        }
        available = [
            {
                "clip_id": "zhangsan_side",
                "start": 10.0,
                "end": 12.8,
                "duration": 2.8,
                "source": "scene",
                "source_scene_id": "scene_002",
                "story_position": 0.48,
                "story_stage_hint": "reveal",
                "scene_summary": "张三先盯着李四，态度还很强硬",
                "subtitle_text": "张三：我不会信你",
                "emotion_score": 0.54,
                "total_score": 0.69,
                "raw_audio_worthy": True,
                "tags": ["conflict"],
                "character_names": ["张三"],
            },
            {
                "clip_id": "relation_anchor",
                "start": 13.0,
                "end": 16.0,
                "duration": 3.0,
                "source": "scene",
                "source_scene_id": "scene_002",
                "story_position": 0.5,
                "story_stage_hint": "reveal",
                "scene_summary": "两人面对面站着，气氛突然变了",
                "subtitle_text": "李四：原来你早就知道了",
                "emotion_score": 0.66,
                "total_score": 0.8,
                "raw_audio_worthy": True,
                "tags": ["reveal"],
                "character_names": ["张三", "李四"],
            },
            {
                "clip_id": "lisi_side",
                "start": 16.2,
                "end": 18.8,
                "duration": 2.6,
                "source": "scene",
                "source_scene_id": "scene_002",
                "story_position": 0.53,
                "story_stage_hint": "reveal",
                "scene_summary": "李四的表情冷了下来，关系彻底变味",
                "subtitle_text": "李四：你从来没相信过我",
                "emotion_score": 0.7,
                "total_score": 0.76,
                "raw_audio_worthy": True,
                "tags": ["reveal"],
                "character_names": ["李四"],
            },
        ]

        group = mapper._build_clip_group(
            best_clip=available[1],
            available=available,
            unit=unit,
            usage_counts={},
            desired_position=0.5,
        )

        group_ids = [clip["clip_id"] for clip in group]
        self.assertIn("relation_anchor", group_ids)
        self.assertIn("zhangsan_side", group_ids)
        self.assertIn("lisi_side", group_ids)

    def test_relation_change_scoring_prefers_explicit_relation_evidence(self):
        text = "\u4e24\u4eba\u7684\u5173\u7cfb\u5728\u8fd9\u4e00\u523b\u5f7b\u5e95\u53cd\u8f6c"
        unit = {
            "text": text,
            "narration_type": "relation_change",
            "match_focus": "relationship_dynamic",
            "story_stage": "reveal",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "target_seconds": 4.0,
        }
        relation_clip = {
            "clip_id": "relation_clip",
            "start": 20.0,
            "end": 24.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.58,
            "story_stage_hint": "reveal",
            "scene_summary": "\u4e24\u4eba\u9762\u5bf9\u9762\u5bf9\u5cd9\uff0c\u5173\u7cfb\u5df2\u7ecf\u5f7b\u5e95\u7834\u88c2",
            "subtitle_text": "\u5f20\u4e09\uff1a\u6211\u4e0d\u4f1a\u518d\u4fe1\u4f60 \u674e\u56db\uff1a\u539f\u6765\u4f60\u65e9\u5c31\u77e5\u9053",
            "emotion_score": 0.48,
            "total_score": 0.71,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "speaker_sequence": ["\u5f20\u4e09", "\u674e\u56db"],
            "speaker_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "exchange_pairs": ["\u5f20\u4e09->\u674e\u56db"],
            "interaction_target_names": ["\u674e\u56db"],
            "relation_score": 0.92,
            "reaction_score": 0.32,
            "dialogue_exchange_score": 0.96,
            "ensemble_scene_score": 0.84,
            "solo_focus_score": 0.22,
            "speaker_turns": 2,
            "shot_role": "dialogue_exchange",
            "primary_evidence": "relation_score",
        }
        reaction_clip = {
            "clip_id": "reaction_clip",
            "start": 20.0,
            "end": 24.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.58,
            "story_stage_hint": "reveal",
            "scene_summary": "\u5f20\u4e09\u6c89\u9ed8\u5730\u770b\u7740\u674e\u56db\uff0c\u773c\u795e\u8eb2\u95ea",
            "subtitle_text": "\u4ed6\u6ca1\u6709\u518d\u8bf4\u8bdd",
            "emotion_score": 0.88,
            "total_score": 0.71,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "speaker_sequence": [],
            "speaker_names": [],
            "exchange_pairs": [],
            "interaction_target_names": [],
            "relation_score": 0.18,
            "reaction_score": 0.9,
            "dialogue_exchange_score": 0.18,
            "ensemble_scene_score": 0.24,
            "solo_focus_score": 0.92,
            "speaker_turns": 0,
            "shot_role": "single_focus",
            "primary_evidence": "reaction_score",
        }

        relation_score = mapper._score_unit_clip(
            unit,
            relation_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.58,
        )
        reaction_score = mapper._score_unit_clip(
            unit,
            reaction_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.58,
        )

        self.assertGreater(relation_score, reaction_score)

    def test_relation_change_scoring_prefers_multi_party_exchange_sequence(self):
        text = "\u5f20\u4e09\u3001\u674e\u56db\u548c\u738b\u4e94\u5728\u8fd9\u4e00\u523b\u5f7b\u5e95\u6485\u7834\u8138"
        unit = {
            "text": text,
            "narration_type": "relation_change",
            "match_focus": "relationship_dynamic",
            "story_stage": "conflict",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "target_seconds": 5.0,
        }
        multi_party_clip = {
            "clip_id": "multi_party_clip",
            "start": 50.0,
            "end": 55.0,
            "duration": 5.0,
            "source": "scene",
            "story_position": 0.68,
            "story_stage_hint": "conflict",
            "scene_summary": "\u4e09\u4eba\u8f6e\u756a\u5bf9\u5cf0\uff0c\u5173\u7cfb\u5f7b\u5e95\u6495\u88c2",
            "subtitle_text": "\u5f20\u4e09\uff1a\u4f60\u8bf4 \u674e\u56db\uff1a\u6211\u51ed\u4ec0\u4e48\u8bf4 \u738b\u4e94\uff1a\u90fd\u522b\u88c5\u4e86",
            "emotion_score": 0.72,
            "total_score": 0.82,
            "raw_audio_worthy": True,
            "tags": ["conflict", "reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "speaker_sequence": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "speaker_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "exchange_pairs": ["\u5f20\u4e09->\u674e\u56db", "\u674e\u56db->\u738b\u4e94"],
            "interaction_target_names": ["\u674e\u56db", "\u738b\u4e94"],
            "relation_score": 0.88,
            "dialogue_exchange_score": 0.92,
            "ensemble_scene_score": 0.9,
            "speaker_turns": 3,
            "shot_role": "ensemble_relation",
            "primary_evidence": "relation_score",
        }
        flat_clip = {
            "clip_id": "flat_clip",
            "start": 50.0,
            "end": 55.0,
            "duration": 5.0,
            "source": "scene",
            "story_position": 0.68,
            "story_stage_hint": "conflict",
            "scene_summary": "\u4e09\u4eba\u7ad9\u5728\u4e00\u8d77\uff0c\u6c14\u6c1b\u7d27\u5f20",
            "subtitle_text": "\u5927\u5bb6\u90fd\u6ca1\u6709\u518d\u8bf4\u8bdd",
            "emotion_score": 0.72,
            "total_score": 0.82,
            "raw_audio_worthy": True,
            "tags": ["conflict", "reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "speaker_sequence": [],
            "speaker_names": [],
            "exchange_pairs": [],
            "interaction_target_names": [],
            "relation_score": 0.88,
            "dialogue_exchange_score": 0.54,
            "ensemble_scene_score": 0.76,
            "speaker_turns": 0,
            "shot_role": "ensemble_relation",
            "primary_evidence": "relation_score",
        }

        multi_score = mapper._score_unit_clip(
            unit,
            multi_party_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.68,
        )
        flat_score = mapper._score_unit_clip(
            unit,
            flat_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.68,
        )

        self.assertGreater(multi_score, flat_score)

    def test_inner_state_scoring_prefers_single_focus_role(self):
        text = "\u4ed6\u8868\u9762\u9547\u5b9a\uff0c\u4f46\u5176\u5b9e\u5fc3\u91cc\u5df2\u7ecf\u5f00\u59cb\u614c\u4e86"
        unit = {
            "text": text,
            "narration_type": "inner_state",
            "match_focus": "psychological_support",
            "story_stage": "turning_point",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["\u4e3b\u89d2"],
            "target_seconds": 4.0,
        }
        single_focus_clip = {
            "clip_id": "single_focus_clip",
            "start": 30.0,
            "end": 34.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.62,
            "story_stage_hint": "turning_point",
            "scene_summary": "\u4ed6\u6c89\u9ed8\u5730\u79fb\u5f00\u89c6\u7ebf\uff0c\u773c\u795e\u91cc\u5df2\u7ecf\u5f00\u59cb\u72b9\u7591",
            "subtitle_text": "\u4ed6\u6ca1\u6709\u518d\u8bf4\u8bdd",
            "emotion_score": 0.78,
            "total_score": 0.74,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u4e3b\u89d2"],
            "inner_state_support": 0.76,
            "reaction_score": 0.74,
            "solo_focus_score": 0.94,
            "dialogue_exchange_score": 0.16,
            "speaker_turns": 0,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }
        dialogue_clip = {
            "clip_id": "dialogue_clip",
            "start": 30.0,
            "end": 34.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.62,
            "story_stage_hint": "turning_point",
            "scene_summary": "\u4ed6\u548c\u5bf9\u65b9\u6b63\u5728\u5bf9\u8bdd\uff0c\u573a\u9762\u4ecd\u5728\u4ea4\u950b",
            "subtitle_text": "\u7532\uff1a\u4f60\u5230\u5e95\u5728\u6015\u4ec0\u4e48 \u4e59\uff1a\u6211\u6ca1\u4ec0\u4e48\u597d\u8bf4\u7684",
            "emotion_score": 0.78,
            "total_score": 0.74,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u4e3b\u89d2", "\u5bf9\u65b9"],
            "inner_state_support": 0.76,
            "reaction_score": 0.74,
            "solo_focus_score": 0.22,
            "dialogue_exchange_score": 0.94,
            "speaker_turns": 2,
            "shot_role": "dialogue_exchange",
            "primary_evidence": "reaction_score",
        }

        single_focus_score = mapper._score_unit_clip(
            unit,
            single_focus_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.62,
        )
        dialogue_score = mapper._score_unit_clip(
            unit,
            dialogue_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.62,
        )

        self.assertGreater(single_focus_score, dialogue_score)

    def test_inner_state_scoring_prefers_target_matched_character(self):
        text = "\u5f20\u4e09\u8868\u9762\u9547\u5b9a\uff0c\u4f46\u5176\u5b9e\u5fc3\u91cc\u5df2\u7ecf\u5f00\u59cb\u614c\u4e86"
        unit = {
            "text": text,
            "narration_type": "inner_state",
            "match_focus": "psychological_support",
            "story_stage": "turning_point",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["\u5f20\u4e09"],
            "target_seconds": 4.0,
        }
        target_clip = {
            "clip_id": "target_clip",
            "start": 40.0,
            "end": 44.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.66,
            "story_stage_hint": "turning_point",
            "scene_summary": "\u5f20\u4e09\u6c89\u9ed8\u5730\u770b\u7740\u5bf9\u65b9\uff0c\u773c\u795e\u91cc\u5df2\u7ecf\u5f00\u59cb\u6447\u6446",
            "subtitle_text": "\u674e\u56db\uff1a\u4f60\u8fd8\u60f3\u77a7\u591a\u4e45",
            "emotion_score": 0.82,
            "total_score": 0.76,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "speaker_names": ["\u674e\u56db"],
            "interaction_target_names": ["\u5f20\u4e09"],
            "inner_state_support": 0.54,
            "reaction_score": 0.48,
            "solo_focus_score": 0.56,
            "dialogue_exchange_score": 0.24,
            "speaker_turns": 1,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }
        speaker_clip = {
            "clip_id": "speaker_clip",
            "start": 40.0,
            "end": 44.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.66,
            "story_stage_hint": "turning_point",
            "scene_summary": "\u5f20\u4e09\u8fd8\u5728\u5f3a\u6491\u7740\u8bf4\u8bdd",
            "subtitle_text": "\u5f20\u4e09\uff1a\u6211\u6ca1\u4e8b",
            "emotion_score": 0.82,
            "total_score": 0.76,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "speaker_names": ["\u5f20\u4e09"],
            "interaction_target_names": ["\u674e\u56db"],
            "inner_state_support": 0.54,
            "reaction_score": 0.48,
            "solo_focus_score": 0.56,
            "dialogue_exchange_score": 0.24,
            "speaker_turns": 1,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }

        target_score = mapper._score_unit_clip(
            unit,
            target_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.66,
        )
        speaker_score = mapper._score_unit_clip(
            unit,
            speaker_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.66,
        )

        self.assertGreater(target_score, speaker_score)

    def test_inner_state_scoring_prefers_pressure_target_focus(self):
        text = "\u738b\u4e94\u770b\u8d77\u6765\u8fd8\u5728\u786c\u6491\uff0c\u4f46\u5fc3\u91cc\u5176\u5b9e\u5df2\u7ecf\u4e71\u4e86"
        unit = {
            "text": text,
            "narration_type": "inner_state",
            "match_focus": "psychological_support",
            "story_stage": "conflict",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["\u738b\u4e94"],
            "target_seconds": 4.0,
        }
        pressure_target_clip = {
            "clip_id": "pressure_target_clip",
            "start": 48.0,
            "end": 52.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.7,
            "story_stage_hint": "conflict",
            "scene_summary": "\u738b\u4e94\u88ab\u4e24\u4e2a\u4eba\u9023\u7e8c\u8ffd\u95ee\u540e\uff0c\u6c89\u9ed8\u5730\u907f\u5f00\u76ee\u5149",
            "subtitle_text": "\u738b\u4e94\u4e00\u65f6\u95f4\u4e5f\u63a5\u4e0d\u4e0a\u8bdd",
            "emotion_score": 0.8,
            "total_score": 0.78,
            "raw_audio_worthy": True,
            "tags": ["conflict", "reveal"],
            "character_names": ["\u738b\u4e94"],
            "pressure_source_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "pressure_target_names": ["\u738b\u4e94"],
            "group_reaction_score": 0.84,
            "inner_state_support": 0.72,
            "reaction_score": 0.78,
            "solo_focus_score": 0.9,
            "speaker_turns": 0,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }
        pressure_source_clip = {
            "clip_id": "pressure_source_clip",
            "start": 48.0,
            "end": 52.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.7,
            "story_stage_hint": "conflict",
            "scene_summary": "\u5f20\u4e09\u8fd8\u5728\u6b65\u6b65\u7d27\u903c\uff0c\u8bed\u6c14\u8d8a\u6765\u8d8a\u91cd",
            "subtitle_text": "\u5f20\u4e09\uff1a\u4f60\u73b0\u5728\u5c31\u7ed9\u6211\u8bf4\u6e05\u695a",
            "emotion_score": 0.8,
            "total_score": 0.78,
            "raw_audio_worthy": True,
            "tags": ["conflict", "reveal"],
            "character_names": ["\u5f20\u4e09"],
            "pressure_source_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "pressure_target_names": ["\u738b\u4e94"],
            "group_reaction_score": 0.84,
            "inner_state_support": 0.72,
            "reaction_score": 0.78,
            "solo_focus_score": 0.9,
            "speaker_turns": 1,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }

        target_score = mapper._score_unit_clip(
            unit,
            pressure_target_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.7,
        )
        source_score = mapper._score_unit_clip(
            unit,
            pressure_source_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.7,
        )

        self.assertGreater(target_score, source_score)

    def test_omniscient_summary_scoring_prefers_group_reaction_scene(self):
        text = "\u8fd9\u4e00\u523b\uff0c\u6240\u6709\u4eba\u90fd\u5f00\u59cb\u628a\u6000\u7591\u6307\u5411\u738b\u4e94"
        unit = {
            "text": text,
            "narration_type": "omniscient_summary",
            "match_focus": "narrative_overview",
            "story_stage": "reveal",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "target_seconds": 4.2,
        }
        group_scene = {
            "clip_id": "group_scene",
            "start": 60.0,
            "end": 64.2,
            "duration": 4.2,
            "source": "scene",
            "story_position": 0.76,
            "story_stage_hint": "reveal",
            "scene_summary": "\u6240\u6709\u4eba\u7684\u76ee\u5149\u90fd\u96c6\u4e2d\u5230\u4e86\u738b\u4e94\u8eab\u4e0a\uff0c\u7a7a\u6c14\u7a81\u7136\u51dd\u4f4f",
            "subtitle_text": "\u73b0\u573a\u4e00\u4e0b\u5b50\u5b89\u9759\u4e0b\u6765",
            "emotion_score": 0.74,
            "total_score": 0.8,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "pressure_source_names": ["\u5f20\u4e09", "\u674e\u56db"],
            "pressure_target_names": ["\u738b\u4e94"],
            "group_reaction_score": 0.92,
            "ensemble_scene_score": 0.88,
            "narrative_overview_score": 0.66,
            "shot_role": "ensemble_relation",
        }
        flat_scene = {
            "clip_id": "flat_scene",
            "start": 60.0,
            "end": 64.2,
            "duration": 4.2,
            "source": "scene",
            "story_position": 0.76,
            "story_stage_hint": "reveal",
            "scene_summary": "\u573a\u9762\u8fd8\u5728\u63a8\u8fdb\uff0c\u6c14\u6c1b\u6709\u4e9b\u7d27\u5f20",
            "subtitle_text": "\u6ca1\u6709\u4eba\u518d\u8bf4\u8bdd",
            "emotion_score": 0.74,
            "total_score": 0.8,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["\u5f20\u4e09", "\u674e\u56db", "\u738b\u4e94"],
            "group_reaction_score": 0.28,
            "ensemble_scene_score": 0.68,
            "narrative_overview_score": 0.66,
            "shot_role": "narrative_bridge",
        }

        group_score = mapper._score_unit_clip(
            unit,
            group_scene,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.76,
        )
        flat_score = mapper._score_unit_clip(
            unit,
            flat_scene,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.76,
        )

        self.assertGreater(group_score, flat_score)

    def test_omniscient_summary_scoring_prefers_collective_target_match(self):
        unit = {
            "text": "所有人都开始怀疑王五",
            "narration_type": "omniscient_summary",
            "match_focus": "narrative_overview",
            "story_stage": "reveal",
            "keywords": mapper.extract_keywords("所有人都开始怀疑王五"),
            "character_names": ["王五"],
            "focus_character_names": ["王五"],
            "collective_target_names": ["王五"],
            "collective_signal": True,
            "target_seconds": 3.8,
        }
        target_clip = {
            "clip_id": "target_clip",
            "start": 70.0,
            "end": 73.8,
            "duration": 3.8,
            "source": "scene",
            "story_position": 0.82,
            "story_stage_hint": "reveal",
            "scene_summary": "所有人的目光都压到了王五身上",
            "subtitle_text": "现场突然安静了下来",
            "emotion_score": 0.7,
            "total_score": 0.76,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["张三", "李四", "王五"],
            "pressure_source_names": ["张三", "李四"],
            "pressure_target_names": ["王五"],
            "group_reaction_score": 0.88,
            "ensemble_scene_score": 0.86,
            "narrative_overview_score": 0.62,
            "shot_role": "ensemble_relation",
        }
        mismatch_clip = {
            "clip_id": "mismatch_clip",
            "start": 70.0,
            "end": 73.8,
            "duration": 3.8,
            "source": "scene",
            "story_position": 0.82,
            "story_stage_hint": "reveal",
            "scene_summary": "所有人的目光都压到了张三身上",
            "subtitle_text": "现场突然安静了下来",
            "emotion_score": 0.7,
            "total_score": 0.76,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["张三", "李四", "王五"],
            "pressure_source_names": ["李四", "王五"],
            "pressure_target_names": ["张三"],
            "group_reaction_score": 0.88,
            "ensemble_scene_score": 0.86,
            "narrative_overview_score": 0.62,
            "shot_role": "ensemble_relation",
        }

        target_score = mapper._score_unit_clip(
            unit,
            target_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.82,
        )
        mismatch_score = mapper._score_unit_clip(
            unit,
            mismatch_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.82,
        )

        self.assertGreater(target_score, mismatch_score)

    def test_inner_state_scoring_prefers_subject_owned_reaction(self):
        unit = {
            "text": "张三看着李四，心里已经开始动摇",
            "narration_type": "inner_state",
            "match_focus": "psychological_support",
            "story_stage": "turning_point",
            "keywords": mapper.extract_keywords("张三看着李四，心里已经开始动摇"),
            "character_names": ["张三", "李四"],
            "subject_character_names": ["张三"],
            "directed_target_names": ["李四"],
            "focus_character_names": ["张三"],
            "target_seconds": 4.0,
        }
        subject_clip = {
            "clip_id": "subject_clip",
            "start": 82.0,
            "end": 86.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.63,
            "story_stage_hint": "turning_point",
            "scene_summary": "张三望着李四，眼神里已经开始迟疑",
            "subtitle_text": "张三没有再说话",
            "emotion_score": 0.82,
            "total_score": 0.77,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["张三"],
            "interaction_target_names": ["李四"],
            "inner_state_support": 0.76,
            "reaction_score": 0.8,
            "solo_focus_score": 0.92,
            "dialogue_exchange_score": 0.22,
            "speaker_turns": 0,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }
        target_clip = {
            "clip_id": "target_clip",
            "start": 82.0,
            "end": 86.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.63,
            "story_stage_hint": "turning_point",
            "scene_summary": "李四也盯着张三，场面仍然很僵",
            "subtitle_text": "李四：你到底怎么了",
            "emotion_score": 0.82,
            "total_score": 0.77,
            "raw_audio_worthy": True,
            "tags": ["reveal"],
            "character_names": ["李四"],
            "interaction_target_names": ["张三"],
            "inner_state_support": 0.76,
            "reaction_score": 0.8,
            "solo_focus_score": 0.92,
            "dialogue_exchange_score": 0.22,
            "speaker_turns": 1,
            "shot_role": "single_focus",
            "primary_evidence": "inner_state_support",
        }

        subject_score = mapper._score_unit_clip(
            unit,
            subject_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.63,
        )
        target_score = mapper._score_unit_clip(
            unit,
            target_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.63,
        )

        self.assertGreater(subject_score, target_score)

    def test_relation_change_scoring_prefers_matching_directional_pair(self):
        unit = {
            "text": "张三开始怀疑李四，两人的关系彻底变了",
            "narration_type": "relation_change",
            "match_focus": "relationship_dynamic",
            "story_stage": "reveal",
            "keywords": mapper.extract_keywords("张三开始怀疑李四，两人的关系彻底变了"),
            "character_names": ["张三", "李四"],
            "subject_character_names": ["张三"],
            "directed_target_names": ["李四"],
            "focus_character_names": ["张三", "李四"],
            "target_seconds": 4.5,
        }
        matching_clip = {
            "clip_id": "matching_clip",
            "start": 90.0,
            "end": 94.5,
            "duration": 4.5,
            "source": "scene",
            "story_position": 0.74,
            "story_stage_hint": "reveal",
            "scene_summary": "张三步步逼近李四，怀疑已经写在脸上",
            "subtitle_text": "张三：我现在最怀疑的人就是你 李四：你凭什么这么说",
            "emotion_score": 0.76,
            "total_score": 0.8,
            "raw_audio_worthy": True,
            "tags": ["reveal", "conflict"],
            "character_names": ["张三", "李四"],
            "speaker_names": ["张三", "李四"],
            "interaction_target_names": ["李四"],
            "exchange_pairs": ["张三->李四"],
            "dialogue_exchange_score": 0.9,
            "ensemble_scene_score": 0.82,
            "relation_score": 0.9,
            "speaker_turns": 2,
            "shot_role": "dialogue_exchange",
            "primary_evidence": "relation_score",
        }
        reversed_clip = {
            "clip_id": "reversed_clip",
            "start": 90.0,
            "end": 94.5,
            "duration": 4.5,
            "source": "scene",
            "story_position": 0.74,
            "story_stage_hint": "reveal",
            "scene_summary": "李四反过来逼问张三",
            "subtitle_text": "李四：我反倒更怀疑你 张三：随便你怎么想",
            "emotion_score": 0.76,
            "total_score": 0.8,
            "raw_audio_worthy": True,
            "tags": ["reveal", "conflict"],
            "character_names": ["张三", "李四"],
            "speaker_names": ["李四", "张三"],
            "interaction_target_names": ["张三"],
            "exchange_pairs": ["李四->张三"],
            "dialogue_exchange_score": 0.9,
            "ensemble_scene_score": 0.82,
            "relation_score": 0.9,
            "speaker_turns": 2,
            "shot_role": "dialogue_exchange",
            "primary_evidence": "relation_score",
        }

        matching_score = mapper._score_unit_clip(
            unit,
            matching_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.74,
        )
        reversed_score = mapper._score_unit_clip(
            unit,
            reversed_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.74,
        )

        self.assertGreater(matching_score, reversed_score)

    def test_visible_action_scoring_prefers_audio_supported_action_clip(self):
        text = "他们忽然冲进房间，现场瞬间乱成一团"
        unit = {
            "text": text,
            "narration_type": "visible_action",
            "match_focus": "action_support",
            "story_stage": "conflict",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["主角"],
            "target_seconds": 3.6,
        }
        quiet_clip = {
            "clip_id": "quiet_action",
            "start": 40.0,
            "end": 43.6,
            "duration": 3.6,
            "source": "scene",
            "story_position": 0.55,
            "story_stage_hint": "conflict",
            "scene_summary": "他们推门而入，继续向前包抄",
            "subtitle_text": "快跟上",
            "emotion_score": 0.44,
            "total_score": 0.7,
            "raw_audio_worthy": True,
            "tags": ["conflict"],
            "character_names": ["主角"],
            "visible_action_score": 0.78,
            "audio_signal_score": 0.18,
            "audio_peak_score": 0.12,
            "audio_onset_score": 0.1,
            "audio_dynamic_score": 0.08,
            "shot_role": "action_follow",
            "primary_evidence": "visible_action_score",
        }
        loud_clip = {
            "clip_id": "loud_action",
            "start": 40.0,
            "end": 43.6,
            "duration": 3.6,
            "source": "scene",
            "story_position": 0.55,
            "story_stage_hint": "conflict",
            "scene_summary": "他们砸开门冲入，爆响之后整个现场立刻炸开",
            "subtitle_text": "冲",
            "emotion_score": 0.44,
            "total_score": 0.7,
            "raw_audio_worthy": True,
            "tags": ["conflict"],
            "character_names": ["主角"],
            "visible_action_score": 0.78,
            "audio_signal_score": 0.82,
            "audio_peak_score": 0.86,
            "audio_onset_score": 0.72,
            "audio_dynamic_score": 0.64,
            "shot_role": "action_follow",
            "primary_evidence": "visible_action_score",
        }

        quiet_score = mapper._score_unit_clip(
            unit,
            quiet_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.55,
        )
        loud_score = mapper._score_unit_clip(
            unit,
            loud_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.55,
        )

        self.assertGreater(loud_score, quiet_score)

    def test_relation_change_scoring_penalizes_early_setup_clip(self):
        text = "他们的关系到这里已经彻底撕裂"
        unit = {
            "text": text,
            "narration_type": "relation_change",
            "match_focus": "relationship_dynamic",
            "story_stage": "conflict",
            "keywords": mapper.extract_keywords(text),
            "character_names": ["张三", "李四"],
            "target_seconds": 4.0,
        }
        early_setup_clip = {
            "clip_id": "early_setup",
            "start": 8.0,
            "end": 12.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.08,
            "story_stage_hint": "setup",
            "intro_risk_score": 0.84,
            "scene_summary": "两人刚刚出现，还在平静地交代背景",
            "subtitle_text": "我们先过去看看",
            "emotion_score": 0.26,
            "total_score": 0.72,
            "raw_audio_worthy": False,
            "tags": [],
            "character_names": ["张三", "李四"],
            "relation_score": 0.48,
            "dialogue_exchange_score": 0.52,
            "ensemble_scene_score": 0.42,
            "speaker_turns": 1,
            "shot_role": "dialogue_exchange",
            "primary_evidence": "relation_score",
        }
        true_conflict_clip = {
            "clip_id": "true_conflict",
            "start": 58.0,
            "end": 62.0,
            "duration": 4.0,
            "source": "scene",
            "story_position": 0.62,
            "story_stage_hint": "conflict",
            "intro_risk_score": 0.0,
            "scene_summary": "两人当面对峙，话里话外都已经彻底撕开",
            "subtitle_text": "我不会再信你",
            "emotion_score": 0.66,
            "total_score": 0.72,
            "raw_audio_worthy": True,
            "tags": ["conflict"],
            "character_names": ["张三", "李四"],
            "relation_score": 0.72,
            "dialogue_exchange_score": 0.82,
            "ensemble_scene_score": 0.68,
            "speaker_turns": 2,
            "shot_role": "dialogue_exchange",
            "primary_evidence": "relation_score",
        }

        early_score = mapper._score_unit_clip(
            unit,
            early_setup_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.62,
        )
        conflict_score = mapper._score_unit_clip(
            unit,
            true_conflict_clip,
            usage_count=0,
            last_start=-1.0,
            desired_position=0.62,
        )

        self.assertGreater(conflict_score, early_score)


if __name__ == "__main__":
    unittest.main()
