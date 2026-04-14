from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from langchain.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import knowledge_base
from src.agents import agent_manager
from src.repositories.conversation_repository import ConversationRepository
from src.services.chat_stream_service import (
    _build_effective_agent_config,
    _resolve_agent_config,
    save_messages_from_langgraph_state,
)
from src.services.interview_coding_service import get_coding_session_from_metadata, list_imported_problem_packages
from src.storage.postgres.models_business import User
from src.utils.datetime_utils import format_utc_datetime
from src.utils.logging_config import logger

INTERVIEW_RESULT_METADATA_KEY = "interview_result"
INTERVIEW_AGENT_ID = "InterviewAgent"
INTERVIEW_SCORECARD_PATTERN = re.compile(
    r"```interview_scorecard\s*(\{[\s\S]*?\})\s*```",
    re.IGNORECASE,
)
PENDING_JUDGE_STATUSES = {"PENDING", "JUDGING"}
DIMENSION_LABELS = {
    "technical_competence": "技术能力",
    "problem_solving": "问题解决",
    "problem_solving_innovation": "问题解决",
    "communication": "沟通表达",
    "communication_clarity": "沟通表达",
    "soft_skills": "综合素质",
    "soft_skills_team_fit": "综合素质",
}
REVERSE_DIMENSION_LABELS = {
    "技术能力": "technical_competence",
    "实战经验": "technical_competence",
    "问题解决": "problem_solving",
    "沟通表达": "communication",
    "沟通与表达": "communication",
    "综合素质": "soft_skills",
    "编码能力": "technical_competence",
    "代码能力": "problem_solving",
    "项目经验与技术深度": "technical_competence",
    "基础知识": "technical_competence",
    "岗位匹配度": "soft_skills",
}
DIMENSION_KEYWORD_MAPPING = (
    (("项目经验", "技术深度"), "technical_competence"),
    (("基础知识",), "technical_competence"),
    (("代码能力", "编程能力", "工程实现"), "problem_solving"),
    (("问题解决",), "problem_solving"),
    (("沟通表达", "沟通与表达", "表达能力"), "communication"),
    (("综合素质", "岗位匹配度", "岗位匹配", "团队协作"), "soft_skills"),
)
FILLER_TERMS = ("嗯", "呃", "额", "啊", "就是", "然后", "那个", "其实")
HEDGE_TERMS = ("可能", "也许", "大概", "应该", "不太确定", "我猜", "我觉得", "或许")
ASSERTIVE_TERMS = ("我会", "我能", "我负责", "我主导", "最终", "落地", "推进", "优化")
SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？；]+")
PAUSE_PUNCTUATION = "，、。；！？"
DIMENSION_DISPLAY_CONFIG = {
    "technical_competence": {
        "label": "技术能力",
        "weakness_title": "技术基础还需要补强",
        "practice_title": "梳理关键知识点",
        "practice_action": "knowledge_review",
        "resource_type": "knowledge",
        "focus_title": "技术细节表达",
    },
    "problem_solving": {
        "label": "问题解决",
        "weakness_title": "题目拆解与实现稳定性偏弱",
        "practice_title": "完成定向算法练习",
        "practice_action": "coding_practice",
        "resource_type": "interview_question",
        "focus_title": "解题思路完整度",
    },
    "communication": {
        "label": "沟通表达",
        "weakness_title": "表达清晰度与说服力需提升",
        "practice_title": "做一次结构化表达练习",
        "practice_action": "communication_practice",
        "resource_type": "communication",
        "focus_title": "表达结构与自信度",
    },
    "soft_skills": {
        "label": "综合素质",
        "weakness_title": "岗位匹配表达不够充分",
        "practice_title": "复盘项目经历亮点",
        "practice_action": "experience_review",
        "resource_type": "knowledge",
        "focus_title": "项目复盘与岗位匹配",
    },
}
LOW_SCORE_THRESHOLD = 75
WEAKNESS_LIMIT = 3
RESOURCE_LIMIT = 5
PRACTICE_LIMIT = 3
HISTORY_PROFILE_WINDOW = 5


async def _get_accessible_databases_for_learning(user_id: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return {"databases": []}

    if normalized_user_id.isdigit():
        return await knowledge_base.get_databases_by_raw_id(int(normalized_user_id))
    return await knowledge_base.get_databases_by_user_id(normalized_user_id)


def _summarize_learning_excerpt(content: str, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if not text:
        return "建议回看该知识点对应文档片段。"
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _normalize_score_value(value: Any) -> int | None:
    try:
        score = round(float(value))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, int(score)))


def _parse_numeric_score(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _detect_score_scale(value: Any) -> float | None:
    raw_scores: list[float] = []

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            score = _parse_numeric_score(item.get("score"))
            if score is not None:
                raw_scores.append(score)
    elif isinstance(value, dict):
        for raw_score in value.values():
            score = _parse_numeric_score(raw_score)
            if score is not None:
                raw_scores.append(score)

    if not raw_scores:
        return None

    max_score = max(raw_scores)
    if max_score <= 5:
        return 5
    if max_score <= 10:
        return 10
    return None


def _normalize_interview_score(value: Any, *, scale_hint: float | None = None) -> int | None:
    raw_score = _parse_numeric_score(value)
    if raw_score is None:
        return None

    if scale_hint is not None:
        if scale_hint <= 5:
            raw_score *= 20
        elif scale_hint <= 10:
            raw_score *= 10
    else:
        if raw_score <= 5:
            raw_score *= 20
        elif raw_score <= 10:
            raw_score *= 10

    return _normalize_score_value(raw_score)


def _clamp_score(value: float, *, lower: int = 0, upper: int = 100) -> int:
    return max(lower, min(upper, round(value)))


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (str(entry or "").strip() for entry in value) if item]


def _normalize_dimensions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        scale_hint = _detect_score_scale(value)
        result: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            score = _normalize_interview_score(item.get("score"), scale_hint=scale_hint)
            if name and score is not None:
                result.append({"name": name, "score": score})
        return result

    if isinstance(value, dict):
        scale_hint = _detect_score_scale(value)
        result = []
        for name, score in value.items():
            normalized_score = _normalize_interview_score(score, scale_hint=scale_hint)
            normalized_name = str(name or "").strip()
            if normalized_name and normalized_score is not None:
                result.append({"name": normalized_name, "score": normalized_score})
        return result

    return []


