import ast
import asyncio
import json
import re
import traceback
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from langchain.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.types import Command
from sqlalchemy import select

from src import config as conf
from src.agents import agent_manager
from src.plugins.guard import content_guard
from src.repositories.agent_config_repository import AgentConfigRepository
from src.repositories.conversation_repository import ConversationRepository
from src.services.interview_resume_service import load_selected_resume_context_payload
from src.services.openviking_service import openviking_service
from src.storage.postgres.models_business import Conversation
from src.storage.postgres.manager import pg_manager
from src.utils.internal_observation import (
    InternalObservationStreamSanitizer,
    strip_internal_observation_text,
)
from src.utils.logging_config import logger

INTERVIEW_SCORECARD_PATTERN = re.compile(
    r"```interview_scorecard\s*(\{[\s\S]*?\})\s*```",
    re.IGNORECASE,
)


def _build_state_files(attachments: list[dict]) -> dict:
    """将附件列表转换为 StateBackend 格式的 files 字典

    StateBackend 期望的格式:
    {
        "/attachments/file.md": {
            "content": ["line1", "line2", ...],
            "created_at": "...",
            "modified_at": "...",
        }
    }
    """
    files = {}
    for attachment in attachments:
        if attachment.get("status") != "parsed":
            continue

        file_path = attachment.get("file_path")
        markdown = attachment.get("markdown")

        if not file_path or not markdown:
            continue

        now = datetime.now(UTC).isoformat()
        # 将 markdown 内容按行拆分
        content_lines = markdown.split("\n")
        files[file_path] = {
            "content": content_lines,
            "created_at": attachment.get("uploaded_at", now),
            "modified_at": attachment.get("uploaded_at", now),
        }

    return files


async def _get_langgraph_messages(agent_instance, config_dict):
    graph = await agent_instance.get_graph()
    state = await graph.aget_state(config_dict)

    if not state or not state.values:
        logger.warning("No state found in LangGraph")
        return None

    return state.values.get("messages", [])


def extract_agent_state(values: dict) -> dict:
    """? LangGraph state ???????? agent state?"""
    if not isinstance(values, dict):
        return {}

    todos = values.get("todos")
    coding_session = values.get("coding_session")
    return {
        "todos": list(todos)[:20] if todos else [],
        "files": values.get("files") or {},
        "coding_session": coding_session if isinstance(coding_session, dict) else None,
    }


def _extract_todos_from_tool_message(msg_dict: dict[str, Any]) -> list[dict[str, Any]]:
    if msg_dict.get("type") != "tool" or msg_dict.get("name") != "write_todos":
        return []

    content = str(msg_dict.get("content") or "").strip()
    if "Updated todo list to" not in content:
        return []

    raw_payload = content.split("Updated todo list to", 1)[1].strip()
    if not raw_payload:
        return []

    try:
        parsed = ast.literal_eval(raw_payload)
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    todos: list[dict[str, Any]] = []
    for item in parsed[:20]:
        if not isinstance(item, dict):
            continue
        content_value = str(item.get("content") or "").strip()
        status_value = str(item.get("status") or "").strip()
        if content_value and status_value:
            todos.append({"content": content_value, "status": status_value})
    return todos


async def enrich_agent_state_with_conversation_metadata(
    conv_repo: ConversationRepository,
    *,
    thread_id: str,
    agent_state: dict | None,
) -> dict:
    next_state = dict(agent_state or {})
    if isinstance(next_state.get("coding_session"), dict):
        return next_state

    conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
    metadata = getattr(conversation, "extra_metadata", None)
    if isinstance(metadata, dict) and isinstance(metadata.get("coding_session"), dict):
        next_state["coding_session"] = metadata["coding_session"]
    return next_state


