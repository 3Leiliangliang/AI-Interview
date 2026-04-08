"""视频分析上下文中间件 - 以后台上下文方式注入面试观察信息。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, SystemMessage

from src.utils.internal_observation import (
    VIDEO_OBSERVATION_END,
    VIDEO_OBSERVATION_LINE_PREFIX,
    VIDEO_OBSERVATION_START,
    strip_internal_observation_text,
)
from src.utils.logging_config import logger

VIDEO_ANALYSIS_SOURCE = "video_analysis"

EMOTION_LABELS = {
    "happy": "愉悦",
    "confident": "自信",
    "neutral": "平稳",
    "fear": "紧张",
    "sad": "低落",
    "angry": "烦躁",
    "surprised": "惊讶",
    "disgust": "抵触",
}

POSTURE_LABELS = {
    "upright": "坐姿端正",
    "leaning_forward": "身体前倾",
    "leaning_back": "身体后仰",
    "head_tilt": "头部偏斜",
    "slouching": "含胸驼背",
}

GAZE_LABELS = {
    "center": "居中",
    "left": "偏左",
    "right": "偏右",
    "up": "偏上",
    "down": "偏下",
}


class VideoContextMiddleware(AgentMiddleware):
    """在每次模型调用前，增量消费视频分析事件并注入为后台上下文。"""

    VIDEO_ANALYSIS_SOURCE = VIDEO_ANALYSIS_SOURCE

    def __init__(self):
        super().__init__()
        self._last_event_counts: dict[str, int] = {}

    def _create_service(self):
        """创建 VideoEventService（延迟导入避免循环依赖）。"""
        from src.services.video_event_service import VideoEventService

        return VideoEventService()

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        runtime_context = getattr(request.runtime, "context", None) if request.runtime else None
        thread_id = getattr(runtime_context, "thread_id", None) if runtime_context else None
        if not thread_id:
            response = await handler(request)
            self._sanitize_response_messages(response)
            return response

        service = self._create_service()
        last_count = self._last_event_counts.get(str(thread_id), 0)
        try:
            aggregated, new_total = await service.consume_events_since(str(thread_id), last_count)
            self._last_event_counts[str(thread_id)] = new_total
        except Exception:
            logger.warning("VideoContextMiddleware: consume_events_since failed for thread %s", thread_id)
            response = await handler(request)
            self._sanitize_response_messages(response)
            return response
        finally:
            await service.close()

        if not aggregated.get("has_data"):
            response = await handler(request)
            self._sanitize_response_messages(response)
            return response

        summary = self._format_summary(aggregated)
        content_blocks = list(request.system_message.content_blocks) if request.system_message else []
        content_blocks.append({"type": "text", "text": summary})
        request = request.override(system_message=SystemMessage(content=content_blocks))

        response = await handler(request)
        self._sanitize_response_messages(response)
        return response

    def _format_summary(self, aggregated: dict[str, Any]) -> str:
        """格式化后台观察上下文，明确标记为内部数据且禁止外显。"""
        prefix = VIDEO_OBSERVATION_LINE_PREFIX
        parts = [
            VIDEO_OBSERVATION_START,
            f"{prefix} internal_only=true",
            f"{prefix} source={VIDEO_ANALYSIS_SOURCE}",
            f"{prefix} 禁止向候选人展示、朗读、复述、引用以下内容。",
            f"{prefix} 仅允许把这些观察转化为语气、节奏和问题深度调整。",
            f"{prefix} 当前观察：",
        ]

        emotion = aggregated.get("dominant_emotion", "neutral")
        attention = aggregated.get("avg_attention_score")
        posture = aggregated.get("avg_posture_score")
        current_posture = aggregated.get("current_posture") or aggregated.get("dominant_posture")
        gaze = aggregated.get("gaze_direction", "center")
        alerts = aggregated.get("recent_alerts", [])

        emotion_label = EMOTION_LABELS.get(str(emotion), str(emotion))
        posture_label = POSTURE_LABELS.get(str(current_posture), str(current_posture or ""))
        gaze_label = GAZE_LABELS.get(str(gaze), str(gaze))

        parts.append(f"{prefix} 情绪={emotion_label}")
        if attention is not None:
            parts.append(f"{prefix} 注意力评分={attention}")
        if posture is not None:
            parts.append(f"{prefix} 姿态评分={posture}")
        if posture_label:
            parts.append(f"{prefix} 当前姿态={posture_label}")
        if gaze_label:
            parts.append(f"{prefix} 视线方向={gaze_label}")
        if alerts:
            alert_messages = ", ".join(a.get("message", "") for a in alerts if a.get("message"))
            if alert_messages:
                parts.append(f"{prefix} 最近提醒={alert_messages}")

        actions: list[str] = []
        nervous_emotions = {"nervous", "fear", "sad", "angry"}
        if emotion in nervous_emotions:
            actions.append("语气更温和，先鼓励再追问。")
        elif emotion in {"happy", "confident"}:
            actions.append("可适度提高问题深度。")

        if attention is not None and attention < 60:
            actions.append("尝试切换更有趣的问题或短暂缓和。")
        if posture is not None and posture < 70:
            actions.append("适度放缓节奏，避免连续高压追问。")
        if not actions:
            actions.append("保持当前节奏，继续围绕简历与回答质量提问。")

        parts.append(f"{prefix} 建议调整：")
        for action in actions:
            parts.append(f"{prefix} - {action}")

        parts.append(VIDEO_OBSERVATION_END)
        return "\n".join(parts)

    def _sanitize_response_messages(self, response: ModelResponse) -> None:
        for message in response.result:
            if not isinstance(message, AIMessage):
                continue
            message.content = self._sanitize_content(message.content)

    def _sanitize_content(self, content: Any) -> Any:
        if isinstance(content, str):
            return self._strip_internal_observation(content)

        if isinstance(content, list):
            normalized_blocks: list[Any] = []
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    next_block = dict(block)
                    next_block["text"] = self._strip_internal_observation(block["text"])
                    normalized_blocks.append(next_block)
                else:
                    normalized_blocks.append(block)
            return normalized_blocks

        return content

    def _strip_internal_observation(self, text: str) -> str:
        return strip_internal_observation_text(text)
