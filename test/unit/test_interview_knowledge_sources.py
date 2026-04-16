from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())

from scripts import import_interview_knowledge  # noqa: E402
from scripts.interview_knowledge_sources import (  # noqa: E402
    _dedupe_output_path,
    build_source_catalog,
    normalize_source_text,
    split_frontmatter,
)
from src.services import position_types as position_service  # noqa: E402


def test_split_frontmatter_extracts_title() -> None:
    content = """---
title: React Hooks 面试
description: 示例
---

正文内容
"""

    metadata, body = split_frontmatter(content)

    assert metadata["title"] == "React Hooks 面试"
    assert body.strip() == "正文内容"


def test_normalize_source_text_strips_frontmatter_imports_and_containers() -> None:
    content = """---
title: React Hooks 面试
---
import Demo from './demo'

::: tip
这里是提示
:::

正文内容
"""

    normalized = normalize_source_text(
        content,
        repo_name="front-end-interview-handbook",
        repo_url="https://github.com/yangshun/front-end-interview-handbook",
        source_path="packages/react-interview-playbook/contents/react-hooks/zh-CN.mdx",
        license_name="MIT",
        commit="abcdef1234567890",
    )

    assert "import Demo" not in normalized
    assert "::: tip" not in normalized
    assert "# React Hooks 面试" in normalized
    assert "这里是提示" in normalized
    assert "正文内容" in normalized


def test_normalize_source_text_trims_react_readme_noise() -> None:
    content = """# React Interview Questions & Answers

广告内容

### Table of Contents

## Core React

### What is React?

React is a library.
"""

    normalized = normalize_source_text(
        content,
        repo_name="reactjs-interview-questions",
        repo_url="https://github.com/sudheerj/reactjs-interview-questions",
        source_path="README.md",
        license_name="MIT",
        commit="abcdef1234567890",
    )

    assert "广告内容" not in normalized
    assert "### Table of Contents" in normalized
    assert "### What is React?" in normalized


def test_normalize_source_text_rewrites_relative_markdown_images_to_raw_urls() -> None:
    content = """# Example

![Architecture](./images/arch.png)
"""

    normalized = normalize_source_text(
        content,
        repo_name="javaguide",
        repo_url="https://github.com/Snailclimb/JavaGuide",
        source_path="docs/system-design/example.md",
        license_name="Apache-2.0",
        commit="abcdef1234567890",
    )

    assert "![Architecture](https://raw.githubusercontent.com/Snailclimb/JavaGuide/abcdef1234567890/docs/system-design/images/arch.png)" in normalized


def test_normalize_source_text_converts_html_images_to_markdown_with_absolute_urls() -> None:
    content = """# Example

<p align="center">
  <img src="../assets/demo.png" alt="demo image" />
</p>
"""

    normalized = normalize_source_text(
        content,
        repo_name="front-end-interview-handbook",
        repo_url="https://github.com/yangshun/front-end-interview-handbook",
        source_path="packages/react-interview-playbook/contents/react-hooks/zh-CN.mdx",
        license_name="MIT",
        commit="abcdef1234567890",
    )

    assert "![demo image](https://raw.githubusercontent.com/yangshun/front-end-interview-handbook/abcdef1234567890/packages/react-interview-playbook/contents/react-hooks/../assets/demo.png)" not in normalized
    assert "![demo image](https://raw.githubusercontent.com/yangshun/front-end-interview-handbook/abcdef1234567890/packages/react-interview-playbook/contents/assets/demo.png)" in normalized


def test_normalize_source_text_trims_nodejs_readme_noise() -> None:
    content = """# Nodejs Interview Questions and Answers

推广内容

### Table of Contents

## What is Node.js?

Node.js is a runtime.
"""

    normalized = normalize_source_text(
        content,
        repo_name="nodejs-interview-questions",
        repo_url="https://github.com/aswanth6000/nodejs-interview-questions",
        source_path="README.md",
        license_name="MIT",
        commit="abcdef1234567890",
    )

    assert "推广内容" not in normalized
    assert "### Table of Contents" in normalized
    assert "## What is Node.js?" in normalized


