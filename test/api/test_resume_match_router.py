"""
Integration tests for resume-job matching API routes
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _make_job_payload(suffix: str = "") -> dict:
    return {
        "title": f"测试匹配岗位_{suffix}",
        "department": "技术部",
        "description": "负责后端系统开发，参与架构设计",
        "requirements": "3年以上后端开发经验",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "preferred_skills": ["Redis", "Kubernetes"],
        "min_experience_years": 3,
        "education_level": "本科",
        "salary_range": "20k-35k",
        "status": "active",
    }


async def _create_test_job(test_client, admin_headers) -> dict:
    suffix = uuid.uuid4().hex[:8]
    payload = _make_job_payload(suffix)
    resp = await test_client.post("/api/job", json=payload, headers=admin_headers)
    assert resp.status_code == 200, f"Create job failed: {resp.text}"
    return resp.json()["job"]


async def _cleanup_job(test_client, admin_headers, job_id: int):
    resp = await test_client.delete(f"/api/job/{job_id}", headers=admin_headers)
    assert resp.status_code == 200


async def test_match_resume_with_job(test_client, admin_headers):
    """测试简历与岗位匹配接口"""
    job = await _create_test_job(test_client, admin_headers)

    try:
        match_payload = {
            "job_id": job["id"],
            "resume_summary": {
                "skills": {
                    "technical": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
                    "languages": ["英语 CET-6"],
                    "certifications": [],
                },
                "work_experience": [
                    {
                        "company": "ABC公司",
                        "position": "高级Python开发工程师",
                        "duration": "2020年6月 - 至今",
                        "highlights": ["负责后端系统架构设计"],
                    }
                ],
                "education": [{"school": "某大学", "major": "计算机科学", "degree": "本科"}],
                "project_experience": [
                    {
                        "name": "电商平台后端",
                        "role": "技术负责人",
                        "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
                    }
                ],
            },
        }

        resp = await test_client.post("/api/job/match", json=match_payload, headers=admin_headers)
        assert resp.status_code == 200, f"Match failed: {resp.text}"

        data = resp.json()
        assert data["message"] == "success"
        result = data["match_result"]

        assert "overall_score" in result
        assert "skill_match" in result
        assert "experience_match" in result
        assert "risk_points" in result
        assert 0 <= result["overall_score"] <= 100
        assert result["skill_match"]["matched_count"] > 0
    finally:
        await _cleanup_job(test_client, admin_headers, job["id"])


async def test_match_empty_resume_summary(test_client, admin_headers):
    """测试空简历摘要匹配"""
    job = await _create_test_job(test_client, admin_headers)

    try:
        resp = await test_client.post(
            "/api/job/match",
            json={"job_id": job["id"], "resume_summary": {}},
            headers=admin_headers,
        )
        assert resp.status_code == 400
    finally:
        await _cleanup_job(test_client, admin_headers, job["id"])


async def test_detect_position_no_summary(test_client, admin_headers):
    """测试意向检测 - 简历不存在"""
    resp = await test_client.post("/api/resume/999999/detect-position", headers=admin_headers)
    assert resp.status_code in (404, 405)


async def test_match_resume_detail_no_summary(test_client, admin_headers):
    """测试简历匹配 - 简历不存在"""
    resp = await test_client.post(
        "/api/resume/999999/match",
        json={"job_id": 1},
        headers=admin_headers,
    )
    assert resp.status_code in (404, 405)


async def test_match_service_skill_fuzzy():
    """测试 MatchService 技能模糊匹配"""
    from src.services.match_service import MatchService

    svc = MatchService()

    result = svc._calculate_skill_match(
        ["Python", "FastAPI", "PostgreSQL"],
        ["python", "fastapi", "postgresql", "docker"],
    )
    assert result.score == 100.0
    assert result.matched_count == 3
    assert len(result.missing) == 0


async def test_match_service_skill_partial():
    """测试 MatchService 部分技能匹配"""
    from src.services.match_service import MatchService

    svc = MatchService()

    result = svc._calculate_skill_match(
        ["Python", "FastAPI", "Kubernetes"],
        ["python", "fastapi"],
    )
    assert result.matched_count == 2
    assert result.total_count == 3
    assert "kubernetes" in result.missing


async def test_match_service_skill_alias():
    """测试 MatchService 技能别名映射"""
    from src.services.match_service import MatchService

    svc = MatchService()

    result = svc._calculate_skill_match(
        ["JavaScript", "TypeScript", "React"],
        ["js", "ts", "react"],
    )
    assert result.matched_count == 3


async def test_match_service_experience():
    """测试 MatchService 经验匹配"""
    from src.services.match_service import MatchService

    svc = MatchService()

    result = svc._calculate_experience_match(
        min_years=3,
        work_experience=[{"duration": "2020年6月 - 至今"}],
        project_experience=[{"name": "项目A"}, {"name": "项目B"}],
    )
    assert result.score > 0


async def test_match_service_calculate_match():
    """测试完整匹配计算"""
    from src.services.match_service import MatchService

    svc = MatchService()

    job_dict = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "min_experience_years": 2,
        "education_level": "本科",
    }
    resume_summary = {
        "skills": {"technical": ["Python", "FastAPI", "Docker"]},
        "work_experience": [{"duration": "2021年 - 至今", "company": "Test"}],
        "project_experience": [{"name": "项目A"}],
        "education": [{"degree": "本科"}],
    }

    result = svc.calculate_match(job_dict, resume_summary)
    assert "overall_score" in result
    assert result["overall_score"] > 0
    assert "skill_match" in result
    assert "experience_match" in result
