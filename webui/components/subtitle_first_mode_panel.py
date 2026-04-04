from __future__ import annotations

import streamlit as st


def _label(tr, text: str) -> str:
    try:
        return tr(text) if callable(tr) else text
    except Exception:
        return text


def init_subtitle_first_mode_state():
    st.session_state.setdefault("subtitle_source_mode", "auto_subtitle")
    st.session_state.setdefault("subtitle_asr_backend", "sensevoice")
    st.session_state.setdefault("subtitle_cache_mode", "clear_and_regenerate")
    st.session_state.setdefault("subtitle_review_mode", "review_suspicious")
    st.session_state.setdefault("generation_mode", "balanced")
    st.session_state.setdefault("visual_mode", "auto")
    st.session_state.setdefault("narration_style", "general")
    st.session_state.setdefault("target_duration_minutes", 8)
    st.session_state.setdefault("narrative_strategy", "chronological")
    st.session_state.setdefault("accuracy_priority", "high")


def render_subtitle_first_mode_panel(tr=None):
    init_subtitle_first_mode_state()

    with st.expander(_label(tr, "影视解说 / 字幕优先模式设置"), expanded=True):
        st.selectbox(
            _label(tr, "字幕来源"),
            options=["auto_subtitle", "existing_subtitle"],
            format_func=lambda x: _label(tr, "自动生成字幕") if x == "auto_subtitle" else _label(tr, "使用已有字幕"),
            key="subtitle_source_mode",
        )

        cols = st.columns(2)
        with cols[0]:
            st.selectbox(
                _label(tr, "字幕识别后端"),
                options=["sensevoice", "faster-whisper"],
                key="subtitle_asr_backend",
            )
        with cols[1]:
            st.selectbox(
                _label(tr, "字幕缓存策略"),
                options=["clear_and_regenerate", "use_cache"],
                format_func=lambda x: _label(tr, "清除字幕缓存并重新生成") if x == "clear_and_regenerate" else _label(tr, "使用缓存字幕"),
                key="subtitle_cache_mode",
            )

        cols2 = st.columns(2)
        with cols2[0]:
            st.selectbox(
                _label(tr, "可疑字幕处理"),
                options=["review_suspicious", "skip_review"],
                format_func=lambda x: _label(tr, "标出可疑字幕并人工审核") if x == "review_suspicious" else _label(tr, "跳过审核直接继续"),
                key="subtitle_review_mode",
            )
        with cols2[1]:
            st.selectbox(
                _label(tr, "解说生成模式"),
                options=["fast", "balanced", "quality"],
                key="generation_mode",
            )

        cols3 = st.columns(2)
        with cols3[0]:
            st.selectbox(
                _label(tr, "视觉辅助模式"),
                options=["off", "auto", "boost"],
                key="visual_mode",
            )
        with cols3[1]:
            st.selectbox(
                _label(tr, "叙事策略"),
                options=["chronological", "dramatic", "mixed"],
                key="narrative_strategy",
            )

        cols4 = st.columns(2)
        with cols4[0]:
            st.number_input(
                _label(tr, "目标解说时长（分钟）"),
                min_value=1,
                max_value=30,
                step=1,
                key="target_duration_minutes",
            )
        with cols4[1]:
            st.selectbox(
                _label(tr, "事实准确优先级"),
                options=["high", "balanced", "expressive"],
                key="accuracy_priority",
            )

        st.selectbox(
            _label(tr, "解说风格"),
            options=["general", "dramatic", "analysis", "short_video"],
            key="narration_style",
        )


def render_panel(tr=None):
    render_subtitle_first_mode_panel(tr)


def render(tr=None):
    render_subtitle_first_mode_panel(tr)
