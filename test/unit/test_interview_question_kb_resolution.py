from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.common.toolkits.kbs import tools as kb_tools


@pytest.mark.asyncio
async def test_backend_role_matching_does_not_misclassify_javascript_kb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_databases() -> dict:
        return {
            "databases": [
                {
                    "db_id": "db_backend",
                    "name": "JavaGuide 后端面试",
                    "description": "Java backend interview handbook with database and distributed system topics.",
                },
                {
                    "db_id": "db_react",
                    "name": "React 面试题库",
                    "description": "React interview questions and javascript coding exercises.",
                },
                {
                    "db_id": "db_sql",
                    "name": "SQL 面试题库",
                    "description": "SQL interview questions covering indexes and transactions.",
                },
            ]
        }

    monkeypatch.setattr(
        kb_tools,
        "knowledge_base",
        SimpleNamespace(get_databases=fake_get_databases),
    )

    resolved = await kb_tools._resolve_candidate_kbs(["backend_interview_questions"])

    assert [item["db_id"] for item in resolved] == ["db_backend"]
