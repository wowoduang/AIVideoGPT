from __future__ import annotations

import streamlit as st


WIDGET_KEYS = {
    "subtitle_source_mode": "_widget_subtitle_source_mode",
    "subtitle_asr_backend": "_widget_subtitle_asr_backend",
    "subtitle_cache_mode": "_widget_subtitle_cache_mode",
    "subtitle_review_mode": "_widget_subtitle_review_mode",
    "prologue_strategy": "_widget_prologue_strategy",
    "manual_prologue_end_time": "_widget_manual_prologue_end_time",
    "highlight_selectivity": "_widget_highlight_selectivity",
    "highlight_only_mode": "_widget_highlight_only_mode",
    "generation_mode": "_widget_generation_mode",
    "visual_mode": "_widget_visual_mode",
    "narration_style": "_widget_narration_style",
    "target_duration_minutes": "_widget_target_duration_minutes",
    "narrative_strategy": "_widget_narrative_strategy",
    "accuracy_priority": "_widget_accuracy_priority",
}


def _label(tr, text: str) -> str:
    try:
        return tr(text) if callable(tr) else text
    except Exception:
        return text


def init_subtitle_first_mode_state():
    st.session_state.setdefault("subtitle_source_mode", "auto_subtitle")
    st.session_state.setdefault("subtitle_asr_backend", "faster-whisper")
    st.session_state.setdefault("subtitle_cache_mode", "clear_and_regenerate")
    st.session_state.setdefault("subtitle_review_mode", "review_suspicious")
    st.session_state.setdefault("prologue_strategy", "speech_first")
    st.session_state.setdefault("manual_prologue_end_time", "")
    st.session_state.setdefault("highlight_selectivity", "balanced")
    st.session_state.setdefault("highlight_only_mode", False)
    st.session_state.setdefault("generation_mode", "balanced")
    st.session_state.setdefault("visual_mode", "auto")
    st.session_state.setdefault("narration_style", "general")
    st.session_state.setdefault("target_duration_minutes", 8)
    st.session_state.setdefault("narrative_strategy", "chronological")
    st.session_state.setdefault("accuracy_priority", "high")
    for state_key, widget_key in WIDGET_KEYS.items():
        st.session_state.setdefault(widget_key, st.session_state.get(state_key))


def _sync_widget_from_state(state_key: str):
    widget_key = WIDGET_KEYS[state_key]
    state_value = st.session_state.get(state_key)
    if st.session_state.get(widget_key) != state_value:
        st.session_state[widget_key] = state_value


def _sync_state_from_widget(state_key: str):
    widget_key = WIDGET_KEYS[state_key]
    st.session_state[state_key] = st.session_state.get(widget_key)


def _prime_widget_state():
    # On reruns triggered by user interaction, Streamlit updates widget keys first.
    # Respect those values and only initialize missing widget keys from business state.
    for state_key, widget_key in WIDGET_KEYS.items():
        if widget_key in st.session_state:
            st.session_state[state_key] = st.session_state.get(widget_key)
        else:
            _sync_widget_from_state(state_key)


