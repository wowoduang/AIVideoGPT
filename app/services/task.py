import json
import os
from os import path

from loguru import logger

from app.config.audio_config import get_recommended_volumes_for_content
from app.models import const
from app.models.schema import VideoClipParams
from app.services import (
    audio_merger,
    clip_video,
    generate_video,
    merger_video,
    subtitle_merger,
    update_script,
    voice,
)
from app.services import state as sm
from app.services.preflight_check import PreflightError, validate_script_items, validate_tts_results
from app.services.script_fallback import ensure_script_shape
from app.services.tts_cache import load_cached_tts_results, store_tts_results
from app.services.media_duration import probe_media_duration
from app.utils import utils


def _timestamp_to_seconds_range(timestamp: str):
    timestamp = str(timestamp or "").strip()
    if not timestamp or "-" not in timestamp:
        return None, None
    try:
        start_raw, end_raw = timestamp.split("-", 1)
        start = utils.time_to_seconds(start_raw.strip())
        end = utils.time_to_seconds(end_raw.strip())
        if end <= start:
            return None, None
        return round(start, 3), round(end, 3)
    except Exception:
        return None, None


def _normalize_script_item(item, idx: int):
    new_item = dict(item or {})
    start = new_item.get("start")
    end = new_item.get("end")
    try:
        start = float(start) if start is not None else None
        end = float(end) if end is not None else None
    except Exception:
        start, end = None, None

    if start is None or end is None or end <= start:
        ts_start, ts_end = _timestamp_to_seconds_range(new_item.get("timestamp", ""))
        if ts_start is not None and ts_end is not None:
            start, end = ts_start, ts_end

    if start is None:
        start = 0.0
    if end is None or end <= start:
        duration_guess = float(new_item.get("duration") or 0)
        end = start + max(duration_guess, 1.0)

    new_item["start"] = round(float(start), 3)
    new_item["end"] = round(float(end), 3)
    new_item["duration"] = round(max(float(end) - float(start), 0.001), 3)
    new_item["timestamp"] = f"{utils.format_time(start)}-{utils.format_time(end)}"
    new_item.setdefault("_id", idx)
    new_item.setdefault("OST", 2)
    new_item.setdefault("picture", "")
    return new_item


def _normalize_script_list(items):
    normalized = [_normalize_script_item(item, idx) for idx, item in enumerate(items or [], start=1)]
    normalized.sort(key=lambda x: (float(x.get("start", 0.0) or 0.0), int(x.get("_id", 0) or 0)))
    return normalized


merged_audio_path = ""
merged_subtitle_path = ""


def _load_and_prepare_script(video_script_path: str):
    if not path.exists(video_script_path):
        logger.error(f"解说脚本文件不存在: {video_script_path}，请先点击【保存脚本】按钮保存脚本后再生成视频")
        raise ValueError("解说脚本文件不存在！请先点击【保存脚本】按钮保存脚本后再生成视频。")

    try:
        with open(video_script_path, "r", encoding="utf-8") as f:
            list_script = json.load(f)
        list_script = ensure_script_shape(list_script)
        list_script = _normalize_script_list(list_script)
        validate_script_items(list_script)
        video_ost = [i["OST"] for i in list_script]
        logger.debug(f"解说完整脚本: {' '.join(i['narration'] for i in list_script)}")
        logger.debug(f"解说 OST 列表: {video_ost}")
        logger.debug(f"解说时间戳列表: {[i['timestamp'] for i in list_script]}")
        return list_script, video_ost
    except PreflightError:
        raise
    except Exception as e:
        logger.error(f"无法读取视频json脚本，请检查脚本格式是否正确: {e}")
        raise ValueError("无法读取视频json脚本，请检查脚本格式是否正确")


