from __future__ import annotations

import uuid
from typing import Any

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.runtime import Runtime

from src.services.openviking_service import openviking_service
from src.utils.logging_config import logger

OPENVIKING_CONTEXT_SOURCE = "openviking_context"


class OpenVikingContextMiddleware(AgentMiddleware):
    def __init__(
        self,
        *,
        agent_id: str,
        include_session: bool = True,
        include_user_memory: bool = True,
        include_agent_memory: bool = True,
        min_query_length: int = 4,
    ) -> None:
        super().__init__()
        self.agent_id = agent_id
        self.include_session = include_session
        self.include_user_memory = include_user_memory
        self.include_agent_memory = include_agent_memory
        self.min_query_length = min_query_length

    @staticmethod
    def _collect_existing_context_message_ids(messages: list[Any]) -> list[str]:
        message_ids: list[str] = []
        for msg in messages:
            if getattr(msg, "id", None) is None:
                continue
            source = getattr(msg, "additional_kwargs", {}).get("lc_source")
            if source == OPENVIKING_CONTEXT_SOURCE:
                message_ids.append(msg.id)
        return message_ids

    @staticmethod
    def _latest_user_query(messages: list[Any]) -> str:
        for msg in reversed(messages):
            if getattr(msg, "type", None) != "human":
                continue

            source = getattr(msg, "additional_kwargs", {}).get("lc_source")
            if source == OPENVIKING_CONTEXT_SOURCE:
                continue

            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return ""

    async def abefore_model(self, state: AgentState[Any], runtime: Runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        remove_ids = self._collect_existing_context_message_ids(messages)
        updates = [RemoveMessage(id=message_id) for message_id in remove_ids]

        if not openviking_service.is_enabled():
            return {"messages": updates} if updates else None

        latest_query = self._latest_user_query(messages)
        if len(latest_query) < self.min_query_length:
            return {"messages": updates} if updates else None

        runtime_context = getattr(runtime, "context", None)
        user_id = getattr(runtime_context, "user_id", None)
        thread_id = getattr(runtime_context, "thread_id", None)

        if not user_id or not thread_id:
            return {"messages": updates} if updates else None

        try:
            context_block = await openviking_service.get_context_block(
                user_id=str(user_id),
                thread_id=str(thread_id),
                query_text=latest_query,
                agent_id=self.agent_id,
                include_session=self.include_session,
                include_user_memory=self.include_user_memory,
                include_agent_memory=self.include_agent_memory,
            )
        except Exception as exc:
            logger.warning("OpenViking context retrieval failed: %s", exc)
            return {"messages": updates} if updates else None

        if not context_block:
            return {"messages": updates} if updates else None

        updates.append(
            HumanMessage(
                id=str(uuid.uuid4()),
                content=context_block,
                additional_kwargs={"lc_source": OPENVIKING_CONTEXT_SOURCE},
            )
        )
        return {"messages": updates}
