from __future__ import annotations

import asyncio
import io
import json
import os
import re
import struct
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Any

import aiohttp
import websockets
from fastapi import HTTPException, WebSocket
from langchain.messages import AIMessageChunk, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from starlette.websockets import WebSocketState

from server.utils.auth_utils import AuthUtils
from src.agents import agent_manager
from src.agents.interview_agent.context import InterviewContext
from src.repositories.conversation_repository import ConversationRepository
from src.services.chat_stream_service import (
    _build_effective_agent_config,
    _resolve_agent_config,
    _sync_interview_case_memory_if_needed,
    enrich_agent_state_with_conversation_metadata,
    extract_agent_state,
    get_agent_state_view,
    save_messages_from_langgraph_state,
)
from src.services.conversation_service import create_thread_view, require_user_conversation
from src.services.history_query_service import get_agent_history_view
from src.storage.postgres.manager import pg_manager
from src.storage.postgres.models_business import User
from src.utils.logging_config import logger

DOUBAO_TTS_WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
DOUBAO_DEFAULT_SPEAKER = "zh_male_m191_uranus_bigtts"
DOUBAO_DEFAULT_RESOURCE_ID = "seed-tts-2.0"
DOUBAO_SAMPLE_RATE = 24000
DOUBAO_CHAR_DELAY_SECONDS = 0.005
VOICE_SESSION_TOKEN_TTL_SECONDS = 60 * 60 * 4
VOICE_DELIVERY_MODE = "voice_direct"

PROTOCOL_VERSION = 0b0001
FULL_CLIENT_REQUEST = 0b0001
FULL_SERVER_RESPONSE = 0b1001
AUDIO_ONLY_RESPONSE = 0b1011
SERVER_ERROR_RESPONSE = 0b1111
WITH_EVENT = 0b0100
JSON_SERIALIZATION = 0b0001
NO_SERIALIZATION = 0b0000
NO_COMPRESSION = 0b0000

EVENT_START_CONNECTION = 1
EVENT_FINISH_CONNECTION = 2
EVENT_CONNECTION_STARTED = 50
EVENT_CONNECTION_FAILED = 51
EVENT_CONNECTION_FINISHED = 52
EVENT_START_SESSION = 100
EVENT_CANCEL_SESSION = 101
EVENT_FINISH_SESSION = 102
EVENT_SESSION_STARTED = 150
EVENT_SESSION_CANCELED = 151
EVENT_SESSION_FINISHED = 152
EVENT_SESSION_FAILED = 153
EVENT_TASK_REQUEST = 200
EVENT_TTS_RESPONSE = 352

VOICE_OPENING_PROMPT_TEMPLATE = (
    "现在开始一轮{position}{round_name}模拟面试。"
    "你必须始终以面试官身份发言，不要代替候选人作答。"
    "请维护固定 7 个阶段 todo：1.读取简历并确认岗位背景；2.发起开场并请候选人自我介绍；"
    "3.追问项目经历与技术细节；4.相关技术知识提问；5.代码考核；6.评估岗位匹配度与风险点；7.输出总结与评分卡。"
    "如果当前会话里有附件，先读取附件简历；如果没有附件，只允许调用一次 query_kb 查询“我的简历”知识。"
    "第 4 阶段每次发技术题前都调用 pick_random_technical_question，并传入 excluded_questions 避免重复。"
    "当第 4 阶段完成时，调用 start_code_assessment 启动代码考核，并明确引导用户进入代码工作台。"
    "代码考核阶段除非用户明确请求提示，否则不要主动点评代码。"
)


class VoiceSessionStartPayload(BaseModel):
    agent_id: str
    position: str | None = None
    round: str | None = None
    thread_id: str | None = None
    force_new_thread: bool = False


class VoiceSessionClaims(BaseModel):
    session_type: str
    voice_session_id: str
    thread_id: str
    agent_id: str
    position: str
    round_name: str


class DoubaoMsgType(IntEnum):
    Invalid = 0
    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111


class DoubaoMsgTypeFlagBits(IntEnum):
    NoSeq = 0
    PositiveSeq = 0b1
    LastNoSeq = 0b10
    NegativeSeq = 0b11
    WithEvent = 0b100


class DoubaoVersionBits(IntEnum):
    Version1 = 1


class DoubaoHeaderSizeBits(IntEnum):
    HeaderSize4 = 1


class DoubaoSerializationBits(IntEnum):
    Raw = 0
    JSON = 0b1


class DoubaoCompressionBits(IntEnum):
    None_ = 0


class DoubaoEventType(IntEnum):
    StartConnection = 1
    FinishConnection = 2
    ConnectionStarted = 50
    ConnectionFailed = 51
    ConnectionFinished = 52
    StartSession = 100
    CancelSession = 101
    FinishSession = 102
    SessionStarted = 150
    SessionCanceled = 151
    SessionFinished = 152
    SessionFailed = 153
    TaskRequest = 200
    TTSSentenceStart = 350
    TTSSentenceEnd = 351
    TTSResponse = 352


