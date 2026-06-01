from __future__ import annotations

import ast
import base64
import hashlib
import html
import json
import os
import random
import re
import xml.etree.ElementTree as ET
import zipfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import select_model
from src.services.position_types import get_problemset_tag_for_position
from src.repositories.conversation_repository import ConversationRepository
from src.storage.postgres.manager import pg_manager
from src.utils.logging_config import logger

CODING_SESSION_METADATA_KEY = "coding_session"
PRACTICE_SESSION_METADATA_KEY = "practice_session"
DEFAULT_CODING_LANGUAGE = "javascript"
CODING_WORKBENCH_ROUTE = "/agent/interview/code"
PRACTICE_WORKBENCH_ROUTE = "/practice/problem"
PRACTICE_AGENT_ID = "PracticeWorkbench"
OJ_API_BASE_URL = os.getenv("OJ_API_BASE_URL", "http://oj-backend.local:8000/api").rstrip("/")
OJ_APPKEY = os.getenv("OJ_APPKEY", "").strip()
# OJ 凭据无安全默认值；缺失时由 _require_oj_credentials/_judge_server_request 在调用时 fail-fast
OJ_USERNAME = os.getenv("OJ_USERNAME", "").strip()
OJ_PASSWORD = os.getenv("OJ_PASSWORD", "").strip()
OJ_PROBLEM_SOURCE = os.getenv("OJ_PROBLEM_SOURCE", "interview-seed").strip()
OJ_REQUEST_TIMEOUT = float(os.getenv("OJ_REQUEST_TIMEOUT", "20"))
OJ_PAGE_LIMIT = min(max(int(os.getenv("OJ_PAGE_LIMIT", "250")), 1), 250)
OJ_MAX_SCAN = max(int(os.getenv("OJ_MAX_SCAN", "1000")), OJ_PAGE_LIMIT)
OJ_JUDGE_SERVER_URL = os.getenv("OJ_JUDGE_SERVER_URL", "http://oj-judge-server:8080").rstrip("/")
OJ_JUDGE_SERVER_TOKEN = os.getenv("OJ_JUDGE_SERVER_TOKEN", "").strip()
FREEPROBLEMSET_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "saves" / "oj" / "freeproblemset_manifest.json"
FREEPROBLEMSET_REPO_DIR = Path(__file__).resolve().parents[2] / ".codex_tmp" / "freeproblemset"
CS_NOTES_CURATED_PROBLEMS_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "config" / "static" / "cs_notes_coding_problems.json"
)
SUPPORTED_FRONTEND_LANGUAGES = ["javascript", "c", "cpp", "java", "python"]
OJ_LANGUAGE_TO_FRONTEND = {
    "JavaScript": "javascript",
    "C": "c",
    "C++": "cpp",
    "Java": "java",
    "Python3": "python",
}
FRONTEND_LANGUAGE_TO_OJ = {value: key for key, value in OJ_LANGUAGE_TO_FRONTEND.items()}
FRONTEND_LANGUAGE_TO_FENCE = {
    "javascript": "javascript",
    "c": "c",
    "cpp": "cpp",
    "java": "java",
    "python": "python",
}
OJ_RESULT_CODE_MAP = {
    -2: "COMPILE_ERROR",
    -1: "WRONG_ANSWER",
    0: "ACCEPTED",
    1: "CPU_TIME_LIMIT_EXCEEDED",
    2: "REAL_TIME_LIMIT_EXCEEDED",
    3: "MEMORY_LIMIT_EXCEEDED",
    4: "RUNTIME_ERROR",
    5: "SYSTEM_ERROR",
    6: "PENDING",
    7: "JUDGING",
    8: "PARTIALLY_ACCEPTED",
}
PENDING_OJ_STATUSES = {"PENDING", "JUDGING"}
GENERAL_POSITION_TAG = "algorithm_general"
DEFAULT_EXECUTION_ENV = ["LANG=en_US.UTF-8", "LANGUAGE=en_US:en", "LC_ALL=en_US.UTF-8"]
JUDGE_SERVER_LANGUAGE_CONFIGS = {
    "c": {
        "compile": {
            "src_name": "main.c",
            "exe_name": "main",
            "max_cpu_time": 3000,
            "max_real_time": 10000,
            "max_memory": 256 * 1024 * 1024,
            "compile_command": "/usr/bin/gcc -DONLINE_JUDGE -O2 -w -fmax-errors=3 -std=c17 {src_path} -lm -o {exe_path}",
        },
        "run": {"command": "{exe_path}", "seccomp_rule": "c_cpp", "env": DEFAULT_EXECUTION_ENV},
    },
    "cpp": {
        "compile": {
            "src_name": "main.cpp",
            "exe_name": "main",
            "max_cpu_time": 10000,
            "max_real_time": 20000,
            "max_memory": 1024 * 1024 * 1024,
            "compile_command": "/usr/bin/g++ -DONLINE_JUDGE -O2 -w -fmax-errors=3 -std=c++20 {src_path} -lm -o {exe_path}",
        },
        "run": {"command": "{exe_path}", "seccomp_rule": "c_cpp", "env": DEFAULT_EXECUTION_ENV},
    },
    "java": {
        "compile": {
            "src_name": "Main.java",
            "exe_name": "Main",
            "max_cpu_time": 5000,
            "max_real_time": 10000,
            "max_memory": -1,
            "compile_command": "/usr/bin/javac {src_path} -d {exe_dir}",
        },
        "run": {
            "command": "/usr/bin/java -cp {exe_dir} -XX:MaxRAM={max_memory}k Main",
            "seccomp_rule": None,
            "env": DEFAULT_EXECUTION_ENV,
            "memory_limit_check_only": 1,
        },
    },
    "python": {
        "compile": {
            "src_name": "solution.py",
            "exe_name": "solution.py",
            "max_cpu_time": 3000,
            "max_real_time": 10000,
            "max_memory": 128 * 1024 * 1024,
            "compile_command": "/usr/bin/python3 -m py_compile {src_path}",
        },
        "run": {"command": "/usr/bin/python3 -BS {exe_path}", "seccomp_rule": "general", "env": DEFAULT_EXECUTION_ENV},
    },
    "javascript": {
        "compile": {
            "src_name": "main.js",
            "exe_name": "main.js",
            "max_cpu_time": 3000,
            "max_real_time": 5000,
            "max_memory": 1024 * 1024 * 1024,
            "compile_command": "/usr/bin/node --check {src_path}",
            "env": DEFAULT_EXECUTION_ENV,
        },
        "run": {
            "command": "/usr/bin/node {exe_path}",
            "seccomp_rule": "node",
            "env": DEFAULT_EXECUTION_ENV,
            "memory_limit_check_only": 1,
        },
    },
}


@dataclass
class OJProblem:
    id: int
    display_id: str
    title: str
    source: str
    summary: str
    description: str
    input_description: str
    output_description: str
    examples: list[dict[str, str]]
    starter_code: dict[str, str]
    allowed_languages: list[str]
    statement_language: str
    difficulty_tag: str


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _require_oj_credentials() -> None:
    if OJ_APPKEY:
        return
    if OJ_USERNAME and OJ_PASSWORD:
        return
    raise HTTPException(
        status_code=500,
        detail="OJ integration is not configured. Please set OJ_APPKEY or OJ_USERNAME/OJ_PASSWORD.",
    )


@asynccontextmanager
async def _get_oj_client():
    _require_oj_credentials()
    async with httpx.AsyncClient(base_url=OJ_API_BASE_URL + "/", timeout=OJ_REQUEST_TIMEOUT) as client:
        if OJ_APPKEY:
            client.headers["Appkey"] = OJ_APPKEY
        else:
            try:
                response = await client.get("profile")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Failed to initialize QingdaoU OJ session at {OJ_API_BASE_URL}. "
                        "Make sure oj-backend is running and reachable."
                    ),
                ) from exc
            csrf_token = client.cookies.get("csrftoken", "")
            if csrf_token:
                client.headers["X-CSRFToken"] = csrf_token
            headers = {"X-CSRFToken": csrf_token} if csrf_token else {}
            data = await _oj_request(
                client,
                "POST",
                "login",
                json={"username": OJ_USERNAME, "password": OJ_PASSWORD},
                headers=headers,
            )
            if data != "Succeeded":
                raise HTTPException(status_code=502, detail="Failed to login to QingdaoU OJ")
            csrf_token = client.cookies.get("csrftoken", "")
            if csrf_token:
                client.headers["X-CSRFToken"] = csrf_token
        yield client


async def _oj_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    try:
        response = await client.request(method, path.lstrip("/"), params=params, json=json, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("QingdaoU OJ request failed: %s %s", method, path)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with QingdaoU OJ at {OJ_API_BASE_URL}",
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid response from QingdaoU OJ") from exc

    if payload.get("error"):
        detail = payload.get("data") or payload.get("error") or "QingdaoU OJ returned an error"
        raise HTTPException(status_code=502, detail=str(detail))
    return payload.get("data")


def _build_sample_run_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "passed": False,
        "message": "",
        "stdout": "",
        "stderr": "",
        "compile_error": "",
        "tests": [],
        "ran_at": "",
    }


async def _judge_server_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not OJ_JUDGE_SERVER_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="OJ judge server is not configured. Please set OJ_JUDGE_SERVER_TOKEN.",
        )
    token = hashlib.sha256(OJ_JUDGE_SERVER_TOKEN.encode("utf-8")).hexdigest()
    urls = [OJ_JUDGE_SERVER_URL]
    if OJ_JUDGE_SERVER_URL.endswith(":12358"):
        urls.append(OJ_JUDGE_SERVER_URL.removesuffix(":12358") + ":8080")

    last_error: Exception | None = None
    for base_url in urls:
        try:
            async with httpx.AsyncClient(timeout=OJ_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{base_url}/judge",
                    json=payload,
                    headers={"X-Judge-Server-Token": token},
                )
                response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:
                raise HTTPException(status_code=502, detail="Invalid response from JudgeServer") from exc
            if not isinstance(data, dict):
                raise HTTPException(status_code=502, detail="Invalid response from JudgeServer")
            return data
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            continue

    raise HTTPException(status_code=502, detail=f"Failed to communicate with JudgeServer at {OJ_JUDGE_SERVER_URL}") from last_error


