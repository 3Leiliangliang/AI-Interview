from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.append(os.getcwd())

from src.agents.common.toolkits.kbs import tools as kb_tools
from src.agents.interview_agent.context import InterviewContext
from src.agents.interview_agent.graph import INTERVIEW_TODO_PROMPT, InterviewKnowledgeBaseMiddleware


def test_extract_question_from_chunk_content_only_returns_question() -> None:
    chunk_content = "问题：什么是 React Hooks？\t回答：它让函数组件拥有状态能力。"

    assert kb_tools._extract_question_from_chunk_content(chunk_content) == "什么是 React Hooks？"


@pytest.mark.asyncio
async def test_collect_technical_question_candidates_merges_kbs_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_files = {
        "db_backend": {
            "file_backend": {"filename": "backend.md", "status": "indexed", "is_folder": False},
        },
        "db_java": {
            "file_java": {"filename": "java.md", "status": "done", "is_folder": False},
        },
    }
    db_lines = {
        ("db_backend", "file_backend"): [
            {"content": "问题：什么是 Redis？\t回答：缓存数据库。"},
            {"content": "问题：什么是 JVM？\t回答：Java 虚拟机。"},
        ],
        ("db_java", "file_java"): [
            {"content": "问题：什么是 JVM？\t回答：另一份重复答案。"},
            {"content": "问题：说一下 Java 内存模型？\t回答：JMM。"},
        ],
    }

    fake_kb = SimpleNamespace(
        get_retrievers=lambda: {
            "db_backend": {"name": "Waking-Up"},
            "db_java": {"name": "JavaGuide"},
        },
        get_database_info=lambda db_id: {"files": db_files[db_id]},
        get_file_content=lambda db_id, file_id: {"lines": db_lines[(db_id, file_id)]},
    )

    async def fake_get_database_info(db_id: str) -> dict:
        return fake_kb.get_database_info(db_id)

    async def fake_get_file_content(db_id: str, file_id: str) -> dict:
        return fake_kb.get_file_content(db_id, file_id)

    monkeypatch.setattr(
        kb_tools,
        "knowledge_base",
        SimpleNamespace(
            get_retrievers=fake_kb.get_retrievers,
            get_database_info=fake_get_database_info,
            get_file_content=fake_get_file_content,
        ),
    )

    candidates = await kb_tools._collect_technical_question_candidates(["Waking-Up", "JavaGuide"])

    assert [candidate["question"] for candidate in candidates] == [
        "什么是 Redis？",
        "什么是 JVM？",
        "说一下 Java 内存模型？",
    ]
    assert candidates[-1]["kb_name"] == "JavaGuide"
    assert candidates[-1]["file_name"] == "java.md"


@pytest.mark.asyncio
async def test_pick_random_technical_question_uses_random_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, str]]:
        return [
            {"question": "第一题", "kb_name": "Waking-Up", "file_name": "a.md"},
            {"question": "第二题", "kb_name": "JavaGuide", "file_name": "b.md"},
        ]

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)
    monkeypatch.setattr(kb_tools.random, "choice", lambda items: items[-1])

    result = await kb_tools._pick_random_technical_question(["Waking-Up", "JavaGuide"])

    assert result == {
        "question": "第二题",
        "kb_name": "JavaGuide",
        "file_name": "b.md",
        "message": "success",
    }


@pytest.mark.asyncio
async def test_pick_random_technical_question_skips_excluded_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, str]]:
        return [
            {"question": "第一题", "kb_name": "Waking-Up", "file_name": "a.md"},
            {"question": "第二题", "kb_name": "JavaGuide", "file_name": "b.md"},
        ]

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)
    monkeypatch.setattr(kb_tools.random, "choice", lambda items: items[0])

    result = await kb_tools._pick_random_technical_question_with_excludes(
        ["Waking-Up", "JavaGuide"],
        ["第一题"],
    )

    assert result == {
        "question": "第二题",
        "kb_name": "JavaGuide",
        "file_name": "b.md",
        "message": "success",
    }


@pytest.mark.asyncio
async def test_pick_random_technical_question_returns_empty_result_when_no_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)

    result = await kb_tools._pick_random_technical_question(["React Interview Questions"])

    assert result["question"] == ""
    assert result["kb_name"] == ""
    assert result["file_name"] == ""
    assert "没有可用的技术题目" in result["message"]


@pytest.mark.asyncio
async def test_pick_random_technical_question_returns_empty_result_when_all_are_excluded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(_: list[str]) -> list[dict[str, str]]:
        return [{"question": "第一题", "kb_name": "React Interview Questions", "file_name": "react.md"}]

    monkeypatch.setattr(kb_tools, "_collect_technical_question_candidates", fake_collect)

    result = await kb_tools._pick_random_technical_question_with_excludes(
        ["React Interview Questions"],
        ["第一题"],
    )

    assert result["question"] == ""
    assert result["kb_name"] == ""
    assert result["file_name"] == ""
    assert "没有更多可用的技术题目" in result["message"]


def test_interview_prompt_and_todo_prompt_include_technical_question_stage() -> None:
    prompt = InterviewContext.build_runtime_system_prompt(
        target_position="后端工程师",
        interview_round="初试",
    )

    assert InterviewContext.get_position_technical_kb_names("前端工程师") == ["React Interview Questions"]
    assert InterviewContext.get_position_technical_kb_names("后端工程师") == ["Waking-Up", "JavaGuide"]
    assert "固定 6 步任务清单" in prompt
    assert "相关技术知识提问" in prompt
    assert "pick_random_technical_question" in prompt
    assert "每次准备发出技术问题前" in prompt
    assert "excluded_questions" in prompt
    assert "固定的 6 步任务清单" in INTERVIEW_TODO_PROMPT
    assert "相关技术知识提问" in INTERVIEW_TODO_PROMPT
    assert "每次准备发出技术问题前" in INTERVIEW_TODO_PROMPT
    assert "excluded_questions" in INTERVIEW_TODO_PROMPT


def test_interview_knowledge_base_middleware_registers_random_question_tool() -> None:
    middleware = InterviewKnowledgeBaseMiddleware()
    tool_names = {tool.name for tool in middleware.tools}

    assert tool_names == {"query_kb", "pick_random_technical_question"}
