from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "tmp" / "ik"
CURATED_KNOWLEDGE_ROOT = ROOT / ".knowledge" / "interview_sources"
CURATED_MANIFEST_PATH = CURATED_KNOWLEDGE_ROOT / "source_manifest.json"


@dataclass(frozen=True)
class SourceSelection:
    source_path: str
    output_path: str
    recursive: bool = False


@dataclass(frozen=True)
class SourceRepository:
    key: str
    repo_url: str
    repo_web_url: str
    license_name: str
    selections: tuple[SourceSelection, ...]


def build_source_catalog() -> tuple[SourceRepository, ...]:
    return (
        SourceRepository(
            key="javaguide",
            repo_url="https://github.com/Snailclimb/JavaGuide.git",
            repo_web_url="https://github.com/Snailclimb/JavaGuide",
            license_name="Apache-2.0",
            selections=(
                SourceSelection(
                    "docs/interview-preparation",
                    "javaguide-backend/interview-preparation",
                    recursive=True,
                ),
                SourceSelection("docs/java", "javaguide-backend/java", recursive=True),
                SourceSelection("docs/database", "javaguide-backend/database", recursive=True),
                SourceSelection("docs/cs-basics", "javaguide-backend/cs-basics", recursive=True),
                SourceSelection("docs/distributed-system", "javaguide-backend/distributed-system", recursive=True),
                SourceSelection("docs/system-design", "javaguide-backend/system-design", recursive=True),
                SourceSelection("docs/high-availability", "javaguide-backend/high-availability", recursive=True),
                SourceSelection("docs/high-performance", "javaguide-backend/high-performance", recursive=True),
                SourceSelection("docs/ai/README.md", "javaguide-ai/README.md"),
                SourceSelection("docs/ai/agent", "javaguide-ai/agent", recursive=True),
                SourceSelection("docs/ai/llm-basis", "javaguide-ai/llm-basis", recursive=True),
                SourceSelection("docs/ai/rag", "javaguide-ai/rag", recursive=True),
                SourceSelection("docs/ai/ai-coding", "javaguide-ai/ai-coding", recursive=True),
            ),
        ),
        SourceRepository(
            key="reactjs-interview-questions",
            repo_url="https://github.com/sudheerj/reactjs-interview-questions.git",
            repo_web_url="https://github.com/sudheerj/reactjs-interview-questions",
            license_name="MIT",
            selections=(
                SourceSelection("README.md", "react-interview/react-interview-questions.md"),
                SourceSelection("coding-exercise/README.md", "react-interview/react-coding-exercise.md"),
            ),
        ),
        SourceRepository(
            key="front-end-interview-handbook",
            repo_url="https://github.com/yangshun/front-end-interview-handbook.git",
            repo_web_url="https://github.com/yangshun/front-end-interview-handbook",
            license_name="MIT",
            selections=(
                SourceSelection(
                    "packages/front-end-interview-guidebook/contents/javascript/zh-CN.mdx",
                    "frontend-handbook/frontend-guide/javascript.md",
                ),
                SourceSelection(
                    "packages/front-end-interview-guidebook/contents/coding/zh-CN.mdx",
                    "frontend-handbook/frontend-guide/coding.md",
                ),
                SourceSelection(
                    "packages/front-end-interview-guidebook/contents/system-design/zh-CN.mdx",
                    "frontend-handbook/frontend-guide/system-design.md",
                ),
                SourceSelection(
                    "packages/front-end-interview-guidebook/contents/user-interface-questions-cheatsheet/zh-CN.mdx",
                    "frontend-handbook/frontend-guide/ui-questions-cheatsheet.md",
                ),
                SourceSelection(
                    "packages/behavioral-interview-guidebook/contents/questions/zh-CN.mdx",
                    "frontend-handbook/behavioral/questions.md",
                ),
                SourceSelection(
                    "packages/behavioral-interview-guidebook/contents/self-introduction/zh-CN.mdx",
                    "frontend-handbook/behavioral/self-introduction.md",
                ),
                SourceSelection(
                    "packages/behavioral-interview-guidebook/contents/why-work-here/zh-CN.mdx",
                    "frontend-handbook/behavioral/why-work-here.md",
                ),
                SourceSelection(
                    "packages/react-interview-playbook/contents/react-interview-preparation/zh-CN.mdx",
                    "frontend-handbook/react-playbook/react-interview-preparation.md",
                ),
                SourceSelection(
                    "packages/react-interview-playbook/contents/react-basic-concepts/zh-CN.mdx",
                    "frontend-handbook/react-playbook/react-basic-concepts.md",
                ),
                SourceSelection(
                    "packages/react-interview-playbook/contents/react-hooks/zh-CN.mdx",
                    "frontend-handbook/react-playbook/react-hooks.md",
                ),
                SourceSelection(
                    "packages/react-interview-playbook/contents/react-state-design/zh-CN.mdx",
                    "frontend-handbook/react-playbook/react-state-design.md",
                ),
            ),
        ),
        SourceRepository(
            key="tech-interview-handbook",
            repo_url="https://github.com/yangshun/tech-interview-handbook.git",
            repo_web_url="https://github.com/yangshun/tech-interview-handbook",
            license_name="MIT",
            selections=(
                SourceSelection(
                    "apps/website/contents/behavioral-interview.md",
                    "tech-interview-handbook/behavioral/behavioral-interview-preparation.md",
                ),
                SourceSelection(
                    "apps/website/contents/behavioral-interview-questions.md",
                    "tech-interview-handbook/behavioral/common-behavioral-questions.md",
                ),
                SourceSelection(
                    "apps/website/contents/behavioral-interview-rubrics.md",
                    "tech-interview-handbook/behavioral/behavioral-interview-rubrics.md",
                ),
                SourceSelection(
                    "apps/website/contents/self-introduction.md",
                    "tech-interview-handbook/behavioral/self-introduction.md",
                ),
                SourceSelection(
                    "apps/website/contents/final-questions.md",
                    "tech-interview-handbook/behavioral/final-questions.md",
                ),
                SourceSelection(
                    "apps/website/contents/coding-interview-prep.md",
                    "tech-interview-handbook/coding/coding-interview-prep.md",
                ),
                SourceSelection(
                    "apps/website/contents/coding-interview-cheatsheet.md",
                    "tech-interview-handbook/coding/coding-interview-cheatsheet.md",
                ),
                SourceSelection(
                    "apps/website/contents/coding-interview-rubrics.md",
                    "tech-interview-handbook/coding/coding-interview-rubrics.md",
                ),
                SourceSelection(
                    "apps/website/contents/coding-interview-study-plan.md",
                    "tech-interview-handbook/coding/coding-interview-study-plan.md",
                ),
                SourceSelection(
                    "apps/website/contents/coding-interview-techniques.md",
                    "tech-interview-handbook/coding/coding-interview-techniques.md",
                ),
                SourceSelection(
                    "apps/website/contents/resume.md",
                    "tech-interview-handbook/general/resume.md",
                ),
                SourceSelection(
                    "apps/website/contents/software-engineering-interview-guide.md",
                    "tech-interview-handbook/general/software-engineering-interview-guide.md",
                ),
                SourceSelection(
                    "apps/website/contents/interview-formats-top-companies.md",
                    "tech-interview-handbook/general/interview-formats-top-companies.md",
                ),
                SourceSelection(
                    "apps/website/contents/system-design.md",
                    "tech-interview-handbook/general/system-design-preparation-guide.md",
                ),
            ),
        ),
        SourceRepository(
            key="system-design-primer",
            repo_url="https://github.com/donnemartin/system-design-primer.git",
            repo_web_url="https://github.com/donnemartin/system-design-primer",
            license_name="CC-BY-4.0",
            selections=(
                SourceSelection("README-zh-Hans.md", "system-design-primer/overview/system-design-primer.md"),
                SourceSelection(
                    "solutions/system_design/twitter/README-zh-Hans.md",
                    "system-design-primer/cases/twitter.md",
                ),
                SourceSelection(
                    "solutions/system_design/web_crawler/README-zh-Hans.md",
                    "system-design-primer/cases/web-crawler.md",
                ),
                SourceSelection(
                    "solutions/system_design/pastebin/README-zh-Hans.md",
                    "system-design-primer/cases/pastebin.md",
                ),
                SourceSelection(
                    "solutions/system_design/mint/README-zh-Hans.md",
                    "system-design-primer/cases/mint.md",
                ),
                SourceSelection(
                    "solutions/system_design/social_graph/README-zh-Hans.md",
                    "system-design-primer/cases/social-graph.md",
                ),
                SourceSelection(
                    "solutions/system_design/scaling_aws/README-zh-Hans.md",
                    "system-design-primer/cases/scaling-aws.md",
                ),
                SourceSelection(
                    "solutions/system_design/sales_rank/README-zh-Hans.md",
                    "system-design-primer/cases/sales-rank.md",
                ),
                SourceSelection(
                    "solutions/system_design/query_cache/README-zh-Hans.md",
                    "system-design-primer/cases/query-cache.md",
                ),
            ),
        ),
        SourceRepository(
            key="dsa-handbook",
            repo_url="https://github.com/TharunKumarReddyPolu/DSA-Handbook-for-Coding-Interviews.git",
            repo_web_url="https://github.com/TharunKumarReddyPolu/DSA-Handbook-for-Coding-Interviews",
            license_name="MIT",
            selections=(
                SourceSelection("README.md", "dsa-handbook/README.md"),
                SourceSelection("Topics", "dsa-handbook/topics", recursive=True),
            ),
        ),
        SourceRepository(
            key="nodejs-interview-questions",
            repo_url="https://github.com/aswanth6000/nodejs-interview-questions.git",
            repo_web_url="https://github.com/aswanth6000/nodejs-interview-questions",
            license_name="MIT",
            selections=(
                SourceSelection("README.md", "nodejs-interview/nodejs-interview-questions.md"),
                SourceSelection("nodejs-advanced.md", "nodejs-interview/nodejs-advanced-questions.md"),
            ),
        ),
        SourceRepository(
            key="cracking-the-sql-interview",
            repo_url="https://github.com/xoraus/CrackingTheSQLInterview.git",
            repo_web_url="https://github.com/xoraus/CrackingTheSQLInterview",
            license_name="MIT",
            selections=(SourceSelection("README.md", "sql-interview/sql-interview-guide.md"),),
        ),
    )


