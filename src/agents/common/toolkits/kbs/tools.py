"""知识库工具模块。"""

import inspect
import random
import re
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, Field
from sqlalchemy import select

from src import knowledge_base
from src.agents.common.runtime_request_context import get_agent_request_context
from src.services.openviking_service import openviking_service
from src.services.position_types import normalize_position_label
from src.storage.postgres.manager import pg_manager
from src.storage.postgres.models_business import UserResume
from src.utils import logger

RESUME_KB_NAME = "我的简历"
RESUME_KB_DESCRIPTION = "用户在“我的简历”中上传的简历文件，可直接用于模拟面试提问。"
MAX_RESUME_CONTENT_CHARS = 8000
INDEXED_FILE_STATUSES = {"indexed", "done"}
QA_QUESTION_PREFIX_RE = re.compile(r"^(?:问题|question)\s*[:：]\s*", flags=re.IGNORECASE)
QA_ANSWER_SPLIT_RE = re.compile(r"(?:回答|答案|answer)\s*[:：]", flags=re.IGNORECASE)
BACKEND_ROLE_KEYWORDS = ("后端", "backend", "java")
FRONTEND_ROLE_KEYWORDS = ("前端", "frontend", "react", "vue")
BACKEND_KB_KEYWORDS = (
    "后端",
    "backend",
    "java",
    "javaguide",
    "waking-up",
    "database",
    "mysql",
    "redis",
    "kafka",
    "rabbitmq",
    "rocketmq",
    "操作系统",
    "计算机网络",
    "python",
)
FRONTEND_KB_KEYWORDS = ("前端", "frontend", "react", "vue", "javascript", "typescript", "css", "html")
QUESTION_FILE_KEYWORDS = ("question", "questions", "interview", "面试", "题")


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


