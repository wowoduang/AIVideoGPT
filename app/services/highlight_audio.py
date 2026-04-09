from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Sequence

from loguru import logger

from app.services.video_working_copy import ensure_working_video_copy
from app.utils import utils


_AUDIO_ANALYSIS_CACHE_VERSION = "2026-04-09-highlight-audio-v1"
_TARGET_SR = 16000
_FRAME_HOP = 512


def _librosa_bundle():
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore

        return librosa, np
    except Exception:
        return None, None


def audio_signal_analysis_available() -> bool:
    librosa, np = _librosa_bundle()
    return librosa is not None and np is not None


def _build_audio_analysis_path(video_path: str) -> str:
    cache_key = utils.md5(
        "|".join(
            [
                os.path.abspath(video_path),
                str(os.path.getmtime(video_path)),
                str(os.path.getsize(video_path)),
                _AUDIO_ANALYSIS_CACHE_VERSION,
            ]
        )
    )
    return os.path.join(utils.temp_dir("highlight_audio"), f"{cache_key}.wav")


def _extract_audio_analysis_file(video_path: str) -> str:
    analysis_path = _build_audio_analysis_path(video_path)
    if os.path.isfile(analysis_path) and os.path.getsize(analysis_path) > 0:
        return analysis_path

    source_path = ensure_working_video_copy(video_path, purpose="highlight_audio_analysis")
    os.makedirs(os.path.dirname(analysis_path), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source_path,
        "-vn",
        "-map",
        "0:a:0?",
        "-ac",
        "1",
        "-ar",
        str(_TARGET_SR),
        "-c:a",
        "pcm_s16le",
        analysis_path,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode == 0 and os.path.isfile(analysis_path) and os.path.getsize(analysis_path) > 0:
        return analysis_path

    if os.path.exists(analysis_path):
        try:
            os.remove(analysis_path)
        except OSError:
            pass
    logger.warning(
        "Highlight audio analysis extract failed for {}: {}",
        os.path.basename(video_path),
        _summarize_process_error(completed.stderr),
    )
    return ""


def _summarize_process_error(stderr: str, max_lines: int = 4, max_chars: int = 300) -> str:
    lines = [line.strip() for line in str(stderr or "").splitlines() if line.strip()]
    if not lines:
        return "unknown error"
    summary = " | ".join(lines[-max_lines:])
    return summary[-max_chars:] if len(summary) > max_chars else summary


def _robust_normalize(values, np_module):
    arr = np_module.asarray(values, dtype=np_module.float32)
    if arr.size == 0:
        return arr
    finite = arr[np_module.isfinite(arr)]
    if finite.size == 0:
        return np_module.zeros_like(arr, dtype=np_module.float32)
    lo = float(np_module.percentile(finite, 10))
    hi = float(np_module.percentile(finite, 95))
    if hi <= lo + 1e-8:
        peak = float(np_module.max(finite))
        if peak <= 1e-8:
            return np_module.zeros_like(arr, dtype=np_module.float32)
        return np_module.clip(arr / peak, 0.0, 1.0).astype(np_module.float32)
    return np_module.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np_module.float32)


def build_audio_signal_context(video_path: str) -> Dict[str, Any]:
    librosa, np = _librosa_bundle()
    if librosa is None or np is None:
        return {"available": False, "reason": "librosa_unavailable"}
    if not video_path or not os.path.isfile(video_path):
        return {"available": False, "reason": "video_missing"}

    audio_path = _extract_audio_analysis_file(video_path)
    if not audio_path:
        return {"available": False, "reason": "audio_extract_failed"}

    try:
        waveform, sample_rate = librosa.load(audio_path, sr=_TARGET_SR, mono=True)
    except Exception as exc:
        logger.warning("Highlight audio analysis load failed for {}: {}", os.path.basename(video_path), exc)
        return {"available": False, "reason": "audio_load_failed"}

    if waveform is None or len(waveform) == 0:
        return {"available": False, "reason": "empty_audio"}

    try:
        rms = librosa.feature.rms(y=waveform, frame_length=2048, hop_length=_FRAME_HOP)[0]
        onset = librosa.onset.onset_strength(y=waveform, sr=sample_rate, hop_length=_FRAME_HOP)
        delta = np.abs(np.diff(rms, prepend=rms[0] if rms.size else 0.0))
    except Exception as exc:
        logger.warning("Highlight audio analysis feature extraction failed for {}: {}", os.path.basename(video_path), exc)
        return {"available": False, "reason": "feature_extract_failed"}

    rms_norm = _robust_normalize(rms, np)
    onset_norm = _robust_normalize(onset, np)
    delta_norm = _robust_normalize(delta, np)
    signal = _robust_normalize(rms_norm * 0.5 + onset_norm * 0.3 + delta_norm * 0.2, np)

    return {
        "available": True,
        "audio_path": audio_path,
        "sample_rate": int(sample_rate),
        "hop_length": int(_FRAME_HOP),
        "frame_times": librosa.frames_to_time(np.arange(len(signal)), sr=sample_rate, hop_length=_FRAME_HOP),
        "rms": rms_norm,
        "onset": onset_norm,
        "delta": delta_norm,
        "signal": signal,
    }