def _build_sample_run_result(
    examples: list[dict[str, str]],
    judge_response: dict[str, Any],
) -> dict[str, Any]:
    if judge_response.get("err"):
        compile_error = str(judge_response.get("data") or "")
        return {
            "status": "COMPILE_ERROR",
            "passed": False,
            "message": "Compile Error",
            "stdout": "",
            "stderr": "",
            "compile_error": compile_error,
            "tests": [],
            "ran_at": _utc_now(),
        }

    raw_cases = judge_response.get("data") or []
    tests: list[dict[str, Any]] = []
    status_list: list[str] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for index, raw_case in enumerate(raw_cases, start=1):
        status = _result_code_to_status(raw_case.get("result"))
        output_text = str(raw_case.get("output") or "")
        expected = examples[index - 1].get("output", "") if index - 1 < len(examples) else ""
        sample_input = examples[index - 1].get("input", "") if index - 1 < len(examples) else ""
        is_output_like = status in {"ACCEPTED", "WRONG_ANSWER", "PARTIALLY_ACCEPTED"}
        if is_output_like:
            status = "ACCEPTED" if _sample_outputs_match(output_text, expected) else "WRONG_ANSWER"
        status_list.append(status)
        stdout = output_text if is_output_like else ""
        stderr = "" if is_output_like else output_text
        if stdout:
            stdout_parts.append(f"[sample_{index}]\n{stdout}")
        if stderr:
            stderr_parts.append(f"[sample_{index}]\n{stderr}")
        tests.append(
            {
                "name": f"sample_{index}",
                "status": status,
                "passed": status == "ACCEPTED",
                "message": status,
                "input": sample_input,
                "expected_output": expected,
                "actual_output": output_text,
                "stdout": stdout,
                "stderr": stderr,
                "compile_error": "",
                "cpu_time": raw_case.get("cpu_time"),
                "memory": raw_case.get("memory"),
            }
        )

    overall_status = "ACCEPTED" if status_list and all(item == "ACCEPTED" for item in status_list) else (status_list[0] if status_list else "SYSTEM_ERROR")
    return {
        "status": overall_status,
        "passed": overall_status == "ACCEPTED",
        "message": "Sample tests passed" if overall_status == "ACCEPTED" else overall_status,
        "stdout": "\n\n".join(stdout_parts),
        "stderr": "\n\n".join(stderr_parts),
        "compile_error": "",
        "tests": tests,
        "ran_at": _utc_now(),
    }


def _html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = value
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_summary(problem_data: dict[str, Any]) -> str:
    hint = _html_to_text(problem_data.get("hint"))
    if hint:
        return hint[:180]
    description = _html_to_text(problem_data.get("description"))
    for line in description.splitlines():
        line = line.strip()
        if line:
            return line[:180]
    return problem_data.get("title", "")


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _parse_loose_literal(value: str) -> Any:
    text = value.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    normalized = re.sub(r"\btrue\b", "True", text)
    normalized = re.sub(r"\bfalse\b", "False", normalized)
    normalized = re.sub(r"\bnull\b", "None", normalized)
    return ast.literal_eval(normalized)


def _sample_outputs_match(actual_output: str, expected_output: str) -> bool:
    actual = actual_output.strip()
    expected = expected_output.strip()
    if actual == expected:
        return True
    try:
        return _parse_loose_literal(actual) == _parse_loose_literal(expected)
    except (ValueError, SyntaxError, json.JSONDecodeError):
        return False


def _extract_javascript_function_signature(code: str) -> tuple[str, list[str]] | None:
    match = re.search(
        r"(?:^|\n)\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\((.*?)\)",
        code,
        re.DOTALL,
    )
    if not match:
        return None
    function_name = match.group(1)
    raw_params = match.group(2).strip()
    if not raw_params:
        return function_name, []

    params: list[str] = []
    for raw_param in raw_params.split(","):
        param = raw_param.strip()
        if not param:
            continue
        param = param.removeprefix("...")
        param = param.split("=", 1)[0].strip()
        param = param.split(":", 1)[0].strip()
        if param:
            params.append(param)
    return function_name, params


def _strip_javascript_exports(code: str) -> str:
    return re.sub(r"(^|\n)(\s*)export\s+(default\s+)?", r"\1\2", code)


def _build_seed_problem_sample_source(problem: dict[str, Any], language: str, code: str) -> str:
    if language != "javascript":
        return code
    if str(problem.get("source") or "").strip() != OJ_PROBLEM_SOURCE:
        return code

    starter_code = str(((problem.get("starter_code") or {}).get(language)) or "")
    signature = _extract_javascript_function_signature(starter_code) or _extract_javascript_function_signature(code)
    if not signature:
        return code

    function_name, param_names = signature
    encoded_param_names = json.dumps(param_names, ensure_ascii=False)
    return (
        f"{_strip_javascript_exports(code).rstrip()}\n\n"
        "function __sampleSplitTopLevel(source) {\n"
        "  const parts = [];\n"
        "  let current = '';\n"
        "  let depth = 0;\n"
        "  let quote = '';\n"
        "  let escaped = false;\n"
        "  for (const char of source) {\n"
        "    if (quote) {\n"
        "      current += char;\n"
        "      if (escaped) {\n"
        "        escaped = false;\n"
        "        continue;\n"
        "      }\n"
        "      if (char === '\\\\') {\n"
        "        escaped = true;\n"
        "        continue;\n"
        "      }\n"
        "      if (char === quote) {\n"
        "        quote = '';\n"
        "      }\n"
        "      continue;\n"
        "    }\n"
        "    if (char === '\"' || char === \"'\") {\n"
        "      quote = char;\n"
        "      current += char;\n"
        "      continue;\n"
        "    }\n"
        "    if (char === '[' || char === '{' || char === '(') {\n"
        "      depth += 1;\n"
        "      current += char;\n"
        "      continue;\n"
        "    }\n"
        "    if (char === ']' || char === '}' || char === ')') {\n"
        "      depth = Math.max(0, depth - 1);\n"
        "      current += char;\n"
        "      continue;\n"
        "    }\n"
        "    if (char === ',' && depth === 0) {\n"
        "      if (current.trim()) {\n"
        "        parts.push(current.trim());\n"
        "      }\n"
        "      current = '';\n"
        "      continue;\n"
        "    }\n"
        "    current += char;\n"
        "  }\n"
        "  if (current.trim()) {\n"
        "    parts.push(current.trim());\n"
        "  }\n"
        "  return parts;\n"
        "}\n\n"
        "function __sampleEval(expression) {\n"
        "  return Function(`\"use strict\"; return (${expression});`)();\n"
        "}\n\n"
        "function __sampleParseArgs(rawInput, paramNames) {\n"
        "  const input = rawInput.trim();\n"
        "  if (!input) {\n"
        "    return [];\n"
        "  }\n"
        "  if (input.startsWith('{')) {\n"
        "    const payload = __sampleEval(input);\n"
        "    if (payload && typeof payload === 'object' && !Array.isArray(payload)) {\n"
        "      return paramNames.map((name) => payload[name]);\n"
        "    }\n"
        "  }\n"
        "  const parts = __sampleSplitTopLevel(input);\n"
        "  if (parts.every((part) => part.includes('='))) {\n"
        "    const values = Object.create(null);\n"
        "    for (const part of parts) {\n"
        "      const [name, expression] = part.split(/=(.+)/, 2);\n"
        "      values[name.trim()] = __sampleEval(expression.trim());\n"
        "    }\n"
        "    return paramNames.map((name) => values[name]);\n"
        "  }\n"
        "  if (paramNames.length <= 1) {\n"
        "    return [__sampleEval(input)];\n"
        "  }\n"
        "  return parts.map((part) => __sampleEval(part));\n"
        "}\n\n"
        "function __sampleFormat(value) {\n"
        "  if (typeof value === 'string') {\n"
        "    return value;\n"
        "  }\n"
        "  if (typeof value === 'number' || typeof value === 'boolean' || value == null) {\n"
        "    return String(value);\n"
        "  }\n"
        "  return JSON.stringify(value);\n"
        "}\n\n"
        "const __sampleInput = require('fs').readFileSync(0, 'utf8');\n"
        f"const __sampleArgs = __sampleParseArgs(__sampleInput, {encoded_param_names});\n"
        f"Promise.resolve({function_name}(...__sampleArgs))\n"
        "  .then((result) => {\n"
        "    process.stdout.write(__sampleFormat(result));\n"
        "  })\n"
        "  .catch((error) => {\n"
        "    console.error(error && error.stack ? error.stack : String(error));\n"
        "    process.exit(1);\n"
        "  });\n"
    )


def _to_frontend_language(language: str) -> str | None:
    return OJ_LANGUAGE_TO_FRONTEND.get(language)


def _to_oj_language(language: str) -> str:
    mapped = FRONTEND_LANGUAGE_TO_OJ.get(language)
    if not mapped:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    return mapped