def render_subtitle_first_mode_panel(tr=None, show_source_mode: bool = True):
    init_subtitle_first_mode_state()
    _prime_widget_state()

    with st.expander(_label(tr, "影视解说模式设置"), expanded=True):
        if show_source_mode:
            st.selectbox(
                _label(tr, "字幕来源"),
                options=["auto_subtitle", "existing_subtitle"],
                format_func=lambda x: _label(tr, "自动生成字幕") if x == "auto_subtitle" else _label(tr, "使用已有字幕"),
                key=WIDGET_KEYS["subtitle_source_mode"],
            )
            _sync_state_from_widget("subtitle_source_mode")

        cols = st.columns(2)
        with cols[0]:
            st.selectbox(
                _label(tr, "字幕识别后端"),
                options=["sensevoice", "faster-whisper", "videocaptioner_shell", "videolingo_shell"],
                format_func=lambda x: {
                    "sensevoice": "SenseVoice",
                    "faster-whisper": "faster-whisper",
                    "videocaptioner_shell": "VideoCaptioner",
                    "videolingo_shell": "VideoLingo (shell)",
                }.get(x, x),
                key=WIDGET_KEYS["subtitle_asr_backend"],
            )
            _sync_state_from_widget("subtitle_asr_backend")
        with cols[1]:
            st.selectbox(
                _label(tr, "字幕缓存策略"),
                options=["clear_and_regenerate", "use_cache"],
                format_func=lambda x: _label(tr, "清除字幕缓存并重新生成") if x == "clear_and_regenerate" else _label(tr, "使用缓存字幕"),
                key=WIDGET_KEYS["subtitle_cache_mode"],
            )
            _sync_state_from_widget("subtitle_cache_mode")

        cols2 = st.columns(2)
        with cols2[0]:
            st.selectbox(
                _label(tr, "可疑字幕处理"),
                options=["review_suspicious", "skip_review"],
                format_func=lambda x: _label(tr, "标出可疑字幕并人工审核") if x == "review_suspicious" else _label(tr, "跳过审核直接继续"),
                key=WIDGET_KEYS["subtitle_review_mode"],
            )
            _sync_state_from_widget("subtitle_review_mode")
        with cols2[1]:
            st.selectbox(
                _label(tr, "解说生成模式"),
                options=["fast", "balanced", "quality"],
                key=WIDGET_KEYS["generation_mode"],
            )
            _sync_state_from_widget("generation_mode")

        cols2b = st.columns(2)
        with cols2b[0]:
            st.selectbox(
                "序幕判断",
                options=["speech_first", "llm_auto", "manual_time"],
                format_func=lambda x: {
                    "speech_first": "人声起点优先",
                    "llm_auto": "LLM 自动判断",
                    "manual_time": "手动输入时间",
                }.get(x, x),
                key=WIDGET_KEYS["prologue_strategy"],
            )
            _sync_state_from_widget("prologue_strategy")
        with cols2b[1]:
            st.text_input(
                "序幕结束时间",
                placeholder="例如 13 / 00:00:13 / 00:00:13,500",
                key=WIDGET_KEYS["manual_prologue_end_time"],
                disabled=st.session_state.get("prologue_strategy") != "manual_time",
            )
            _sync_state_from_widget("manual_prologue_end_time")

        st.checkbox(
            _label(tr, "仅生成高光验证脚本（不生成解说）"),
            key=WIDGET_KEYS["highlight_only_mode"],
        )
        _sync_state_from_widget("highlight_only_mode")

        st.selectbox(
            "Highlight Selectivity",
            options=["loose", "balanced", "strict"],
            format_func=lambda x: {
                "loose": "Loose",
                "balanced": "Balanced",
                "strict": "Strict",
            }.get(x, x),
            key=WIDGET_KEYS["highlight_selectivity"],
        )
        _sync_state_from_widget("highlight_selectivity")

        cols3 = st.columns(2)
        with cols3[0]:
            st.selectbox(
                _label(tr, "视觉辅助模式"),
                options=["off", "auto", "boost"],
                key=WIDGET_KEYS["visual_mode"],
            )
            _sync_state_from_widget("visual_mode")
        with cols3[1]:
            st.selectbox(
                _label(tr, "叙事策略"),
                options=["chronological", "dramatic", "mixed"],
                key=WIDGET_KEYS["narrative_strategy"],
            )
            _sync_state_from_widget("narrative_strategy")

        cols4 = st.columns(2)
        with cols4[0]:
            st.number_input(
                _label(tr, "目标解说时长（分钟）"),
                min_value=1,
                max_value=30,
                step=1,
                key=WIDGET_KEYS["target_duration_minutes"],
            )
            _sync_state_from_widget("target_duration_minutes")
        with cols4[1]:
            st.selectbox(
                _label(tr, "事实准确优先级"),
                options=["high", "balanced", "expressive"],
                key=WIDGET_KEYS["accuracy_priority"],
            )
            _sync_state_from_widget("accuracy_priority")

        st.selectbox(
            _label(tr, "解说风格"),
            options=["general", "dramatic", "analysis", "short_video"],
            key=WIDGET_KEYS["narration_style"],
        )
        _sync_state_from_widget("narration_style")


def render_panel(tr=None):
    render_subtitle_first_mode_panel(tr)


def render(tr=None):
    render_subtitle_first_mode_panel(tr)