def _format_structured_summary(summary_json: dict) -> str:
    """将结构化 JSON 格式化为可读文本"""
    lines = []

    # 基础信息
    basic = summary_json.get("basic_info") or {}
    if basic:
        basic_parts = []
        for key, label in [
            ("name", "姓名"),
            ("gender", "性别"),
            ("age", "年龄"),
            ("phone", "手机"),
            ("email", "邮箱"),
            ("location", "所在地"),
        ]:
            val = basic.get(key)
            if val:
                basic_parts.append(f"{label}：{val}")
        if basic.get("github"):
            basic_parts.append(f"GitHub：{basic['github']}")
        if basic.get("linkedin"):
            basic_parts.append(f"LinkedIn：{basic['linkedin']}")
        if basic_parts:
            lines.append("【基础信息】 " + " | ".join(basic_parts))

    # 教育经历
    education = summary_json.get("education") or []
    if education:
        lines.append("")
        lines.append("【教育经历】")
        for edu in education:
            edu_parts = [edu.get("school", "")]
            if edu.get("major"):
                edu_parts.append(edu["major"])
            if edu.get("degree"):
                edu_parts.append(edu["degree"])
            if edu.get("duration"):
                edu_parts.append(f"({edu['duration']})")
            line = "".join(edu_parts)
            if edu.get("gpa"):
                line += f" | GPA：{edu['gpa']}"
            if edu.get("ranking"):
                line += f" | 排名：{edu['ranking']}"
            lines.append(f"  - {line}")

    # 工作经历
    work = summary_json.get("work_experience") or []
    if work:
        lines.append("")
        lines.append("【工作经历】")
        for w in work:
            title = w.get("company", "")
            if w.get("position"):
                title += f" - {w['position']}"
            if w.get("duration"):
                title += f" ({w['duration']})"
            lines.append(f"  - {title}")
            highlights = w.get("highlights") or []
            for h in highlights:
                lines.append(f"    · {h}")

    # 项目经历
    projects = summary_json.get("project_experience") or []
    if projects:
        lines.append("")
        lines.append("【项目经历】")
        for p in projects:
            title = p.get("name", "")
            if p.get("role"):
                title += f"（{p['role']}）"
            if p.get("duration"):
                title += f" ({p['duration']})"
            lines.append(f"  - {title}")
            tech_stack = p.get("tech_stack") or []
            if tech_stack:
                lines.append(f"    技术栈：{', '.join(tech_stack)}")
            if p.get("team_size"):
                lines.append(f"    团队规模：{p['team_size']}人")
            desc = p.get("description", "")
            if desc:
                lines.append(f"    描述：{desc}")
            results = p.get("results") or []
            for r in results:
                lines.append(f"    成果：{r}")

    # 技能
    skills = summary_json.get("skills") or {}
    if skills:
        lines.append("")
        skill_parts = []
        tech = skills.get("technical") or []
        if tech:
            skill_parts.append(f"技术技能：{', '.join(tech)}")
        langs = skills.get("languages") or []
        if langs:
            skill_parts.append(f"语言能力：{', '.join(langs)}")
        certs = skills.get("certifications") or []
        if certs:
            skill_parts.append(f"证书：{', '.join(certs)}")
        if skill_parts:
            lines.append("【技能】 " + " | ".join(skill_parts))

    # 获奖情况
    awards = summary_json.get("awards") or []
    if awards:
        lines.append("")
        lines.append("【获奖情况】")
        for a in awards:
            lines.append(f"  - {a}")

    # 培训经历
    training = summary_json.get("training") or []
    if training:
        lines.append("")
        lines.append("【培训经历】")
        for t in training:
            lines.append(f"  - {t}")

    # 自我评价
    self_eval = summary_json.get("self_evaluation")
    if self_eval:
        lines.append("")
        lines.append(f"【自我评价】 {self_eval}")

    # 求职偏好
    pref = summary_json.get("job_preference") or {}
    if pref:
        lines.append("")
        pref_parts = []
        if pref.get("job_intention"):
            pref_parts.append(f"求职意向：{pref['job_intention']}")
        if pref.get("expected_salary"):
            pref_parts.append(f"期望薪资：{pref['expected_salary']}")
        if pref.get("desired_location"):
            pref_parts.append(f"期望地点：{pref['desired_location']}")
        if pref_parts:
            lines.append("【求职偏好】 " + " | ".join(pref_parts))

    return "\n".join(lines) if lines else ""


def _build_resume_kb_result(resume: UserResume, query_text: str) -> str:
    updated_at = resume.updated_at.isoformat() if resume.updated_at else "未知"

    # 优先使用结构化摘要（当状态为 completed 时）
    if resume.summary_status == "completed" and resume.summary_json:
        formatted_summary = _format_structured_summary(resume.summary_json)
        if formatted_summary:
            return (
                f"知识库：{RESUME_KB_NAME}\n"
                f"命中文件：{resume.filename}\n"
                f"更新时间：{updated_at}\n"
                f"检索意图：{query_text}\n\n"
                "以下是该简历的结构化摘要信息：\n\n"
                f"{formatted_summary}"
            )

    # 降级方案：使用原始 markdown 内容
    content = _truncate_resume_content(resume.markdown_content or "")
    return (
        f"知识库：{RESUME_KB_NAME}\n"
        f"命中文件：{resume.filename}\n"
        f"更新时间：{updated_at}\n"
        f"检索意图：{query_text}\n\n"
        "以下是该简历的正文内容，请直接基于这份简历继续面试提问：\n\n"
        f"{content}"
    )


def _extract_question_from_chunk_content(chunk_content: str) -> str | None:
    if not chunk_content:
        return None

    question_part = chunk_content.strip().split("\t", 1)[0].strip()
    if not question_part:
        return None

    if not QA_QUESTION_PREFIX_RE.match(question_part) and not question_part.endswith(("?", "？")):
        return None

    question_part = QA_ANSWER_SPLIT_RE.split(question_part, maxsplit=1)[0].strip()
    question = QA_QUESTION_PREFIX_RE.sub("", question_part).strip()
    return question or None