async def _get_existing_message_ids(conv_repo: ConversationRepository, thread_id: str) -> set[str]:
    existing_messages = await conv_repo.get_messages_by_thread_id(thread_id)
    return {
        msg.extra_metadata["id"]
        for msg in existing_messages
        if msg.extra_metadata and "id" in msg.extra_metadata and isinstance(msg.extra_metadata["id"], str)
    }


async def _save_ai_message(conv_repo: ConversationRepository, thread_id: str, msg_dict: dict) -> None:
    content = msg_dict.get("content", "")
    tool_calls_data = msg_dict.get("tool_calls", [])

    ai_msg = await conv_repo.add_message_by_thread_id(
        thread_id=thread_id,
        role="assistant",
        content=content,
        message_type="text",
        extra_metadata=msg_dict,
    )

    if ai_msg and tool_calls_data:
        for tc in tool_calls_data:
            await conv_repo.add_tool_call(
                message_id=ai_msg.id,
                tool_name=tc.get("name", "unknown"),
                tool_input=tc.get("args", {}),
                status="pending",
                langgraph_tool_call_id=tc.get("id"),
            )


async def _save_tool_message(conv_repo: ConversationRepository, msg_dict: dict) -> None:
    tool_call_id = msg_dict.get("tool_call_id")
    content = msg_dict.get("content", "")

    if not tool_call_id:
        return

    if isinstance(content, list):
        tool_output = json.dumps(content) if content else ""
    else:
        tool_output = str(content)

    await conv_repo.update_tool_call_output(
        langgraph_tool_call_id=tool_call_id,
        tool_output=tool_output,
        status="success",
    )


async def save_partial_message(
    conv_repo: ConversationRepository,
    thread_id: str,
    full_msg=None,
    error_message: str | None = None,
    error_type: str = "interrupted",
):
    try:
        extra_metadata = {
            "error_type": error_type,
            "is_error": True,
            "error_message": error_message or f"发生错误: {error_type}",
        }
        if full_msg:
            msg_dict = full_msg.model_dump() if hasattr(full_msg, "model_dump") else {}
            content = full_msg.content if hasattr(full_msg, "content") else str(full_msg)
            extra_metadata = msg_dict | extra_metadata
        else:
            content = ""

        return await conv_repo.add_message_by_thread_id(
            thread_id=thread_id,
            role="assistant",
            content=content,
            message_type="text",
            extra_metadata=extra_metadata,
        )

    except Exception as e:
        logger.error(f"Error saving message: {e}")
        logger.error(traceback.format_exc())
        return None


async def save_messages_from_langgraph_state(
    agent_instance,
    thread_id: str,
    conv_repo: ConversationRepository,
    config_dict: dict,
) -> None:
    try:
        messages = await _get_langgraph_messages(agent_instance, config_dict)
        if messages is None:
            return

        existing_ids = await _get_existing_message_ids(conv_repo, thread_id)

        for msg in messages:
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else {}
            msg_type = msg_dict.get("type", "unknown")

            if msg_type == "human" or getattr(msg, "id", None) in existing_ids:
                continue

            if msg_type == "ai":
                await _save_ai_message(conv_repo, thread_id, msg_dict)
            elif msg_type == "tool":
                await _save_tool_message(conv_repo, msg_dict)

    except Exception as e:
        logger.error(f"Error saving messages from LangGraph state: {e}")
        logger.error(traceback.format_exc())


def _extract_interview_scorecard(content: str) -> dict[str, Any] | None:
    if not content:
        return None

    match = INTERVIEW_SCORECARD_PATTERN.search(content)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except Exception:
        return None


async def _sync_interview_case_memory_if_needed(
    *,
    agent_id: str,
    user_id: str,
    thread_id: str,
    user_query: str,
    assistant_content: str,
) -> None:
    if agent_id != "InterviewAgent" or not openviking_service.is_enabled():
        return

    if "```interview_scorecard" not in (assistant_content or ""):
        return

    try:
        await openviking_service.sync_interview_case_memory(
            user_id=user_id,
            agent_id=agent_id,
            thread_id=thread_id,
            user_query=user_query,
            summary_content=assistant_content,
            scorecard=_extract_interview_scorecard(assistant_content),
        )
    except Exception as exc:
        logger.warning("Sync interview case memory to OpenViking failed: %s", exc)


