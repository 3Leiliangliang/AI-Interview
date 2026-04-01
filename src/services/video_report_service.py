"""面试后视频分析报告生成服务 - 聚合视频分析事件并生成综合报告"""

from __future__ import annotations

import json
from typing import Any

from src.models.chat import select_model
from src.services.video_event_service import VideoEventService
from src.utils.logging_config import logger


class VideoReportService:
    """视频分析报告生成服务"""

    def __init__(self, event_service: VideoEventService | None = None):
        self._event_service = event_service or VideoEventService()

    async def generate_report(self, session_id: str) -> dict[str, Any]:
        """生成面试视频分析报告"""
        aggregated = await self._event_service.aggregate_events(session_id)

        if not aggregated.get("has_data"):
            return {
                "session_id": session_id,
                "has_data": False,
                "scores": {},
                "overall_impression": "",
                "recommendations": [],
                "strengths": [],
            }

        scores = self._compute_scores(aggregated)

        # 尝试使用 LLM 生成报告
        try:
            report = await self._generate_llm_report(session_id, scores, aggregated)
        except Exception as e:
            logger.warning(f"LLM report generation failed, falling back to rules: {e}")
            report = self._generate_fallback_report(session_id, scores, aggregated)

        return report

    def _compute_scores(self, aggregated: dict) -> dict[str, float]:
        """计算各维度评分

        情绪稳定性: 基于情绪分布集中度计算
        姿态评分: 直接使用 avg_posture_score
        注意力评分: 直接使用 avg_attention_score
        综合评分: 0.3*情绪 + 0.3*姿态 + 0.4*注意力
        """
        # 情绪稳定性
        emotion_scores = aggregated.get("emotion_scores", {})
        if emotion_scores:
            values = list(emotion_scores.values())
            max_score = max(values)
            # 集中度越高（越接近1.0），稳定性越高
            emotion_stability = round(max_score * 100, 1)
        else:
            emotion_stability = 70.0

        # 姿态评分
        posture = aggregated.get("avg_posture_score")
        posture = posture if posture is not None else 70.0

        # 注意力评分
        attention = aggregated.get("avg_attention_score")
        attention = attention if attention is not None else 70.0

        # 综合评分
        overall = round(0.3 * emotion_stability + 0.3 * posture + 0.4 * attention, 1)

        return {
            "emotion_stability": emotion_stability,
            "posture": posture,
            "attention": attention,
            "overall": overall,
        }

    def _format_report_prompt(self, scores: dict, aggregated: dict) -> str:
        """格式化 LLM prompt"""
        emotion_scores_str = ", ".join(
            f"{k}: {v:.1%}" for k, v in aggregated.get("emotion_scores", {}).items()
        )
        alerts_str = "; ".join(
            a.get("message", "") for a in aggregated.get("recent_alerts", [])
        )

        return f"""你是一位专业的面试行为分析师。请根据以下面试者的视频分析数据，生成一份综合分析报告。

## 视频分析数据

### 各维度评分 (0-100)
- 情绪稳定性: {scores.get('emotion_stability', 0)}
- 姿态评分: {scores.get('posture', 0)}
- 注意力评分: {scores.get('attention', 0)}
- 综合评分: {scores.get('overall', 0)}

### 详细信息
- 主要情绪: {aggregated.get('dominant_emotion', 'unknown')}
- 情绪分布: {emotion_scores_str or '无数据'}
- 视线方向: {aggregated.get('gaze_direction', 'unknown')}
- 事件总数: {aggregated.get('event_count', 0)}
- 警告信息: {alerts_str or '无'}

## 输出要求

请以 JSON 格式输出，包含以下字段：
{{
  "overall_impression": "整体印象（2-3句话概括面试者的整体表现）",
  "dimension_analysis": {{
    "emotion": "情绪分析（详细分析情绪表现）",
    "posture": "姿态分析（详细分析姿态和肢体语言）",
    "attention": "注意力分析（详细分析注意力表现）"
  }},
  "recommendations": ["3-5条具体改进建议"],
  "strengths": ["2-3条优势总结"]
}}

请确保输出合法的 JSON 格式。"""

    async def _generate_llm_report(
        self, session_id: str, scores: dict, aggregated: dict
    ) -> dict[str, Any]:
        """使用 LLM 生成报告"""
        prompt = self._format_report_prompt(scores, aggregated)
        model = select_model()

        response = await model.call(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # 解析 LLM 返回的 JSON
        llm_result = self._parse_llm_response(content)

        return {
            "session_id": session_id,
            "has_data": True,
            "scores": scores,
            "overall_impression": llm_result.get("overall_impression", ""),
            "dimension_analysis": llm_result.get("dimension_analysis", {}),
            "recommendations": llm_result.get("recommendations", []),
            "strengths": llm_result.get("strengths", []),
            "alerts": aggregated.get("recent_alerts", []),
            "event_count": aggregated.get("event_count", 0),
        }

    def _parse_llm_response(self, content: str) -> dict:
        """解析 LLM 返回的 JSON 内容"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        import re

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号内容
        brace_match = re.search(r"\{.*\}", content, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Failed to parse LLM response as JSON: {content[:200]}")

    def _generate_fallback_report(
        self, session_id: str, scores: dict, aggregated: dict
    ) -> dict[str, Any]:
        """LLM 失败时的降级报告（纯规则评分）"""
        recommendations = self._generate_rule_based_recommendations(scores, aggregated)
        strengths = self._generate_rule_based_strengths(scores)

        # 简单的整体印象
        overall = scores.get("overall", 0)
        if overall >= 85:
            impression = "面试者在视频中表现出色，整体状态良好。"
        elif overall >= 70:
            impression = "面试者在视频中表现尚可，部分维度有提升空间。"
        elif overall >= 55:
            impression = "面试者在视频中的表现有待改善，建议针对性训练。"
        else:
            impression = "面试者在视频中的表现需要较大改善，建议系统性地进行面试技巧训练。"

        return {
            "session_id": session_id,
            "has_data": True,
            "scores": scores,
            "overall_impression": impression,
            "dimension_analysis": {},
            "recommendations": recommendations,
            "strengths": strengths,
            "alerts": aggregated.get("recent_alerts", []),
            "event_count": aggregated.get("event_count", 0),
        }

    def _generate_rule_based_recommendations(self, scores: dict, aggregated: dict) -> list[str]:
        """基于规则生成改进建议"""
        recs = []

        attention = scores.get("attention", 100)
        posture = scores.get("posture", 100)
        emotion = scores.get("emotion_stability", 100)

        if attention < 60:
            recs.append("建议提升注意力集中度，面试时保持眼神交流，避免频繁分心。")
        elif attention < 80:
            recs.append("注意力表现尚可，可进一步练习保持专注力。")

        if posture < 60:
            recs.append("建议改善坐姿习惯，保持背部挺直，避免驼背或过度前倾。")
        elif posture < 80:
            recs.append("姿态整体可以，注意保持端正坐姿，减少不必要的肢体动作。")

        if emotion < 60:
            recs.append("建议进行情绪管理训练，面试前可做深呼吸放松，保持平稳心态。")
        elif emotion < 80:
            recs.append("情绪控制能力可以进一步提升，建议模拟面试练习情绪调节。")

        gaze = aggregated.get("gaze_direction", "center")
        if gaze != "center":
            recs.append("注意保持视线居中，避免频繁看向其他方向。")

        if not recs:
            recs.append("各项指标表现优秀，继续保持良好的面试状态。")

        return recs

    def _generate_rule_based_strengths(self, scores: dict) -> list[str]:
        """基于规则生成优势总结"""
        strengths = []

        if scores.get("emotion_stability", 0) >= 80:
            strengths.append("情绪稳定性良好，面试过程中情绪波动较小。")
        if scores.get("posture", 0) >= 80:
            strengths.append("姿态表现端正，展现出良好的精神面貌。")
        if scores.get("attention", 0) >= 80:
            strengths.append("注意力集中度较高，能够专注于面试交流。")

        if not strengths:
            strengths.append("整体表现平稳，具备面试基本素养。")

        return strengths
