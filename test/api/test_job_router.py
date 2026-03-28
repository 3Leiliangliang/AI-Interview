"""
Integration tests for job description API routes (P0-1: JD-简历智能匹配系统)
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_create_job_description(test_client, admin_headers):
    """测试创建职位描述"""
    unique_id = uuid.uuid4().hex[:8]
    payload = {
        "title": f"Python开发工程师_{unique_id}",
        "department": "技术部",
        "description": "负责后端系统开发",
        "requirements": "熟练掌握Python、Fluent in FastAPI",
        "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        "preferred_skills": ["Docker", "Kubernetes"],
        "min_experience_years": 3,
        "education_level": "本科",
        "salary_range": "20k-35k",
        "status": "active",
    }

    response = await test_client.post("/api/job", json=payload, headers=admin_headers)
    assert response.status_code == 200, f"Failed to create job description: {response.text}"

    data = response.json()
    assert data["message"] == "success"
    assert "job" in data

    job = data["job"]
    assert job["title"] == payload["title"]
    assert job["department"] == payload["department"]
    assert job["required_skills"] == payload["required_skills"]
    assert job["status"] == "active"

    # 验证自动生成的字段
    assert job["id"] is not None
    assert job["created_at"] is not None

    # 清理：删除创建的JD
    delete_response = await test_client.delete(f"/api/job/{job['id']}", headers=admin_headers)
    assert delete_response.status_code == 200


async def test_list_job_descriptions(test_client, admin_headers):
    """测试获取职位描述列表"""
    # 先创建一个JD
    unique_id = uuid.uuid4().hex[:8]
    create_payload = {
        "title": f"测试岗位_{unique_id}",
        "department": "测试部",
        "description": "测试描述",
        "requirements": "测试要求",
        "required_skills": ["Python"],
        "status": "active",
    }

    create_response = await test_client.post("/api/job", json=create_payload, headers=admin_headers)
    assert create_response.status_code == 200
    created_job = create_response.json()["job"]

    # 获取列表
    list_response = await test_client.get("/api/job", headers=admin_headers)
    assert list_response.status_code == 200, f"Failed to list jobs: {list_response.text}"

    list_data = list_response.json()
    assert list_data["message"] == "success"
    assert "jobs" in list_data
    assert isinstance(list_data["jobs"], list)
    assert len(list_data["jobs"]) >= 1

    # 清理
    delete_response = await test_client.delete(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert delete_response.status_code == 200


async def test_get_job_description_detail(test_client, admin_headers):
    """测试获取单个职位描述详情"""
    # 创建
    unique_id = uuid.uuid4().hex[:8]
    create_payload = {
        "title": f"详情测试岗位_{unique_id}",
        "department": "技术部",
        "description": "测试详情描述",
        "requirements": "测试要求",
        "required_skills": ["Python", "FastAPI", "Docker"],
        "preferred_skills": ["Redis"],
        "min_experience_years": 2,
        "education_level": "本科",
        "status": "active",
    }

    create_response = await test_client.post("/api/job", json=create_payload, headers=admin_headers)
    assert create_response.status_code == 200
    created_job = create_response.json()["job"]

    # 获取详情
    detail_response = await test_client.get(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert detail_response.status_code == 200, f"Failed to get job detail: {detail_response.text}"

    detail_data = detail_response.json()
    assert detail_data["message"] == "success"
    assert "job" in detail_data

    job = detail_data["job"]
    assert job["id"] == created_job["id"]
    assert job["title"] == create_payload["title"]
    assert job["required_skills"] == create_payload["required_skills"]
    assert job["preferred_skills"] == create_payload["preferred_skills"]

    # 清理
    delete_response = await test_client.delete(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert delete_response.status_code == 200


async def test_update_job_description(test_client, admin_headers):
    """测试更新职位描述"""
    # 创建
    unique_id = uuid.uuid4().hex[:8]
    create_payload = {
        "title": f"更新测试岗位_{unique_id}",
        "department": "技术部",
        "description": "原始描述",
        "requirements": "原始要求",
        "required_skills": ["Python"],
        "status": "active",
    }

    create_response = await test_client.post("/api/job", json=create_payload, headers=admin_headers)
    assert create_response.status_code == 200
    created_job = create_response.json()["job"]

    # 更新
    update_payload = {
        "title": f"更新后岗位_{unique_id}",
        "department": "产品部",
        "description": "更新后描述",
        "requirements": "更新后要求",
        "required_skills": ["Python", "JavaScript"],
        "status": "closed",
    }

    update_response = await test_client.put(f"/api/job/{created_job['id']}", json=update_payload, headers=admin_headers)
    assert update_response.status_code == 200, f"Failed to update job: {update_response.text}"

    update_data = update_response.json()
    assert update_data["message"] == "success"
    assert "job" in update_data

    updated_job = update_data["job"]
    assert updated_job["title"] == update_payload["title"]
    assert updated_job["department"] == update_payload["department"]
    assert updated_job["required_skills"] == update_payload["required_skills"]
    assert updated_job["status"] == update_payload["status"]

    # 清理
    delete_response = await test_client.delete(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert delete_response.status_code == 200


async def test_delete_job_description(test_client, admin_headers):
    """测试删除职位描述"""
    # 创建
    unique_id = uuid.uuid4().hex[:8]
    create_payload = {
        "title": f"删除测试岗位_{unique_id}",
        "department": "技术部",
        "description": "测试删除",
        "requirements": "测试要求",
        "required_skills": ["Python"],
        "status": "active",
    }

    create_response = await test_client.post("/api/job", json=create_payload, headers=admin_headers)
    assert create_response.status_code == 200
    created_job = create_response.json()["job"]

    # 删除
    delete_response = await test_client.delete(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert delete_response.status_code == 200, f"Failed to delete job: {delete_response.text}"
    assert delete_response.json()["message"] == "success"

    # 验证已删除
    detail_response = await test_client.get(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert detail_response.status_code == 404


async def test_match_resume_with_job(test_client, admin_headers):
    """测试简历与JD的匹配功能"""
    # 创建JD
    unique_id = uuid.uuid4().hex[:8]
    create_payload = {
        "title": f"匹配测试岗位_{unique_id}",
        "department": "技术部",
        "description": "负责后端系统开发",
        "requirements": "需要具备后端开发经验",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "preferred_skills": ["Redis", "Kubernetes"],
        "min_experience_years": 3,
        "education_level": "本科",
        "status": "active",
    }

    create_response = await test_client.post("/api/job", json=create_payload, headers=admin_headers)
    assert create_response.status_code == 200
    created_job = create_response.json()["job"]

    # 模拟简历数据（实际项目中应该使用已上传的简历）
    mock_resume_summary = {
        "skills": {
            "technical": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
            "languages": ["英语CET-6"],
            "certifications": []
        },
        "work_experience": [
            {
                "company": "ABC公司",
                "position": "高级Python开发工程师",
                "duration": "2020年6月 - 至今",
                "highlights": ["负责后端系统架构设计", "主导微服务改造"]
            }
        ],
        "education": [
            {
                "school": "某知名大学",
                "major": "计算机科学与技术",
                "degree": "本科"
            }
        ],
        "project_experience": [
            {
                "name": "电商平台后端重构",
                "role": "技术负责人",
                "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Redis"],
                "description": "负责系统架构重构",
                "results": "提升系统性能300%"
            }
        ]
    }

    # 执行匹配
    match_payload = {
        "job_id": created_job["id"],
        "resume_summary": mock_resume_summary,
    }

    match_response = await test_client.post("/api/job/match", json=match_payload, headers=admin_headers)
    assert match_response.status_code == 200, f"Failed to match resume with job: {match_response.text}"

    match_data = match_response.json()
    assert match_data["message"] == "success"
    assert "match_result" in match_data

    result = match_data["match_result"]
    # 验证匹配结果结构
    assert "overall_score" in result
    assert "skill_match" in result
    assert "experience_match" in result
    assert "risk_points" in result

    # 验证分数范围
    assert 0 <= result["overall_score"] <= 100
    assert 0 <= result["skill_match"]["score"] <= 100

    # 验证技能匹配详情
    assert "matched" in result["skill_match"]
    assert "missing" in result["skill_match"]

    # 清理
    delete_response = await test_client.delete(f"/api/job/{created_job['id']}", headers=admin_headers)
    assert delete_response.status_code == 200


async def test_job_description_requires_auth(test_client):
    """测试未认证用户无法访问JD API"""
    # 无token访问
    response = await test_client.get("/api/job")
    assert response.status_code == 401

    # 无效token访问
    headers = {"Authorization": "Bearer invalid_token"}
    response = await test_client.get("/api/job", headers=headers)
    assert response.status_code == 401


async def test_job_not_found(test_client, admin_headers):
    """测试获取不存在的JD"""
    response = await test_client.get("/api/job/999999", headers=admin_headers)
    assert response.status_code == 404