def _load_freeproblemset_manifest_entries() -> list[dict[str, Any]]:
    if not FREEPROBLEMSET_MANIFEST_PATH.exists():
        return []
    try:
        payload = json.loads(FREEPROBLEMSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load freeproblemset manifest: %s", exc)
        return []

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("problems") or []
    else:
        entries = []
    return [entry for entry in entries if isinstance(entry, dict)]


def _load_freeproblemset_manifest_payload() -> dict[str, Any]:
    if not FREEPROBLEMSET_MANIFEST_PATH.exists():
        return {"packages": [], "problems": []}
    try:
        payload = json.loads(FREEPROBLEMSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load freeproblemset manifest payload: %s", exc)
        return {"packages": [], "problems": []}
    if isinstance(payload, dict):
        return {
            "packages": [item for item in (payload.get("packages") or []) if isinstance(item, dict)],
            "problems": [item for item in (payload.get("problems") or []) if isinstance(item, dict)],
        }
    if isinstance(payload, list):
        return {"packages": [], "problems": [item for item in payload if isinstance(item, dict)]}
    return {"packages": [], "problems": []}


def _build_freeproblemset_display_map() -> dict[str, list[dict[str, Any]]]:
    display_map: dict[str, list[dict[str, Any]]] = {}
    for entry in _load_freeproblemset_manifest_entries():
        display_ids = entry.get("oj_display_ids") or []
        if not isinstance(display_ids, list):
            continue
        for raw_display_id in display_ids:
            display_id = str(raw_display_id or "").strip()
            if not display_id:
                continue
            display_map.setdefault(display_id, []).append(entry)
    return display_map


def _normalize_repo_package_path(package_path: str) -> str:
    return str(package_path or "").replace("\\", "/").lstrip("./")


def _resolve_primary_position_tag(position_tags: list[str] | None) -> str:
    normalized = {str(tag or "").strip() for tag in (position_tags or [])}
    if "frontend" in normalized:
        return "frontend"
    if "backend" in normalized:
        return "backend"
    return GENERAL_POSITION_TAG


def _normalize_difficulty_tag(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in {"easy", "low", "简单", "初级"}:
        return "easy"
    if value in {"hard", "high", "困难", "高级"}:
        return "hard"
    if value in {"medium", "mid", "normal", "中等", "中级"}:
        return "medium"
    return "medium"


def _detect_statement_language(*parts: Any) -> str:
    text = "\n".join(_html_to_text(part) for part in parts if part)
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


def _map_fps_language_to_frontend(language: str) -> str | None:
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


def _parse_freeproblemset_xml_bytes(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    problems: list[dict[str, Any]] = []
    for item in root.findall("item"):
        problem = {
            "title": "",
            "description": "",
            "input_description": "",
            "output_description": "",
            "hint": "",
            "source": "",
            "examples": [],
            "starter_code": {},
            "allowed_languages": [],
        }
        example_state: dict[str, str] | None = None
        for child in item:
            tag = child.tag
            text = child.text or ""
            if tag == "title":
                problem["title"] = text
            elif tag == "description":
                problem["description"] = _html_to_text(text)
            elif tag == "input":
                problem["input_description"] = _html_to_text(text)
            elif tag == "output":
                problem["output_description"] = _html_to_text(text)
            elif tag == "hint":
                problem["hint"] = _html_to_text(text)
            elif tag == "source":
                problem["source"] = _html_to_text(text)
            elif tag == "sample_input":
                example_state = {"input": text, "output": ""}
                problem["examples"].append(example_state)
            elif tag == "sample_output":
                if example_state is None:
                    example_state = {"input": "", "output": text}
                    problem["examples"].append(example_state)
                else:
                    example_state["output"] = text
            elif tag in {"template", "append", "prepend"}:
                mapped_language = _map_fps_language_to_frontend(child.attrib.get("language", ""))
                if not mapped_language or mapped_language not in SUPPORTED_FRONTEND_LANGUAGES:
                    continue
                if tag == "template":
                    problem["starter_code"][mapped_language] = text
        allowed_languages = list(problem["starter_code"].keys())
        problem["allowed_languages"] = _dedupe_preserve_order(allowed_languages)
        summary_source = problem["hint"] or problem["description"] or problem["title"]
        problem["summary"] = summary_source[:180]
        problem["statement_language"] = _detect_statement_language(
            problem.get("title"),
            problem.get("description"),
            problem.get("input_description"),
            problem.get("output_description"),
            problem.get("hint"),
        )
        problem["difficulty_tag"] = _normalize_difficulty_tag(problem.get("difficulty_tag"))
        problem["examples"] = [
            {"input": _html_to_text(example.get("input")), "output": _html_to_text(example.get("output"))}
            for example in problem["examples"]
        ]
        problems.append(problem)
    return problems


def _load_freeproblemset_package_problems(package_path: str) -> list[dict[str, Any]]:
    normalized_path = _normalize_repo_package_path(package_path)
    absolute_path = FREEPROBLEMSET_REPO_DIR / normalized_path
    if not absolute_path.exists():
        return []
    if absolute_path.suffix.lower() == ".xml":
        return _parse_freeproblemset_xml_bytes(absolute_path.read_bytes())
    if absolute_path.suffix.lower() != ".zip":
        raise HTTPException(status_code=400, detail="Unsupported problem package type")

    problems: list[dict[str, Any]] = []
    with zipfile.ZipFile(absolute_path) as archive:
        for member in sorted(archive.namelist()):
            if member.endswith("/") or not member.lower().endswith(".xml"):
                continue
            problems.extend(_parse_freeproblemset_xml_bytes(archive.read(member)))
    return problems


def _load_cs_notes_curated_problems() -> list[dict[str, Any]]:
    if not CS_NOTES_CURATED_PROBLEMS_PATH.exists():
        return []
    try:
        payload = json.loads(CS_NOTES_CURATED_PROBLEMS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load CS-Notes curated problems: %s", exc)
        return []

    if not isinstance(payload, list):
        return []

    problems: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        position_tags = [
            str(tag).strip() for tag in (item.get("position_tags") or []) if str(tag or "").strip()
        ]
        normalized_item = {
            "package_path": _normalize_repo_package_path(item.get("package_path") or ""),
            "package_type": str(item.get("package_type") or "curated"),
            "package_sha": str(item.get("package_sha") or ""),
            "problem_index": int(item.get("problem_index") or 0),
            "title": str(item.get("title") or ""),
            "source": str(item.get("source") or ""),
            "summary": str(item.get("summary") or ""),
            "description": str(item.get("description") or ""),
            "input_description": str(item.get("input_description") or ""),
            "output_description": str(item.get("output_description") or ""),
            "examples": list(item.get("examples") or []),
            "starter_code": dict(item.get("starter_code") or {}),
            "allowed_languages": list(item.get("allowed_languages") or []),
            "statement_language": str(item.get("statement_language") or "zh"),
            "difficulty_tag": _normalize_difficulty_tag(item.get("difficulty_tag")),
            "topic_tags": [str(tag).strip() for tag in (item.get("topic_tags") or []) if str(tag or "").strip()],
            "position_tags": position_tags,
            "primary_position_tag": str(item.get("primary_position_tag") or "").strip()
            or _resolve_primary_position_tag(position_tags),
            "classifier": str(item.get("classifier") or "cs_notes_rule"),
            "imported_at": str(item.get("imported_at") or ""),
        }
        if normalized_item["package_path"]:
            problems.append(normalized_item)
    return problems


def _build_curated_problem_packages(problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    package_buckets: dict[str, dict[str, Any]] = {}
    for problem in problems:
        package_path = str(problem.get("package_path") or "").strip()
        if not package_path:
            continue
        bucket = package_buckets.setdefault(
            package_path,
            {
                "package_path": package_path,
                "package_type": str(problem.get("package_type") or "curated"),
                "package_sha": "",
                "problem_count": 0,
                "imported_problem_count": 0,
                "oj_problem_ids": [],
                "oj_display_ids": [],
                "imported_at": "",
                "updated_at": "",
                "classifier": str(problem.get("classifier") or "cs_notes_rule"),
                "position_tag_summary": {"frontend": 0, "backend": 0, GENERAL_POSITION_TAG: 0},
                "topic_tags": {},
            },
        )
        bucket["problem_count"] += 1
        bucket["imported_problem_count"] += 1
        for tag in problem.get("position_tags") or []:
            if tag in bucket["position_tag_summary"]:
                bucket["position_tag_summary"][tag] += 1
        for tag in problem.get("topic_tags") or []:
            bucket["topic_tags"][tag] = int(bucket["topic_tags"].get(tag) or 0) + 1

    packages = []
    for bucket in package_buckets.values():
        top_topics = sorted(
            bucket["topic_tags"].items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[:5]
        packages.append(
            {
                "package_path": bucket["package_path"],
                "package_type": bucket["package_type"],
                "package_sha": bucket["package_sha"],
                "problem_count": bucket["problem_count"],
                "imported_problem_count": bucket["imported_problem_count"],
                "oj_problem_ids": bucket["oj_problem_ids"],
                "oj_display_ids": bucket["oj_display_ids"],
                "imported_at": bucket["imported_at"],
                "updated_at": bucket["updated_at"],
                "classifier": bucket["classifier"],
                "position_tag_summary": bucket["position_tag_summary"],
                "top_topic_tags": [{"tag": tag, "count": count} for tag, count in top_topics],
            }
        )
    packages.sort(key=lambda item: str(item.get("package_path") or ""))
    return packages


def list_imported_problem_packages() -> dict[str, Any]:
    manifest = _load_freeproblemset_manifest_payload()
    packages = list(manifest.get("packages") or [])
    problems = list(manifest.get("problems") or [])
    curated_problems = _load_cs_notes_curated_problems()
    curated_packages = _build_curated_problem_packages(curated_problems)

    problem_counts_by_package: dict[str, dict[str, Any]] = {}
    for item in problems:
        package_path = str(item.get("package_path") or "").strip()
        if not package_path:
            continue
        bucket = problem_counts_by_package.setdefault(
            package_path,
            {
                "imported_problem_count": 0,
                "position_tags": {"frontend": 0, "backend": 0, GENERAL_POSITION_TAG: 0},
                "topic_tags": {},
            },
        )
        if item.get("imported_at"):
            bucket["imported_problem_count"] += 1
        for tag in item.get("position_tags") or []:
            if tag in bucket["position_tags"]:
                bucket["position_tags"][tag] += 1
        for tag in item.get("topic_tags") or []:
            bucket["topic_tags"][tag] = int(bucket["topic_tags"].get(tag) or 0) + 1

    imported_packages = []
    for package in packages:
        imported_at = str(package.get("imported_at") or "").strip()
        if not imported_at:
            continue
        package_path = str(package.get("package_path") or "").strip()
        counts = problem_counts_by_package.get(package_path) or {
            "imported_problem_count": 0,
            "position_tags": {"frontend": 0, "backend": 0, GENERAL_POSITION_TAG: 0},
            "topic_tags": {},
        }
        top_topics = sorted(
            counts["topic_tags"].items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )[:5]
        imported_packages.append(
            {
                "package_path": package_path,
                "package_type": package.get("package_type") or "xml",
                "package_sha": package.get("package_sha") or "",
                "problem_count": int(package.get("problem_count") or 0),
                "imported_problem_count": int(counts["imported_problem_count"] or 0),
                "oj_problem_ids": list(package.get("oj_problem_ids") or []),
                "oj_display_ids": list(package.get("oj_display_ids") or []),
                "imported_at": imported_at,
                "updated_at": package.get("updated_at") or "",
                "classifier": package.get("classifier") or "rule",
                "position_tag_summary": counts["position_tags"],
                "top_topic_tags": [{"tag": tag, "count": count} for tag, count in top_topics],
            }
        )

    imported_packages.sort(key=lambda item: str(item.get("imported_at") or ""), reverse=True)
    imported_problems = []
    for item in problems:
        imported_at = str(item.get("imported_at") or "").strip()
        if not imported_at:
            continue
        position_tags = [str(tag) for tag in (item.get("position_tags") or []) if str(tag or "").strip()]
        imported_problems.append(
            {
                "package_path": _normalize_repo_package_path(item.get("package_path") or ""),
                "package_type": item.get("package_type") or "xml",
                "package_sha": item.get("package_sha") or "",
                "problem_index": int(item.get("problem_index") or 0),
                "title": item.get("title") or "",
                "source": item.get("source") or "",
                "summary": item.get("summary") or "",
                "topic_tags": list(item.get("topic_tags") or []),
                "position_tags": position_tags,
                "primary_position_tag": _resolve_primary_position_tag(position_tags),
                "statement_language": str(
                    item.get("statement_language")
                    or _detect_statement_language(
                        item.get("title"),
                        item.get("description"),
                        item.get("input_description"),
                        item.get("output_description"),
                        item.get("summary"),
                    )
                ),
                "difficulty_tag": _normalize_difficulty_tag(item.get("difficulty_tag")),
                "allowed_languages": list(item.get("allowed_languages") or []),
                "oj_problem_ids": list(item.get("oj_problem_ids") or []),
                "oj_display_ids": list(item.get("oj_display_ids") or []),
                "imported_at": imported_at,
                "classifier": item.get("classifier") or "rule",
            }
        )

    imported_problems.sort(
        key=lambda item: (
            {"frontend": 0, "backend": 1, GENERAL_POSITION_TAG: 2}.get(item.get("primary_position_tag"), 3),
            -int(item.get("problem_index") or 0),
            str(item.get("title") or ""),
        )
    )
    imported_problems.extend(curated_problems)
    imported_problems.sort(
        key=lambda item: (
            {"frontend": 0, "backend": 1, GENERAL_POSITION_TAG: 2}.get(item.get("primary_position_tag"), 3),
            str(item.get("package_type") or ""),
            str(item.get("package_path") or ""),
            -int(item.get("problem_index") or 0),
            str(item.get("title") or ""),
        )
    )

    all_packages = imported_packages + curated_packages
    return {
        "packages": all_packages,
        "problems": imported_problems,
        "summary": {
            "imported_package_count": len(all_packages),
            "imported_problem_count": len(imported_problems),
            "tracked_package_count": len(packages) + len(curated_packages),
            "tracked_problem_count": len(problems) + len(curated_problems),
        },
    }


def get_problem_package_detail(package_path: str) -> dict[str, Any]:
    normalized_path = _normalize_repo_package_path(package_path)
    curated_problems = [
        problem
        for problem in _load_cs_notes_curated_problems()
        if _normalize_repo_package_path(problem.get("package_path") or "") == normalized_path
    ]
    if curated_problems:
        curated_packages = {
            item["package_path"]: item for item in _build_curated_problem_packages(curated_problems)
        }
        return {
            "package": curated_packages[normalized_path],
            "problems": [
                {
                    "problem_index": int(problem.get("problem_index") or 0),
                    "title": problem.get("title") or "",
                    "source": problem.get("source") or normalized_path,
                    "summary": problem.get("summary") or "",
                    "description": problem.get("description") or "",
                    "input_description": problem.get("input_description") or "",
                    "output_description": problem.get("output_description") or "",
                    "examples": list(problem.get("examples") or []),
                    "allowed_languages": list(problem.get("allowed_languages") or []),
                    "starter_code": dict(problem.get("starter_code") or {}),
                    "topic_tags": list(problem.get("topic_tags") or []),
                    "position_tags": list(problem.get("position_tags") or []),
                    "statement_language": str(problem.get("statement_language") or "zh"),
                    "difficulty_tag": _normalize_difficulty_tag(problem.get("difficulty_tag")),
                    "oj_problem_ids": [],
                    "oj_display_ids": [],
                    "imported_at": problem.get("imported_at") or "",
                }
                for problem in sorted(curated_problems, key=lambda item: int(item.get("problem_index") or 0))
            ],
        }

    manifest = _load_freeproblemset_manifest_payload()
    package = next(
        (
            item
            for item in (manifest.get("packages") or [])
            if _normalize_repo_package_path(item.get("package_path") or "") == normalized_path
        ),
        None,
    )
    if not package:
        raise HTTPException(status_code=404, detail="Problem package not found")

    manifest_problem_map = {
        int(item.get("problem_index") or 0): item
        for item in (manifest.get("problems") or [])
        if _normalize_repo_package_path(item.get("package_path") or "") == normalized_path
    }
    package_problems = _load_freeproblemset_package_problems(normalized_path)
    if not package_problems and not manifest_problem_map:
        raise HTTPException(status_code=404, detail="Problem package not found")
    problems = []
    max_problem_index = max(
        [*manifest_problem_map.keys(), *range(1, len(package_problems) + 1)],
        default=0,
    )
    for index in range(1, max_problem_index + 1):
        manifest_item = manifest_problem_map.get(index) or {}
        problem = package_problems[index - 1] if index - 1 < len(package_problems) else {}
        problems.append(
            {
                "problem_index": index,
                "title": manifest_item.get("title") or problem.get("title") or f"Problem {index}",
                "source": manifest_item.get("source") or problem.get("source") or normalized_path,
                "summary": manifest_item.get("summary") or problem.get("summary") or "",
                "description": manifest_item.get("description") or problem.get("description") or "",
                "input_description": manifest_item.get("input_description") or problem.get("input_description") or "",
                "output_description": manifest_item.get("output_description") or problem.get("output_description") or "",
                "examples": manifest_item.get("examples") or problem.get("examples") or [],
                "allowed_languages": manifest_item.get("allowed_languages") or problem.get("allowed_languages") or [],
                "starter_code": manifest_item.get("starter_code") or problem.get("starter_code") or {},
                "topic_tags": manifest_item.get("topic_tags") or [],
                "position_tags": manifest_item.get("position_tags") or [],
                "statement_language": manifest_item.get("statement_language")
                or problem.get("statement_language")
                or _detect_statement_language(
                    manifest_item.get("title") or problem.get("title"),
                    manifest_item.get("description") or problem.get("description"),
                    manifest_item.get("input_description") or problem.get("input_description"),
                    manifest_item.get("output_description") or problem.get("output_description"),
                ),
                "difficulty_tag": _normalize_difficulty_tag(
                    manifest_item.get("difficulty_tag") or problem.get("difficulty_tag")
                ),
                "oj_problem_ids": manifest_item.get("oj_problem_ids") or [],
                "oj_display_ids": manifest_item.get("oj_display_ids") or [],
                "imported_at": manifest_item.get("imported_at"),
            }
        )

    return {
        "package": {
            "package_path": normalized_path,
            "package_type": package.get("package_type") or "xml",
            "package_sha": package.get("package_sha") or "",
            "problem_count": int(package.get("problem_count") or len(problems)),
            "imported_at": package.get("imported_at") or "",
            "classifier": package.get("classifier") or "rule",
        },
        "problems": problems,
    }


def _build_practice_problem_ref(package_path: str, problem_index: int) -> str:
    raw = f"{_normalize_repo_package_path(package_path)}::{int(problem_index)}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _parse_practice_problem_ref(problem_ref: str) -> tuple[str, int]:
    normalized_ref = str(problem_ref or "").strip()
    if not normalized_ref:
        raise HTTPException(status_code=404, detail="Problem not found")

    padding = "=" * (-len(normalized_ref) % 4)
    try:
        decoded = base64.urlsafe_b64decode((normalized_ref + padding).encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=404, detail="Problem not found") from exc

    package_path, separator, problem_index_text = decoded.rpartition("::")
    if not separator or not package_path.strip():
        raise HTTPException(status_code=404, detail="Problem not found")
    try:
        problem_index = int(problem_index_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Problem not found") from exc
    if problem_index <= 0:
        raise HTTPException(status_code=404, detail="Problem not found")
    return _normalize_repo_package_path(package_path), problem_index


def _normalize_practice_topic_key(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "other"
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    return normalized or "other"


def _resolve_primary_topic_tag(topic_tags: list[str] | None) -> str:
    for tag in topic_tags or []:
        normalized = str(tag or "").strip()
        if normalized:
            return normalized
    return "其他"


def _serialize_practice_problem_summary(item: dict[str, Any]) -> dict[str, Any]:
    package_path = _normalize_repo_package_path(item.get("package_path") or "")
    problem_index = int(item.get("problem_index") or 0)
    title = str(item.get("title") or f"Problem {problem_index}").strip() or f"Problem {problem_index}"
    topic_tags = [str(tag).strip() for tag in (item.get("topic_tags") or []) if str(tag).strip()]
    primary_topic_tag = _resolve_primary_topic_tag(topic_tags)
    oj_problem_ids = [problem_id for problem_id in (item.get("oj_problem_ids") or []) if problem_id]
    return {
        "problem_ref": _build_practice_problem_ref(package_path, problem_index),
        "problem_index": problem_index,
        "package_path": package_path,
        "title": title,
        "summary": str(item.get("summary") or "").strip(),
        "difficulty_tag": _normalize_difficulty_tag(item.get("difficulty_tag")),
        "statement_language": str(item.get("statement_language") or "").strip() or "zh",
        "topic_tags": topic_tags,
        "primary_topic_tag": primary_topic_tag,
        "primary_topic_key": _normalize_practice_topic_key(primary_topic_tag),
        "allowed_languages": list(item.get("allowed_languages") or []),
        "oj_problem_ids": oj_problem_ids,
        "supports_online_judge": bool(oj_problem_ids),
    }


def get_practice_plan() -> dict[str, Any]:
    imported = list_imported_problem_packages()
    raw_problems = imported.get("problems") or []
    problems = [
        summary
        for item in raw_problems
        if (summary := _serialize_practice_problem_summary(item)).get("supports_online_judge")
    ]

    topic_groups: dict[str, dict[str, Any]] = {}
    for item in problems:
        topic_key = item["primary_topic_key"]
        topic_name = item["primary_topic_tag"]
        group = topic_groups.setdefault(
            topic_key,
            {
                "topic_key": topic_key,
                "topic_name": topic_name,
                "problem_count": 0,
                "problems": [],
            },
        )
        group["problem_count"] += 1
        group["problems"].append(item)

    topics = sorted(
        topic_groups.values(),
        key=lambda item: (-int(item["problem_count"]), str(item["topic_name"])),
    )
    for item in topics:
        item["problems"] = sorted(
            item["problems"],
            key=lambda problem: (
                {"easy": 0, "medium": 1, "hard": 2}.get(problem.get("difficulty_tag"), 1),
                str(problem.get("title") or ""),
                int(problem.get("problem_index") or 0),
            ),
        )

    return {
        "plan": {
            "key": "default",
            "title": "代码练习",
            "description": "从已导入题库中按专题分段练习，支持样例运行与在线判题。",
            "problem_count": len(problems),
            "topic_count": len(topics),
        },
        "topics": topics,
    }


def get_practice_problem_detail(problem_ref: str) -> dict[str, Any]:
    package_path, problem_index = _parse_practice_problem_ref(problem_ref)
    detail = get_problem_package_detail(package_path)
    problem = next(
        (item for item in (detail.get("problems") or []) if int(item.get("problem_index") or 0) == problem_index),
        None,
    )
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    summary = _serialize_practice_problem_summary(
        {
            **problem,
            "package_path": package_path,
            "problem_index": problem_index,
        }
    )
    return {
        "problem_ref": summary["problem_ref"],
        "problem_index": problem_index,
        "package_path": package_path,
        "package_name": Path(package_path).name,
        "title": summary["title"],
        "summary": str(problem.get("summary") or "").strip(),
        "description": str(problem.get("description") or "").strip(),
        "input_description": str(problem.get("input_description") or "").strip(),
        "output_description": str(problem.get("output_description") or "").strip(),
        "examples": list(problem.get("examples") or []),
        "allowed_languages": [
            language
            for language in (problem.get("allowed_languages") or [])
            if language in SUPPORTED_FRONTEND_LANGUAGES
        ],
        "starter_code": {
            language: str(code or "")
            for language, code in (problem.get("starter_code") or {}).items()
            if language in SUPPORTED_FRONTEND_LANGUAGES
        },
        "difficulty_tag": summary["difficulty_tag"],
        "statement_language": summary["statement_language"],
        "topic_tags": summary["topic_tags"],
        "primary_topic_tag": summary["primary_topic_tag"],
        "primary_topic_key": summary["primary_topic_key"],
        "oj_problem_ids": summary["oj_problem_ids"],
        "supports_online_judge": summary["supports_online_judge"],
    }


def _normalize_position_tag(target_position: str | None) -> str:
    normalized = str(get_problemset_tag_for_position(target_position) or "").strip().lower()
    if normalized in {"frontend", "backend"}:
        return normalized
    return GENERAL_POSITION_TAG


def _normalize_problem(problem_data: dict[str, Any]) -> OJProblem:
    display_id = str(problem_data.get("_id") or problem_data["id"])
    allowed_languages = _dedupe_preserve_order(
        [
            mapped
            for language in (problem_data.get("languages") or [])
            if (mapped := _to_frontend_language(str(language)))
        ]
    )
    starter_code = {
        mapped: code
        for language, code in (problem_data.get("template") or {}).items()
        if (mapped := _to_frontend_language(str(language)))
    }
    statement_language = _detect_statement_language(
        problem_data.get("title"),
        problem_data.get("description"),
        problem_data.get("input_description"),
        problem_data.get("output_description"),
        problem_data.get("hint"),
    )
    difficulty_tag = _normalize_difficulty_tag(problem_data.get("difficulty"))
    manifest_entries = _build_freeproblemset_display_map().get(display_id) or []
    if manifest_entries:
        difficulty_candidates = [
            _normalize_difficulty_tag(entry.get("difficulty_tag"))
            for entry in manifest_entries
        ]
        if difficulty_candidates:
            difficulty_rank = {"easy": 0, "medium": 1, "hard": 2}
            difficulty_tag = max(difficulty_candidates, key=lambda item: difficulty_rank.get(item, 1))
        statement_language = (
            next(
                (
                    str(entry.get("statement_language") or "").strip()
                    for entry in manifest_entries
                    if str(entry.get("statement_language") or "").strip()
                ),
                "",
            )
            or statement_language
        )
    return OJProblem(
        id=int(problem_data["id"]),
        display_id=display_id,
        title=str(problem_data.get("title") or ""),
        source=str(problem_data.get("source") or "QingdaoU OJ"),
        summary=_build_summary(problem_data),
        description=_html_to_text(problem_data.get("description")),
        input_description=_html_to_text(problem_data.get("input_description")),
        output_description=_html_to_text(problem_data.get("output_description")),
        examples=[
            {
                "input": _html_to_text(item.get("input")),
                "output": _html_to_text(item.get("output")),
            }
            for item in (problem_data.get("samples") or [])
        ],
        starter_code=starter_code,
        allowed_languages=allowed_languages,
        statement_language=statement_language,
        difficulty_tag=difficulty_tag,
    )


def _serialize_problem(problem: OJProblem) -> dict[str, Any]:
    return {
        "id": problem.display_id,
        "title": problem.title,
        "source": problem.source,
        "summary": problem.summary,
        "description": problem.description,
        "input_description": problem.input_description,
        "output_description": problem.output_description,
        "examples": problem.examples,
        "allowed_languages": problem.allowed_languages,
        "starter_code": problem.starter_code,
        "statement_language": problem.statement_language,
        "difficulty_tag": problem.difficulty_tag,
    }


# 非编程题目标题关键词，用于过滤数理化等非编程问题
_NON_CODING_TITLE_PATTERNS = [
    "物理", "化学", "数学", "磁通量", "磁场", "电场",
    "力学", "热学", "光学", "原子", "分子",
]


def _is_coding_problem(problem_data: dict[str, Any]) -> bool:
    """排除明显非编程的题目（物理/数学/化学等）。"""
    title = str(problem_data.get("title") or "")
    for pattern in _NON_CODING_TITLE_PATTERNS:
        if pattern in title:
            return False
    return True


def _filter_candidate_problem(problem_data: dict[str, Any], *, excluded_problem_ids: set[str]) -> bool:
    display_id = str(problem_data.get("_id") or "")
    numeric_id = str(problem_data.get("id") or "")
    languages = set(problem_data.get("languages") or [])

    if not languages.intersection(OJ_LANGUAGE_TO_FRONTEND):
        return False
    if display_id in excluded_problem_ids or numeric_id in excluded_problem_ids:
        return False
    if not _is_coding_problem(problem_data):
        return False
    return True


async def _list_candidate_problems(excluded_problem_ids: set[str]) -> list[dict[str, Any]]:
    results_cache: list[dict[str, Any]] = []
    scanned = 0
    offset = 0

    async with _get_oj_client() as client:
        while scanned < OJ_MAX_SCAN:
            page = await _oj_request(
                client,
                "GET",
                "problem",
                params={"limit": OJ_PAGE_LIMIT, "offset": offset},
            )
            results = page.get("results") or []
            if not results:
                break
            results_cache.extend(
                problem
                for problem in results
                if _filter_candidate_problem(problem, excluded_problem_ids=excluded_problem_ids)
            )
            scanned += len(results)
            offset += len(results)
            total = int(page.get("total") or 0)
            if offset >= total:
                break
    return results_cache


def _pick_candidate_bucket(
    candidates: list[dict[str, Any]],
    *,
    target_position: str | None,
    difficulty_level: str | None = None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    manifest_display_map = _build_freeproblemset_display_map()
    target_tag = _normalize_position_tag(target_position)
    target_difficulty = _normalize_difficulty_tag(difficulty_level) if str(difficulty_level or "").strip() else ""
    matching_position: list[dict[str, Any]] = []
    matching_general: list[dict[str, Any]] = []
    interview_seed: list[dict[str, Any]] = []
    remainder: list[dict[str, Any]] = []

    for candidate in candidates:
        display_id = str(candidate.get("_id") or candidate.get("id") or "").strip()
        source = str(candidate.get("source") or "")
        manifest_entries = manifest_display_map.get(display_id) or []
        candidate_difficulty = _normalize_difficulty_tag(candidate.get("difficulty"))
        if manifest_entries:
            position_tags = {
                str(tag).strip()
                for entry in manifest_entries
                for tag in (entry.get("position_tags") or [])
                if str(tag).strip()
            }
            manifest_difficulties = {
                _normalize_difficulty_tag(entry.get("difficulty_tag"))
                for entry in manifest_entries
            }
            effective_difficulty = next(iter(manifest_difficulties or {candidate_difficulty}), "medium")
            if target_tag in position_tags and (not target_difficulty or effective_difficulty == target_difficulty):
                matching_position.append(candidate)
                continue
            if GENERAL_POSITION_TAG in position_tags and (
                not target_difficulty or effective_difficulty == target_difficulty
            ):
                matching_general.append(candidate)
                continue
        if OJ_PROBLEM_SOURCE and source == OJ_PROBLEM_SOURCE and (
            not target_difficulty or candidate_difficulty == target_difficulty
        ):
            interview_seed.append(candidate)
        else:
            remainder.append(candidate)

    return matching_position or matching_general or interview_seed or remainder or candidates


async def _get_problem_detail(display_id: str) -> OJProblem:
    async with _get_oj_client() as client:
        problem_data = await _oj_request(client, "GET", "problem", params={"problem_id": display_id})
    return _normalize_problem(problem_data)


async def _pick_random_problem(
    excluded_problem_ids: list[str] | None = None,
    *,
    target_position: str | None = None,
    statement_language: str | None = None,
    difficulty_level: str | None = None,
) -> OJProblem:
    excluded = {str(item).strip() for item in (excluded_problem_ids or []) if str(item).strip()}
    candidates = _pick_candidate_bucket(
        await _list_candidate_problems(excluded),
        target_position=target_position,
        difficulty_level=difficulty_level,
    )
    if not candidates:
        raise HTTPException(
            status_code=500,
            detail="No suitable QingdaoU OJ problems found. Please import visible interview-seed or freeproblemset problems first.",
        )
    normalized_language = str(statement_language or "").strip().lower()
    if not normalized_language:
        problem_data = random.choice(candidates)
        return await _get_problem_detail(str(problem_data.get("_id") or problem_data.get("id")))

    shuffled_candidates = random.sample(candidates, k=len(candidates))
    for candidate in shuffled_candidates:
        problem = await _get_problem_detail(str(candidate.get("_id") or candidate.get("id")))
        if problem.statement_language == normalized_language:
            return problem

    raise HTTPException(
        status_code=500,
        detail=f"No suitable QingdaoU OJ problems found for statement_language={normalized_language}.",
    )


def _build_workbench_path(thread_id: str, target_position: str | None = None) -> str:
    position = (target_position or "").strip()
    suffix = f"&position={position}" if position else ""
    return f"{CODING_WORKBENCH_ROUTE}?threadId={thread_id}{suffix}"


def _result_code_to_status(result_code: int | str | None) -> str:
    if result_code is None:
        return "PENDING"
    try:
        numeric = int(result_code)
    except (TypeError, ValueError):
        # Non-integer result (e.g. "UNKNOWN" string from OJ) — treat as pending
        return "PENDING"
    return OJ_RESULT_CODE_MAP.get(numeric, f"UNKNOWN_{numeric}")


def _build_judge_result(submission_data: dict[str, Any]) -> dict[str, Any]:
    result_code = submission_data.get("result")
    judge_status = _result_code_to_status(result_code)
    statistic_info = submission_data.get("statistic_info") or {}
    info = submission_data.get("info") or {}
    compile_error = str(statistic_info.get("err_info") or "") if judge_status == "COMPILE_ERROR" else ""
    tests = []
    for item in info.get("data") or []:
        item_status = _result_code_to_status(item.get("result"))
        tests.append(
            {
                "name": f"test_case_{item.get('test_case')}",
                "status": item_status,
                "passed": item_status == "ACCEPTED",
                "message": item_status,
                "cpu_time": item.get("cpu_time"),
                "memory": item.get("memory"),
            }
        )
    return {
        "status": judge_status,
        "passed": judge_status == "ACCEPTED",
        "score": statistic_info.get("score", 100 if judge_status == "ACCEPTED" else 0),
        "message": statistic_info.get("err_info") or judge_status,
        "time_cost": statistic_info.get("time_cost"),
        "memory_cost": statistic_info.get("memory_cost"),
        "stdout": "",
        "stderr": "",
        "compile_error": compile_error,
        "tests": tests,
    }


async def _fetch_submission_data(submission_id: str) -> dict[str, Any]:
    async with _get_oj_client() as client:
        return await _oj_request(client, "GET", "submission", params={"id": submission_id})


def _resolve_default_language(problem: OJProblem) -> str:
    if DEFAULT_CODING_LANGUAGE in problem.allowed_languages:
        return DEFAULT_CODING_LANGUAGE
    if problem.allowed_languages:
        return problem.allowed_languages[0]
    return DEFAULT_CODING_LANGUAGE


def _build_initial_drafts(problem: OJProblem) -> dict[str, str]:
    drafts = {
        language: problem.starter_code.get(language, "")
        for language in problem.allowed_languages
        if language in SUPPORTED_FRONTEND_LANGUAGES
    }
    default_language = _resolve_default_language(problem)
    drafts.setdefault(default_language, problem.starter_code.get(default_language, ""))
    return drafts


def _normalize_coding_session_state(coding_session: dict[str, Any]) -> dict[str, Any]:
    session = dict(coding_session or {})
    problem = session.get("problem") if isinstance(session.get("problem"), dict) else {}
    allowed_languages = [
        language
        for language in (problem.get("allowed_languages") or [])
        if language in SUPPORTED_FRONTEND_LANGUAGES
    ]
    if not allowed_languages:
        current_language = str(session.get("language") or DEFAULT_CODING_LANGUAGE)
        if current_language in SUPPORTED_FRONTEND_LANGUAGES:
            allowed_languages = [current_language]
        else:
            allowed_languages = [DEFAULT_CODING_LANGUAGE]
    allowed_languages = _dedupe_preserve_order(allowed_languages)
    if problem:
        problem["allowed_languages"] = allowed_languages
        problem["starter_code"] = {
            language: str(code or "")
            for language, code in (problem.get("starter_code") or {}).items()
            if language in SUPPORTED_FRONTEND_LANGUAGES
        }
        session["problem"] = problem

    current_language = str(session.get("language") or "").strip()
    if current_language not in allowed_languages:
        current_language = allowed_languages[0]

    drafts = {
        language: str(code or "")
        for language, code in (session.get("drafts") or {}).items()
        if language in SUPPORTED_FRONTEND_LANGUAGES
    }
    starter_code = problem.get("starter_code") if isinstance(problem, dict) else {}
    for language in allowed_languages:
        drafts.setdefault(language, str((starter_code or {}).get(language) or ""))

    current_draft = str(session.get("draft_code") or "")
    if current_draft and not drafts.get(current_language):
        drafts[current_language] = current_draft

    session["language"] = current_language
    session["drafts"] = drafts
    session["draft_code"] = drafts.get(current_language, str((starter_code or {}).get(current_language) or ""))

    sample_run = session.get("sample_run") if isinstance(session.get("sample_run"), dict) else {}
    normalized_sample_run = _build_sample_run_state()
    normalized_sample_run.update({
        "status": str(sample_run.get("status") or normalized_sample_run["status"]),
        "passed": bool(sample_run.get("passed", normalized_sample_run["passed"])),
        "message": str(sample_run.get("message") or ""),
        "stdout": str(sample_run.get("stdout") or ""),
        "stderr": str(sample_run.get("stderr") or ""),
        "compile_error": str(sample_run.get("compile_error") or ""),
        "tests": list(sample_run.get("tests") or []),
        "ran_at": str(sample_run.get("ran_at") or ""),
    })
    session["sample_run"] = normalized_sample_run
    return session


async def _refresh_submission_if_needed(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    coding_session: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    submission_id = str(coding_session.get("submission_id") or "").strip()
    if not submission_id:
        return _normalize_coding_session_state(coding_session)

    judge_status = str(coding_session.get("judge_status") or "").strip()
    if not force and judge_status and judge_status not in PENDING_OJ_STATUSES:
        return _normalize_coding_session_state(coding_session)

    submission_data = await _fetch_submission_data(submission_id)
    coding_session = dict(coding_session)
    next_status = _result_code_to_status(submission_data.get("result"))
    coding_session["judge_status"] = next_status
    coding_session["judge_result"] = _build_judge_result(submission_data)
    coding_session["submitted_at"] = submission_data.get("create_time") or coding_session.get("submitted_at") or ""
    if next_status not in PENDING_OJ_STATUSES:
        coding_session["status"] = "submitted"
    return await save_coding_session(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
    )


async def _get_conversation_or_404(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
):
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_conversation_by_thread_id(thread_id)
    if not conversation or conversation.user_id != str(current_user_id) or conversation.status == "deleted":
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv_repo, conversation


def get_coding_session_from_metadata(metadata: dict | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    coding_session = metadata.get(CODING_SESSION_METADATA_KEY)
    if not isinstance(coding_session, dict):
        return None
    return _normalize_coding_session_state(coding_session)


async def save_coding_session(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    coding_session: dict[str, Any],
) -> dict[str, Any]:
    conv_repo, conversation = await _get_conversation_or_404(db, thread_id=thread_id, current_user_id=current_user_id)
    normalized_session = _normalize_coding_session_state(coding_session)
    metadata = dict(conversation.extra_metadata or {})
    metadata[CODING_SESSION_METADATA_KEY] = normalized_session
    await conv_repo.update_conversation(thread_id, metadata=metadata)
    return normalized_session


async def get_coding_session(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
) -> dict[str, Any]:
    _, conversation = await _get_conversation_or_404(db, thread_id=thread_id, current_user_id=current_user_id)
    coding_session = get_coding_session_from_metadata(conversation.extra_metadata)
    if not coding_session:
        raise HTTPException(status_code=404, detail="Coding session not found")
    return await _refresh_submission_if_needed(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
        force=False,
    )


async def find_coding_session(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
) -> dict[str, Any] | None:
    _, conversation = await _get_conversation_or_404(db, thread_id=thread_id, current_user_id=current_user_id)
    coding_session = get_coding_session_from_metadata(conversation.extra_metadata)
    if not coding_session:
        return None
    return await _refresh_submission_if_needed(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
        force=False,
    )


async def start_coding_session(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    target_position: str | None = None,
    excluded_problem_ids: list[str] | None = None,
    difficulty_level: str | None = None,
    statement_language: str | None = None,
) -> dict[str, Any]:
    problem = await _pick_random_problem(
        excluded_problem_ids,
        target_position=target_position,
        statement_language=statement_language,
        difficulty_level=difficulty_level,
    )
    language = _resolve_default_language(problem)
    drafts = _build_initial_drafts(problem)
    coding_session = {
        "status": "ready",
        "problem_id": problem.display_id,
        "problem_title": problem.title,
        "source": problem.source,
        "target_position": target_position or "",
        "difficulty_level": _normalize_difficulty_tag(difficulty_level) if str(difficulty_level or "").strip() else "",
        "language": language,
        "draft_code": drafts.get(language, ""),
        "drafts": drafts,
        "submission_id": "",
        "judge_status": "",
        "judge_result": {},
        "workbench_path": _build_workbench_path(thread_id, target_position),
        "started_at": _utc_now(),
        "submitted_at": "",
        "requested_hints": [],
        "sample_run": _build_sample_run_state(),
        "problem": _serialize_problem(problem),
        "oj_problem_pk": problem.id,
    }
    return await save_coding_session(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
    )


async def update_coding_draft(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    language: str,
    draft_code: str,
) -> dict[str, Any]:
    coding_session = await get_coding_session(db, thread_id=thread_id, current_user_id=current_user_id)
    allowed_languages = (coding_session.get("problem") or {}).get("allowed_languages") or SUPPORTED_FRONTEND_LANGUAGES
    if language not in SUPPORTED_FRONTEND_LANGUAGES or language not in allowed_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    coding_session["status"] = "coding"
    coding_session["language"] = language
    coding_session["draft_code"] = draft_code
    drafts = dict(coding_session.get("drafts") or {})
    drafts[language] = draft_code
    coding_session["drafts"] = drafts
    return await save_coding_session(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
    )


def _get_sample_run_limits(language: str) -> tuple[int, int]:
    if language == "c":
        return 3000, 256 * 1024 * 1024
    if language == "python":
        return 3000, 256 * 1024 * 1024
    if language == "javascript":
        return 3000, 512 * 1024 * 1024
    if language == "java":
        return 5000, 512 * 1024 * 1024
    return 5000, 512 * 1024 * 1024


async def run_sample_coding_session(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    language: str,
    code: str,
) -> dict[str, Any]:
    coding_session = await get_coding_session(db, thread_id=thread_id, current_user_id=current_user_id)
    problem = coding_session.get("problem") or {}
    allowed_languages = problem.get("allowed_languages") or SUPPORTED_FRONTEND_LANGUAGES
    if language not in SUPPORTED_FRONTEND_LANGUAGES or language not in allowed_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    examples = [
        {
            "input": str(item.get("input") or ""),
            "output": str(item.get("output") or ""),
        }
        for item in ((coding_session.get("problem") or {}).get("examples") or [])
        if str(item.get("input") or "").strip() or str(item.get("output") or "").strip()
    ]
    if not examples:
        raise HTTPException(status_code=400, detail="Current problem has no sample cases")

    language_config = JUDGE_SERVER_LANGUAGE_CONFIGS.get(language)
    if not language_config:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    max_cpu_time, max_memory = _get_sample_run_limits(language)
    sample_source = _build_seed_problem_sample_source(problem, language, code)
    judge_response = await _judge_server_request(
        {
            "language_config": language_config,
            "src": sample_source,
            "max_cpu_time": max_cpu_time,
            "max_memory": max_memory,
            "test_case": examples,
            "output": True,
            "io_mode": {"io_mode": "Standard IO"},
        }
    )
    sample_run = _build_sample_run_result(examples, judge_response)

    drafts = dict(coding_session.get("drafts") or {})
    drafts[language] = code
    coding_session.update(
        {
            "status": "coding",
            "language": language,
            "draft_code": code,
            "drafts": drafts,
            "sample_run": sample_run,
        }
    )
    return await save_coding_session(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
    )


async def submit_coding_session(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    language: str,
    code: str,
) -> dict[str, Any]:
    coding_session = await get_coding_session(db, thread_id=thread_id, current_user_id=current_user_id)
    allowed_languages = (coding_session.get("problem") or {}).get("allowed_languages") or SUPPORTED_FRONTEND_LANGUAGES
    if language not in SUPPORTED_FRONTEND_LANGUAGES or language not in allowed_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    oj_language = _to_oj_language(language)
    problem_pk = coding_session.get("oj_problem_pk")
    if not problem_pk:
        raise HTTPException(status_code=500, detail="Missing QingdaoU OJ problem id in coding session")

    async with _get_oj_client() as client:
        response = await _oj_request(
            client,
            "POST",
            "submission",
            json={
                "problem_id": int(problem_pk),
                "language": oj_language,
                "code": code,
            },
        )

    submission_id = str(response.get("submission_id") or "").strip()
    if not submission_id:
        raise HTTPException(status_code=502, detail="QingdaoU OJ did not return submission_id")

    drafts = dict(coding_session.get("drafts") or {})
    drafts[language] = code
    coding_session.update(
        {
            "status": "submitted",
            "language": language,
            "draft_code": code,
            "drafts": drafts,
            "submission_id": submission_id,
            "judge_status": "PENDING",
            "judge_result": {
                "status": "PENDING",
                "passed": False,
                "score": 0,
                "message": "Submission accepted by OJ, waiting for judge result",
                "tests": [],
            },
            "submitted_at": _utc_now(),
        }
    )
    return await save_coding_session(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
    )


async def get_submission_result(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    submission_id: str,
) -> dict[str, Any]:
    coding_session = await get_coding_session(db, thread_id=thread_id, current_user_id=current_user_id)
    if coding_session.get("submission_id") != submission_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    coding_session = await _refresh_submission_if_needed(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
        force=True,
    )
    return {
        "submission_id": submission_id,
        "judge_status": coding_session.get("judge_status", ""),
        "judge_result": coding_session.get("judge_result") or {},
        "submitted_at": coding_session.get("submitted_at", ""),
    }


def get_practice_session_from_metadata(metadata: dict | None) -> dict[str, Any] | None:
    if not isinstance(metadata, dict):
        return None
    practice_session = metadata.get(PRACTICE_SESSION_METADATA_KEY)
    if not isinstance(practice_session, dict):
        return None
    return _normalize_coding_session_state(practice_session)


async def _find_practice_conversation(
    db: AsyncSession,
    *,
    current_user_id: str,
    problem_ref: str,
):
    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_conversations(user_id=current_user_id, agent_id=PRACTICE_AGENT_ID)
    for conversation in conversations:
        if conversation.status == "deleted":
            continue
        session = get_practice_session_from_metadata(conversation.extra_metadata)
        if session and str(session.get("problem_ref") or "").strip() == problem_ref:
            return conv_repo, conversation, session
    return conv_repo, None, None


async def _get_practice_conversation_or_404(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
):
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_conversation_by_thread_id(session_id)
    if (
        not conversation
        or conversation.user_id != str(current_user_id)
        or conversation.status == "deleted"
        or conversation.agent_id != PRACTICE_AGENT_ID
    ):
        raise HTTPException(status_code=404, detail="Practice session not found")
    return conv_repo, conversation


async def save_practice_session(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
    practice_session: dict[str, Any],
) -> dict[str, Any]:
    conv_repo, conversation = await _get_practice_conversation_or_404(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
    )
    normalized_session = _normalize_coding_session_state(practice_session)
    normalized_session["session_id"] = session_id
    metadata = dict(conversation.extra_metadata or {})
    metadata[PRACTICE_SESSION_METADATA_KEY] = normalized_session
    metadata["practice_problem_ref"] = normalized_session.get("problem_ref") or ""
    await conv_repo.update_conversation(session_id, metadata=metadata)
    return normalized_session


async def _refresh_practice_submission_if_needed(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
    practice_session: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    submission_id = str(practice_session.get("submission_id") or "").strip()
    if not submission_id:
        normalized = _normalize_coding_session_state(practice_session)
        normalized["session_id"] = session_id
        return normalized

    judge_status = str(practice_session.get("judge_status") or "").strip()
    if not force and judge_status and judge_status not in PENDING_OJ_STATUSES:
        normalized = _normalize_coding_session_state(practice_session)
        normalized["session_id"] = session_id
        return normalized

    submission_data = await _fetch_submission_data(submission_id)
    next_session = dict(practice_session)
    next_status = _result_code_to_status(submission_data.get("result"))
    next_session["judge_status"] = next_status
    next_session["judge_result"] = _build_judge_result(submission_data)
    next_session["submitted_at"] = submission_data.get("create_time") or next_session.get("submitted_at") or ""
    if next_status not in PENDING_OJ_STATUSES:
        next_session["status"] = "submitted"
    return await save_practice_session(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
        practice_session=next_session,
    )


async def get_practice_session(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
) -> dict[str, Any]:
    _, conversation = await _get_practice_conversation_or_404(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
    )
    practice_session = get_practice_session_from_metadata(conversation.extra_metadata)
    if not practice_session:
        raise HTTPException(status_code=404, detail="Practice session not found")
    return await _refresh_practice_submission_if_needed(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
        practice_session=practice_session,
        force=False,
    )


async def start_practice_session(
    db: AsyncSession,
    *,
    problem_ref: str,
    current_user_id: str,
) -> dict[str, Any]:
    problem_detail = get_practice_problem_detail(problem_ref)
    conv_repo, conversation, existing_session = await _find_practice_conversation(
        db,
        current_user_id=current_user_id,
        problem_ref=problem_ref,
    )
    if conversation and existing_session:
        return await _refresh_practice_submission_if_needed(
            db,
            session_id=conversation.thread_id,
            current_user_id=current_user_id,
            practice_session=existing_session,
            force=False,
        )

    problem = OJProblem(
        id=int((problem_detail.get("problem_index") or 0)),
        display_id=str(problem_ref),
        title=str(problem_detail.get("title") or ""),
        source=str(problem_detail.get("package_name") or problem_detail.get("package_path") or ""),
        summary=str(problem_detail.get("summary") or ""),
        description=str(problem_detail.get("description") or ""),
        input_description=str(problem_detail.get("input_description") or ""),
        output_description=str(problem_detail.get("output_description") or ""),
        examples=list(problem_detail.get("examples") or []),
        starter_code=dict(problem_detail.get("starter_code") or {}),
        allowed_languages=list(problem_detail.get("allowed_languages") or []),
        statement_language=str(problem_detail.get("statement_language") or "zh"),
        difficulty_tag=str(problem_detail.get("difficulty_tag") or "medium"),
    )
    language = _resolve_default_language(problem)
    drafts = _build_initial_drafts(problem)
    conversation = await conv_repo.create_conversation(
        user_id=current_user_id,
        agent_id=PRACTICE_AGENT_ID,
        title=f"代码练习 · {problem.title}",
        metadata={"practice_problem_ref": problem_ref},
    )
    practice_session = {
        "session_id": conversation.thread_id,
        "status": "ready",
        "problem_ref": problem_ref,
        "problem_id": problem_ref,
        "problem_title": problem.title,
        "source": problem.source,
        "difficulty_level": problem.difficulty_tag,
        "language": language,
        "draft_code": drafts.get(language, ""),
        "drafts": drafts,
        "submission_id": "",
        "judge_status": "",
        "judge_result": {},
        "workbench_path": f"{PRACTICE_WORKBENCH_ROUTE}/{problem_ref}",
        "started_at": _utc_now(),
        "submitted_at": "",
        "requested_hints": [],
        "sample_run": _build_sample_run_state(),
        "problem": {
            **_serialize_problem(problem),
            "package_path": problem_detail.get("package_path") or "",
            "package_name": problem_detail.get("package_name") or "",
            "problem_index": int(problem_detail.get("problem_index") or 0),
            "topic_tags": list(problem_detail.get("topic_tags") or []),
            "primary_topic_key": str(problem_detail.get("primary_topic_key") or ""),
        },
        "oj_problem_pk": next(iter(problem_detail.get("oj_problem_ids") or []), None),
    }
    if not practice_session["oj_problem_pk"]:
        raise HTTPException(status_code=400, detail="Current problem is not linked to an OJ problem")
    return await save_practice_session(
        db,
        session_id=conversation.thread_id,
        current_user_id=current_user_id,
        practice_session=practice_session,
    )


async def update_practice_draft(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
    language: str,
    draft_code: str,
) -> dict[str, Any]:
    practice_session = await get_practice_session(db, session_id=session_id, current_user_id=current_user_id)
    allowed_languages = (practice_session.get("problem") or {}).get("allowed_languages") or SUPPORTED_FRONTEND_LANGUAGES
    if language not in SUPPORTED_FRONTEND_LANGUAGES or language not in allowed_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    practice_session["status"] = "coding"
    practice_session["language"] = language
    practice_session["draft_code"] = draft_code
    drafts = dict(practice_session.get("drafts") or {})
    drafts[language] = draft_code
    practice_session["drafts"] = drafts
    return await save_practice_session(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
        practice_session=practice_session,
    )


async def run_sample_practice_session(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
    language: str,
    code: str,
) -> dict[str, Any]:
    practice_session = await get_practice_session(db, session_id=session_id, current_user_id=current_user_id)
    problem = practice_session.get("problem") or {}
    allowed_languages = problem.get("allowed_languages") or SUPPORTED_FRONTEND_LANGUAGES
    if language not in SUPPORTED_FRONTEND_LANGUAGES or language not in allowed_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    examples = [
        {"input": str(item.get("input") or ""), "output": str(item.get("output") or "")}
        for item in (problem.get("examples") or [])
        if str(item.get("input") or "").strip() or str(item.get("output") or "").strip()
    ]
    if not examples:
        raise HTTPException(status_code=400, detail="Current problem has no sample cases")

    language_config = JUDGE_SERVER_LANGUAGE_CONFIGS.get(language)
    if not language_config:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")

    max_cpu_time, max_memory = _get_sample_run_limits(language)
    sample_source = _build_seed_problem_sample_source(problem, language, code)
    judge_response = await _judge_server_request(
        {
            "language_config": language_config,
            "src": sample_source,
            "max_cpu_time": max_cpu_time,
            "max_memory": max_memory,
            "test_case": examples,
            "output": True,
            "io_mode": {"io_mode": "Standard IO"},
        }
    )
    sample_run = _build_sample_run_result(examples, judge_response)

    drafts = dict(practice_session.get("drafts") or {})
    drafts[language] = code
    practice_session.update(
        {
            "status": "coding",
            "language": language,
            "draft_code": code,
            "drafts": drafts,
            "sample_run": sample_run,
        }
    )
    return await save_practice_session(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
        practice_session=practice_session,
    )


async def submit_practice_session(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
    language: str,
    code: str,
) -> dict[str, Any]:
    practice_session = await get_practice_session(db, session_id=session_id, current_user_id=current_user_id)
    allowed_languages = (practice_session.get("problem") or {}).get("allowed_languages") or SUPPORTED_FRONTEND_LANGUAGES
    if language not in SUPPORTED_FRONTEND_LANGUAGES or language not in allowed_languages:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    oj_language = _to_oj_language(language)
    problem_pk = practice_session.get("oj_problem_pk")
    if not problem_pk:
        raise HTTPException(status_code=500, detail="Missing QingdaoU OJ problem id in practice session")

    async with _get_oj_client() as client:
        response = await _oj_request(
            client,
            "POST",
            "submission",
            json={"problem_id": int(problem_pk), "language": oj_language, "code": code},
        )

    submission_id = str(response.get("submission_id") or "").strip()
    if not submission_id:
        raise HTTPException(status_code=502, detail="QingdaoU OJ did not return submission_id")

    drafts = dict(practice_session.get("drafts") or {})
    drafts[language] = code
    practice_session.update(
        {
            "status": "submitted",
            "language": language,
            "draft_code": code,
            "drafts": drafts,
            "submission_id": submission_id,
            "judge_status": "PENDING",
            "judge_result": {
                "status": "PENDING",
                "passed": False,
                "score": 0,
                "message": "Submission accepted by OJ, waiting for judge result",
                "tests": [],
            },
            "submitted_at": _utc_now(),
        }
    )
    return await save_practice_session(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
        practice_session=practice_session,
    )


async def get_practice_submission_result(
    db: AsyncSession,
    *,
    session_id: str,
    current_user_id: str,
    submission_id: str,
) -> dict[str, Any]:
    practice_session = await get_practice_session(db, session_id=session_id, current_user_id=current_user_id)
    if practice_session.get("submission_id") != submission_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    practice_session = await _refresh_practice_submission_if_needed(
        db,
        session_id=session_id,
        current_user_id=current_user_id,
        practice_session=practice_session,
        force=True,
    )
    return {
        "submission_id": submission_id,
        "judge_status": practice_session.get("judge_status", ""),
        "judge_result": practice_session.get("judge_result") or {},
        "submitted_at": practice_session.get("submitted_at", ""),
    }


async def request_coding_hint(
    db: AsyncSession,
    *,
    thread_id: str,
    current_user_id: str,
    question: str,
    draft_code: str,
) -> dict[str, Any]:
    coding_session = await get_coding_session(db, thread_id=thread_id, current_user_id=current_user_id)
    problem = coding_session.get("problem") or {}
    from src.agents.interview_agent.context import InterviewContext

    context = InterviewContext.from_file(module_name="interview_agent")
    current_language = str(coding_session.get("language") or DEFAULT_CODING_LANGUAGE)
    prompt = (
        "你是一名模拟面试中的代码考核提示助手。"
        "只能给方向性提示，不要直接给出完整答案，也不要输出可直接提交的完整代码。\n\n"
        f"岗位方向：{coding_session.get('target_position') or '未指定'}\n"
        f"题目：{problem.get('title') or coding_session.get('problem_title') or ''}\n"
        f"题目摘要：{problem.get('summary') or ''}\n"
        f"候选人问题：{question}\n"
        f"当前代码：\n```{FRONTEND_LANGUAGE_TO_FENCE.get(current_language, current_language)}\n{draft_code}\n```\n\n"
        "请输出 2-4 条简洁提示，优先指出思路、关键 API、常见错误和下一步检查点。"
    )
    model = select_model(model_spec=context.model)
    response = await model.call(
        [
            {"role": "system", "content": "你是专业、克制的代码面试提示助手。"},
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )
    hint = (response.content or "").strip()
    requested_hints = list(coding_session.get("requested_hints") or [])
    requested_hints.append({"question": question, "hint": hint, "created_at": _utc_now()})
    coding_session["requested_hints"] = requested_hints[-10:]
    drafts = dict(coding_session.get("drafts") or {})
    drafts[current_language] = draft_code
    coding_session["drafts"] = drafts
    coding_session["draft_code"] = draft_code
    await save_coding_session(
        db,
        thread_id=thread_id,
        current_user_id=current_user_id,
        coding_session=coding_session,
    )
    return {"hint": hint, "history": coding_session["requested_hints"]}


async def start_coding_session_from_tool(
    *,
    thread_id: str,
    user_id: str,
    target_position: str | None = None,
    excluded_problem_ids: list[str] | None = None,
    difficulty_level: str | None = None,
) -> dict[str, Any]:
    async with pg_manager.get_async_session_context() as db:
        session = await start_coding_session(
            db,
            thread_id=thread_id,
            current_user_id=str(user_id),
            target_position=target_position,
            excluded_problem_ids=excluded_problem_ids,
            difficulty_level=difficulty_level,
            statement_language="zh",
        )
        return {
            "status": session["status"],
            "problem_id": session["problem_id"],
            "problem_title": session["problem_title"],
            "summary": session["problem"]["summary"],
            "workbench_path": session["workbench_path"],
            "source": session["source"],
            "difficulty_level": session.get("difficulty_level") or session["problem"].get("difficulty_tag") or "medium",
        }