def _extract_interrupt_info(state) -> Any | None:
    """从 LangGraph state 中提取中断信息"""
    if hasattr(state, "tasks") and state.tasks:
        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                return task.interrupts[0]

    interrupt_data = state.values.get("__interrupt__")
    if isinstance(interrupt_data, list) and interrupt_data:
        return interrupt_data[0]

    return None


def _coerce_interrupt_payload(info: Any) -> dict:
    """将 LangGraph interrupt 对象转换为 dict 结构。"""
    if isinstance(info, dict):
        return info

    payload = getattr(info, "value", None)
    if isinstance(payload, dict):
        return payload

    question = getattr(info, "question", None)
    operation = getattr(info, "operation", None)
    result: dict[str, Any] = {}
    if isinstance(question, str) and question.strip():
        result["question"] = question
    if isinstance(operation, str) and operation.strip():
        result["operation"] = operation
    return result


def _normalize_interrupt_options(raw_options: Any) -> list[dict[str, str]]:
    if not isinstance(raw_options, list):
        return []

    options: list[dict[str, str]] = []
    for item in raw_options:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("value") or "").strip()
            value = str(item.get("value") or item.get("label") or "").strip()
        else:
            label = str(item).strip()
            value = label
        if label and value:
            options.append({"label": label, "value": value})
    return options


def _build_ask_user_question_payload(info: Any, thread_id: str) -> dict[str, Any]:
    """将 interrupt 信息标准化为 ask_user_question_required 载荷。"""
    payload = _coerce_interrupt_payload(info)

    question = str(payload.get("question") or "请选择一个选项").strip()
    question_id = str(payload.get("question_id") or uuid.uuid4())
    source = str(payload.get("source") or payload.get("tool_name") or "interrupt")
    multi_select = bool(payload.get("multi_select", False))
    allow_other = bool(payload.get("allow_other", True))
    operation = payload.get("operation")

    options = _normalize_interrupt_options(payload.get("options"))

    return {
        "question_id": question_id,
        "question": question,
        "options": options,
        "multi_select": multi_select,
        "allow_other": allow_other,
        "source": source,
        "operation": operation if isinstance(operation, str) else "",
        "thread_id": thread_id,
    }


def _ensure_full_msg(full_msg: AIMessage | None, accumulated_content: list[str]) -> AIMessage | None:
    """如果 full_msg 为空且有累积内容，构建 AIMessage"""
    if not full_msg and accumulated_content:
        return AIMessage(content="".join(accumulated_content))
    return full_msg


def _sanitize_full_msg(full_msg: AIMessage | None) -> AIMessage | None:
    """Ensure saved assistant message never carries internal observation tags."""
    if full_msg and hasattr(full_msg, "content"):
        full_msg.content = strip_internal_observation_text(str(full_msg.content or ""))
    return full_msg


def _normalize_chunk_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return str(content or "")


