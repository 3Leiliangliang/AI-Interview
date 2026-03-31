"""Unit tests for VideoContextMiddleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from src.agents.common.middlewares.video_context_middleware import VideoContextMiddleware


def _make_request(has_context=True):
    """Create a mock ModelRequest."""
    runtime = MagicMock()
    if has_context:
        runtime.context.thread_id = "thread-1"
    else:
        runtime.context = None
    request = MagicMock(spec=ModelRequest)
    request.runtime = runtime
    request.system_message = SystemMessage(content=[])
    return request


async def _make_handler():
    """Create a mock async handler."""

    async def handler(req):
        return ModelResponse(result=[])

    return handler


def _aggregated_data(event_count=3):
    """Create mock aggregated video data."""
    return {
        "has_data": True,
        "event_count": event_count,
        "dominant_emotion": "happy",
        "avg_attention_score": 85.0,
        "avg_posture_score": 90.0,
        "gaze_direction": "center",
        "recent_alerts": [],
    }


@pytest.fixture
def middleware():
    """Create a VideoContextMiddleware instance."""
    return VideoContextMiddleware()


@pytest.fixture
def mock_service():
    """Create a mock VideoEventService."""
    service = MagicMock()
    service.consume_events_since = AsyncMock()
    service.close = AsyncMock()
    return service


class TestVideoContextMiddleware:
    """Tests for VideoContextMiddleware."""

    async def test_no_thread_id_passes_through(self, middleware, mock_service):
        """No thread_id means no context, so handler is called directly."""
        request = _make_request(has_context=False)
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            result = await middleware.awrap_model_call(request, handler)

        # Should not call service at all
        mock_service.consume_events_since.assert_not_called()
        assert result.result == []

    async def test_service_called_with_thread_id(self, middleware, mock_service):
        """Service is called with correct thread_id and last_count."""
        mock_service.consume_events_since.return_value = ({"has_data": False}, 0)
        request = _make_request(has_context=True)
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            await middleware.awrap_model_call(request, handler)

        mock_service.consume_events_since.assert_called_once_with("thread-1", 0)
        mock_service.close.assert_called_once()

    async def test_no_new_events_no_injection(self, middleware, mock_service):
        """No new events means just pass through, no injection."""
        mock_service.consume_events_since.return_value = ({"has_data": False}, 10)
        request = _make_request(has_context=True)
        request.system_message = SystemMessage(content=[{"type": "text", "text": "original"}])
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            result = await middleware.awrap_model_call(request, handler)

        assert result.result == []

    async def test_injects_video_context_to_system_message(self, middleware, mock_service):
        """Video analysis summary is injected into system message."""
        mock_service.consume_events_since.return_value = (_aggregated_data(), 10)

        # 使用真实 SystemMessage 以便验证 content_blocks
        original_sm = SystemMessage(content=[{"type": "text", "text": "原始提示词"}])
        request = _make_request(has_context=True)
        request.system_message = original_sm

        # 捕获 override 传入的参数
        captured_override = {}
        original_override = request.override

        def capturing_override(**kwargs):
            captured_override.update(kwargs)
            return original_override(**kwargs)

        request.override = capturing_override
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            await middleware.awrap_model_call(request, handler)

        # 验证 override 被调用并传入了 system_message
        assert "system_message" in captured_override
        new_sm = captured_override["system_message"]
        content_str = str(new_sm.content)
        assert "[面试观察备注" in content_str
        assert "原始提示词" in content_str

        # cursor should be updated after successful consume
        assert middleware._last_event_counts["thread-1"] == 10
        mock_service.close.assert_called_once()

    async def test_service_close_called_on_success(self, middleware, mock_service):
        """Service.close is always called after consume, even with data."""
        mock_service.consume_events_since.return_value = (_aggregated_data(), 5)
        request = _make_request(has_context=True)
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            await middleware.awrap_model_call(request, handler)

        mock_service.close.assert_called_once()

    async def test_consume_failure_does_not_update_cursor(self, middleware, mock_service):
        """Redis exception does NOT update cursor - old cursor value stays."""
        # Set initial cursor value
        middleware._last_event_counts["thread-1"] = 10

        # Simulate Redis exception
        mock_service.consume_events_since.side_effect = Exception("Redis error")
        request = _make_request(has_context=True)
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            await middleware.awrap_model_call(request, handler)

        # close should still be called even on error
        mock_service.close.assert_called_once()

        # Cursor should NOT be updated - should still be 10 (old value)
        assert middleware._last_event_counts["thread-1"] == 10

    async def test_consume_success_updates_cursor(self, middleware, mock_service):
        """Successful consume updates cursor to new value."""
        middleware._last_event_counts["thread-1"] = 5
        mock_service.consume_events_since.return_value = (_aggregated_data(), 15)
        request = _make_request(has_context=True)
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            await middleware.awrap_model_call(request, handler)

        # Cursor should be updated to new value
        assert middleware._last_event_counts["thread-1"] == 15

    async def test_incremental_consumption_per_thread(self, middleware, mock_service):
        """Different threads track consumption position independently."""
        # Set different cursor values for different threads
        middleware._last_event_counts["thread-1"] = 5
        middleware._last_event_counts["thread-2"] = 20

        # Consume for thread-1 should use 5, not 0
        mock_service.consume_events_since.return_value = (_aggregated_data(), 13)
        request1 = _make_request(has_context=True)
        request1.runtime.context.thread_id = "thread-1"
        handler = await _make_handler()

        with patch.object(middleware, "_create_service", return_value=mock_service):
            await middleware.awrap_model_call(request1, handler)

        # thread-1 cursor updated to 13
        assert middleware._last_event_counts["thread-1"] == 13
        # thread-2 cursor unchanged
        assert middleware._last_event_counts["thread-2"] == 20
