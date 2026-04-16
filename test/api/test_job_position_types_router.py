from __future__ import annotations

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_get_job_position_types(test_client, admin_headers):
    response = await test_client.get("/api/job/position-types", headers=admin_headers)

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["message"] == "success"
    assert data["default_position_key"] == "backend"
    assert not any(item["key"] == "database" for item in data["position_types"])
    assert any(item["label"] == "算法工程师" for item in data["position_types"])
    assert any(item["label"] == "系统架构师" for item in data["position_types"])
    assert any(item["key"] == "ai_app" for item in data["position_types"])
