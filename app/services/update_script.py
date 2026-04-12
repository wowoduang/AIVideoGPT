#!/usr/bin/env python
# -*- coding: UTF-8 -*-

'''
@Project: NarratoAI
@File   : update_script
@Author : Viccy同学
@Date   : 2025/5/6 下午11:00 
'''

import re
import os
from typing import Dict, List, Any, Tuple, Union

from app.utils import utils


def extract_timestamp_from_video_path(video_path: str) -> str:
    """
    从视频文件路径中提取时间戳，统一返回 HH:MM:SS,mmm-HH:MM:SS,mmm。
    兼容文件名示例：
    - ost2_vid_00-00-00-000@00-00-20-250.mp4
    - vid_00-00-00-000@00-00-20-250.mp4
    - vid-00-00-00-00-00-00.mp4
    """
    filename = os.path.basename(video_path)

    match_precise = re.search(r'vid_(\d{2})-(\d{2})-(\d{2})-(\d{3})@(\d{2})-(\d{2})-(\d{2})-(\d{3})\.mp4', filename)
    if match_precise:
        sh, sm, ss, sms, eh, em, es, ems = match_precise.groups()
        return f"{sh}:{sm}:{ss},{sms}-{eh}:{em}:{es},{ems}"

    match_old = re.search(r'vid-(\d{2}-\d{2}-\d{2})-(\d{2}-\d{2}-\d{2})\.mp4', filename)
    if match_old:
        start_time = match_old.group(1).replace('-', ':')
        end_time = match_old.group(2).replace('-', ':')
        return f"{start_time}-{end_time}"

    return ""


def _timestamp_to_seconds_range(timestamp: str):
    raw = str(timestamp or "").strip()
    if not raw or '-' not in raw:
        return None, None
    try:
        start_raw, end_raw = raw.split('-', 1)
        start = utils.time_to_seconds(start_raw.strip())
        end = utils.time_to_seconds(end_raw.strip())
        if end <= start:
            return None, None
        return round(start, 3), round(end, 3)
    except Exception:
        return None, None


def _canonical_timestamp_from_seconds(start: float, end: float) -> str:
    return f"{utils.format_time(start)}-{utils.format_time(end)}"


def calculate_duration(timestamp: str) -> float:
    """计算时间戳范围的持续时间（秒），兼容秒数字符串与 SRT 时间。"""
    start_seconds, end_seconds = _timestamp_to_seconds_range(timestamp)
    if start_seconds is None or end_seconds is None:
        return 0.0
    return round(end_seconds - start_seconds, 3)


def update_script_timestamps(
    script_list: List[Dict[str, Any]], 
    video_result: Dict[Union[str, int], str], 
    audio_result: Dict[Union[str, int], str] = None,
    subtitle_result: Dict[Union[str, int], str] = None,
    calculate_edited_timerange: bool = True
) -> List[Dict[str, Any]]:
    """
    根据 video_result 中的视频文件更新 script_list 中的时间戳，添加持续时间，
    并根据 audio_result 添加音频路径，根据 subtitle_result 添加字幕路径
    
    Args:
        script_list: 原始脚本列表
        video_result: 视频结果字典，键为原时间戳或_id，值为视频文件路径
        audio_result: 音频结果字典，键为原时间戳或_id，值为音频文件路径
        subtitle_result: 字幕结果字典，键为原时间戳或_id，值为字幕文件路径
        calculate_edited_timerange: 是否计算并添加成品视频中的时间范围
    
    Returns:
        更新后的脚本列表
    """
    # 创建副本，避免修改原始数据
    updated_script = []

    # 建立ID和时间戳到视频路径和新时间戳的映射
    id_timestamp_mapping = {}
    for key, video_path in video_result.items():
        new_timestamp = extract_timestamp_from_video_path(video_path)
        if new_timestamp:
            id_timestamp_mapping[key] = {
                'new_timestamp': new_timestamp,
                'video_path': video_path
            }

    # 计算累积时长，用于生成成品视频中的时间范围
    accumulated_duration = 0.0
    
    # 更新脚本中的时间戳
    for item in script_list:
        item_copy = item.copy()
        item_id = item_copy.get('_id')
        orig_timestamp = item_copy.get('timestamp', '')

        # 初始化音频和字幕路径为空字符串
        item_copy['audio'] = ""
        item_copy['subtitle'] = ""
        item_copy['video'] = ""  # 初始化视频路径为空字符串

        # 如果提供了音频结果字典且ID存在于音频结果中，直接使用对应的音频路径
        if audio_result:
            if item_id and item_id in audio_result:
                item_copy['audio'] = audio_result[item_id]
            elif orig_timestamp in audio_result:
                item_copy['audio'] = audio_result[orig_timestamp]

        # 如果提供了字幕结果字典且ID存在于字幕结果中，直接使用对应的字幕路径
        if subtitle_result:
            if item_id and item_id in subtitle_result:
                item_copy['subtitle'] = subtitle_result[item_id]
            elif orig_timestamp in subtitle_result:
                item_copy['subtitle'] = subtitle_result[orig_timestamp]

        # 添加视频路径
        if item_id and item_id in video_result:
            item_copy['video'] = video_result[item_id]
        elif orig_timestamp in video_result:
            item_copy['video'] = video_result[orig_timestamp]

        # 更新时间戳和计算持续时间
        current_duration = 0.0
        if item_id and item_id in id_timestamp_mapping:
            # 根据ID找到对应的新时间戳
            item_copy['sourceTimeRange'] = id_timestamp_mapping[item_id]['new_timestamp']
            current_duration = calculate_duration(item_copy['sourceTimeRange'])
            item_copy['duration'] = current_duration
        elif orig_timestamp in id_timestamp_mapping:
            # 根据原始时间戳找到对应的新时间戳
            item_copy['sourceTimeRange'] = id_timestamp_mapping[orig_timestamp]['new_timestamp']
            current_duration = calculate_duration(item_copy['sourceTimeRange'])
            item_copy['duration'] = current_duration
        elif orig_timestamp:
            # 对于未更新的时间戳，也计算并添加持续时间
            item_copy['sourceTimeRange'] = orig_timestamp
            current_duration = calculate_duration(orig_timestamp)
            item_copy['duration'] = current_duration
            
        # 规范化原始时间戳/起止秒
        range_start, range_end = _timestamp_to_seconds_range(item_copy.get('sourceTimeRange', '') or item_copy.get('timestamp', ''))
        if range_start is not None and range_end is not None:
            item_copy['timestamp'] = _canonical_timestamp_from_seconds(range_start, range_end)
            item_copy['start'] = round(range_start, 3)
            item_copy['end'] = round(range_end, 3)

        # 计算片段在成品视频中的时间范围
        if calculate_edited_timerange and current_duration > 0:
            start_time_seconds = accumulated_duration
            end_time_seconds = accumulated_duration + current_duration
            item_copy['editedTimeRange'] = _canonical_timestamp_from_seconds(start_time_seconds, end_time_seconds)
            # 更新累积时长
            accumulated_duration = end_time_seconds

        updated_script.append(item_copy)

    return updated_script


if __name__ == '__main__':
    print("Use update_script_timestamps() from the app pipeline; legacy local-path demo data has been removed.")
