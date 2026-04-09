import streamlit as st
from moviepy import VideoFileClip
from app.models.schema import VideoClipParams, VideoAspect, AudioVolumeDefaults


def _infer_source_video_aspect() -> str:
    video_path = str(st.session_state.get("video_origin_path", "") or "").strip()
    cached_path = str(st.session_state.get("_inferred_source_video_path", "") or "").strip()
    cached_aspect = str(st.session_state.get("_inferred_source_video_aspect", "") or "").strip()
    if cached_aspect and cached_path == video_path:
        return cached_aspect

    inferred = VideoAspect.landscape.value
    if video_path:
        clip = None
        try:
            clip = VideoFileClip(video_path)
            width, height = clip.size
            inferred = VideoAspect.portrait.value if height > width else VideoAspect.landscape.value
        except Exception:
            inferred = VideoAspect.landscape.value
        finally:
            if clip is not None:
                clip.close()

    st.session_state["_inferred_source_video_path"] = video_path
    st.session_state["_inferred_source_video_aspect"] = inferred
    return inferred


def render_video_panel(tr):
    """渲染视频配置面板"""
    with st.container(border=True):
        st.write(tr("Video Settings"))
        params = VideoClipParams()
        render_video_config(tr, params)


def render_video_config(tr, params):
    """渲染视频配置"""
    # 视频比例
    video_aspect_ratios = [
        (tr("Portrait"), VideoAspect.portrait.value),
        (tr("Landscape"), VideoAspect.landscape.value),
    ]
    inferred_aspect = _infer_source_video_aspect()
    current_aspect = str(st.session_state.get("video_aspect", "") or "").strip() or inferred_aspect
    if "video_ratio_select" not in st.session_state:
        current_aspect = inferred_aspect
    valid_aspects = {value for _, value in video_aspect_ratios}
    if current_aspect not in valid_aspects:
        current_aspect = inferred_aspect
    selected_default = next(
        (idx for idx, (_, value) in enumerate(video_aspect_ratios) if value == current_aspect),
        1,
    )
    selected_index = st.selectbox(
        tr("Video Ratio"),
        options=range(len(video_aspect_ratios)),
        format_func=lambda x: video_aspect_ratios[x][0],
        index=selected_default,
        key="video_ratio_select",
    )
    params.video_aspect = VideoAspect(video_aspect_ratios[selected_index][1])
    st.session_state['video_aspect'] = params.video_aspect.value

    # 视频画质
    video_qualities = [
        ("4K (2160p)", "2160p"),
        ("2K (1440p)", "1440p"),
        ("Full HD (1080p)", "1080p"),
        ("HD (720p)", "720p"),
        ("SD (480p)", "480p"),
    ]
    quality_index = st.selectbox(
        tr("Video Quality"),
        options=range(len(video_qualities)),
        format_func=lambda x: video_qualities[x][0],
        index=2  # 默认选择 1080p
    )
    st.session_state['video_quality'] = video_qualities[quality_index][1]

    # 原声音量 - 使用统一的默认值
    params.original_volume = st.slider(
        tr("Original Volume"),
        min_value=AudioVolumeDefaults.MIN_VOLUME,
        max_value=AudioVolumeDefaults.MAX_VOLUME,
        value=AudioVolumeDefaults.ORIGINAL_VOLUME,
        step=0.01,
        help=tr("Adjust the volume of the original audio")
    )
    st.session_state['original_volume'] = params.original_volume


def get_video_params():
    """获取视频参数"""
    return {
        'video_aspect': st.session_state.get('video_aspect', st.session_state.get("_inferred_source_video_aspect", VideoAspect.landscape.value)),
        'video_quality': st.session_state.get('video_quality', '1080p'),
        'original_volume': st.session_state.get('original_volume', AudioVolumeDefaults.ORIGINAL_VOLUME)
    }