def split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized

    end_marker = normalized.find("\n---\n", 4)
    if end_marker == -1:
        return {}, normalized

    frontmatter_block = normalized[4:end_marker]
    body = normalized[end_marker + len("\n---\n") :]
    metadata: dict[str, str] = {}
    for raw_line in frontmatter_block.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, body


_HTML_IMG_PATTERN = re.compile(
    r"<img\b([^>]*?)/?>",
    re.IGNORECASE,
)
_HTML_IMG_ATTR_PATTERN = re.compile(
    r"""(?P<name>\w[\w-]*)\s*=\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>\S+))""",
)
_MD_IMAGE_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")


def _github_repo_slug(repo_url: str) -> str | None:
    """Extract 'owner/repo' from a GitHub URL like https://github.com/owner/repo."""
    match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo_url.strip())
    return match.group(1) if match else None


def _collapse_relative_path(base_dir: str, rel: str) -> str:
    """Resolve `rel` against `base_dir` collapsing '..' / '.' without leaving the repo root."""
    base_parts = [p for p in base_dir.split("/") if p and p != "."]
    rel = rel.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    parts = base_parts + [p for p in rel.split("/") if p]
    resolved: list[str] = []
    for part in parts:
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        if part in ("", "."):
            continue
        resolved.append(part)
    return "/".join(resolved)