def _normalize_expression_metric(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    score = _normalize_score_value(value.get("score"))
    level = str(value.get("level") or "").strip()
    detail = str(value.get("detail") or "").strip()
    metric_value = str(value.get("value") or "").strip()
    if score is None and not level and not detail and not metric_value:
        return None

    return {
        "score": score,
        "level": level,
        "detail": detail,
        "value": metric_value,
    }


def _normalize_expression_analysis(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    normalized = {
        "input_mode": str(value.get("input_mode") or "").strip(),
        "summary": str(value.get("summary") or "").strip(),
        "speech_rate": _normalize_expression_metric(value.get("speech_rate")),
        "pause_control": _normalize_expression_metric(value.get("pause_control")),
        "clarity": _normalize_expression_metric(value.get("clarity")),
        "confidence": _normalize_expression_metric(value.get("confidence")),
    }

    if not any(normalized.get(key) for key in ("speech_rate", "pause_control", "clarity", "confidence")):
        return None

    return normalized


def _normalize_improvement_plan(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    def normalize_weaknesses(items: Any) -> list[dict[str, str]]:
        if not isinstance(items, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            dimension_key = _normalize_dimension_key(item.get("dimension_key"))
            if dimension_key not in DIMENSION_DISPLAY_CONFIG:
                continue
            title = str(item.get("title") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not title or not reason:
                continue
            normalized.append(
                {
                    "dimension_key": dimension_key,
                    "title": title,
                    "reason": reason,
                }
            )
        return normalized

    def normalize_resources(items: Any) -> list[dict[str, str]]:
        if not isinstance(items, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            resource_type = str(item.get("resource_type") or "").strip()
            if resource_type not in {"knowledge", "interview_question", "communication"}:
                continue
            title = str(item.get("title") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if not title or not summary:
                continue
            resource = {
                "resource_type": resource_type,
                "title": title,
                "summary": summary,
                "source_type": str(item.get("source_type") or "internal").strip() or "internal",
                "source_id": str(item.get("source_id") or "").strip(),
                "source_ref": str(item.get("source_ref") or "").strip(),
            }
            locator = item.get("locator")
            if isinstance(locator, dict):
                db_id = str(locator.get("db_id") or "").strip()
                file_id = str(locator.get("file_id") or "").strip()
                chunk_id = str(locator.get("chunk_id") or "").strip()
                keyword = str(locator.get("keyword") or "").strip()
                query_text = str(locator.get("query_text") or "").strip()
                chunk_index = locator.get("chunk_index")
                try:
                    normalized_chunk_index = int(chunk_index) if chunk_index not in {None, ""} else None
                except (TypeError, ValueError):
                    normalized_chunk_index = None
                if db_id and file_id and (chunk_id or normalized_chunk_index is not None):
                    resource["locator"] = {
                        "db_id": db_id,
                        "file_id": file_id,
                        "chunk_id": chunk_id,
                        "chunk_index": normalized_chunk_index,
                        "keyword": keyword,
                        "query_text": query_text,
                    }
            normalized.append(resource)
        return normalized

    def normalize_practice_tasks(items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            objective = str(item.get("objective") or "").strip()
            action_type = str(item.get("action_type") or "").strip()
            estimated_minutes = item.get("estimated_minutes")
            if not title or not objective or not action_type:
                continue
            try:
                estimated_value = max(5, int(estimated_minutes))
            except (TypeError, ValueError):
                estimated_value = 30
            normalized.append(
                {
                    "title": title,
                    "objective": objective,
                    "action_type": action_type,
                    "estimated_minutes": estimated_value,
                }
            )
        return normalized

    def normalize_focus(items: Any) -> list[dict[str, str]]:
        if not isinstance(items, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            dimension_key = _normalize_dimension_key(item.get("dimension_key"))
            if dimension_key not in DIMENSION_DISPLAY_CONFIG:
                continue
            title = str(item.get("title") or "").strip()
            focus = str(item.get("focus") or item.get("description") or "").strip()
            if not title or not focus:
                continue
            normalized.append(
                {
                    "dimension_key": dimension_key,
                    "title": title,
                    "focus": focus,
                }
            )
        return normalized

    normalized = {
        "weaknesses": normalize_weaknesses(value.get("weaknesses")),
        "recommended_resources": normalize_resources(value.get("recommended_resources")),
        "practice_tasks": normalize_practice_tasks(value.get("practice_tasks")),
        "next_assessment_focus": normalize_focus(value.get("next_assessment_focus")),
    }
    if not any(normalized.values()):
        return None
    return normalized


def _normalize_detailed_scores(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []

    result: list[dict[str, Any]] = []
    for key, raw_score in value.items():
        normalized_score = _normalize_interview_score(raw_score)
        if normalized_score is None:
            continue
        result.append({"name": _label_dimension_key(str(key)), "score": normalized_score})
    return result


def _extract_score_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _label_dimension_key(key: str) -> str:
    fallback_labels = {
        "technical_knowledge": "技术能力",
        "practical_experience": "实战经验",
        "problem_solving_innovation": "问题解决",
        "communication_clarity": "沟通表达",
        "soft_skills_team_fit": "综合素质",
        "code_ability": "编码能力",
    }
    return fallback_labels.get(key, DIMENSION_LABELS.get(key, key))


def _normalize_dimension_key(key: str) -> str:
    normalized = str(key or "").strip()
    if not normalized:
        return ""
    normalized_no_space = normalized.replace(" ", "")
    direct_mapping = REVERSE_DIMENSION_LABELS.get(normalized) or REVERSE_DIMENSION_LABELS.get(normalized_no_space)
    if direct_mapping:
        return direct_mapping

    for keywords, target_key in DIMENSION_KEYWORD_MAPPING:
        if any(keyword in normalized_no_space for keyword in keywords):
            return target_key
    return normalized


def _normalize_scorecard(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    candidate_info = value.get("candidate_info") if isinstance(value.get("candidate_info"), dict) else {}
    assessment_summary = (
        value.get("assessment_summary") if isinstance(value.get("assessment_summary"), dict) else {}
    )
    detailed_scores = _extract_score_mapping(value.get("detailed_scores") or value.get("rating_scores"))
    dimension_scores = _extract_score_mapping(value.get("dimension_scores"))
    dimensions_scale_hint = _detect_score_scale(value.get("dimensions"))
    fallback_scale_hint = _detect_score_scale(detailed_scores or dimension_scores)
    interview_outcome = value.get("interview_outcome") if isinstance(value.get("interview_outcome"), dict) else {}
    match_assessment = value.get("match_assessment") if isinstance(value.get("match_assessment"), dict) else {}
    fallback_dimensions = _normalize_detailed_scores(detailed_scores or dimension_scores)
    fallback_overall = None
    if fallback_dimensions:
        fallback_overall = round(sum(item["score"] for item in fallback_dimensions) / len(fallback_dimensions))
    raw_overall_value = value.get(
        "overall",
        value.get("overall_score", value.get("total_score", value.get("total"))),
    )
    normalized_overall = _normalize_interview_score(
        raw_overall_value,
        scale_hint=dimensions_scale_hint or fallback_scale_hint,
    )
    if normalized_overall is None and fallback_overall is not None:
        normalized_overall = _normalize_score_value(fallback_overall)

    normalized = {
        "overall": normalized_overall,
        "role": str(
            value.get("role")
            or value.get("position")
            or value.get("target_position")
            or candidate_info.get("target_position")
            or ""
        ).strip(),
        "round": str(
            value.get("round") or value.get("interview_round") or candidate_info.get("interview_round") or ""
        ).strip(),
        "dimensions": _normalize_dimensions(value.get("dimensions")) or fallback_dimensions,
        "strengths": _normalize_string_list(
            value.get("strengths")
            or value.get("highlights")
            or assessment_summary.get("strengths")
            or assessment_summary.get("key_strengths")
            or match_assessment.get("strengths_for_position")
        ),
        "risks": _normalize_string_list(
            value.get("risks")
            or value.get("improvement_areas")
            or assessment_summary.get("concerns")
            or assessment_summary.get("key_concerns")
            or match_assessment.get("concerns_for_position")
        ),
        "suggestions": _normalize_string_list(
            value.get("suggestions")
            or value.get("next_steps")
            or interview_outcome.get("next_assessment_focus")
            or match_assessment.get("next_assessment_focus")
        ),
        "summary": str(
            value.get("summary")
            or assessment_summary.get("overall_conclusion")
            or interview_outcome.get("recommendation")
            or interview_outcome.get("recommendation_reason")
            or match_assessment.get("recommendation")
            or match_assessment.get("recommendation_reason")
            or value.get("final_recommendation")
            or ""
        ).strip(),
    }

    if (
        normalized["overall"] is None
        and not normalized["role"]
        and not normalized["round"]
        and not normalized["dimensions"]
        and not normalized["strengths"]
        and not normalized["risks"]
        and not normalized["suggestions"]
        and not normalized["summary"]
    ):
        return None

    return normalized


def _strip_scorecard_block(content: str) -> str:
    if not content:
        return ""
    return INTERVIEW_SCORECARD_PATTERN.sub("", content).strip()


def _count_terms(content: str, terms: tuple[str, ...]) -> int:
    text = str(content or "")
    if not text:
        return 0
    return sum(text.count(term) for term in terms)


def _estimate_speech_duration_seconds(
    *,
    content: str,
    previous_assistant_at,
    current_created_at,
) -> float:
    estimated_duration = max(8.0, len(content) / 3.6)
    if previous_assistant_at is None or current_created_at is None:
        return estimated_duration

    gap_seconds = (current_created_at - previous_assistant_at).total_seconds()
    if gap_seconds <= 0:
        return estimated_duration
    if 5 <= gap_seconds <= 180:
        return max(estimated_duration * 0.7, min(gap_seconds, estimated_duration * 1.8))
    return estimated_duration


def _collect_speech_turns(messages: list[Any] | None) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    last_assistant_created_at = None

    for message in messages or []:
        role = str(getattr(message, "role", "") or "").strip()
        metadata = getattr(message, "extra_metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}

        if role == "assistant" and not metadata.get("hidden_from_history"):
            last_assistant_created_at = getattr(message, "created_at", None)
            continue

        if role != "user" or metadata.get("hidden_from_history"):
            continue
        if str(metadata.get("voice_input_mode") or "").strip() != "speech":
            continue

        content = str(getattr(message, "content", "") or "").strip()
        if not content:
            continue

        created_at = getattr(message, "created_at", None)
        turns.append(
            {
                "content": content,
                "char_count": len(content),
                "duration_seconds": _estimate_speech_duration_seconds(
                    content=content,
                    previous_assistant_at=last_assistant_created_at,
                    current_created_at=created_at,
                ),
            }
        )

    return turns


def _build_expression_metric(
    *,
    score: float,
    level: str,
    detail: str,
    value: str,
) -> dict[str, Any]:
    return {
        "score": _clamp_score(score),
        "level": level,
        "detail": detail,
        "value": value,
    }


def _build_expression_analysis(
    *,
    conversation,
    scorecard: dict[str, Any] | None,
    messages: list[Any] | None,
) -> dict[str, Any] | None:
    metadata = dict(getattr(conversation, "extra_metadata", None) or {})
    if str(metadata.get("interview_mode") or "").strip() != "voice":
        return None

    speech_turns = _collect_speech_turns(messages)
    if not speech_turns:
        return None

    total_chars = sum(turn["char_count"] for turn in speech_turns)
    total_duration_seconds = max(sum(turn["duration_seconds"] for turn in speech_turns), 1.0)
    chars_per_minute = round(total_chars / total_duration_seconds * 60)

    filler_count = sum(_count_terms(turn["content"], FILLER_TERMS) for turn in speech_turns)
    hedge_count = sum(_count_terms(turn["content"], HEDGE_TERMS) for turn in speech_turns)
    assertive_count = sum(_count_terms(turn["content"], ASSERTIVE_TERMS) for turn in speech_turns)
    punctuation_count = sum(sum(turn["content"].count(char) for char in PAUSE_PUNCTUATION) for turn in speech_turns)
    sentences = [
        segment.strip()
        for turn in speech_turns
        for segment in SENTENCE_SPLIT_PATTERN.split(turn["content"])
        if segment.strip()
    ]
    sentence_count = max(len(sentences), 1)
    avg_sentence_chars = round(total_chars / sentence_count, 1)
    filler_density = filler_count / max(total_chars, 1) * 100
    hedge_density = hedge_count / max(total_chars, 1) * 100
    punctuation_density = punctuation_count / max(total_chars, 1) * 100

    speech_rate_score = 96 - min(abs(chars_per_minute - 220) * 0.32, 42)
    if chars_per_minute < 160:
        speech_rate_level = "偏慢"
    elif chars_per_minute > 280:
        speech_rate_level = "偏快"
    else:
        speech_rate_level = "适中"

    pause_control_score = 80 - filler_density * 8
    if 3 <= punctuation_density <= 12:
        pause_control_score += 8
    elif punctuation_density < 2:
        pause_control_score -= 8
    if filler_density < 1.2:
        pause_control_level = "自然"
    elif filler_density < 2.8:
        pause_control_level = "稳定"
    else:
        pause_control_level = "待优化"

    clarity_score = 78 - filler_density * 4
    if 12 <= avg_sentence_chars <= 38:
        clarity_score += 10
    elif avg_sentence_chars > 50 or avg_sentence_chars < 8:
        clarity_score -= 8
    if 3 <= punctuation_density <= 12:
        clarity_score += 4
    if clarity_score >= 85:
        clarity_level = "清晰"
    elif clarity_score >= 70:
        clarity_level = "较清晰"
    else:
        clarity_level = "待优化"

    communication_score = _extract_dimension_scores(scorecard).get("communication")
    confidence_score = 72 + assertive_count * 2.5 - hedge_density * 9 - filler_density * 3
    confidence_score += (_clamp_score(pause_control_score) - 75) * 0.12
    confidence_score += (_clamp_score(clarity_score) - 75) * 0.12
    if communication_score is not None:
        confidence_score += (communication_score - 70) * 0.18
    if confidence_score >= 85:
        confidence_level = "自信"
    elif confidence_score >= 70:
        confidence_level = "稳健"
    else:
        confidence_level = "保守"

    speech_rate_metric = _build_expression_metric(
        score=speech_rate_score,
        level=speech_rate_level,
        value=f"约 {chars_per_minute} 字/分钟",
        detail=f"基于 {len(speech_turns)} 次语音回答估算，当前回答节奏整体{speech_rate_level}。",
    )
    pause_control_metric = _build_expression_metric(
        score=pause_control_score,
        level=pause_control_level,
        value=f"语气词 {filler_count} 次",
        detail=f"语气词占比约 {filler_density:.1f}%，停顿节奏整体{pause_control_level}。",
    )
    clarity_metric = _build_expression_metric(
        score=clarity_score,
        level=clarity_level,
        value=f"句均 {avg_sentence_chars} 字",
        detail=f"句子平均长度约 {avg_sentence_chars} 字，表达结构{clarity_level}。",
    )
    confidence_metric = _build_expression_metric(
        score=confidence_score,
        level=confidence_level,
        value=f"肯定表达 {assertive_count} 次",
        detail=f"结合措辞强度与沟通表现推断，当前表达状态偏{confidence_level}。",
    )

    return {
        "input_mode": "speech",
        "summary": (
            f"本轮共分析 {len(speech_turns)} 次语音回答，语速{speech_rate_level}，"
            f"停顿控制{pause_control_level}，整体表达清晰度为{clarity_level}。"
        ),
        "speech_rate": speech_rate_metric,
        "pause_control": pause_control_metric,
        "clarity": clarity_metric,
        "confidence": confidence_metric,
    }


def _extract_scorecard(content: str) -> dict[str, Any] | None:
    if not content:
        return None

    match = INTERVIEW_SCORECARD_PATTERN.search(content)
    if not match:
        return None

    try:
        return _normalize_scorecard(json.loads(match.group(1).strip()))
    except Exception:
        return None


def _parse_thread_context(title: str | None) -> tuple[str, str]:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        return "", ""

    if "·" in normalized_title:
        left, right = normalized_title.split("·", 1)
        return left.strip(), right.strip()

    return normalized_title, ""


def _build_result_from_message(message, conversation, coding_session: dict[str, Any] | None) -> dict[str, Any] | None:
    scorecard = _extract_scorecard(getattr(message, "content", "") or "")
    if not scorecard:
        return None

    title_position, title_round = _parse_thread_context(getattr(conversation, "title", ""))
    if not scorecard.get("role"):
        scorecard["role"] = str((coding_session or {}).get("target_position") or title_position or "").strip()
    if not scorecard.get("round"):
        scorecard["round"] = title_round

    return {
        "status": "completed",
        "generated_at": format_utc_datetime(getattr(message, "created_at", None)),
        "source_message_id": getattr(message, "id", None),
        "summary_markdown": _strip_scorecard_block(getattr(message, "content", "") or ""),
        "scorecard": scorecard,
        "improvement_plan": None,
    }


def _normalize_result_payload(
    value: Any,
    *,
    conversation,
    coding_session: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    scorecard = _normalize_scorecard(value.get("scorecard"))
    title_position, title_round = _parse_thread_context(getattr(conversation, "title", ""))
    if scorecard:
        if not scorecard.get("role"):
            scorecard["role"] = str((coding_session or {}).get("target_position") or title_position or "").strip()
        if not scorecard.get("round"):
            scorecard["round"] = title_round

    status = str(value.get("status") or "").strip() or ("completed" if scorecard else "idle")
    payload = {
        "status": status,
        "generated_at": str(value.get("generated_at") or "").strip(),
        "source_message_id": value.get("source_message_id"),
        "summary_markdown": str(value.get("summary_markdown") or "").strip(),
        "scorecard": scorecard,
        "error_message": str(value.get("error_message") or "").strip(),
        "expression_analysis": _normalize_expression_analysis(value.get("expression_analysis")),
        "improvement_plan": _normalize_improvement_plan(value.get("improvement_plan")),
    }

    if payload["status"] == "completed" and payload["scorecard"]:
        return payload
    if payload["status"] in {"generating", "failed"}:
        return payload
    return None


def _resolve_interview_result_payload(
    conversation,
    *,
    stored_result: dict[str, Any] | None,
    coding_session: dict[str, Any] | None,
    messages: list[Any] | None = None,
) -> dict[str, Any] | None:
    if _is_result_complete_enough(stored_result):
        return stored_result

    for message in reversed(messages or []):
        if getattr(message, "role", "") != "assistant":
            continue
        derived = _build_result_from_message(message, conversation, coding_session)
        if derived:
            return derived

    return stored_result


def _extract_dimension_scores(scorecard: dict[str, Any] | None) -> dict[str, int | None]:
    values = {
        "technical_competence": None,
        "problem_solving": None,
        "communication": None,
        "soft_skills": None,
    }
    if not isinstance(scorecard, dict):
        return values
    buckets: dict[str, list[int]] = {key: [] for key in values}

    for item in scorecard.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        normalized_key = _normalize_dimension_key(item.get("name"))
        if normalized_key not in buckets:
            continue
        score = _normalize_score_value(item.get("score"))
        if score is not None:
            buckets[normalized_key].append(score)

    for key, score_bucket in buckets.items():
        if score_bucket:
            values[key] = round(sum(score_bucket) / len(score_bucket))
    return values


def _dimension_sort_key(item: tuple[str, int | None]) -> tuple[int, int]:
    key, score = item
    normalized = score if score is not None else -1
    return (normalized, list(DIMENSION_DISPLAY_CONFIG.keys()).index(key))


def _build_weakness_reason(
    *,
    dimension_key: str,
    score: int | None,
    scorecard: dict[str, Any] | None,
    expression_analysis: dict[str, Any] | None,
    coding_session: dict[str, Any] | None,
) -> str:
    config = DIMENSION_DISPLAY_CONFIG[dimension_key]
    risks = _normalize_string_list((scorecard or {}).get("risks"))
    suggestions = _normalize_string_list((scorecard or {}).get("suggestions"))
    related_hint = next(
        (
            item
            for item in [*risks, *suggestions]
            if config["label"][:2] in item or dimension_key == _normalize_dimension_key(item)
        ),
        "",
    )
    if related_hint:
        return related_hint
    if dimension_key == "communication" and expression_analysis:
        summary = str(expression_analysis.get("summary") or "").strip()
        if summary:
            return summary
    if dimension_key == "problem_solving":
        judge_status = str((coding_session or {}).get("judge_status") or "").strip()
        judge_score = (coding_session or {}).get("judge_result") or {}
        judge_numeric = _normalize_score_value(judge_score.get("score"))
        if judge_status and judge_status != "ACCEPTED":
            return f"代码考核当前判题结果为 {judge_status}，说明解题稳定性和实现完整度还有提升空间。"
        if judge_numeric is not None and judge_numeric < 80:
            return f"代码题得分为 {judge_numeric}，建议继续强化题目拆解、边界处理和实现细节。"
    score_text = f"当前维度得分约为 {score} 分，" if score is not None else ""
    return f"{score_text}在{config['label']}上的表现相对其他维度偏弱，建议优先安排专项练习。"


async def _select_knowledge_resources(
    *,
    user_id: str,
    keywords: list[str],
    query_text: str = "",
) -> list[dict[str, str]]:
    if not keywords:
        return []

    resources: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    databases = (await _get_accessible_databases_for_learning(user_id)).get("databases", [])
    normalized_keywords = [keyword for keyword in (str(item).strip() for item in keywords) if keyword]
    query_candidates = [query_text.strip()] if query_text.strip() else []
    query_candidates.extend(normalized_keywords)
    if normalized_keywords:
        query_candidates.append(" ".join(normalized_keywords))

    for database in databases:
        db_id = str(database.get("db_id") or "").strip()
        if not db_id:
            continue
        for candidate in query_candidates:
            if not candidate:
                continue
            try:
                query_results = await knowledge_base.aquery(candidate, db_id=db_id, final_top_k=3)
            except Exception as exc:
                logger.warning("Failed to query knowledge base %s for learning resource: %s", db_id, exc)
                continue

            if not isinstance(query_results, list):
                continue

            for result in query_results:
                if not isinstance(result, dict):
                    continue
                metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
                file_id = str(metadata.get("file_id") or "").strip()
                chunk_id = str(metadata.get("chunk_id") or "").strip()
                chunk_index = metadata.get("chunk_index")
                try:
                    normalized_chunk_index = int(chunk_index) if chunk_index not in {None, ""} else None
                except (TypeError, ValueError):
                    normalized_chunk_index = None
                if not file_id or (not chunk_id and normalized_chunk_index is None):
                    continue

                matched_keyword = next(
                    (
                        keyword
                        for keyword in normalized_keywords
                        if keyword.lower() in str(result.get("content") or "").lower()
                    ),
                    normalized_keywords[0] if normalized_keywords else candidate,
                )
                ref_anchor = chunk_id or normalized_chunk_index
                ref = f"knowledge-chunk://{db_id}/{file_id}#{ref_anchor}"
                if ref in seen_refs:
                    continue

                seen_refs.add(ref)
                resources.append(
                    {
                        "resource_type": "knowledge",
                        "title": f"{database.get('name') or '知识库'} · 精准学习",
                        "summary": _summarize_learning_excerpt(str(result.get("content") or "").strip()),
                        "source_type": "knowledge_chunk",
                        "source_id": db_id,
                        "source_ref": ref,
                        "locator": {
                            "db_id": db_id,
                            "file_id": file_id,
                            "chunk_id": chunk_id,
                            "chunk_index": normalized_chunk_index,
                            "keyword": matched_keyword,
                            "query_text": candidate,
                        },
                    }
                )
                if len(resources) >= RESOURCE_LIMIT:
                    return resources
    return resources


def _select_problem_resources(
    *,
    target_position: str,
    difficulty_level: str | None,
    keywords: list[str],
) -> list[dict[str, str]]:
    package_payload = list_imported_problem_packages()
    problems = package_payload.get("problems") or []
    normalized_position = str(target_position or "").strip().lower()
    normalized_difficulty = str(difficulty_level or "").strip().lower()

    ranked: list[dict[str, Any]] = []
    for item in problems:
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        topic_tags = [str(tag).strip().lower() for tag in (item.get("topic_tags") or []) if str(tag).strip()]
        position_tag = str(item.get("primary_position_tag") or "").strip().lower()
        difficulty_tag = str(item.get("difficulty_tag") or "").strip().lower()
        score = 0
        if normalized_position:
            if ("前端" in normalized_position and position_tag == "frontend") or (
                "后端" in normalized_position and position_tag == "backend"
            ):
                score += 3
        if normalized_difficulty and difficulty_tag == normalized_difficulty:
            score += 2
        if any(keyword.lower() in f"{title} {summary}".lower() for keyword in keywords):
            score += 2
        if any(keyword.lower() in topic_tags for keyword in keywords):
            score += 1
        if score <= 0:
            continue
        ranked.append({"score": score, "item": item})

    ranked.sort(key=lambda entry: (-entry["score"], str(entry["item"].get("title") or "")))
    selected: list[dict[str, str]] = []
    for entry in ranked[:2]:
        item = entry["item"]
        selected.append(
            {
                "resource_type": "interview_question",
                "title": str(item.get("title") or "推荐练习题").strip(),
                "summary": str(item.get("summary") or "结合当前短板做一轮定向代码练习。").strip(),
                "source_type": "problem_package",
                "source_id": str(item.get("package_path") or "").strip(),
                "source_ref": (
                    "problem-package://"
                    f"{str(item.get('package_path') or '').strip()}#problem-"
                    f"{int(item.get('problem_index') or 0)}"
                ),
            }
        )
    return selected


def _build_practice_task(dimension_key: str, reason: str) -> dict[str, Any]:
    config = DIMENSION_DISPLAY_CONFIG[dimension_key]
    minute_map = {
        "technical_competence": 35,
        "problem_solving": 45,
        "communication": 20,
        "soft_skills": 25,
    }
    return {
        "title": config["practice_title"],
        "objective": reason,
        "action_type": config["practice_action"],
        "estimated_minutes": minute_map.get(dimension_key, 30),
    }


def _build_next_focus(dimension_key: str, score: int | None) -> dict[str, str]:
    config = DIMENSION_DISPLAY_CONFIG[dimension_key]
    if dimension_key == "communication":
        focus = "下次评估重点观察回答是否先给结论、再补充细节，并保持稳定语速与停顿。"
    elif dimension_key == "problem_solving":
        focus = "下次评估重点观察题目拆解、边界覆盖和代码实现是否更加完整。"
    elif dimension_key == "technical_competence":
        focus = "下次评估重点观察是否能准确解释基础概念、原理差异与实际应用场景。"
    else:
        focus = "下次评估重点观察是否能用具体项目经历支撑岗位匹配和团队协作判断。"
    if score is not None:
        focus = f"{focus} 当前该维度约 {score} 分。"
    return {
        "dimension_key": dimension_key,
        "title": config["focus_title"],
        "focus": focus,
    }


async def _generate_improvement_plan(
    *,
    conversation,
    scorecard: dict[str, Any] | None,
    expression_analysis: dict[str, Any] | None,
    coding_session: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(scorecard, dict):
        return None

    dimension_scores = _extract_dimension_scores(scorecard)
    ordered_scores = sorted(dimension_scores.items(), key=_dimension_sort_key)
    weakness_candidates: list[tuple[str, int | None]] = []
    for dimension_key, score in ordered_scores:
        if score is None or score <= LOW_SCORE_THRESHOLD:
            weakness_candidates.append((dimension_key, score))
    if not weakness_candidates:
        weakness_candidates = ordered_scores[:2]

    weaknesses: list[dict[str, str]] = []
    recommended_resources: list[dict[str, str]] = []
    practice_tasks: list[dict[str, Any]] = []
    next_focus: list[dict[str, str]] = []
    seen_resource_refs: set[str] = set()

    target_position = str(
        (coding_session or {}).get("target_position")
        or (scorecard or {}).get("role")
        or (conversation.extra_metadata or {}).get("target_position")
        or ""
    ).strip()
    difficulty_level = str((coding_session or {}).get("difficulty_level") or "").strip()
    dimension_keywords = {
        "technical_competence": ["基础", "原理", "技术", "知识点", "问答", "八股"],
        "problem_solving": ["算法", "题解", "边界", "复杂度"],
        "communication": ["表达", "沟通", "结构化", "回答", "追问"],
        "soft_skills": ["项目", "协作", "亮点", "岗位", "经历"],
    }

    for dimension_key, score in weakness_candidates[:WEAKNESS_LIMIT]:
        config = DIMENSION_DISPLAY_CONFIG[dimension_key]
        reason = _build_weakness_reason(
            dimension_key=dimension_key,
            score=score,
            scorecard=scorecard,
            expression_analysis=expression_analysis,
            coding_session=coding_session,
        )
        weaknesses.append(
            {
                "dimension_key": dimension_key,
                "title": config["weakness_title"],
                "reason": reason,
            }
        )
        practice_tasks.append(_build_practice_task(dimension_key, reason))
        next_focus.append(_build_next_focus(dimension_key, score))

        resources: list[dict[str, str]]
        if dimension_key == "technical_competence":
            resources = await _select_knowledge_resources(
                user_id=str(conversation.user_id),
                keywords=dimension_keywords[dimension_key],
                query_text=reason,
            )
        elif dimension_key == "problem_solving":
            resources = _select_problem_resources(
                target_position=target_position,
                difficulty_level=difficulty_level,
                keywords=dimension_keywords[dimension_key],
            )
        else:
            resources = await _select_knowledge_resources(
                user_id=str(conversation.user_id),
                keywords=dimension_keywords[dimension_key],
                query_text=reason,
            )

        for resource in resources:
            ref = str(resource.get("source_ref") or "").strip()
            if ref and ref in seen_resource_refs:
                continue
            if ref:
                seen_resource_refs.add(ref)
            recommended_resources.append(resource)
            if len(recommended_resources) >= RESOURCE_LIMIT:
                break

    return {
        "weaknesses": weaknesses[:WEAKNESS_LIMIT],
        "recommended_resources": recommended_resources[:RESOURCE_LIMIT],
        "practice_tasks": practice_tasks[:PRACTICE_LIMIT],
        "next_assessment_focus": next_focus[:WEAKNESS_LIMIT],
    }


async def _ensure_result_enrichment(
    *,
    db: AsyncSession,
    thread_id: str,
    current_user_id: str,
    conversation,
    result_payload: dict[str, Any] | None,
    coding_session: dict[str, Any] | None,
    messages: list[Any] | None,
    persist_if_missing: bool,
) -> dict[str, Any] | None:
    if not isinstance(result_payload, dict):
        return result_payload

    enriched = dict(result_payload)
    expression_analysis = _normalize_expression_analysis(enriched.get("expression_analysis")) or (
        _build_expression_analysis(
            conversation=conversation,
            scorecard=enriched.get("scorecard"),
            messages=messages,
        )
    )
    if expression_analysis:
        enriched["expression_analysis"] = expression_analysis

    if not _normalize_improvement_plan(enriched.get("improvement_plan")) and enriched.get("status") == "completed":
        improvement_plan = await _generate_improvement_plan(
            conversation=conversation,
            scorecard=enriched.get("scorecard"),
            expression_analysis=expression_analysis,
            coding_session=coding_session,
        )
        if improvement_plan:
            enriched["improvement_plan"] = improvement_plan
            if persist_if_missing:
                await _save_interview_result_metadata(
                    db,
                    thread_id=thread_id,
                    current_user_id=current_user_id,
                    result_payload=enriched,
                )
    return enriched


def _build_result_summary(scorecard: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(scorecard, dict):
        return {}
    return {
        "overall": scorecard.get("overall"),
        "role": str(scorecard.get("role") or "").strip(),
        "round": str(scorecard.get("round") or "").strip(),
        "summary": str(scorecard.get("summary") or "").strip(),
        "dimensions": list(scorecard.get("dimensions") or []),
    }


def _build_history_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed_records = [
        item
        for item in records
        if item.get("has_result") and item.get("status") == "completed" and item.get("improvement_plan")
    ][:HISTORY_PROFILE_WINDOW]
    dimension_buckets: dict[str, list[int]] = {key: [] for key in DIMENSION_DISPLAY_CONFIG}
    low_score_counts: dict[str, int] = {key: 0 for key in DIMENSION_DISPLAY_CONFIG}

    for record in completed_records:
        for dimension in record.get("dimensions") or []:
            key = str(dimension.get("key") or "").strip()
            score = _normalize_score_value(dimension.get("score"))
            if key not in dimension_buckets or score is None:
                continue
            dimension_buckets[key].append(score)
            if score <= LOW_SCORE_THRESHOLD:
                low_score_counts[key] += 1

    top_weakness_dimensions = sorted(
        [
            {
                "dimension_key": key,
                "label": DIMENSION_DISPLAY_CONFIG[key]["label"],
                "average_score": round(sum(scores) / len(scores)),
                "low_score_count": low_score_counts[key],
            }
            for key, scores in dimension_buckets.items()
            if scores
        ],
        key=lambda item: (item["average_score"], -item["low_score_count"]),
    )[:3]

    latest_record = completed_records[0] if completed_records else {}
    latest_plan = latest_record.get("improvement_plan") if isinstance(latest_record, dict) else {}

    return {
        "top_weakness_dimensions": top_weakness_dimensions,
        "latest_focus": list((latest_plan or {}).get("next_assessment_focus") or []),
        "pending_practice_count": len((latest_plan or {}).get("practice_tasks") or []),
    }


async def _resolve_target_user(
    db: AsyncSession,
    *,
    current_user: User,
    target_user_id: int | None,
) -> User:
    if target_user_id is None or target_user_id == current_user.id:
        return current_user

    result = await db.execute(select(User).where(User.id == target_user_id, User.is_deleted == 0))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if current_user.role == "superadmin":
        return target_user

    if current_user.role == "admin":
        if target_user.role != "user":
            raise HTTPException(status_code=403, detail="无权查看该用户的面试记录")
        return target_user

    raise HTTPException(status_code=403, detail="无权查看其他用户的面试记录")


def _build_history_record(*, conversation, result_payload: dict[str, Any] | None) -> dict[str, Any]:
    metadata = dict(conversation.extra_metadata or {})
    coding_session = get_coding_session_from_metadata(metadata)
    title_position, title_round = _parse_thread_context(conversation.title)
    scorecard = result_payload.get("scorecard") if isinstance(result_payload, dict) else None
    dimension_scores = _extract_dimension_scores(scorecard)
    interview_mode = str(metadata.get("interview_mode") or "").strip() or "text"
    position = str(
        metadata.get("target_position")
        or (coding_session or {}).get("target_position")
        or (scorecard or {}).get("role")
        or title_position
        or ""
    ).strip()
    round_name = str(
        metadata.get("interview_round")
        or (scorecard or {}).get("round")
        or title_round
        or ""
    ).strip()

    result_status = str((result_payload or {}).get("status") or "").strip()
    is_complete_result = _is_result_complete_enough(result_payload)
    if result_status == "completed" and is_complete_result:
        status = "completed"
    elif result_status in {"generating", "failed"}:
        status = result_status
    else:
        status = "in_progress"

    dimension_items = [
        {
            "key": "technical_competence",
            "label": "技术能力",
            "score": dimension_scores["technical_competence"],
        },
        {
            "key": "problem_solving",
            "label": "问题解决",
            "score": dimension_scores["problem_solving"],
        },
        {
            "key": "communication",
            "label": "沟通表达",
            "score": dimension_scores["communication"],
        },
        {
            "key": "soft_skills",
            "label": "综合素质",
            "score": dimension_scores["soft_skills"],
        },
    ]

    return {
        "thread_id": conversation.thread_id,
        "title": conversation.title or "未命名面试",
        "created_at": format_utc_datetime(conversation.created_at),
        "updated_at": format_utc_datetime(conversation.updated_at),
        "interview_mode": interview_mode,
        "position": position or "后端工程师",
        "round": round_name or "初试",
        "status": status,
        "overall_score": (scorecard or {}).get("overall"),
        "dimensions": dimension_items,
        "has_result": status == "completed" and is_complete_result,
        "result_generated_at": str((result_payload or {}).get("generated_at") or "").strip(),
    }


def _build_history_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed_records = sorted(
        [
            item
            for item in records
            if item.get("has_result") and item.get("status") == "completed"
        ],
        key=lambda item: (str(item.get("created_at") or ""), str(item.get("thread_id") or "")),
    )

    categories = [item["created_at"] for item in completed_records]
    dimension_key_map = {
        "technical_competence": "technical_competence",
        "problem_solving": "problem_solving",
        "communication": "communication",
        "soft_skills": "soft_skills",
    }

    series = [
        {
            "key": "overall",
            "label": "总分",
            "data": [item.get("overall_score") for item in completed_records],
        }
    ]

    for key, label in (
        ("technical_competence", "技术能力"),
        ("problem_solving", "问题解决"),
        ("communication", "沟通表达"),
        ("soft_skills", "综合素质"),
    ):
        series.append(
            {
                "key": key,
                "label": label,
                "data": [
                    next(
                        (
                            dimension.get("score")
                            for dimension in item.get("dimensions", [])
                            if dimension.get("key") == dimension_key_map[key]
                        ),
                        None,
                    )
                    for item in completed_records
                ],
            }
        )

    return {
        "categories": categories,
        "series": series,
    }


def _is_result_complete_enough(result_payload: dict[str, Any] | None) -> bool:
    if not isinstance(result_payload, dict):
        return False
    if result_payload.get("status") != "completed":
        return False

    scorecard = result_payload.get("scorecard")
    if not isinstance(scorecard, dict):
        return False

    if scorecard.get("overall") is not None:
        return True
    if scorecard.get("dimensions"):
        return True
    if scorecard.get("strengths"):
        return True
    if scorecard.get("risks"):
        return True
    if scorecard.get("suggestions"):
        return True
    return False


async def _require_interview_conversation(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
):
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
    if not conversation or conversation.user_id != str(current_user_id) or conversation.status == "deleted":
        raise HTTPException(status_code=404, detail="对话线程不存在")
    if conversation.agent_id != INTERVIEW_AGENT_ID:
        raise HTTPException(status_code=400, detail="当前线程不是模拟面试线程")
    return conv_repo, conversation


async def _save_interview_result_metadata(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    conv_repo, _ = await _require_interview_conversation(db, thread_id=thread_id, current_user_id=current_user_id)
    await conv_repo.update_conversation(
        thread_id,
        metadata={INTERVIEW_RESULT_METADATA_KEY: result_payload},
    )
    return result_payload


async def get_interview_result(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
) -> dict[str, Any]:
    conv_repo, conversation = await _require_interview_conversation(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
    )
    coding_session = get_coding_session_from_metadata(conversation.extra_metadata)
    messages = await conv_repo.get_messages_by_thread_id(thread_id)

    stored_result = _normalize_result_payload(
        (conversation.extra_metadata or {}).get(INTERVIEW_RESULT_METADATA_KEY),
        conversation=conversation,
        coding_session=coding_session,
    )
    if _is_result_complete_enough(stored_result):
        result_payload = await _ensure_result_enrichment(
            db=db,
            thread_id=thread_id,
            current_user_id=current_user_id,
            conversation=conversation,
            result_payload=dict(stored_result or {}),
            coding_session=coding_session,
            messages=messages,
            persist_if_missing=True,
        )
        return {
            "thread_id": conversation.thread_id,
            "title": conversation.title,
            "agent_id": conversation.agent_id,
            "result": result_payload,
            "coding_session": coding_session,
        }

    for message in reversed(messages):
        if getattr(message, "role", "") != "assistant":
            continue
        derived = _build_result_from_message(message, conversation, coding_session)
        if not derived:
            continue

        await _save_interview_result_metadata(
            db,
            thread_id=thread_id,
            current_user_id=current_user_id,
            result_payload=derived,
        )
        derived = await _ensure_result_enrichment(
            db=db,
            thread_id=thread_id,
            current_user_id=current_user_id,
            conversation=conversation,
            result_payload=derived,
            coding_session=coding_session,
            messages=messages,
            persist_if_missing=True,
        )
        return {
            "thread_id": conversation.thread_id,
            "title": conversation.title,
            "agent_id": conversation.agent_id,
            "result": derived,
            "coding_session": coding_session,
        }

    if stored_result:
        stored_result = await _ensure_result_enrichment(
            db=db,
            thread_id=thread_id,
            current_user_id=current_user_id,
            conversation=conversation,
            result_payload=dict(stored_result),
            coding_session=coding_session,
            messages=messages,
            persist_if_missing=True,
        )

    return {
        "thread_id": conversation.thread_id,
        "title": conversation.title,
        "agent_id": conversation.agent_id,
        "result": stored_result,
        "coding_session": coding_session,
    }


async def get_interview_history(
    db: AsyncSession,
    *,
    current_user: User,
    user_id: int | None = None,
) -> dict[str, Any]:
    target_user = await _resolve_target_user(
        db,
        current_user=current_user,
        target_user_id=user_id,
    )
    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_conversations(
        user_id=str(target_user.id),
        agent_id=INTERVIEW_AGENT_ID,
        status="active",
        limit=None,
        offset=0,
    )

    records: list[dict[str, Any]] = []
    for conversation in conversations:
        metadata = dict(conversation.extra_metadata or {})
        coding_session = get_coding_session_from_metadata(metadata)
        stored_result = _normalize_result_payload(
            metadata.get(INTERVIEW_RESULT_METADATA_KEY),
            conversation=conversation,
            coding_session=coding_session,
        )

        messages: list[Any] | None = None
        if not _is_result_complete_enough(stored_result):
            messages = await conv_repo.get_messages_by_thread_id(conversation.thread_id)

        result_payload = _resolve_interview_result_payload(
            conversation,
            stored_result=stored_result,
            coding_session=coding_session,
            messages=messages,
        )
        enriched_result = await _ensure_result_enrichment(
            db=db,
            thread_id=conversation.thread_id,
            current_user_id=str(target_user.id),
            conversation=conversation,
            result_payload=result_payload,
            coding_session=coding_session,
            messages=messages,
            persist_if_missing=False,
        )
        record = _build_history_record(conversation=conversation, result_payload=enriched_result)
        record["improvement_plan"] = (enriched_result or {}).get("improvement_plan")
        records.append(record)

    records.sort(
        key=lambda item: (str(item.get("updated_at") or ""), str(item.get("thread_id") or "")),
        reverse=True,
    )

    return {
        "target_user": {
            "id": target_user.id,
            "user_id": target_user.user_id,
            "username": target_user.username,
            "role": target_user.role,
        },
        "profile": _build_history_profile(records),
        "chart": _build_history_chart(records),
        "records": records,
    }


async def get_interview_improvement_plan(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
) -> dict[str, Any]:
    payload = await get_interview_result(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
    )
    result = payload.get("result") if isinstance(payload, dict) else {}
    scorecard = result.get("scorecard") if isinstance(result, dict) else None
    return {
        "thread_id": thread_id,
        "result_status": str((result or {}).get("status") or "").strip(),
        "scorecard_summary": _build_result_summary(scorecard),
        "improvement_plan": (result or {}).get("improvement_plan"),
    }


async def get_interview_learning_document(
    *,
    db_id: str,
    file_id: str,
    current_user: User,
) -> dict[str, Any]:
    _ = current_user
    accessible = await knowledge_base.check_accessible({"role": current_user.role}, db_id)
    if not accessible:
        raise HTTPException(status_code=403, detail="无权访问该知识库文档")

    database = await knowledge_base.get_database_info(db_id)
    if not isinstance(database, dict):
        raise HTTPException(status_code=404, detail="知识库不存在")

    files = database.get("files") if isinstance(database.get("files"), dict) else {}
    file_meta = files.get(file_id)
    if not isinstance(file_meta, dict):
        raise HTTPException(status_code=404, detail="文档不存在")
    if file_meta.get("is_folder"):
        raise HTTPException(status_code=400, detail="当前目标不是可学习文档")

    file_info = await knowledge_base.get_file_info(db_id, file_id)
    meta = file_info.get("meta") if isinstance(file_info.get("meta"), dict) else file_meta
    return {
        "db_id": db_id,
        "db_name": str(database.get("name") or "").strip(),
        "file_id": file_id,
        "file_name": str(meta.get("filename") or meta.get("original_filename") or file_id).strip(),
        "meta": meta,
        "content": str(file_info.get("content") or ""),
        "lines": file_info.get("lines") or [],
    }


def _build_finalize_prompt(
    *,
    target_position: str,
    interview_round: str,
    coding_session: dict[str, Any] | None,
) -> str:
    coding_result = coding_session.get("judge_result") if isinstance(coding_session, dict) else {}
    coding_status = str((coding_session or {}).get("judge_status") or (coding_result or {}).get("status") or "").strip()
    coding_score = (coding_result or {}).get("score")
    problem_title = str((coding_session or {}).get("problem_title") or "").strip()
    difficulty = str((coding_session or {}).get("difficulty_level") or "").strip()
    submitted_at = str((coding_session or {}).get("submitted_at") or "").strip()

    lines = [
        "代码考核已经结束，请你现在直接完成第 6、7 阶段，不要继续追问用户，也不要要求用户再返回聊天作答。",
        f"目标岗位：{target_position or '后端工程师'}",
        f"面试轮次：{interview_round or '初试'}",
    ]
    if problem_title:
        lines.append(f"代码题：{problem_title}")
    if difficulty:
        lines.append(f"代码题难度：{difficulty}")
    if coding_status:
        lines.append(f"判题结果：{coding_status}")
    if coding_score is not None:
        lines.append(f"代码题得分：{coding_score}")
    if submitted_at:
        lines.append(f"提交时间：{submitted_at}")

    lines.extend(
        [
            "",
            "请输出最终总结，要求：",
            "1. 先用一小段中文给出岗位匹配结论、亮点与主要风险。",
            "2. 明确说明“完整结果已生成，可在面试结果页查看”。",
            "3. 最后必须输出 ```interview_scorecard``` 代码块，内容为合法 JSON。",
            "4. 不要继续发问，不要输出额外待办，不要省略评分卡。",
        ]
    )
    return "\n".join(lines)


async def _invoke_interview_finalize_turn(
    db: AsyncSession,
    *,
    conversation,
    current_user: User,
    target_position: str,
    interview_round: str,
    coding_session: dict[str, Any] | None,
) -> None:
    agent = agent_manager.get_agent("InterviewAgent")
    if not agent:
        raise HTTPException(status_code=500, detail="模拟面试智能体不存在")

    conv_repo = ConversationRepository(db)
    prompt = _build_finalize_prompt(
        target_position=target_position,
        interview_round=interview_round,
        coding_session=coding_session,
    )
    human_message = HumanMessage(content=prompt)
    await conv_repo.add_message_by_thread_id(
        thread_id=conversation.thread_id,
        role="user",
        content=prompt,
        message_type="text",
        extra_metadata={
            "raw_message": human_message.model_dump(),
            "hidden_from_history": True,
            "internal_prompt_type": "interview_finalize_result",
        },
    )

    config_item, agent_config_id = await _resolve_agent_config(
        db,
        "InterviewAgent",
        str(current_user.id),
        None,
    )
    runtime_config = {
        "context_overrides": {
            "target_position": target_position,
            "interview_round": interview_round,
        }
    }
    agent_config = await _build_effective_agent_config(
        "InterviewAgent",
        config_item,
        runtime_config,
        db=db,
        user_id=str(current_user.id),
    )
    input_context = {
        "user_id": str(current_user.id),
        "thread_id": conversation.thread_id,
        "agent_config_id": agent_config_id,
        "agent_config": agent_config,
    }

    try:
        await agent.invoke_messages([human_message], input_context=input_context)
        langgraph_config = {"configurable": {"thread_id": conversation.thread_id, "user_id": str(current_user.id)}}
        await save_messages_from_langgraph_state(
            agent_instance=agent,
            thread_id=conversation.thread_id,
            conv_repo=conv_repo,
            config_dict=langgraph_config,
        )
    except Exception as exc:
        logger.error("Finalize interview result failed: %s", exc)
        raise HTTPException(status_code=500, detail="生成面试结果失败，请稍后重试") from exc


async def finalize_interview_result(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user: User,
    target_position: str | None = None,
    interview_round: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    _, conversation = await _require_interview_conversation(
        db,
        thread_id=thread_id,
        current_user_id=str(current_user.id),
    )
    coding_session = get_coding_session_from_metadata(conversation.extra_metadata)

    existing = await get_interview_result(db, thread_id=thread_id, current_user_id=str(current_user.id))
    existing_result = existing.get("result") or {}
    if existing_result.get("status") == "completed" and not force:
        return existing

    judge_status = str((coding_session or {}).get("judge_status") or "").strip()
    if judge_status in PENDING_JUDGE_STATUSES:
        raise HTTPException(status_code=409, detail="代码考核仍在判题中，请稍后再生成面试结果")

    title_position, title_round = _parse_thread_context(conversation.title)
    effective_position = (
        str(target_position or (coding_session or {}).get("target_position") or title_position or "").strip()
        or "后端工程师"
    )
    effective_round = str(interview_round or title_round or "").strip() or "初试"

    await _save_interview_result_metadata(
        db,
        thread_id=thread_id,
        current_user_id=str(current_user.id),
        result_payload={
            "status": "generating",
            "generated_at": "",
            "source_message_id": None,
            "summary_markdown": "",
            "scorecard": None,
            "error_message": "",
        },
    )

    try:
        await _invoke_interview_finalize_turn(
            db,
            conversation=conversation,
            current_user=current_user,
            target_position=effective_position,
            interview_round=effective_round,
            coding_session=coding_session,
        )
        refreshed = await get_interview_result(db, thread_id=thread_id, current_user_id=str(current_user.id))
        if refreshed.get("result", {}).get("status") == "completed":
            return refreshed

        raise HTTPException(status_code=500, detail="面试结果生成完成，但未解析出评分卡")
    except HTTPException as exc:
        await _save_interview_result_metadata(
            db,
            thread_id=thread_id,
            current_user_id=str(current_user.id),
            result_payload={
                "status": "failed",
                "generated_at": "",
                "source_message_id": None,
                "summary_markdown": "",
                "scorecard": None,
                "error_message": str(exc.detail),
            },
        )
        raise
