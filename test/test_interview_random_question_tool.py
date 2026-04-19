from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.append(os.getcwd())

from src.agents.common.toolkits.kbs import tools as kb_tools
from src.agents.interview_agent.context import InterviewContext
from src.agents.interview_agent.graph import INTERVIEW_TODO_PROMPT, InterviewKnowledgeBaseMiddleware
from src.services.position_types import get_position_type


def test_extract_question_from_chunk_content_only_returns_question() -> None:
    chunk_content = "问题：什么是 React Hooks\t回答：它让函数组件拥有状态能力。"

    assert kb_tools._extract_question_from_chunk_content(chunk_content) == "什么是 React Hooks"


@pytest.mark.asyncio
async def test_collect_technical_question_candidates_merges_kbs_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_files = {
        "db_backend": {
            "file_backend": {"filename": "backend.md", "status": "indexed", "is_folder": False},
        },
        "db_algorithm": {
            "file_algorithm": {"filename": "algorithm.md", "status": "done", "is_folder": False},
        },
    }
    db_lines = {
        ("db_backend", "file_backend"): [
            {"id": "chunk-backend-1", "chunk_order_index": 1, "content": "问题：什么是 Redis\t回答：缓存数据库。"},
            {"id": "chunk-backend-2", "chunk_order_index": 2, "content": "问题：什么是 JVM\t回答：Java 虚拟机。"},
        ],
        ("db_algorithm", "file_algorithm"): [
            {"id": "chunk-algorithm-1", "chunk_order_index": 1, "content": "问题：什么是 JVM\t回答：另一份重复答案。"},
            {
                "id": "chunk-algorithm-2",
                "chunk_order_index": 2,
                "content": "问题：说一下动态规划。\t回答：一种算法设计方法。",
            },
        ],
    }

    fake_kb = SimpleNamespace(
        get_retrievers=lambda: {
            "db_backend": {"name": get_position_type("backend")["label"]},
            "db_algorithm": {"name": get_position_type("algorithm")["label"]},
        },
        get_database_info=lambda db_id: {"files": db_files[db_id]},
        get_file_content=lambda db_id, file_id: {"lines": db_lines[(db_id, file_id)]},
    )

    async def fake_get_database_info(db_id: str) -> dict:
        return fake_kb.get_database_info(db_id)

    async def fake_get_file_content(db_id: str, file_id: str) -> dict:
        return fake_kb.get_file_content(db_id, file_id)

    async def fake_get_databases() -> dict:
        return {
            "databases": [
                {"db_id": "db_backend", "name": get_position_type("backend")["label"]},
                {"db_id": "db_algorithm", "name": get_position_type("algorithm")["label"]},
            ]
        }

    monkeypatch.setattr(
        kb_tools,
        "knowledge_base",
        SimpleNamespace(
            get_databases=fake_get_databases,
            get_retrievers=fake_kb.get_retrievers,
            get_database_info=fake_get_database_info,
            get_file_content=fake_get_file_content,
        ),
    )

    candidates = await kb_tools._collect_technical_question_candidates(
        [get_position_type("backend")["label"], get_position_type("algorithm")["label"]]
    )

    assert [candidate["question"] for candidate in candidates] == [
        "什么是 Redis",
        "什么是 JVM",
        "说一下动态规划。",
    ]
    assert candidates[-1]["kb_name"] == get_position_type("algorithm")["label"]
    assert candidates[-1]["file_name"] == "algorithm.md"
    assert candidates[-1]["db_id"] == "db_algorithm"
    assert candidates[-1]["file_id"] == "file_algorithm"
    assert candidates[-1]["chunk_id"] == "chunk-algorithm-2"
    assert candidates[-1]["chunk_index"] == 2


@pytest.mark.asyncio
async def test_pick_random_technical_question_uses_random_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, object]]:
        return [
            {
                "question": "第一题",
                "kb_name": get_position_type("backend")["label"],
                "db_id": "db_backend",
                "file_id": "file_backend",
                "file_name": "a.md",
                "chunk_id": "chunk-1",
                "chunk_index": 1,
            },
            {
                "question": "第二题",
                "kb_name": get_position_type("algorithm")["label"],
                "db_id": "db_algorithm",
                "file_id": "file_algorithm",
                "file_name": "b.md",
                "chunk_id": "chunk-2",
                "chunk_index": 2,
            },
        ]

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)
    monkeypatch.setattr(kb_tools.random, "choice", lambda items: items[-1])

    result = await kb_tools._pick_random_technical_question(
        [get_position_type("backend")["label"], get_position_type("algorithm")["label"]]
    )

    assert result == {
        "question": "第二题",
        "kb_name": get_position_type("algorithm")["label"],
        "db_id": "db_algorithm",
        "file_id": "file_algorithm",
        "file_name": "b.md",
        "chunk_id": "chunk-2",
        "chunk_index": 2,
        "message": "success",
    }


