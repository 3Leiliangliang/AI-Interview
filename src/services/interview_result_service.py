from __future__ import annotations

import ast
import asyncio
import html
import json
import re
from urllib.parse import urlparse
from typing import Any

from fastapi import HTTPException
from langchain.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import config, knowledge_base
from src.agents import agent_manager
from src.repositories.conversation_repository import ConversationRepository
from src.services.chat_stream_service import (
    _build_effective_agent_config,
    _resolve_agent_config,
    save_messages_from_langgraph_state,
)
from src.services.interview_coding_service import (
    _build_practice_problem_ref,
    get_coding_session_from_metadata,
    list_imported_problem_packages,
)
from src.services.position_types import get_default_position_label, get_problemset_tag_for_position
from src.storage.postgres.models_business import User
from src.utils.datetime_utils import format_utc_datetime
from src.utils.logging_config import logger
from src.utils.web_search import WebSearcher

INTERVIEW_RESULT_METADATA_KEY = "interview_result"
INTERVIEW_AGENT_ID = "InterviewAgent"
INTERVIEW_SCORECARD_PATTERN = re.compile(
    r"```interview_scorecard\s*(\{[\s\S]*?\})\s*```",
    re.IGNORECASE,
)
GENERIC_JSON_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",
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
    "架构设计": "problem_solving",
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
QUESTION_MATCH_NORMALIZE_PATTERN = re.compile(r"[^\w\u4e00-\u9fff]+")
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
TECHNICAL_QUESTION_REVIEW_LIMIT = 8
TECHNICAL_QUESTION_LOW_SCORE_THRESHOLD = 60
EXTERNAL_RESOURCE_LIMIT = 4
EXTERNAL_RESOURCE_MIN_SCORE = 0.5
EXTERNAL_RESOURCE_PER_TYPE_LIMIT = 2
REPORT_HIGHLIGHT_LIMIT = 3
TECHNICAL_QUESTION_STOPWORDS = {
    "什么",
    "一下",
    "一个",
    "一种",
    "如何",
    "为什么",
    "怎么",
    "怎样",
    "哪些",
    "请问",
    "说明",
    "介绍",
    "这个",
    "那个",
    "以及",
    "如果",
    "是否",
    "实现",
    "原理",
    "过程",
    "场景",
}
ENGLISH_TECHNICAL_QUESTION_STOPWORDS = {
    "how",
    "what",
    "when",
    "where",
    "which",
    "why",
    "who",
    "can",
    "could",
    "would",
    "should",
    "will",
    "you",
    "your",
    "ensure",
    "explain",
    "describe",
    "mention",
    "specific",
    "techniques",
    "modules",
    "application",
    "particularly",
    "dealing",
    "tasks",
    "task",
    "using",
    "would",
    "use",
    "with",
    "from",
    "into",
    "about",
    "there",
    "their",
    "them",
    "they",
    "this",
    "that",
    "these",
    "those",
    "the",
    "and",
    "for",
}
QUESTION_KEYWORD_NOISE_TERMS = (
    "感谢分享",
    "你的回答",
    "很具体",
    "继续下一题",
    "接下来",
    "请听题",
    "下面我们",
)
QUESTION_KEYWORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_+#.-]{2,}|[\u4e00-\u9fff]{2,}")
EXTERNAL_RESOURCE_DOMAIN_ALLOWLIST = (
    "redis.io",
    "postgresql.org",
    "mysql.com",
    "developer.mozilla.org",
    "docs.python.org",
    "docs.djangoproject.com",
    "fastapi.tiangolo.com",
    "nodejs.org",
    "go.dev",
    "spring.io",
    "docs.oracle.com",
    "juejin.cn",
    "infoq.cn",
    "cnblogs.com",
    "cloud.tencent.com",
    "developer.aliyun.com",
    "bilibili.com",
)
THREAD_CONTEXT_SPLIT_PATTERNS = (
    re.compile(r"\s*[·•｜|]\s*"),
    re.compile(r"\s+[?？]\s+"),
    re.compile(r"\s+[-—–]+\s+"),
)


async def _get_accessible_databases_for_learning(user_id: str) -> dict[str, Any]:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return {"databases": []}

    if normalized_user_id.isdigit():
        return await knowledge_base.get_databases_by_raw_id(int(normalized_user_id))
    return await knowledge_base.get_databases_by_user_id(normalized_user_id)


def _clean_resource_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _summarize_learning_excerpt(content: str, limit: int = 140) -> str:
    text = _clean_resource_text(content)
    if not text:
        return "建议回看该知识点对应文档片段。"
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _create_web_searcher() -> WebSearcher | None:
    if not config.enable_web_search:
        return None
    try:
        return WebSearcher()
    except Exception as exc:
        logger.warning("Web search unavailable for interview result enrichment: %s", exc)
        return None


def _hostname_matches_allowed_domain(hostname: str) -> bool:
    normalized = str(hostname or "").strip().lower()
    if not normalized:
        return False
    return any(
        normalized == domain or normalized.endswith(f".{domain}") for domain in EXTERNAL_RESOURCE_DOMAIN_ALLOWLIST
    )


def _is_allowed_external_resource_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    return _hostname_matches_allowed_domain(parsed.netloc.split(":")[0])


def _extract_provider_from_url(url: str) -> str:
    try:
        hostname = urlparse(str(url or "").strip()).netloc.split(":")[0].lower()
    except Exception:
        return ""
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _infer_external_resource_type(*, title: str, content: str, url: str) -> str:
    normalized_title = str(title or "").lower()
    normalized_content = str(content or "").lower()
    normalized_url = str(url or "").lower()
    if "bilibili.com" in normalized_url or "youtube.com" in normalized_url or "youtu.be" in normalized_url:
        return "video"
    if any(
        keyword in normalized_title or keyword in normalized_content
        for keyword in ("视频", "讲解", "课程", "tutorial", "course", "lesson")
    ):
        return "video"
    if any(
        keyword in normalized_title or keyword in normalized_content
        for keyword in ("案例", "实战", "case study", "case-study", "复盘", "架构实践")
    ):
        return "case"
    return "article"


def _infer_external_resource_language(*, title: str, content: str) -> str:
    text = f"{title} {content}"
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def _default_external_resource_minutes(resource_type: str) -> int:
    if resource_type == "video":
        return 20
    if resource_type == "case":
        return 25
    return 15


def _default_external_resource_difficulty(resource_type: str) -> str:
    if resource_type == "case":
        return "强化"
    if resource_type == "video":
        return "进阶"
    return "进阶"


def _build_external_resource_reason(
    *,
    dimension_label: str,
    focus_keyword: str,
    weakness_reason: str,
    resource_title: str,
    resource_content: str,
    resource_type: str,
) -> str:
    resource_label = {
        "article": "这篇文章",
        "video": "这个视频",
        "case": "这个案例",
    }.get(resource_type, "这个资源")
    summary = _summarize_learning_excerpt(resource_content, limit=48)
    weakness_hint = str(weakness_reason or "").strip() or f"你在{dimension_label}上的表现偏弱"
    if summary and summary != "建议回看该知识点对应文档片段。":
        return f"{resource_label}围绕“{focus_keyword}”展开，{summary}，能直接帮助你改善“{weakness_hint}”这个问题。"
    title_hint = str(resource_title or "").strip() or resource_label
    return f"推荐你学习《{title_hint}》，它更贴近“{weakness_hint}”，可重点补强 {focus_keyword}。"


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


