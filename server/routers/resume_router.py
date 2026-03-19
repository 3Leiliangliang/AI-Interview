import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from src.knowledge.indexing import process_file_to_markdown
from src.knowledge.utils import calculate_content_hash
from src.plugins.document_processor_base import DocumentProcessorException
from src.services.openviking_service import openviking_service
from src.storage.minio import aupload_file_to_minio, get_minio_client
from src.storage.postgres.models_business import User, UserResume
from src.utils import logger

resume = APIRouter(prefix="/resume", tags=["resume"])

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

    return {
        "message": "success",
        "resume": _serialize_resume(resume_record),
    }


@resume.post("")
async def upload_my_resume(
    file: UploadFile = File(...),
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
        markdown_content = await process_file_to_markdown(
            temp_path,
            params={
                "enable_ocr": "mineru_official",
                "db_id": f"user_resume_{current_user.id}_{uuid.uuid4().hex[:8]}",
            },
        )

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
            except Exception as exc:
                logger.warning("Sync resume to OpenViking failed for user %s: %s", current_user.user_id, exc)

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
