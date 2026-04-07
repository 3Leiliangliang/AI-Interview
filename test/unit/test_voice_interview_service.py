from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import voice_interview_service as service  # noqa: E402


class DummyDoubaoClient:
    def __init__(self) -> None:
        self.cancelled_session_ids: list[str] = []

    async def cancel_session(self, session_id: str) -> None:
        self.cancelled_session_ids.append(session_id)

    async def close(self) -> None:
        return None


class DummyAsrClient:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.frames: list[bytes] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def send_audio_frame(self, buffer: bytes) -> None:
        self.frames.append(buffer)


def make_bridge(**kwargs) -> service.VoiceInterviewBridge:
    claims = service.VoiceSessionClaims(
        session_type="voice_interview",
        voice_session_id="voice-session",
        thread_id="thread-1",
        agent_id="agent-1",
        position="后端工程师",
        round_name="初试",
    )
    user = SimpleNamespace(id=1, department_id=1)
    return service.VoiceInterviewBridge(
        websocket=SimpleNamespace(),
        claims=claims,
        user=user,
        doubao_client=kwargs.get("doubao_client", DummyDoubaoClient()),
        asr_client_factory=kwargs.get("asr_client_factory"),
    )


@pytest.mark.asyncio
async def test_persist_user_message_marks_speech_mode(monkeypatch):
    captured: dict = {}

    class FakeConversationRepository:
        def __init__(self, db_session) -> None:
            captured["db_session"] = db_session

        async def add_message_by_thread_id(self, thread_id: str, **kwargs) -> None:
            captured["thread_id"] = thread_id
            captured.update(kwargs)

    monkeypatch.setattr(service, "ConversationRepository", FakeConversationRepository)

    await service._persist_user_message(
        thread_id="thread-1",
        content="你好",
        db=object(),
        hidden_from_history=False,
        voice_input_mode="speech",
    )

    assert captured["thread_id"] == "thread-1"
    assert captured["content"] == "你好"
    assert captured["extra_metadata"]["voice_input_mode"] == "speech"


@pytest.mark.asyncio
async def test_candidate_partial_only_emits_partial_event(monkeypatch):
    bridge = make_bridge()
    events: list[tuple[str, dict]] = []
    start_turn_calls: list[dict] = []

    async def fake_send_event(event_type: str, **payload):
        events.append((event_type, payload))

    async def fake_start_turn(query: str, *, is_opening: bool, voice_input_mode: str = "text"):
        start_turn_calls.append(
            {"query": query, "is_opening": is_opening, "voice_input_mode": voice_input_mode}
        )

    monkeypatch.setattr(bridge, "_send_event", fake_send_event)
    monkeypatch.setattr(bridge, "_start_turn", fake_start_turn)

    await bridge._handle_candidate_transcript_partial("实时字幕")

    assert events == [("candidate_transcript_partial", {"content": "实时字幕"})]
    assert start_turn_calls == []


@pytest.mark.asyncio
async def test_candidate_final_starts_agent_turn_with_speech_mode(monkeypatch):
    bridge = make_bridge()
    events: list[tuple[str, dict]] = []
    start_turn_calls: list[dict] = []

    async def fake_send_event(event_type: str, **payload):
        events.append((event_type, payload))

    async def fake_start_turn(query: str, *, is_opening: bool, voice_input_mode: str = "text"):
        start_turn_calls.append(
            {"query": query, "is_opening": is_opening, "voice_input_mode": voice_input_mode}
        )

    monkeypatch.setattr(bridge, "_send_event", fake_send_event)
    monkeypatch.setattr(bridge, "_start_turn", fake_start_turn)

    await bridge._handle_candidate_transcript_final("最终修正文本")

    assert ("candidate_transcript_final", {"content": "最终修正文本"}) in events
    assert start_turn_calls == [
        {"query": "最终修正文本", "is_opening": False, "voice_input_mode": "speech"}
    ]


@pytest.mark.asyncio
async def test_start_candidate_capture_rejected_while_assistant_busy(monkeypatch):
    bridge = make_bridge(asr_client_factory=lambda **kwargs: DummyAsrClient())
    bridge._active_session_id = "tts-session"
    events: list[tuple[str, dict]] = []

    async def fake_send_event(event_type: str, **payload):
        events.append((event_type, payload))

    monkeypatch.setattr(bridge, "_send_event", fake_send_event)

    await bridge._start_candidate_capture()

    assert ("candidate_capture_state", {"state": "disabled"}) in events
    assert ("error", {"message": "请等待当前面试官回复结束"}) in events
    assert bridge._candidate_asr is None


@pytest.mark.asyncio
async def test_interrupt_current_turn_stops_tts_and_asr(monkeypatch):
    doubao_client = DummyDoubaoClient()
    asr_client = DummyAsrClient()
    bridge = make_bridge(doubao_client=doubao_client)
    bridge._candidate_asr = asr_client
    bridge._active_session_id = "tts-session"
    bridge._turn_task = asyncio.create_task(asyncio.sleep(60))
    events: list[tuple[str, dict]] = []

    async def fake_send_event(event_type: str, **payload):
        events.append((event_type, payload))

    monkeypatch.setattr(bridge, "_send_event", fake_send_event)

    await bridge._interrupt_current_turn(notify=True)
    await asyncio.sleep(0)

    assert asr_client.stopped is True
    assert doubao_client.cancelled_session_ids == ["tts-session"]
    assert bridge._turn_task.cancelled() or bridge._turn_task.done()
    assert ("interrupted", {"message": "已停止当前播报"}) in events
