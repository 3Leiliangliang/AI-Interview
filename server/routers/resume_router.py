import asyncio
import json
import os
import re
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from src.knowledge.indexing import process_file_to_markdown
from src.knowledge.utils import calculate_content_hash
from src.plugins.document_processor_base import DocumentProcessorException
from src.services.match_service import match_service
from src.services.openviking_service import openviking_service
from src.services.resume_summary_service import resume_summary_service
from src.storage.minio import aupload_file_to_minio, get_minio_client
from src.storage.postgres.manager import pg_manager
from src.storage.postgres.models_business import User, UserResume
from src.utils.datetime_utils import utc_now_naive
from src.utils import logger

resume = APIRouter(prefix="/resume", tags=["resume"])
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()
SUMMARY_STALE_TIMEOUT = timedelta(minutes=5)

SECTION_KEYWORDS = {
    "education": ["教育经历", "教育背景", "教育", "education"],
    "work": ["工作经历", "实习经历", "工作经验", "职业经历", "experience"],
    "project": ["项目经历", "项目经验", "项目", "projects", "project"],
    "skills": ["技能", "专业技能", "技能特长", "skills", "skill"],
    "awards": ["获奖情况", "荣誉奖项", "奖励荣誉", "获奖经历", "awards", "honors", "荣誉"],
}

LABELED_FIELDS = {
    "school": ["学校", "院校", "毕业院校"],
    "major": ["专业"],
    "degree": ["学历", "学位"],
    "grade": ["年级"],
    "location": ["所在地", "居住地", "城市"],
    "intention": ["求职意向", "意向岗位", "应聘岗位"],
    "github": ["Github 账号", "GitHub 账号", "Github账号", "GitHub账号", "Github", "GitHub"],
    "phone": ["联系电话", "手机", "手机号", "电话"],
    "email": ["电子邮箱", "邮箱", "Email", "E-mail", "email", "mail"],
}

ALL_FIELD_LABELS = [label for labels in LABELED_FIELDS.values() for label in labels]

DATE_REGEX = re.compile(
    r"((?:19|20)\d{2}(?:[./-]\d{1,2}|年\d{1,2}月?)?(?:\s*(?:-|–|—|~|至|到)\s*(?:至今|现在|Present|present|Current|current|(?:19|20)\d{2}(?:[./-]\d{1,2}|年\d{1,2}月?)?))?)",
    re.I,
)


def _clean_inline_text(value: str = "") -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("`", "").replace("**", "").replace("__", "")
    value = re.sub(r"^\s*>+\s?", "", value)
    return value.strip()


