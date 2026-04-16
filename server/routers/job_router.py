"""职位描述 API 与岗位类型配置。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.utils.auth_middleware import get_required_user
from src.services.builtin_jobs import (
    DEFAULT_POSITION_KEY,
    get_all_builtin_jobs,
    get_builtin_job,
    get_default_position_config,
    get_public_position_types,
)
from src.services.match_service import match_service
from src.storage.postgres.models_business import User

job = APIRouter(prefix="/job", tags=["job"])


class MatchRequest(BaseModel):
    """简历-JD匹配请求模型"""
    job_id: int
    resume_summary: dict[str, Any]


@job.get("")
async def list_job_descriptions(
    current_user: User = Depends(get_required_user),
):
    """获取内置岗位列表与岗位类型配置"""
    jobs = get_all_builtin_jobs()
    return {
        "message": "success",
        "jobs": jobs,
        "position_types": get_public_position_types(),
        "default_position_key": DEFAULT_POSITION_KEY,
        "default_position": get_default_position_config(),
        "total": len(jobs),
        "skip": 0,
        "limit": len(jobs),
    }


@job.get("/position-types")
async def list_position_types(
    current_user: User = Depends(get_required_user),
):
    """获取统一岗位类型配置"""
    _ = current_user
    return {
        "message": "success",
        "position_types": get_public_position_types(),
        "default_position_key": DEFAULT_POSITION_KEY,
        "default_position": get_default_position_config(),
    }


@job.get("/{job_id}")
async def get_job_description(
    job_id: int,
    current_user: User = Depends(get_required_user),
):
    """获取单个内置岗位详情"""
    job_data = get_builtin_job(job_id)
    if job_data is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {
        "message": "success",
        "job": job_data,
    }


@job.post("/match")
async def match_resume_with_job(
    match_data: MatchRequest,
    current_user: User = Depends(get_required_user),
):
    """简历与JD匹配"""
    if not match_data.resume_summary:
        raise HTTPException(status_code=400, detail="简历摘要不能为空")

    if not isinstance(match_data.resume_summary, dict):
        raise HTTPException(status_code=400, detail="简历摘要格式错误：必须是字典类型")

    valid_keys = ["skills", "work_experience", "education", "projects", "work"]
    if not any(key in match_data.resume_summary for key in valid_keys):
        raise HTTPException(
            status_code=400,
            detail=f"简历摘要缺少必要字段，需要包含以下至少一个：{', '.join(valid_keys)}",
        )

    job_data = get_builtin_job(match_data.job_id)
    if job_data is None:
        raise HTTPException(status_code=404, detail="岗位不存在")

    match_result = match_service.calculate_match(
        job_dict=job_data,
        resume_summary=match_data.resume_summary,
    )

    if match_result.get("_error"):
        raise HTTPException(
            status_code=500,
            detail=match_result.get("_error_detail", "匹配计算失败"),
        )

    match_result.pop("_error", None)
    match_result.pop("_error_detail", None)

    return {
        "message": "success",
        "match_result": match_result,
    }