@dataclass
class DoubaoMessage:
    version: DoubaoVersionBits = DoubaoVersionBits.Version1
    header_size: DoubaoHeaderSizeBits = DoubaoHeaderSizeBits.HeaderSize4
    type: DoubaoMsgType = DoubaoMsgType.Invalid
    flag: DoubaoMsgTypeFlagBits = DoubaoMsgTypeFlagBits.NoSeq
    serialization: DoubaoSerializationBits = DoubaoSerializationBits.JSON
    compression: DoubaoCompressionBits = DoubaoCompressionBits.None_
    event: DoubaoEventType | int = 0
    session_id: str = ""
    connect_id: str = ""
    sequence: int = 0
    error_code: int = 0
    payload: bytes = b""

    @classmethod
    def from_bytes(cls, data: bytes) -> "DoubaoMessage":
        type_and_flag = data[1]
        msg_type = DoubaoMsgType(type_and_flag >> 4)
        flag = DoubaoMsgTypeFlagBits(type_and_flag & 0b00001111)
        msg = cls(type=msg_type, flag=flag)
        msg.unmarshal(data)
        return msg

    def unmarshal(self, data: bytes) -> None:
        buffer = io.BytesIO(data)
        version_and_header_size = buffer.read(1)[0]
        self.version = DoubaoVersionBits(version_and_header_size >> 4)
        self.header_size = DoubaoHeaderSizeBits(version_and_header_size & 0b00001111)
        buffer.read(1)
        serialization_compression = buffer.read(1)[0]
        self.serialization = DoubaoSerializationBits(serialization_compression >> 4)
        self.compression = DoubaoCompressionBits(serialization_compression & 0b00001111)
        header_size = 4 * self.header_size
        if padding_size := header_size - 3:
            buffer.read(padding_size)
        if self.type in [
            DoubaoMsgType.FullClientRequest,
            DoubaoMsgType.FullServerResponse,
            DoubaoMsgType.FrontEndResultServer,
            DoubaoMsgType.AudioOnlyClient,
            DoubaoMsgType.AudioOnlyServer,
        ] and self.flag in [DoubaoMsgTypeFlagBits.PositiveSeq, DoubaoMsgTypeFlagBits.NegativeSeq]:
            sequence_bytes = buffer.read(4)
            if sequence_bytes:
                self.sequence = struct.unpack(">i", sequence_bytes)[0]
        elif self.type == DoubaoMsgType.Error:
            error_code_bytes = buffer.read(4)
            if error_code_bytes:
                self.error_code = struct.unpack(">I", error_code_bytes)[0]

        if self.flag == DoubaoMsgTypeFlagBits.WithEvent:
            event_bytes = buffer.read(4)
            if event_bytes:
                self.event = struct.unpack(">i", event_bytes)[0]
            if self.event not in [
                DoubaoEventType.StartConnection,
                DoubaoEventType.FinishConnection,
                DoubaoEventType.ConnectionStarted,
                DoubaoEventType.ConnectionFailed,
                DoubaoEventType.ConnectionFinished,
            ]:
                size_bytes = buffer.read(4)
                if size_bytes:
                    size = struct.unpack(">I", size_bytes)[0]
                    if size > 0:
                        self.session_id = buffer.read(size).decode("utf-8")
            elif self.event in [
                DoubaoEventType.ConnectionStarted,
                DoubaoEventType.ConnectionFailed,
                DoubaoEventType.ConnectionFinished,
            ]:
                size_bytes = buffer.read(4)
                if size_bytes:
                    size = struct.unpack(">I", size_bytes)[0]
                    if size > 0:
                        self.connect_id = buffer.read(size).decode("utf-8")

        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                self.payload = buffer.read(size)


async def doubao_receive_message(websocket) -> DoubaoMessage:
    data = await websocket.recv()
    if isinstance(data, str):
        raise ValueError(f"Unexpected text message: {data}")
    return DoubaoMessage.from_bytes(data)


async def doubao_send_event_request(websocket, event: DoubaoEventType, payload: bytes, session_id: str = "") -> None:
    msg = DoubaoMessage(type=DoubaoMsgType.FullClientRequest, flag=DoubaoMsgTypeFlagBits.WithEvent)
    msg.event = event
    msg.session_id = session_id
    msg.payload = payload

    buffer = io.BytesIO()
    header = [
        (msg.version << 4) | msg.header_size,
        (msg.type << 4) | msg.flag,
        (msg.serialization << 4) | msg.compression,
    ]
    if padding := 4 * msg.header_size - len(header):
        header.extend([0] * padding)
    buffer.write(bytes(header))
    buffer.write(struct.pack(">i", int(msg.event)))
    if event not in [
        DoubaoEventType.StartConnection,
        DoubaoEventType.FinishConnection,
        DoubaoEventType.ConnectionStarted,
        DoubaoEventType.ConnectionFailed,
    ]:
        session_id_bytes = session_id.encode("utf-8")
        buffer.write(struct.pack(">I", len(session_id_bytes)))
        if session_id_bytes:
            buffer.write(session_id_bytes)
    buffer.write(struct.pack(">I", len(payload)))
    buffer.write(payload)
    await websocket.send(buffer.getvalue())


