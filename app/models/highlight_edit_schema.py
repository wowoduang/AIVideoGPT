from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict


EditMode = Literal["highlight_recut", "narrated_highlight_edit"]
AudioMode = Literal["raw", "ducked_raw", "tts", "mute"]
SignalSource = Literal["subtitle", "scene", "hybrid"]
NarrationType = Literal["visible_action", "emotion_state", "inner_state", "relation_change", "omniscient_summary"]


class SourceHints(TypedDict, total=False):
    use_subtitle: bool
    use_visual: bool
    use_external_narration: bool


class EditRequest(TypedDict, total=False):
    video_path: str
    mode: EditMode
    target_duration_seconds: int
    movie_title: str
    highlight_profile: str
    subtitle_path: str
    subtitle_text: str
    narration_text: str
    narration_audio_path: str
    prefer_raw_audio: bool
    visual_mode: str
    alignment_mode: str
    source_hints: SourceHints
    regenerate_subtitle: bool
    subtitle_backend: str


class NarrationSignal(TypedDict, total=False):
    text: str
    audio_path: str


class SignalPack(TypedDict, total=False):
    subtitle_result: Dict
    subtitle_segments: List[Dict]
    scene_segments: List[Dict]
    plot_chunks: List[Dict]
    video_boundary_candidates: List[Dict]
    plot_candidate_clips: List[Dict]
    candidate_clips: List[Dict]
    scene_candidate_clips: List[Dict]
    candidate_stats: Dict
    highlight_profile: Dict
    highlight_capabilities: Dict
    external_narration: NarrationSignal
    metadata: Dict


class CandidateClip(TypedDict, total=False):
    clip_id: str
    start: float
    end: float
    duration: float
    source: SignalSource
    story_index: int
    story_position: float
    story_stage_hint: str
    plot_function: str
    plot_role: str
    importance_level: str
    attraction_level: str
    narration_level: str
    subtitle_text: str
    scene_summary: str
    energy_score: float
    story_score: float
    emotion_score: float
    total_score: float
    base_total_score: float
    profile_fit_score: float
    profile_total_score: float
    highlight_profile_id: str
    audio_rms_score: float
    audio_onset_score: float
    audio_dynamic_score: float
    audio_signal_score: float
    audio_peak_score: float
    raw_audio_worthy: bool
    speaker_sequence: List[str]
    speaker_names: List[str]
    exchange_pairs: List[str]
    interaction_target_names: List[str]
    pressure_source_names: List[str]
    pressure_target_names: List[str]
    visible_action_score: float
    reaction_score: float
    inner_state_support: float
    relation_score: float
    narrative_overview_score: float
    group_reaction_score: float
    speaker_turns: int
    solo_focus_score: float
    dialogue_exchange_score: float
    ensemble_scene_score: float
    shot_role: str
    primary_evidence: str
    tags: List[str]
    character_names: List[str]
    keyframe_candidates: List[float]
    boundary_candidates: List[float]
    prevent_merge: bool
    parent_clip_id: str
    subshot_index: int
    source_scene_id: str
    source_segment_ids: List[str]
    selection_reason: List[str]


class SelectedClip(TypedDict, total=False):
    clip_id: str
    start: float
    end: float
    duration: float
    story_index: int
    story_position: float
    story_stage_hint: str
    plot_function: str
    plot_role: str
    total_score: float
    base_total_score: float
    profile_fit_score: float
    profile_total_score: float
    highlight_profile_id: str
    audio_rms_score: float
    audio_onset_score: float
    audio_dynamic_score: float
    audio_signal_score: float
    audio_peak_score: float
    raw_audio_worthy: bool
    speaker_sequence: List[str]
    speaker_names: List[str]
    exchange_pairs: List[str]
    interaction_target_names: List[str]
    pressure_source_names: List[str]
    pressure_target_names: List[str]
    visible_action_score: float
    reaction_score: float
    inner_state_support: float
    relation_score: float
    narrative_overview_score: float
    group_reaction_score: float
    speaker_turns: int
    solo_focus_score: float
    dialogue_exchange_score: float
    ensemble_scene_score: float
    shot_role: str
    primary_evidence: str
    selection_reason: List[str]
    character_names: List[str]
    keyframe_candidates: List[float]
    boundary_candidates: List[float]
    prevent_merge: bool
    parent_clip_id: str
    subshot_index: int
    source_scene_id: str
    source_segment_ids: List[str]
    subtitle_text: str
    scene_summary: str
    original_duration: float
    planned_duration: float
    trim_strategy: str


class NarrationUnit(TypedDict, total=False):
    unit_id: str
    text: str
    target_seconds: float
    story_stage: str
    narration_type: NarrationType
    match_focus: str
    shot_template: str
    keywords: List[str]
    character_names: List[str]
    subject_character_names: List[str]
    directed_target_names: List[str]
    focus_character_names: List[str]
    collective_target_names: List[str]
    collective_signal: bool
    rhythm_profile: str
    rhythm_config: Dict
    position_hint: float
    duration_scale: float


class CompositionSegment(TypedDict, total=False):
    segment_id: str
    video_start: float
    video_end: float
    timeline_start: float
    timeline_end: float
    audio_mode: AudioMode
    narration_text: str
    narration_audio_path: str
    selection_reason: List[str]
    picture: str
    audio_strategy: str
    source_clip_id: str
    clip_source: SignalSource
    source_scene_id: str
    raw_audio_worthy: bool
    parent_clip_id: str
    subshot_index: int
    trim_strategy: str
    original_duration: float
    planned_duration: float
    match_score: float
    match_strategy: str


class CompositionPlan(TypedDict, total=False):
    mode: EditMode
    video_path: str
    movie_title: str
    target_duration_seconds: int
    segments: List[CompositionSegment]
    audio_tracks: Dict[str, Optional[str]]
    metadata: Dict