async def _build_effective_agent_config(
    agent_id: str,
    config_item,
    runtime_config: dict | None,
    *,
    db=None,
    user_id: str | int | None = None,
) -> dict:
    raw_config = config_item.config_json or {}
    stored_context = raw_config.get("context", raw_config)
    effective_config = dict(stored_context) if isinstance(stored_context, dict) else {}

    context_overrides = (runtime_config or {}).get("context_overrides") or {}
    if isinstance(context_overrides, dict):
        effective_config.update(
            {
                key: value
                for key, value in context_overrides.items()
                if value is not None and str(value).strip() != ""
            }
        )

    if agent_id == "InterviewAgent":
        from src.agents.interview_agent.context import InterviewContext

        explicit_selected_resume_id = context_overrides.get("selected_resume_id")
        selected_resume_id = effective_config.get("selected_resume_id")
        if not selected_resume_id and db is not None:
            thread_id = str((runtime_config or {}).get("thread_id") or "").strip()
            if thread_id:
                conversation_result = await db.execute(select(Conversation).where(Conversation.thread_id == thread_id))
                conversation = conversation_result.scalar_one_or_none()
                metadata = getattr(conversation, "extra_metadata", None) if conversation else None
                if isinstance(metadata, dict) and metadata.get("resume_id"):
                    selected_resume_id = metadata.get("resume_id")
                    effective_config["selected_resume_id"] = selected_resume_id

        if db is not None and user_id not in (None, "") and selected_resume_id:
            resume_context = await load_selected_resume_context_payload(
                db=db,
                user_id=int(user_id),
                resume_id=int(selected_resume_id),
                strict=explicit_selected_resume_id not in (None, ""),
            )
            if resume_context:
                effective_config.update(resume_context)

        target_position, interview_round = InterviewContext.normalize_runtime_values(
            effective_config.get("target_position"),
            effective_config.get("interview_round"),
        )
        effective_config["target_position"] = target_position
        effective_config["interview_round"] = interview_round
        effective_config["system_prompt"] = InterviewContext.build_runtime_system_prompt(
            effective_config.get("system_prompt"),
            target_position=target_position,
            interview_round=interview_round,
            selected_resume_filename=effective_config.get("selected_resume_filename"),
            selected_resume_summary=effective_config.get("selected_resume_summary"),
            selected_resume_structured=effective_config.get("selected_resume_structured"),
            selected_resume_markdown_excerpt=effective_config.get("selected_resume_markdown_excerpt"),
        )

    return effective_config


async def _resolve_agent_config(db, agent_id: str, user_id: str, agent_config_id: int | str | None) -> tuple:
    """解析 agent_config，返回 (config_item, agent_config_id)"""
    config_repo = AgentConfigRepository(db)
    config_item = None
    if agent_config_id is not None:
        try:
            config_item = await config_repo.get_by_id(int(agent_config_id))
        except Exception:
            logger.warning(f"Failed to fetch agent config {agent_config_id}: {traceback.format_exc()}")
            config_item = None
        if config_item is not None and config_item.agent_id != agent_id:
            config_item = None

    if config_item is None:
        config_item = await config_repo.get_or_create_default(agent_id=agent_id, created_by=user_id)
        agent_config_id = config_item.id

    return config_item, agent_config_id


async def check_and_handle_interrupts(
    agent,
    langgraph_config: dict,
    make_chunk,
    meta: dict,
    thread_id: str,
) -> AsyncIterator[bytes]:
    try:
        graph = await agent.get_graph()
        state = await graph.aget_state(langgraph_config)

        if not state or not state.values:
            return

        interrupt_info = _extract_interrupt_info(state)
        if interrupt_info:
            question_payload = _build_ask_user_question_payload(interrupt_info, thread_id)
            meta["interrupt"] = question_payload
            yield make_chunk(status="ask_user_question_required", meta=meta, **question_payload)

    except Exception as e:
        logger.error(f"Error checking interrupts: {e}")
        logger.error(traceback.format_exc())


