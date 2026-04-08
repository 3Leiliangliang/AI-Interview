import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from src.agents.common.runtime_request_context import (  # noqa: E402
    get_agent_request_context,
    reset_agent_request_context,
    set_agent_request_context,
)


def test_reset_agent_request_context_restores_current_context():
    token = set_agent_request_context(thread_id="thread-1", user_id="user-1", target_position="backend")

    assert get_agent_request_context() == {
        "thread_id": "thread-1",
        "user_id": "user-1",
        "target_position": "backend",
    }

    reset_agent_request_context(token)

    assert get_agent_request_context() == {}


def test_reset_agent_request_context_ignores_cross_context_token():
    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        holder: dict[str, object] = {}

        async def worker():
            holder["token"] = set_agent_request_context(
                thread_id="thread-2",
                user_id="user-2",
                target_position="frontend",
            )
            started.set()
            await release.wait()

        task = asyncio.create_task(worker())
        await started.wait()

        reset_agent_request_context(holder["token"])

        assert get_agent_request_context() == {}

        release.set()
        await task

    asyncio.run(scenario())
