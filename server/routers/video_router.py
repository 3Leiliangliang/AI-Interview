"""视频面试分析 API 路由"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.video_event_service import VideoEventService
from src.services.video_report_service import VideoReportService
from src.utils.logging_config import logger

# session_id 格式校验（UUID 或 hex 字符串，防止 Redis key 注入）
_SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]{8,128}$")


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format")

video = APIRouter(prefix="/video", tags=["video"])


class VideoEventPayload(BaseModel):
    event_id: str
    session_id: str
    timestamp: float
    sequence: int
    type: str
    data: dict
    severity: str = "low"


class EventBatchPayload(BaseModel):
    session_id: str
    batch_id: str
    events: list[VideoEventPayload]
    batch_timestamp: float
    batch_sequence: int


def _get_service() -> VideoEventService:
    """获取视频事件服务实例"""
    return VideoEventService()


@video.post("/event")
async def receive_event_batch(batch: EventBatchPayload):
    """接收前端时序事件批次，存储到 Redis"""
    service = _get_service()
    try:
        events_dicts = [event.model_dump() for event in batch.events]
        count = await service.store_events(batch.session_id, events_dicts)
        logger.info(f"Stored {count} video events for session {batch.session_id}")
        return {"status": "ok", "events_count": count}
    finally:
        await service.close()


@video.get("/status/{session_id}")
async def get_video_status(session_id: str):
    """获取视频分析状态"""
    _validate_session_id(session_id)
    service = _get_service()
    try:
        status = await service.get_session_status(session_id)
        return status
    finally:
        await service.close()


@video.get("/aggregate/{session_id}")
async def get_video_aggregate(session_id: str):
    """获取视频分析聚合摘要"""
    _validate_session_id(session_id)
    service = _get_service()
    try:
        aggregate = await service.aggregate_events(session_id)
        return aggregate
    finally:
        await service.close()


@video.post("/report/{session_id}")
async def generate_report(session_id: str):
    """生成面试视频分析报告"""
    _validate_session_id(session_id)
    report_service = VideoReportService()
    try:
        report = await report_service.generate_report(session_id)
        return report
    finally:
        await report_service._event_service.close()
