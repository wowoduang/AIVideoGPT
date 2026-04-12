from __future__ import annotations

import json
import re
from typing import Dict, List

from loguru import logger

from app.services.llm_text_completion import call_text_chat_completion
from app.services.prompts import PromptManager
from app.services.timeline_allocator import apply_timeline_budget, estimate_char_budget, fit_check, trim_text_to_budget
from app.utils import utils

try:
    from app.services.llm.migration_adapter import generate_narration as legacy_generate_narration
except Exception:  # pragma: no cover
    legacy_generate_narration = None


STYLE_GUIDE = {
    "documentary": "客观、清楚、偏影视旁白口吻，避免夸张。",
    "short_drama": "更有悬念感和戏剧张力，但不能改事实。",
    "dramatic": "强调冲突和悬念推进，但不能说反人物关系或编造事实。",
    "general": "自然口语化，信息清晰，像真人解说。",
    "analysis": "偏剧情分析，强调人物关系与因果，不要空话。",
    "short_video": "节奏更紧，句子更短，要有钩子但不能编造。",
    "default": "自然口语化，信息清晰，避免空话。",
}

STYLE_EXAMPLES = {
    "documentary": [
        "镜头推进到这里，人物关系已经开始悄悄失衡，后面的冲突其实早就埋下了伏笔。",
        "表面上这只是一场普通对话，但真正推动剧情的，是角色态度在这一刻发生了变化。",
    ],
    "short_drama": [
        "谁都没想到，这句看似随口的话，反而把真正的矛盾彻底撕开了。",
        "镜头一转，局面马上变了，前面还在硬撑的人，这下终于藏不住了。",
    ],
    "dramatic": [
        "这一来一回看着平静，真正危险的信号，其实已经冒出来了。",
        "话刚说到这里，局势就开始拐弯了，后面的冲突也跟着被推了上来。",
    ],
    "general": [
        "这一段最关键的，不是台词本身，而是人物立场已经开始发生变化。",
        "表面上事情还没彻底爆发，但观众这时候已经能感觉到，后面的冲突躲不掉了。",
    ],
    "analysis": [
        "这一幕承担的叙事功能更像是信息揭露，它把前面隐约存在的矛盾正式摆到了台面上。",
        "如果把整段剧情放在一起看，这里其实是人物关系转向的第一处明确信号。",
    ],
    "short_video": [
        "别看这一段表面平静，真正的转折点，其实已经到了。",
        "一句话就把局势带偏了，后面会怎么炸开，观众这时候已经有预感了。",
    ],
}

STYLE_LABELS = {
    "documentary": "纪录片旁白型",
    "short_drama": "短剧悬念推进型",
    "dramatic": "冲突悬念型",
    "general": "通用概括解说型",
    "analysis": "概括点评分析型",
    "short_video": "短视频快节奏型",
    "default": "通用概括解说型",
}

_OPENING_PREFIX_BY_STYLE = {
    "documentary": "开场先把局势交代清楚，",
    "short_drama": "故事一开场，",
    "dramatic": "一上来，",
    "general": "故事一开场，",
    "analysis": "开场这段先把局势摆出来，",
    "short_video": "一上来，",
    "default": "故事一开场，",
}

_MOVIE_CATEGORY_KEYWORDS = {
    "历史宫廷": ("皇上", "皇帝", "娘娘", "太监", "圣旨", "朝堂", "王爷", "后宫", "陛下", "臣"),
    "战争权谋": ("守城", "攻城", "战场", "敌军", "军令", "将军", "士兵", "前线", "军营", "出征"),
    "悬疑罪案": ("凶手", "案件", "证据", "线索", "审讯", "警察", "嫌疑", "尸体", "追查", "破案"),
    "家庭伦理": ("婆婆", "老公", "老婆", "儿子", "女儿", "离婚", "结婚", "家庭", "爸", "妈"),
    "爱情情感": ("喜欢", "爱上", "表白", "分手", "初恋", "婚礼", "约会", "感情", "心动", "复合"),
    "都市职场": ("公司", "合同", "项目", "总裁", "同事", "开会", "老板", "办公室", "客户", "升职"),
    "江湖动作": ("杀手", "帮派", "打斗", "追杀", "刀", "枪", "江湖", "仇家", "埋伏", "逃亡"),
    "喜剧轻松": ("搞笑", "好笑", "笑", "乌龙", "误会", "整蛊", "荒唐", "逗", "闹剧", "乐呵"),
}

