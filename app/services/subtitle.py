import os
import os.path
import re
import sys
import traceback
import subprocess
import json
from typing import Optional, List, Tuple, Dict, Any

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

try:
    from funasr import AutoModel as FunASRAutoModel
except Exception:
    FunASRAutoModel = None

from timeit import default_timer as timer
from loguru import logger
import google.generativeai as genai
from moviepy import VideoFileClip

from app.config import config
from app.services.subtitle_external import is_external_backend, normalize_external_backend, run_external_subtitle_backend
from app.services.video_working_copy import ensure_working_video_copy
from app.utils import utils


model_size = config.whisper.get("model_size", "faster-whisper-large-v3")
backend_name = str(config.whisper.get("backend", "")).strip().lower()
device = config.whisper.get("device", "cpu")
compute_type = config.whisper.get("compute_type", "int8")
model = None
_model_identity = None

DEFAULT_AUDIO_SAMPLE_RATE = int(config.whisper.get("audio_sample_rate", 16000))
DEFAULT_AUDIO_CHANNELS = int(config.whisper.get("audio_channels", 1))
DEFAULT_AUDIO_BITRATE = str(config.whisper.get("audio_bitrate", "32k"))
DEFAULT_FORCE_LANGUAGE = str(config.whisper.get("language", config.ui.get("language", "zh"))).strip() or None
DEFAULT_BEAM_SIZE = int(config.whisper.get("beam_size", 5))
DEFAULT_BEST_OF = int(config.whisper.get("best_of", 5))
DEFAULT_VAD_MIN_SILENCE_MS = int(config.whisper.get("vad_min_silence_duration_ms", 400))
DEFAULT_INITIAL_PROMPT = str(config.whisper.get("initial_prompt", "") or "").strip()
DEFAULT_AUDIO_FILTER = config.whisper.get("audio_filter", "highpass=f=120,lowpass=f=3800,volume=1.8")
DEFAULT_FUNASR_BATCH_SIZE_S = int(config.whisper.get("funasr_batch_size_s", 180))
DEFAULT_FUNASR_MERGE_LENGTH_S = int(config.whisper.get("funasr_merge_length_s", 15))
DEFAULT_FUNASR_USE_ITN = bool(config.whisper.get("funasr_use_itn", True))
DEFAULT_FUNASR_VAD_SEGMENT_MS = int(config.whisper.get("funasr_max_single_segment_time_ms", 30000))
DEFAULT_FUNASR_VAD_MODEL = str(config.whisper.get("funasr_vad_model", "")).strip()

MODEL_CANDIDATES = {
    "sensevoice": ["SenseVoiceSmall", "SenseVoiceSmall-onnx", "iic/SenseVoiceSmall"],
    "faster-whisper": ["faster-whisper-large-v3", "faster-whisper-large-v2", "large-v3", "large-v2"],
    "funasr-vad": ["speech_fsmn_vad_zh-cn-16k-common-pytorch", "speech_fsmn_vad_zh-cn-16k-common", "fsmn-vad"],
}

_MODEL_FILES = ("model.bin", "model.safetensors")