async def stream_agent_chat(
    *,
    agent_id: str,
    query: str,
    config: dict,
    meta: dict,
    image_content: str | None,
    current_user,
    db,
) -> AsyncIterator[bytes]:
    start_time = asyncio.get_event_loop().time()

    def make_chunk(content=None, **kwargs):
        return (
            json.dumps(
                {"request_id": meta.get("request_id"), "response": content, **kwargs}, ensure_ascii=False
            ).encode("utf-8")
            + b"\n"
        )

    if image_content:
        human_message = HumanMessage(
            content=[
                {"type": "text", "text": query},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_content}"}},
            ]
        )
        message_type = "multimodal_image"
    else:
        human_message = HumanMessage(content=query)
        message_type = "text"

    init_msg = {"role": "user", "content": query, "type": "human"}
    if image_content:
        init_msg["message_type"] = "multimodal_image"
        init_msg["image_content"] = image_content
    else:
        init_msg["message_type"] = "text"

    yield make_chunk(status="init", meta=meta, msg=init_msg)

    if conf.enable_content_guard and await content_guard.check(query):
        yield make_chunk(
            status="error", error_type="content_guard_blocked", error_message="输入内容包含敏感词", meta=meta
        )
        return

    try:
        agent = agent_manager.get_agent(agent_id)
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}, {traceback.format_exc()}")
        yield make_chunk(
            status="error",
            error_type="agent_error",
            error_message=f"智能体 {agent_id} 获取失败: {str(e)}",
            meta=meta,
        )
        return

    messages = [human_message]

    user_id = str(current_user.id)
    agent_config_id = config.get("agent_config_id")
    config_item, agent_config_id = await _resolve_agent_config(db, agent_id, user_id, agent_config_id)

    if not (thread_id := config.get("thread_id")):
        thread_id = str(uuid.uuid4())
        logger.warning(f"No thread_id provided, generated new thread_id: {thread_id}")

    agent_config = await _build_effective_agent_config(
        agent_id,
        config_item,
        config,
        db=db,
        user_id=user_id,
    )
    input_context = {
        "user_id": user_id,
        "thread_id": thread_id,
        "agent_config_id": agent_config_id,
        "agent_config": agent_config,
        "selected_resume_id": agent_config.get("selected_resume_id"),
        "selected_resume_filename": agent_config.get("selected_resume_filename", ""),
        "selected_resume_summary": agent_config.get("selected_resume_summary") or {},
        "selected_resume_structured": agent_config.get("selected_resume_structured") or {},
        "selected_resume_markdown_excerpt": agent_config.get("selected_resume_markdown_excerpt", ""),
    }
    full_msg = None
    accumulated_content: list[str] = []
    stream_sanitizer = InternalObservationStreamSanitizer()
    last_ai_metadata: dict[str, Any] | None = None

    try:
        conv_repo = ConversationRepository(db)
        selected_resume_id = agent_config.get("selected_resume_id")
        selected_resume_filename = str(agent_config.get("selected_resume_filename") or "").strip()
        if selected_resume_id:
            await conv_repo.update_conversation(
                thread_id,
                metadata={
                    "resume_id": selected_resume_id,
                    "resume_filename": selected_resume_filename,
                },
            )

        try:
            await conv_repo.add_message_by_thread_id(
                thread_id=thread_id,
                role="user",
                content=query,
                message_type=message_type,
                image_content=image_content,
                extra_metadata={"raw_message": human_message.model_dump()},
            )
        except Exception as e:
            logger.error(f"Error saving user message: {e}")

        # 先构建 langgraph_config
        langgraph_config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

        full_msg = None
        accumulated_content = []
        stream_sanitizer = InternalObservationStreamSanitizer()
        last_ai_metadata = None
        async for msg, metadata in agent.stream_messages(messages, input_context=input_context):
            if isinstance(msg, AIMessageChunk):
                raw_delta = _normalize_chunk_text(msg.content)
                if not raw_delta:
                    continue
                accumulated_content.append(raw_delta)

                content_for_check = "".join(accumulated_content[-10:])
                if conf.enable_content_guard and await content_guard.check_with_keywords(content_for_check):
                    full_msg = _sanitize_full_msg(AIMessage(content="".join(accumulated_content)))
                    await save_partial_message(conv_repo, thread_id, full_msg, "content_guard_blocked")
                    meta["time_cost"] = asyncio.get_event_loop().time() - start_time
                    yield make_chunk(status="interrupted", message="检测到敏感内容，已中断输出", meta=meta)
                    return

                last_ai_metadata = metadata if isinstance(metadata, dict) else None
                safe_delta = stream_sanitizer.feed(raw_delta)
                if not safe_delta:
                    continue

                safe_msg = msg.model_dump()
                safe_msg["content"] = safe_delta
                yield make_chunk(content=safe_delta, msg=safe_msg, metadata=metadata, status="loading")
            else:
                msg_dict = msg.model_dump()
                if msg_dict.get("type") == "ai":
                    safe_content = strip_internal_observation_text(str(msg_dict.get("content") or ""))
                    msg_dict["content"] = safe_content
                    if safe_content:
                        yield make_chunk(content=safe_content, msg=msg_dict, metadata=metadata, status="loading")
                else:
                    yield make_chunk(msg=msg_dict, metadata=metadata, status="loading")

                try:
                    if msg_dict.get("type") == "tool":
                        graph = await agent.get_graph()
                        state = await graph.aget_state(langgraph_config)
                        agent_state = extract_agent_state(getattr(state, "values", {})) if state else {}
                        if not agent_state.get("todos"):
                            tool_todos = _extract_todos_from_tool_message(msg_dict)
                            if tool_todos:
                                agent_state["todos"] = tool_todos
                        if agent_state:
                            agent_state = await enrich_agent_state_with_conversation_metadata(
                                conv_repo,
                                thread_id=thread_id,
                                agent_state=agent_state,
                            )
                            yield make_chunk(status="agent_state", agent_state=agent_state, meta=meta)
                except Exception as e:
                    logger.error(f"Error processing tool message: {e}")

        remaining_safe_delta = stream_sanitizer.flush()
        if remaining_safe_delta:
            yield make_chunk(
                content=remaining_safe_delta,
                msg={"type": "ai", "content": remaining_safe_delta},
                metadata=last_ai_metadata or {},
                status="loading",
            )

        full_msg = _ensure_full_msg(full_msg, accumulated_content)
        if full_msg:
            full_msg.content = stream_sanitizer.full_text()
        full_msg = _sanitize_full_msg(full_msg)

        if conf.enable_content_guard and hasattr(full_msg, "content") and await content_guard.check(full_msg.content):
            await save_partial_message(conv_repo, thread_id, full_msg, "content_guard_blocked")
            meta["time_cost"] = asyncio.get_event_loop().time() - start_time
            yield make_chunk(status="interrupted", message="检测到敏感内容，已中断输出", meta=meta)
            return

        async for chunk in check_and_handle_interrupts(agent, langgraph_config, make_chunk, meta, thread_id):
            yield chunk

        meta["time_cost"] = asyncio.get_event_loop().time() - start_time
        try:
            graph = await agent.get_graph()
            state = await graph.aget_state(langgraph_config)
            agent_state = extract_agent_state(getattr(state, "values", {})) if state else {}
            agent_state = await enrich_agent_state_with_conversation_metadata(
                conv_repo,
                thread_id=thread_id,
                agent_state=agent_state,
            )
        except Exception:
            agent_state = {}

        if agent_state:
            yield make_chunk(status="agent_state", agent_state=agent_state, meta=meta)

        # 先存储数据库，再返回 finished，避免前端查询时数据未落库
        await save_messages_from_langgraph_state(
            agent_instance=agent,
            thread_id=thread_id,
            conv_repo=conv_repo,
            config_dict=langgraph_config,
        )
        await _sync_interview_case_memory_if_needed(
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            user_query=query,
            assistant_content=getattr(full_msg, "content", "") if full_msg else "",
        )

        yield make_chunk(status="finished", meta=meta)

    except (asyncio.CancelledError, ConnectionError) as e:
        logger.warning(f"Client disconnected, cancelling stream: {e}")

        async def save_cleanup():
            nonlocal full_msg
            full_msg = _ensure_full_msg(full_msg, accumulated_content)
            if full_msg:
                full_msg.content = stream_sanitizer.full_text()
            full_msg = _sanitize_full_msg(full_msg)

            async with pg_manager.get_async_session_context() as new_db:
                new_conv_repo = ConversationRepository(new_db)
                # Only flag as interrupted if we got no content at all.
                # If the agent produced a response before the stream was cancelled
                # (e.g. user navigated to coding page), save it normally.
                if full_msg and getattr(full_msg, "content", "").strip():
                    await save_messages_from_langgraph_state(
                        agent_instance=agent,
                        thread_id=thread_id,
                        conv_repo=new_conv_repo,
                        config_dict=langgraph_config,
                    )
                else:
                    await save_partial_message(
                        new_conv_repo,
                        thread_id,
                        full_msg=full_msg,
                        error_message="对话已中断" if not full_msg else None,
                        error_type="interrupted",
                    )

        cleanup_task = asyncio.create_task(save_cleanup())
        try:
            await asyncio.shield(cleanup_task)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Error during cleanup save: {exc}")

        yield make_chunk(status="interrupted", message="对话已中断", meta=meta)

    except Exception as e:
        logger.error(f"Error streaming messages: {e}, {traceback.format_exc()}")

        error_msg = f"Error streaming messages: {e}"
        error_type = "unexpected_error"

        full_msg = _ensure_full_msg(full_msg, accumulated_content)
        if full_msg:
            full_msg.content = stream_sanitizer.full_text()
        full_msg = _sanitize_full_msg(full_msg)

        async with pg_manager.get_async_session_context() as new_db:
            new_conv_repo = ConversationRepository(new_db)
            await save_partial_message(
                new_conv_repo,
                thread_id,
                full_msg=full_msg,
                error_message=error_msg,
                error_type=error_type,
            )

        yield make_chunk(status="error", error_type=error_type, error_message=error_msg, meta=meta)