def _normalize_title(value: str = "") -> str:
    normalized = _clean_inline_text(value)
    normalized = re.sub(r"^#+\s*", "", normalized)
    normalized = re.sub(r"[：:]", "", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.lower()


def _is_markdown_table_divider(line: str = "") -> bool:
    return bool(re.match(r"^\s*\|?[\s:-]+(?:\|[\s:-]+)+\|?\s*$", line))


def _is_markdown_table_row(line: str = "") -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _split_table_cells(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    if not stripped:
        return []
    return [_clean_inline_text(cell) for cell in stripped.split("|")]


def _match_section_key(line: str = "") -> str | None:
    normalized = _normalize_title(line)
    if not normalized:
        return None

    best_key = None
    best_score = 0

    for key, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = _normalize_title(keyword)
            if not normalized_keyword:
                continue
            if normalized == normalized_keyword:
                score = len(normalized_keyword) + 100
            elif normalized.startswith(normalized_keyword):
                score = len(normalized_keyword) + 50
            elif normalized_keyword in normalized and len(normalized) <= max(24, len(normalized_keyword) * 4):
                score = len(normalized_keyword)
            else:
                continue

            if score > best_score:
                best_key = key
                best_score = score

    return best_key


def _is_standalone_section_title(line: str = "") -> bool:
    return _match_section_key(line) is not None


def _looks_like_date_range(line: str = "") -> bool:
    return bool(DATE_REGEX.search(line))


def _extract_title_and_date(line: str = "") -> tuple[str, str]:
    match = DATE_REGEX.search(line)
    if not match:
        return line.strip(), ""

    title = line.replace(match.group(0), "")
    title = re.sub(r"[|｜·•]", " ", title)
    title = re.sub(r"\s{2,}", " ", title).strip()
    return title, match.group(0).strip()


def _extract_table_blocks(markdown: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []

    for raw_line in markdown.splitlines():
        if _is_markdown_table_row(raw_line) or (_is_markdown_table_divider(raw_line) and current):
            current.append(raw_line)
            continue

        if current:
            blocks.append(current)
            current = []

    if current:
        blocks.append(current)

    return blocks


def _extract_table_column_texts(markdown: str) -> list[str]:
    column_texts: list[str] = []

    for block in _extract_table_blocks(markdown):
        rows = [row for row in block if _is_markdown_table_row(row) and not _is_markdown_table_divider(row)]
        if not rows:
            continue

        parsed_rows = [_split_table_cells(row) for row in rows]
        max_cols = max((len(row) for row in parsed_rows), default=0)
        if max_cols <= 1:
            continue

        columns: list[list[str]] = [[] for _ in range(max_cols)]
        for row in parsed_rows:
            for index, cell in enumerate(row):
                if cell:
                    columns[index].append(cell)

        for column in columns:
            cleaned_lines = []
            for line in column:
                if not line:
                    continue
                if cleaned_lines and cleaned_lines[-1] == line:
                    continue
                cleaned_lines.append(line)
            if cleaned_lines:
                column_texts.append("\n".join(cleaned_lines))

    return column_texts


def _extract_table_pairs(markdown: str) -> dict[str, str]:
    pairs: dict[str, str] = {}

    for block in _extract_table_blocks(markdown):
        for row in block:
            if not _is_markdown_table_row(row) or _is_markdown_table_divider(row):
                continue

            cells = [cell for cell in _split_table_cells(row) if cell]
            if len(cells) < 2:
                continue

            for index in range(0, len(cells) - 1, 2):
                key = re.sub(r"[：:]$", "", cells[index]).strip()
                value = cells[index + 1].strip()
                if key and value and key not in pairs:
                    pairs[key] = value

    return pairs


def _strip_table_lines(markdown: str) -> str:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        if _is_markdown_table_row(raw_line) or _is_markdown_table_divider(raw_line):
            continue
        lines.append(raw_line)
    return "\n".join(lines).strip()


def _split_markdown_sections(markdown: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] = {"title": "", "key": None, "lines": []}

    def push_current():
        if current["title"] or any(_clean_inline_text(line) for line in current["lines"]):
            sections.append({"title": current["title"], "key": current["key"], "lines": list(current["lines"])})

    for raw_line in markdown.splitlines():
        trimmed = raw_line.strip()
        heading_match = re.match(r"^#{1,6}\s+(.+)$", trimmed)
        section_title = ""
        section_key = None

        if heading_match:
            section_title = _clean_inline_text(heading_match.group(1))
            section_key = _match_section_key(section_title)
        else:
            section_key = _match_section_key(trimmed)
            if section_key and len(_clean_inline_text(trimmed)) <= 32:
                section_title = _clean_inline_text(trimmed)

        if not section_title and _is_standalone_section_title(trimmed):
            section_title = _clean_inline_text(trimmed)
            section_key = _match_section_key(section_title)

        if section_title:
            push_current()
            current = {"title": section_title, "key": section_key, "lines": []}
            continue

        current["lines"].append(raw_line)

    push_current()
    return sections


def _find_section(sections: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    return next(
        (
            section
            for section in sections
            if section.get("key") == key
            or any(_normalize_title(keyword) in _normalize_title(section["title"]) for keyword in SECTION_KEYWORDS[key])
        ),
        None,
    )


def _lines_to_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []

    for raw_line in lines:
        if _is_markdown_table_divider(raw_line):
            continue

        heading_match = re.match(r"^#{2,6}\s+(.+)$", raw_line.strip())
        if heading_match:
            if current:
                blocks.append(current)
            current = [_clean_inline_text(heading_match.group(1))]
            continue

        cleaned = _clean_inline_text(raw_line)
        cleaned = re.sub(r"^\s*[-*•]\s*", "", cleaned).strip()
        if not cleaned:
            if current:
                blocks.append(current)
                current = []
            continue

        current.append(cleaned)

    if current:
        blocks.append(current)

    return blocks


def _parse_timeline_section(section: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not section:
        return []

    items: list[dict[str, Any]] = []
    for block in _lines_to_blocks(section["lines"]):
        first_line = block[0] if block else ""
        title, inline_date = _extract_title_and_date(first_line)
        date = inline_date
        rest = block[1:]

        if not date:
            date_index = next((index for index, line in enumerate(rest) if _looks_like_date_range(line)), -1)
            if date_index >= 0:
                date = rest[date_index].strip()
                rest = [line for index, line in enumerate(rest) if index != date_index]

        subtitle = ""
        if rest and len(rest[0]) <= 30 and not _looks_like_date_range(rest[0]) and not re.search(r"[。；;]", rest[0]):
            subtitle = rest[0].strip()
            rest = rest[1:]

        if title.strip():
            items.append(
                {
                    "title": title.strip(),
                    "subtitle": subtitle,
                    "date": date,
                    "details": [line for line in rest if line],
                }
            )

    return items


def _parse_skill_section(section: dict[str, Any] | None) -> list[str]:
    if not section:
        return []

    skills: list[str] = []
    for line in section["lines"]:
        cleaned = _clean_inline_text(line)
        cleaned = re.sub(r"^\s*[-*•]\s*", "", cleaned).strip()
        if not cleaned:
            continue
        skills.extend(item.strip() for item in re.split(r"[、，,；;|｜/]", cleaned))

    return list(dict.fromkeys(item for item in skills if item and len(item) <= 30))


def _parse_award_section(section: dict[str, Any] | None) -> list[str]:
    if not section:
        return []

    return [" ".join(block).strip() for block in _lines_to_blocks(section["lines"]) if block]


def _extract_phone(markdown: str, table_pairs: dict[str, str] | None = None) -> str:
    labeled_phone = _extract_labeled_field(markdown, LABELED_FIELDS["phone"], table_pairs=table_pairs)
    if labeled_phone:
        return labeled_phone

    match = re.search(r"(?:\+?86[-\s]?)?(?:1[3-9]\d{9}|\d{3,4}[-\s]?\d{7,8})", markdown)
    return match.group(0).strip() if match else ""


def _extract_email(markdown: str, table_pairs: dict[str, str] | None = None) -> str:
    labeled_email = _extract_labeled_field(markdown, LABELED_FIELDS["email"], table_pairs=table_pairs)
    if labeled_email:
        email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,10}", labeled_email, re.I)
        if email_match:
            return email_match.group(0).strip()
        return labeled_email

    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,10}", markdown, re.I)
    return match.group(0).strip() if match else ""


def _extract_labeled_field(markdown: str, labels: list[str], table_pairs: dict[str, str] | None = None) -> str:
    table_pairs = table_pairs or {}

    for key, value in table_pairs.items():
        normalized_key = _normalize_title(key)
        if any(_normalize_title(label) == normalized_key or _normalize_title(label) in normalized_key for label in labels):
            return re.sub(r"\s+", " ", value).strip()

    labels_pattern = "|".join(re.escape(label) for label in labels)
    lookahead_labels_pattern = "|".join(re.escape(label) for label in ALL_FIELD_LABELS)
    pattern = rf"(?:{labels_pattern})\s*[：:]\s*(.+?)(?=(?:{lookahead_labels_pattern})\s*[：:]|\n|$)"
    match = re.search(pattern, markdown, re.I | re.S)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()

    for line in markdown.splitlines():
        cleaned = _clean_inline_text(line)
        if not cleaned:
            continue
        for label in labels:
            if cleaned.startswith(label):
                candidate = cleaned[len(label) :].lstrip("：:|- ").strip()
                if candidate:
                    return candidate

    return ""


def _extract_basic_info(markdown: str, table_pairs: dict[str, str] | None = None) -> dict[str, str]:
    return {
        "school": _extract_labeled_field(markdown, LABELED_FIELDS["school"], table_pairs=table_pairs),
        "major": _extract_labeled_field(markdown, LABELED_FIELDS["major"], table_pairs=table_pairs),
        "degree": _extract_labeled_field(markdown, LABELED_FIELDS["degree"], table_pairs=table_pairs),
        "grade": _extract_labeled_field(markdown, LABELED_FIELDS["grade"], table_pairs=table_pairs),
        "location": _extract_labeled_field(markdown, LABELED_FIELDS["location"], table_pairs=table_pairs),
        "intention": _extract_labeled_field(markdown, LABELED_FIELDS["intention"], table_pairs=table_pairs),
        "github": _extract_labeled_field(markdown, LABELED_FIELDS["github"], table_pairs=table_pairs),
    }


def _merge_timeline_items(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()

    for group in groups:
        for item in group:
            key = (
                item.get("title", ""),
                item.get("subtitle", ""),
                item.get("date", ""),
                tuple(item.get("details", []) or []),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

    return merged


def _merge_unique_strings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for group in groups:
        for item in group:
            cleaned = re.sub(r"\s+", " ", item).strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            merged.append(cleaned)

    return merged


def _extract_name(markdown: str, filename: str) -> str:
    lines = [_clean_inline_text(line) for line in markdown.splitlines()]
    lines = [line for line in lines if line]

    for line in lines[:8]:
        if _is_standalone_section_title(line):
            continue
        if "简历" in line.lower() or "resume" in line.lower():
            continue
        if "@" in line or re.search(r"\d{6,}", line) or _looks_like_date_range(line):
            continue
        if len(line) > 30 or re.fullmatch(r"[\d\s\-_.]+", line):
            continue
        return re.sub(r"[:：]$", "", line)

    return re.sub(r"\.pdf$", "", filename, flags=re.I)


def _build_structured_resume(markdown_content: str, filename: str) -> dict[str, Any]:
    markdown_content = markdown_content or ""
    table_pairs = _extract_table_pairs(markdown_content)
    text_body = _strip_table_lines(markdown_content)
    sources = [source for source in [text_body, *_extract_table_column_texts(markdown_content)] if source]
    combined_text = "\n\n".join(source for source in sources if source)

    education_groups: list[list[dict[str, Any]]] = []
    work_groups: list[list[dict[str, Any]]] = []
    project_groups: list[list[dict[str, Any]]] = []
    skill_groups: list[list[str]] = []
    award_groups: list[list[str]] = []

    for source in sources:
        sections = _split_markdown_sections(source)
        education_groups.append(_parse_timeline_section(_find_section(sections, "education")))
        work_groups.append(_parse_timeline_section(_find_section(sections, "work")))
        project_groups.append(_parse_timeline_section(_find_section(sections, "project")))
        skill_groups.append(_parse_skill_section(_find_section(sections, "skills")))
        award_groups.append(_parse_award_section(_find_section(sections, "awards")))

    basic_info = _extract_basic_info(combined_text, table_pairs=table_pairs)
    education = _merge_timeline_items(*education_groups)

    if not education and any(basic_info.get(key) for key in ("school", "major", "degree", "grade")):
        education_details = []
        if basic_info.get("degree"):
            education_details.append(f"学历：{basic_info['degree']}")
        if basic_info.get("grade"):
            education_details.append(f"年级：{basic_info['grade']}")
        if basic_info.get("location"):
            education_details.append(f"所在地：{basic_info['location']}")

        education = [
            {
                "title": basic_info.get("school") or "教育信息",
                "subtitle": basic_info.get("major") or "",
                "date": "",
                "details": education_details,
            }
        ]

    return {
        "name": _extract_name(combined_text or markdown_content, filename),
        "phone": _extract_phone(combined_text or markdown_content, table_pairs=table_pairs),
        "email": _extract_email(combined_text or markdown_content, table_pairs=table_pairs),
        "basic_info": basic_info,
        "education": education,
        "work": _merge_timeline_items(*work_groups),
        "projects": _merge_timeline_items(*project_groups),
        "skills": _merge_unique_strings(*skill_groups),
        "awards": _merge_unique_strings(*award_groups),
    }


def _serialize_resume(resume_record: UserResume, include_markdown: bool = True) -> dict[str, Any]:
    data = resume_record.to_dict(include_markdown=include_markdown)
    data["structured_resume"] = _build_structured_resume(resume_record.markdown_content or "", resume_record.filename)
    return data


def _is_summary_in_progress(status: str | None) -> bool:
    return (status or "pending") in {"pending", "processing", "extracting"}


async def _mark_stale_summary_if_needed(db: AsyncSession, resume_record: UserResume) -> UserResume:
    if not _is_summary_in_progress(resume_record.summary_status):
        return resume_record

    updated_at = resume_record.updated_at or resume_record.created_at
    if updated_at and utc_now_naive() - updated_at < SUMMARY_STALE_TIMEOUT:
        return resume_record

    resume_record.summary_status = "failed"
    resume_record.summary_error = "简历分析超时，请点击“重新分析”重试"
    await db.commit()
    await db.refresh(resume_record)
    logger.warning("简历摘要任务超时，已标记失败，resume_id=%s", resume_record.id)
    return resume_record


def _fire_and_forget(coro, *, label: str) -> None:
    """创建后台任务并追踪异常，防止静默丢失"""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    logger.info("%s已提交", label)

    def _on_done(done_task: asyncio.Task[Any]) -> None:
        _BACKGROUND_TASKS.discard(done_task)
        try:
            exc = done_task.exception()
        except asyncio.CancelledError:
            logger.warning("%s已取消", label)
            return
        if exc is not None:
            logger.error("%s异常: %s", label, exc)

    task.add_done_callback(_on_done)


async def _trigger_summary_extraction(resume_id: int) -> None:
    """触发简历摘要提取（异步执行，不阻塞主流程）"""
    try:
        await resume_summary_service.update_resume_summary(resume_id)
    except Exception as e:
        logger.error(f"触发简历摘要提取失败，resume_id={resume_id}: {e}")
        # 显式更新 DB 状态为 failed，防止永远停留在 processing
        try:
            async with pg_manager.get_async_session_context() as session:
                from sqlalchemy import select

                result = await session.execute(select(UserResume).where(UserResume.id == resume_id))
                record = result.scalar_one_or_none()
                if record and _is_summary_in_progress(record.summary_status):
                    record.summary_status = "failed"
                    record.summary_error = f"后台任务异常: {e}"
                    await session.commit()
        except Exception as db_err:
            logger.error(f"更新失败状态时出错，resume_id={resume_id}: {db_err}")


@resume.get("")
async def get_my_resumes(current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserResume).where(UserResume.user_id == current_user.id).order_by(UserResume.created_at.desc(), UserResume.id.desc())
    )
    resume_records = result.scalars().all()
    return {
        "message": "success",
        "resumes": [resume_record.to_dict(include_markdown=False) for resume_record in resume_records],
    }


@resume.get("/{resume_id}")
async def get_my_resume_detail(
    resume_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id,
        )
    )
    resume_record = result.scalar_one_or_none()
    if resume_record is None:
        raise HTTPException(status_code=404, detail="简历不存在")
    resume_record = await _mark_stale_summary_if_needed(db, resume_record)

    return {
        "message": "success",
        "resume": _serialize_resume(resume_record),
    }


@resume.get("/{resume_id}/extract-progress")
async def extract_progress(
    resume_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 端点：流式返回简历提取进度"""
    # 验证简历归属
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id,
        )
    )
    resume_record = result.scalar_one_or_none()
    if resume_record is None:
        raise HTTPException(status_code=404, detail="简历不存在")

    async def event_stream():
        from src.storage.postgres.manager import pg_manager

        while True:
            try:
                async with pg_manager.get_async_session_context() as session:
                    result = await session.execute(
                        select(UserResume).where(UserResume.id == resume_id)
                    )
                    record = result.scalar_one_or_none()
                    if record is None:
                        yield f"data: {json.dumps({'stage': 'failed', 'error': '简历记录不存在'})}\n\n"
                        break
                    record = await _mark_stale_summary_if_needed(session, record)

                    status = record.summary_status or "pending"

                    if status == "completed":
                        yield f"data: {json.dumps({'stage': 'completed', 'summary': record.summary_json})}\n\n"
                        break
                    elif status == "failed":
                        yield f"data: {json.dumps({'stage': 'failed', 'error': record.summary_error or '提取失败'})}\n\n"
                        break
                    else:
                        yield f"data: {json.dumps({'stage': 'extracting', 'status': status})}\n\n"
            except Exception as e:
                logger.error(f"SSE 进度查询异常: {e}")
                yield f"data: {json.dumps({'stage': 'failed', 'error': str(e)})}\n\n"
                break

            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@resume.post("/{resume_id}/retry-extract")
async def retry_extract_resume(
    resume_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """重新触发简历摘要提取"""
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="简历不存在")
    record = await _mark_stale_summary_if_needed(db, record)

    if record.summary_status not in ("failed", "completed"):
        raise HTTPException(status_code=400, detail="简历正在处理中，请稍后重试")

    # 重置状态
    record.summary_status = "pending"
    record.summary_error = None
    await db.commit()

    # 异步触发重新提取
    _fire_and_forget(_trigger_summary_extraction(resume_id), label=f"简历摘要提取[{resume_id}]")

    return {"message": "success", "resume_id": resume_id}


@resume.post("")
async def upload_my_resume(
    file: UploadFile = File(...),
    job_id: int | None = Form(None),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择 PDF 简历文件")

    filename = Path(file.filename).name
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="仅支持上传 PDF 简历")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传的简历文件为空")

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        content_hash = await calculate_content_hash(file_bytes)
        markdown_content, _ = await process_file_to_markdown(
            temp_path,
            params={
                "enable_ocr": "mineru_official",
                "db_id": f"user_resume_{current_user.id}_{uuid.uuid4().hex[:8]}",
            },
        )

        if not markdown_content or not markdown_content.strip():
            logger.warning(f"PDF 解析结果为空，filename={filename}, user={current_user.user_id}")
            raise HTTPException(status_code=422, detail="PDF 解析失败：未能从文件中提取到文本内容，请检查文件是否损坏")

        object_name = f"{current_user.user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        file_url = await aupload_file_to_minio("user-resumes", object_name, file_bytes, "pdf")

        resume_record = UserResume(
            user_id=current_user.id,
            filename=filename,
            content_hash=content_hash,
            file_size=len(file_bytes),
            bucket_name="user-resumes",
            object_name=object_name,
            file_url=file_url,
            parser_name="mineru_official",
            markdown_content=markdown_content,
        )
        db.add(resume_record)

        await db.commit()
        await db.refresh(resume_record)

        if openviking_service.is_enabled():
            try:
                await openviking_service.sync_resume(resume_record)
                await openviking_service.sync_resume_memory(resume_record)
            except Exception as exc:
                logger.warning("Sync resume to OpenViking failed for user %s: %s", current_user.user_id, exc)

        # 异步触发 LLM 瑘历摘要提取（不阻塞主流程）
        _fire_and_forget(_trigger_summary_extraction(resume_record.id), label=f"简历摘要提取[{resume_record.id}]")

        # 如果指定了目标岗位，异步触发匹配
        if job_id:
            resume_record.target_job_id = job_id
            resume_record.match_status = "pending"
            await db.commit()
            _fire_and_forget(_trigger_resume_match(resume_record.id, job_id), label=f"简历岗位匹配[{resume_record.id}:{job_id}]")

        return {
            "message": "success",
            "resume": _serialize_resume(resume_record),
        }
    except DocumentProcessorException as exc:
        logger.error(f"Resume parsing failed for user {current_user.user_id}: {exc}")
        raise HTTPException(status_code=502, detail=f"简历解析失败：{exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Resume upload failed for user {current_user.user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"简历上传失败：{exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@resume.delete("/{resume_id}")
async def delete_my_resume(
    resume_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id,
        )
    )
    resume_record = result.scalar_one_or_none()
    if resume_record is None:
        raise HTTPException(status_code=404, detail="简历不存在")

    try:
        minio_client = get_minio_client()
        await minio_client.adelete_file(resume_record.bucket_name, resume_record.object_name)

        if openviking_service.is_enabled():
            try:
                await openviking_service.remove_resume(resume_record)
                await openviking_service.remove_resume_memory(resume_record)
            except Exception as exc:
                logger.warning("Remove resume from OpenViking failed for user %s: %s", current_user.user_id, exc)

        await db.delete(resume_record)
        await db.commit()
        return {"message": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Resume delete failed for user {current_user.user_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"删除简历失败：{exc}") from exc


# ─── 简历匹配相关 API ───


class ResumeMatchRequest(BaseModel):
    """简历匹配请求"""
    job_id: int | None = None
    auto_detect: bool = False


async def _trigger_resume_match(resume_id: int, job_id: int) -> None:
    """异步触发简历匹配"""
    from src.services.builtin_jobs import get_builtin_job
    from src.storage.postgres.manager import pg_manager

    try:
        # 从内置岗位数据获取 JD
        job_dict = get_builtin_job(job_id)
        if not job_dict:
            logger.warning(f"简历匹配跳过：岗位不存在，job_id={job_id}")
            return

        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(select(UserResume).where(UserResume.id == resume_id))
            resume = result.scalar_one_or_none()
            if not resume or not resume.summary_json:
                logger.warning(f"简历匹配跳过：简历不存在或摘要为空，resume_id={resume_id}")
                return

            resume.match_status = "processing"
            await session.commit()

            match_result = await asyncio.to_thread(
                match_service.calculate_match,
                job_dict,
                resume.summary_json,
            )

            resume.match_result = match_result
            resume.match_status = "completed"
            resume.target_job_id = job_id
            await session.commit()
            logger.info(f"简历匹配完成，resume_id={resume_id}, job_id={job_id}")
    except Exception as e:
        logger.error(f"简历匹配失败，resume_id={resume_id}: {e}")
        try:
            async with pg_manager.get_async_session_context() as session:
                result = await session.execute(select(UserResume).where(UserResume.id == resume_id))
                resume = result.scalar_one_or_none()
                if resume:
                    resume.match_status = "failed"
                    await session.commit()
        except Exception as cleanup_exc:  # noqa: BLE001 - background cleanup must not propagate
            logger.error(f"更新匹配失败状态也失败，resume_id={resume_id}: {cleanup_exc}")


@resume.post("/{resume_id}/match")
async def match_resume_with_job(
    resume_id: int,
    match_request: ResumeMatchRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """简历与岗位匹配"""
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id,
        )
    )
    resume_record = result.scalar_one_or_none()
    if resume_record is None:
        raise HTTPException(status_code=404, detail="简历不存在")

    if not resume_record.summary_json:
        raise HTTPException(status_code=400, detail="简历摘要尚未提取完成，请稍后再试")

    job_id = match_request.job_id
    job_dict = None

    # 自动检测：从简历意向岗位匹配内置岗位
    if match_request.auto_detect and not job_id:
        detected = resume_record.summary_json.get("job_preference", {}).get("job_intention", "")
        if detected:
            from src.services.builtin_jobs import get_all_builtin_jobs

            for job in get_all_builtin_jobs():
                if detected in job["title"] or detected in job.get("description", ""):
                    job_dict = job
                    job_id = job["id"]
                    break

    if not job_id:
        raise HTTPException(status_code=400, detail="请指定目标岗位或开启自动检测")

    # 获取内置岗位
    if not job_dict:
        from src.services.builtin_jobs import get_builtin_job

        job_dict = get_builtin_job(job_id)
    if not job_dict:
        raise HTTPException(status_code=404, detail="岗位不存在")

    # 执行匹配（在线程池中运行避免阻塞事件循环）
    match_result = await asyncio.to_thread(
        match_service.calculate_match,
        job_dict=job_dict,
        resume_summary=resume_record.summary_json,
    )

    # 持久化
    resume_record.target_job_id = job_id
    resume_record.match_result = match_result
    resume_record.match_status = "completed"
    await db.commit()
    await db.refresh(resume_record)

    return {
        "message": "success",
        "match_result": match_result,
        "resume_summary": resume_record.summary_json,
        "job": job_dict,
    }


@resume.post("/{resume_id}/detect-position")
async def detect_resume_position(
    resume_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """从简历中检测意向岗位并推荐匹配岗位"""
    result = await db.execute(
        select(UserResume).where(
            UserResume.id == resume_id,
            UserResume.user_id == current_user.id,
        )
    )
    resume_record = result.scalar_one_or_none()
    if resume_record is None:
        raise HTTPException(status_code=404, detail="简历不存在")

    if not resume_record.summary_json:
        raise HTTPException(status_code=400, detail="简历摘要尚未提取完成，请稍后再试")

    detected_position = (
        resume_record.summary_json.get("job_preference", {}).get("job_intention", "")
        or resume_record.detected_position
        or ""
    )

    if not detected_position:
        # 尝试从 structured_resume 中提取
        structured = _build_structured_resume(resume_record.markdown_content or "", resume_record.filename)
        detected_position = structured.get("basic_info", {}).get("intention", "")

    recommended_jobs = []
    if detected_position:
        # 更新 detected_position
        resume_record.detected_position = detected_position
        await db.commit()

        # 从内置岗位中搜索匹配
        from src.services.builtin_jobs import get_all_builtin_jobs

        for job in get_all_builtin_jobs():
            if detected_position in job["title"] or detected_position in job.get("description", ""):
                recommended_jobs.append(job)
            if len(recommended_jobs) >= 10:
                break

    return {
        "message": "success",
        "detected_position": detected_position,
        "recommended_jobs": recommended_jobs,
    }