_ROLE_SUBJECTS = (
    "皇上", "皇帝", "太监", "皇后", "娘娘", "太后", "王爷", "王妃", "公主", "驸马",
    "将军", "大臣", "丞相", "大帅", "老爷", "夫人", "姑娘", "少爷", "掌柜", "伙计",
)
_ROLE_VERBS = ("说道", "说", "问道", "问", "回道", "回应", "命令", "吩咐", "质问", "提醒", "表示", "怒斥")
_ROLE_ATTR_RE = re.compile(
    rf"(?P<subject>{'|'.join(sorted((re.escape(x) for x in _ROLE_SUBJECTS), key=len, reverse=True))})"
    rf"(?P<verb>{'|'.join(sorted((re.escape(x) for x in _ROLE_VERBS), key=len, reverse=True))})"
)
_OPENING_MARKERS = ("开场", "故事一开场", "一上来", "片子一开始", "这段一开始", "先看这一段")

_RAW_VOICE_MAX_DURATION = 18.0
_RAW_VOICE_STRONG_MAX_DURATION = 28.0
_REWRITE_QUOTE_RE = re.compile(r'[“"「『](.+?)[”"」』]')
_REWRITE_PREFIXES = (
    "如果需要更保守，可以改成：",
    "如果需要更保守，可以修改为：",
    "如果想更保守，可以改成：",
    "如果想更保守，可以写成：",
    "更保守的写法是：",
    "更保守一点可以写成：",
    "建议改为：",
    "可以改为：",
    "可改为：",
    "改成：",
    "写成：",
)


def generate_narration(markdown_content: str, api_key: str, base_url: str, model: str) -> str:
    if legacy_generate_narration:
        return legacy_generate_narration(markdown_content, api_key, base_url, model)
    return ""


def _call_chat_completion(prompt: str, api_key: str, base_url: str, model: str) -> str:
    return call_text_chat_completion(
        prompt,
        api_key=api_key,
        model=model,
        base_url=base_url,
        system_prompt="你是一个严格、可靠的中文影视解说助手。",
        temperature=0.25,
        timeout=90,
        log_label="解说生成 LLM",
    )


def _extract_json_obj(raw: str):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            return None
    return None


def _compact_story_text(parts: List[str]) -> str:
    return " ".join(str(part or "").strip() for part in parts if str(part or "").strip())


def _infer_movie_category(video_title: str, global_summary: Dict, scene_evidence: List[Dict]) -> str:
    corpus = _compact_story_text(
        [
            video_title,
            global_summary.get("video_title"),
            global_summary.get("main_storyline"),
            global_summary.get("arc"),
            global_summary.get("protagonist"),
            " ".join(str(item.get("main_text_evidence") or item.get("subtitle_text") or "")[:80] for item in (scene_evidence or [])[:8]),
        ]
    )
    best_label = ""
    best_score = 0
    for label, keywords in _MOVIE_CATEGORY_KEYWORDS.items():
        score = sum(corpus.count(keyword) for keyword in keywords)
        if score > best_score:
            best_label = label
            best_score = score
    return best_label or "通用剧情"


def _speaker_attribution_confidence(pkg: Dict) -> str:
    speaker_names = [str(item or "").strip() for item in (pkg.get("speaker_names") or []) if str(item or "").strip()]
    speaker_turns = int(pkg.get("speaker_turns", 0) or 0)
    if len(speaker_names) == 1 and speaker_turns <= 1:
        return "single_explicit"
    if len(speaker_names) >= 2 or speaker_turns >= 2:
        return "multi_party"
    if len(speaker_names) == 1:
        return "single_uncertain"
    return "unknown"