def _build_kb_search_text(kb_info: dict[str, Any]) -> str:
    return " ".join(
        str(part).strip().lower()
        for part in (
            kb_info.get("name"),
            kb_info.get("description"),
        )
        if part
    )


def _keyword_matches_search_text(keyword: str, search_text: str) -> bool:
    normalized_keyword = str(keyword or "").strip().lower()
    normalized_search_text = str(search_text or "").strip().lower()
    if not normalized_keyword or not normalized_search_text:
        return False

    if re.fullmatch(r"[a-z0-9][a-z0-9_+\-.]*", normalized_keyword):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
        return re.search(pattern, normalized_search_text) is not None

    return normalized_keyword in normalized_search_text


def _match_role_based_kbs(requested_name: str, all_kbs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_name = requested_name.strip().lower()
    if not normalized_name:
        return []

    if any(keyword in normalized_name for keyword in BACKEND_ROLE_KEYWORDS):
        keywords = BACKEND_KB_KEYWORDS
    elif any(keyword in normalized_name for keyword in FRONTEND_ROLE_KEYWORDS):
        keywords = FRONTEND_KB_KEYWORDS
    else:
        return []

    return [
        kb_info
        for kb_info in all_kbs
        if any(_keyword_matches_search_text(keyword, _build_kb_search_text(kb_info)) for keyword in keywords)
    ]


def _get_position_kb_names(target_position: str | None) -> list[str]:
    normalized = str(target_position or "").strip()
    if not normalized:
        return []
    return [normalize_position_label(normalized)]


def _get_interview_kb_names_from_runtime(runtime: ToolRuntime | None) -> list[str]:
    runtime_context = getattr(runtime, "context", None)
    request_context = get_agent_request_context()
    target_position = getattr(runtime_context, "target_position", "") or str(
        request_context.get("target_position") or ""
    )
    return _get_position_kb_names(target_position)


async def _resolve_candidate_kbs(kb_names: list[str]) -> list[dict[str, Any]]:
    all_kbs = (await knowledge_base.get_databases()).get("databases", []) or []
    if not all_kbs:
        return []

    exact_lookup = {str(kb.get("name") or "").strip().lower(): kb for kb in all_kbs if kb.get("name")}
    resolved: list[dict[str, Any]] = []
    seen_db_ids: set[str] = set()

    for kb_name in kb_names:
        normalized_name = kb_name.strip().lower()
        if not normalized_name:
            continue

        matched_kbs: list[dict[str, Any]] = []
        exact_match = exact_lookup.get(normalized_name)
        if exact_match:
            matched_kbs = [exact_match]
        else:
            matched_kbs = [
                kb_info
                for kb_info in all_kbs
                if normalized_name in _build_kb_search_text(kb_info)
                or _build_kb_search_text(kb_info) in normalized_name
            ]
            if not matched_kbs:
                requested_position_label = normalize_position_label(kb_name, fallback_to_default=False)
                matched_kbs = [
                    kb_info
                    for kb_info in all_kbs
                    if normalize_position_label(
                        (kb_info.get("additional_params") or {}).get("position", ""),
                        fallback_to_default=False,
                    )
                    == requested_position_label
                ]
            if not matched_kbs:
                matched_kbs = _match_role_based_kbs(kb_name, all_kbs)

        for kb_info in matched_kbs:
            db_id = str(kb_info.get("db_id") or "").strip()
            if not db_id or db_id in seen_db_ids:
                continue
            seen_db_ids.add(db_id)
            resolved.append(kb_info)

    return resolved


async def _collect_technical_question_candidates(kb_names: list[str]) -> list[dict[str, Any]]:
    if not kb_names:
        return []

    seen_questions: set[str] = set()
    candidates: list[dict[str, Any]] = []

    resolved_kbs = await _resolve_candidate_kbs(kb_names)
    for kb_info in resolved_kbs:
        db_id = str(kb_info.get("db_id") or "")
        kb_name = str(kb_info.get("name") or "")
        db_info = await knowledge_base.get_database_info(db_id)
        if not db_info:
            continue

        files = db_info.get("files", {}) or {}
        eligible_files = [
            (file_id, file_info)
            for file_id, file_info in files.items()
            if not file_info.get("is_folder") and file_info.get("status") in INDEXED_FILE_STATUSES
        ]
        question_files = [
            (file_id, file_info)
            for file_id, file_info in eligible_files
            if any(keyword in str(file_info.get("filename") or "").lower() for keyword in QUESTION_FILE_KEYWORDS)
        ]

        for file_id, file_info in question_files or eligible_files:
            file_content = await knowledge_base.get_file_content(db_id, file_id)
            for line in file_content.get("lines") or []:
                question = _extract_question_from_chunk_content(line.get("content", ""))
                if not question or question in seen_questions:
                    continue

                seen_questions.add(question)
                candidates.append(
                    {
                        "question": question,
                        "kb_name": kb_name,
                        "db_id": db_id,
                        "file_id": str(file_id or "").strip(),
                        "file_name": file_info.get("filename") or "",
                        "chunk_id": str(line.get("id") or "").strip(),
                        "chunk_index": line.get("chunk_order_index"),
                    }
                )

    return candidates


async def _pick_random_technical_question(kb_names: list[str]) -> dict[str, Any]:
    return await _pick_random_technical_question_with_excludes(kb_names, excluded_questions=None)


async def _pick_random_technical_question_with_excludes(
    kb_names: list[str],
    excluded_questions: list[str] | None = None,
) -> dict[str, Any]:
    normalized_kb_names = [name.strip() for name in kb_names if isinstance(name, str) and name.strip()]
    if not normalized_kb_names:
        return {
            "question": "",
            "kb_name": "",
            "db_id": "",
            "file_id": "",
            "file_name": "",
            "chunk_id": "",
            "chunk_index": None,
            "message": "当前没有可用的技术题库。",
        }

    candidates = await _collect_technical_question_candidates(normalized_kb_names)
    normalized_excluded_questions = {
        question.strip() for question in (excluded_questions or []) if isinstance(question, str) and question.strip()
    }
    if normalized_excluded_questions:
        candidates = [
            candidate for candidate in candidates if candidate["question"] not in normalized_excluded_questions
        ]

    if not candidates:
        return {
            "question": "",
            "kb_name": "",
            "db_id": "",
            "file_id": "",
            "file_name": "",
            "chunk_id": "",
            "chunk_index": None,
            "message": (
                "当前岗位对应的知识库里没有更多可用的技术题目。"
                if normalized_excluded_questions
                else "当前岗位对应的知识库里没有可用的技术题目。"
            ),
        }

    selected = random.choice(candidates)
    return {
        "question": selected["question"],
        "kb_name": selected["kb_name"],
        "db_id": selected["db_id"],
        "file_id": selected["file_id"],
        "file_name": selected["file_name"],
        "chunk_id": selected["chunk_id"],
        "chunk_index": selected["chunk_index"],
        "message": "success",
    }


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


class PickRandomTechnicalQuestionInput(BaseModel):
    """随机抽取技术问题输入模型。"""

    kb_names: list[str] = Field(description="候选题目来源的知识库名称列表")
    excluded_questions: list[str] | None = Field(default=None, description="本阶段已经问过的问题列表")


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


@tool(args_schema=PickRandomTechnicalQuestionInput)
async def pick_random_technical_question(
    kb_names: list[str],
    excluded_questions: list[str] | None = None,
) -> dict[str, str]:
    """从指定知识库的 QA 分块中随机抽取一个技术问题。"""
    try:
        return await _pick_random_technical_question_with_excludes(kb_names, excluded_questions)
    except Exception as e:
        logger.error("随机抽取技术问题失败: %s", e)
        return {
            "question": "",
            "kb_name": "",
            "file_name": "",
            "message": f"随机抽取技术问题失败: {str(e)}",
        }


def get_common_kb_tools() -> list:
    """获取通用知识库工具列表。"""
    return [list_kbs, get_mindmap, query_kb]
