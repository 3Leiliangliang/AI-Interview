"""
Unit tests for VideoEventService - Redis-backed video event storage.
Tests for:
- store_events: verifying events are correctly stored to Redis
- get_recent_events: verifying recent events retrieval
- get_session_status: verifying session status query
- ttl_expiration: verifying TTL is set correctly
- aggregate_events: verifying event aggregation logic
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.video_event_service import VideoEventService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client with common async methods."""
    redis = AsyncMock()
    redis.lpush = AsyncMock(return_value=1)
    redis.lrange = AsyncMock(return_value=[])
    redis.llen = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    redis.close = AsyncMock()

    # Pipeline mock
    pipeline = AsyncMock()
    pipeline.lpush = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 1, 1, True])
    redis.pipeline = MagicMock(return_value=pipeline)

    return redis


@pytest.fixture
def service(mock_redis):
    """Create a VideoEventService with mocked Redis."""
    svc = VideoEventService(redis_url="redis://localhost:6379/0")
    svc._redis = mock_redis
    return svc


def _make_event(
    event_type: str,
    event_id: str = "evt-1",
    session_id: str = "sess-123",
    data: dict | None = None,
    severity: str = "low",
) -> dict:
    """Helper to build a sample event dict."""
    return {
        "event_id": event_id,
        "session_id": session_id,
        "timestamp": 1700000000.0,
        "sequence": 1,
        "type": event_type,
        "data": data or {},
        "severity": severity,
    }


# ============================================================
# store_events
# ============================================================


class TestStoreEvents:
    """Test storing event batches to Redis."""

    async def test_store_single_event(self, service: VideoEventService, mock_redis):
        """A single event should be pushed to the correct Redis list key."""
        events = [_make_event("emotion_detected")]
        count = await service.store_events("sess-1", events)

        assert count == 1
        pipeline = mock_redis.pipeline.return_value
        pipeline.lpush.assert_called_once()
        call_args = pipeline.lpush.call_args[0]
        assert call_args[0] == "video:events:sess-1"

    async def test_store_multiple_events(self, service: VideoEventService, mock_redis):
        """Multiple events should be pushed individually via pipeline."""
        events = [_make_event("emotion_detected", event_id=f"evt-{i}") for i in range(5)]
        count = await service.store_events("sess-1", events)

        assert count == 5
        pipeline = mock_redis.pipeline.return_value
        assert pipeline.lpush.call_count == 5

    async def test_store_events_sets_ttl(self, service: VideoEventService, mock_redis):
        """Storing events should set TTL on the key."""
        events = [_make_event("emotion_detected")]
        await service.store_events("sess-1", events)

        pipeline = mock_redis.pipeline.return_value
        pipeline.expire.assert_called_once_with("video:events:sess-1", VideoEventService.EVENT_TTL)

    async def test_store_events_serializes_json(self, service: VideoEventService, mock_redis):
        """Events should be serialized to JSON with ensure_ascii=False."""
        event = _make_event("emotion_detected", data={"emotion": "快乐"})
        await service.store_events("sess-1", [event])

        pipeline = mock_redis.pipeline.return_value
        call_args = pipeline.lpush.call_args[0]
        serialized = call_args[1]
        assert "快乐" in serialized
        parsed = json.loads(serialized)
        assert parsed["data"]["emotion"] == "快乐"

    async def test_store_empty_events(self, service: VideoEventService, mock_redis):
        """Empty event list should return 0 and not push anything."""
        count = await service.store_events("sess-1", [])
        assert count == 0
        pipeline = mock_redis.pipeline.return_value
        pipeline.lpush.assert_not_called()


# ============================================================
# get_recent_events
# ============================================================


