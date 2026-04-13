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
    plan_counts = [len(plan.root_files) + sum(len(folder.files) for folder in plan.folders) for plan in plans]

    assert len(plans) == 9
    assert plan_counts == [8, 5, 2, 3, 3, 2, 2, 2, 1]
