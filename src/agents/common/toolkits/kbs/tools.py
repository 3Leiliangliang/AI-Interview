"""知识库工具模块。"""

import inspect
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field
from sqlalchemy import select

from src import knowledge_base
from src.services.openviking_service import openviking_service
from src.storage.postgres.manager import pg_manager
from src.storage.postgres.models_business import UserResume
from src.utils import logger

RESUME_KB_NAME = "我的简历"
RESUME_KB_DESCRIPTION = "用户在“我的简历”中上传的简历文件，可直接用于模拟面试提问。"
MAX_RESUME_CONTENT_CHARS = 8000


def _normalize_runtime_user_id(runtime: ToolRuntime) -> int | None:
    runtime_context = getattr(runtime, "context", None)
    user_id = getattr(runtime_context, "user_id", None)
    if user_id in (None, ""):
        return None

    try:
        return int(user_id)
    except (TypeError, ValueError):
        logger.warning("知识库工具无法解析 user_id: %s", user_id)
        return None


async def _get_user_resumes(user_id: int) -> list[UserResume]:
    async with pg_manager.get_async_session_context() as session:
        result = await session.execute(
            select(UserResume)
            .where(UserResume.user_id == user_id)
            .order_by(UserResume.updated_at.desc(), UserResume.id.desc())
        )
        return list(result.scalars().all())


def _select_resume(resumes: list[UserResume], file_name: str | None = None) -> UserResume | None:
    if not resumes:
        return None

    if not file_name:
        return resumes[0]

    keyword = file_name.strip().lower()
    if not keyword:
        return resumes[0]

    for resume in resumes:
        filename = (resume.filename or "").lower()
        if keyword in filename or filename in keyword:
            return resume

    return resumes[0]


def _truncate_resume_content(content: str) -> str:
    if len(content) <= MAX_RESUME_CONTENT_CHARS:
        return content

    truncated = content[:MAX_RESUME_CONTENT_CHARS].rstrip()
    return f"{truncated}\n\n[内容已截断，请基于当前简历片段继续提问]"


def _build_resume_kb_result(resume: UserResume, query_text: str) -> str:
    updated_at = resume.updated_at.isoformat() if resume.updated_at else "未知"
    content = _truncate_resume_content(resume.markdown_content or "")
    return (
        f"知识库：{RESUME_KB_NAME}\n"
        f"命中文件：{resume.filename}\n"
        f"更新时间：{updated_at}\n"
        f"检索意图：{query_text}\n\n"
        "以下是该简历的正文内容，请直接基于这份简历继续面试提问：\n\n"
        f"{content}"
    )


class ListKBsInput(BaseModel):
    """列出用户可访问的知识库输入模型。"""

    dummy: str = Field(default="", description="占位参数，忽略即可")


@tool(args_schema=ListKBsInput)
async def list_kbs(dummy: str, runtime: ToolRuntime) -> Any:
    """列出当前用户可访问的知识库列表。"""
    user_id = _normalize_runtime_user_id(runtime)
    if user_id is None:
        return "无法获取用户信息"

    runtime_context = runtime.context
    enabled_kb_names = getattr(runtime_context, "knowledges", []) or []

    try:
        result = await knowledge_base.get_databases_by_raw_id(str(user_id))
        all_kbs = result.get("databases", [])
    except Exception as e:
        logger.error("获取用户知识库列表失败: %s", e)
        all_kbs = []

    available_kbs = [kb for kb in all_kbs if kb.get("name") in enabled_kb_names]

    try:
        resumes = await _get_user_resumes(user_id)
    except Exception as e:
        logger.error("获取用户简历列表失败: %s", e)
        resumes = []

    kb_list = [
        {
            "name": kb.get("name", ""),
            "description": kb.get("description") or "无描述",
        }
        for kb in available_kbs
    ]

    if resumes:
        kb_list.append({"name": RESUME_KB_NAME, "description": RESUME_KB_DESCRIPTION})

    if not kb_list:
        return "当前没有可访问的知识库"

    return kb_list


class GetMindmapInput(BaseModel):
    """获取思维导图输入模型。"""

    kb_name: str = Field(description="知识库名称")