def _is_absolute_url(url: str) -> bool:
    return bool(re.match(r"^(?:[a-z][a-z0-9+\-.]*:)?//", url, re.IGNORECASE)) or url.startswith("data:")


def _rewrite_image_url(src: str, *, repo_slug: str, commit: str, source_dir: str) -> str:
    """Turn a relative image src into a github raw URL, preserving absolute URLs."""
    src = src.strip()
    if not src or _is_absolute_url(src):
        return src
    if src.startswith("/"):
        # Repo-root-absolute path (`/images/x.png`).
        absolute = src.lstrip("/")
    else:
        absolute = _collapse_relative_path(source_dir, src)
    return f"https://raw.githubusercontent.com/{repo_slug}/{commit}/{absolute}"


def _convert_html_img_tag(match: re.Match, *, repo_slug: str | None, commit: str, source_dir: str) -> str:
    """Convert a single `<img \u2026>` HTML tag into Markdown syntax."""
    attrs = {}
    for attr in _HTML_IMG_ATTR_PATTERN.finditer(match.group(1)):
        value = attr.group("dq") if attr.group("dq") is not None else (
            attr.group("sq") if attr.group("sq") is not None else attr.group("bare") or ""
        )
        attrs[attr.group("name").lower()] = value
    src = attrs.get("src", "").strip()
    if not src:
        return ""
    alt = attrs.get("alt", "").strip() or attrs.get("title", "").strip()
    if repo_slug and not _is_absolute_url(src):
        src = _rewrite_image_url(src, repo_slug=repo_slug, commit=commit, source_dir=source_dir)
    return f"![{alt}]({src})"