def _build_project_context(
    *,
    video_title: str,
    style: str,
    movie_category: str,
    pkg: Dict,
    segment_index: int,
    segment_count: int,
) -> Dict:
    speaker_names = [str(item or "").strip() for item in (pkg.get("speaker_names") or []) if str(item or "").strip()]
    start = float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0)
    end = float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or start)
    return {
        "video_title": str(video_title or "").strip(),
        "movie_category_hint": movie_category,
        "narration_style": style,
        "narration_style_label": STYLE_LABELS.get(style, STYLE_LABELS["default"]),
        "segment_index": int(segment_index),
        "segment_count": int(segment_count),
        "is_opening_segment": bool(segment_index == 1),
        "opening_requirement": "如果这是第一段，必须先用一句话交代开场局势、人物或场面，不能整段零开场。",
        "segment_timestamp": str(pkg.get("timestamp") or ""),
        "segment_start_seconds": round(start, 3),
        "segment_end_seconds": round(end, 3),
        "segment_duration_seconds": round(max(end - start, 0.0), 3),
        "representative_frame_count": len(list(pkg.get("frame_paths") or [])),
        "representative_frames": [
            {
                "frame_path": item.get("frame_path") or item.get("frame"),
                "timestamp_seconds": item.get("timestamp_seconds"),
                "timestamp": item.get("timestamp"),
                "desc": item.get("desc"),
            }
            for item in list(pkg.get("representative_frames") or [])[:4]
        ],
        "visual_evidence_digest": [str(item.get("desc") or "")[:80] for item in list(pkg.get("visual_summary") or [])[:4]],
        "char_budget": int(pkg.get("char_budget", 0) or 0),
        "title_prior_usage_rule": "如果你熟悉这部影片，可以使用片名对应的既有剧情知识来辨认角色、场面和关系，但只能用于当前时间窗内的内容，不能提前剧透后续情节。",
        "speaker_names": speaker_names[:4],
        "speaker_turns": int(pkg.get("speaker_turns", 0) or 0),
        "exchange_pairs": list(pkg.get("exchange_pairs") or [])[:4],
        "speaker_attribution_confidence": _speaker_attribution_confidence(pkg),
        "speaker_attribution_rule": "只有说话人证据明确时，才写成“某人说/某人命令”；证据不够时用“有人/对方/现场/这番话”这种中性说法。",
    }


def _raw_voice_duration_limit(pkg: Dict) -> float:
    plot_function = str(pkg.get("plot_function") or "")
    importance = str(pkg.get("importance_level") or "")
    strong_raw_voice = (
        importance == "high"
        and plot_function in {"反转", "情感爆发", "结局收束"}
    )
    return _RAW_VOICE_STRONG_MAX_DURATION if strong_raw_voice else _RAW_VOICE_MAX_DURATION


def _can_keep_raw_voice(pkg: Dict) -> bool:
    start = float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0)
    end = float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or start)
    duration = max(end - start, 0.0)
    return duration <= _raw_voice_duration_limit(pkg)


def _clean_review_rewrite_hint(text: str) -> str:
    hint = str(text or "").strip()
    if not hint:
        return ""

    quoted = _REWRITE_QUOTE_RE.search(hint)
    if quoted:
        hint = quoted.group(1).strip()

    for prefix in _REWRITE_PREFIXES:
        if hint.startswith(prefix):
            hint = hint[len(prefix):].strip()
            break

    hint = hint.strip("“”\"'：:，,；; ")
    return hint


def _resolve_review_narration_text(original: str, validation: Dict, char_budget: int) -> str:
    cleaned_hint = _clean_review_rewrite_hint(str(validation.get("safe_rewrite_hint") or ""))
    if cleaned_hint and all(token not in cleaned_hint[:10] for token in ("如果", "建议", "改为", "写成", "保守")):
        return trim_text_to_budget(cleaned_hint, char_budget)
    return trim_text_to_budget(str(original or "").strip(), max(12, int(char_budget * 0.92)))


def _soften_uncertain_speaker_attribution(text: str, pkg: Dict) -> str:
    narration = str(text or "").strip()
    if not narration:
        return ""
    if _speaker_attribution_confidence(pkg) == "single_explicit":
        return narration

    explicit_names = {
        str(item or "").strip()
        for item in (pkg.get("speaker_names") or [])
        if str(item or "").strip()
    }

    def _replace(match: re.Match) -> str:
        subject = str(match.group("subject") or "").strip()
        verb = str(match.group("verb") or "").strip()
        if subject in explicit_names:
            return match.group(0)
        return f"有人{verb}"

    return _ROLE_ATTR_RE.sub(_replace, narration)


