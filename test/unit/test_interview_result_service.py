from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import interview_result_service as service  # noqa: E402


def test_generate_improvement_plan_builds_structured_sections(monkeypatch):
    async def fake_get_databases_by_user_id(_user_id: str):
        return {"databases": [{"db_id": "kb-1", "name": "后端知识库"}]}

    async def fake_get_database_info(_db_id: str):
        return {
            "db_id": "kb-1",
            "name": "后端知识库",
            "sample_questions": ["请解释索引失效的常见原因", "Redis 持久化方案对比"],
        }

    monkeypatch.setattr(service.knowledge_base, "get_databases_by_user_id", fake_get_databases_by_user_id)
    monkeypatch.setattr(service.knowledge_base, "get_database_info", fake_get_database_info)
    monkeypatch.setattr(
        service,
        "list_imported_problem_packages",
        lambda: {
            "problems": [
                {
                    "title": "二叉树层序遍历",
                    "summary": "考察队列、层次遍历和边界处理",
                    "topic_tags": ["算法", "边界"],
                    "primary_position_tag": "backend",
                    "difficulty_tag": "medium",
                    "package_path": "demo.xml",
                    "problem_index": 1,
                }
            ]
        },
    )

    conversation = SimpleNamespace(user_id="user-1", extra_metadata={"target_position": "后端工程师"})
    scorecard = {
        "role": "后端工程师",
        "round": "初试",
        "dimensions": [
            {"name": "技术能力", "score": 62},
            {"name": "问题解决", "score": 68},
            {"name": "沟通表达", "score": 82},
            {"name": "综合素质", "score": 79},
        ],
        "risks": ["技术基础回答不够扎实", "算法边界条件覆盖不足"],
        "suggestions": ["建议补强基础原理和题目拆解能力"],
    }
    coding_session = {
        "target_position": "后端工程师",
        "difficulty_level": "medium",
        "judge_status": "WRONG_ANSWER",
        "judge_result": {"score": 55},
    }
    expression_analysis = {
        "summary": "本轮语音回答表达较清晰，但结论先行不足。",
    }

    plan = asyncio.run(
        service._generate_improvement_plan(
            conversation=conversation,
            scorecard=scorecard,
            expression_analysis=expression_analysis,
            coding_session=coding_session,
        )
    )

    assert plan is not None
    assert len(plan["weaknesses"]) >= 2
    assert len(plan["recommended_resources"]) >= 2
    assert len(plan["practice_tasks"]) >= 2
    assert len(plan["next_assessment_focus"]) >= 2
    assert {item["resource_type"] for item in plan["recommended_resources"]} >= {"knowledge", "interview_question"}


def test_build_history_profile_aggregates_recent_completed_records():
    records = [
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 60},
                {"key": "problem_solving", "score": 70},
            ],
            "improvement_plan": {
                "practice_tasks": [{"title": "task-1"}],
                "next_assessment_focus": [{"dimension_key": "technical_competence", "title": "技术细节表达", "focus": "关注原理说明"}],
            },
        },
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 65},
                {"key": "problem_solving", "score": 85},
            ],
            "improvement_plan": {
                "practice_tasks": [{"title": "task-2"}, {"title": "task-3"}],
                "next_assessment_focus": [{"dimension_key": "problem_solving", "title": "解题思路完整度", "focus": "关注边界覆盖"}],
            },
        },
    ]

    profile = service._build_history_profile(records)

    assert profile["pending_practice_count"] == 1
    assert profile["latest_focus"][0]["dimension_key"] == "technical_competence"
    assert profile["top_weakness_dimensions"][0]["dimension_key"] == "technical_competence"
