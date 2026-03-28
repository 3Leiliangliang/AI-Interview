"""职位描述管理 API"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from src.storage.postgres.models_business import JobDescription, User
from src.services.match_service import match_service

job = APIRouter(prefix="/job", tags=["job"])


class JobDescriptionCreate(BaseModel):
    """创建职位描述的请求模型"""
    title: str
    department: str | None = None
    description: str | None = None
    requirements: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    min_experience_years: int | None = None
    education_level: str | None = None
    salary_range: str | None = None
    status: str = Field(default="active", pattern="^(draft|active|closed)$")


class JobDescriptionUpdate(BaseModel):
    """更新职位描述的请求模型"""
    title: str | None = None
    department: str | None = None
    description: str | None = None
    requirements: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    min_experience_years: int | None = None
    education_level: str | None = None
    salary_range: str | None = None
    status: str | None = None


class MatchRequest(BaseModel):
    """简历-JD匹配请求模型"""
    job_id: int
    resume_summary: dict[str, Any]


class MatchErrorResponse(BaseModel):
    """匹配错误响应模型"""
    error: str
    detail: str


@job.get("")
async def list_job_descriptions(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    skip: int = Query(default=0, ge=0, description="跳过的记录数"),
    limit: int = Query(default=20, ge=1, le=100, description="返回的记录数"),
):
    """获取职位描述列表（支持分页）"""
    query = select(JobDescription).order_by(JobDescription.created_at.desc())

    if status:
        query = query.where(JobDescription.status == status)

    # 获取总数
    from sqlalchemy import func

    count_query = select(func.count()).select_from(JobDescription)
    if status:
        count_query = count_query.where(JobDescription.status == status)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 应用分页
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "message": "success",
        "jobs": [job.to_dict() for job in jobs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@job.get("/{job_id}")
async def get_job_description(
    job_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个职位描述详情"""
    result = await db.execute(select(JobDescription).where(JobDescription.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="职位描述不存在")

    return {
        "message": "success",
        "job": job.to_dict(),
    }


@job.post("")
async def create_job_description(
    job_data: JobDescriptionCreate,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """创建职位描述"""
    job = JobDescription(
        title=job_data.title,
        department=job_data.department,
        description=job_data.description,
        requirements=job_data.requirements,
        required_skills=job_data.required_skills or [],
        preferred_skills=job_data.preferred_skills or [],
        min_experience_years=job_data.min_experience_years,
        education_level=job_data.education_level,
        salary_range=job_data.salary_range,
        status=job_data.status,
        created_by=current_user.user_id,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    return {
        "message": "success",
        "job": job.to_dict(),
    }


@job.put("/{job_id}")
async def update_job_description(
    job_id: int,
    job_data: JobDescriptionUpdate,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """更新职位描述"""
    result = await db.execute(select(JobDescription).where(JobDescription.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="职位描述不存在")

    # 更新非空字段
    update_data = job_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(job, key):
            setattr(job, key, value)

    await db.commit()
    await db.refresh(job)

    return {
        "message": "success",
        "job": job.to_dict(),
    }


@job.delete("/{job_id}")
async def delete_job_description(
    job_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """删除职位描述"""
    result = await db.execute(select(JobDescription).where(JobDescription.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="职位描述不存在")

    await db.delete(job)
    await db.commit()

    return {"message": "success"}


@job.post("/match")
async def match_resume_with_job(
    match_data: MatchRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """简历与JD匹配"""
    # 增强输入验证
    if not match_data.resume_summary:
        raise HTTPException(status_code=400, detail="简历摘要不能为空")
    
    if not isinstance(match_data.resume_summary, dict):
        raise HTTPException(status_code=400, detail="简历摘要格式错误：必须是字典类型")
    
    # 至少需要包含一个有效字段
    valid_keys = ["skills", "work_experience", "education", "projects", "work"]
    if not any(key in match_data.resume_summary for key in valid_keys):
        raise HTTPException(
            status_code=400, 
            detail=f"简历摘要缺少必要字段，需要包含以下至少一个：{', '.join(valid_keys)}"
        )

    # 获取JD
    result = await db.execute(select(JobDescription).where(JobDescription.id == match_data.job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="职位描述不存在")

    # 执行匹配（同步函数，不需要await）
    match_result = match_service.calculate_match(
        job_dict=job.to_dict(),
        resume_summary=match_data.resume_summary,
    )

    # 检查是否发生了错误（通过 special key 标记）
    if match_result.get("_error"):
        raise HTTPException(
            status_code=500,
            detail=match_result.get("_error_detail", "匹配计算失败"),
        )

    # 移除内部标记字段
    match_result.pop("_error", None)
    match_result.pop("_error_detail", None)

    return {
        "message": "success",
        "match_result": match_result,
    }
