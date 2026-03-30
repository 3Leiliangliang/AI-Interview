from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

REPO_URL = "https://github.com/zhblue/freeproblemset.git"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DEFAULT_REPO_DIR = PROJECT_ROOT / ".codex_tmp" / "freeproblemset"
MANIFEST_PATH = PROJECT_ROOT / "saves" / "oj" / "freeproblemset_manifest.json"
OJ_BASE_URL = os.getenv("OJ_ADMIN_BASE_URL", "http://localhost:8088").rstrip("/")
OJ_USERNAME = os.getenv("OJ_USERNAME", "root")
OJ_PASSWORD = os.getenv("OJ_PASSWORD", "rootroot")
IMPORT_UPLOAD_TIMEOUT = int(os.getenv("FREEPROBLEMSET_IMPORT_TIMEOUT", "600"))
IMPORT_CHUNK_SIZE = max(int(os.getenv("FREEPROBLEMSET_IMPORT_CHUNK_SIZE", "200")), 1)
SUPPORTED_FRONTEND_LANGUAGES = ["javascript", "c", "cpp", "java", "python"]
SUPPORTED_OJ_LANGUAGES = ["JavaScript", "C", "C++", "Java", "Python3"]
POSITION_TAGS = ["frontend", "backend", "algorithm_general"]
DIFFICULTY_TAGS = ["easy", "medium", "hard"]
TOPIC_TAGS = [
    "array",
    "string",
    "hash_table",
    "stack",
    "queue",
    "linked_list",
    "tree",
    "graph",
    "dynamic_programming",
    "greedy",
    "binary_search",
    "sorting",
    "math",
    "simulation",
    "sql",
    "database",
    "frontend_dom",
    "frontend_async",
    "backend_api",
    "backend_concurrency",
]
DEFAULT_CLASSIFIER = os.getenv("FREEPROBLEMSET_CLASSIFIER", "rule").strip().lower() or "rule"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_repo_exists(repo_dir: Path) -> None:
    if not repo_dir.exists() or not (repo_dir / ".git").exists():
        raise RuntimeError(f"freeproblemset mirror not found: {repo_dir}. Please run sync first.")


def run_git(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=str(cwd) if cwd else None, check=True)


def sync_repository(repo_dir: Path) -> None:
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").exists():
        try:
            run_git(["git", "-C", str(repo_dir), "rev-parse", "--is-inside-work-tree"])
            run_git(["git", "-c", "http.version=HTTP/1.1", "-C", str(repo_dir), "pull", "--ff-only"])
            print(f"Updated freeproblemset mirror: {repo_dir}")
            return
        except subprocess.CalledProcessError:
            shutil.rmtree(repo_dir)
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    clone_commands = [
        ["git", "-c", "http.version=HTTP/1.1", "clone", "--depth", "1", REPO_URL, str(repo_dir)],
        ["git", "clone", "--depth", "1", REPO_URL, str(repo_dir)],
    ]
    last_error: subprocess.CalledProcessError | None = None
    for command in clone_commands:
        try:
            run_git(command)
            print(f"Cloned freeproblemset mirror: {repo_dir}")
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
    raise last_error or RuntimeError(f"Failed to clone repository: {REPO_URL}")


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"repo_path": str(DEFAULT_REPO_DIR), "updated_at": "", "packages": [], "problems": []}
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"repo_path": str(DEFAULT_REPO_DIR), "updated_at": "", "packages": [], "problems": payload}
    payload.setdefault("packages", [])
    payload.setdefault("problems", [])
    return payload


def save_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_package_path(package_path: str) -> str:
    return str(package_path).replace("\\", "/").lstrip("./")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def build_display_id(package_path: str, problem_index: int) -> str:
    normalized = normalize_package_path(package_path)
    digest = hashlib.sha1(f"{normalized}:{problem_index}".encode("utf-8")).hexdigest()[:12]
    return f"fpsm-{digest}"


def build_fallback_display_id(package_path: str, problem_index: int, problem_id: int) -> str:
    normalized = normalize_package_path(package_path)
    digest = hashlib.sha1(f"{normalized}:{problem_index}:{problem_id}".encode("utf-8")).hexdigest()[:16]
    return f"fpsm-{digest}"


def scan_package_paths(repo_dir: Path) -> list[str]:
    package_paths: list[str] = []
    for path in repo_dir.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".xml", ".zip"}:
            continue
        package_paths.append(path.relative_to(repo_dir).as_posix())
    return sorted(package_paths)