@pytest.mark.asyncio
async def test_pick_random_technical_question_skips_excluded_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, object]]:
        return [
            {
                "question": "第一题",
                "kb_name": get_position_type("backend")["label"],
                "db_id": "db_backend",
                "file_id": "file_backend",
                "file_name": "a.md",
                "chunk_id": "chunk-1",
                "chunk_index": 1,
            },
            {
                "question": "第二题",
                "kb_name": get_position_type("algorithm")["label"],
                "db_id": "db_algorithm",
                "file_id": "file_algorithm",
                "file_name": "b.md",
                "chunk_id": "chunk-2",
                "chunk_index": 2,
            },
        ]

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)
    monkeypatch.setattr(kb_tools.random, "choice", lambda items: items[0])

    result = await kb_tools._pick_random_technical_question_with_excludes(
        [get_position_type("backend")["label"], get_position_type("algorithm")["label"]],
        ["第一题"],
    )

    assert result == {
        "question": "第二题",
        "kb_name": get_position_type("algorithm")["label"],
        "db_id": "db_algorithm",
        "file_id": "file_algorithm",
        "file_name": "b.md",
        "chunk_id": "chunk-2",
        "chunk_index": 2,
        "message": "success",
    }


@pytest.mark.asyncio
async def test_pick_random_technical_question_returns_empty_result_when_no_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)

    result = await kb_tools._pick_random_technical_question([get_position_type("frontend")["label"]])

    assert result["question"] == ""
    assert result["kb_name"] == ""
    assert result["db_id"] == ""
    assert result["file_id"] == ""
    assert result["file_name"] == ""
    assert result["chunk_id"] == ""
    assert result["chunk_index"] is None
    assert "没有可用的技术题目" in result["message"]


@pytest.mark.asyncio
async def test_pick_random_technical_question_returns_empty_result_when_all_are_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, object]]:
        return [
            {
                "question": "第一题",
                "kb_name": get_position_type("frontend")["label"],
                "db_id": "db_frontend",
                "file_id": "file_frontend",
                "file_name": "react.md",
                "chunk_id": "chunk-1",
                "chunk_index": 1,
            },
        ]

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)

    result = await kb_tools._pick_random_technical_question_with_excludes(
        [get_position_type("frontend")["label"]],
        ["第一题"],
    )

    assert result["question"] == ""
    assert result["kb_name"] == ""
    assert result["db_id"] == ""
    assert result["file_id"] == ""
    assert result["file_name"] == ""
    assert result["chunk_id"] == ""
    assert result["chunk_index"] is None
    assert "没有更多可用的技术题目" in result["message"]


def test_interview_prompt_and_todo_prompt_include_technical_question_stage() -> None:
    prompt = InterviewContext.build_runtime_system_prompt(
        None,
        target_position=get_position_type("backend")["label"],
        interview_round="初试",
    )

    assert InterviewContext.get_position_technical_kb_names(get_position_type("frontend")["label"]) == [
        get_position_type("frontend")["label"]
    ]
    assert InterviewContext.get_position_technical_kb_names(get_position_type("backend")["label"]) == [
        get_position_type("backend")["label"]
    ]
    assert "固定 6 个阶段" in prompt
    assert "相关技术知识提问" in prompt
    assert "pick_random_technical_question" in prompt
    assert "excluded_questions" in prompt
    assert "固定的 6 个 todo" in INTERVIEW_TODO_PROMPT
    assert "相关技术知识提问" in INTERVIEW_TODO_PROMPT
    assert "excluded_questions" in INTERVIEW_TODO_PROMPT


def test_interview_knowledge_base_middleware_registers_random_question_tool() -> None:
    middleware = InterviewKnowledgeBaseMiddleware()
    tool_names = {tool.name for tool in middleware.tools}

    assert tool_names == {"query_kb", "pick_random_technical_question", "start_code_assessment"}