def _ensure_opening_narration(text: str, pkg: Dict, char_budget: int, style: str) -> str:
    narration = str(text or "").strip()
    if not narration:
        return ""
    if not bool(pkg.get("is_opening_segment")):
        return trim_text_to_budget(narration, char_budget)
    if narration.startswith(_OPENING_MARKERS):
        return trim_text_to_budget(narration, char_budget)

    prefix = _OPENING_PREFIX_BY_STYLE.get(style, _OPENING_PREFIX_BY_STYLE["default"])
    return trim_text_to_budget(f"{prefix}{narration}", char_budget)


def _postprocess_candidate_narration(text: str, pkg: Dict, char_budget: int, style: str) -> str:
    narration = _soften_uncertain_speaker_attribution(text, pkg)
    narration = _ensure_opening_narration(narration, pkg, char_budget, style)
    return trim_text_to_budget(narration, char_budget)


def _validate_generated_narration(
    pkg: Dict,
    narration: str,
    raw_voice_keep: bool,
    project_context: Dict,
    api_key: str,
    base_url: str,
    model: str,
) -> Dict:
    fallback = {
        "status": "pass",
        "issues": [],
        "safe_rewrite_hint": "",
        "raw_voice_keep": raw_voice_keep,
    }
    if not (api_key and model and narration.strip()):
        return fallback

    prompt = PromptManager.get_prompt(
        "movie_story_narration",
        "narration_validation",
        parameters={
            "segment_json": json.dumps(
                {
                    "segment_id": pkg.get("segment_id"),
                    "highlight_id": pkg.get("highlight_id"),
                    "timestamp": pkg.get("timestamp"),
                    "start": round(float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0), 3),
                    "end": round(float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or 0.0), 3),
                    "plot_function": pkg.get("plot_function"),
                    "importance_level": pkg.get("importance_level"),
                    "surface_dialogue_meaning": pkg.get("surface_dialogue_meaning"),
                    "real_narrative_state": pkg.get("real_narrative_state"),
                    "story_validation": pkg.get("story_validation"),
                    "local_understanding": pkg.get("local_understanding"),
                    "main_text_evidence": pkg.get("main_text_evidence") or pkg.get("subtitle_text"),
                    "visual_summary": list(pkg.get("visual_summary") or [])[:4],
                    "frame_paths": list(pkg.get("frame_paths") or [])[:6],
                    "representative_frames": list(pkg.get("representative_frames") or [])[:4],
                    "speaker_names": list(pkg.get("speaker_names") or []),
                    "speaker_turns": int(pkg.get("speaker_turns", 0) or 0),
                    "exchange_pairs": list(pkg.get("exchange_pairs") or []),
                    "speaker_attribution_confidence": _speaker_attribution_confidence(pkg),
                    "is_opening_segment": bool(pkg.get("is_opening_segment")),
                },
                ensure_ascii=False,
                indent=2,
            ),
            "project_context_json": json.dumps(project_context or {}, ensure_ascii=False, indent=2),
            "generated_narration": narration.strip(),
        },
    )
    raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
    parsed = _extract_json_obj(raw)
    if isinstance(parsed, dict):
        result = dict(fallback)
        result.update({k: v for k, v in parsed.items() if v not in (None, "", [], {})})
        result["raw_voice_keep"] = bool(parsed.get("raw_voice_keep", raw_voice_keep))
        return result
    return fallback