def _rewrite_images(text: str, *, repo_slug: str | None, commit: str, source_dir: str) -> str:
    """Rewrite both `<img \u2026>` HTML and Markdown `![](rel/path)` to raw URLs."""
    if repo_slug:
        text = _HTML_IMG_PATTERN.sub(
            lambda m: _convert_html_img_tag(m, repo_slug=repo_slug, commit=commit, source_dir=source_dir),
            text,
        )

        def _md_rewriter(match: re.Match) -> str:
            src = match.group("src").strip()
            # Markdown links may contain a title:  ![alt](url "title")
            url_only = src.split(" ", 1)[0]
            title = src[len(url_only):].strip()
            if _is_absolute_url(url_only):
                return match.group(0)
            new_url = _rewrite_image_url(url_only, repo_slug=repo_slug, commit=commit, source_dir=source_dir)
            inner = new_url if not title else f"{new_url} {title}"
            return f"![{match.group('alt')}]({inner})"

        text = _MD_IMAGE_PATTERN.sub(_md_rewriter, text)
    return text


def normalize_source_text(
    content: str,
    *,
    repo_name: str,
    repo_url: str,
    source_path: str,
    license_name: str,
    commit: str,
) -> str:
    metadata, body = split_frontmatter(content.lstrip("\ufeff"))

    repo_slug = _github_repo_slug(repo_url)
    source_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
    # Pre-process images BEFORE the cleaning loop strips raw <img> tags.
    body = _rewrite_images(body, repo_slug=repo_slug, commit=commit, source_dir=source_dir)

    if repo_name in {"reactjs-interview-questions", "nodejs-interview-questions"} and source_path == "README.md":
        marker = "### Table of Contents"
        marker_index = body.find(marker)
        if marker_index != -1:
            body = body[marker_index:]
    elif repo_name == "system-design-primer" and source_path == "README-zh-Hans.md":
        marker = "# 系统设计入门"
        marker_index = body.find(marker)
        if marker_index != -1:
            body = body[marker_index:]
    elif repo_name == "dsa-handbook" and source_path == "README.md":
        marker = "## 🎯 About This Handbook"
        marker_index = body.find(marker)
        if marker_index != -1:
            body = body[marker_index:]

    cleaned_lines: list[str] = []
    skip_head_block = False
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("<head"):
            skip_head_block = True
            continue
        if skip_head_block:
            if stripped.startswith("</head>"):
                skip_head_block = False
            continue
        if stripped.startswith(("import ", "export ")):
            continue
        if stripped.startswith(":::"):
            continue
        if stripped.startswith("<!-- @include:"):
            continue
        if "Back to Top" in raw_line:
            continue
        if stripped.startswith(("<InDocAd", "<QuestionList")):
            continue
        if stripped.startswith(("<meta", "<div", "</div>", "<figure", "</figure>", "<figcaption", "</figcaption>")):
            continue
        if stripped.startswith(("<img", "<p ", "</p>", "<br", "</br>")):
            continue
        if "className=" in stripped or "src={require(" in stripped:
            continue
        if stripped.startswith(("title=", "alt=", "content=")):
            continue
        cleaned_lines.append(raw_line.rstrip())

    cleaned = "\n".join(cleaned_lines).strip()
    title = metadata.get("title")
    if title and not cleaned.startswith("# "):
        cleaned = f"# {title}\n\n{cleaned}" if cleaned else f"# {title}"

    header = "\n".join(
        [
            "<!--",
            f"source_repo: {repo_url}",
            f"source_path: {source_path}",
            f"license: {license_name}",
            f"commit: {commit}",
            "-->",
        ]
    )

    if cleaned:
        return f"{header}\n\n{cleaned}\n"
    return f"{header}\n"