def test_normalize_source_text_strips_mdx_head_and_jsx_noise() -> None:
    content = """---
title: Behavioral Interviews
---
<head>
  <meta property="og:image" content="https://example.com/social.png" />
</head>

import InDocAd from './_components/InDocAd';

<div className="text--center margin-vert--lg">
  <figure>
    <img alt="summary"
    title="summary" className="shadow--md" src={require('@site/static/img/example.png').default} />
    <figcaption>summary</figcaption>
  </figure>
</div>

<InDocAd />

Real interview content.
"""

    normalized = normalize_source_text(
        content,
        repo_name="tech-interview-handbook",
        repo_url="https://github.com/yangshun/tech-interview-handbook",
        source_path="apps/website/contents/behavioral-interview.md",
        license_name="MIT",
        commit="abcdef1234567890",
    )

    assert "<head>" not in normalized
    assert "og:image" not in normalized
    assert "className=" not in normalized
    assert "InDocAd" not in normalized
    assert "Real interview content." in normalized


def test_build_source_catalog_contains_expected_repositories() -> None:
    catalog = build_source_catalog()

    repo_keys = {repo.key for repo in catalog}

    assert repo_keys == {
        "cracking-the-sql-interview",
        "dsa-handbook",
        "front-end-interview-handbook",
        "javaguide",
        "nodejs-interview-questions",
        "reactjs-interview-questions",
        "system-design-primer",
        "tech-interview-handbook",
    }
    assert any(selection.recursive for repo in catalog if repo.key == "javaguide" for selection in repo.selections)
    assert all(
        selection.output_path.endswith(".md") or selection.recursive
        for repo in catalog
        for selection in repo.selections
    )


def test_dedupe_output_path_handles_case_only_conflicts() -> None:
    reserved: dict[str, Path] = {}

    first = _dedupe_output_path(Path("frontend/Async.md"), reserved)
    second = _dedupe_output_path(Path("frontend/async.md"), reserved)

    assert first.as_posix() == "frontend/Async.md"
    assert second.as_posix() == "frontend/async__case_variant_2.md"


def test_build_import_plan_reads_curated_root(monkeypatch, tmp_path: Path) -> None:
    curated_root = tmp_path / "interview_sources"

    def write_md(relative_path: str) -> None:
        path = curated_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# sample\n", encoding="utf-8")

    for relative_path in (
        "javaguide-backend/interview-preparation/a.md",
        "javaguide-backend/java/a.md",
        "javaguide-backend/database/a.md",
        "javaguide-backend/cs-basics/a.md",
        "javaguide-backend/distributed-system/a.md",
        "javaguide-backend/system-design/a.md",
        "javaguide-backend/high-availability/a.md",
        "javaguide-backend/high-performance/a.md",
        "javaguide-ai/README.md",
        "javaguide-ai/llm-basis/a.md",
        "javaguide-ai/rag/a.md",
        "javaguide-ai/agent/a.md",
        "javaguide-ai/ai-coding/a.md",
        "react-interview/react-interview-questions.md",
        "react-interview/react-coding-exercise.md",
        "frontend-handbook/frontend-guide/a.md",
        "frontend-handbook/behavioral/a.md",
        "frontend-handbook/react-playbook/a.md",
        "tech-interview-handbook/behavioral/a.md",
        "tech-interview-handbook/coding/a.md",
        "tech-interview-handbook/general/a.md",
        "system-design-primer/overview/system-design-primer.md",
        "system-design-primer/cases/twitter.md",
        "dsa-handbook/README.md",
        "dsa-handbook/topics/a.md",
        "nodejs-interview/nodejs-interview-questions.md",
        "nodejs-interview/nodejs-advanced-questions.md",
        "sql-interview/sql-interview-guide.md",
    ):
        write_md(relative_path)

    monkeypatch.setattr(import_interview_knowledge, "CURATED_KNOWLEDGE_ROOT", curated_root)

    plans = import_interview_knowledge.build_import_plan()
    plan_counts = [len(plan.documents) for plan in plans]
    plan_positions = [plan.position for plan in plans]
    plan_names = [plan.name for plan in plans]
    plan_batches = {plan.name: {document.chunk_preset_id for document in plan.documents} for plan in plans}
    backend_plan = next(plan for plan in plans if plan.name == position_service.get_position_type("backend")["label"])
    system_plan = next(
        plan for plan in plans if plan.name == position_service.get_position_type("system_design")["label"]
    )
    frontend_plan = next(plan for plan in plans if plan.name == position_service.get_position_type("frontend")["label"])
    ai_plan = next(plan for plan in plans if plan.name == position_service.get_position_type("ai_app")["label"])

    assert len(plans) == 5
    assert plan_names == [
        position_service.get_position_type("frontend")["label"],
        position_service.get_position_type("backend")["label"],
        position_service.get_position_type("algorithm")["label"],
        position_service.get_position_type("system_design")["label"],
        position_service.get_position_type("ai_app")["label"],
    ]
    assert plan_counts == [8, 14, 6, 6, 8]
    assert plan_positions == [
        position_service.get_position_type("frontend")["label"],
        position_service.get_position_type("backend")["label"],
        position_service.get_position_type("algorithm")["label"],
        position_service.get_position_type("system_design")["label"],
        position_service.get_position_type("ai_app")["label"],
    ]
    assert plan_batches[position_service.get_position_type("frontend")["label"]] == {"qa"}
    assert plan_batches[position_service.get_position_type("backend")["label"]] == {"qa"}
    assert any(
        document.source_path == curated_root / "javaguide-backend" / "system-design" / "a.md"
        and document.topic_name == "系统设计"
        for document in backend_plan.documents
    )
    assert any(
        document.source_path == curated_root / "javaguide-backend" / "system-design" / "a.md"
        and document.topic_name == "系统设计"
        for document in system_plan.documents
    )
    assert {document.topic_name for document in frontend_plan.documents} == {"React", "前端基础", "行为面试", "编程面试", "通用基础"}
    assert {"AI 总览", "LLM基础", "RAG", "Agent", "AI Coding"} <= {
        document.topic_name for document in ai_plan.documents
    }
    backend_topics = {document.topic_name for document in backend_plan.documents}
    assert {"面试准备", "Java", "数据库", "计算机基础", "分布式", "系统设计", "高可用", "高性能", "Node.js"} <= backend_topics
    assert len({(document.topic_name, document.target_filename) for document in backend_plan.documents}) == len(
        backend_plan.documents
    )