def _fallback_narration(pkg: Dict, style: str, char_budget: int) -> Dict:
    real_state = (pkg.get("real_narrative_state") or "").strip()
    surface = (pkg.get("surface_dialogue_meaning") or "").strip()
    core = real_state or surface or (pkg.get("main_text_evidence") or pkg.get("subtitle_text") or "").strip()
    core = trim_text_to_budget(core or "这一段剧情继续推进。", char_budget)

    if style in {"short_drama", "dramatic"}:
        if pkg.get("plot_function") in {"反转", "情感爆发"}:
            narration = f"关键时刻到了，{core}"
        else:
            narration = f"镜头一转，{core}"
    elif style == "analysis":
        narration = f"这一段更重要的是，{core}"
    else:
        narration = core

    risk_flags = pkg.get("narrative_risk_flags") or []
    if risk_flags:
        narration = narration.replace("一定", "像是").replace("就是", "似乎是")
    narration = _postprocess_candidate_narration(narration, pkg, char_budget, style)

    raw_voice_keep = bool(pkg.get("llm_raw_voice_keep"))
    if isinstance(pkg.get("story_validation"), dict):
        raw_voice_keep = bool(pkg["story_validation"].get("raw_voice_keep", raw_voice_keep))
    if not raw_voice_keep:
        raw_voice_keep = bool(
            pkg.get("raw_voice_retain_suggestion")
            and str(pkg.get("importance_level") or "") == "high"
            and str(pkg.get("plot_function") or "") in {"反转", "情感爆发", "结局收束"}
        )
    raw_voice_keep = bool(raw_voice_keep and _can_keep_raw_voice(pkg))

    return {
        "narration": trim_text_to_budget(narration, char_budget),
        "raw_voice_keep": raw_voice_keep,
        "tone": pkg.get("emotion_hint") or "平静",
        "opening_type": "过渡",
        "risk_note": "；".join(risk_flags[:2]) if risk_flags else "",
    }


def _pick_ost(pkg: Dict, generation_result: Dict) -> int:
    plot_function = str(pkg.get("plot_function") or "")
    importance = str(pkg.get("importance_level") or "")

    if bool(pkg.get("is_opening_segment")):
        return 2

    if not _can_keep_raw_voice(pkg):
        return 2

    if bool(generation_result.get("raw_voice_keep")):
        return 1
    if bool(pkg.get("llm_raw_voice_keep")):
        return 1
    strategy = pkg.get("audio_strategy") or "duck"
    if strategy == "keep" and importance == "high" and plot_function in {"反转", "情感爆发", "结局收束"}:
        return 1
    if pkg.get("block_type") == "visual" and pkg.get("importance_level") == "high" and pkg.get("llm_highlight_selected"):
        return 1
    return 2


def _normalize_generated_narration(narration: str, pkg: Dict, char_budget: int, style: str) -> str:
    text = _postprocess_candidate_narration((narration or "").strip(), pkg, char_budget, style)
    plot_function = str(pkg.get("plot_function") or "")
    importance = str(pkg.get("importance_level") or "medium")
    validator_status = str((pkg.get("story_validation") or {}).get("validator_status") or "pass")

    effective_budget = int(char_budget)
    if plot_function in {"铺垫", "节奏缓冲"}:
        effective_budget = max(12, int(char_budget * 0.72))
    elif importance == "low":
        effective_budget = max(12, int(char_budget * 0.8))

    if validator_status == "review":
        effective_budget = max(12, min(effective_budget, char_budget - 4))

    return trim_text_to_budget(text, effective_budget)


def _should_merge_context_items(left: Dict, right: Dict) -> bool:
    left_end = float(left.get("end", 0.0) or 0.0)
    right_start = float(right.get("start", left_end) or left_end)
    gap = right_start - left_end
    if gap > 0.8:
        return False

    left_importance = str(left.get("importance_level") or "medium")
    right_importance = str(right.get("importance_level") or "medium")
    left_plot = str(left.get("plot_function") or "")
    right_plot = str(right.get("plot_function") or "")
    left_duration = float(left.get("duration", 0.0) or 0.0)
    right_duration = float(right.get("duration", 0.0) or 0.0)
    same_ost = int(left.get("OST", 2) or 2) == int(right.get("OST", 2) or 2)

    weak_left = left_importance == "low" or left_plot in {"铺垫", "节奏缓冲"}
    weak_right = right_importance == "low" or right_plot in {"铺垫", "节奏缓冲"}
    short_pair = left_duration <= 10.0 and right_duration <= 10.0
    return weak_left and weak_right and short_pair and same_ost