async def doubao_start_connection(websocket) -> None:
    await doubao_send_event_request(websocket, DoubaoEventType.StartConnection, b"{}")


async def doubao_finish_connection(websocket) -> None:
    await doubao_send_event_request(websocket, DoubaoEventType.FinishConnection, b"{}")


async def doubao_start_session(websocket, payload: bytes, session_id: str) -> None:
    await doubao_send_event_request(websocket, DoubaoEventType.StartSession, payload, session_id)


async def doubao_finish_session(websocket, session_id: str) -> None:
    await doubao_send_event_request(websocket, DoubaoEventType.FinishSession, b"{}", session_id)


async def doubao_cancel_session(websocket, session_id: str) -> None:
    await doubao_send_event_request(websocket, DoubaoEventType.CancelSession, b"{}", session_id)


async def doubao_task_request(websocket, payload: bytes, session_id: str) -> None:
    await doubao_send_event_request(websocket, DoubaoEventType.TaskRequest, payload, session_id)


def _generate_header(
    *,
    message_type: int,
    message_flags: int = WITH_EVENT,
    serialization: int = JSON_SERIALIZATION,
    compression: int = NO_COMPRESSION,
) -> bytearray:
    header = bytearray()
    header.append((PROTOCOL_VERSION << 4) | 0b0001)
    header.append((message_type << 4) | message_flags)
    header.append((serialization << 4) | compression)
    header.append(0x00)
    return header


def _build_event_request(event: int, payload: dict[str, Any], *, session_id: str | None = None) -> bytes:
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = bytearray(_generate_header(message_type=FULL_CLIENT_REQUEST))
    request.extend(int(event).to_bytes(4, "big", signed=True))
    if session_id is not None:
        session_bytes = session_id.encode("utf-8")
        request.extend(len(session_bytes).to_bytes(4, "big", signed=False))
        request.extend(session_bytes)
    request.extend(len(payload_bytes).to_bytes(4, "big", signed=False))
    request.extend(payload_bytes)
    return bytes(request)


def _parse_tts_response(raw: bytes | str) -> dict[str, Any]:
    if isinstance(raw, str):
        return {}

    header_size = raw[0] & 0x0F
    message_type = raw[1] >> 4
    message_flags = raw[1] & 0x0F
    serialization = raw[2] >> 4
    payload = raw[header_size * 4 :]

    result: dict[str, Any] = {"message_type": message_type}
    cursor = 0

    if message_type in {FULL_SERVER_RESPONSE, AUDIO_ONLY_RESPONSE}:
        has_sequence = message_flags in {0b0001, 0b0011, 0b0101, 0b0111}
        if has_sequence:
            result["sequence"] = int.from_bytes(payload[cursor : cursor + 4], "big", signed=True)
            cursor += 4
        if message_flags & WITH_EVENT:
            result["event"] = int.from_bytes(payload[cursor : cursor + 4], "big", signed=True)
            cursor += 4

        event = result.get("event")
        if event not in {EVENT_START_CONNECTION, EVENT_FINISH_CONNECTION, EVENT_CONNECTION_STARTED, EVENT_CONNECTION_FAILED, EVENT_CONNECTION_FINISHED}:
            field_size = int.from_bytes(payload[cursor : cursor + 4], "big", signed=False)
            cursor += 4
            result["session_id"] = payload[cursor : cursor + field_size].decode("utf-8", errors="ignore")
            cursor += field_size
        elif event in {EVENT_CONNECTION_STARTED, EVENT_CONNECTION_FAILED, EVENT_CONNECTION_FINISHED}:
            field_size = int.from_bytes(payload[cursor : cursor + 4], "big", signed=False)
            cursor += 4
            result["connection_id"] = payload[cursor : cursor + field_size].decode("utf-8", errors="ignore")
            cursor += field_size

        payload_size = int.from_bytes(payload[cursor : cursor + 4], "big", signed=False)
        cursor += 4
        payload_msg = payload[cursor : cursor + payload_size]
        if serialization == JSON_SERIALIZATION:
            try:
                result["payload_msg"] = json.loads(payload_msg.decode("utf-8"))
            except Exception:
                result["payload_msg"] = {}
        else:
            result["payload_msg"] = payload_msg
        return result

    if message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8 : 8 + payload_size]
        result["code"] = code
        try:
            result["payload_msg"] = json.loads(payload_msg.decode("utf-8"))
        except Exception:
            result["payload_msg"] = payload_msg.decode("utf-8", errors="ignore")
        return result

    return result


def _normalize_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_normalize_text_content(item) for item in content)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        return json.dumps(content, ensure_ascii=False)
    return str(content or "")