@tool(args_schema=GetMindmapInput)
async def get_mindmap(kb_name: str, runtime: ToolRuntime) -> str:
    """获取指定知识库的思维导图结构。"""
    if not kb_name:
        return "请提供知识库名称"

    if kb_name == RESUME_KB_NAME:
        return "“我的简历”知识库不提供思维导图，请直接使用 query_kb 检索简历内容。"

    retrievers = knowledge_base.get_retrievers()

    target_db_id = None
    target_info = None
    for db_id, info in retrievers.items():
        if info["name"] == kb_name:
            target_db_id = db_id
            target_info = info
            break

    if not target_db_id:
        return f"知识库“{kb_name}”不存在"

    try:
        from src.repositories.knowledge_base_repository import KnowledgeBaseRepository

        kb_repo = KnowledgeBaseRepository()
        kb = await kb_repo.get_by_id(target_db_id)
        if kb is None:
            return f"知识库“{target_info['name']}”不存在"

        mindmap_data = kb.mindmap
        if not mindmap_data:
            return f"知识库“{target_info['name']}”还没有生成思维导图。"

        def mindmap_to_text(node, level=0):
            indent = "  " * level
            text = f"{indent}- {node.get('content', '')}\n"
            for child in node.get("children", []):
                text += mindmap_to_text(child, level + 1)
            return text

        return f"知识库“{target_info['name']}”的思维导图结构：\n\n{mindmap_to_text(mindmap_data)}"
    except Exception as e:
        logger.error("获取思维导图失败: %s", e)
        return f"获取思维导图失败: {str(e)}"


class QueryKBInput(BaseModel):
    """知识库检索输入模型。"""

    kb_name: str = Field(description="知识库名称")
    query_text: str = Field(description="检索问题或检索关键词")
    file_name: str | None = Field(default=None, description="可选的文件名过滤")


@tool(args_schema=QueryKBInput)
async def query_kb(kb_name: str, query_text: str, file_name: str | None = None, runtime: ToolRuntime = None) -> Any:
    """在指定知识库中检索内容。"""
    if not kb_name:
        return "请提供知识库名称"
    if not query_text:
        return "请提供检索内容"

    if kb_name == RESUME_KB_NAME:
        if runtime is None:
            return "无法获取当前用户信息"

        user_id = _normalize_runtime_user_id(runtime)
        if user_id is None:
            return "无法获取当前用户信息"

        try:
            resumes = await _get_user_resumes(user_id)
        except Exception as e:
            logger.error("检索“我的简历”失败: %s", e)
            return f"检索“我的简历”失败: {str(e)}"

        if not resumes:
            return "当前用户还没有上传简历"

        resume = _select_resume(resumes, file_name=file_name)
        if resume is None:
            return "未找到匹配的简历文件"

        if openviking_service.is_enabled():
            try:
                return await openviking_service.query_resume(resume, query_text)
            except Exception as e:
                logger.error("OpenViking 检索“我的简历”失败: %s", e)
                return f"OpenViking 检索“我的简历”失败: {str(e)}"

        return _build_resume_kb_result(resume, query_text)

    retrievers = knowledge_base.get_retrievers()

    target_db_id = None
    target_info = None
    for db_id, info in retrievers.items():
        if info["name"] == kb_name:
            target_db_id = db_id
            target_info = info
            break

    if not target_info:
        return f"知识库“{kb_name}”不存在"

    if (
        openviking_service.is_enabled()
        and target_db_id
        and target_info.get("metadata", {}).get("kb_type") != "openviking"
    ):
        try:
            return await openviking_service.query_database(
                db_id=target_db_id,
                kb_name=kb_name,
                query_text=query_text,
                file_name=file_name,
            )
        except Exception as e:
            logger.error("OpenViking 知识库检索失败: %s", e)
            return f"OpenViking 知识库检索失败: {str(e)}"

    try:
        retriever = target_info["retriever"]
        kwargs = {}
        if file_name:
            kwargs["file_name"] = file_name

        if inspect.iscoroutinefunction(retriever):
            return await retriever(query_text, **kwargs)
        return retriever(query_text, **kwargs)
    except Exception as e:
        logger.error("知识库检索失败: %s", e)
        return f"知识库检索失败: {str(e)}"


def get_common_kb_tools() -> list:
    """获取通用知识库工具列表。"""
    return [list_kbs, get_mindmap, query_kb]
