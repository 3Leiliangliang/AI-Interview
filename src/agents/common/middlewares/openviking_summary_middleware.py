from __future__ import annotations

import uuid
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from src.agents.common.middlewares.summary_middleware import (
    DEFAULT_SUMMARY_PROMPT,
    ContextSize,
    SummaryOffloadMiddleware,
    TokenCounter,
    _DEFAULT_MESSAGES_TO_KEEP,
    _DEFAULT_TRIM_TOKEN_LIMIT,
)
from src.services.openviking_service import openviking_service
from src.utils.logging_config import logger

OPENVIKING_SUMMARY_SOURCE = "openviking_summary"


class OpenVikingSummaryMiddleware(AgentMiddleware):
    def __init__(
        self,
        model: str | BaseChatModel,
        *,
        trigger: ContextSize | list[ContextSize] | None = None,
        keep: ContextSize = ("messages", _DEFAULT_MESSAGES_TO_KEEP),
        token_counter: TokenCounter | None = None,
        summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
        trim_tokens_to_summarize: int | None = _DEFAULT_TRIM_TOKEN_LIMIT,
        summary_offload_threshold: int = 1000,
        max_retention_ratio: float = 0.6,
        **deprecated_kwargs: Any,
    ) -> None:
        super().__init__()
        kwargs: dict[str, Any] = {
            "trigger": trigger,
            "keep": keep,
            "summary_prompt": summary_prompt,
            "trim_tokens_to_summarize": trim_tokens_to_summarize,
            "summary_offload_threshold": summary_offload_threshold,
            "max_retention_ratio": max_retention_ratio,
            **deprecated_kwargs,
        }
        if token_counter is not None:
            kwargs["token_counter"] = token_counter
        self.fallback = SummaryOffloadMiddleware(model=model, **kwargs)

    def before_model(self, state: AgentState[Any], runtime: Runtime) -> dict[str, Any] | None:
        return self.fallback.before_model(state, runtime)

    async def abefore_model(self, state: AgentState[Any], runtime: Runtime) -> dict[str, Any] | None:
        if not openviking_service.is_enabled():
            return await self.fallback.abefore_model(state, runtime)

        messages = state["messages"]
        self.fallback._ensure_message_ids(messages)

        total_tokens = self.fallback.token_counter(messages)
        if not self.fallback._should_summarize(messages, total_tokens):
            return None

        trigger_value = self.fallback._get_token_trigger_value()
        if trigger_value is None:
            return await self.fallback.abefore_model(state, runtime)

        retention_limit = int(trigger_value * self.fallback.max_retention_ratio)
        if retention_limit <= 0:
            return await self.fallback.abefore_model(state, runtime)

        current_tokens = self.fallback.token_counter(messages)
        if current_tokens <= retention_limit:
            return None

        system_msg_count = 0
        messages_to_process = messages
        if messages and messages[0].type == "system":
            system_msg_count = 1
            messages_to_process = messages[1:]

        cutoff_relative = self.fallback._find_cutoff_by_token_limit(messages_to_process, retention_limit)
        cutoff_index = system_msg_count + cutoff_relative
        if cutoff_index <= system_msg_count:
            return None

        messages_to_archive, preserved_messages = self.fallback._partition_messages(messages, cutoff_index)

        runtime_context = getattr(runtime, "context", None)
        user_id = getattr(runtime_context, "user_id", None)
        thread_id = getattr(runtime_context, "thread_id", None)
        if not user_id or not thread_id:
            return await self.fallback.abefore_model(state, runtime)

        try:
            archive_result = await openviking_service.archive_session_messages(
                user_id=str(user_id),
                thread_id=str(thread_id),
                messages=messages_to_archive,
            )
        except Exception as exc:
            logger.warning("OpenViking session archive failed, fallback to summary middleware: %s", exc)
            return await self.fallback.abefore_model(state, runtime)

        overview = archive_result.get("overview") or archive_result.get("abstract") or "历史上下文已迁移到 OpenViking。"
        archive_message = HumanMessage(
            id=str(uuid.uuid4()),
            content=(
                "较早的会话上下文已迁移到 OpenViking。\n"
                f"存档位置：{archive_result['uri']}\n"
                f"摘要：{overview}"
            ),
            additional_kwargs={"lc_source": OPENVIKING_SUMMARY_SOURCE},
        )

        final_messages: list[Any] = []
        if system_msg_count > 0:
            final_messages.append(messages[0])
        final_messages.append(archive_message)
        final_messages.extend(preserved_messages)

        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *final_messages]}