def _build_opening_prompt(position: str, round_name: str) -> str:
    return VOICE_OPENING_PROMPT_TEMPLATE.format(position=position, round_name=round_name)


def _normalize_tts_text(content: str) -> str:
    text = str(content or "")
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\*{1,3}", "", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_tts_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        message = str(payload.get("message") or payload.get("error") or "").strip()
        status_code = str(payload.get("status_code") or "").strip()
        normalized_message = message.replace(" ", "")
        if (
            "resourceIDismismatchedwithspeakerrelatedresource" in normalized_message
            or "resourceIDismismatchedwithspeakerrelatedresource" in message
            or "resourceIDismismatchedwithspeakerrelatedresource" in json.dumps(payload, ensure_ascii=False)
            or "resourceidisismatchedwithspeakerrelatedresource" in normalized_message.lower()
            or "resourceidismismatchedwithspeakerrelatedresource" in normalized_message.lower()
            or "resourceidis" in normalized_message.lower() and "speakerrelatedresource" in normalized_message.lower()
            or "resourceidis" in json.dumps(payload, ensure_ascii=False).replace(" ", "").lower()
            or "resourceidismismatchedwithspeakerrelatedresource" in json.dumps(payload, ensure_ascii=False).replace(" ", "").lower()
            or "resourceidisismatchedwithspeakerrelatedresource" in json.dumps(payload, ensure_ascii=False).replace(" ", "").lower()
            or "resourceidismismatchedwithspeakerrelatedresource" in message.replace(" ", "").lower()
            or "mismatchedwithspeakerrelatedresource" in normalized_message.lower()
        ):
            return "当前豆包资源与所选音色不匹配，请检查 resource_id 和 speaker 配置"
        if status_code and message:
            return f"{message} ({status_code})"
        if message:
            return message
        return json.dumps(payload, ensure_ascii=False)

    message = str(payload or "").strip()
    normalized_message = message.replace(" ", "").lower()
    if (
        "resourceidismismatchedwithspeakerrelatedresource" in normalized_message
        or "resourceidisismatchedwithspeakerrelatedresource" in normalized_message
        or "mismatchedwithspeakerrelatedresource" in normalized_message
    ):
        return "当前豆包资源与所选音色不匹配，请检查 resource_id 和 speaker 配置"
    return message