async def stream_agent_resume(
    *,
    agent_id: str,
    thread_id: str,
    resume_input: Any,
    meta: dict,
    config: dict,
    current_user,
    db,
) -> AsyncIterator[bytes]:
    start_time = asyncio.get_event_loop().time()

    def make_resume_chunk(content=None, **kwargs):
        return (
            json.dumps(
                {"request_id": meta.get("request_id"), "response": content, **kwargs}, ensure_ascii=False
            ).encode("utf-8")
            + b"\n"
        )

    try:
        agent = agent_manager.get_agent(agent_id)
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}, {traceback.format_exc()}")
        yield (
            f'{{"request_id": "{meta.get("request_id")}", "message": '
            f'"Error getting agent {agent_id}: {e}", "status": "error"}}\n'
        )
        return

    init_msg = {"type": "system", "content": f"Resume with input: {resume_input}"}
    yield make_resume_chunk(status="init", meta=meta, msg=init_msg)

    resume_command = Command(resume=resume_input)
    graph = await agent.get_graph()

    user_id = str(current_user.id)
    agent_config_id = (config or {}).get("agent_config_id")
    config_item, agent_config_id = await _resolve_agent_config(db, agent_id, user_id, agent_config_id)

    agent_config = await _build_effective_agent_config(
        agent_id,
        config_item,
        config,
        db=db,
        user_id=user_id,
    )
    input_context = {
        "user_id": user_id,
        "thread_id": thread_id,
        "agent_config_id": agent_config_id,
        "agent_config": agent_config,
        "selected_resume_id": agent_config.get("selected_resume_id"),
        "selected_resume_filename": agent_config.get("selected_resume_filename", ""),
        "selected_resume_summary": agent_config.get("selected_resume_summary") or {},
        "selected_resume_structured": agent_config.get("selected_resume_structured") or {},
        "selected_resume_markdown_excerpt": agent_config.get("selected_resume_markdown_excerpt", ""),
    }
    context = agent.context_schema()
    agent_config = input_context.get("agent_config")
    if isinstance(agent_config, dict):
        context.update(agent_config)
    context.update(input_context)

    stream_source = graph.astream(
        resume_command,
        context=context,
        config={"configurable": {"thread_id": thread_id, "user_id": user_id}},
        stream_mode="messages",
    )

    try:
        async for msg, metadata in stream_source:
            msg_dict = msg.model_dump()
            if "id" not in msg_dict:
                msg_dict["id"] = str(uuid.uuid4())

            yield make_resume_chunk(
                content=getattr(msg, "content", ""), msg=msg_dict, metadata=metadata, status="loading"
            )

        langgraph_config = {"configurable": {"thread_id": thread_id, "user_id": str(current_user.id)}}
        async for chunk in check_and_handle_interrupts(agent, langgraph_config, make_resume_chunk, meta, thread_id):
            yield chunk

        meta["time_cost"] = asyncio.get_event_loop().time() - start_time

        # 先存储数据库，再返回 finished，避免前端查询时数据未落库
        conv_repo = ConversationRepository(db)
        await save_messages_from_langgraph_state(
            agent_instance=agent,
            thread_id=thread_id,
            conv_repo=conv_repo,
            config_dict=langgraph_config,
        )

        yield make_resume_chunk(status="finished", meta=meta)

    except (asyncio.CancelledError, ConnectionError) as e:
        logger.warning(f"Client disconnected during resume: {e}")

        async with pg_manager.get_async_session_context() as new_db:
            new_conv_repo = ConversationRepository(new_db)
            await save_partial_message(
                new_conv_repo, thread_id, error_message="对话恢复已中断", error_type="resume_interrupted"
            )

        yield make_resume_chunk(status="interrupted", message="对话恢复已中断", meta=meta)

    except Exception as e:
        logger.error(f"Error during resume: {e}, {traceback.format_exc()}")

        async with pg_manager.get_async_session_context() as new_db:
            new_conv_repo = ConversationRepository(new_db)
            await save_partial_message(
                new_conv_repo, thread_id, error_message=f"Error during resume: {e}", error_type="resume_error"
            )

        yield make_resume_chunk(message=f"Error during resume: {e}", status="error")


