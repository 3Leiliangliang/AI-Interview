"""视频事件存储服务 - 使用 Redis 存储时序事件流"""

from __future__ import annotations

import json
import math
import os
from typing import Any

import redis.asyncio as aioredis

from src.utils.logging_config import logger


class VideoEventService:
    """视频分析事件的 Redis 存储服务"""

    EVENT_KEY_PREFIX = "video:events:"
    EVENT_TTL = 300  # 5分钟 TTL

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url)
        return self._redis

    async def store_events(self, session_id: str, events: list[dict]) -> int:
        """存储事件批次到 Redis List"""
        if not events:
            return 0

        r = await self._get_redis()
        key = f"{self.EVENT_KEY_PREFIX}{session_id}"

        pipe = r.pipeline()
        for event in events:
            pipe.lpush(key, json.dumps(event, ensure_ascii=False))
        pipe.expire(key, self.EVENT_TTL)
        await pipe.execute()

        return len(events)

    async def get_recent_events(self, session_id: str, count: int = 100) -> list[dict]:
        """获取最近的事件"""
        r = await self._get_redis()
        key = f"{self.EVENT_KEY_PREFIX}{session_id}"
        raw_events = await r.lrange(key, 0, count - 1)
        return [json.loads(e) for e in raw_events]

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        """获取会话的视频分析状态"""
        r = await self._get_redis()
        key = f"{self.EVENT_KEY_PREFIX}{session_id}"
        count = await r.llen(key)
        return {
            "session_id": session_id,
            "events_in_buffer": count,
            "status": "active" if count > 0 else "inactive",
        }

    async def aggregate_events(self, session_id: str) -> dict[str, Any]:
        """聚合最近事件为结构化摘要"""
        events = await self.get_recent_events(session_id)
        if not events:
            return {"has_data": False}

        return self._aggregate_event_list(events)

    def _aggregate_event_list(self, events: list[dict]) -> dict[str, Any]:
        """从事件列表聚合为结构化摘要"""
        if not events:
            return {"has_data": False}

        # 情绪聚合
        emotion_scores: dict[str, float] = {}
        for idx, event in enumerate(events):
            if event.get("type") != "emotion_detected":
                continue

            # Redis 使用 LPUSH，index 越小越新。给越新的情绪更高权重，提高灵敏度。
            recency_weight = math.exp(-idx / 20)
            for emo, score in event.get("data", {}).get("scores", {}).items():
                try:
                    numeric_score = float(score)
                except (TypeError, ValueError):
                    continue
                emotion_scores[emo] = emotion_scores.get(emo, 0.0) + numeric_score * recency_weight

        dominant_emotion = "neutral"
        if emotion_scores:
            dominant_emotion = max(emotion_scores, key=emotion_scores.get)
            total = sum(emotion_scores.values())
            if total > 0:
                emotion_scores = {k: round(v / total, 3) for k, v in emotion_scores.items()}

        # 姿态聚合
        posture_scores: list[float] = []
        posture_counts: dict[str, int] = {}
        current_posture: str | None = None
        gaze_direction = "center"
        for event in events:
            if event.get("type") == "posture_detected":
                data = event.get("data", {})
                posture_name = str(data.get("posture") or "").strip() or "upright"
                posture_scores.append(data.get("posture_score", 100))
                gaze_direction = data.get("gaze_direction", "center")
                posture_counts[posture_name] = posture_counts.get(posture_name, 0) + 1
                if current_posture is None:
                    current_posture = posture_name
        avg_posture = round(sum(posture_scores) / len(posture_scores), 1) if posture_scores else None
        dominant_posture = max(posture_counts, key=posture_counts.get) if posture_counts else current_posture

        # 注意力聚合
        attention_scores: list[float] = []
        for event in events:
            if event.get("type") == "attention_change":
                attention_scores.append(event.get("data", {}).get("attention_score", 100))
        avg_attention = round(sum(attention_scores) / len(attention_scores), 1) if attention_scores else None

        # 警告（取最近3条）
        recent_alerts = [
            {"type": e.get("data", {}).get("alert_type"), "message": e.get("data", {}).get("message")}
            for e in events
            if e.get("type") == "alert_triggered"
        ][-3:]

        return {
            "has_data": True,
            "dominant_emotion": dominant_emotion,
            "emotion_scores": emotion_scores,
            "avg_posture_score": avg_posture,
            "current_posture": current_posture,
            "dominant_posture": dominant_posture,
            "gaze_direction": gaze_direction,
            "avg_attention_score": avg_attention,
            "recent_alerts": recent_alerts,
            "event_count": len(events),
        }

    async def consume_events_since(
        self,
        session_id: str,
        last_event_count: int = 0,
        count: int = 500,
    ) -> tuple[dict[str, Any], int]:
        """增量消费上次读取后的新事件。

        事件以 LPUSH 写入，index 0 是最新事件。last_event_count 是上次消费后的 llen 值。
        新事件数量 = total_count - last_event_count，它们位于列表头部（index 0 起）。

        Args:
            session_id: Redis key 的 session 部分
            last_event_count: 上次消费后的事件总数（0 表示首次消费全部）
            count: 最多读取的事件数量

        Returns:
            (聚合摘要 dict, 当前 Redis List 总长度 int)
        """
        r = await self._get_redis()
        key = f"{self.EVENT_KEY_PREFIX}{session_id}"

        total_count = await r.llen(key)

        if last_event_count > 0:
            # 计算增量事件数量
            new_count = total_count - last_event_count
            if new_count <= 0:
                return {"has_data": False}, total_count
            # 确保读取足够的事件（取 max(count, new_count)）
            effective_count = max(count, new_count)
            raw_events = await r.lrange(key, 0, effective_count - 1)
            events = [json.loads(e) for e in raw_events]
            # LPUSH: 新事件在列表头部，取前 new_count 个
            events = events[:new_count]
        else:
            # 首次消费：读取全部
            raw_events = await r.lrange(key, 0, count - 1)
            events = [json.loads(e) for e in raw_events]

        if not events:
            return {"has_data": False}, total_count

        result = self._aggregate_event_list(events)

        # 续期 TTL
        await r.expire(key, self.EVENT_TTL)

        return result, total_count

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None