async def _get_user_from_access_token(token: str, db) -> User:
    try:
        payload = AuthUtils.verify_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("missing sub")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="无效的语音会话凭证") from exc

    result = await db.execute(select(User).filter(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def _create_voice_session_id(*, thread_id: str, agent_id: str, position: str, round_name: str) -> str:
    return AuthUtils.create_access_token(
        {
            "session_type": "voice_interview",
            "voice_session_id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "agent_id": agent_id,
            "position": position,
            "round_name": round_name,
        },
        expires_delta=timedelta(seconds=VOICE_SESSION_TOKEN_TTL_SECONDS),
    )


def _decode_voice_session_id(voice_session_id: str) -> VoiceSessionClaims:
    try:
        payload = AuthUtils.verify_access_token(voice_session_id)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="语音会话已失效") from exc

    if payload.get("session_type") != "voice_interview":
        raise HTTPException(status_code=401, detail="无效的语音会话标识")

    return VoiceSessionClaims(
        session_type="voice_interview",
        voice_session_id=str(payload.get("voice_session_id") or ""),
        thread_id=str(payload.get("thread_id") or ""),
        agent_id=str(payload.get("agent_id") or ""),
        position=str(payload.get("position") or ""),
        round_name=str(payload.get("round_name") or ""),
    )


class DoubaoBidirectionalTTSClient:
    def __init__(self) -> None:
        self.app_id = os.getenv("DOUBAO_VOICE_APP_ID", "").strip()
        self.api_key = os.getenv("DOUBAO_VOICE_API_KEY", "").strip()
        if not self.app_id or not self.api_key:
            raise RuntimeError("缺少 DOUBAO_VOICE_APP_ID 或 DOUBAO_VOICE_API_KEY")

        self.resource_id = DOUBAO_DEFAULT_RESOURCE_ID
        self._connect_id = str(uuid.uuid4())
        self._ws = None

    async def connect(self) -> None:
        logger.info(
            f"Connecting Doubao bidirectional TTS with resource_id={self.resource_id}, "
            f"speaker={DOUBAO_DEFAULT_SPEAKER}"
        )
        self._ws = await websockets.connect(
            DOUBAO_TTS_WS_URL,
            additional_headers={
                "X-Api-App-Key": self.app_id,
                "X-Api-Access-Key": self.api_key,
                "X-Api-Resource-Id": self.resource_id,
                "X-Api-Connect-Id": self._connect_id,
            },
            max_size=10 * 1024 * 1024,
        )
        await doubao_start_connection(self._ws)
        response = await self.receive_response()
        if response.get("event") != EVENT_CONNECTION_STARTED:
            raise RuntimeError("豆包 TTS 建连失败")

    async def start_session(self, session_id: str, *, user_id: str) -> None:
        payload = {
            "user": {"uid": user_id},
            "namespace": "BidirectionalTTS",
            "event": EVENT_START_SESSION,
            "req_params": {
                "speaker": DOUBAO_DEFAULT_SPEAKER,
                "audio_params": {
                    "format": "pcm",
                    "sample_rate": DOUBAO_SAMPLE_RATE,
                    "enable_timestamp": True,
                },
                "additions": json.dumps(
                    {
                        "disable_markdown_filter": False,
                    },
                    ensure_ascii=False,
                ),
            },
        }
        await doubao_start_session(
            self._ws,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            session_id,
        )

    async def send_task_text(self, session_id: str, content: str, *, user_id: str) -> None:
        if not content:
            return
        for char in content:
            payload = {
                "user": {"uid": user_id},
                "namespace": "BidirectionalTTS",
                "event": EVENT_TASK_REQUEST,
                "req_params": {
                    "speaker": DOUBAO_DEFAULT_SPEAKER,
                    "audio_params": {
                        "format": "pcm",
                        "sample_rate": DOUBAO_SAMPLE_RATE,
                        "enable_timestamp": True,
                    },
                    "additions": json.dumps(
                        {
                            "disable_markdown_filter": False,
                        },
                        ensure_ascii=False,
                    ),
                    "text": char,
                },
            }
            await doubao_task_request(
                self._ws,
                json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                session_id,
            )
            await asyncio.sleep(DOUBAO_CHAR_DELAY_SECONDS)

    async def finish_session(self, session_id: str) -> None:
        await doubao_finish_session(self._ws, session_id)

    async def cancel_session(self, session_id: str) -> None:
        await doubao_cancel_session(self._ws, session_id)

    async def receive_response(self) -> dict[str, Any]:
        if not self._ws:
            raise RuntimeError("豆包 TTS websocket 未连接")
        msg = await doubao_receive_message(self._ws)
        payload_msg: Any
        if msg.type == DoubaoMsgType.Error:
            try:
                payload_msg = json.loads(msg.payload.decode("utf-8"))
            except Exception:
                payload_msg = msg.payload.decode("utf-8", errors="ignore")
            return {
                "message_type": SERVER_ERROR_RESPONSE,
                "event": int(msg.event),
                "session_id": msg.session_id,
                "payload_msg": payload_msg,
            }

        if msg.serialization.value == 1:
            try:
                payload_msg = json.loads(msg.payload.decode("utf-8"))
            except Exception:
                payload_msg = {}
        else:
            payload_msg = msg.payload

        return {
            "message_type": int(msg.type),
            "event": int(msg.event),
            "session_id": msg.session_id,
            "payload_msg": payload_msg,
        }

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await doubao_finish_connection(self._ws)
            except Exception:
                pass
            await self._ws.close()
            self._ws = None


async def start_voice_interview_session(
    *,
    payload: VoiceSessionStartPayload,
    current_user: User,
    db,
) -> dict[str, Any]:
    position, round_name = InterviewContext.normalize_runtime_values(payload.position, payload.round)
    agent_id = str(payload.agent_id or "").strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id 不能为空")

    conv_repo = ConversationRepository(db)
    thread_id = str(payload.thread_id or "").strip()

    if payload.force_new_thread or not thread_id:
        thread = await create_thread_view(
            agent_id=agent_id,
            title=f"{position} · {round_name}",
            metadata={
                "interview_mode": "voice",
                "target_position": position,
                "interview_round": round_name,
            },
            db=db,
            current_user_id=str(current_user.id),
        )
        thread_id = thread["id"]
    else:
        conversation = await require_user_conversation(conv_repo, thread_id, str(current_user.id))
        if conversation.agent_id != agent_id:
            raise HTTPException(status_code=400, detail="线程所属智能体不匹配")
        await conv_repo.update_conversation(
            thread_id,
            title=f"{position} · {round_name}",
            metadata={
                "interview_mode": "voice",
                "target_position": position,
                "interview_round": round_name,
            },
        )

    return {
        "thread_id": thread_id,
        "voice_session_id": _create_voice_session_id(
            thread_id=thread_id,
            agent_id=agent_id,
            position=position,
            round_name=round_name,
        ),
        "agent_id": agent_id,
        "position": position,
        "round": round_name,
    }


async def _persist_user_message(*, thread_id: str, content: str, db, hidden_from_history: bool = False) -> None:
    conv_repo = ConversationRepository(db)
    await conv_repo.add_message_by_thread_id(
        thread_id=thread_id,
        role="user",
        content=content,
        message_type="text",
        extra_metadata={
            "voice_input_mode": "text",
            "hidden_from_history": hidden_from_history,
        },
    )


class VoiceInterviewBridge:
    def __init__(self, *, websocket: WebSocket, claims: VoiceSessionClaims, user: User) -> None:
        self.websocket = websocket
        self.claims = claims
        self.user = user
        self.doubao = DoubaoBidirectionalTTSClient()
        self._client_send_lock = asyncio.Lock()
        self._turn_lock = asyncio.Lock()
        self._turn_task: asyncio.Task | None = None
        self._active_session_id = ""
        self._tts_started_future: asyncio.Future | None = None
        self._tts_finished_future: asyncio.Future | None = None
        self._session_watchdog_task: asyncio.Task | None = None

    async def run(self) -> None:
        await self.websocket.accept()
        await self.doubao.connect()
        await self._send_event(
            "session_ready",
            thread_id=self.claims.thread_id,
            agent_id=self.claims.agent_id,
            position=self.claims.position,
            round=self.claims.round_name,
        )
        await self._send_initial_history()

        client_task = asyncio.create_task(self._client_loop())
        doubao_task = asyncio.create_task(self._doubao_loop())
        done, pending = await asyncio.wait({client_task, doubao_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()

    async def close(self) -> None:
        await self._interrupt_current_turn(notify=False)
        if self._session_watchdog_task and not self._session_watchdog_task.done():
            self._session_watchdog_task.cancel()
        await self.doubao.close()
        try:
            await self.websocket.close()
        except Exception:
            pass

    async def _send_event(self, event_type: str, **payload: Any) -> None:
        async with self._client_send_lock:
            await self.websocket.send_text(json.dumps({"type": event_type, **payload}, ensure_ascii=False))

    async def _send_initial_history(self) -> None:
        async with pg_manager.get_async_session_context() as db:
            history_payload = await get_agent_history_view(
                agent_id=self.claims.agent_id,
                thread_id=self.claims.thread_id,
                current_user_id=str(self.user.id),
                db=db,
            )
            agent_state_response = await get_agent_state_view(
                agent_id=self.claims.agent_id,
                thread_id=self.claims.thread_id,
                current_user_id=str(self.user.id),
                db=db,
            )

        agent_state = agent_state_response.get("agent_state") or {}
        await self._send_event("history_loaded", history=history_payload.get("history") or [])
        await self._send_event("agent_state", agent_state=agent_state)
        await self._maybe_send_coding_redirect(agent_state)

    async def _maybe_send_coding_redirect(self, agent_state: dict[str, Any]) -> None:
        coding_session = agent_state.get("coding_session")
        if isinstance(coding_session, dict) and coding_session.get("status") in {"ready", "coding"}:
            await self._send_event(
                "coding_redirect",
                thread_id=self.claims.thread_id,
                position=self.claims.position,
                round=self.claims.round_name,
            )

    async def _client_loop(self) -> None:
        while True:
            raw = await self.websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await self._send_event("error", message="无效的语音会话消息")
                continue

            message_type = str(payload.get("type") or "").strip()
            if message_type == "start_interview":
                await self._start_turn(_build_opening_prompt(self.claims.position, self.claims.round_name), is_opening=True)
            elif message_type == "user_text":
                content = str(payload.get("content") or "").strip()
                if content:
                    await self._start_turn(content, is_opening=False)
            elif message_type == "interrupt":
                await self._interrupt_current_turn(notify=True)
            elif message_type == "finish":
                break

    async def _start_turn(self, query: str, *, is_opening: bool) -> None:
        async with self._turn_lock:
            if (self._turn_task and not self._turn_task.done()) or self._active_session_id:
                await self._send_event("error", message="请等待当前面试官回复结束")
                return
            self._turn_task = asyncio.create_task(self._run_turn_wrapper(query=query, is_opening=is_opening))

    async def _run_turn_wrapper(self, *, query: str, is_opening: bool) -> None:
        try:
            await self._run_agent_turn(query=query, is_opening=is_opening)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Voice interview turn failed: %r", exc, exc_info=True)
            await self._send_event("error", message=str(exc) or exc.__class__.__name__)
        finally:
            self._turn_task = None

    async def _run_agent_turn(self, *, query: str, is_opening: bool) -> None:
        agent = agent_manager.get_agent(self.claims.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"智能体 {self.claims.agent_id} 不存在")
        if not self.user.department_id:
            raise HTTPException(status_code=400, detail="当前用户未绑定部门")

        async with pg_manager.get_async_session_context() as db:
            conv_repo = ConversationRepository(db)
            runtime_config = {
                "context_overrides": {
                    "target_position": self.claims.position,
                    "interview_round": self.claims.round_name,
                }
            }
            config_item, agent_config_id = await _resolve_agent_config(
                db,
                self.claims.agent_id,
                self.user.department_id,
                str(self.user.id),
                None,
            )
            agent_config = _build_effective_agent_config(self.claims.agent_id, config_item, runtime_config)
            agent_config["delivery_mode"] = VOICE_DELIVERY_MODE
            input_context = {
                "user_id": str(self.user.id),
                "thread_id": self.claims.thread_id,
                "department_id": self.user.department_id,
                "agent_config_id": agent_config_id,
                "agent_config": agent_config,
                "target_position": self.claims.position,
                "interview_round": self.claims.round_name,
                "delivery_mode": VOICE_DELIVERY_MODE,
            }
            langgraph_config = {
                "configurable": {
                    "thread_id": self.claims.thread_id,
                    "user_id": str(self.user.id),
                }
            }

            await _persist_user_message(
                thread_id=self.claims.thread_id,
                content=query,
                db=db,
                hidden_from_history=is_opening,
            )
            if not is_opening:
                await self._send_event("user_message", content=query)

            async def speak_text_chunk(text: str) -> None:
                session_id = str(uuid.uuid4())
                self._active_session_id = session_id
                self._tts_started_future = asyncio.get_running_loop().create_future()
                self._tts_finished_future = asyncio.get_running_loop().create_future()
                await self.doubao.start_session(session_id, user_id=str(self.user.id))
                try:
                    await asyncio.wait_for(self._tts_started_future, timeout=10)
                except asyncio.TimeoutError as exc:
                    self._active_session_id = ""
                    raise RuntimeError("豆包 TTS 会话启动超时") from exc

                await self.doubao.send_task_text(session_id, text, user_id=str(self.user.id))
                await self.doubao.finish_session(session_id)
                self._arm_session_watchdog(session_id)
                try:
                    await asyncio.wait_for(self._tts_finished_future, timeout=30)
                except asyncio.TimeoutError as exc:
                    raise RuntimeError("豆包 TTS 会话结束超时") from exc

            accumulated_content: list[str] = []
            tts_buffer = ""
            async for msg, _metadata in agent.stream_messages([HumanMessage(content=query)], input_context=input_context):
                if isinstance(msg, AIMessageChunk):
                    delta = _normalize_text_content(msg.content)
                    if delta:
                        accumulated_content.append(delta)
                        await self._send_event("assistant_delta", content=delta)
                        cleaned_delta = _normalize_tts_text(delta)
                        if cleaned_delta:
                            tts_buffer += cleaned_delta
                            sentence_break = max(tts_buffer.rfind("。"), tts_buffer.rfind("！"), tts_buffer.rfind("？"))
                            if sentence_break >= 0:
                                chunk = tts_buffer[: sentence_break + 1].strip()
                                tts_buffer = tts_buffer[sentence_break + 1 :].strip()
                                if chunk:
                                    logger.info("Sending TTS chunk: %s", chunk)
                                    await speak_text_chunk(chunk)
                    continue

                msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else {}
                if msg_dict.get("type") == "tool":
                    graph = await agent.get_graph()
                    state = await graph.aget_state(langgraph_config)
                    agent_state = extract_agent_state(getattr(state, "values", {})) if state else {}
                    agent_state = await enrich_agent_state_with_conversation_metadata(
                        conv_repo,
                        thread_id=self.claims.thread_id,
                        agent_state=agent_state,
                    )
                    if agent_state:
                        await self._send_event("agent_state", agent_state=agent_state)
                        await self._maybe_send_coding_redirect(agent_state)

            final_text = "".join(accumulated_content).strip()
            remaining_tts_text = _normalize_tts_text(tts_buffer)
            if remaining_tts_text:
                logger.info("Sending final TTS chunk: %s", remaining_tts_text)
                await speak_text_chunk(remaining_tts_text)

            graph = await agent.get_graph()
            state = await graph.aget_state(langgraph_config)
            agent_state = extract_agent_state(getattr(state, "values", {})) if state else {}
            agent_state = await enrich_agent_state_with_conversation_metadata(
                conv_repo,
                thread_id=self.claims.thread_id,
                agent_state=agent_state,
            )
            if agent_state:
                await self._send_event("agent_state", agent_state=agent_state)
                await self._maybe_send_coding_redirect(agent_state)

            await save_messages_from_langgraph_state(
                agent_instance=agent,
                thread_id=self.claims.thread_id,
                conv_repo=conv_repo,
                config_dict=langgraph_config,
            )
            await _sync_interview_case_memory_if_needed(
                agent_id=self.claims.agent_id,
                user_id=str(self.user.id),
                thread_id=self.claims.thread_id,
                user_query=query,
                assistant_content=final_text,
            )
            if final_text:
                await self._send_event("assistant_final", content=final_text)

    async def _interrupt_current_turn(self, *, notify: bool) -> None:
        async with self._turn_lock:
            turn_task = self._turn_task
            session_id = self._active_session_id
            if session_id:
                try:
                    await self.doubao.cancel_session(session_id)
                except Exception:
                    pass
            if turn_task and not turn_task.done():
                turn_task.cancel()
            if notify:
                await self._send_event("interrupted", message="已停止当前播报")

    def _fail_active_tts_session(self, error: str) -> None:
        if self._session_watchdog_task and not self._session_watchdog_task.done():
            self._session_watchdog_task.cancel()
        if self._tts_started_future and not self._tts_started_future.done():
            self._tts_started_future.set_exception(RuntimeError(error))
        if self._tts_finished_future and not self._tts_finished_future.done():
            self._tts_finished_future.set_exception(RuntimeError(error))
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
        self._active_session_id = ""

    def _arm_session_watchdog(self, session_id: str) -> None:
        if self._session_watchdog_task and not self._session_watchdog_task.done():
            self._session_watchdog_task.cancel()
        self._session_watchdog_task = asyncio.create_task(self._watch_session_finish(session_id))

    async def _watch_session_finish(self, session_id: str) -> None:
        try:
            await asyncio.sleep(120)
        except asyncio.CancelledError:
            return

        if self._active_session_id != session_id:
            return

        logger.warning("Doubao TTS session did not finish in time, releasing session lock: %s", session_id)
        self._active_session_id = ""
        if self._tts_finished_future and not self._tts_finished_future.done():
            self._tts_finished_future.set_result({"status_code": "watchdog_release"})

    async def _doubao_loop(self) -> None:
        while True:
            response = await self.doubao.receive_response()
            if not response:
                continue

            if response.get("message_type") == SERVER_ERROR_RESPONSE:
                payload_msg = response.get("payload_msg")
                message = _format_tts_error_message(payload_msg)
                self._fail_active_tts_session(message or "豆包 TTS 服务异常")
                await self._send_event(
                    "error",
                    message=message or "豆包 TTS 服务异常",
                    resource_id=self.doubao.resource_id,
                    speaker=DOUBAO_DEFAULT_SPEAKER,
                )
                continue

            event = response.get("event")
            session_id = str(response.get("session_id") or "")
            payload_msg = response.get("payload_msg")

            if event == EVENT_SESSION_STARTED and session_id == self._active_session_id and self._tts_started_future:
                logger.info("Doubao TTS session started: %s", session_id)
                if not self._tts_started_future.done():
                    self._tts_started_future.set_result(payload_msg or {})
                continue

            if event in {EVENT_SESSION_CANCELED, EVENT_SESSION_FINISHED} and session_id == self._active_session_id:
                logger.info("Doubao TTS session finished: %s, event=%s", session_id, event)
                if self._session_watchdog_task and not self._session_watchdog_task.done():
                    self._session_watchdog_task.cancel()
                if self._tts_finished_future and not self._tts_finished_future.done():
                    self._tts_finished_future.set_result(payload_msg or {})
                self._active_session_id = ""
                continue

            if event == EVENT_SESSION_FAILED and session_id == self._active_session_id:
                error = _format_tts_error_message(payload_msg)
                self._fail_active_tts_session(error or "豆包 TTS 会话失败")
                await self._send_event(
                    "error",
                    message=error or "豆包 TTS 会话失败",
                    resource_id=self.doubao.resource_id,
                    speaker=DOUBAO_DEFAULT_SPEAKER,
                )
                continue

            if event == EVENT_TTS_RESPONSE and isinstance(payload_msg, (bytes, bytearray)):
                logger.info(
                    f"Doubao TTS audio chunk received: session_id={session_id}, size={len(payload_msg)}"
                )
                async with self._client_send_lock:
                    await self.websocket.send_bytes(bytes(payload_msg))
                logger.info(
                    f"Voice WS audio chunk forwarded to client: session_id={session_id}, size={len(payload_msg)}"
                )
                continue

            if event in {350, 351}:
                logger.info("Doubao sentence event: event=%s, payload=%s", event, payload_msg)
                continue

            logger.info(
                f"Unhandled Doubao response: type={response.get('message_type')}, "
                f"event={event}, session_id={session_id}, payload_type={type(payload_msg).__name__}"
            )


async def voice_interview_websocket_endpoint(*, websocket: WebSocket, voice_session_id: str, token: str) -> None:
    bridge: VoiceInterviewBridge | None = None
    try:
        claims = _decode_voice_session_id(voice_session_id)
        async with pg_manager.get_async_session_context() as db:
            user = await _get_user_from_access_token(token, db)
            conv_repo = ConversationRepository(db)
            conversation = await require_user_conversation(conv_repo, claims.thread_id, str(user.id))
            if conversation.agent_id != claims.agent_id:
                raise HTTPException(status_code=400, detail="线程所属智能体不匹配")

        bridge = VoiceInterviewBridge(websocket=websocket, claims=claims, user=user)
        await bridge.run()
    except HTTPException as exc:
        try:
            if websocket.application_state == WebSocketState.CONNECTING:
                await websocket.accept()
            await websocket.send_text(json.dumps({"type": "error", "message": exc.detail}, ensure_ascii=False))
        finally:
            await websocket.close(code=1008)
    except Exception as exc:
        logger.error("Voice interview websocket error: %s", exc, exc_info=True)
        try:
            if websocket.application_state == WebSocketState.CONNECTING:
                await websocket.accept()
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False))
        except Exception:
            pass
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if bridge is not None:
            await bridge.close()