def _build_tts_results(task_id: str, list_script, params):
    tts_segments = [segment for segment in list_script if segment["OST"] in [0, 2]]
    logger.info(f"需要生成TTS的片段数: {len(tts_segments)}")
    if not tts_segments:
        return [], []

    cached_results, missing_items = load_cached_tts_results(
        task_id=task_id,
        list_script=tts_segments,
        voice_name=params.voice_name,
        voice_rate=params.voice_rate,
        voice_pitch=params.voice_pitch,
        tts_engine=params.tts_engine,
    )

    generated_results = []
    if missing_items:
        generated_results = voice.tts_multiple(
            task_id=task_id,
            list_script=missing_items,
            tts_engine=params.tts_engine,
            voice_name=params.voice_name,
            voice_rate=params.voice_rate,
            voice_pitch=params.voice_pitch,
        ) or []
        if generated_results:
            store_tts_results(
                list_script=missing_items,
                tts_results=generated_results,
                voice_name=params.voice_name,
                voice_rate=params.voice_rate,
                voice_pitch=params.voice_pitch,
                tts_engine=params.tts_engine,
            )

    tts_results = sorted(cached_results + generated_results, key=lambda x: x.get('_id', 0))
    tts_results = _ensure_tts_result_durations(tts_results)
    validate_tts_results(list_script, tts_results)
    return tts_segments, tts_results


def _ensure_tts_result_durations(tts_results):
    updated = []
    for item in tts_results or []:
        new_item = dict(item)
        duration = float(new_item.get("duration") or 0)
        if duration <= 0:
            duration = probe_media_duration(new_item.get("audio_file", ""))
            if duration > 0:
                new_item["duration"] = duration
        updated.append(new_item)
    return updated


def _align_script_timings_to_audio(script_list):
    aligned = []
    for item in script_list or []:
        new_item = dict(item)
        duration = float(new_item.get("duration") or 0)
        if duration <= 0 and new_item.get("audio"):
            duration = probe_media_duration(new_item.get("audio"))
            if duration > 0:
                new_item["duration"] = duration
        aligned.append(new_item)
    return aligned


def _merge_audio_and_subtitles(task_id: str, list_script, total_duration: float):
    global merged_audio_path, merged_subtitle_path
    if not list_script:
        merged_audio_path = ""
        merged_subtitle_path = ""
        return merged_audio_path, merged_subtitle_path

    merged_audio_path = audio_merger.merge_audio_files(
        task_id=task_id,
        total_duration=total_duration,
        list_script=list_script,
    )
    merged_subtitle_path = subtitle_merger.merge_subtitle_files(list_script) or ""
    return merged_audio_path, merged_subtitle_path


def _combine_video_segments(task_id: str, params: VideoClipParams, new_script_list, video_ost):
    combined_video_path = path.join(utils.task_dir(task_id), "merger.mp4")
    video_clips = []
    for new_script in new_script_list:
        video_path = new_script.get("video")
        if video_path and os.path.exists(video_path):
            video_clips.append(video_path)
        else:
            logger.error(f"片段 {new_script.get('_id')} 的视频文件不存在: {video_path}")

    if not video_clips:
        raise ValueError("没有可用于合并的视频片段")

    merger_video.combine_clip_videos(
        output_video_path=combined_video_path,
        video_paths=video_clips,
        video_ost_list=video_ost,
        video_aspect=params.video_aspect,
        threads=params.n_threads,
    )
    return combined_video_path