def _normalize_learning_locator(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    db_id = str(value.get("db_id") or "").strip()
    file_id = str(value.get("file_id") or "").strip()
    if not db_id or not file_id:
        return None

    raw_chunk_index = value.get("chunk_index")
    try:
        chunk_index = int(raw_chunk_index) if raw_chunk_index not in {None, ""} else None
    except (TypeError, ValueError):
        chunk_index = None

    locator = {
        "db_id": db_id,
        "file_id": file_id,
        "chunk_id": str(value.get("chunk_id") or "").strip(),
        "chunk_index": chunk_index,
        "keyword": str(value.get("keyword") or "").strip(),
        "query_text": str(value.get("query_text") or "").strip(),
    }
    return locator


def _normalize_technical_question_review(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    question = str(value.get("question") or "").strip()
    if not question:
        return None

    try:
        question_index = max(1, int(value.get("question_index") or 1))
    except (TypeError, ValueError):
        question_index = 1

    review = {
        "question_index": question_index,
        "question": question,
        "kb_name": str(value.get("kb_name") or "").strip(),
        "file_name": str(value.get("file_name") or "").strip(),
        "asked_at": str(value.get("asked_at") or "").strip(),
        "answered_at": str(value.get("answered_at") or "").strip(),
        "answer": str(value.get("answer") or "").strip(),
        "answer_excerpt": str(value.get("answer_excerpt") or "").strip(),
        "score": _normalize_score_value(value.get("score")),
        "level": str(value.get("level") or "").strip(),
        "matched_keywords": _normalize_string_list(value.get("matched_keywords")),
        "suggested_keywords": _normalize_string_list(value.get("suggested_keywords")),
        "strengths": _normalize_string_list(value.get("strengths")),
        "gaps": _normalize_string_list(value.get("gaps")),
        "locator": _normalize_learning_locator(value.get("locator")),
    }
    if not review["answer_excerpt"] and review["answer"]:
        review["answer_excerpt"] = _summarize_learning_excerpt(review["answer"], limit=110)
    return review


def _normalize_technical_question_reviews(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    reviews: list[dict[str, Any]] = []
    for item in value[:TECHNICAL_QUESTION_REVIEW_LIMIT]:
        normalized = _normalize_technical_question_review(item)
        if normalized:
            reviews.append(normalized)
    return reviews


def _normalize_evidence_ref(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind") or "").strip()
    if kind not in {"question_review", "dimension", "expression_metric", "coding"}:
        return None
    key = str(value.get("key") or "").strip()
    label = str(value.get("label") or "").strip()
    if not key or not label:
        return None
    return {"kind": kind, "key": key, "label": label}


def _normalize_report_highlight(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    title = str(value.get("title") or "").strip()
    summary = str(value.get("summary") or "").strip()
    tone = str(value.get("tone") or "").strip()
    dimension_key = _normalize_dimension_key(value.get("dimension_key"))
    if tone not in {"strength", "risk", "action"} or not title or not summary:
        return None
    if dimension_key and dimension_key not in DIMENSION_DISPLAY_CONFIG:
        dimension_key = ""
    try:
        priority = max(1, int(value.get("priority") or 1))
    except (TypeError, ValueError):
        priority = 1
    evidence_refs = [
        normalized
        for normalized in (_normalize_evidence_ref(item) for item in (value.get("evidence_refs") or []))
        if normalized
    ]
    if not evidence_refs:
        return None
    return {
        "title": title,
        "summary": summary,
        "tone": tone,
        "dimension_key": dimension_key,
        "priority": priority,
        "evidence_refs": evidence_refs,
    }


def _normalize_report_highlights(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    highlights: list[dict[str, Any]] = []
    for item in value[:REPORT_HIGHLIGHT_LIMIT]:
        normalized = _normalize_report_highlight(item)
        if normalized:
            highlights.append(normalized)
    highlights.sort(key=lambda item: (int(item.get("priority") or 0), str(item.get("title") or "")))
    return highlights


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
            if resource_type not in {"knowledge", "interview_question", "communication", "article", "video", "case"}:
                continue
            title = _clean_resource_text(item.get("title"))
            summary = _clean_resource_text(item.get("summary"))
            if not title or not summary:
                continue
            resource = {
                "resource_type": resource_type,
                "title": title,
                "summary": summary,
                "source_type": str(item.get("source_type") or "internal").strip() or "internal",
                "source_id": str(item.get("source_id") or "").strip(),
                "source_ref": str(item.get("source_ref") or "").strip(),
                "provider": _clean_resource_text(item.get("provider")),
                "url": str(item.get("url") or "").strip(),
                "reason": _clean_resource_text(item.get("reason")),
                "language": str(item.get("language") or "").strip(),
                "difficulty": str(item.get("difficulty") or "").strip(),
                "problem_ref": str(item.get("problem_ref") or "").strip(),
                "is_external": bool(item.get("is_external")),
            }
            try:
                estimated_minutes = int(item.get("estimated_minutes") or 0)
            except (TypeError, ValueError):
                estimated_minutes = 0
            if estimated_minutes > 0:
                resource["estimated_minutes"] = estimated_minutes
            search_score = _parse_numeric_score(item.get("search_score"))
            if search_score is not None:
                resource["search_score"] = round(search_score, 3)
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

    def normalize_action_plan(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        title = str(value.get("title") or "").strip()
        summary = str(value.get("summary") or "").strip()
        steps: list[dict[str, Any]] = []
        for item in value.get("steps") or []:
            if not isinstance(item, dict):
                continue
            step_type = str(item.get("step_type") or "").strip()
            if step_type not in {"learn", "practice", "recheck"}:
                continue
            related_dimension_key = _normalize_dimension_key(item.get("related_dimension_key"))
            if related_dimension_key and related_dimension_key not in DIMENSION_DISPLAY_CONFIG:
                related_dimension_key = ""
            title_value = str(item.get("title") or "").strip()
            objective = str(item.get("objective") or "").strip()
            success_signal = str(item.get("success_signal") or "").strip()
            if not title_value or not objective or not success_signal:
                continue
            try:
                estimated_minutes = max(5, int(item.get("estimated_minutes") or 30))
            except (TypeError, ValueError):
                estimated_minutes = 30
            resource_refs = [
                str(resource_ref).strip()
                for resource_ref in (item.get("resource_refs") or [])
                if str(resource_ref).strip()
            ]
            steps.append(
                {
                    "step_type": step_type,
                    "title": title_value,
                    "objective": objective,
                    "estimated_minutes": estimated_minutes,
                    "related_dimension_key": related_dimension_key,
                    "resource_refs": resource_refs,
                    "success_signal": success_signal,
                }
            )
        if not steps:
            return None
        return {
            "title": title or "7 天提升路径",
            "summary": summary or "先补知识，再做练习，最后通过下一轮问题验证改进效果。",
            "steps": steps,
        }

    normalized = {
        "weaknesses": normalize_weaknesses(value.get("weaknesses")),
        "recommended_resources": normalize_resources(value.get("recommended_resources")),
        "practice_tasks": normalize_practice_tasks(value.get("practice_tasks")),
        "next_assessment_focus": normalize_focus(value.get("next_assessment_focus")),
        "action_plan": normalize_action_plan(value.get("action_plan")),
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

    basic_info = value.get("基本信息") if isinstance(value.get("基本信息"), dict) else {}
    candidate_info = value.get("candidate_info") if isinstance(value.get("candidate_info"), dict) else {}
    if not candidate_info and basic_info:
        candidate_info = {
            "target_position": basic_info.get("目标岗位") or basic_info.get("岗位") or basic_info.get("应聘岗位"),
            "interview_round": basic_info.get("面试轮次") or basic_info.get("轮次"),
        }
    assessment_summary = value.get("assessment_summary") if isinstance(value.get("assessment_summary"), dict) else {}
    zh_dimensions = []
    zh_dimension_mapping = value.get("评估维度") if isinstance(value.get("评估维度"), dict) else {}
    for dimension_name, dimension_payload in zh_dimension_mapping.items():
        if not isinstance(dimension_payload, dict):
            continue
        raw_score = dimension_payload.get("分数")
        if _parse_numeric_score(raw_score) is None:
            continue
        zh_dimensions.append({"name": str(dimension_name or "").strip(), "score": raw_score})
    detailed_scores = _extract_score_mapping(value.get("detailed_scores") or value.get("rating_scores"))
    dimension_scores = _extract_score_mapping(value.get("dimension_scores"))
    dimensions_value = value.get("dimensions") or zh_dimensions
    dimensions_scale_hint = _detect_score_scale(dimensions_value)
    fallback_scale_hint = _detect_score_scale(detailed_scores or dimension_scores)
    interview_outcome = value.get("interview_outcome") if isinstance(value.get("interview_outcome"), dict) else {}
    match_assessment = value.get("match_assessment") if isinstance(value.get("match_assessment"), dict) else {}
    fallback_dimensions = _normalize_detailed_scores(detailed_scores or dimension_scores)
    fallback_overall = None
    if fallback_dimensions:
        fallback_overall = round(sum(item["score"] for item in fallback_dimensions) / len(fallback_dimensions))
    raw_overall_value = value.get(
        "overall",
        value.get("overall_score", value.get("total_score", value.get("total", value.get("综合评分")))),
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
            or basic_info.get("目标岗位")
            or ""
        ).strip(),
        "round": str(
            value.get("round")
            or value.get("interview_round")
            or candidate_info.get("interview_round")
            or basic_info.get("面试轮次")
            or ""
        ).strip(),
        "dimensions": _normalize_dimensions(dimensions_value) or fallback_dimensions,
        "strengths": _normalize_string_list(
            value.get("strengths")
            or value.get("highlights")
            or value.get("主要亮点")
            or assessment_summary.get("strengths")
            or assessment_summary.get("key_strengths")
            or match_assessment.get("strengths_for_position")
        ),
        "risks": _normalize_string_list(
            value.get("risks")
            or value.get("improvement_areas")
            or value.get("主要风险点")
            or assessment_summary.get("concerns")
            or assessment_summary.get("key_concerns")
            or match_assessment.get("concerns_for_position")
        ),
        "suggestions": _normalize_string_list(
            value.get("suggestions")
            or value.get("next_steps")
            or value.get("推荐方向")
            or interview_outcome.get("next_assessment_focus")
            or match_assessment.get("next_assessment_focus")
        ),
        "summary": str(
            value.get("summary")
            or value.get("面试官总体评价")
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
    stripped = INTERVIEW_SCORECARD_PATTERN.sub("", content)
    generic_match = GENERIC_JSON_CODE_BLOCK_PATTERN.search(stripped)
    if generic_match:
        try:
            payload = json.loads(generic_match.group(1).strip())
        except Exception:
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("interview_scorecard"), dict):
            stripped = stripped[: generic_match.start()] + stripped[generic_match.end() :]
    return stripped.strip()


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


def _parse_tool_output_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    text = str(value or "").strip()
    if not text:
        return {}

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _is_hidden_history_message(message: Any) -> bool:
    metadata = getattr(message, "extra_metadata", None)
    return bool(metadata.get("hidden_from_history")) if isinstance(metadata, dict) else False


def _is_interview_finalize_control_message(message: Any) -> bool:
    metadata = getattr(message, "extra_metadata", None)
    if (
        isinstance(metadata, dict)
        and str(metadata.get("internal_prompt_type") or "").strip() == "interview_finalize_result"
    ):
        return True

    content = str(getattr(message, "content", "") or "").strip()
    return "代码考核已经结束" in content and "完整结果已生成，可在面试结果页查看" in content


def _normalize_question_match_text(value: str) -> str:
    normalized = QUESTION_MATCH_NORMALIZE_PATTERN.sub("", str(value or "")).lower()
    return normalized.strip()


def _extract_question_keywords(question: str) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for token in QUESTION_KEYWORD_PATTERN.findall(str(question or "")):
        normalized = token.strip().lower()
        if not normalized or normalized in TECHNICAL_QUESTION_STOPWORDS:
            continue
        if normalized in ENGLISH_TECHNICAL_QUESTION_STOPWORDS:
            continue
        if any(noise_term in token for noise_term in QUESTION_KEYWORD_NOISE_TERMS):
            continue
        if "技术题" in normalized or (normalized.startswith("我们") and len(normalized) <= 8):
            continue
        if len(normalized) <= 6 and any(stopword in normalized for stopword in TECHNICAL_QUESTION_STOPWORDS):
            continue
        if normalized.isdigit() or normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(token.strip())
    return keywords[:6]


def _build_technical_answer_effect(question: str, answer: str) -> dict[str, Any]:
    keywords = _extract_question_keywords(question)
    answer_text = str(answer or "").strip()
    if not answer_text:
        return {
            "score": 0,
            "level": "未作答",
            "matched_keywords": [],
            "suggested_keywords": keywords[:3],
            "strengths": [],
            "gaps": ["未看到候选人对这道题的有效回答。"],
        }

    normalized_answer = answer_text.lower()
    matched_keywords = [keyword for keyword in keywords if keyword.lower() in normalized_answer]
    suggested_keywords = [keyword for keyword in keywords if keyword not in matched_keywords][:3]
    answer_length = len(re.sub(r"\s+", "", answer_text))
    sentence_count = max(len([item for item in SENTENCE_SPLIT_PATTERN.split(answer_text) if item.strip()]), 1)
    filler_count = _count_terms(answer_text, FILLER_TERMS)
    hedge_count = _count_terms(answer_text, HEDGE_TERMS)
    assertive_count = _count_terms(answer_text, ASSERTIVE_TERMS)

    coverage_ratio = len(matched_keywords) / len(keywords) if keywords else 0.5
    length_score = min(answer_length / 140, 1.0) * 36
    coverage_score = coverage_ratio * 34
    structure_score = 12 if 2 <= sentence_count <= 6 else 6 if sentence_count > 1 else 2
    confidence_score = 16
    confidence_score += min(assertive_count * 2.5, 8)
    confidence_score -= min(hedge_count * 3.0, 12)
    confidence_score -= min(filler_count * 2.0, 8)
    score = _clamp_score(length_score + coverage_score + structure_score + confidence_score)

    if score >= 85:
        level = "优秀"
    elif score >= 70:
        level = "良好"
    elif score >= 55:
        level = "一般"
    else:
        level = "待提升"

    strengths: list[str] = []
    gaps: list[str] = []
    if matched_keywords:
        strengths.append("回答覆盖了题目的部分关键知识点。")
    if answer_length >= 80:
        strengths.append("回答展开较充分，不是只停留在结论层。")
    if 2 <= sentence_count <= 5:
        strengths.append("回答结构相对清晰。")
    if assertive_count >= hedge_count and answer_length >= 40:
        strengths.append("表达较明确，技术判断不算过于保守。")

    if answer_length < 35:
        gaps.append("回答偏短，可补充原理、流程或边界细节。")
    if keywords and coverage_ratio < 0.4:
        gaps.append("没有充分覆盖题目的核心关键词。")
    if hedge_count > assertive_count + 1:
        gaps.append("表述偏保守，结论不够明确。")
    if sentence_count <= 1 and answer_length >= 35:
        gaps.append("回答结构较松散，建议先给结论再展开。")

    if not strengths and answer_length >= 45:
        strengths.append("能围绕题目持续作答，具备基本展开能力。")
    if not gaps and score < 85:
        gaps.append("可以继续补充更具体的实现细节或实际场景。")

    return {
        "score": score,
        "level": level,
        "matched_keywords": matched_keywords,
        "suggested_keywords": suggested_keywords,
        "strengths": strengths[:3],
        "gaps": gaps[:3],
    }


def _find_question_delivery_message(
    messages: list[Any],
    *,
    start_index: int,
    question: str,
) -> tuple[int, Any | None]:
    normalized_question = _normalize_question_match_text(question)
    current_message = messages[start_index] if 0 <= start_index < len(messages) else None
    current_content = str(getattr(current_message, "content", "") or "").strip() if current_message else ""
    if (
        current_content
        and normalized_question
        and normalized_question in _normalize_question_match_text(current_content)
    ):
        return start_index, current_message

    fallback_index = start_index
    fallback_message = current_message
    for index in range(start_index + 1, len(messages)):
        message = messages[index]
        if _is_hidden_history_message(message):
            continue

        role = str(getattr(message, "role", "") or "").strip()
        if role == "user":
            break
        if role != "assistant":
            continue

        content = str(getattr(message, "content", "") or "").strip()
        if not content:
            continue
        if fallback_message is None or fallback_message is current_message:
            fallback_index = index
            fallback_message = message
        if normalized_question and normalized_question in _normalize_question_match_text(content):
            return index, message

    return fallback_index, fallback_message


def _collect_answer_messages(messages: list[Any], *, question_index: int) -> list[Any]:
    answers: list[Any] = []
    for index in range(question_index + 1, len(messages)):
        message = messages[index]
        if _is_interview_finalize_control_message(message):
            break
        if _is_hidden_history_message(message):
            continue

        role = str(getattr(message, "role", "") or "").strip()
        if role == "assistant":
            if answers:
                break
            continue
        if role != "user":
            continue

        content = str(getattr(message, "content", "") or "").strip()
        if content:
            answers.append(message)
    return answers


def _question_was_interrupted_by_finalize_control(messages: list[Any], *, question_index: int) -> bool:
    for index in range(question_index + 1, len(messages)):
        message = messages[index]
        if _is_interview_finalize_control_message(message):
            return True
        if _is_hidden_history_message(message):
            continue

        role = str(getattr(message, "role", "") or "").strip()
        if role in {"user", "assistant"}:
            return False

    return False


def _collect_technical_question_reviews(messages: list[Any] | None) -> list[dict[str, Any]]:
    ordered_messages = list(messages or [])
    reviews: list[dict[str, Any]] = []

    for index, message in enumerate(ordered_messages):
        if _is_hidden_history_message(message):
            continue
        if str(getattr(message, "role", "") or "").strip() != "assistant":
            continue

        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            if str(getattr(tool_call, "tool_name", "") or "").strip() != "pick_random_technical_question":
                continue
            if str(getattr(tool_call, "status", "") or "").strip() != "success":
                continue

            payload = _parse_tool_output_payload(getattr(tool_call, "tool_output", ""))
            question = str(payload.get("question") or "").strip()
            if not question:
                continue

            asked_index, asked_message = _find_question_delivery_message(
                ordered_messages,
                start_index=index,
                question=question,
            )
            answer_messages = _collect_answer_messages(ordered_messages, question_index=asked_index)
            answer_text = "\n".join(
                str(getattr(answer_message, "content", "") or "").strip()
                for answer_message in answer_messages
                if str(getattr(answer_message, "content", "") or "").strip()
            ).strip()
            if not answer_text and _question_was_interrupted_by_finalize_control(
                ordered_messages, question_index=asked_index
            ):
                continue
            effect = _build_technical_answer_effect(question, answer_text)
            locator = _normalize_learning_locator(
                {
                    "db_id": payload.get("db_id"),
                    "file_id": payload.get("file_id"),
                    "chunk_id": payload.get("chunk_id"),
                    "chunk_index": payload.get("chunk_index"),
                    "keyword": (effect.get("suggested_keywords") or effect.get("matched_keywords") or [""])[0],
                    "query_text": question,
                }
            )

            reviews.append(
                {
                    "question_index": len(reviews) + 1,
                    "question": question,
                    "kb_name": str(payload.get("kb_name") or "").strip(),
                    "file_name": str(payload.get("file_name") or "").strip(),
                    "asked_at": format_utc_datetime(getattr(asked_message, "created_at", None)),
                    "answered_at": format_utc_datetime(getattr(answer_messages[-1], "created_at", None))
                    if answer_messages
                    else "",
                    "answer": answer_text,
                    "answer_excerpt": _summarize_learning_excerpt(answer_text, limit=110) if answer_text else "",
                    "score": effect["score"],
                    "level": effect["level"],
                    "matched_keywords": effect["matched_keywords"],
                    "suggested_keywords": effect["suggested_keywords"],
                    "strengths": effect["strengths"],
                    "gaps": effect["gaps"],
                    "locator": locator,
                }
            )

    return reviews[:TECHNICAL_QUESTION_REVIEW_LIMIT]


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
    if match:
        try:
            return _normalize_scorecard(json.loads(match.group(1).strip()))
        except Exception:
            return None

    for generic_match in GENERIC_JSON_CODE_BLOCK_PATTERN.finditer(content):
        try:
            payload = json.loads(generic_match.group(1).strip())
        except Exception:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("interview_scorecard"), dict):
            return _normalize_scorecard(payload.get("interview_scorecard"))
    return None


def _parse_thread_context(title: str | None) -> tuple[str, str]:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        return "", ""

    for pattern in THREAD_CONTEXT_SPLIT_PATTERNS:
        parts = pattern.split(normalized_title, maxsplit=1)
        if len(parts) != 2:
            continue
        left, right = (part.strip() for part in parts)
        if left and right:
            return left, right

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
        "report_highlights": None,
        "improvement_plan": None,
        "technical_question_reviews": None,
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
        role_position, role_round = _parse_thread_context(scorecard.get("role"))
        if role_round:
            scorecard["role"] = role_position
            scorecard["round"] = scorecard.get("round") or role_round
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
        "report_highlights": _normalize_report_highlights(value.get("report_highlights")),
        "improvement_plan": _normalize_improvement_plan(value.get("improvement_plan")),
        "technical_question_reviews": _normalize_technical_question_reviews(value.get("technical_question_reviews")),
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
    normalized = score if score is not None else 101
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
                        "title": _clean_resource_text(f"{database.get('name') or '知识库'} · 精准学习"),
                        "summary": _summarize_learning_excerpt(str(result.get("content") or "").strip()),
                        "source_type": "knowledge_chunk",
                        "source_id": db_id,
                        "source_ref": ref,
                        "locator": {
                            "db_id": db_id,
                            "file_id": file_id,
                            "chunk_id": chunk_id,
                            "chunk_index": normalized_chunk_index,
                            "keyword": _clean_resource_text(matched_keyword),
                            "query_text": _clean_resource_text(candidate),
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
    normalized_position_tag = str(get_problemset_tag_for_position(target_position) or "").strip().lower()
    normalized_difficulty = str(difficulty_level or "").strip().lower()

    ranked: list[dict[str, Any]] = []
    for item in problems:
        title = _clean_resource_text(item.get("title"))
        summary = _clean_resource_text(item.get("summary"))
        topic_tags = [str(tag).strip().lower() for tag in (item.get("topic_tags") or []) if str(tag).strip()]
        position_tag = str(item.get("primary_position_tag") or "").strip().lower()
        difficulty_tag = str(item.get("difficulty_tag") or "").strip().lower()
        score = 0
        if normalized_position_tag and position_tag == normalized_position_tag:
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
                "problem_ref": _build_practice_problem_ref(
                    str(item.get("package_path") or "").strip(),
                    int(item.get("problem_index") or 0),
                ),
            }
        )
    return selected


def _collect_low_score_review_keywords(reviews: list[dict[str, Any]] | None) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for review in sorted(list(reviews or []), key=lambda item: int(item.get("score") or 0)):
        score = _normalize_score_value(review.get("score"))
        if score is None or score > TECHNICAL_QUESTION_LOW_SCORE_THRESHOLD:
            continue
        raw_keywords = [
            *list(review.get("suggested_keywords") or []),
            *list(review.get("matched_keywords") or []),
            *_extract_question_keywords(str(review.get("question") or "")),
        ]
        for keyword in raw_keywords:
            normalized = str(keyword or "").strip()
            if not normalized:
                continue
            lower = normalized.lower()
            if lower in seen:
                continue
            seen.add(lower)
            keywords.append(normalized)
        if len(keywords) >= 6:
            break
    return keywords[:6]


async def _search_external_learning_resources(
    *,
    target_position: str,
    dimension_key: str,
    weakness_reason: str,
    technical_question_reviews: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    searcher = _create_web_searcher()
    if searcher is None:
        return []

    dimension_label = DIMENSION_DISPLAY_CONFIG[dimension_key]["label"]
    review_keywords = _collect_low_score_review_keywords(technical_question_reviews)
    keyword_text = " ".join(review_keywords[:3])
    query_specs = [
        ("article", f"{target_position} {dimension_label} {weakness_reason} {keyword_text} 官方文档 教程 博客"),
        ("video", f"{target_position} {dimension_label} {weakness_reason} {keyword_text} 视频 讲解 实战"),
        ("case", f"{target_position} {dimension_label} {weakness_reason} {keyword_text} 案例 实战 复盘"),
    ]

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for expected_type, query in query_specs:
        try:
            rows = await asyncio.to_thread(searcher.search, query, 8, "advanced")
        except Exception as exc:
            logger.warning("External resource search failed for query %s: %s", query, exc)
            continue
        for row in rows:
            url = str(row.get("url") or "").strip()
            if not url or url in seen_urls or not _is_allowed_external_resource_url(url):
                continue
            score = float(row.get("score") or 0)
            if score < EXTERNAL_RESOURCE_MIN_SCORE:
                continue
            title = _clean_resource_text(row.get("title"))
            content = _clean_resource_text(row.get("content"))
            actual_type = _infer_external_resource_type(title=title, content=content, url=url)
            if actual_type != expected_type:
                continue
            seen_urls.add(url)
            candidates.append(
                {
                    "resource_type": actual_type,
                    "title": title or "外部学习资源",
                    "content": content,
                    "url": url,
                    "score": score,
                }
            )

    candidates.sort(key=lambda item: float(item.get("score") or 0), reverse=True)

    resources: list[dict[str, Any]] = []
    per_type_counts: dict[str, int] = {}
    focus_keyword = review_keywords[0] if review_keywords else dimension_label
    for candidate in candidates:
        resource_type = str(candidate.get("resource_type") or "").strip()
        if per_type_counts.get(resource_type, 0) >= EXTERNAL_RESOURCE_PER_TYPE_LIMIT:
            continue
        url = str(candidate.get("url") or "").strip()
        title = str(candidate.get("title") or "").strip()
        content = str(candidate.get("content") or "").strip()
        provider = _extract_provider_from_url(url)
        resources.append(
            {
                "resource_type": resource_type,
                "title": title or "外部学习资源",
                "summary": _summarize_learning_excerpt(content, limit=120),
                "source_type": "web_search",
                "source_id": provider,
                "source_ref": f"web-search://{provider}/{len(resources) + 1}",
                "provider": provider,
                "url": url,
                "reason": _build_external_resource_reason(
                    dimension_label=dimension_label,
                    focus_keyword=focus_keyword,
                    weakness_reason=weakness_reason,
                    resource_title=title,
                    resource_content=content,
                    resource_type=resource_type,
                ),
                "estimated_minutes": _default_external_resource_minutes(resource_type),
                "language": _infer_external_resource_language(title=title, content=content),
                "difficulty": _default_external_resource_difficulty(resource_type),
                "is_external": True,
                "search_score": round(float(candidate.get("score") or 0), 3),
            }
        )
        per_type_counts[resource_type] = per_type_counts.get(resource_type, 0) + 1
        if len(resources) >= EXTERNAL_RESOURCE_LIMIT:
            break
    return resources[:EXTERNAL_RESOURCE_LIMIT]


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


def _build_action_plan(
    *,
    weaknesses: list[dict[str, Any]],
    recommended_resources: list[dict[str, Any]],
    practice_tasks: list[dict[str, Any]],
    next_focus: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not weaknesses and not practice_tasks and not next_focus:
        return None

    primary_weakness = weaknesses[0] if weaknesses else {}
    learn_resources = [
        item
        for item in recommended_resources
        if str(item.get("resource_type") or "").strip() in {"knowledge", "article", "video", "case", "communication"}
    ]
    practice_resources = [
        item for item in recommended_resources if str(item.get("resource_type") or "").strip() == "interview_question"
    ]

    steps: list[dict[str, Any]] = []

    if primary_weakness:
        related_dimension_key = str(primary_weakness.get("dimension_key") or "").strip()
        primary_resource_refs = [
            str(item.get("source_ref") or "").strip()
            for item in learn_resources[:2]
            if str(item.get("source_ref") or "").strip()
        ]
        primary_minutes = next(
            (
                int(item.get("estimated_minutes") or 0)
                for item in learn_resources
                if int(item.get("estimated_minutes") or 0) > 0
            ),
            25,
        )
        steps.append(
            {
                "step_type": "learn",
                "title": f"先补 {str(primary_weakness.get('title') or '核心短板').strip()}",
                "objective": str(primary_weakness.get("reason") or "先把核心概念和答题框架补齐。").strip(),
                "estimated_minutes": max(10, primary_minutes),
                "related_dimension_key": related_dimension_key,
                "resource_refs": primary_resource_refs,
                "success_signal": (
                    "能独立说明 "
                    f"{DIMENSION_DISPLAY_CONFIG.get(related_dimension_key, {}).get('label', '关键能力')}"
                    " 的核心概念与常见场景。"
                ),
            }
        )

    practice_task = practice_tasks[0] if practice_tasks else {}
    if practice_task:
        related_dimension_key = str(
            (weaknesses[1] if len(weaknesses) > 1 else primary_weakness).get("dimension_key") or ""
        ).strip()
        practice_refs = [
            str(item.get("source_ref") or "").strip()
            for item in practice_resources[:1]
            if str(item.get("source_ref") or "").strip()
        ]
        steps.append(
            {
                "step_type": "practice",
                "title": str(practice_task.get("title") or "做一次定向练习").strip(),
                "objective": str(practice_task.get("objective") or "把分析结果落实到实际练习里。").strip(),
                "estimated_minutes": max(10, int(practice_task.get("estimated_minutes") or 30)),
                "related_dimension_key": related_dimension_key,
                "resource_refs": practice_refs,
                "success_signal": "能在练习中稳定复现正确思路，而不是只会背结论。",
            }
        )

    focus_item = next_focus[0] if next_focus else {}
    if focus_item:
        related_dimension_key = str(focus_item.get("dimension_key") or "").strip()
        steps.append(
            {
                "step_type": "recheck",
                "title": str(focus_item.get("title") or "安排下一轮回测").strip(),
                "objective": str(focus_item.get("focus") or "用下一轮面试验证是否真正提升。").strip(),
                "estimated_minutes": 15,
                "related_dimension_key": related_dimension_key,
                "resource_refs": [],
                "success_signal": str(focus_item.get("focus") or "下次同类问题不再卡顿。").strip(),
            }
        )

    if not steps:
        return None

    return {
        "title": "7 天提升路径",
        "summary": "先补知识，再做定向练习，最后通过下一轮问题验证改进效果。",
        "steps": steps[:3],
    }


def _improvement_plan_needs_refresh(value: Any, scorecard: dict[str, Any] | None) -> bool:
    plan = _normalize_improvement_plan(value)
    if not plan or not isinstance(scorecard, dict):
        return False

    dimension_scores = _extract_dimension_scores(scorecard)

    def refers_missing_dimension(dimension_key: Any) -> bool:
        normalized_key = str(dimension_key or "").strip()
        return bool(normalized_key) and dimension_scores.get(normalized_key) is None

    if any(refers_missing_dimension(item.get("dimension_key")) for item in plan.get("weaknesses") or []):
        return True
    if any(refers_missing_dimension(item.get("dimension_key")) for item in plan.get("next_assessment_focus") or []):
        return True

    action_plan = plan.get("action_plan") or {}
    steps = action_plan.get("steps") or []
    return any(refers_missing_dimension(step.get("related_dimension_key")) for step in steps)


def _build_report_highlights(
    *,
    scorecard: dict[str, Any] | None,
    technical_question_reviews: list[dict[str, Any]] | None,
    expression_analysis: dict[str, Any] | None,
    coding_session: dict[str, Any] | None,
    improvement_plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    highlights: list[dict[str, Any]] = []
    dimension_scores = _extract_dimension_scores(scorecard)
    ordered_dimensions = sorted(dimension_scores.items(), key=_dimension_sort_key)
    lowest_dimension_key, lowest_dimension_score = ordered_dimensions[0] if ordered_dimensions else ("", None)
    highest_dimension_key, highest_dimension_score = (
        sorted(ordered_dimensions, key=lambda item: item[1] if item[1] is not None else -1, reverse=True)[0]
        if ordered_dimensions
        else ("", None)
    )

    reviews = list(technical_question_reviews or [])
    low_review = min(reviews, key=lambda item: _normalize_score_value(item.get("score")) or 999, default=None)
    strong_review = max(reviews, key=lambda item: _normalize_score_value(item.get("score")) or -1, default=None)

    if low_review and (_normalize_score_value(low_review.get("score")) or 0) <= TECHNICAL_QUESTION_LOW_SCORE_THRESHOLD:
        focus_text = (
            list(low_review.get("suggested_keywords") or [])
            or _extract_question_keywords(str(low_review.get("question") or ""))
            or ["当前技术题"]
        )[0]
        highlights.append(
            {
                "title": "最低分技术题暴露出关键短板",
                "summary": (
                    f"最低分技术题直接暴露出“{focus_text}”相关答题深度不足，建议优先补齐核心概念和表达结构。"
                    if focus_text and focus_text != "当前技术题"
                    else "最低分技术题直接暴露出这里的答题深度不足，建议优先补齐核心概念和表达结构。"
                ),
                "tone": "risk",
                "dimension_key": "technical_competence",
                "priority": 1,
                "evidence_refs": [
                    {
                        "kind": "question_review",
                        "key": f"question_review:{int(low_review.get('question_index') or 1)}",
                        "label": (
                            f"技术题 {int(low_review.get('question_index') or 1)}"
                            f" · {int(low_review.get('score') or 0)} 分"
                        ),
                    },
                    {
                        "kind": "dimension",
                        "key": "technical_competence",
                        "label": (
                            f"技术能力 · {lowest_dimension_score if lowest_dimension_score is not None else '--'} 分"
                        ),
                    },
                ],
            }
        )
    elif lowest_dimension_key:
        highlights.append(
            {
                "title": f"{DIMENSION_DISPLAY_CONFIG[lowest_dimension_key]['label']} 需要优先补强",
                "summary": (
                    f"当前最弱维度是{DIMENSION_DISPLAY_CONFIG[lowest_dimension_key]['label']}，优先补这里最划算。"
                ),
                "tone": "risk",
                "dimension_key": lowest_dimension_key,
                "priority": 1,
                "evidence_refs": [
                    {
                        "kind": "dimension",
                        "key": lowest_dimension_key,
                        "label": (
                            f"{DIMENSION_DISPLAY_CONFIG[lowest_dimension_key]['label']}"
                            f" · {lowest_dimension_score if lowest_dimension_score is not None else '--'} 分"
                        ),
                    }
                ],
            }
        )

    if strong_review and (_normalize_score_value(strong_review.get("score")) or 0) >= 80:
        evidence_ref = {
            "kind": "question_review",
            "key": f"question_review:{int(strong_review.get('question_index') or 1)}",
            "label": (
                f"技术题 {int(strong_review.get('question_index') or 1)} · {int(strong_review.get('score') or 0)} 分"
            ),
        }
        summary = list(strong_review.get("strengths") or ["这部分回答已经具备不错的完整度和稳定性。"])[0]
        highlights.append(
            {
                "title": "有一项能力已经值得保留",
                "summary": summary,
                "tone": "strength",
                "dimension_key": "technical_competence",
                "priority": 2,
                "evidence_refs": [evidence_ref],
            }
        )
    elif highest_dimension_key:
        label = DIMENSION_DISPLAY_CONFIG[highest_dimension_key]["label"]
        strength_summary = list((scorecard or {}).get("strengths") or [f"{label}是这轮表现相对稳定的一项。"])[0]
        highlights.append(
            {
                "title": f"{label} 是这轮最值得保持的优势",
                "summary": strength_summary,
                "tone": "strength",
                "dimension_key": highest_dimension_key,
                "priority": 2,
                "evidence_refs": [
                    {
                        "kind": "dimension",
                        "key": highest_dimension_key,
                        "label": (
                            f"{label} · {highest_dimension_score if highest_dimension_score is not None else '--'} 分"
                        ),
                    }
                ],
            }
        )

    action_steps = ((improvement_plan or {}).get("action_plan") or {}).get("steps") or []
    first_action = action_steps[0] if action_steps else {}
    if first_action:
        related_dimension_key = str(first_action.get("related_dimension_key") or lowest_dimension_key or "").strip()
        evidence_refs = []
        if low_review:
            evidence_refs.append(
                {
                    "kind": "question_review",
                    "key": f"question_review:{int(low_review.get('question_index') or 1)}",
                    "label": (
                        f"技术题 {int(low_review.get('question_index') or 1)} · {int(low_review.get('score') or 0)} 分"
                    ),
                }
            )
        elif related_dimension_key:
            evidence_refs.append(
                {
                    "kind": "dimension",
                    "key": related_dimension_key,
                    "label": (
                        f"{DIMENSION_DISPLAY_CONFIG.get(related_dimension_key, {}).get('label', '关键维度')}"
                        f" · {dimension_scores.get(related_dimension_key) if related_dimension_key else '--'} 分"
                    ),
                }
            )
        highlights.append(
            {
                "title": str(first_action.get("title") or "先做最关键的动作").strip(),
                "summary": str(first_action.get("objective") or "先做最能带来提升的一步。").strip(),
                "tone": "action",
                "dimension_key": related_dimension_key,
                "priority": 3,
                "evidence_refs": evidence_refs
                or [
                    {
                        "kind": "coding",
                        "key": "coding",
                        "label": "代码考核摘要",
                    }
                ],
            }
        )

    return _normalize_report_highlights(highlights)


async def _generate_improvement_plan(
    *,
    conversation,
    scorecard: dict[str, Any] | None,
    expression_analysis: dict[str, Any] | None,
    coding_session: dict[str, Any] | None,
    technical_question_reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(scorecard, dict):
        return None

    dimension_scores = _extract_dimension_scores(scorecard)
    ordered_scores = sorted(dimension_scores.items(), key=_dimension_sort_key)
    weakness_candidates: list[tuple[str, int | None]] = []
    for dimension_key, score in ordered_scores:
        if score is not None and score <= LOW_SCORE_THRESHOLD:
            weakness_candidates.append((dimension_key, score))
    if not weakness_candidates:
        weakness_candidates = [item for item in ordered_scores if item[1] is not None][:2]

    weaknesses: list[dict[str, str]] = []
    recommended_resources: list[dict[str, str]] = []
    practice_tasks: list[dict[str, Any]] = []
    next_focus: list[dict[str, str]] = []
    seen_resource_refs: set[str] = set()
    external_resource_count = 0

    target_position = str(
        (coding_session or {}).get("target_position")
        or (scorecard or {}).get("role")
        or (conversation.extra_metadata or {}).get("target_position")
        or ""
    ).strip()
    difficulty_level = str((coding_session or {}).get("difficulty_level") or "").strip()
    low_score_review_keywords = _collect_low_score_review_keywords(technical_question_reviews)
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
                keywords=[*dimension_keywords[dimension_key], *low_score_review_keywords],
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

        if external_resource_count < EXTERNAL_RESOURCE_LIMIT:
            external_resources = await _search_external_learning_resources(
                target_position=target_position or str((scorecard or {}).get("role") or "").strip(),
                dimension_key=dimension_key,
                weakness_reason=reason,
                technical_question_reviews=technical_question_reviews,
            )
            for resource in external_resources:
                ref = str(resource.get("source_ref") or "").strip()
                url = str(resource.get("url") or "").strip()
                if (ref and ref in seen_resource_refs) or any(
                    url == str(existing.get("url") or "").strip() for existing in recommended_resources if url
                ):
                    continue
                if ref:
                    seen_resource_refs.add(ref)
                recommended_resources.append(resource)
                external_resource_count += 1
                if external_resource_count >= EXTERNAL_RESOURCE_LIMIT:
                    break

    action_plan = _build_action_plan(
        weaknesses=weaknesses[:WEAKNESS_LIMIT],
        recommended_resources=recommended_resources,
        practice_tasks=practice_tasks[:PRACTICE_LIMIT],
        next_focus=next_focus[:WEAKNESS_LIMIT],
    )
    return {
        "weaknesses": weaknesses[:WEAKNESS_LIMIT],
        "recommended_resources": recommended_resources[: RESOURCE_LIMIT + EXTERNAL_RESOURCE_LIMIT],
        "practice_tasks": practice_tasks[:PRACTICE_LIMIT],
        "next_assessment_focus": next_focus[:WEAKNESS_LIMIT],
        "action_plan": action_plan,
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
    should_persist = False
    reviews_changed = False
    expression_analysis = _normalize_expression_analysis(enriched.get("expression_analysis")) or (
        _build_expression_analysis(
            conversation=conversation,
            scorecard=enriched.get("scorecard"),
            messages=messages,
        )
    )
    if expression_analysis:
        enriched["expression_analysis"] = expression_analysis

    if enriched.get("status") == "completed":
        existing_reviews = _normalize_technical_question_reviews(enriched.get("technical_question_reviews"))
        rebuilt_reviews = _collect_technical_question_reviews(messages)
        reviews_changed = rebuilt_reviews != existing_reviews
        if reviews_changed:
            enriched["technical_question_reviews"] = rebuilt_reviews
            should_persist = True

    plan_needs_refresh = _improvement_plan_needs_refresh(enriched.get("improvement_plan"), enriched.get("scorecard"))
    if enriched.get("status") == "completed" and (
        not _normalize_improvement_plan(enriched.get("improvement_plan"))
        or (persist_if_missing and (reviews_changed or plan_needs_refresh))
    ):
        improvement_plan = await _generate_improvement_plan(
            conversation=conversation,
            scorecard=enriched.get("scorecard"),
            expression_analysis=expression_analysis,
            coding_session=coding_session,
            technical_question_reviews=_normalize_technical_question_reviews(
                enriched.get("technical_question_reviews")
            ),
        )
        if improvement_plan:
            enriched["improvement_plan"] = improvement_plan
            should_persist = True

    if enriched.get("status") == "completed":
        existing_highlights = _normalize_report_highlights(enriched.get("report_highlights"))
        report_highlights = _build_report_highlights(
            scorecard=enriched.get("scorecard"),
            technical_question_reviews=_normalize_technical_question_reviews(
                enriched.get("technical_question_reviews")
            ),
            expression_analysis=expression_analysis,
            coding_session=coding_session,
            improvement_plan=_normalize_improvement_plan(enriched.get("improvement_plan")),
        )
        if report_highlights != existing_highlights:
            enriched["report_highlights"] = report_highlights
            should_persist = True

    if persist_if_missing and should_persist:
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

    ranked_dimensions = [
        {
            "dimension_key": key,
            "label": DIMENSION_DISPLAY_CONFIG[key]["label"],
            "average_score": round(sum(scores) / len(scores)),
            "low_score_count": low_score_counts[key],
        }
        for key, scores in dimension_buckets.items()
        if scores
    ]
    weakness_candidates = [
        item
        for item in ranked_dimensions
        if item["average_score"] <= LOW_SCORE_THRESHOLD or item["low_score_count"] >= 2
    ]
    top_weakness_dimensions = sorted(
        weakness_candidates or ranked_dimensions,
        key=lambda item: (item["average_score"], -item["low_score_count"]),
    )[:3]
    weakness_dimension_keys = {
        str(item.get("dimension_key") or "").strip() for item in top_weakness_dimensions if item.get("dimension_key")
    }
    top_strength_dimensions = [
        item
        for item in sorted(
            ranked_dimensions,
            key=lambda item: (-item["average_score"], item["low_score_count"]),
        )
        if str(item.get("dimension_key") or "").strip() not in weakness_dimension_keys
    ][:3]

    latest_record = completed_records[0] if completed_records else {}
    latest_plan = latest_record.get("improvement_plan") if isinstance(latest_record, dict) else {}

    return {
        "top_weakness_dimensions": top_weakness_dimensions,
        "top_strength_dimensions": top_strength_dimensions,
        "latest_focus": list((latest_plan or {}).get("next_assessment_focus") or []),
        "pending_practice_count": len((latest_plan or {}).get("practice_tasks") or []),
    }


def _build_empty_personalized_path() -> dict[str, Any]:
    return {
        "summary": {
            "stage_label": "待生成",
            "top_priority_dimension": "",
            "top_priority_label": "",
            "message": "完成更多模拟面试后，会在这里生成长期提升路径。",
        },
        "weaknesses": [],
        "recommended_resources": [],
        "practice_tasks": [],
        "next_assessment_focus": [],
        "action_plan": None,
        "strengths": [],
        "source_round_count": 0,
        "latest_updated_at": "",
        "related_records": [],
    }


def _build_personalized_path(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed_records = [
        item
        for item in records
        if item.get("has_result") and item.get("status") == "completed" and item.get("improvement_plan")
    ][:HISTORY_PROFILE_WINDOW]
    if not completed_records:
        return _build_empty_personalized_path()

    profile = _build_history_profile(completed_records)
    dimension_profile_map = {
        str(item.get("dimension_key") or "").strip(): item for item in profile.get("top_weakness_dimensions") or []
    }
    recent_reasons: dict[str, str] = {}
    weakness_counts: dict[str, int] = {}

    resource_buckets: dict[str, dict[str, Any]] = {}
    strength_buckets: dict[str, dict[str, Any]] = {}
    practice_buckets: dict[str, dict[str, Any]] = {}
    focus_buckets: dict[str, dict[str, Any]] = {}

    for index, record in enumerate(completed_records):
        plan = record.get("improvement_plan") or {}
        for weakness in plan.get("weaknesses") or []:
            dimension_key = _normalize_dimension_key(weakness.get("dimension_key"))
            if dimension_key not in DIMENSION_DISPLAY_CONFIG:
                continue
            weakness_counts[dimension_key] = weakness_counts.get(dimension_key, 0) + 1
            if dimension_key not in recent_reasons:
                recent_reasons[dimension_key] = str(weakness.get("reason") or "").strip()

        for resource in plan.get("recommended_resources") or []:
            bucket_key = (
                str(resource.get("source_ref") or "").strip()
                or str(resource.get("url") or "").strip()
                or f"{str(resource.get('resource_type') or '').strip()}::{str(resource.get('title') or '').strip()}"
            )
            if not bucket_key:
                continue
            bucket = resource_buckets.setdefault(bucket_key, {"count": 0, "latest_index": index, "item": resource})
            bucket["count"] += 1
            if index <= int(bucket.get("latest_index") or index):
                bucket["latest_index"] = index
                bucket["item"] = resource

        for strength in record.get("strengths") or []:
            normalized_strength = _clean_resource_text(strength)
            if not normalized_strength:
                continue
            bucket = strength_buckets.setdefault(
                normalized_strength,
                {"count": 0, "latest_index": index, "text": normalized_strength},
            )
            bucket["count"] += 1
            if index <= int(bucket.get("latest_index") or index):
                bucket["latest_index"] = index
                bucket["text"] = normalized_strength

        for task in plan.get("practice_tasks") or []:
            bucket_key = str(task.get("title") or "").strip()
            if not bucket_key:
                continue
            bucket = practice_buckets.setdefault(bucket_key, {"count": 0, "latest_index": index, "item": task})
            bucket["count"] += 1
            if index <= int(bucket.get("latest_index") or index):
                bucket["latest_index"] = index
                bucket["item"] = task

        for focus in plan.get("next_assessment_focus") or []:
            dimension_key = _normalize_dimension_key(focus.get("dimension_key"))
            title = str(focus.get("title") or "").strip()
            bucket_key = f"{dimension_key}::{title}"
            if not dimension_key or not title:
                continue
            bucket = focus_buckets.setdefault(bucket_key, {"count": 0, "latest_index": index, "item": focus})
            bucket["count"] += 1
            if index <= int(bucket.get("latest_index") or index):
                bucket["latest_index"] = index
                bucket["item"] = focus

    weaknesses: list[dict[str, Any]] = []
    for item in profile.get("top_weakness_dimensions") or []:
        dimension_key = str(item.get("dimension_key") or "").strip()
        if dimension_key not in DIMENSION_DISPLAY_CONFIG:
            continue
        average_score = _normalize_score_value(item.get("average_score")) or 0
        low_score_count = int(item.get("low_score_count") or 0)
        reason = recent_reasons.get(dimension_key) or (
            f"最近 {len(completed_records)} 次已完成面试中，"
            f"该维度平均 {average_score} 分，低分出现 {low_score_count} 次，"
            "建议优先持续补强。"
        )
        weaknesses.append(
            {
                "dimension_key": dimension_key,
                "title": DIMENSION_DISPLAY_CONFIG[dimension_key]["weakness_title"],
                "reason": reason,
            }
        )
    weaknesses = weaknesses[:WEAKNESS_LIMIT]

    if not weaknesses:
        fallback_dimension_key = next(iter(DIMENSION_DISPLAY_CONFIG))
        weaknesses.append(
            {
                "dimension_key": fallback_dimension_key,
                "title": DIMENSION_DISPLAY_CONFIG[fallback_dimension_key]["weakness_title"],
                "reason": "建议继续通过更多模拟面试积累稳定证据后再聚焦长期短板。",
            }
        )

    recommended_resources = [
        dict(item["item"])
        for item in sorted(
            resource_buckets.values(),
            key=lambda bucket: (
                -int(
                    bool(
                        (bucket.get("item") or {}).get("is_external")
                        and str((bucket.get("item") or {}).get("url") or "").strip()
                    )
                ),
                -int(bool(str((bucket.get("item") or {}).get("problem_ref") or "").strip())),
                -int(bool((bucket.get("item") or {}).get("locator"))),
                -int(bucket.get("count") or 0),
                int(bucket.get("latest_index") or 0),
            ),
        )[: RESOURCE_LIMIT + EXTERNAL_RESOURCE_LIMIT]
    ]
    external_resources = [
        item for item in recommended_resources if item.get("is_external") and str(item.get("url") or "").strip()
    ]
    if len(external_resources) < 2:
        extra_external = [
            dict(item["item"])
            for item in sorted(
                resource_buckets.values(),
                key=lambda bucket: (-int(bucket.get("count") or 0), int(bucket.get("latest_index") or 0)),
            )
            if (bucket_item := dict(item["item"])).get("is_external") and str(bucket_item.get("url") or "").strip()
        ]
        seen_refs = {
            str(item.get("source_ref") or "").strip() or str(item.get("url") or "").strip()
            for item in recommended_resources
        }
        for resource in extra_external:
            resource_key = str(resource.get("source_ref") or "").strip() or str(resource.get("url") or "").strip()
            if not resource_key or resource_key in seen_refs:
                continue
            recommended_resources.append(resource)
            seen_refs.add(resource_key)
            external_resources.append(resource)
            if len(external_resources) >= 2:
                break
    recommended_resources = recommended_resources[: RESOURCE_LIMIT + EXTERNAL_RESOURCE_LIMIT]
    practice_tasks = [
        dict(item["item"])
        for item in sorted(
            practice_buckets.values(),
            key=lambda bucket: (-int(bucket.get("count") or 0), int(bucket.get("latest_index") or 0)),
        )[:PRACTICE_LIMIT]
    ]
    next_focus = [
        dict(item["item"])
        for item in sorted(
            focus_buckets.values(),
            key=lambda bucket: (-int(bucket.get("count") or 0), int(bucket.get("latest_index") or 0)),
        )[:WEAKNESS_LIMIT]
    ]

    if not practice_tasks:
        practice_tasks = [
            _build_practice_task(item["dimension_key"], item["reason"])
            for item in weaknesses[:PRACTICE_LIMIT]
            if item.get("dimension_key") in DIMENSION_DISPLAY_CONFIG
        ]

    if not next_focus:
        next_focus = [
            _build_next_focus(
                item["dimension_key"],
                (dimension_profile_map.get(item["dimension_key"]) or {}).get("average_score"),
            )
            for item in weaknesses[:WEAKNESS_LIMIT]
            if item.get("dimension_key") in DIMENSION_DISPLAY_CONFIG
        ]

    strengths = [
        str(item.get("text") or "").strip()
        for item in sorted(
            strength_buckets.values(),
            key=lambda bucket: (-int(bucket.get("count") or 0), int(bucket.get("latest_index") or 0)),
        )[:3]
        if str(item.get("text") or "").strip()
    ]

    action_plan = _build_action_plan(
        weaknesses=weaknesses,
        recommended_resources=recommended_resources,
        practice_tasks=practice_tasks,
        next_focus=next_focus,
    )

    primary_dimension_key = str(weaknesses[0].get("dimension_key") or "").strip() if weaknesses else ""
    primary_label = DIMENSION_DISPLAY_CONFIG.get(primary_dimension_key, {}).get("label", "")
    primary_dimension_profile = dimension_profile_map.get(primary_dimension_key) or {}
    average_score = _normalize_score_value(primary_dimension_profile.get("average_score")) or 0
    low_score_count = int(
        primary_dimension_profile.get("low_score_count") or weakness_counts.get(primary_dimension_key) or 0
    )
    if low_score_count >= 3 or average_score < 65:
        stage_label = "基础补强期"
    elif low_score_count >= 2 or average_score < 75:
        stage_label = "专项提升期"
    else:
        stage_label = "稳定提升期"

    return {
        "summary": {
            "stage_label": stage_label,
            "top_priority_dimension": primary_dimension_key,
            "top_priority_label": primary_label,
            "message": (
                f"基于最近 {len(completed_records)} 次已完成面试，当前最需要优先补强的是{primary_label or '核心能力'}，"
                f"该维度平均 {average_score} 分，低分出现 {low_score_count} 次。"
            ),
        },
        "weaknesses": weaknesses,
        "recommended_resources": recommended_resources,
        "practice_tasks": practice_tasks,
        "next_assessment_focus": next_focus,
        "action_plan": action_plan,
        "strengths": strengths,
        "source_round_count": len(completed_records),
        "latest_updated_at": str(completed_records[0].get("updated_at") or "").strip(),
        "related_records": [
            {
                "thread_id": str(item.get("thread_id") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "updated_at": str(item.get("updated_at") or "").strip(),
                "position": str(item.get("position") or "").strip(),
                "round": str(item.get("round") or "").strip(),
            }
            for item in completed_records[:3]
            if str(item.get("thread_id") or "").strip()
        ],
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
    round_name = str(metadata.get("interview_round") or (scorecard or {}).get("round") or title_round or "").strip()

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
        "position": position or get_default_position_label(),
        "round": round_name or "初试",
        "status": status,
        "overall_score": (scorecard or {}).get("overall"),
        "dimensions": dimension_items,
        "strengths": list((scorecard or {}).get("strengths") or []),
        "has_result": status == "completed" and is_complete_result,
        "result_generated_at": str((result_payload or {}).get("generated_at") or "").strip(),
    }


def _build_history_chart(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed_records = sorted(
        [item for item in records if item.get("has_result") and item.get("status") == "completed"],
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


async def get_personalized_interview_path(
    db: AsyncSession,
    *,
    current_user: User,
    user_id: int | None = None,
) -> dict[str, Any]:
    history_payload = await get_interview_history(
        db,
        current_user=current_user,
        user_id=user_id,
    )
    records = history_payload.get("records") if isinstance(history_payload, dict) else []
    return {
        "target_user": (history_payload or {}).get("target_user") or {},
        "personalized_path": _build_personalized_path(records if isinstance(records, list) else []),
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


def _resolve_learning_file_name(file_meta: dict[str, Any]) -> str:
    return str(
        file_meta.get("filename")
        or file_meta.get("original_filename")
        or file_meta.get("file_name")
        or file_meta.get("name")
        or file_meta.get("file_id")
        or ""
    ).strip()


def _resolve_learning_position(database: dict[str, Any]) -> str:
    additional_params = database.get("additional_params") if isinstance(database, dict) else {}
    metadata = database.get("metadata") if isinstance(database, dict) else {}
    return str((additional_params or {}).get("position") or (metadata or {}).get("position") or "").strip()


def _build_learning_parent_path(
    file_meta: dict[str, Any],
    files: dict[str, dict[str, Any]],
) -> str:
    parent_segments: list[str] = []
    current_parent_id = file_meta.get("parent_id")
    visited: set[str] = set()

    while current_parent_id:
        normalized_parent_id = str(current_parent_id).strip()
        if not normalized_parent_id or normalized_parent_id in visited:
            break
        visited.add(normalized_parent_id)

        parent = files.get(normalized_parent_id)
        if not isinstance(parent, dict):
            break

        parent_name = _resolve_learning_file_name(parent)
        if parent_name:
            parent_segments.append(parent_name)
        current_parent_id = parent.get("parent_id")

    parent_segments.reverse()
    return " / ".join(parent_segments)


def _serialize_learning_document(
    file_meta: dict[str, Any],
    files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    file_name = _resolve_learning_file_name(file_meta)
    parent_path = _build_learning_parent_path(file_meta, files)
    full_path = " / ".join(part for part in [parent_path, file_name] if part)
    return {
        "file_id": str(file_meta.get("file_id") or "").strip(),
        "filename": file_name,
        "parent_id": str(file_meta.get("parent_id") or "").strip(),
        "path": full_path or file_name,
        "folder_path": parent_path,
        "summary": _summarize_learning_excerpt(file_meta.get("description") or file_meta.get("summary") or file_name),
        "status": str(file_meta.get("status") or "").strip(),
        "updated_at": file_meta.get("updated_at") or file_meta.get("modified_at") or file_meta.get("created_at"),
        "created_at": file_meta.get("created_at"),
    }


async def list_learning_databases(*, current_user: User) -> dict[str, Any]:
    accessible = await _get_accessible_databases_for_learning(str(current_user.user_id or current_user.id))
    databases = accessible.get("databases") if isinstance(accessible, dict) else []

    result: list[dict[str, Any]] = []
    for database in databases:
        if not isinstance(database, dict):
            continue

        files = database.get("files") if isinstance(database.get("files"), dict) else {}
        file_count = sum(1 for item in files.values() if isinstance(item, dict) and not item.get("is_folder"))
        result.append(
            {
                "db_id": str(database.get("db_id") or "").strip(),
                "name": str(database.get("name") or "").strip(),
                "description": str(database.get("description") or "").strip(),
                "position": _resolve_learning_position(database),
                "file_count": file_count,
            }
        )

    result.sort(key=lambda item: (item["position"], item["name"]))
    return {"databases": result}


async def get_learning_database_detail(*, db_id: str, current_user: User) -> dict[str, Any]:
    accessible = await knowledge_base.check_accessible({"role": current_user.role}, db_id)
    if not accessible:
        raise HTTPException(status_code=403, detail="鏃犳潈璁块棶璇ョ煡璇嗗簱。")

    database = await knowledge_base.get_database_info(db_id)
    if not isinstance(database, dict):
        raise HTTPException(status_code=404, detail="鐭ヨ瘑搴撲笉瀛樺湪")

    files = database.get("files") if isinstance(database.get("files"), dict) else {}
    documents = [
        _serialize_learning_document(file_meta, files)
        for file_meta in files.values()
        if isinstance(file_meta, dict) and not file_meta.get("is_folder")
    ]
    documents.sort(key=lambda item: (item["folder_path"], item["filename"]))

    return {
        "db_id": str(database.get("db_id") or db_id).strip(),
        "name": str(database.get("name") or "").strip(),
        "description": str(database.get("description") or "").strip(),
        "position": _resolve_learning_position(database),
        "file_count": len(documents),
        "documents": documents,
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
        f"目标岗位：{target_position or get_default_position_label()}",
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
        or get_default_position_label()
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