_CONTROL_TAG_GROUP_RE = re.compile(r"(?:<\|[^|]+?\|>\s*)+")
_CONTROL_TAG_RE = re.compile(r"<\|[^|]+?\|>")
_ASS_TAG_RE = re.compile(r"\{\\[^{}]*\}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"[ \t\u3000]+")
_DUP_PUNC_RE = re.compile(r"([，。！？；：,.!?;:])\1{1,}")
_GARBAGE_WORDS_RE = re.compile(r"\b(?:Speech|BGM|EMO_UNKNOWN|NEUTRAL|HAPPY|ANGRY|SAD|FEAR|SURPRISE|DISGUST|withitn|withit|withint)\b", re.IGNORECASE)
_LEADING_PUNCT_RE = re.compile(r"^[锛屻€傦紒锛燂紱锛氥€佲€溾€濃€樷€欍€娿€嬨€?.!?;:\]\)\}]+")
_FILLER_ONLY_RE = re.compile(r"^[鍟婂摝璇跺攭娆稿搱鍝煎棷鍠傚憖]+[锛屻€傦紒锛燂紝,.!?]*$")
_TERMINAL_PUNCT = ("锛?", "锛?", "銆?", ".", "!", "?", "锛?", ";")

_CUE_ONLY_PATTERNS = [
    r"^\(?\s*(bgm|music|applause|laughter|laughing|sigh|crying|phone ringing|ringtone)\s*\)?$",
    r"^\(?\s*(音乐|配乐|背景音乐|掌声|笑声|哭声|叹气|铃声|电话铃声|风声|雨声|脚步声|鼓掌)\s*\)?$",
    r"^\[?\s*(bgm|music|applause|laughter|laughing|sigh|crying)\s*\]?$",
    r"^\[?\s*(音乐|配乐|背景音乐|掌声|笑声|哭声)\s*\]?$",
]
_CUE_ONLY_RE = re.compile("|".join(_CUE_ONLY_PATTERNS), re.IGNORECASE)
_PROMPT_POLLUTION_MARKERS = tuple(
    x for x in (
        str(DEFAULT_INITIAL_PROMPT or "").strip(),
        "以下是中文影视对白，请尽量准确识别人名、称谓、短句回应和语气词。",
        "请尽量准确识别人名、称谓、短句回应和语气词。",
    ) if x
)

_SEGMENT_JSON_SUFFIX = "_segments.json"
_RAW_SRT_SUFFIX = "_raw.srt"
_CLEAN_SRT_SUFFIX = "_clean.srt"


def _base_dirs() -> List[str]:
    seen: set = set()
    bases: List[str] = []
    for raw in (utils.root_dir(), os.getcwd(), os.path.dirname(os.path.abspath(sys.executable))):
        d = os.path.abspath(raw)
        if d not in seen:
            seen.add(d)
            bases.append(d)
    return bases


def _normalize_backend() -> str:
    external_backend = normalize_external_backend(backend_name)
    if external_backend:
        return external_backend
    if backend_name:
        if "sensevoice" in backend_name:
            return "sensevoice"
        if "paraformer" in backend_name or "funasr" in backend_name:
            return "funasr"
        if "whisper" in backend_name:
            return "faster-whisper"
        return backend_name
    lowered = str(model_size or "").strip().lower()
    if "sensevoice" in lowered:
        return "sensevoice"
    if "paraformer" in lowered:
        return "funasr"
    return "faster-whisper"


CURRENT_BACKEND = _normalize_backend()


def _resolve_runtime_backend(backend_override: Optional[str] = None) -> str:
    value = str(backend_override or "").strip().lower()
    if not value:
        return CURRENT_BACKEND
    external_backend = normalize_external_backend(value)
    if external_backend:
        return external_backend
    if "sensevoice" in value:
        return "sensevoice"
    if "paraformer" in value or "funasr" in value:
        return "funasr"
    if "whisper" in value:
        return "faster-whisper"
    return CURRENT_BACKEND



def _derive_debug_paths(subtitle_file: str) -> Tuple[str, str]:
    root, ext = os.path.splitext(subtitle_file)
    if not ext:
        ext = ".srt"
    return f"{root}{_RAW_SRT_SUFFIX}", f"{root}{_CLEAN_SRT_SUFFIX}"


def _derive_segments_json_path(subtitle_file: str) -> str:
    root, _ = os.path.splitext(subtitle_file)
    return f"{root}{_SEGMENT_JSON_SUFFIX}"


def _clean_subtitle_text(text: str) -> str:
    text = text or ""
    for marker in _PROMPT_POLLUTION_MARKERS:
        if marker and marker in text:
            text = text.replace(marker, " ")
    text = _CONTROL_TAG_GROUP_RE.sub("\n", text)
    text = _ASS_TAG_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _CONTROL_TAG_RE.sub("", text)
    text = _GARBAGE_WORDS_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[·•]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = re.sub(r"\s*([，。！？；：、“”‘’《》、,.!?;:])\s*", r"\1", text)
    text = _DUP_PUNC_RE.sub(r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"（\s*）", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    return text.strip()


def _is_short_prefix_fragment(text: str) -> bool:
    cleaned = _clean_subtitle_text(text)
    if not cleaned:
        return False
    core = _normalize_text_core(cleaned)
    if not core:
        return True
    if _LEADING_PUNCT_RE.match(cleaned):
        return True
    if _FILLER_ONLY_RE.match(cleaned):
        return True
    if len(core) <= 2 and not cleaned.endswith(_TERMINAL_PUNCT):
        return True
    return False


def _merge_adjacent_text(left: str, right: str) -> str:
    left = _clean_subtitle_text(left or "")
    right = _clean_subtitle_text(right or "")
    if not left:
        return right
    if not right:
        return left
    if _LEADING_PUNCT_RE.match(right):
        right = _LEADING_PUNCT_RE.sub("", right, count=1).strip()
    if not right:
        return left
    return _clean_subtitle_text(f"{left}{right}")


def _is_meaningful_subtitle_text(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    for marker in _PROMPT_POLLUTION_MARKERS:
        if not marker:
            continue
        compact = stripped.replace(" ", "")
        marker_compact = marker.replace(" ", "")
        if stripped == marker or compact == marker_compact or compact in marker_compact:
            return False
    if _CUE_ONLY_RE.match(stripped):
        return False
    if not re.sub(r"[，。！？；：、“”‘’《》、,.!?;:\-\—~…·\s]", "", stripped):
        return False
    return True


def _normalize_text_core(text: str) -> str:
    return re.sub(r"[，。！？；：、“”‘’《》、,.!?;:\-\—~…·\s]", "", text or "")


def _extract_clean_sentence_units(text: str) -> List[str]:
    cleaned = _clean_subtitle_text(text)
    if not cleaned:
        return []
    coarse_parts = [p.strip() for p in cleaned.split("\n") if p.strip()]
    final_parts: List[str] = []
    for part in coarse_parts:
        if not _is_meaningful_subtitle_text(part):
            continue
        strong_parts = [seg.strip() for seg in re.split(r"(?<=[。！？!?；;])", part) if seg.strip()]
        refined: List[str] = []
        for seg in strong_parts:
            if len(seg) > 42:
                comma_parts = [x.strip() for x in re.split(r"(?<=[，,])", seg) if x.strip()]
                refined.extend(comma_parts or [seg])
            else:
                refined.append(seg)
        for seg in refined:
            seg = _clean_subtitle_text(seg)
            if _is_meaningful_subtitle_text(seg):
                final_parts.append(seg)
    return final_parts


def _is_valid_model_dir(path: str) -> bool:
    return any(os.path.isfile(os.path.join(path, f)) for f in _MODEL_FILES)


def _candidate_model_dirs(names: List[str]) -> List[str]:
    dirs: List[str] = []
    seen: set = set()
    for base in _base_dirs():
        for name in names:
            if not name:
                continue
            raw_name = str(name).strip()
            if not raw_name:
                continue

            direct_candidates: List[str] = []
            if os.path.isabs(raw_name):
                direct_candidates.append(os.path.abspath(raw_name))
            else:
                normalized = raw_name.replace("/", os.sep).replace("\\", os.sep)
                if os.path.sep in normalized:
                    direct_candidates.append(os.path.abspath(os.path.join(utils.root_dir(), normalized)))
                    direct_candidates.append(os.path.abspath(normalized))

            for candidate in direct_candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    dirs.append(candidate)

            if "/" in raw_name or "\\" in raw_name:
                continue

            base_candidates = [
                os.path.abspath(os.path.join(base, "app", "models", raw_name)),
                os.path.abspath(os.path.join(base, "models", raw_name)),
                os.path.abspath(os.path.join(utils.model_dir(), raw_name)),
            ]
            for candidate in base_candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    dirs.append(candidate)
    return dirs


def _resolve_local_model_path(names: List[str], *, require_ctranslate2: bool = False) -> Tuple[Optional[str], List[str]]:
    searched = _candidate_model_dirs(names)
    for path in searched:
        if os.path.isdir(path):
            if not require_ctranslate2 or _is_valid_model_dir(path):
                return path, searched
            try:
                contents = os.listdir(path)
            except OSError:
                contents = []
            logger.warning(f"模型目录存在但未找到模型文件 ({', '.join(_MODEL_FILES)}): {path}\n目录内容: {contents}")
    return None, searched


def _resolve_faster_whisper_model_path() -> Tuple[Optional[str], List[str]]:
    requested = (str(model_size or "").strip() or MODEL_CANDIDATES["faster-whisper"][0])
    candidates = [requested]
    for fallback in MODEL_CANDIDATES["faster-whisper"]:
        if fallback not in candidates:
            candidates.append(fallback)
    return _resolve_local_model_path(candidates, require_ctranslate2=True)


def _resolve_sensevoice_model_ref() -> Tuple[str, List[str]]:
    requested = str(model_size or "").strip()
    candidates = []
    if requested:
        candidates.append(requested)
    candidates.extend(MODEL_CANDIDATES["sensevoice"])
    local_path, searched = _resolve_local_model_path(candidates, require_ctranslate2=False)
    if local_path:
        return local_path, searched
    if requested and os.path.isdir(requested):
        return requested, searched
    if requested and "/" in requested:
        return requested, searched
    return "iic/SenseVoiceSmall", searched


def _resolve_funasr_vad_model_ref() -> Tuple[str, List[str]]:
    requested = DEFAULT_FUNASR_VAD_MODEL
    candidates = []
    if requested:
        candidates.append(requested)
    candidates.extend(MODEL_CANDIDATES["funasr-vad"])
    local_path, searched = _resolve_local_model_path(candidates, require_ctranslate2=False)
    if local_path:
        return local_path, searched
    if requested:
        return requested, searched
    return "fsmn-vad", searched


def _load_faster_whisper_model() -> bool:
    global model, device, compute_type, _model_identity
    if WhisperModel is None:
        logger.error("未安装 faster-whisper，请先安装依赖后再使用自动字幕生成")
        return False
    model_path, searched = _resolve_faster_whisper_model_path()
    if not model_path:
        searched_text = "\n".join([f"- {p}" for p in searched])
        bases_text = "\n".join([f"- {d}" for d in _base_dirs()])
        logger.error(
            "请先下载 whisper 模型\n\n"
            "********************************************\n"
            "推荐下载：\n"
            "https://huggingface.co/guillaumekln/faster-whisper-large-v3\n"
            "或：\n"
            "https://huggingface.co/guillaumekln/faster-whisper-large-v2\n\n"
            "存放路径示例：workspace/models/faster-whisper-large-v3\n"
            "兼容旧路径：app/models/faster-whisper-large-v3\n\n"
            f"root_dir(): {utils.root_dir()}\n"
            f"cwd: {os.getcwd()}\n"
            f"executable: {sys.executable}\n\n"
            "搜索基础目录：\n"
            f"{bases_text}\n\n"
            "已搜索目录：\n"
            f"{searched_text}\n"
            "********************************************\n"
        )
        return False

    identity = f"faster-whisper::{model_path}"
    if model is not None and _model_identity == identity:
        return True

    use_cuda = False
    try:
        import torch
        use_cuda = torch.cuda.is_available()
    except Exception:
        use_cuda = False

    if use_cuda:
        try:
            model = WhisperModel(model_size_or_path=model_path, device="cuda", compute_type="float16", local_files_only=True)
            device = "cuda"
            compute_type = "float16"
            _model_identity = identity
            logger.info("成功使用 CUDA 加载 faster-whisper 模型")
            return True
        except Exception as e:
            logger.warning(f"CUDA 加载 faster-whisper 失败，回退到 CPU: {e}")

    device = "cpu"
    compute_type = "int8"
    model = WhisperModel(model_size_or_path=model_path, device=device, compute_type=compute_type, local_files_only=True)
    _model_identity = identity
    logger.info(f"模型加载完成，使用设备: {device}, 计算类型: {compute_type}")
    return True


def _sensevoice_device() -> str:
    prefer = str(config.whisper.get("device", device)).strip().lower() or "cpu"
    if prefer in {"cuda", "gpu"}:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
    return "cpu"


def _load_sensevoice_model() -> bool:
    global model, _model_identity
    if FunASRAutoModel is None:
        logger.error("未安装 funasr，请先安装 funasr 和 modelscope 后再使用 SenseVoice-Small")
        return False
    model_ref, searched = _resolve_sensevoice_model_ref()
    vad_ref, vad_searched = _resolve_funasr_vad_model_ref()
    identity = f"sensevoice::{model_ref}::{vad_ref}"
    if model is not None and _model_identity == identity:
        return True
    try:
        model = FunASRAutoModel(
            model=model_ref,
            vad_model=vad_ref,
            vad_kwargs={"max_single_segment_time": DEFAULT_FUNASR_VAD_SEGMENT_MS},
            device=_sensevoice_device(),
            disable_progress_bar=True,
        )
        _model_identity = identity
        return True
    except Exception as e:
        logger.error(
            "加载 SenseVoice-Small 失败。\n"
            f"model={model_ref}\n"
            f"vad_model={vad_ref}\n"
            f"searched_models={searched}\n"
            f"searched_vad={vad_searched}\n"
            f"error={e}"
        )
        return False


def _normalize_language_code(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    lang = str(lang).strip().lower()
    mapping = {"zh-cn": "zh", "zh_simplified": "zh", "zh-hans": "zh", "cn": "zh", "chs": "zh", "zn": "zh"}
    return mapping.get(lang, lang)


def _safe_file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0.0


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False


def _extract_audio_ffmpeg(video_file: str, audio_file: str) -> bool:
    os.makedirs(os.path.dirname(audio_file), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", video_file, "-vn", "-map", "a:0", "-ac", str(DEFAULT_AUDIO_CHANNELS), "-ar", str(DEFAULT_AUDIO_SAMPLE_RATE), "-af", DEFAULT_AUDIO_FILTER, "-c:a", "libmp3lame", "-b:a", DEFAULT_AUDIO_BITRATE, audio_file]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return proc.returncode == 0 and os.path.exists(audio_file)


def _append_subtitle_line(subtitles: List[Dict[str, Any]], seg_text: str, seg_start: float, seg_end: float):
    seg_text = _clean_subtitle_text(seg_text or "")
    if not _is_meaningful_subtitle_text(seg_text):
        return
    seg_start = max(0.0, float(seg_start or 0.0))
    seg_end = max(seg_start, float(seg_end or seg_start))
    subtitles.append({"msg": seg_text, "start_time": seg_start, "end_time": seg_end})


def _append_raw_subtitle_line(raw_subtitles: List[Dict[str, Any]], seg_text: str, seg_start: float, seg_end: float):
    seg_text = (seg_text or "").strip()
    if not seg_text:
        return
    seg_start = max(0.0, float(seg_start or 0.0))
    seg_end = max(seg_start, float(seg_end or seg_start))
    raw_subtitles.append({"msg": seg_text, "start_time": seg_start, "end_time": seg_end})


def _coerce_seconds(value: Any) -> float:
    try:
        num = float(value)
    except Exception:
        return 0.0
    return num / 1000.0 if num > 1000 else num


def _split_sentences_keep_punctuation(text: str) -> List[str]:
    parts = _extract_clean_sentence_units(text)
    if parts:
        return parts
    text = _clean_subtitle_text(text)
    if not _is_meaningful_subtitle_text(text):
        return []
    parts = [seg.strip() for seg in re.split(r"(?<=[。！？!?；;])\s*", text) if seg.strip()]
    if len(parts) <= 1:
        parts = [seg.strip() for seg in re.split(r"(?<=[，,])\s*", text) if seg.strip()]
    if len(parts) <= 1:
        parts = utils.split_string_by_punctuations(text)
    return [seg.strip() for seg in parts if _is_meaningful_subtitle_text(seg)] or ([text] if _is_meaningful_subtitle_text(text) else [])


def _extract_word_items(segment) -> List[Dict[str, float]]:
    words = getattr(segment, "words", None) or []
    result: List[Dict[str, float]] = []
    for w in words:
        try:
            word_text = str(getattr(w, "word", "") or "").strip()
            word_start = float(getattr(w, "start", 0.0) or 0.0)
            word_end = float(getattr(w, "end", word_start) or word_start)
        except Exception:
            continue
        if word_end < word_start:
            word_end = word_start
        result.append({"word": word_text, "start": word_start, "end": word_end})
    return result


def _append_split_subtitle_lines(subtitles: List[Dict[str, Any]], text: str, start: float, end: float) -> int:
    text = _clean_subtitle_text(text or "")
    if not _is_meaningful_subtitle_text(text):
        return 0
    start = max(0.0, float(start or 0.0))
    end = max(start, float(end or start))
    sentences = _split_sentences_keep_punctuation(text)
    if not sentences:
        return 0
    if len(sentences) <= 1:
        _append_subtitle_line(subtitles, text, start, end)
        return 1
    total_chars = sum(max(1, len(_normalize_text_core(s)) or len(s)) for s in sentences)
    duration = max(0.0, end - start)
    if duration <= 0:
        duration = max(1.5, 2.6 * len(sentences))
        end = start + duration
    cursor = start
    appended = 0
    for idx, sentence in enumerate(sentences):
        weight = max(1, len(_normalize_text_core(sentence)) or len(sentence)) / total_chars
        seg_end = end if idx == len(sentences) - 1 else min(end, cursor + duration * weight)
        _append_subtitle_line(subtitles, sentence, cursor, seg_end)
        cursor = seg_end
        appended += 1
    return appended


def _append_split_subtitle_lines_with_words(subtitles: List[Dict[str, Any]], text: str, start: float, end: float, word_items: List[Dict[str, float]]) -> int:
    text = _clean_subtitle_text(text or "")
    if not _is_meaningful_subtitle_text(text):
        return 0
    sentences = _split_sentences_keep_punctuation(text)
    if not sentences:
        return 0
    if len(sentences) <= 1:
        _append_subtitle_line(subtitles, text, start, end)
        return 1
    if not word_items:
        return _append_split_subtitle_lines(subtitles, text, start, end)

    word_cores = [_normalize_text_core(item["word"]) for item in word_items]
    total_word_core_len = sum(len(core) for core in word_cores)
    if total_word_core_len <= 0:
        return _append_split_subtitle_lines(subtitles, text, start, end)

    consumed_word_idx = 0
    appended = 0
    cursor_start = max(0.0, float(start or 0.0))
    seg_end = max(cursor_start, float(end or cursor_start))

    for sent_idx, sentence in enumerate(sentences):
        sentence_core = _normalize_text_core(sentence)
        target_len = len(sentence_core)
        if target_len <= 0:
            continue
        sentence_word_start_idx = consumed_word_idx
        collected_len = 0
        while consumed_word_idx < len(word_items) and collected_len < target_len:
            collected_len += len(word_cores[consumed_word_idx])
            consumed_word_idx += 1
        if sentence_word_start_idx < len(word_items):
            sentence_start = float(word_items[sentence_word_start_idx]["start"])
            sentence_end = float(word_items[max(sentence_word_start_idx, consumed_word_idx - 1)]["end"])
        else:
            sentence_start = cursor_start
            sentence_end = seg_end
        if sent_idx == len(sentences) - 1:
            sentence_end = max(sentence_end, seg_end)
        if sentence_end < sentence_start:
            sentence_end = sentence_start
        _append_subtitle_line(subtitles, sentence, sentence_start, sentence_end)
        cursor_start = sentence_end
        appended += 1
    return appended


def _extract_item_time_range(item: Dict[str, Any]) -> Tuple[float, float]:
    sentence_info = item.get("sentence_info") or []
    if sentence_info:
        try:
            start = _coerce_seconds(sentence_info[0].get("start", 0.0))
            end = _coerce_seconds(sentence_info[-1].get("end", start))
            return start, max(start, end)
        except Exception:
            pass
    timestamp_pairs = item.get("timestamp") or []
    if timestamp_pairs:
        try:
            return _coerce_seconds(timestamp_pairs[0][0]), max(_coerce_seconds(timestamp_pairs[0][0]), _coerce_seconds(timestamp_pairs[-1][1]))
        except Exception:
            pass
    start = _coerce_seconds(item.get("start", 0.0))
    end = _coerce_seconds(item.get("end", start))
    return start, max(start, end)


def _parse_funasr_result_item(item: Dict[str, Any], subtitles: List[Dict[str, Any]], raw_subtitles: Optional[List[Dict[str, Any]]] = None) -> int:
    count = 0
    sentence_info = item.get("sentence_info") or []
    for sentence in sentence_info:
        if not isinstance(sentence, dict):
            continue
        text = sentence.get("text") or sentence.get("sentence") or ""
        start = _coerce_seconds(sentence.get("start", 0.0))
        end = _coerce_seconds(sentence.get("end", start))
        if raw_subtitles is not None:
            _append_raw_subtitle_line(raw_subtitles, text, start, end)
        count += _append_split_subtitle_lines(subtitles, text, start, end)
    if count:
        return count
    timestamp_pairs = item.get("timestamp") or []
    text = item.get("text") or item.get("sentence") or ""
    if timestamp_pairs and text:
        try:
            start = _coerce_seconds(timestamp_pairs[0][0])
            end = _coerce_seconds(timestamp_pairs[-1][1])
            if raw_subtitles is not None:
                _append_raw_subtitle_line(raw_subtitles, text, start, end)
            return _append_split_subtitle_lines(subtitles, text, start, end)
        except Exception:
            pass
    if text:
        start, end = _extract_item_time_range(item)
        if raw_subtitles is not None:
            _append_raw_subtitle_line(raw_subtitles, text, start, end)
        return _append_split_subtitle_lines(subtitles, text, start, end)
    return 0


def _merge_overlapping_subtitles(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not subtitles:
        return []
    ordered = sorted(subtitles, key=lambda x: (float(x.get("start_time", 0.0) or 0.0), float(x.get("end_time", 0.0) or 0.0)))
    merged: List[Dict[str, Any]] = []
    for item in ordered:
        text = _clean_subtitle_text(item.get("msg") or "")
        if not _is_meaningful_subtitle_text(text):
            continue
        start = max(0.0, float(item.get("start_time", 0.0) or 0.0))
        end = max(start, float(item.get("end_time", start) or start))
        if merged:
            prev = merged[-1]
            prev_text = str(prev.get("msg") or "")
            prev_end = float(prev.get("end_time", 0.0) or 0.0)
            if text == prev_text and abs(start - float(prev.get("start_time", 0.0) or 0.0)) < 0.01:
                prev["end_time"] = max(prev_end, end)
                continue
            if start <= prev_end + 0.12 and (len(text) <= 4 or len(prev_text) <= 4):
                joined = _merge_adjacent_text(prev_text, text)
                if _is_meaningful_subtitle_text(joined):
                    prev["msg"] = joined
                    prev["end_time"] = max(prev_end, end)
                    continue
            if start <= prev_end + 0.35 and (
                _is_short_prefix_fragment(prev_text)
                or _is_short_prefix_fragment(text)
                or _LEADING_PUNCT_RE.match(text)
                or (not prev_text.endswith(_TERMINAL_PUNCT) and len(_normalize_text_core(prev_text)) <= 4)
            ):
                joined = _merge_adjacent_text(prev_text, text)
                if _is_meaningful_subtitle_text(joined):
                    prev["msg"] = joined
                    prev["end_time"] = max(prev_end, end)
                    continue
        merged.append({"msg": text, "start_time": start, "end_time": end})
    return merged


def _subtitles_to_srt(subtitles: List[Dict[str, Any]]) -> str:
    idx = 1
    lines: List[str] = []
    for subtitle in subtitles:
        text = subtitle.get("msg")
        if text:
            lines.append(utils.text_to_srt(idx, text, subtitle.get("start_time"), subtitle.get("end_time")))
            idx += 1
    return "\n".join(lines) + ("\n" if lines else "")


def _write_text_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _build_segments_payload(subtitles: List[Dict[str, Any]], *, source: str, backend: str) -> List[Dict[str, Any]]:
    payload = []
    for idx, item in enumerate(subtitles, start=1):
        payload.append({"id": idx, "start": float(item.get("start_time", 0.0) or 0.0), "end": float(item.get("end_time", 0.0) or 0.0), "text": str(item.get("msg") or ""), "source": source, "backend": backend, "confidence": None})
    return payload


def _write_segments_json(path: str, subtitles: List[Dict[str, Any]], *, source: str, backend: str):
    payload = _build_segments_payload(subtitles, source=source, backend=backend)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _create_with_sensevoice(audio_file: str, subtitle_file: str = ""):
    if not _load_sensevoice_model():
        return None
    if not subtitle_file:
        subtitle_file = f"{audio_file}.srt"
    raw_srt_path, clean_srt_path = _derive_debug_paths(subtitle_file)
    segments_json_path = _derive_segments_json_path(subtitle_file)
    forced_language = _normalize_language_code(DEFAULT_FORCE_LANGUAGE) or "zh"
    try:
        results = model.generate(input=audio_file, cache={}, language=forced_language, use_itn=DEFAULT_FUNASR_USE_ITN, batch_size_s=DEFAULT_FUNASR_BATCH_SIZE_S, merge_vad=True, merge_length_s=DEFAULT_FUNASR_MERGE_LENGTH_S, output_timestamp=True)
    except TypeError:
        results = model.generate(input=audio_file, cache={}, language=forced_language, use_itn=DEFAULT_FUNASR_USE_ITN, batch_size_s=DEFAULT_FUNASR_BATCH_SIZE_S, merge_vad=True, merge_length_s=DEFAULT_FUNASR_MERGE_LENGTH_S)
    subtitles: List[Dict[str, Any]] = []
    raw_subtitles: List[Dict[str, Any]] = []
    if isinstance(results, dict):
        results = [results]
    for item in results or []:
        if isinstance(item, dict):
            _parse_funasr_result_item(item, subtitles, raw_subtitles)
    raw_subtitles = _merge_overlapping_subtitles(raw_subtitles)
    subtitles = _merge_overlapping_subtitles(subtitles)
    if not subtitles:
        return None
    raw_srt = _subtitles_to_srt(raw_subtitles)
    clean_srt = _subtitles_to_srt(subtitles)
    _write_text_file(raw_srt_path, raw_srt)
    _write_text_file(clean_srt_path, clean_srt)
    _write_text_file(subtitle_file, clean_srt)
    _write_segments_json(segments_json_path, subtitles, source="auto_clean", backend="sensevoice")
    return subtitle_file if os.path.exists(subtitle_file) else None


def _create_with_faster_whisper(audio_file: str, subtitle_file: str = ""):
    global model
    if not _load_faster_whisper_model():
        return None
    if not subtitle_file:
        subtitle_file = f"{audio_file}.srt"
    raw_srt_path, clean_srt_path = _derive_debug_paths(subtitle_file)
    segments_json_path = _derive_segments_json_path(subtitle_file)
    forced_language = _normalize_language_code(DEFAULT_FORCE_LANGUAGE) or "zh"
    transcribe_kwargs = dict(
        audio=audio_file,
        beam_size=max(1, DEFAULT_BEAM_SIZE),
        best_of=max(1, DEFAULT_BEST_OF),
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(
            threshold=0.35,
            min_silence_duration_ms=DEFAULT_VAD_MIN_SILENCE_MS,
            speech_pad_ms=600,
        ),
        condition_on_previous_text=False,
        temperature=0.0,
        language=forced_language,
    )
    if DEFAULT_INITIAL_PROMPT:
        transcribe_kwargs["initial_prompt"] = DEFAULT_INITIAL_PROMPT
    segments, info = model.transcribe(**transcribe_kwargs)
    logger.info(
        "检测到的语言: '{}', probability: {:.2f}, vad_parameters={}",
        info.language,
        info.language_probability,
        transcribe_kwargs.get("vad_parameters", {}),
    )
    subtitles: List[Dict[str, Any]] = []
    raw_subtitles: List[Dict[str, Any]] = []
    for segment in segments:
        raw_text = getattr(segment, "text", "") or ""
        seg_start = float(getattr(segment, "start", 0.0) or 0.0)
        seg_end = float(getattr(segment, "end", 0.0) or 0.0)
        if not raw_text:
            continue
        _append_raw_subtitle_line(raw_subtitles, raw_text, seg_start, seg_end)
        word_items = _extract_word_items(segment)
        appended = _append_split_subtitle_lines_with_words(subtitles, raw_text, seg_start, seg_end, word_items)
        if appended <= 0:
            _append_split_subtitle_lines(subtitles, raw_text, seg_start, seg_end)
    raw_subtitles = _merge_overlapping_subtitles(raw_subtitles)
    subtitles = _merge_overlapping_subtitles(subtitles)
    if not subtitles:
        return None
    raw_srt = _subtitles_to_srt(raw_subtitles)
    clean_srt = _subtitles_to_srt(subtitles)
    _write_text_file(raw_srt_path, raw_srt)
    _write_text_file(clean_srt_path, clean_srt)
    _write_text_file(subtitle_file, clean_srt)
    _write_segments_json(segments_json_path, subtitles, source="auto_clean", backend="faster-whisper")
    return subtitle_file if os.path.exists(subtitle_file) else None


def _create_with_external_backend(video_file: str, audio_file: str, subtitle_file: str, backend: str):
    if not video_file:
        logger.warning("外部字幕后端缺少视频路径，无法调用: backend={}", backend)
        return None
    return run_external_subtitle_backend(
        backend,
        video_file=video_file,
        audio_file=audio_file,
        subtitle_file=subtitle_file,
    )


def create(audio_file, subtitle_file: str = "", backend_override: str = "", model_override: str = "", video_file: str = "", **kwargs):
    backend = _resolve_runtime_backend(backend_override)
    logger.info(f"字幕生成后端: requested={backend_override or CURRENT_BACKEND}, resolved={backend}")
    if is_external_backend(backend):
        result = _create_with_external_backend(video_file, audio_file, subtitle_file, backend)
        if result:
            return result
        logger.warning("external subtitle backend failed, fallback to native ASR: backend={}", backend)
    if backend in {"sensevoice", "funasr"}:
        result = _create_with_sensevoice(audio_file, subtitle_file)
        if result:
            return result
        logger.warning("SenseVoice-Small 字幕生成失败，回退到 faster-whisper")
    return _create_with_faster_whisper(audio_file, subtitle_file)


def file_to_subtitles(filename):
    if not filename or not os.path.isfile(filename):
        return []
    times_texts = []
    current_times = None
    current_text = ""
    index = 0
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            times = re.findall(r"([0-9]*:[0-9]*:[0-9]*,[0-9]*)", line)
            if times:
                current_times = line
            elif line.strip() == "" and current_times:
                index += 1
                times_texts.append((index, current_times.strip(), current_text.strip()))
                current_times, current_text = None, ""
            elif current_times:
                current_text += line
    return times_texts


def levenshtein_distance(a, b):
    n, m = len(a), len(b)
    if n > m:
        a, b = b, a
        n, m = m, n
    current = list(range(n + 1))
    for i in range(1, m + 1):
        previous, current = current, [i] + [0] * n
        for j in range(1, n + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if a[j - 1] != b[i - 1]:
                change += 1
            current[j] = min(add, delete, change)
    return current[n]


def similarity(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    distance = levenshtein_distance(a.lower(), b.lower())
    max_length = max(len(a), len(b))
    if max_length == 0:
        return 1.0
    return 1 - (distance / max_length)


def correct(subtitle_file, video_script):
    subtitle_items = file_to_subtitles(subtitle_file)
    script_lines = utils.split_string_by_punctuations(video_script)
    return subtitle_items, script_lines


def create_with_gemini(audio_file: str, subtitle_file: str, api_key: str):
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    prompt = "生成这段语音的转录文本。请以SRT格式输出，包含时间戳。"
    try:
        with open(audio_file, "rb") as f:
            audio_data = f.read()
        response = gemini_model.generate_content([prompt, audio_data])
        transcript = response.text
        if not subtitle_file:
            subtitle_file = f"{audio_file}.srt"
        with open(subtitle_file, "w", encoding="utf-8") as f:
            f.write(transcript)
        return subtitle_file
    except Exception:
        return None


def extract_audio_and_create_subtitle(video_file: str, subtitle_file: str = "", backend_override: str = "", model_override: str = "", **kwargs) -> Optional[str]:
    audio_file = ""
    video = None
    try:
        processing_video_file = ensure_working_video_copy(video_file, purpose="subtitle_audio_extract")
        video_name = os.path.splitext(os.path.basename(video_file))[0]
        audio_dir = utils.temp_dir("audio_extract")
        os.makedirs(audio_dir, exist_ok=True)
        audio_file = os.path.join(audio_dir, f"{video_name}_speech.mp3")
        if not subtitle_file:
            subtitle_dir = utils.temp_dir("subtitles")
            os.makedirs(subtitle_dir, exist_ok=True)
            subtitle_file = os.path.join(subtitle_dir, f"{video_name}.srt")
        extracted = False
        if _ffmpeg_available():
            extracted = _extract_audio_ffmpeg(processing_video_file, audio_file)
        if not extracted:
            video = VideoFileClip(processing_video_file)
            if video.audio is None:
                return None
            audio_file = os.path.join(audio_dir, f"{video_name}_speech.wav")
            video.audio.write_audiofile(audio_file, codec="pcm_s16le", ffmpeg_params=["-ac", str(DEFAULT_AUDIO_CHANNELS), "-ar", str(DEFAULT_AUDIO_SAMPLE_RATE)], logger=None)
        result = create(
            audio_file,
            subtitle_file,
            backend_override=backend_override,
            model_override=model_override,
            video_file=processing_video_file,
            **kwargs,
        )
        if result and os.path.exists(result):
            return result
        return None
    except Exception:
        logger.error(f"从视频提取音频并生成字幕失败: {traceback.format_exc()}")
        return None
    finally:
        try:
            if video is not None:
                video.close()
        except Exception:
            pass
        try:
            if audio_file and os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception:
            pass


def create_from_video(video_file: str, subtitle_file: str = "", backend_override: str = "", model_override: str = "", **kwargs) -> Optional[str]:
    return extract_audio_and_create_subtitle(video_file, subtitle_file, backend_override=backend_override, model_override=model_override, **kwargs)
