from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import requests

PROBLEM_SET_PATH = Path(__file__).resolve().parents[1] / "src" / "config" / "static" / "interview_coding_problems.json"
DEFAULT_BASE_URL = os.getenv("OJ_ADMIN_BASE_URL", "http://localhost:8088").rstrip("/")
OJ_USERNAME = os.getenv("OJ_USERNAME", "root")
OJ_PASSWORD = os.getenv("OJ_PASSWORD", "rootroot")

TEMPLATE_BASE = """//PREPEND BEGIN
{prepend}
//PREPEND END

//TEMPLATE BEGIN
{template}
//TEMPLATE END

//APPEND BEGIN
{append}
//APPEND END"""

PROBLEM_OJ_CONFIG = {
    "two-sum-index": {
        "description": (
            "<p>请实现 <code>twoSum(nums, target)</code>，返回两个和为 <code>target</code> 的元素下标。</p>"
            "<p>评测时标准输入为一行 JSON，例如：<code>{\"nums\":[2,7,11,15],\"target\":9}</code>。</p>"
        ),
        "input_description": "<p>输入为一个 JSON 对象，包含 <code>nums</code> 数组和 <code>target</code> 整数。</p>",
        "output_description": "<p>输出一个 JSON 数组，如 <code>[0,1]</code>。</p>",
        "samples": [
            {"input": '{"nums":[2,7,11,15],"target":9}', "output": "[0,1]"},
            {"input": '{"nums":[3,2,4],"target":6}', "output": "[1,2]"},
        ],
        "test_cases": [
            ('{"nums":[2,7,11,15],"target":9}', "[0,1]"),
            ('{"nums":[3,2,4],"target":6}', "[1,2]"),
            ('{"nums":[3,3],"target":6}', "[0,1]"),
            ('{"nums":[1,5,3,7],"target":8}', "[0,3]"),
        ],
        "template": """function twoSum(nums, target) {
  // TODO
  return []
}""",
        "answer": """function twoSum(nums, target) {
  const seen = new Map()
  for (let index = 0; index < nums.length; index += 1) {
    const value = nums[index]
    const complement = target - value
    if (seen.has(complement)) {
      return [seen.get(complement), index]
    }
    seen.set(value, index)
  }
  return []
}""",
        "append": """const fs = require("fs")

const raw = fs.readFileSync(0, "utf8").trim()
const payload = raw ? JSON.parse(raw) : { nums: [], target: 0 }
const result = twoSum(payload.nums, payload.target)
process.stdout.write(JSON.stringify(result))""",
    },
    "valid-parentheses": {
        "description": (
            "<p>请实现 <code>isValid(s)</code>，判断括号字符串是否有效闭合。</p>"
            "<p>评测时标准输入为一行 JSON，例如：<code>{\"s\":\"()[]{}\"}</code>。</p>"
        ),
        "input_description": "<p>输入为一个 JSON 对象，包含字符串字段 <code>s</code>。</p>",
        "output_description": "<p>输出 <code>true</code> 或 <code>false</code>。</p>",
        "samples": [
            {"input": '{"s":"()[]{}"}', "output": "true"},
            {"input": '{"s":"([)]"}', "output": "false"},
        ],
        "test_cases": [
            ('{"s":"()[]{}"}', "true"),
            ('{"s":"([)]"}', "false"),
            ('{"s":"{[]}"}', "true"),
            ('{"s":"((("}', "false"),
        ],
        "template": """function isValid(s) {
  // TODO
  return false
}""",
        "answer": """function isValid(s) {
  const pairs = {
    ")": "(",
    "]": "[",
    "}": "{"
  }
  const stack = []
  for (const char of s) {
    if (!pairs[char]) {
      stack.push(char)
      continue
    }
    if (stack.pop() !== pairs[char]) {
      return false
    }
  }
  return stack.length === 0
}""",
        "append": """const fs = require("fs")

const raw = fs.readFileSync(0, "utf8").trim()
const payload = raw ? JSON.parse(raw) : { s: "" }
process.stdout.write(String(isValid(payload.s)))""",
    },
    "max-subarray": {
        "description": (
            "<p>请实现 <code>maxSubArray(nums)</code>，返回连续子数组的最大和。</p>"
            "<p>评测时标准输入为一行 JSON，例如：<code>{\"nums\":[-2,1,-3,4,-1,2,1,-5,4]}</code>。</p>"
        ),
        "input_description": "<p>输入为一个 JSON 对象，包含整数数组字段 <code>nums</code>。</p>",
        "output_description": "<p>输出一个整数。</p>",
        "samples": [
            {"input": '{"nums":[-2,1,-3,4,-1,2,1,-5,4]}', "output": "6"},
        ],
        "test_cases": [
            ('{"nums":[-2,1,-3,4,-1,2,1,-5,4]}', "6"),
            ('{"nums":[1]}', "1"),
            ('{"nums":[5,4,-1,7,8]}', "23"),
            ('{"nums":[-1,-2,-3]}', "-1"),
        ],
        "template": """function maxSubArray(nums) {
  // TODO
  return 0
}""",
        "answer": """function maxSubArray(nums) {
  let current = nums[0]
  let best = nums[0]
  for (let index = 1; index < nums.length; index += 1) {
    current = Math.max(nums[index], current + nums[index])
    best = Math.max(best, current)
  }
  return best
}""",
        "append": """const fs = require("fs")

const raw = fs.readFileSync(0, "utf8").trim()
const payload = raw ? JSON.parse(raw) : { nums: [] }
process.stdout.write(String(maxSubArray(payload.nums)))""",
    },
}