def _merge_script_items(left: Dict, right: Dict) -> Dict:
    merged = dict(left)
    merged_end = round(float(right.get("end", merged.get("end", 0.0)) or merged.get("end", 0.0)), 3)
    merged["end"] = merged_end
    merged["duration"] = round(max(merged_end - float(merged.get("start", 0.0) or 0.0), 0.1), 3)
    merged["timestamp"] = f"{utils.format_time(float(merged.get('start', 0.0) or 0.0))}-{utils.format_time(merged_end)}"
    merged["source_timestamp"] = merged["timestamp"]
    merged["picture"] = (str(merged.get("picture") or "") + "；" + str(right.get("picture") or "")).strip("；")[:80]
    merged["narration"] = trim_text_to_budget(
        f"{str(merged.get('narration') or '').strip()}，{str(right.get('narration') or '').strip()}".strip("，"),
        max(int(merged.get("char_budget") or 0) + int(right.get("char_budget") or 0), 20),
    )
    merged["evidence_refs"] = list(dict.fromkeys(list(merged.get("evidence_refs") or []) + list(right.get("evidence_refs") or [])))
    merged["segment_id"] = f"{merged.get('segment_id')}+{right.get('segment_id')}"
    merged["scene_id"] = merged["segment_id"]
    if str(right.get("importance_level") or "") == "high":
        merged["plot_function"] = right.get("plot_function")
        merged["importance_level"] = right.get("importance_level")
    elif "medium" in {str(merged.get("importance_level") or ""), str(right.get("importance_level") or "")}:
        merged["importance_level"] = "medium"
    if "review" in {str(merged.get("validator_status") or ""), str(right.get("validator_status") or "")}:
        merged["validator_status"] = "review"
    merged["before_prologue_end"] = bool(merged.get("before_prologue_end") or right.get("before_prologue_end"))
    merged["crosses_prologue_boundary"] = bool(
        merged.get("crosses_prologue_boundary") or right.get("crosses_prologue_boundary")
    )
    merged["prologue_trimmed"] = bool(merged.get("prologue_trimmed") or right.get("prologue_trimmed"))
    merged["prologue_original_before_prologue_end"] = bool(
        merged.get("prologue_original_before_prologue_end") or right.get("prologue_original_before_prologue_end")
    )
    merged["prologue_end"] = merged.get("prologue_end") if merged.get("prologue_end") is not None else right.get("prologue_end")
    return merged


def _trim_script_overlaps(items: List[Dict]) -> List[Dict]:
    if not items:
        return []

    trimmed: List[Dict] = []
    previous_end = None
    for item in items:
        cur = dict(item)
        start = float(cur.get("start", 0.0) or 0.0)
        end = float(cur.get("end", start) or start)

        if previous_end is not None and start < previous_end:
            start = round(previous_end, 3)
            cur["start"] = start

        if end <= start:
            continue

        cur["end"] = round(end, 3)
        cur["duration"] = round(max(cur["end"] - cur["start"], 0.1), 3)
        canonical_timestamp = f"{utils.format_time(cur['start'])}-{utils.format_time(cur['end'])}"
        cur["timestamp"] = canonical_timestamp
        cur["source_timestamp"] = canonical_timestamp
        trimmed.append(cur)
        previous_end = cur["end"]

    for idx, item in enumerate(trimmed, start=1):
        item["_id"] = idx
    return trimmed


def _postprocess_script_items(items: List[Dict]) -> List[Dict]:
    if not items:
        return []

    ordered = sorted((dict(item) for item in items), key=lambda x: (float(x.get("start", 0.0) or 0.0), int(x.get("_id", 0) or 0)))
    merged: List[Dict] = []
    for item in ordered:
        if merged and _should_merge_context_items(merged[-1], item):
            merged[-1] = _merge_script_items(merged[-1], item)
        else:
            merged.append(item)

    for idx, item in enumerate(merged, start=1):
        item["_id"] = idx

    merged = _trim_script_overlaps(merged)
    return apply_timeline_budget(merged, auto_trim=True)


