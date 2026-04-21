"""
阿里云百炼平台 ASR 服务
支持 Qwen3-ASR-Flash 和 Fun-ASR
"""

import os
import time
import base64
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path
from loguru import logger

from app.config import config


class BailianASRService:
    """阿里云百炼 ASR 服务"""
    
    # API 端点
    BASE_URL_CN = "https://dashscope.aliyuncs.com/api/v1"
    BASE_URL_INTL = "https://dashscope-intl.aliyuncs.com/api/v1"
    
    # 模型名称
    MODEL_QWEN3_ASR_FLASH = "qwen3-asr-flash"
    MODEL_QWEN3_ASR_FLASH_FILETRANS = "qwen3-asr-flash-filetrans"
    MODEL_FUN_ASR = "fun-asr"
    
    def __init__(self, api_key: Optional[str] = None, region: str = "cn"):
        """
        初始化百炼 ASR 服务
        
        Args:
            api_key: 阿里云百炼 API Key，如果不提供则从配置读取
            region: 区域，cn=中国内地，intl=国际
        """
        # 从配置读取 API Key（统一使用 whisper.bailian_api_key）
        self.api_key = api_key or config.whisper.get("bailian_api_key", "")
        self.region = region
        self.base_url = self.BASE_URL_CN if region == "cn" else self.BASE_URL_INTL
        
        if not self.api_key:
            raise ValueError(
                "百炼 API Key 未配置，请在 config.toml 的 [whisper] 部分设置 bailian_api_key"
            )
    
    def _get_headers(self, async_mode: bool = False) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if async_mode:
            headers["X-DashScope-Async"] = "enable"
        return headers
    
    def _file_to_base64(self, file_path: str) -> str:
        """将文件转换为 base64"""
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _get_audio_mime_type(self, file_path: str) -> str:
        """获取音频文件的 MIME 类型"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
        }
        return mime_types.get(ext, "audio/mpeg")
    
    def recognize_short_audio(
        self,
        audio_path: str,
        model: str = "qwen3-asr-flash",
        language: Optional[str] = "zh",
        enable_itn: bool = True,
    ) -> Dict[str, Any]:
        """
        短音频同步识别（最长 5 分钟）
        
        Args:
            audio_path: 音频文件路径
            model: 模型名称，默认 qwen3-asr-flash
            language: 语言代码，默认 zh
            enable_itn: 是否开启逆文本正则化
            
        Returns:
            识别结果字典
        """
        # 检查文件大小（最大 10MB）
        file_size = os.path.getsize(audio_path)
        if file_size > 10 * 1024 * 1024:
            raise ValueError(f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过 10MB 限制，请使用长音频接口")
        
        # 转换为 base64
        audio_base64 = self._file_to_base64(audio_path)
        mime_type = self._get_audio_mime_type(audio_path)
        
        url = f"{self.base_url}/services/aigc/multimodal-generation/generation"
        
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"audio": f"data:{mime_type};base64,{audio_base64}"}
                        ]
                    }
                ]
            },
            "parameters": {
                "asr_options": {
                    "enable_itn": enable_itn,
                }
            }
        }
        
        if language:
            payload["parameters"]["asr_options"]["language"] = language
        
        logger.info(f"调用百炼短音频识别: {model}, 文件: {audio_path}")
        
        response = requests.post(url, headers=self._get_headers(), json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"百炼 ASR 识别完成")
        
        return result
    
    def submit_long_audio_task(
        self,
        audio_url: str,
        model: str = "qwen3-asr-flash-filetrans",
        language: Optional[str] = "zh",
        enable_itn: bool = True,
        enable_words: bool = False,
        channel_id: Optional[List[int]] = None,
    ) -> str:
        """
        提交长音频异步识别任务（最长 12 小时）
        
        Args:
            audio_url: 音频文件 URL（必须是公网可访问）
            model: 模型名称，默认 qwen3-asr-flash-filetrans
            language: 语言代码
            enable_itn: 是否开启逆文本正则化
            enable_words: 是否开启字级别时间戳
            channel_id: 指定音轨索引
            
        Returns:
            任务 ID
        """
        url = f"{self.base_url}/services/audio/asr/transcription"
        
        payload = {
            "model": model,
            "input": {
                "file_url": audio_url
            },
            "parameters": {
                "enable_itn": enable_itn,
                "enable_words": enable_words,
            }
        }
        
        if language:
            payload["parameters"]["language"] = language
        if channel_id:
            payload["parameters"]["channel_id"] = channel_id
        
        logger.info(f"提交百炼长音频任务: {model}, URL: {audio_url}")
        
        response = requests.post(url, headers=self._get_headers(async_mode=True), json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        task_id = result.get("output", {}).get("task_id")
        
        if not task_id:
            raise RuntimeError(f"未能获取任务 ID: {result}")
        
        logger.info(f"百炼长音频任务提交成功: {task_id}")
        return task_id
    
    def query_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        查询异步任务结果
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务状态和结果
        """
        url = f"{self.base_url}/tasks/{task_id}"
        
        response = requests.get(url, headers=self._get_headers(), timeout=60)
        response.raise_for_status()
        
        return response.json()
    
    def wait_for_task_complete(
        self,
        task_id: str,
        timeout: int = 3600,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        等待异步任务完成
        
        Args:
            task_id: 任务 ID
            timeout: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
            
        Returns:
            任务结果
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.query_task_result(task_id)
            status = result.get("output", {}).get("task_status", "UNKNOWN")
            
            logger.debug(f"任务 {task_id} 状态: {status}")
            
            if status == "SUCCEEDED":
                logger.info(f"任务 {task_id} 完成")
                return result
            elif status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"任务 {task_id} 失败: {result}")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"等待任务 {task_id} 超时")
    
    def parse_result_to_segments(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析识别结果为分段格式
        
        Returns:
            分段列表，每项包含 text, start, end
        """
        segments = []
        
        # 短音频结果格式
        if "output" in result and "choices" in result["output"]:
            choice = result["output"]["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", [])
            
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    segments.append({
                        "text": item["text"],
                        "start": 0.0,
                        "end": 0.0,
                    })
        
        # 长音频结果格式
        elif "output" in result and "results" in result["output"]:
            results = result["output"]["results"]
            for item in results:
                segments.append({
                    "text": item.get("text", ""),
                    "start": item.get("begin_time", 0) / 1000.0,  # 毫秒转秒
                    "end": item.get("end_time", 0) / 1000.0,
                })
        
        return segments


# 全局服务实例
_bailian_service: Optional[BailianASRService] = None


def get_bailian_service() -> BailianASRService:
    """获取百炼 ASR 服务实例"""
    global _bailian_service
    if _bailian_service is None:
        _bailian_service = BailianASRService()
    return _bailian_service


def _extract_audio_from_video(video_path: str, output_audio_path: str) -> str:
    """
    从视频文件中提取音频
    
    Args:
        video_path: 视频文件路径
        output_audio_path: 输出音频路径
        
    Returns:
        提取的音频文件路径
    """
    import subprocess
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",  # 禁用视频
        "-acodec", "libmp3lame",
        "-ar", "16000",  # 采样率 16kHz
        "-ac", "1",  # 单声道
        "-b:a", "32k",  # 比特率 32kbps
        output_audio_path
    ]
    
    logger.info(f"从视频提取音频: {video_path} -> {output_audio_path}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"音频提取完成: {output_audio_path}")
        return output_audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f"音频提取失败: {e.stderr}")
        raise RuntimeError(f"无法从视频提取音频: {video_path}")


def _detect_silence_points(audio_path: str, min_silence_duration: float = 0.3, 
                           silence_threshold: int = -40) -> List[float]:
    """
    检测音频中的静音点（用于语义分割）
    
    Args:
        audio_path: 音频文件路径
        min_silence_duration: 最小静音时长（秒）
        silence_threshold: 静音阈值（dB）
        
    Returns:
        静音点时间点列表（秒）
    """
    import subprocess
    import re
    
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={silence_threshold}dB:d={min_silence_duration}",
        "-f", "null", "-"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        output = result.stderr
        
        # 解析静音检测结果
        silence_starts = re.findall(r'silence_start: ([\d.]+)', output)
        silence_ends = re.findall(r'silence_end: ([\d.]+)', output)
        
        # 取静音段的中间点作为分割点
        split_points = []
        for start, end in zip(silence_starts, silence_ends):
            mid_point = (float(start) + float(end)) / 2
            split_points.append(mid_point)
        
        logger.debug(f"检测到 {len(split_points)} 个静音分割点")
        return split_points
        
    except Exception as e:
        logger.warning(f"静音检测失败: {e}，将使用固定时长分割")
        return []


def _split_audio_semantic(audio_path: str, target_duration: int = 300, 
                          output_dir: Optional[str] = None) -> List[tuple]:
    """
    智能语义分割音频（在静音点处分割，避免切断语句）
    
    Args:
        audio_path: 音频文件路径
        target_duration: 目标每段时长（秒），默认 5 分钟
        output_dir: 输出目录
        
    Returns:
        分割后的 (文件路径, 偏移时间) 列表
    """
    import subprocess
    import tempfile
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="bailian_asr_")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取音频时长
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        total_duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error(f"获取音频时长失败: {e}")
        raise RuntimeError(f"无法获取音频时长: {audio_path}")
    
    logger.info(f"音频总时长: {total_duration:.2f}秒，目标每段 {target_duration}秒")
    
    # 检测静音点
    silence_points = _detect_silence_points(audio_path)
    
    # 计算分割点（优先在静音点分割）
    split_points = [0]
    current_pos = 0
    
    while current_pos + target_duration < total_duration:
        target_pos = current_pos + target_duration
        
        # 在目标位置附近找最近的静音点（±10秒范围内）
        best_point = target_pos
        min_distance = float('inf')
        
        for sp in silence_points:
            if current_pos < sp < current_pos + target_duration + 10:
                distance = abs(sp - target_pos)
                if distance < min_distance and distance < 10:
                    min_distance = distance
                    best_point = sp
        
        split_points.append(best_point)
        current_pos = best_point
    
    split_points.append(total_duration)
    
    logger.info(f"语义分割点: {len(split_points)-1} 段")
    
    # 分割音频
    segments = []
    base_name = Path(audio_path).stem
    
    for i in range(len(split_points) - 1):
        start = split_points[i]
        end = split_points[i + 1]
        segment_path = os.path.join(output_dir, f"{base_name}_{i:04d}_{int(start):06d}.mp3")
        
        split_cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start), "-to", str(end),
            "-ar", "16000", "-ac", "1", "-b:a", "32k",
            "-f", "mp3", segment_path
        ]
        
        try:
            subprocess.run(split_cmd, capture_output=True, check=True)
            segments.append((segment_path, start))
            logger.debug(f"分割片段 {i+1}: {start:.2f}-{end:.2f}秒")
        except subprocess.CalledProcessError as e:
            logger.error(f"分割片段 {i+1} 失败: {e}")
            raise
    
    logger.info(f"音频语义分割完成，共 {len(segments)} 个片段")
    return segments


def recognize_with_bailian(
    audio_path: str,
    model: Optional[str] = None,
    language: str = "zh",
    segment_duration: int = 300,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    使用百炼 ASR 识别音频/视频（支持大文件自动分片，语义分割）
    
    处理流程:
    1. 如果是视频，先提取音频
    2. 如果音频 > 10MB，使用语义分割（在静音点处分割）
    3. 逐段识别并合并结果
    
    Args:
        audio_path: 音频/视频文件路径
        model: 模型名称，None 则自动选择
        language: 语言
        segment_duration: 目标分片时长（秒），默认 5 分钟
        
    Returns:
        识别结果分段列表
    """
    import tempfile
    
    service = get_bailian_service()
    temp_files_to_cleanup = []
    
    try:
        # 判断文件类型
        ext = Path(audio_path).suffix.lower()
        is_video = ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
        
        # 步骤 1: 如果是视频，提取音频
        if is_video:
            logger.info(f"检测到视频文件，先提取音频: {audio_path}")
            temp_audio = os.path.join(tempfile.mkdtemp(), "extracted_audio.mp3")
            audio_path = _extract_audio_from_video(audio_path, temp_audio)
            temp_files_to_cleanup.append(audio_path)
        
        # 步骤 2: 检查音频大小
        file_size = os.path.getsize(audio_path)
        file_size_mb = file_size / 1024 / 1024
        
        if file_size_mb <= 10:  # 小于 10MB 直接用短音频接口
            model = model or "qwen3-asr-flash"
            logger.info(f"使用百炼短音频识别: {audio_path} ({file_size_mb:.2f}MB)")
            result = service.recognize_short_audio(audio_path, model=model, language=language, **kwargs)
            return service.parse_result_to_segments(result)
        
        # 步骤 3: 大文件使用语义分割
        logger.info(f"音频较大 ({file_size_mb:.2f}MB)，使用语义分割识别")
        
        segments_info = _split_audio_semantic(audio_path, segment_duration=segment_duration)
        all_segments = []
        
        for idx, (segment_path, time_offset) in enumerate(segments_info):
            logger.info(f"识别片段 {idx + 1}/{len(segments_info)} (偏移: {time_offset:.2f}s)")
            
            try:
                result = service.recognize_short_audio(
                    segment_path, 
                    model="qwen3-asr-flash", 
                    language=language, 
                    **kwargs
                )
                segments = service.parse_result_to_segments(result)
                
                # 调整时间戳
                for seg in segments:
                    seg["start"] += time_offset
                    seg["end"] += time_offset
                
                all_segments.extend(segments)
                
                # 清理临时片段文件
                try:
                    os.remove(segment_path)
                except OSError:
                    pass
                    
            except Exception as e:
                logger.error(f"片段 {idx + 1} 识别失败: {e}")
                # 继续处理其他片段
        
        # 清理分割临时目录
        if segments_info:
            try:
                os.rmdir(os.path.dirname(segments_info[0][0]))
            except OSError:
                pass
        
        logger.info(f"语义分片识别完成，共 {len(all_segments)} 段结果")
        return all_segments
        
    finally:
        # 清理临时提取的音频文件
        for temp_file in temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"清理临时文件: {temp_file}")
            except OSError:
                pass