def strip_html(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_problem_statement_language(problem: dict[str, Any]) -> str:
    text = "\n".join(
        [
            strip_html(problem.get("title")),
            strip_html(problem.get("description")),
            strip_html(problem.get("input")),
            strip_html(problem.get("output")),
            strip_html(problem.get("hint")),
        ]
    )
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_count = len(re.findall(r"[A-Za-z]", text))
    if chinese_count and not english_count:
        return "zh"
    if english_count and not chinese_count:
        return "en"
    if chinese_count and english_count:
        if chinese_count >= max(english_count // 4, 1):
            return "zh"
        if english_count >= max(chinese_count * 4, 1):
            return "en"
        return "mixed"
    return "unknown"


def detect_problem_difficulty_by_rule(problem: dict[str, Any], package_path: str) -> str:
    title = str(problem.get("title") or "")
    source = str(problem.get("source") or "")
    summary = build_problem_summary(problem)
    package_name = normalize_package_path(package_path)
    text = _normalize_text(title, source, summary, package_name)
    samples_count = len(problem.get("samples") or [])

    easy_keywords = [
        "a+b",
        "入门",
        "基础",
        "简单",
        "example",
        "hello world",
        "顺序结构",
    ]
    hard_keywords = [
        "提高级",
        "省选",
        "noi",
        "noip 提高",
        "csp-s",
        "最短路",
        "线段树",
        "并查集",
        "动态规划",
        "dp",
        "图论",
        "网络流",
        "强连通",
        "树状数组",
    ]

    if any(keyword in text for keyword in easy_keywords):
        return "easy"
    if any(keyword in text for keyword in hard_keywords):
        return "hard"

    topic_text = _normalize_text(title, source, package_name)
    if any(keyword in topic_text for keyword in ["sql", "数据库", "frontend", "backend", "api"]):
        return "medium"
    if samples_count >= 5:
        return "hard"
    if samples_count <= 1 and len(summary) < 180:
        return "easy"
    return "medium"


def map_fps_language_to_frontend(language: str) -> str | None:
    normalized = str(language or "").strip().lower()
    mapping = {
        "javascript": "javascript",
        "nodejs": "javascript",
        "c": "c",
        "c++": "cpp",
        "cpp": "cpp",
        "java": "java",
        "python": "python",
        "python3": "python",
    }
    return mapping.get(normalized)


def parse_fps_xml_bytes(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    problems: list[dict[str, Any]] = []
    for item in root.findall("item"):
        problem = {
            "title": "",
            "description": "",
            "input": "",
            "output": "",
            "hint": "",
            "source": "",
            "samples": [],
            "templates": [],
            "appends": [],
            "prepends": [],
        }
        sample_state: dict[str, str] | None = None
        for child in item:
            tag = child.tag
            text = child.text or ""
            if tag in {"title", "description", "input", "output", "hint", "source"}:
                problem[tag] = text
            elif tag in {"template", "append", "prepend"}:
                language = child.attrib.get("language", "")
                mapped = map_fps_language_to_frontend(language)
                entry = {"language": language, "frontend_language": mapped, "code": text}
                if tag == "template":
                    problem["templates"].append(entry)
                elif tag == "append":
                    problem["appends"].append(entry)
                else:
                    problem["prepends"].append(entry)
            elif tag == "sample_input":
                sample_state = {"input": text, "output": ""}
                problem["samples"].append(sample_state)
            elif tag == "sample_output":
                if sample_state is None:
                    sample_state = {"input": "", "output": text}
                    problem["samples"].append(sample_state)
                else:
                    sample_state["output"] = text
        detected_languages = [
            mapped
            for entry in [*problem["templates"], *problem["appends"], *problem["prepends"]]
            if (mapped := entry.get("frontend_language"))
        ]
        problem["detected_languages"] = list(dict.fromkeys(detected_languages))
        problems.append(problem)
    return problems


def load_package_snapshot(repo_dir: Path, package_path: str) -> dict[str, Any]:
    relative_path = normalize_package_path(package_path)
    absolute_path = repo_dir / relative_path
    if not absolute_path.exists():
        raise FileNotFoundError(f"Package not found: {relative_path}")

    package_bytes = absolute_path.read_bytes()
    package_sha = sha256_bytes(package_bytes)
    if absolute_path.suffix.lower() == ".xml":
        problems = parse_fps_xml_bytes(package_bytes)
        return {
            "package_path": relative_path,
            "package_type": "xml",
            "package_sha": package_sha,
            "problems": problems,
            "xml_entries": [relative_path],
        }

    if absolute_path.suffix.lower() != ".zip":
        raise RuntimeError(f"Unsupported package type: {relative_path}")

    problems: list[dict[str, Any]] = []
    xml_entries: list[str] = []
    with zipfile.ZipFile(absolute_path) as archive:
        for member in sorted(archive.namelist()):
            if member.endswith("/") or not member.lower().endswith(".xml"):
                continue
            xml_entries.append(member)
            problems.extend(parse_fps_xml_bytes(archive.read(member)))
    if not xml_entries:
        raise RuntimeError(f"No XML found in zip package: {relative_path}")
    return {
        "package_path": relative_path,
        "package_type": "zip",
        "package_sha": package_sha,
        "problems": problems,
        "xml_entries": xml_entries,
    }


def build_problem_sha(problem: dict[str, Any]) -> str:
    return sha256_json(
        {
            "title": problem.get("title") or "",
            "source": problem.get("source") or "",
            "description": strip_html(problem.get("description")),
            "input": strip_html(problem.get("input")),
            "output": strip_html(problem.get("output")),
        }
    )


def build_problem_summary(problem: dict[str, Any]) -> str:
    parts = [
        strip_html(problem.get("description")),
        strip_html(problem.get("input")),
        strip_html(problem.get("output")),
        strip_html(problem.get("hint")),
    ]
    merged = "\n".join(part for part in parts if part)
    return merged[:1600]


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"No JSON object found: {text}")
    return json.loads(text[start : end + 1])


def _normalize_text(*parts: Any) -> str:
    return " ".join(strip_html(part).lower() for part in parts if part)


def classify_problem_entry_by_rule(problem: dict[str, Any], package_path: str) -> dict[str, Any]:
    title = str(problem.get("title") or "")
    source = str(problem.get("source") or "")
    summary = build_problem_summary(problem)
    package_name = normalize_package_path(package_path)
    text = _normalize_text(title, source, summary, package_name)

    topic_keywords = {
        "sql": ["sql", "mysql", "select ", "join", "group by", "数据库", "查询"],
        "database": ["database", "数据库", "事务", "索引", "表", "sql"],
        "frontend_dom": ["dom", "html", "css", "浏览器", "页面", "前端", "事件冒泡", "event loop"],
        "frontend_async": ["promise", "async", "await", "fetch", "ajax", "异步", "vue", "react", "nodejs"],
        "backend_api": ["api", "http", "rest", "rpc", "服务", "后端", "server", "middleware"],
        "backend_concurrency": ["并发", "concurrency", "thread", "lock", "mutex", "协程", "goroutine"],
        "dynamic_programming": ["dp", "动态规划", "状态转移"],
        "binary_search": ["二分", "binary search"],
        "sorting": ["排序", "sort", "quick sort", "merge sort"],
        "greedy": ["贪心", "greedy"],
        "graph": ["图", "graph", "最短路", "拓扑", "dijkstra", "floyd", "kruskal", "prim"],
        "tree": ["树", "tree", "二叉", "bst", "trie", "线段树"],
        "linked_list": ["链表", "linked list"],
        "queue": ["队列", "queue", "deque"],
        "stack": ["栈", "stack", "括号"],
        "hash_table": ["哈希", "hash", "map", "字典", "set"],
        "string": ["字符串", "string", "文本", "回文"],
        "array": ["数组", "array", "序列", "子数组"],
        "math": ["数学", "math", "几何", "质数", "取模", "概率"],
        "simulation": ["模拟", "simulation"],
    }

    topic_tags: list[str] = []
    for tag, keywords in topic_keywords.items():
        if any(keyword in text for keyword in keywords):
            topic_tags.append(tag)

    if not topic_tags:
        topic_tags.append("simulation")

    position_tags = ["algorithm_general"]
    if any(keyword in text for keyword in ["前端", "frontend", "dom", "html", "css", "javascript", "react", "vue"]):
        position_tags.append("frontend")
    if any(keyword in text for keyword in ["后端", "backend", "api", "服务", "server", "数据库", "sql", "并发"]):
        position_tags.append("backend")

    return {
        "topic_tags": list(dict.fromkeys(topic_tags))[:4],
        "position_tags": list(dict.fromkeys(position_tags))[:3],
        "difficulty_tag": detect_problem_difficulty_by_rule(problem, package_path),
    }


async def classify_problem_entry_by_llm(problem: dict[str, Any], package_path: str) -> dict[str, Any]:
    from src.models import select_model

    model = select_model()
    prompt = {
        "task": "classify_problem",
        "package_path": package_path,
        "title": problem.get("title") or "",
        "source": problem.get("source") or "",
        "summary": build_problem_summary(problem),
        "allowed_topic_tags": TOPIC_TAGS,
        "allowed_position_tags": POSITION_TAGS,
        "allowed_difficulty_tags": DIFFICULTY_TAGS,
        "rules": [
            "topic_tags 必须只从 allowed_topic_tags 中选择 1 到 4 个",
            "position_tags 必须只从 allowed_position_tags 中选择 1 到 3 个",
            "difficulty_tag 必须只从 allowed_difficulty_tags 中选择 1 个",
            "如果题目主要是基础算法/数据结构/通用编程题，必须包含 algorithm_general",
            "只有当题目明显偏前端或后端工程实践时，才补充 frontend 或 backend",
            "严格返回 JSON，不要输出额外解释",
        ],
        "output_schema": {
            "topic_tags": ["array"],
            "position_tags": ["algorithm_general"],
            "difficulty_tag": "medium",
        },
    }
    response = await model.call(
        [
            {
                "role": "system",
                "content": "你是编程题分类助手，只能返回合法 JSON。",
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        stream=False,
    )
    parsed = extract_json_object(response.content or "")
    topic_tags = [tag for tag in parsed.get("topic_tags") or [] if tag in TOPIC_TAGS]
    position_tags = [tag for tag in parsed.get("position_tags") or [] if tag in POSITION_TAGS]
    difficulty_tag = str(parsed.get("difficulty_tag") or "").strip().lower()
    if not topic_tags:
        raise ValueError(f"LLM returned empty topic_tags for {package_path}::{problem.get('title')}")
    if not position_tags:
        position_tags = ["algorithm_general"]
    if difficulty_tag not in DIFFICULTY_TAGS:
        difficulty_tag = detect_problem_difficulty_by_rule(problem, package_path)
    return {
        "topic_tags": list(dict.fromkeys(topic_tags))[:4],
        "position_tags": list(dict.fromkeys(position_tags))[:3],
        "difficulty_tag": difficulty_tag,
    }


async def classify_problem_entry(
    problem: dict[str, Any],
    package_path: str,
    *,
    classifier: str,
) -> dict[str, Any]:
    if classifier == "llm":
        return await classify_problem_entry_by_llm(problem, package_path)
    return classify_problem_entry_by_rule(problem, package_path)


async def classify_packages(
    repo_dir: Path,
    manifest: dict[str, Any],
    package_paths: list[str],
    *,
    classifier: str,
) -> dict[str, Any]:
    existing_problem_map = {}
    for item in manifest.get("problems") or []:
        if not isinstance(item, dict):
            continue
        key = (
            normalize_package_path(item.get("package_path") or ""),
            str(item.get("package_sha") or ""),
            int(item.get("problem_index") or 0),
            str(item.get("problem_sha") or ""),
        )
        existing_problem_map[key] = item

    retained_packages = {
        normalize_package_path(item.get("package_path") or ""): item
        for item in manifest.get("packages") or []
        if isinstance(item, dict)
    }
    retained_problems = [
        item
        for item in manifest.get("problems") or []
        if isinstance(item, dict) and normalize_package_path(item.get("package_path") or "") not in package_paths
    ]

    updated_packages: list[dict[str, Any]] = []
    updated_problems: list[dict[str, Any]] = []

    for package_path in package_paths:
        snapshot = load_package_snapshot(repo_dir, package_path)
        package_entries: list[dict[str, Any]] = []
        for index, problem in enumerate(snapshot["problems"], start=1):
            problem_sha = build_problem_sha(problem)
            existing = existing_problem_map.get((snapshot["package_path"], snapshot["package_sha"], index, problem_sha))
            if (
                existing
                and existing.get("topic_tags")
                and existing.get("position_tags")
                and existing.get("difficulty_tag")
                and str(existing.get("classifier") or "rule") == classifier
            ):
                tags = {
                    "topic_tags": existing.get("topic_tags") or [],
                    "position_tags": existing.get("position_tags") or ["algorithm_general"],
                    "difficulty_tag": existing.get("difficulty_tag") or detect_problem_difficulty_by_rule(problem, snapshot["package_path"]),
                }
            else:
                tags = await classify_problem_entry(problem, snapshot["package_path"], classifier=classifier)
            package_entries.append(
                {
                    "package_path": snapshot["package_path"],
                    "package_type": snapshot["package_type"],
                    "package_sha": snapshot["package_sha"],
                    "problem_index": index,
                    "problem_sha": problem_sha,
                    "title": problem.get("title") or f"Problem {index}",
                    "source": problem.get("source") or snapshot["package_path"],
                    "summary": build_problem_summary(problem)[:180],
                    "description": strip_html(problem.get("description")),
                    "input_description": strip_html(problem.get("input")),
                    "output_description": strip_html(problem.get("output")),
                    "examples": list(problem.get("samples") or []),
                    "starter_code": {
                        language: entry.get("code") or ""
                        for entry in (problem.get("templates") or [])
                        if (language := entry.get("frontend_language")) in SUPPORTED_FRONTEND_LANGUAGES
                    },
                    "statement_language": existing.get("statement_language")
                    if existing and existing.get("statement_language")
                    else detect_problem_statement_language(problem),
                    "difficulty_tag": tags["difficulty_tag"],
                    "allowed_languages": list(problem.get("detected_languages") or []),
                    "topic_tags": tags["topic_tags"],
                    "position_tags": tags["position_tags"],
                    "supported_languages": SUPPORTED_FRONTEND_LANGUAGES,
                    "oj_problem_ids": list(existing.get("oj_problem_ids") or []) if existing else [],
                    "oj_display_ids": list(existing.get("oj_display_ids") or []) if existing else [],
                    "imported_at": existing.get("imported_at") if existing else None,
                    "classifier": classifier,
                }
            )
        updated_problems.extend(package_entries)
        imported_values = [item.get("imported_at") for item in package_entries if item.get("imported_at")]
        updated_packages.append(
            {
                "package_path": snapshot["package_path"],
                "package_type": snapshot["package_type"],
                "package_sha": snapshot["package_sha"],
                "problem_count": len(package_entries),
                "oj_problem_ids": [problem_id for entry in package_entries for problem_id in (entry.get("oj_problem_ids") or [])],
                "oj_display_ids": [display_id for entry in package_entries for display_id in (entry.get("oj_display_ids") or [])],
                "imported_at": max(imported_values) if imported_values else None,
                "updated_at": utc_now(),
                "classifier": classifier,
            }
        )
        retained_packages.pop(snapshot["package_path"], None)

    manifest["repo_path"] = str(repo_dir)
    manifest["updated_at"] = utc_now()
    manifest["packages"] = [*retained_packages.values(), *updated_packages]
    manifest["problems"] = [*retained_problems, *updated_problems]
    return manifest


def login(session: requests.Session) -> None:
    profile = session.get(f"{OJ_BASE_URL}/api/profile", timeout=30)
    profile.raise_for_status()
    csrf_token = session.cookies.get("csrftoken", "")
    headers = {"X-CSRFToken": csrf_token} if csrf_token else {}
    response = session.post(
        f"{OJ_BASE_URL}/api/login",
        json={"username": OJ_USERNAME, "password": OJ_PASSWORD},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error") or payload.get("data") != "Succeeded":
        raise RuntimeError(f"OJ login failed: {payload}")


def csrf_headers(session: requests.Session) -> dict[str, str]:
    csrf_token = session.cookies.get("csrftoken", "")
    return {"X-CSRFToken": csrf_token} if csrf_token else {}


def list_admin_problems(session: requests.Session) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    offset = 0
    limit = 250
    while True:
        response = session.get(
            f"{OJ_BASE_URL}/api/admin/problem",
            params={"limit": limit, "offset": offset},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(f"List admin problems failed: {payload}")
        page = payload.get("data") or {}
        page_results = page.get("results") or []
        if not page_results:
            break
        results.extend(page_results)
        offset += len(page_results)
        if offset >= int(page.get("total") or 0):
            break
    return results


def get_admin_problem_detail(session: requests.Session, problem_id: int) -> dict[str, Any]:
    response = session.get(f"{OJ_BASE_URL}/api/admin/problem", params={"id": problem_id}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"Get problem detail failed: {payload}")
    return payload.get("data") or {}


def update_admin_problem(
    session: requests.Session,
    problem_id: int,
    *,
    source: str,
    package_path: str,
    problem_index: int,
) -> str | None:
    detail = get_admin_problem_detail(session, problem_id)
    if detail.get("spj") and not detail.get("spj_compile_ok"):
        print(f"Skip SPJ problem without compiled checker: problem_id={problem_id}")
        return None
    tags = list(dict.fromkeys([*(detail.get("tags") or []), "freeproblemset"]))
    if not tags:
        tags = ["freeproblemset"]
    samples = detail.get("samples") or []
    normalized_samples = []
    for sample in samples:
        normalized_samples.append(
            {
                "input": sample.get("input") if sample.get("input") not in (None, "") else "N/A",
                "output": sample.get("output") if sample.get("output") not in (None, "") else "N/A",
            }
        )
    if not normalized_samples:
        normalized_samples = [{"input": "N/A", "output": "N/A"}]

    normalized_test_case_score = []
    for index, item in enumerate(detail.get("test_case_score") or [], start=1):
        normalized_test_case_score.append(
            {
                "input_name": item.get("input_name") or f"{index}.in",
                "output_name": item.get("output_name") or f"{index}.out",
                "score": item.get("score") if item.get("score") is not None else 100,
            }
        )

    payload = {
        "id": detail["id"],
        "_id": build_display_id(package_path, problem_index),
        "title": detail.get("title") or "",
        "description": detail.get("description") or "",
        "input_description": detail.get("input_description") or "",
        "output_description": detail.get("output_description") or "",
        "samples": normalized_samples,
        "test_case_id": detail["test_case_id"],
        "test_case_score": normalized_test_case_score,
        "time_limit": min(max(int(detail.get("time_limit") or 1000), 1), 1000 * 60),
        "memory_limit": min(max(int(detail.get("memory_limit") or 128), 1), 1024),
        "languages": SUPPORTED_OJ_LANGUAGES,
        "template": {
            language: code
            for language, code in (detail.get("template") or {}).items()
            if language in SUPPORTED_OJ_LANGUAGES
        },
        "rule_type": detail.get("rule_type") or "ACM",
        "io_mode": detail.get("io_mode") or {"io_mode": "Standard IO", "input": "input.txt", "output": "output.txt"},
        "spj": bool(detail.get("spj")),
        "spj_language": detail.get("spj_language"),
        "spj_code": detail.get("spj_code"),
        "spj_compile_ok": bool(detail.get("spj_compile_ok")),
        "visible": True,
        "difficulty": detail.get("difficulty") or "Mid",
        "tags": tags,
        "hint": detail.get("hint") or "",
        "source": source,
        "share_submission": bool(detail.get("share_submission")),
    }
    response = session.put(
        f"{OJ_BASE_URL}/api/admin/problem",
        json=payload,
        headers=csrf_headers(session),
        timeout=30,
    )
    body = response.json()
    if response.ok and not body.get("error"):
        return payload["_id"]
    if body.get("data") == "Display ID already exists":
        payload["_id"] = build_fallback_display_id(package_path, problem_index, problem_id)
        response = session.put(
            f"{OJ_BASE_URL}/api/admin/problem",
            json=payload,
            headers=csrf_headers(session),
            timeout=30,
        )
        body = response.json()
        if response.ok and not body.get("error"):
            return payload["_id"]
    response.raise_for_status()
    if body.get("error"):
        raise RuntimeError(f"Update imported problem failed: {body}")
    return payload["_id"]


def upload_fps_file(session: requests.Session, file_path: Path) -> None:
    with file_path.open("rb") as handle:
        response = session.post(
            f"{OJ_BASE_URL}/api/admin/import_fps",
            files={"file": (file_path.name, handle, "application/xml")},
            timeout=IMPORT_UPLOAD_TIMEOUT,
        )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"Import FPS failed: {payload}")


def materialize_import_xmls(repo_dir: Path, package_path: str, temp_dir: Path) -> list[Path]:
    def append_paired_fields(
        item: ET.Element,
        *,
        input_tag: str,
        output_tag: str,
        default_input: str,
        default_output: str,
    ) -> None:
        inputs = [child.text if child.text not in (None, "") else default_input for child in item.findall(input_tag)]
        outputs = [child.text if child.text not in (None, "") else default_output for child in item.findall(output_tag)]
        pair_count = max(len(inputs), len(outputs), 1)
        while len(inputs) < pair_count:
            inputs.append(default_input)
        while len(outputs) < pair_count:
            outputs.append(default_output)
        for index in range(pair_count):
            ET.SubElement(item, input_tag).text = inputs[index]
            ET.SubElement(item, output_tag).text = outputs[index]

    def split_xml_file_if_needed(xml_path: Path) -> list[Path]:
        root = ET.fromstring(xml_path.read_bytes().lstrip(b"\xef\xbb\xbf"))
        items = root.findall("item")
        if len(items) <= IMPORT_CHUNK_SIZE:
            return [xml_path]

        chunk_paths: list[Path] = []
        for chunk_index, start in enumerate(range(0, len(items), IMPORT_CHUNK_SIZE), start=1):
            chunk_root = ET.Element(root.tag, root.attrib)
            for item in items[start : start + IMPORT_CHUNK_SIZE]:
                chunk_root.append(item)
            chunk_path = xml_path.with_name(f"{xml_path.stem}.part{chunk_index}{xml_path.suffix}")
            chunk_path.write_bytes(ET.tostring(chunk_root, encoding="utf-8", xml_declaration=True))
            chunk_paths.append(chunk_path)
        try:
            xml_path.unlink()
        except OSError:
            pass
        return chunk_paths

    def normalize_fps_xml_bytes(raw_xml: bytes) -> bytes:
        field_defaults = {
            "title": "Untitled Problem",
            "description": "No description provided.",
            "input": "No additional input description.",
            "output": "Output the required result according to the problem statement.",
            "time_limit": "1000",
            "memory_limit": "128",
        }
        placeholder_by_tag = {
            "sample_input": "N/A",
            "sample_output": "N/A",
            "test_input": "N/A",
            "test_output": "N/A",
            "hint": "",
            "source": "",
        }
        root = ET.fromstring(raw_xml.lstrip(b"\xef\xbb\xbf"))
        version = str(root.attrib.get("version") or "").strip()
        if version not in {"1.1", "1.2"}:
            root.attrib["version"] = "1.2"

        for item in root.findall("item"):
            existing_tags = {child.tag: child for child in item}
            for required_tag, default_text in field_defaults.items():
                node = existing_tags.get(required_tag)
                if node is None:
                    node = ET.SubElement(item, required_tag)
                    existing_tags[required_tag] = node
                if node.text is None or not str(node.text).strip():
                    node.text = default_text
                if required_tag == "time_limit" and not node.attrib.get("unit"):
                    node.attrib["unit"] = "ms"
                if required_tag == "memory_limit" and not node.attrib.get("unit"):
                    node.attrib["unit"] = "MB"

            removable_children = []

            for child in item:
                if child.tag in {"img", "solution", "spj"}:
                    removable_children.append(child)
                    continue
                if child.tag in {"sample_input", "sample_output", "test_input", "test_output"}:
                    removable_children.append(child)
                    continue
                if child.tag not in {"time_limit", "memory_limit"}:
                    if child.tag in placeholder_by_tag and (child.text is None or not str(child.text).strip()):
                        child.text = placeholder_by_tag[child.tag]
                    continue
                raw_text = str(child.text or "").strip()
                if not raw_text:
                    continue
                try:
                    integer_value = int(raw_text)
                    if integer_value <= 0:
                        child.text = "1000" if child.tag == "time_limit" else "128"
                    continue
                except ValueError:
                    pass

                try:
                    numeric = float(raw_text)
                except ValueError:
                    continue

                unit = str(child.attrib.get("unit") or "").strip().lower()
                if child.tag == "time_limit":
                    if unit == "s":
                        child.attrib["unit"] = "ms"
                        child.text = str(max(int(round(numeric * 1000)), 1))
                    else:
                        child.text = str(max(int(round(numeric)), 1))
                else:
                    child.text = str(max(int(round(numeric)), 1))

            for child in removable_children:
                item.remove(child)

            append_paired_fields(
                item,
                input_tag="sample_input",
                output_tag="sample_output",
                default_input=placeholder_by_tag["sample_input"],
                default_output=placeholder_by_tag["sample_output"],
            )
            append_paired_fields(
                item,
                input_tag="test_input",
                output_tag="test_output",
                default_input=placeholder_by_tag["test_input"],
                default_output=placeholder_by_tag["test_output"],
            )

        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    absolute_path = repo_dir / normalize_package_path(package_path)
    if absolute_path.suffix.lower() == ".xml":
        target_path = temp_dir / absolute_path.name
        target_path.write_bytes(normalize_fps_xml_bytes(absolute_path.read_bytes()))
        return split_xml_file_if_needed(target_path)

    xml_paths: list[Path] = []
    with zipfile.ZipFile(absolute_path) as archive:
        for member in sorted(archive.namelist()):
            if member.endswith("/") or not member.lower().endswith(".xml"):
                continue
            target_path = temp_dir / Path(member).name
            target_path.write_bytes(normalize_fps_xml_bytes(archive.read(member)))
            xml_paths.extend(split_xml_file_if_needed(target_path))
    if not xml_paths:
        raise RuntimeError(f"No XML found in zip package: {package_path}")
    return xml_paths


def match_imported_problems(local_entries: list[dict[str, Any]], new_problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = sorted(new_problems, key=lambda item: int(item.get("id") or 0))
    matched: list[dict[str, Any]] = []
    for entry in local_entries:
        title = str(entry.get("title") or "")
        source = str(entry.get("source") or "")
        target = None
        for candidate in remaining:
            if str(candidate.get("title") or "") == title and str(candidate.get("source") or "") == source:
                target = candidate
                break
        if target is None:
            for candidate in remaining:
                if str(candidate.get("title") or "") == title:
                    target = candidate
                    break
        if target is None and remaining:
            target = remaining[0]
        if target is None:
            break
        matched.append(target)
        remaining.remove(target)
    return matched


def normalize_classifier(classifier: str) -> str:
    normalized = str(classifier or "").strip().lower() or "rule"
    if normalized not in {"rule", "llm"}:
        raise ValueError(f"Unsupported classifier: {classifier}")
    return normalized


async def classify_command(repo_dir: Path, *, classifier: str) -> None:
    ensure_repo_exists(repo_dir)
    manifest = load_manifest()
    package_paths = scan_package_paths(repo_dir)
    manifest = await classify_packages(repo_dir, manifest, package_paths, classifier=classifier)
    save_manifest(manifest)
    print(f"Classified {len(package_paths)} packages, {len(manifest['problems'])} problems, classifier={classifier}")


async def import_package_command(repo_dir: Path, package_path: str, force: bool, *, classifier: str) -> None:
    ensure_repo_exists(repo_dir)
    normalized_package_path = normalize_package_path(package_path)
    manifest = await classify_packages(repo_dir, load_manifest(), [normalized_package_path], classifier=classifier)

    snapshot = load_package_snapshot(repo_dir, normalized_package_path)
    package_entries = [
        item
        for item in manifest.get("problems") or []
        if normalize_package_path(item.get("package_path") or "") == normalized_package_path
        and str(item.get("package_sha") or "") == snapshot["package_sha"]
    ]
    if not package_entries:
        raise RuntimeError(f"No manifest entries found for package: {normalized_package_path}")

    package_record = next(
        (
            item
            for item in manifest.get("packages") or []
            if normalize_package_path(item.get("package_path") or "") == normalized_package_path
            and str(item.get("package_sha") or "") == snapshot["package_sha"]
        ),
        None,
    )
    if package_record and package_record.get("imported_at") and not force:
        print(f"Skip already imported package: {normalized_package_path} ({snapshot['package_sha']})")
        save_manifest(manifest)
        return

    session = requests.Session()
    login(session)
    before_problems = list_admin_problems(session)
    before_ids = {int(item.get("id")) for item in before_problems if item.get("id") is not None}

    with tempfile.TemporaryDirectory() as temp_dir_name:
        xml_paths = materialize_import_xmls(repo_dir, normalized_package_path, Path(temp_dir_name))
        for xml_path in xml_paths:
            upload_fps_file(session, xml_path)

    after_problems = list_admin_problems(session)
    added_problems = [item for item in after_problems if int(item.get("id") or 0) not in before_ids]
    matched_problems = match_imported_problems(package_entries, added_problems)
    if len(matched_problems) < len(package_entries):
        raise RuntimeError(
            f"Imported problem count mismatch: expected {len(package_entries)}, matched {len(matched_problems)}"
        )

    imported_at = utc_now()
    for entry, imported_problem in zip(package_entries, matched_problems, strict=False):
        problem_id = int(imported_problem["id"])
        display_id = update_admin_problem(
            session,
            problem_id,
            source=str(entry.get("source") or normalized_package_path),
            package_path=normalized_package_path,
            problem_index=int(entry.get("problem_index") or 0),
        )
        if display_id:
            entry["oj_problem_ids"] = [problem_id]
            entry["oj_display_ids"] = [display_id]
            entry["supported_languages"] = SUPPORTED_FRONTEND_LANGUAGES
            entry["imported_at"] = imported_at
        else:
            entry["oj_problem_ids"] = []
            entry["oj_display_ids"] = []
            entry["imported_at"] = None

    manifest["updated_at"] = utc_now()
    for item in manifest.get("problems") or []:
        if normalize_package_path(item.get("package_path") or "") != normalized_package_path:
            continue
        for entry in package_entries:
            if int(item.get("problem_index") or 0) == int(entry.get("problem_index") or 0) and str(item.get("package_sha") or "") == snapshot["package_sha"]:
                item.update(entry)
                break

    manifest_packages = []
    package_updated = False
    for item in manifest.get("packages") or []:
        if normalize_package_path(item.get("package_path") or "") == normalized_package_path:
            manifest_packages.append(
                {
                    "package_path": normalized_package_path,
                    "package_type": snapshot["package_type"],
                    "package_sha": snapshot["package_sha"],
                    "problem_count": len(package_entries),
                    "oj_problem_ids": [problem_id for entry in package_entries for problem_id in (entry.get("oj_problem_ids") or [])],
                    "oj_display_ids": [display_id for entry in package_entries for display_id in (entry.get("oj_display_ids") or [])],
                    "imported_at": imported_at if any(entry.get("imported_at") for entry in package_entries) else None,
                    "updated_at": utc_now(),
                    "classifier": classifier,
                }
            )
            package_updated = True
        else:
            manifest_packages.append(item)
    if not package_updated:
        manifest_packages.append(
            {
                "package_path": normalized_package_path,
                "package_type": snapshot["package_type"],
                "package_sha": snapshot["package_sha"],
                "problem_count": len(package_entries),
                "oj_problem_ids": [problem_id for entry in package_entries for problem_id in (entry.get("oj_problem_ids") or [])],
                "oj_display_ids": [display_id for entry in package_entries for display_id in (entry.get("oj_display_ids") or [])],
                "imported_at": imported_at if any(entry.get("imported_at") for entry in package_entries) else None,
                "updated_at": utc_now(),
                "classifier": classifier,
            }
        )
    manifest["packages"] = manifest_packages
    save_manifest(manifest)
    print(f"Imported package {normalized_package_path}: {len(package_entries)} problems")


async def import_all_command(repo_dir: Path, force: bool, *, classifier: str) -> None:
    ensure_repo_exists(repo_dir)
    package_paths = scan_package_paths(repo_dir)
    if not package_paths:
        print("No freeproblemset packages found")
        return

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    for index, package_path in enumerate(package_paths, start=1):
        print(f"[{index}/{len(package_paths)}] Importing {package_path}")
        try:
            await import_package_command(repo_dir, package_path, force, classifier=classifier)
            succeeded.append(package_path)
        except Exception as exc:
            failed.append((package_path, str(exc)))
            print(f"[FAILED] {package_path}: {exc}")

    print(
        f"Import-all finished. total={len(package_paths)}, succeeded={len(succeeded)}, failed={len(failed)}"
    )
    if failed:
        print("Failed packages:")
        for package, reason in failed:
            print(f" - {package}: {reason}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage zhblue/freeproblemset mirror and QingdaoU OJ imports")
    parser.add_argument("--repo-dir", default=str(DEFAULT_REPO_DIR))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync")
    classify_parser = subparsers.add_parser("classify")
    classify_parser.add_argument("--classifier", choices=["rule", "llm"], default=DEFAULT_CLASSIFIER)

    import_parser = subparsers.add_parser("import-package")
    import_parser.add_argument("--package", required=True)
    import_parser.add_argument("--force", action="store_true")
    import_parser.add_argument("--classifier", choices=["rule", "llm"], default=DEFAULT_CLASSIFIER)

    import_all_parser = subparsers.add_parser("import-all")
    import_all_parser.add_argument("--force", action="store_true")
    import_all_parser.add_argument("--classifier", choices=["rule", "llm"], default=DEFAULT_CLASSIFIER)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    repo_dir = Path(args.repo_dir)

    if args.command == "sync":
        sync_repository(repo_dir)
        return
    if args.command == "classify":
        asyncio.run(classify_command(repo_dir, classifier=normalize_classifier(args.classifier)))
        return
    if args.command == "import-package":
        asyncio.run(
            import_package_command(
                repo_dir,
                args.package,
                args.force,
                classifier=normalize_classifier(args.classifier),
            )
        )
        return
    if args.command == "import-all":
        asyncio.run(
            import_all_command(
                repo_dir,
                args.force,
                classifier=normalize_classifier(args.classifier),
            )
        )
        return
    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