def ensure_interview_knowledge_sources(force: bool = False) -> dict[str, object]:
    catalog = build_source_catalog()
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    if CURATED_KNOWLEDGE_ROOT.exists():
        shutil.rmtree(CURATED_KNOWLEDGE_ROOT)
    CURATED_KNOWLEDGE_ROOT.mkdir(parents=True, exist_ok=True)

    manifest_repos: list[dict[str, object]] = []
    reserved_output_paths: dict[str, Path] = {}
    for repo in catalog:
        repo_dir, git_ref = _ensure_repo(repo, force=force)
        commit = _run_git(repo_dir, "rev-parse", git_ref).strip()
        synced_files = _materialize_repo(repo, repo_dir, git_ref, commit, reserved_output_paths)
        manifest_repos.append(
            {
                "key": repo.key,
                "repo_url": repo.repo_web_url,
                "license": repo.license_name,
                "commit": commit,
                "file_count": len(synced_files),
                "files": synced_files,
            }
        )

    manifest: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(CURATED_KNOWLEDGE_ROOT),
        "repositories": manifest_repos,
    }
    CURATED_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _ensure_repo(repo: SourceRepository, *, force: bool) -> tuple[Path, str]:
    repo_dir = CACHE_ROOT / repo.key
    if force and repo_dir.exists():
        _remove_tree(repo_dir)

    if not repo_dir.exists():
        _run_git(
            None,
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--no-checkout",
            repo.repo_url,
            str(repo_dir),
        )
        return repo_dir, "HEAD"

    _run_git(repo_dir, "fetch", "--depth", "1", "origin")
    return repo_dir, "FETCH_HEAD"


def _materialize_repo(
    repo: SourceRepository,
    repo_dir: Path,
    git_ref: str,
    commit: str,
    reserved_output_paths: dict[str, Path],
) -> list[str]:
    synced_files: list[str] = []
    for selection in repo.selections:
        source_paths = _resolve_source_paths(repo_dir, git_ref, selection)
        for source_path in source_paths:
            output_path = _resolve_output_path(selection, source_path)
            output_path = _dedupe_output_path(output_path, reserved_output_paths)
            try:
                raw_content = _run_git(repo_dir, "show", f"{git_ref}:{source_path}")
            except subprocess.CalledProcessError:
                print(f"[knowledge-sync] skip missing source in {repo.key}: {source_path}")
                continue
            normalized = normalize_source_text(
                raw_content,
                repo_name=repo.key,
                repo_url=repo.repo_web_url,
                source_path=source_path,
                license_name=repo.license_name,
                commit=commit,
            )
            target_path = CURATED_KNOWLEDGE_ROOT / output_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(normalized, encoding="utf-8")
            synced_files.append(output_path.as_posix())
    return synced_files


def _resolve_source_paths(repo_dir: Path, git_ref: str, selection: SourceSelection) -> list[str]:
    if not selection.recursive:
        if _git_path_exists(repo_dir, git_ref, selection.source_path):
            return [selection.source_path]
        print(f"[knowledge-sync] skip missing selection: {selection.source_path}")
        return []

    output = _run_git(repo_dir, "ls-tree", "-r", "--name-only", git_ref, selection.source_path)
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip() and Path(line.strip()).suffix.lower() in {".md", ".mdx"}
    ]


def _resolve_output_path(selection: SourceSelection, source_path: str) -> Path:
    if not selection.recursive:
        return Path(selection.output_path)

    source_root = Path(selection.source_path)
    source_item = Path(source_path)
    relative_path = source_item.relative_to(source_root)
    output_root = Path(selection.output_path)
    if relative_path.suffix.lower() == ".mdx":
        relative_path = relative_path.with_suffix(".md")
    return output_root / relative_path


def _git_path_exists(repo_dir: Path, git_ref: str, source_path: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{git_ref}:{source_path}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0


def _dedupe_output_path(output_path: Path, reserved_output_paths: dict[str, Path]) -> Path:
    lookup_key = output_path.as_posix().lower()
    existing = reserved_output_paths.get(lookup_key)
    if existing is None:
        reserved_output_paths[lookup_key] = output_path
        return output_path

    if existing.as_posix() == output_path.as_posix():
        return output_path

    candidate_index = 2
    while True:
        candidate = output_path.with_name(f"{output_path.stem}__case_variant_{candidate_index}{output_path.suffix}")
        candidate_key = candidate.as_posix().lower()
        if candidate_key not in reserved_output_paths:
            reserved_output_paths[candidate_key] = candidate
            return candidate
        candidate_index += 1


def _run_git(repo_dir: Path | None, *args: str) -> str:
    command = ["git", *args]
    completed = subprocess.run(
        command,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completed.stdout


def _remove_tree(path: Path) -> None:
    def on_error(func, failing_path, exc_info):  # type: ignore[no-untyped-def]
        try:
            os.chmod(failing_path, 0o700)
            func(failing_path)
        except OSError:
            return

    shutil.rmtree(path, onerror=on_error)
