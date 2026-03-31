from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException
from langchain.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents import agent_manager
from src.repositories.conversation_repository import ConversationRepository
from src.services.chat_stream_service import (
    _build_effective_agent_config,
    _resolve_agent_config,
    save_messages_from_langgraph_state,
)
from src.services.interview_coding_service import get_coding_session_from_metadata
from src.storage.postgres.models_business import User
from src.utils.datetime_utils import format_utc_datetime
from src.utils.logging_config import logger

INTERVIEW_RESULT_METADATA_KEY = "interview_result"
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


def _normalize_score_value(value: Any) -> int | None:
    try:
        score = round(float(value))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, int(score)))


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (str(entry or "").strip() for entry in value) if item]


def _normalize_dimensions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            score = _normalize_score_value(item.get("score"))
            if name and score is not None:
                result.append({"name": name, "score": score})
        return result

    if isinstance(value, dict):
        result = []
        for name, score in value.items():
            normalized_score = _normalize_score_value(score)
            normalized_name = str(name or "").strip()
            if normalized_name and normalized_score is not None:
                result.append({"name": normalized_name, "score": normalized_score})
        return result

    return []


def _normalize_detailed_scores(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []

    result: list[dict[str, Any]] = []
    for key, raw_score in value.items():
        try:
            numeric_score = float(raw_score)
        except (TypeError, ValueError):
            continue
        display_score = round(numeric_score * 10) if numeric_score <= 10 else round(numeric_score)
        normalized_score = _normalize_score_value(display_score)
        if normalized_score is None:
            continue
        result.append({"name": DIMENSION_LABELS.get(str(key), str(key)), "score": normalized_score})
    return result


def _extract_score_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_scorecard(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    candidate_info = value.get("candidate_info") if isinstance(value.get("candidate_info"), dict) else {}
    assessment_summary = (
        value.get("assessment_summary") if isinstance(value.get("assessment_summary"), dict) else {}
    )
    detailed_scores = _extract_score_mapping(value.get("detailed_scores") or value.get("rating_scores"))
    interview_outcome = value.get("interview_outcome") if isinstance(value.get("interview_outcome"), dict) else {}
    fallback_dimensions = _normalize_detailed_scores(detailed_scores)
    fallback_overall = None
    if fallback_dimensions:
        fallback_overall = round(sum(item["score"] for item in fallback_dimensions) / len(fallback_dimensions))

    normalized = {
        "overall": _normalize_score_value(
            value.get("overall", value.get("total_score", value.get("total", fallback_overall)))
        ),
        "role": str(
            value.get("role") or value.get("position") or candidate_info.get("target_position") or ""
        ).strip(),
        "round": str(value.get("round") or candidate_info.get("interview_round") or "").strip(),
        "dimensions": _normalize_dimensions(value.get("dimensions")) or fallback_dimensions,
        "strengths": _normalize_string_list(
            value.get("strengths")
            or assessment_summary.get("strengths")
            or assessment_summary.get("key_strengths")
        ),
        "risks": _normalize_string_list(
            value.get("risks")
            or assessment_summary.get("concerns")
            or assessment_summary.get("key_concerns")
        ),
        "suggestions": _normalize_string_list(
            value.get("suggestions")
            or value.get("next_steps")
            or interview_outcome.get("next_assessment_focus")
        ),
        "summary": str(
            value.get("summary")
            or assessment_summary.get("overall_conclusion")
            or interview_outcome.get("recommendation")
            or interview_outcome.get("recommendation_reason")
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
    }


def _normalize_result_payload(value: Any, *, conversation, coding_session: dict[str, Any] | None) -> dict[str, Any] | None:
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
    }

    if payload["status"] == "completed" and payload["scorecard"]:
        return payload
    if payload["status"] in {"generating", "failed"}:
        return payload
    return None


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
    if conversation.agent_id != "InterviewAgent":
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
    conv_repo, conversation = await _require_interview_conversation(db, thread_id=thread_id, current_user_id=current_user_id)
    coding_session = get_coding_session_from_metadata(conversation.extra_metadata)

    stored_result = _normalize_result_payload(
        (conversation.extra_metadata or {}).get(INTERVIEW_RESULT_METADATA_KEY),
        conversation=conversation,
        coding_session=coding_session,
    )
    if _is_result_complete_enough(stored_result):
        return {
            "thread_id": conversation.thread_id,
            "title": conversation.title,
            "agent_id": conversation.agent_id,
            "result": stored_result,
            "coding_session": coding_session,
        }

    messages = await conv_repo.get_messages_by_thread_id(thread_id)
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
        return {
            "thread_id": conversation.thread_id,
            "title": conversation.title,
            "agent_id": conversation.agent_id,
            "result": derived,
            "coding_session": coding_session,
        }

    return {
        "thread_id": conversation.thread_id,
        "title": conversation.title,
        "agent_id": conversation.agent_id,
        "result": stored_result,
        "coding_session": coding_session,
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

    department_id = current_user.department_id
    if not department_id:
        raise HTTPException(status_code=400, detail="当前用户未绑定部门")

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
        department_id,
        str(current_user.id),
        None,
    )
    runtime_config = {
        "context_overrides": {
            "target_position": target_position,
            "interview_round": interview_round,
        }
    }
    agent_config = _build_effective_agent_config("InterviewAgent", config_item, runtime_config)
    input_context = {
        "user_id": str(current_user.id),
        "thread_id": conversation.thread_id,
        "department_id": department_id,
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
    effective_position = str(target_position or (coding_session or {}).get("target_position") or title_position or "").strip() or "后端工程师"
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
