"""视频分析上下文中间件 - 通过 System Message 将视频分析摘要注入 Agent 上下文"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from src.utils.logging_config import logger

VIDEO_ANALYSIS_SOURCE = "video_analysis"


class VideoContextMiddleware(AgentMiddleware):
    """在每次模型调用前，从 Redis 增量消费视频分析事件，通过 system message 注入自然语言摘要。

    核心流程：
    1. 从 request.runtime.context 获取 thread_id
    2. 调用 VideoEventService.consume_events_since 增量消费事件
    3. 格式化为自然语言摘要
    4. 追加到 system message 的 content_blocks（对前端不可见）
    """

    VIDEO_ANALYSIS_SOURCE = VIDEO_ANALYSIS_SOURCE

    def __init__(self):
        super().__init__()
        self._last_event_counts: dict[str, int] = {}  # thread_id -> 上次消费后的事件总数

    def _create_service(self):
        """创建 VideoEventService（延迟导入避免循环依赖）。"""
        from src.services.video_event_service import VideoEventService

        return VideoEventService()

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        # 1. 从 runtime.context 获取 thread_id
        runtime_context = getattr(request.runtime, "context", None) if request.runtime else None
        thread_id = getattr(runtime_context, "thread_id", None) if runtime_context else None
        if not thread_id:
            return await handler(request)

        # 2. 增量消费 Redis 事件
        service = self._create_service()
        last_count = self._last_event_counts.get(str(thread_id), 0)
        try:
            aggregated, new_total = await service.consume_events_since(str(thread_id), last_count)
            self._last_event_counts[str(thread_id)] = new_total
        except Exception:
            logger.warning("VideoContextMiddleware: consume_events_since failed for thread %s", thread_id)
            return await handler(request)
        finally:
            await service.close()

        if not aggregated.get("has_data"):
            return await handler(request)

        # 3. 格式化为自然语言摘要
        summary = self._format_summary(aggregated)

        # 4. 追加到 system message（对前端不可见）
        content_blocks = list(request.system_message.content_blocks) if request.system_message else []
        content_blocks.append({"type": "text", "text": summary})
        new_system_message = SystemMessage(content=content_blocks)
        request = request.override(system_message=new_system_message)

        return await handler(request)

    def _format_summary(self, aggregated: dict[str, Any]) -> str:
        """将聚合数据格式化为自然语言摘要，包含行为建议。"""
        parts = ["[面试观察备注 - 回答期间新增观察]"]

        emotion = aggregated.get("dominant_emotion", "neutral")
        attention = aggregated.get("avg_attention_score")
        posture = aggregated.get("avg_posture_score")
        gaze = aggregated.get("gaze_direction", "center")
        alerts = aggregated.get("recent_alerts", [])

        # 情绪分析 + 行为建议
        nervous_emotions = {"nervous", "fear", "sad", "angry"}
        if emotion in nervous_emotions:
            parts.append(f"面试者当前情绪：{emotion}（紧张迹象明显）")
            parts.append("建议行为：")
            parts.append("- 面试者可能感到紧张，请用鼓励性语言安抚，适当降低追问强度")
            parts.append("- 避免连续追问尖锐问题，给面试者思考时间")
        elif emotion in {"happy", "confident"}:
            parts.append(f"面试者当前情绪：{emotion}（状态良好）")
            parts.append("建议行为：")
            parts.append("- 可以适当增加问题深度和挑战性")
        else:
            parts.append(f"面试者当前情绪：{emotion}")

        # 注意力分析 + 行为建议
        if attention is not None:
            if attention < 60:
                parts.append(f"注意力偏低（{attention}分）")
                parts.append("建议行为：")
                parts.append("- 可以尝试换一个更有趣的问题或短暂闲聊缓解")
            elif attention < 80:
                parts.append(f"注意力一般（{attention}分）")
            else:
                parts.append(f"注意力良好（{attention}分）")

        # 坐姿
        if posture is not None and posture < 70:
            parts.append(f"坐姿评分偏低（{posture}分）")

        # 视线
        if gaze != "center":
            parts.append(f"视线偏{gaze}")

        # 警告
        if alerts:
            parts.append(f"最近{len(alerts)}条提醒：{', '.join(a.get('message', '') for a in alerts)}")

        parts.append("请在提问和反馈时自然地参考上述观察，但不要提及'视频分析'或'摄像头'等技术细节。")

        return "\n".join(parts)