def _build_script_item(
    idx: int,
    pkg: Dict,
    generation_result: Dict,
    picture: str,
    global_summary: Dict,
    style: str,
) -> Dict:
    narration = generation_result.get("narration") or ""
    start = float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0)
    end = float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or 0.0)
    if end <= start:
        end = start + 1.0
    duration = end - start
    planned_budget = int(pkg.get("planned_char_budget") or 0)
    base_budget = estimate_char_budget(duration)
    char_budget = max(planned_budget, min(base_budget + 12, int(base_budget * 1.25))) if planned_budget else base_budget
    canonical_timestamp = f"{utils.format_time(start)}-{utils.format_time(end)}"
    item = {
        "_id": idx,
        "timestamp": canonical_timestamp,
        "source_timestamp": pkg.get("timestamp") or canonical_timestamp,
        "picture": (picture or "").strip()[:80] or "画面推进",
        "narration": _normalize_generated_narration((narration or "").strip(), pkg, char_budget, style),
        "OST": _pick_ost(pkg, generation_result),
        "evidence_refs": list(pkg.get("subtitle_ids") or []) + [pkg.get("segment_id")],
        "char_budget": char_budget,
        "emotion": pkg.get("emotion_hint") or "平静",
        "segment_id": pkg.get("segment_id"),
        "scene_id": pkg.get("scene_id"),
        "start": round(start, 3),
        "end": round(end, 3),
        "duration": round(duration, 3),
        "plot_role": pkg.get("plot_role"),
        "plot_function": pkg.get("plot_function"),
        "attraction_level": pkg.get("attraction_level"),
        "importance_level": pkg.get("importance_level"),
        "narration_level": pkg.get("narration_level"),
        "confidence": pkg.get("confidence"),
        "global_arc": global_summary.get("arc"),
        "risk_note": generation_result.get("risk_note", ""),
        "validator_status": (pkg.get("story_validation") or {}).get("validator_status"),
        "llm_highlight_selected": bool(pkg.get("llm_highlight_selected")),
        "llm_raw_voice_keep": bool(pkg.get("llm_raw_voice_keep")),
        "before_prologue_end": bool(pkg.get("before_prologue_end")),
        "crosses_prologue_boundary": bool(pkg.get("crosses_prologue_boundary")),
        "prologue_trimmed": bool(pkg.get("prologue_trimmed")),
        "prologue_original_before_prologue_end": bool(pkg.get("prologue_original_before_prologue_end")),
        "prologue_end": pkg.get("prologue_end"),
        "semantic_timestamp": pkg.get("semantic_timestamp") or pkg.get("timestamp") or canonical_timestamp,
        "highlight_id": pkg.get("highlight_id"),
        "highlight_rank": pkg.get("highlight_rank"),
        "highlight_reasons": list(pkg.get("highlight_reasons") or []),
        "frame_paths": list(pkg.get("frame_paths") or []),
        "visual_summary": list(pkg.get("visual_summary") or []),
        "representative_frames": list(pkg.get("representative_frames") or []),
        "source_segment_ids": list(pkg.get("source_segment_ids") or []),
        "source_scene_ids": list(pkg.get("source_scene_ids") or []),
        "source_evidence_ids": list(pkg.get("source_evidence_ids") or []),
        "main_text_evidence": pkg.get("main_text_evidence") or pkg.get("subtitle_text") or "",
        "narration_validation": generation_result.get("narration_validation") or {},
    }
    item["fit_check"] = fit_check(item["narration"], duration)
    return item