class TestGetRecentEvents:
    """Test retrieving recent events from Redis."""

    async def test_get_recent_events_empty(self, service: VideoEventService, mock_redis):
        """Should return empty list when no events exist."""
        mock_redis.lrange.return_value = []
        events = await service.get_recent_events("sess-1")
        assert events == []

    async def test_get_recent_events_parses_json(self, service: VideoEventService, mock_redis):
        """Should parse JSON strings into dicts."""
        raw = [
            json.dumps({"type": "emotion_detected", "data": {}}).encode(),
            json.dumps({"type": "posture_detected", "data": {}}).encode(),
        ]
        mock_redis.lrange.return_value = raw

        events = await service.get_recent_events("sess-1")
        assert len(events) == 2
        assert events[0]["type"] == "emotion_detected"
        assert events[1]["type"] == "posture_detected"

    async def test_get_recent_events_respects_count(self, service: VideoEventService, mock_redis):
        """Should request the correct count from Redis."""
        await service.get_recent_events("sess-1", count=50)
        mock_redis.lrange.assert_called_once_with("video:events:sess-1", 0, 49)

    async def test_get_recent_events_default_count(self, service: VideoEventService, mock_redis):
        """Default count should be 100."""
        await service.get_recent_events("sess-1")
        mock_redis.lrange.assert_called_once_with("video:events:sess-1", 0, 99)


# ============================================================
# get_session_status
# ============================================================


class TestGetSessionStatus:
    """Test session status queries."""

    async def test_active_session(self, service: VideoEventService, mock_redis):
        """Session with events should report 'active' status."""
        mock_redis.llen.return_value = 42
        status = await service.get_session_status("sess-1")

        assert status["session_id"] == "sess-1"
        assert status["events_in_buffer"] == 42
        assert status["status"] == "active"

    async def test_inactive_session(self, service: VideoEventService, mock_redis):
        """Session with no events should report 'inactive' status."""
        mock_redis.llen.return_value = 0
        status = await service.get_session_status("sess-1")

        assert status["session_id"] == "sess-1"
        assert status["events_in_buffer"] == 0
        assert status["status"] == "inactive"


# ============================================================
# aggregate_events
# ============================================================


