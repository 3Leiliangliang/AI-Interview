from __future__ import annotations

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field

from src.agents.common.runtime_request_context import get_agent_request_context
from src.services.interview_coding_service import start_coding_session_from_tool


class StartCodeAssessmentInput(BaseModel):
    thread_id: str | None = Field(default=None, description="当前面试线程 ID，可为空，默认读取运行时线程")
    target_position: str | None = Field(default=None, description="目标岗位名称")
    excluded_problem_ids: list[str] | None = Field(default=None, description="本轮已用过的编程题 ID")
    difficulty_level: str | None = Field(
        default=None,
        description="编程题难度，取值建议为 easy / medium / hard",
    )


@tool(args_schema=StartCodeAssessmentInput)
async def start_code_assessment(
    thread_id: str | None = None,
    target_position: str | None = None,
    excluded_problem_ids: list[str] | None = None,
    difficulty_level: str | None = None,
    runtime: ToolRuntime | None = None,
) -> dict:
    """启动代码考核，为当前面试线程按岗位和难度分配一道中文编程题并返回工作台信息。"""
    runtime_context = getattr(runtime, "context", None)
    runtime_config = getattr(runtime, "config", None) or {}
    configurable = runtime_config.get("configurable", {}) if isinstance(runtime_config, dict) else {}
    request_context = get_agent_request_context()
    effective_thread_id = (
        thread_id
        or getattr(runtime_context, "thread_id", "")
        or str(configurable.get("thread_id") or "")
        or str(request_context.get("thread_id") or "")
    )
    user_id = (
        getattr(runtime_context, "user_id", "")
        or str(configurable.get("user_id") or "")
        or str(request_context.get("user_id") or "")
    )
    effective_position = (
        target_position
        or getattr(runtime_context, "target_position", "")
        or str(request_context.get("target_position") or "")
    )
    if not effective_thread_id or not user_id:
        return {
            "status": "error",
            "message": "Missing runtime thread_id or user_id",
            "problem_id": "",
            "problem_title": "",
            "summary": "",
            "workbench_path": "",
            "source": "",
        }

    result = await start_coding_session_from_tool(
        thread_id=effective_thread_id,
        user_id=str(user_id),
        target_position=effective_position,
        excluded_problem_ids=excluded_problem_ids,
        difficulty_level=difficulty_level,
    )
    result["message"] = "success"
    return result