async def get_agent_state_view(
    *,
    agent_id: str,
    thread_id: str,
    current_user_id: str,
    db,
) -> dict:
    if not agent_manager.get_agent(agent_id):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"智能体 {agent_id} 不存在")

    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
    if not conversation or conversation.user_id != str(current_user_id) or conversation.status == "deleted":
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="对话线程不存在")

    agent = agent_manager.get_agent(agent_id)
    graph = await agent.get_graph()
    langgraph_config = {"configurable": {"user_id": str(current_user_id), "thread_id": thread_id}}
    state = await graph.aget_state(langgraph_config)
    agent_state = extract_agent_state(getattr(state, "values", {})) if state else {}

    coding_session = None
    if isinstance(conversation.extra_metadata, dict):
        coding_session = conversation.extra_metadata.get("coding_session")
    if isinstance(coding_session, dict):
        agent_state["coding_session"] = coding_session

    # 如果 state 中没有 files，从附件构建
    # 这确保了上传附件后立即可以在文件列表中看到文件
    if not agent_state.get("files") or agent_state["files"] == {}:
        try:
            attachments = await conv_repo.get_attachments_by_thread_id(thread_id)
            logger.info(f"[get_agent_state_view] found {len(attachments)} attachments in DB")
            if attachments:
                first_status = attachments[0].get("status")
                first_has_markdown = bool(attachments[0].get("markdown"))
                logger.info(
                    f"[get_agent_state_view] first attachment status: {first_status}, "
                    f"has markdown: {first_has_markdown}"
                )
                files = _build_state_files(attachments)
                agent_state["files"] = files
                logger.info(f"[get_agent_state_view] Built files from attachments: {len(files)} files")
        except Exception as e:
            logger.warning(f"Failed to fetch attachments for thread {thread_id}: {e}")

    return {"agent_state": agent_state}