class TestAggregateEvents:
    """Test event aggregation logic."""

    async def test_aggregate_no_events(self, service: VideoEventService, mock_redis):
        """No events should return has_data=False."""
        mock_redis.lrange.return_value = []
        result = await service.aggregate_events("sess-1")

        assert result["has_data"] is False

    async def test_aggregate_emotion(self, service: VideoEventService, mock_redis):
        """Should compute dominant emotion and normalized scores."""
        events = [
            json.dumps({
                "type": "emotion_detected",
                "data": {"scores": {"happy": 0.6, "neutral": 0.3, "sad": 0.1}},
            }),
            json.dumps({
                "type": "emotion_detected",
                "data": {"scores": {"happy": 0.5, "neutral": 0.4, "sad": 0.1}},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")
        assert result["has_data"] is True
        assert result["dominant_emotion"] == "happy"
        assert result["event_count"] == 2

    async def test_aggregate_posture(self, service: VideoEventService, mock_redis):
        """Should compute average posture score and retain current posture."""
        events = [
            json.dumps({
                "type": "posture_detected",
                "data": {"posture": "upright", "posture_score": 85, "gaze_direction": "left"},
            }),
            json.dumps({
                "type": "posture_detected",
                "data": {"posture": "slouching", "posture_score": 95, "gaze_direction": "right"},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")
        assert result["avg_posture_score"] == 90.0
        assert result["gaze_direction"] == "right"
        assert result["current_posture"] == "upright"
        assert result["dominant_posture"] in {"upright", "slouching"}

    async def test_aggregate_attention(self, service: VideoEventService, mock_redis):
        """Should compute average attention score."""
        events = [
            json.dumps({
                "type": "attention_change",
                "data": {"attention_score": 80},
            }),
            json.dumps({
                "type": "attention_change",
                "data": {"attention_score": 60},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")
        assert result["avg_attention_score"] == 70.0

    async def test_aggregate_alerts(self, service: VideoEventService, mock_redis):
        """Should collect up to 3 most recent alerts."""
        events = [
            json.dumps({
                "type": "alert_triggered",
                "data": {"alert_type": "gaze", "message": "Looking away"},
            }),
            json.dumps({
                "type": "alert_triggered",
                "data": {"alert_type": "posture", "message": "Bad posture"},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")
        assert len(result["recent_alerts"]) == 2
        assert result["recent_alerts"][-1]["type"] == "posture"

    async def test_aggregate_mixed_events(self, service: VideoEventService, mock_redis):
        """Should aggregate all event types together correctly."""
        events = [
            json.dumps({
                "type": "emotion_detected",
                "data": {"scores": {"happy": 0.8, "neutral": 0.2}},
            }),
            json.dumps({
                "type": "posture_detected",
                "data": {"posture": "upright", "posture_score": 90, "gaze_direction": "center"},
            }),
            json.dumps({
                "type": "attention_change",
                "data": {"attention_score": 75},
            }),
            json.dumps({
                "type": "alert_triggered",
                "data": {"alert_type": "attention", "message": "Distracted"},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")
        assert result["has_data"] is True
        assert result["dominant_emotion"] == "happy"
        assert result["avg_posture_score"] == 90.0
        assert result["gaze_direction"] == "center"
        assert result["current_posture"] == "upright"
        assert result["avg_attention_score"] == 75.0
        assert len(result["recent_alerts"]) == 1
        assert result["event_count"] == 4

    async def test_aggregate_tracks_current_posture_from_latest_event(
        self, service: VideoEventService, mock_redis
    ):
        """Should expose the latest posture classification for UI and middleware use."""
        events = [
            json.dumps({
                "type": "posture_detected",
                "data": {"posture": "leaning_forward", "posture_score": 88, "gaze_direction": "center"},
            }),
            json.dumps({
                "type": "posture_detected",
                "data": {"posture": "slouching", "posture_score": 62, "gaze_direction": "down"},
            }),
            json.dumps({
                "type": "posture_detected",
                "data": {"posture": "leaning_forward", "posture_score": 84, "gaze_direction": "center"},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")

        assert result["current_posture"] == "leaning_forward"
        assert result["dominant_posture"] == "leaning_forward"

    async def test_aggregate_no_matching_event_types(self, service: VideoEventService, mock_redis):
        """Events with unknown types should still count but produce no specific metrics."""
        events = [
            json.dumps({"type": "unknown_type", "data": {}}),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]

        result = await service.aggregate_events("sess-1")
        assert result["has_data"] is True
        assert result["dominant_emotion"] == "neutral"
        assert result["avg_posture_score"] is None
        assert result["avg_attention_score"] is None
        assert result["recent_alerts"] == []
        assert result["event_count"] == 1


# ============================================================
# close
# ============================================================


class TestClose:
    """Test service cleanup."""

    async def test_close_closes_redis(self, service: VideoEventService, mock_redis):
        """close() should close the Redis connection."""
        await service.close()
        mock_redis.close.assert_called_once()
        assert service._redis is None

    async def test_close_idempotent(self, service: VideoEventService):
        """Calling close() when _redis is None should be safe."""
        service._redis = None
        await service.close()
        assert service._redis is None


# ============================================================
# Redis lazy init
# ============================================================


class TestRedisInit:
    """Test Redis lazy initialization."""

    async def test_get_redis_creates_connection(self):
        """_get_redis should create a connection when _redis is None."""
        svc = VideoEventService(redis_url="redis://localhost:6379/0")
        assert svc._redis is None

        with patch("src.services.video_event_service.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            r = await svc._get_redis()
            mock_from_url.assert_called_once_with("redis://localhost:6379/0")
            assert r is mock_redis

    async def test_get_redis_reuses_connection(self, service: VideoEventService, mock_redis):
        """_get_redis should return existing connection if already created."""
        r = await service._get_redis()
        assert r is mock_redis


# ============================================================
# consume_events_since
# ============================================================


class TestConsumeEventsSince:
    """Test incremental event consumption since last read."""

    async def test_consume_all_events_first_time(self, service: VideoEventService, mock_redis):
        """last_event_count=0 should read and aggregate all events."""
        events = [
            json.dumps({
                "type": "emotion_detected",
                "data": {"scores": {"happy": 0.8, "neutral": 0.2}},
            }),
            json.dumps({
                "type": "posture_detected",
                "data": {"posture_score": 90, "gaze_direction": "center"},
            }),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in events]
        mock_redis.llen.return_value = 2

        result, total = await service.consume_events_since("sess-1", last_event_count=0)

        assert result["has_data"] is True
        assert result["dominant_emotion"] == "happy"
        assert result["avg_posture_score"] == 90.0
        assert total == 2

    async def test_consume_incremental_events(self, service: VideoEventService, mock_redis):
        """last_event_count=N should only aggregate new events (first N in LPUSH list)."""
        # 模拟 Redis 中有 5 个事件（LPUSH，index 0 最新），last_event_count=2，新增 3 个
        # 新增事件在最前面（index 0-2），旧事件在后面（index 3-4）
        all_events = [
            json.dumps({"type": "emotion_detected", "data": {"scores": {"happy": 0.7, "neutral": 0.3}}}),
            json.dumps({"type": "posture_detected", "data": {"posture_score": 85, "gaze_direction": "left"}}),
            json.dumps({"type": "attention_change", "data": {"attention_score": 75}}),
            json.dumps({"type": "emotion_detected", "data": {"scores": {"sad": 0.9, "neutral": 0.1}}}),
            json.dumps({"type": "emotion_detected", "data": {"scores": {"happy": 0.8, "neutral": 0.2}}}),
        ]
        mock_redis.lrange.return_value = [e.encode() for e in all_events]
        mock_redis.llen.return_value = 5

        result, total = await service.consume_events_since("sess-1", last_event_count=2)

        # 增量部分：前 3 个（new_count = 5 - 2 = 3）
        assert result["has_data"] is True
        assert result["dominant_emotion"] == "happy"  # happy: 0.7
        assert result["avg_posture_score"] == 85.0
        assert result["avg_attention_score"] == 75.0
        assert total == 5

    async def test_consume_no_new_events(self, service: VideoEventService, mock_redis):
        """last_event_count equals current total should return has_data=False."""
        # 有 3 个事件，但 last_event_count=3，没有增量
        mock_redis.lrange.return_value = [
            json.dumps({"type": "emotion_detected", "data": {"scores": {"happy": 0.8}}}).encode(),
        ]
        mock_redis.llen.return_value = 3

        result, total = await service.consume_events_since("sess-1", last_event_count=3)

        assert result["has_data"] is False
        assert total == 3

    async def test_consume_renews_ttl(self, service: VideoEventService, mock_redis):
        """consume_events_since should renew TTL on each call."""
        mock_redis.lrange.return_value = [
            json.dumps({"type": "emotion_detected", "data": {"scores": {"happy": 0.8}}}).encode(),
        ]
        mock_redis.llen.return_value = 1

        await service.consume_events_since("sess-1", last_event_count=0)

        mock_redis.expire.assert_called_once()
        call_args = mock_redis.expire.call_args[0]
        assert call_args[0] == "video:events:sess-1"
        assert call_args[1] == VideoEventService.EVENT_TTL

    async def test_consume_empty_session(self, service: VideoEventService, mock_redis):
        """No events should return has_data=False and total=0."""
        mock_redis.lrange.return_value = []
        mock_redis.llen.return_value = 0

        result, total = await service.consume_events_since("sess-1", last_event_count=0)

        assert result["has_data"] is False
        assert total == 0

    async def test_consume_returns_new_total_count(self, service: VideoEventService, mock_redis):
        """Return value should include the current Redis List total length."""
        mock_redis.lrange.return_value = [
            json.dumps({"type": "emotion_detected", "data": {"scores": {"happy": 0.8}}}).encode(),
        ]
        # 消费时又有新事件，总数变成 10
        mock_redis.llen.return_value = 10

        result, total = await service.consume_events_since("sess-1", last_event_count=0)

        assert total == 10
        assert result["event_count"] == 1