def build_template(prepend: str, template: str, append: str) -> str:
    return TEMPLATE_BASE.format(prepend=prepend.strip(), template=template.strip(), append=append.strip())


def load_seed_problems() -> list[dict]:
    return json.loads(PROBLEM_SET_PATH.read_text(encoding="utf-8-sig"))


def login(session: requests.Session) -> None:
    profile = session.get(f"{DEFAULT_BASE_URL}/api/profile", timeout=30)
    profile.raise_for_status()
    csrf_token = session.cookies.get("csrftoken", "")
    headers = {"X-CSRFToken": csrf_token} if csrf_token else {}
    response = session.post(
        f"{DEFAULT_BASE_URL}/api/login",
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


def problem_exists(session: requests.Session, display_id: str) -> bool:
    response = session.get(f"{DEFAULT_BASE_URL}/api/problem", params={"problem_id": display_id}, timeout=30)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    payload = response.json()
    return payload.get("error") is None and bool(payload.get("data"))


def build_test_case_zip(test_cases: list[tuple[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (test_input, test_output) in enumerate(test_cases, start=1):
            archive.writestr(f"{index}.in", test_input)
            archive.writestr(f"{index}.out", test_output)
    return buffer.getvalue()


def upload_test_cases(session: requests.Session, test_cases: list[tuple[str, str]]) -> dict:
    archive = build_test_case_zip(test_cases)
    response = session.post(
        f"{DEFAULT_BASE_URL}/api/admin/test_case",
        data={"spj": "false"},
        files={"file": ("test_cases.zip", io.BytesIO(archive), "application/zip")},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"Test case upload failed: {payload}")
    return payload["data"]


def build_problem_payload(problem: dict, upload_data: dict) -> dict:
    config = PROBLEM_OJ_CONFIG[problem["id"]]
    info = upload_data["info"]
    return {
        "_id": problem["id"],
        "title": problem["title"],
        "description": config["description"],
        "input_description": config["input_description"],
        "output_description": config["output_description"],
        "samples": config["samples"],
        "test_case_id": upload_data["id"],
        "test_case_score": [
            {
                "input_name": item["input_name"],
                "output_name": item["output_name"],
                "score": 100,
            }
            for item in info
        ],
        "time_limit": 1000,
        "memory_limit": 128,
        "languages": ["JavaScript"],
        "template": {
            "JavaScript": build_template("", config["template"], config["append"]),
        },
        "rule_type": "ACM",
        "io_mode": {"io_mode": "Standard IO", "input": "input.txt", "output": "output.txt"},
        "spj": False,
        "spj_language": None,
        "spj_code": None,
        "spj_compile_ok": False,
        "visible": True,
        "difficulty": "Mid",
        "tags": ["interview", "javascript"],
        "hint": problem.get("summary") or "",
        "source": problem.get("source") or "interview-seed",
        "share_submission": False,
    }


def create_problem(session: requests.Session, payload: dict) -> None:
    response = session.post(
        f"{DEFAULT_BASE_URL}/api/admin/problem",
        json=payload,
        headers=csrf_headers(session),
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("error"):
        raise RuntimeError(f"Create problem failed: {body}")


def main() -> None:
    session = requests.Session()
    login(session)

    problems = load_seed_problems()
    imported = 0
    skipped = 0

    for problem in problems:
        config = PROBLEM_OJ_CONFIG.get(problem["id"])
        if not config:
            raise RuntimeError(f"Missing OJ config for problem: {problem['id']}")
        if problem_exists(session, problem["id"]):
            skipped += 1
            print(f"Skip existing problem: {problem['id']}")
            continue

        upload_data = upload_test_cases(session, config["test_cases"])
        payload = build_problem_payload(problem, upload_data)
        create_problem(session, payload)
        imported += 1
        print(f"Imported problem: {problem['id']}")

    print(f"Done. imported={imported}, skipped={skipped}")


if __name__ == "__main__":
    main()