def _slice_window_indices(frame_times, start: float, end: float) -> tuple[int, int]:
    if end <= start:
        end = start + 0.4
    start_idx = 0
    end_idx = len(frame_times)
    try:
        import numpy as np  # type: ignore

        start_idx = int(np.searchsorted(frame_times, max(float(start), 0.0), side="left"))
        end_idx = int(np.searchsorted(frame_times, max(float(end), 0.0), side="right"))
    except Exception:
        for idx, value in enumerate(frame_times):
            if value >= start:
                start_idx = idx
                break
        for idx, value in enumerate(frame_times):
            if value > end:
                end_idx = idx
                break
    if end_idx <= start_idx:
        end_idx = min(start_idx + 1, len(frame_times))
    return max(start_idx, 0), max(end_idx, 0)


def compute_audio_scores_for_clips(
    clip_windows: Sequence[Dict[str, Any]],
    audio_context: Dict[str, Any],
) -> List[Dict[str, float]]:
    if not clip_windows:
        return []
    if not audio_context or not audio_context.get("available"):
        return [
            {
                "audio_rms_score": 0.0,
                "audio_onset_score": 0.0,
                "audio_dynamic_score": 0.0,
                "audio_signal_score": 0.0,
                "audio_peak_score": 0.0,
            }
            for _ in clip_windows
        ]

    frame_times = audio_context.get("frame_times")
    if frame_times is None:
        frame_times = []
    rms = audio_context.get("rms")
    if rms is None:
        rms = []
    onset = audio_context.get("onset")
    if onset is None:
        onset = []
    delta = audio_context.get("delta")
    if delta is None:
        delta = []
    signal = audio_context.get("signal")
    if signal is None:
        signal = []

    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None

    results: List[Dict[str, float]] = []
    for clip in clip_windows:
        start = float(clip.get("start", 0.0) or 0.0)
        end = float(clip.get("end", start) or start)
        start_idx, end_idx = _slice_window_indices(frame_times, start, end)
        rms_slice = rms[start_idx:end_idx]
        onset_slice = onset[start_idx:end_idx]
        delta_slice = delta[start_idx:end_idx]
        signal_slice = signal[start_idx:end_idx]

        if np is not None:
            rms_score = float(np.mean(rms_slice)) if len(rms_slice) else 0.0
            onset_score = float(np.mean(onset_slice)) if len(onset_slice) else 0.0
            dynamic_score = float(np.mean(delta_slice)) if len(delta_slice) else 0.0
            signal_score = float(np.mean(signal_slice)) if len(signal_slice) else 0.0
            peak_score = float(np.max(signal_slice)) if len(signal_slice) else 0.0
        else:
            rms_score = sum(rms_slice) / len(rms_slice) if rms_slice else 0.0
            onset_score = sum(onset_slice) / len(onset_slice) if onset_slice else 0.0
            dynamic_score = sum(delta_slice) / len(delta_slice) if delta_slice else 0.0
            signal_score = sum(signal_slice) / len(signal_slice) if signal_slice else 0.0
            peak_score = max(signal_slice) if signal_slice else 0.0

        results.append(
            {
                "audio_rms_score": round(max(min(rms_score, 1.0), 0.0), 3),
                "audio_onset_score": round(max(min(onset_score, 1.0), 0.0), 3),
                "audio_dynamic_score": round(max(min(dynamic_score, 1.0), 0.0), 3),
                "audio_signal_score": round(max(min(signal_score, 1.0), 0.0), 3),
                "audio_peak_score": round(max(min(peak_score, 1.0), 0.0), 3),
            }
        )
    return results


def summarize_audio_scores(audio_scores: Sequence[Dict[str, float]]) -> Dict[str, Any]:
    scores = list(audio_scores or [])
    if not scores:
        return {
            "audio_signal_used": False,
            "audio_signal_clip_count": 0,
            "audio_raw_candidate_count": 0,
            "audio_signal_mean": 0.0,
            "audio_peak_mean": 0.0,
        }

    signal_values = [float(item.get("audio_signal_score", 0.0) or 0.0) for item in scores]
    peak_values = [float(item.get("audio_peak_score", 0.0) or 0.0) for item in scores]
    return {
        "audio_signal_used": True,
        "audio_signal_clip_count": len(scores),
        "audio_raw_candidate_count": sum(
            1 for item in scores if float(item.get("audio_signal_score", 0.0) or 0.0) >= 0.58 or float(item.get("audio_peak_score", 0.0) or 0.0) >= 0.72
        ),
        "audio_signal_mean": round(sum(signal_values) / max(len(signal_values), 1), 3),
        "audio_peak_mean": round(sum(peak_values) / max(len(peak_values), 1), 3),
    }