def generate_narration_from_scene_evidence(
    scene_evidence: List[Dict],
    api_key: str,
    base_url: str,
    model: str,
    style: str = "documentary",
    video_title: str = "",
) -> List[Dict]:
    if not scene_evidence:
        return []

    global_summary = {}
    if scene_evidence and isinstance(scene_evidence[0].get("_global_summary"), dict):
        global_summary = scene_evidence[0]["_global_summary"]

    normalized_style = style if style in STYLE_GUIDE else "default"
    style_guide = STYLE_GUIDE.get(normalized_style, STYLE_GUIDE["default"])
    style_examples = "\n".join(f"- {x}" for x in STYLE_EXAMPLES.get(normalized_style, STYLE_EXAMPLES["general"]))
    effective_video_title = str(video_title or global_summary.get("video_title") or "").strip()
    movie_category = _infer_movie_category(effective_video_title, global_summary or {}, scene_evidence)

    script_items: List[Dict] = []
    segment_count = len(scene_evidence)
    for idx, pkg in enumerate(scene_evidence, start=1):
        pkg["is_opening_segment"] = bool(idx == 1)
        pkg["narration_style"] = normalized_style
        start = float(pkg.get("start", pkg.get("time_window", [0.0, 0.0])[0]) or 0.0)
        end = float(pkg.get("end", pkg.get("time_window", [0.0, 0.0])[1]) or 0.0)
        duration = max(end - start, 0.1)
        char_budget = int(pkg.get("planned_char_budget") or estimate_char_budget(duration))
        pkg["char_budget"] = char_budget
        project_context = _build_project_context(
            video_title=effective_video_title,
            style=normalized_style,
            movie_category=movie_category,
            pkg=pkg,
            segment_index=idx,
            segment_count=segment_count,
        )

        generation_result = {}
        if api_key and model:
            prompt = PromptManager.get_prompt(
                "movie_story_narration",
                "narration_generation",
                parameters={
                    "segment_json": json.dumps(
                        {
                            "segment_id": pkg.get("segment_id"),
                            "highlight_id": pkg.get("highlight_id"),
                            "timestamp": pkg.get("timestamp"),
                            "start": round(start, 3),
                            "end": round(end, 3),
                            "plot_function": pkg.get("plot_function"),
                            "importance_level": pkg.get("importance_level"),
                            "surface_dialogue_meaning": pkg.get("surface_dialogue_meaning"),
                            "real_narrative_state": pkg.get("real_narrative_state"),
                            "local_understanding": pkg.get("local_understanding"),
                            "story_validation": pkg.get("story_validation"),
                            "raw_voice_retain_suggestion": pkg.get("raw_voice_retain_suggestion"),
                            "emotion_hint": pkg.get("emotion_hint"),
                            "main_text_evidence": pkg.get("main_text_evidence") or pkg.get("subtitle_text"),
                            "visual_summary": list(pkg.get("visual_summary") or [])[:4],
                            "frame_paths": list(pkg.get("frame_paths") or [])[:6],
                            "representative_frames": list(pkg.get("representative_frames") or [])[:4],
                            "speaker_names": list(pkg.get("speaker_names") or []),
                            "speaker_turns": int(pkg.get("speaker_turns", 0) or 0),
                            "exchange_pairs": list(pkg.get("exchange_pairs") or []),
                            "speaker_attribution_confidence": _speaker_attribution_confidence(pkg),
                            "is_opening_segment": bool(pkg.get("is_opening_segment")),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    "global_summary_json": json.dumps(global_summary or {}, ensure_ascii=False, indent=2),
                    "project_context_json": json.dumps(project_context or {}, ensure_ascii=False, indent=2),
                    "style_guide": style_guide,
                    "style_examples": style_examples,
                    "char_budget": char_budget,
                },
            )
            raw = _call_chat_completion(prompt, api_key=api_key, base_url=base_url, model=model)
            parsed = _extract_json_obj(raw)
            if isinstance(parsed, dict):
                generation_result = parsed
                generation_result["narration"] = _postprocess_candidate_narration(
                    generation_result.get("narration", ""),
                    pkg,
                    char_budget,
                    normalized_style,
                )

        if not generation_result:
            generation_result = _fallback_narration(pkg, normalized_style, char_budget)
        else:
            validation = _validate_generated_narration(
                pkg,
                generation_result.get("narration", ""),
                bool(generation_result.get("raw_voice_keep")),
                project_context,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            generation_result["narration_validation"] = validation
            if validation.get("status") == "reject":
                generation_result = _fallback_narration(pkg, normalized_style, char_budget)
                generation_result["risk_note"] = (
                    f"{generation_result.get('risk_note', '')}；"
                    f"narration_rejected:{';'.join(validation.get('issues') or [])}"
                ).strip("；")
            elif validation.get("status") == "review":
                generation_result["narration"] = _resolve_review_narration_text(
                    generation_result.get("narration", ""),
                    validation,
                    char_budget,
                )
                generation_result["narration"] = _postprocess_candidate_narration(
                    generation_result.get("narration", ""),
                    pkg,
                    char_budget,
                    normalized_style,
                )
                generation_result["raw_voice_keep"] = bool(
                    generation_result.get("raw_voice_keep") and _can_keep_raw_voice(pkg)
                )
                generation_result["risk_note"] = (
                    f"{generation_result.get('risk_note', '')}；"
                    f"narration_review:{';'.join(validation.get('issues') or [])}"
                ).strip("；")

        picture = pkg.get("picture") or "；".join(x.get("desc", "") for x in (pkg.get("visual_summary") or [])[:2])
        script_items.append(
            _build_script_item(idx, pkg, generation_result, picture, global_summary or {}, normalized_style)
        )

    return _postprocess_script_items(script_items)