def _final_merge(task_id: str, params: VideoClipParams, combined_video_path: str, list_script):
    output_video_path = path.join(utils.task_dir(task_id), "combined.mp4")
    bgm_path = utils.get_bgm_file()
    optimized_volumes = get_recommended_volumes_for_content("mixed")
    has_original_audio_segments = any(segment["OST"] == 1 for segment in list_script)
    final_tts_volume = params.tts_volume if getattr(params, "tts_volume", 1.0) != 1.0 else optimized_volumes["tts_volume"]
    final_original_volume = 1.0 if has_original_audio_segments else (
        params.original_volume if getattr(params, "original_volume", 0.7) != 0.7 else optimized_volumes["original_volume"]
    )
    final_bgm_volume = params.bgm_volume if getattr(params, "bgm_volume", 0.3) != 0.3 else optimized_volumes["bgm_volume"]

    options = {
        "voice_volume": final_tts_volume,
        "bgm_volume": final_bgm_volume,
        "original_audio_volume": final_original_volume,
        "keep_original_audio": True,
        "subtitle_enabled": params.subtitle_enabled,
        "subtitle_font": params.font_name,
        "subtitle_font_size": params.font_size,
        "subtitle_color": params.text_fore_color,
        "subtitle_bg_color": None,
        "subtitle_position": params.subtitle_position,
        "custom_position": params.custom_position,
        "threads": params.n_threads,
    }
    generate_video.merge_materials(
        video_path=combined_video_path,
        audio_path=merged_audio_path,
        subtitle_path=merged_subtitle_path,
        bgm_path=bgm_path,
        output_path=output_video_path,
        options=options,
    )
    return output_video_path


def _run_pipeline(task_id: str, params: VideoClipParams):
    logger.info(f"\n\n## 开始统一视频处理任务: {task_id}")
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=0)

    logger.info("\n\n## 1. 加载视频脚本")
    list_script, video_ost = _load_and_prepare_script(path.join(params.video_clip_json_path))

    logger.info("\n\n## 2. 根据OST设置生成音频列表")
    try:
        tts_segments, tts_results = _build_tts_results(task_id, list_script, params)
    except PreflightError as e:
        logger.error(str(e))
        raise ValueError(str(e))
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=20)

    logger.info("\n\n## 3. 统一视频裁剪（基于OST类型）")
    video_clip_result = clip_video.clip_video_unified(
        video_origin_path=params.video_origin_path,
        script_list=list_script,
        tts_results=tts_results,
    )
    tts_clip_result = {tts_result["_id"]: tts_result["audio_file"] for tts_result in tts_results}
    subclip_clip_result = {tts_result["_id"]: tts_result["subtitle_file"] for tts_result in tts_results}
    new_script_list = update_script.update_script_timestamps(list_script, video_clip_result, tts_clip_result, subclip_clip_result)
    new_script_list = _align_script_timings_to_audio(new_script_list)
    logger.info(f"统一裁剪完成，处理了 {len(video_clip_result)} 个视频片段")
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=60)

    logger.info("\n\n## 4. 合并音频和字幕")
    total_duration = sum([script.get("duration", 0) for script in new_script_list])
    if tts_segments:
        try:
            _merge_audio_and_subtitles(task_id, new_script_list, total_duration)
        except Exception as e:
            logger.error(f"合并音频/字幕文件失败: {str(e)}")
            raise
    else:
        logger.warning("没有需要合并的音频/字幕")
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=80)

    logger.info("\n\n## 5. 合并视频")
    combined_video_path = _combine_video_segments(task_id, params, new_script_list, video_ost)

    logger.info(f"\n\n## 6. 最后一步: 合并字幕/BGM/配音/视频")
    output_video_path = _final_merge(task_id, params, combined_video_path, list_script)

    kwargs = {
        "videos": [output_video_path],
        "combined_videos": [combined_video_path],
    }
    sm.state.update_task(task_id, state=const.TASK_STATE_COMPLETE, progress=100, **kwargs)
    logger.success(f"统一处理任务 {task_id} 已完成")
    return kwargs


def start_subclip(task_id: str, params: VideoClipParams, subclip_path_videos: dict = None):
    return _run_pipeline(task_id, params)


def start_subclip_unified(task_id: str, params: VideoClipParams):
    return _run_pipeline(task_id, params)


def validate_params(video_path, audio_path, output_file, params):
    if not video_path:
        raise ValueError("视频路径不能为空")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    if audio_path and not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
    if not output_file:
        raise ValueError("输出文件路径不能为空")
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not params:
        raise ValueError("视频参数不能为空")
