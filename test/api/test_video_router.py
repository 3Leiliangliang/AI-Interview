"""
Integration tests for video interview analysis API routes.

Tests cover:
- POST /api/video/event - Event batch ingestion
- GET /api/video/status/{session_id} - Session status
- GET /api/video/aggregate/{session_id} - Aggregated analysis summary
- POST /api/video/report/{session_id} - Report generation

Note: These tests require Redis to be running. They are marked as
integration tests and will be skipped if the API service is not available.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _make_event_payload(
    event_type: str = "emotion_detected",
    session_id: str = "test-sess-123",
    data: dict | None = None,
    severity: str = "low",
) -> dict:
    """Build a sample event payload."""
    return {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "session_id": session_id,
        "timestamp": 1700000000.0,
        "sequence": 1,
        "type": event_type,
        "data": data or {},
        "severity": severity,
    }


def _make_event_batch(
    session_id: str = "test-sess-123",
    batch_id: str | None = None,
    events: list[dict] | None = None,
) -> dict:
    """Build a sample event batch payload."""
    return {
        "session_id": session_id,
        "batch_id": batch_id or uuid.uuid4().hex,
        "events": events if events is not None else [_make_event_payload(session_id=session_id)],
        "batch_timestamp": 1700000000.0,
        "batch_sequence": 1,
    }


class TestVideoEventEndpoint:
    """Test POST /api/video/event - event batch ingestion."""

    async def test_store_single_event_batch(self, test_client):
        """Should store an event batch and return count."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        batch = _make_event_batch(
            session_id=session_id,
            events=[
                _make_event_payload(
                    event_type="emotion_detected",
                    session_id=session_id,
                    data={"emotion": "happy", "scores": {"happy": 0.8, "neutral": 0.2}},
                )
            ],
        )

        response = await test_client.post("/api/video/event", json=batch)

        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "ok"
        assert result["events_count"] == 1

    async def test_store_multiple_events_batch(self, test_client):
        """Should store multiple events in a batch."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        events = [
            _make_event_payload(
                event_type="emotion_detected",
                session_id=session_id,
                data={"emotion": "happy", "scores": {"happy": 0.6, "neutral": 0.4}},
            ),
            _make_event_payload(
                event_type="posture_detected",
                session_id=session_id,
                data={"posture_score": 85, "gaze_direction": "center"},
            ),
            _make_event_payload(
                event_type="attention_change",
                session_id=session_id,
                data={"attention_score": 80},
            ),
        ]
        batch = _make_event_batch(session_id=session_id, events=events)

        response = await test_client.post("/api/video/event", json=batch)

        assert response.status_code == 200
        result = response.json()
        assert result["events_count"] == 3

    async def test_store_empty_events_returns_zero(self, test_client):
        """Empty event list should return count 0."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        batch = _make_event_batch(session_id=session_id, events=[])

        response = await test_client.post("/api/video/event", json=batch)

        assert response.status_code == 200
        assert response.json()["events_count"] == 0

    async def test_store_event_with_alert(self, test_client):
        """Should store alert events correctly."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        batch = _make_event_batch(
            session_id=session_id,
            events=[
                _make_event_payload(
                    event_type="alert_triggered",
                    session_id=session_id,
                    data={"alert_type": "gaze", "message": "Looking away"},
                    severity="medium",
                )
            ],
        )

        response = await test_client.post("/api/video/event", json=batch)

        assert response.status_code == 200
        assert response.json()["events_count"] == 1


class TestVideoStatusEndpoint:
    """Test GET /api/video/status/{session_id} - session status."""

    async def test_get_status_active_session(self, test_client):
        """Should return active status for session with events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        # First store some events
        batch = _make_event_batch(session_id=session_id)
        await test_client.post("/api/video/event", json=batch)

        # Then check status
        response = await test_client.get(f"/api/video/status/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["session_id"] == session_id
        assert result["status"] == "active"
        assert result["events_in_buffer"] > 0

    async def test_get_status_inactive_session(self, test_client):
        """Should return inactive status for session with no events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        # Use a unique session ID that has never had events
        response = await test_client.get(f"/api/video/status/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["session_id"] == session_id
        assert result["status"] == "inactive"
        assert result["events_in_buffer"] == 0

    async def test_get_status_invalid_session_id(self, test_client):
        """Should reject invalid session_id format."""
        # Session ID with special characters (potential injection)
        response = await test_client.get("/api/video/status/sess:inject@redis")

        assert response.status_code == 400
        assert "detail" in response.json()


class TestVideoAggregateEndpoint:
    """Test GET /api/video/aggregate/{session_id} - aggregated summary."""

    async def test_aggregate_empty_session(self, test_client):
        """Should return has_data=False for session with no events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        response = await test_client.get(f"/api/video/aggregate/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["has_data"] is False

    async def test_aggregate_emotion_events(self, test_client):
        """Should correctly aggregate emotion detection events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        # Store emotion events
        events = [
            _make_event_payload(
                event_type="emotion_detected",
                session_id=session_id,
                data={"scores": {"happy": 0.6, "neutral": 0.3, "sad": 0.1}},
            ),
            _make_event_payload(
                event_type="emotion_detected",
                session_id=session_id,
                data={"scores": {"happy": 0.7, "neutral": 0.2, "sad": 0.1}},
            ),
        ]
        batch = _make_event_batch(session_id=session_id, events=events)
        await test_client.post("/api/video/event", json=batch)

        # Get aggregate
        response = await test_client.get(f"/api/video/aggregate/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["has_data"] is True
        assert result["dominant_emotion"] == "happy"
        assert "emotion_scores" in result
        assert result["event_count"] == 2

    async def test_aggregate_posture_events(self, test_client):
        """Should correctly aggregate posture detection events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        events = [
            _make_event_payload(
                event_type="posture_detected",
                session_id=session_id,
                data={"posture_score": 85, "gaze_direction": "left"},
            ),
            _make_event_payload(
                event_type="posture_detected",
                session_id=session_id,
                data={"posture_score": 95, "gaze_direction": "right"},
            ),
        ]
        batch = _make_event_batch(session_id=session_id, events=events)
        await test_client.post("/api/video/event", json=batch)

        response = await test_client.get(f"/api/video/aggregate/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["has_data"] is True
        assert result["avg_posture_score"] == 90.0
        assert result["gaze_direction"] == "left"  # lpush reverses order, last processed is first inserted

    async def test_aggregate_attention_events(self, test_client):
        """Should correctly aggregate attention change events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        events = [
            _make_event_payload(
                event_type="attention_change",
                session_id=session_id,
                data={"attention_score": 80},
            ),
            _make_event_payload(
                event_type="attention_change",
                session_id=session_id,
                data={"attention_score": 60},
            ),
        ]
        batch = _make_event_batch(session_id=session_id, events=events)
        await test_client.post("/api/video/event", json=batch)

        response = await test_client.get(f"/api/video/aggregate/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["has_data"] is True
        assert result["avg_attention_score"] == 70.0

    async def test_aggregate_mixed_events(self, test_client):
        """Should aggregate mixed event types correctly."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        events = [
            _make_event_payload(
                event_type="emotion_detected",
                session_id=session_id,
                data={"scores": {"happy": 0.8, "neutral": 0.2}},
            ),
            _make_event_payload(
                event_type="posture_detected",
                session_id=session_id,
                data={"posture_score": 90, "gaze_direction": "center"},
            ),
            _make_event_payload(
                event_type="attention_change",
                session_id=session_id,
                data={"attention_score": 75},
            ),
            _make_event_payload(
                event_type="alert_triggered",
                session_id=session_id,
                data={"alert_type": "attention", "message": "Distracted"},
                severity="medium",
            ),
        ]
        batch = _make_event_batch(session_id=session_id, events=events)
        await test_client.post("/api/video/event", json=batch)

        response = await test_client.get(f"/api/video/aggregate/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["has_data"] is True
        assert result["dominant_emotion"] == "happy"
        assert result["avg_posture_score"] == 90.0
        assert result["avg_attention_score"] == 75.0
        assert len(result["recent_alerts"]) == 1
        assert result["event_count"] == 4

    async def test_aggregate_invalid_session_id(self, test_client):
        """Should reject invalid session_id format."""
        response = await test_client.get("/api/video/aggregate/sess:bad")

        assert response.status_code == 400


class TestVideoReportEndpoint:
    """Test POST /api/video/report/{session_id} - report generation."""

    async def test_generate_report_no_data(self, test_client):
        """Should return empty report for session with no events."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"
        response = await test_client.post(f"/api/video/report/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["session_id"] == session_id
        assert result["has_data"] is False
        assert result["scores"] == {}
        assert result["recommendations"] == []

    async def test_generate_report_with_data(self, test_client):
        """Should generate report with scores when events exist."""
        session_id = f"test-sess-{uuid.uuid4().hex[:8]}"

        # Store events first
        events = [
            _make_event_payload(
                event_type="emotion_detected",
                session_id=session_id,
                data={"scores": {"neutral": 0.9, "happy": 0.1}},
            ),
            _make_event_payload(
                event_type="posture_detected",
                session_id=session_id,
                data={"posture_score": 85, "gaze_direction": "center"},
            ),
            _make_event_payload(
                event_type="attention_change",
                session_id=session_id,
                data={"attention_score": 78},
            ),
        ]
        batch = _make_event_batch(session_id=session_id, events=events)
        await test_client.post("/api/video/event", json=batch)

        # Generate report
        response = await test_client.post(f"/api/video/report/{session_id}")

        assert response.status_code == 200
        result = response.json()
        assert result["session_id"] == session_id
        assert result["has_data"] is True
        assert "scores" in result
        assert "emotion_stability" in result["scores"]
        assert "posture" in result["scores"]
        assert "attention" in result["scores"]
        assert "overall" in result["scores"]
        # LLM fallback report should have recommendations
        assert isinstance(result["recommendations"], list)

    async def test_generate_report_invalid_session_id(self, test_client):
        """Should reject invalid session_id format."""
        response = await test_client.post("/api/video/report/sess:bad")

        assert response.status_code == 400


class TestVideoApiEdgeCases:
    """Test edge cases and error handling."""

    async def test_session_id_validation_rejects_long_string(self, test_client):
        """Should reject session_id that is too long."""
        # 129 character string (exceeds 128 max)
        long_session_id = "a" * 129
        response = await test_client.get(f"/api/video/status/{long_session_id}")

        assert response.status_code == 400

    async def test_session_id_validation_accepts_valid_formats(self, test_client):
        """Should accept various valid session_id formats."""
        valid_ids = [
            f"test-{uuid.uuid4().hex}",  # UUID-like
            "session-123",  # with hyphen
            "session_123",  # with underscore
        ]

        for session_id in valid_ids:
            response = await test_client.get(f"/api/video/status/{session_id}")
            # Should not be 400 (may be 200 or other success/error)
            # We only care it passes format validation
            assert response.status_code != 400 or "detail" not in response.json() or "session_id" not in response.json().get("detail", "")

    async def test_multiple_sessions_isolated(self, test_client):
        """Events for different sessions should be isolated."""
        session_1 = f"test-sess-{uuid.uuid4().hex[:8]}"
        session_2 = f"test-sess-{uuid.uuid4().hex[:8]}"

        # Store different events in each session
        batch1 = _make_event_batch(
            session_id=session_1,
            events=[_make_event_payload(
                event_type="emotion_detected",
                session_id=session_1,
                data={"scores": {"happy": 0.9}},
            )],
        )
        batch2 = _make_event_batch(
            session_id=session_2,
            events=[_make_event_payload(
                event_type="emotion_detected",
                session_id=session_2,
                data={"scores": {"sad": 0.9}},
            )],
        )

        await test_client.post("/api/video/event", json=batch1)
        await test_client.post("/api/video/event", json=batch2)

        # Check aggregates are different
        resp1 = await test_client.get(f"/api/video/aggregate/{session_1}")
        resp2 = await test_client.get(f"/api/video/aggregate/{session_2}")

        assert resp1.json()["dominant_emotion"] == "happy"
        assert resp2.json()["dominant_emotion"] == "sad"