def test_build_index_params_includes_position() -> None:
    params = import_interview_knowledge.build_index_params(
        "qa",
        position_service.get_position_type("backend")["label"],
    )

    assert params["chunk_preset_id"] == "qa"
    assert params["position"] == position_service.get_position_type("backend")["label"]
    assert params["qa_separator"] == import_interview_knowledge.QA_SEPARATOR


def test_build_flattened_target_filename_is_unique_and_readable() -> None:
    curated_root = Path("/tmp/interview_sources")
    source_path = curated_root / "javaguide-backend" / "system-design" / "basis" / "a.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("# 系统设计基础\n\ncontent\n", encoding="utf-8")

    target_filename = import_interview_knowledge.build_target_filename(source_path, curated_root)

    assert target_filename == "系统设计基础.md"


def test_build_target_filename_deduplicates_duplicate_titles() -> None:
    curated_root = Path("/tmp/interview_sources")
    first_path = curated_root / "repo-a" / "first.md"
    second_path = curated_root / "repo-b" / "second.md"
    first_path.parent.mkdir(parents=True, exist_ok=True)
    second_path.parent.mkdir(parents=True, exist_ok=True)
    first_path.write_text("# 重复标题\n\nA\n", encoding="utf-8")
    second_path.write_text("# 重复标题\n\nB\n", encoding="utf-8")

    used_filenames: set[str] = set()
    first_name = import_interview_knowledge.build_target_filename(
        first_path,
        curated_root,
        used_filenames=used_filenames,
    )
    second_name = import_interview_knowledge.build_target_filename(
        second_path,
        curated_root,
        used_filenames=used_filenames,
    )

    assert first_name == "重复标题.md"
    assert second_name == "重复标题__2.md"


def test_get_legacy_package_database_names_returns_old_seed_names() -> None:
    assert import_interview_knowledge.get_legacy_package_database_names() == [
        "JavaGuide 后端面试",
        "AI 应用开发面试",
        "React 面试题库",
        "前端面试手册",
        "通用技术面试手册",
        "系统设计面试题库",
        "DSA 面试手册",
        "Node.js 面试题库",
        "SQL 面试题库",
    ]
def test_get_managed_interview_database_names_includes_legacy_and_position_names() -> None:
    names = import_interview_knowledge.get_managed_interview_database_names()

    assert import_interview_knowledge.get_legacy_package_database_names()[0] in names
    assert position_service.get_position_type("frontend")["label"] in names
    assert position_service.get_position_type("backend")["label"] in names
    assert position_service.get_position_type("algorithm")["label"] in names
    assert position_service.get_position_type("system_design")["label"] in names
    assert position_service.get_position_type("ai_app")["label"] in names
