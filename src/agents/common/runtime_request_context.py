from __future__ import annotations

import logging
from contextvars import ContextVar, Token

_AGENT_REQUEST_CONTEXT: ContextVar[dict[str, str]] = ContextVar("agent_request_context", default={})
logger = logging.getLogger(__name__)


def set_agent_request_context(*, thread_id: str, user_id: str, target_position: str = "") -> Token:
    return _AGENT_REQUEST_CONTEXT.set(
        {
            "thread_id": str(thread_id or ""),
            "user_id": str(user_id or ""),
            "target_position": str(target_position or ""),
        }
    )


def reset_agent_request_context(token: Token) -> None:
    try:
        _AGENT_REQUEST_CONTEXT.reset(token)
    except ValueError:
        # Async generator cleanup may run in a copied context after the request
        # has already finished. Skipping reset avoids turning a completed agent run
        # into a failed one.
        logger.debug("Skip resetting agent request context from a different async context")


def get_agent_request_context() -> dict[str, str]:
    return dict(_AGENT_REQUEST_CONTEXT.get() or {})
