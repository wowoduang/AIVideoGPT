import os
from typing import Dict, List

from loguru import logger


class PreflightError(ValueError):
    """Raised when a preflight validation check fails."""
    pass


REQUIRED_SCRIPT_KEYS = ["_id", "timestamp", "picture", "narration", "OST"]


# ---------------------------------------------------------------------------
# Script structure validation
# ---------------------------------------------------------------------------

def validate_script_items(script_list: List[Dict]) -> None:
    """Validate that every script item has the required fields."""
    if not script_list:
        raise PreflightError("脚本数组不能为空")
    for idx, item in enumerate(script_list, start=1):
        for key in REQUIRED_SCRIPT_KEYS:
            if key not in item:
                raise PreflightError(f"第 {idx} 个片段缺少字段: {key}")
        if not str(item.get("narration", "")).strip():
            raise PreflightError(f"第 {idx} 个片段 narration 为空")


# ---------------------------------------------------------------------------
# TTS result validation
# ---------------------------------------------------------------------------

def validate_tts_results(script_list: List[Dict], tts_results: List[Dict]) -> None:
    """Validate that TTS results cover all required script items."""
    required_ids = {item["_id"] for item in script_list if item.get("OST") in [0, 2]}
    result_ids = {item.get("_id") for item in (tts_results or []) if item.get("audio_file")}
    missing = sorted([rid for rid in required_ids if rid not in result_ids])
    if missing:
        raise PreflightError(
            "缺少 TTS 结果，无法继续统一裁剪。"
            f" 缺失片段ID: {missing}. 请检查语音合成是否成功，或将相关片段改为不依赖TTS的 OST 模式。"
        )


# ---------------------------------------------------------------------------
# OST=2 narration non-empty validation (PRD M11)
# ---------------------------------------------------------------------------

def validate_ost2_narrations(script_list: List[Dict]) -> None:
    """Ensure every item with OST=2 has a non-empty narration.

    OST=2 means the narration replaces original audio, so the text
    must not be empty.
    """
    empty_ids = []
    for item in script_list or []:
        if item.get("OST") == 2:
            narration = str(item.get("narration", "")).strip()
            if not narration:
                empty_ids.append(item.get("_id", "?"))
    if empty_ids:
        raise PreflightError(
            f"OST=2 的片段必须有解说文案，以下片段 narration 为空: {empty_ids}"
        )


# ---------------------------------------------------------------------------
# TTS provider configuration check (PRD M11)
# ---------------------------------------------------------------------------

def validate_tts_provider(provider: str = "", api_key: str = "") -> None:
    """Validate that TTS provider is properly configured.

    Parameters
    ----------
    provider : str
        TTS provider name (e.g. "edge-tts", "azure", "openai").
    api_key : str
        API key for cloud TTS providers (not needed for edge-tts).
    """
    if not provider:
        raise PreflightError("未配置 TTS 服务提供商，请在设置中配置 TTS 服务")

    # edge-tts is local and doesn't need an API key
    if provider.lower() in ("edge-tts", "edge_tts", "edgetts"):
        return

    # Cloud providers need an API key
    if not api_key:
        raise PreflightError(
            f"TTS 服务 '{provider}' 需要 API 密钥，请在设置中配置"
        )


# ---------------------------------------------------------------------------
# Network availability check (PRD M11)
# ---------------------------------------------------------------------------

def validate_network(timeout: float = 5.0) -> None:
    """Quick check that the network is reachable.

    Tries to connect to a well-known endpoint.  Raises PreflightError
    if the network is unreachable.
    """
    import urllib.request
    import urllib.error

    test_urls = [
        "https://www.baidu.com",
        "https://www.google.com",
    ]
    for url in test_urls:
        try:
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=timeout)
            return  # At least one URL is reachable
        except (urllib.error.URLError, OSError):
            continue

    raise PreflightError(
        "网络不可用，无法访问外部服务。请检查网络连接。"
    )


# ---------------------------------------------------------------------------
# Reuse-mode file completeness check (PRD M11)
# ---------------------------------------------------------------------------

def validate_reuse_files(
    script_path: str = "",
    audio_dir: str = "",
    subclip_dir: str = "",
) -> None:
    """Validate that required files exist when reuse mode is active.

    Parameters
    ----------
    script_path : str
        Path to the previously generated script JSON.
    audio_dir : str
        Directory containing previously generated TTS audio files.
    subclip_dir : str
        Directory containing previously clipped video segments.
    """
    issues: List[str] = []

    if script_path and not os.path.isfile(script_path):
        issues.append(f"脚本文件不存在: {script_path}")

    if audio_dir and not os.path.isdir(audio_dir):
        issues.append(f"音频目录不存在: {audio_dir}")

    if subclip_dir and not os.path.isdir(subclip_dir):
        issues.append(f"视频片段目录不存在: {subclip_dir}")

    if issues:
        raise PreflightError(
            "复用模式文件检查失败:\n" + "\n".join(issues)
        )


# ---------------------------------------------------------------------------
# Comprehensive preflight (convenience wrapper)
# ---------------------------------------------------------------------------

def run_full_preflight(
    script_list: List[Dict],
    tts_provider: str = "edge-tts",
    tts_api_key: str = "",
    check_network: bool = True,
    reuse_script_path: str = "",
    reuse_audio_dir: str = "",
    reuse_subclip_dir: str = "",
) -> List[str]:
    """Run all preflight checks and collect warnings.

    Returns a list of warning messages (non-fatal).  Raises
    ``PreflightError`` for fatal issues.
    """
    warnings: List[str] = []

    # 1. Script structure
    validate_script_items(script_list)

    # 2. OST=2 narration check
    try:
        validate_ost2_narrations(script_list)
    except PreflightError as e:
        warnings.append(str(e))

    # 3. TTS provider
    validate_tts_provider(tts_provider, tts_api_key)

    # 4. Network (optional, non-fatal)
    if check_network:
        try:
            validate_network()
        except PreflightError as e:
            warnings.append(str(e))

    # 5. Reuse files (only if paths are provided)
    if reuse_script_path or reuse_audio_dir or reuse_subclip_dir:
        validate_reuse_files(reuse_script_path, reuse_audio_dir, reuse_subclip_dir)

    if warnings:
        logger.warning(f"M11 预检警告 ({len(warnings)} 条): {warnings}")
    else:
        logger.info("M11 预检全部通过")

    return warnings
