from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont


ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
TMP_DIR = ROOT_DIR / "tmp"
OUTPUT_ROOT = ROOT_DIR / "output" / "e2e_interview_runs"

API_HOST = "127.0.0.1"
API_PORT = 5052
WEB_HOST = "127.0.0.1"
WEB_PORT = 5174

API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
WEB_BASE_URL = f"http://{WEB_HOST}:{WEB_PORT}"

DB_PATH = TMP_DIR / "e2e_interview.sqlite3"
DB_URL = "sqlite+aiosqlite:///./tmp/e2e_interview.sqlite3"

RESUME_FILENAME = "candidate_backend_resume.md"

RESUME_MARKDOWN = """# 候选人简历

## 基本信息
- 姓名：陈一鸣
- 目标岗位：Java后端开发工程师
- 工作年限：3年

## 技能栈
- Java / Spring Boot / Spring Cloud
- MySQL / Redis / Elasticsearch
- RabbitMQ / Kafka
- Docker / Linux / GitLab CI

## 项目经历
### 订单中心重构
- 负责将单体订单服务拆分为订单、库存、支付三个服务，峰值 QPS 提升约 40%
- 设计了幂等下单、防重支付、延迟关单和库存回滚机制
- 通过 Redis + Lua 处理热点库存扣减，减少并发下超卖

### 搜索推荐平台
- 使用 Elasticsearch 搭建搜索能力，支持多条件筛选和聚合统计
- 对慢查询进行排查，优化索引结构与查询 DSL，P95 响应时间从 1.2s 降到 300ms

## 自我评价
- 擅长把业务流程抽象成清晰的服务边界
- 表达偏务实，能说明取舍，但有时总结不够精炼
"""

RESUME_SUMMARY = {
    "basic_info": {
        "name": "陈一鸣",
        "years_of_experience": "3年",
        "current_role": "后端开发工程师",
    },
    "job_preference": {
        "job_intention": "Java后端开发",
    },
    "skills": {
        "backend": ["Java", "Spring Boot", "Spring Cloud"],
        "database": ["MySQL", "Redis", "Elasticsearch"],
        "middleware": ["RabbitMQ", "Kafka"],
        "engineering": ["Docker", "GitLab CI", "Linux"],
    },
    "project_experience": [
        {
            "name": "订单中心重构",
            "description": "负责拆分订单服务，设计幂等、延迟关单和库存回滚机制。",
            "tech_stack": ["Java", "Spring Boot", "Redis", "RabbitMQ", "MySQL"],
        },
        {
            "name": "搜索推荐平台",
            "description": "负责 Elasticsearch 搜索能力和慢查询优化。",
            "tech_stack": ["Java", "Elasticsearch", "MySQL"],
        },
    ],
}


ROUNDS = [
    {
        "position": "Java后端开发",
        "round": "初试",
        "answers": [
            (
                "你好，我叫陈一鸣，做了三年 Java 后端，最近两年主要负责订单和交易链路。"
                "我比较熟悉 Spring Boot、MySQL、Redis，也做过服务拆分、库存一致性和消息队列相关的设计。"
            ),
            (
                "我最近做得最完整的项目是订单中心重构。最难的是高并发下的库存一致性和支付幂等，"
                "我当时把下单、扣库存、支付状态流转拆开，用 Redis Lua 先做热点库存预扣，"
                "再结合消息补偿和延迟关单兜底。"
            ),
            (
                "如果问 Redis 和 MySQL 一致性，我通常会先明确场景。像库存这种核心数据，"
                "最终还是以 MySQL 为准，Redis 更适合承载热点读和短周期状态；"
                "更新时我更倾向于先落库再删缓存，复杂链路配合消息重试和监控告警。"
            ),
            "这轮我先回答到这里。如果你判断信息已经足够，请直接结束这轮面试并给我简短反馈，我这次先不进入代码考核。",
        ],
    },
    {
        "position": "Java后端开发",
        "round": "复试",
        "answers": [
            (
                "如果让我再介绍一次，我会更强调业务结果。"
                "我参与的几个核心项目都跟交易稳定性有关，"
                "我的优势是能把复杂业务拆成清晰模块，但我也知道自己在架构表达上还可以更系统一些。"
            ),
            (
                "关于系统设计，我会先看流量峰值、是否要求强一致、是否有异步容忍空间，"
                "再决定是同步事务、最终一致性还是事件驱动。"
                "比如订单、库存、支付联动时，我会把关键状态机和失败补偿路径先画清楚。"
            ),
            (
                "如果要排查慢查询，我一般先分层定位：先看接口耗时，再看 SQL、索引命中、执行计划和热点参数。"
                "以前我做 ES 搜索优化时，就发现问题不是机器不够，而是查询条件设计不合理导致回表和聚合成本太高。"
            ),
            "这一轮也先到这里。请直接给我本轮总结和口头反馈，不进入代码考核。",
        ],
    },
]


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_path: Path


def now_label() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def print_step(message: str) -> None:
    print(f"[E2E] {message}", flush=True)


def ensure_clean_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


def start_process(name: str, command: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> ManagedProcess:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    return ManagedProcess(name=name, process=process, log_path=log_path)


def stop_process(managed: ManagedProcess | None) -> None:
    if managed is None or managed.process.poll() is not None:
        return

    managed.process.terminate()
    try:
        managed.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        managed.process.kill()
        managed.process.wait(timeout=5)


def wait_for_http_ready(
    client: httpx.Client,
    url: str,
    *,
    timeout_seconds: int,
    process: ManagedProcess,
) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        if process.process.poll() is not None:
            raise RuntimeError(f"{process.name} 已退出，请查看日志：{process.log_path}")
        try:
            response = client.get(url, timeout=5.0)
            if response.status_code < 500:
                return
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"{process.name} 启动超时，最后错误：{last_error}，日志：{process.log_path}")


def load_admin_credentials() -> tuple[str, str]:
    admin_name = os.getenv("AI_INTERVIEW_SUPER_ADMIN_NAME", "").strip()
    admin_password = os.getenv("AI_INTERVIEW_SUPER_ADMIN_PASSWORD", "").strip()
    if not admin_name or not admin_password:
        raise RuntimeError("缺少 AI_INTERVIEW_SUPER_ADMIN_NAME 或 AI_INTERVIEW_SUPER_ADMIN_PASSWORD 环境变量")
    return admin_name, admin_password


def initialize_admin(client: httpx.Client) -> dict[str, Any]:
    admin_name, admin_password = load_admin_credentials()
    response = client.get("/api/auth/check-first-run")
    response.raise_for_status()
    first_run = response.json().get("first_run", False)

    if first_run:
        init_response = client.post(
            "/api/auth/initialize",
            json={"user_id": admin_name, "password": admin_password},
        )
        init_response.raise_for_status()
        return init_response.json()

    login_response = client.post(
        "/api/auth/token",
        data={"username": admin_name, "password": admin_password},
    )
    login_response.raise_for_status()
    return login_response.json()


def seed_resume(*, user_id: int, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / RESUME_FILENAME
    markdown_path.write_text(RESUME_MARKDOWN, encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id FROM user_resume_items WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if existing:
            return int(existing["id"])

        now = datetime.now().isoformat(timespec="seconds")
        cursor = conn.execute(
            """
            INSERT INTO user_resume_items (
                user_id,
                filename,
                content_hash,
                file_size,
                bucket_name,
                object_name,
                file_url,
                parser_name,
                markdown_content,
                summary_json,
                summary_status,
                summary_error,
                target_job_id,
                detected_position,
                match_result,
                match_status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                RESUME_FILENAME,
                uuid4().hex,
                len(RESUME_MARKDOWN.encode("utf-8")),
                "local-e2e",
                RESUME_FILENAME,
                f"file://{markdown_path.as_posix()}",
                "local_e2e_seed",
                RESUME_MARKDOWN,
                json.dumps(RESUME_SUMMARY, ensure_ascii=False),
                "completed",
                None,
                None,
                "Java后端开发",
                None,
                "none",
                now,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def stream_chat(
    client: httpx.Client,
    *,
    agent_id: str,
    token: str,
    thread_id: str,
    resume_id: int,
    position: str,
    interview_round: str,
    query: str,
) -> dict[str, Any]:
    payload = {
        "query": query,
        "config": {
            "thread_id": thread_id,
            "selected_resume_id": resume_id,
            "target_position": position,
            "interview_round": interview_round,
        },
        "meta": {"request_id": uuid4().hex},
    }
    headers = {"Authorization": f"Bearer {token}"}
    full_response = []
    chunks = []
    agent_states = []

    with client.stream("POST", f"/api/chat/agent/{agent_id}", json=payload, headers=headers, timeout=180.0) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            chunks.append(chunk)
            if chunk.get("status") == "loading" and chunk.get("response"):
                full_response.append(str(chunk["response"]))
            if chunk.get("status") == "agent_state":
                agent_states.append(chunk.get("agent_state") or {})

    return {
        "query": query,
        "assistant_reply": "".join(full_response).strip(),
        "chunks": chunks,
        "agent_states": agent_states,
    }


def create_thread(
    client: httpx.Client,
    *,
    agent_id: str,
    token: str,
    title: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/api/chat/thread",
        json={"agent_id": agent_id, "title": title, "metadata": metadata},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()


def finalize_round(
    client: httpx.Client,
    *,
    token: str,
    thread_id: str,
    position: str,
    interview_round: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/interview/{thread_id}/result/finalize",
        json={
            "target_position": position,
            "interview_round": interview_round,
            "force": True,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()


def fetch_personalized_path(client: httpx.Client, *, token: str) -> dict[str, Any]:
    response = client.get(
        "/api/interview/personalized-path",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def normalize_score(result_payload: dict[str, Any]) -> int | None:
    scorecard = (result_payload.get("result") or {}).get("scorecard") or {}
    for key in ("overall", "overall_score", "total_score"):
        value = scorecard.get(key)
        if value is None:
            continue
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            continue
    return None


def build_result_summary(result_payload: dict[str, Any]) -> dict[str, Any]:
    result = result_payload.get("result") or {}
    scorecard = result.get("scorecard") or {}
    improvement_plan = result.get("improvement_plan") or {}
    action_plan = (improvement_plan.get("action_plan") or {}).get("steps") or []
    highlights = result.get("report_highlights") or []

    return {
        "overall_score": normalize_score(result_payload),
        "strengths": list(scorecard.get("strengths") or [])[:3],
        "risks": list(scorecard.get("risks") or [])[:3],
        "suggestions": list(scorecard.get("suggestions") or [])[:3],
        "action_steps": [
            {
                "title": step.get("title"),
                "objective": step.get("objective"),
                "estimated_minutes": step.get("estimated_minutes"),
            }
            for step in action_plan[:3]
        ],
        "report_highlights": [
            {
                "title": item.get("title"),
                "summary": item.get("summary"),
                "tone": item.get("tone"),
            }
            for item in highlights[:3]
        ],
        "summary_markdown": result.get("summary_markdown", ""),
    }


def run_round(
    client: httpx.Client,
    *,
    agent_id: str,
    token: str,
    resume_id: int,
    round_config: dict[str, Any],
) -> dict[str, Any]:
    position = str(round_config["position"])
    interview_round = str(round_config["round"])
    title = f"{position} · {interview_round}"
    thread = create_thread(
        client,
        agent_id=agent_id,
        token=token,
        title=title,
        metadata={
            "interview_mode": "text",
            "target_position": position,
            "interview_round": interview_round,
            "resume_id": resume_id,
        },
    )
    thread_id = thread["id"]
    conversation = []

    opening_prompt = (
        f"现在开始一轮{position}{interview_round}模拟面试。"
        "请基于当前岗位设定与系统已注入的简历上下文，直接开始本轮面试。"
        "先完成开场引导并请候选人做简短自我介绍。"
    )
    conversation.append(
        stream_chat(
            client,
            agent_id=agent_id,
            token=token,
            thread_id=thread_id,
            resume_id=resume_id,
            position=position,
            interview_round=interview_round,
            query=opening_prompt,
        )
    )

    for answer in round_config["answers"]:
        conversation.append(
            stream_chat(
                client,
                agent_id=agent_id,
                token=token,
                thread_id=thread_id,
                resume_id=resume_id,
                position=position,
                interview_round=interview_round,
                query=answer,
            )
        )

    result_payload = finalize_round(
        client,
        token=token,
        thread_id=thread_id,
        position=position,
        interview_round=interview_round,
    )

    return {
        "position": position,
        "round": interview_round,
        "thread_id": thread_id,
        "thread_title": title,
        "conversation": conversation,
        "result_payload": result_payload,
        "result_summary": build_result_summary(result_payload),
    }


def run_capture_script(*, manifest_path: Path) -> None:
    command = ["node", "e2e/interview_capture.mjs", str(manifest_path)]
    completed = subprocess.run(
        command,
        cwd=str(WEB_DIR),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"截图脚本执行失败\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}")
    print(completed.stdout, flush=True)


def resolve_font_path(*, bold: bool = False) -> Path | None:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = resolve_font_path(bold=bold)
    if font_path:
        return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def wrap_lines(text: str, width: int) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return ["无"]
    lines = []
    for raw_line in normalized.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(stripped, width=width, break_long_words=True, replace_whitespace=False) or [""])
    return lines or ["无"]


def create_snapshot_image(
    *,
    title: str,
    subtitle: str,
    sections: list[tuple[str, list[str]]],
    output_path: Path,
) -> None:
    width = 1600
    margin = 48
    header_height = 220
    section_gap = 22
    card_padding = 24

    title_font = load_font(54, bold=True)
    subtitle_font = load_font(24)
    section_title_font = load_font(30, bold=True)
    body_font = load_font(22)
    small_font = load_font(18)

    estimated_height = header_height + margin
    for _, items in sections:
        estimated_height += 110 + max(1, sum(max(1, len(wrap_lines(item, 60))) for item in items)) * 34
    estimated_height += 120

    image = Image.new("RGB", (width, estimated_height), color="#f5f7fb")
    draw = ImageDraw.Draw(image)

    y = margin
    draw.rounded_rectangle((margin, y, width - margin, y + 170), radius=26, fill="#ffffff", outline="#dbe3f0", width=2)
    draw.text((margin + 28, y + 24), title, fill="#172033", font=title_font)
    draw.text((margin + 28, y + 100), subtitle, fill="#5b6780", font=subtitle_font)
    y += header_height

    for section_title, items in sections:
        content_lines: list[tuple[str, ImageFont.ImageFont | ImageFont.FreeTypeFont, str]] = []
        for item in items:
            wrapped = wrap_lines(item, 60)
            for idx, line in enumerate(wrapped):
                prefix = "• " if idx == 0 else "  "
                content_lines.append((f"{prefix}{line}", body_font, "#21304f"))
            content_lines.append(("", small_font, "#21304f"))
        if content_lines and content_lines[-1][0] == "":
            content_lines.pop()

        section_height = 88 + max(1, len(content_lines)) * 34 + card_padding
        draw.rounded_rectangle(
            (margin, y, width - margin, y + section_height),
            radius=22,
            fill="#ffffff",
            outline="#dbe3f0",
            width=2,
        )
        draw.text((margin + card_padding, y + 20), section_title, fill="#172033", font=section_title_font)
        inner_y = y + 72
        for line, font, color in content_lines:
            draw.text((margin + card_padding, inner_y), line, fill=color, font=font)
            inner_y += 34
        y += section_height + section_gap

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.crop((0, 0, width, y + margin)).save(output_path)


def html_escape(value: Any) -> str:
    text = str(value or "")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_badge_list(items: list[str], badge_class: str) -> str:
    if not items:
        return f'<span class="{badge_class}">无</span>'
    return "".join(f'<span class="{badge_class}">{html_escape(item)}</span>' for item in items)


def render_list(items: list[str], empty_text: str) -> str:
    if not items:
        return f"<li>{html_escape(empty_text)}</li>"
    return "".join(f"<li>{html_escape(item)}</li>" for item in items)


def render_action_steps(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "<li>暂无结构化行动步骤</li>"
    return "".join(
        (
            "<li>"
            f"<strong>{html_escape(step.get('title') or '未命名步骤')}</strong>"
            f"<div>{html_escape(step.get('objective') or '无明确目标')}</div>"
            f'<div class="muted">预计 {html_escape(step.get("estimated_minutes") or "--")} 分钟</div>'
            "</li>"
        )
        for step in steps
    )


def build_snapshot_shell(title: str, subtitle: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html_escape(title)}</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --line: #dbe3f0;
      --text: #172033;
      --muted: #5b6780;
      --primary: #2357ff;
      --success: #127a4d;
      --warn: #c77700;
      --danger: #c63d2f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 32px;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(35, 87, 255, 0.08), transparent 28%),
        linear-gradient(180deg, #f8fbff 0%, var(--bg) 100%);
    }}
    .page {{
      max-width: 1280px;
      margin: 0 auto;
    }}
    .snapshot-hero {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 28px 32px;
      margin-bottom: 24px;
      box-shadow: 0 14px 42px rgba(20, 35, 90, 0.08);
    }}
    .eyebrow {{
      color: var(--primary);
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 10px;
      font-weight: 700;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.2;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 20px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 22px 24px;
      box-shadow: 0 10px 30px rgba(20, 35, 90, 0.05);
    }}
    .card h2 {{
      margin: 0 0 14px;
      font-size: 20px;
    }}
    .span-4 {{ grid-column: span 4; }}
    .span-6 {{ grid-column: span 6; }}
    .span-8 {{ grid-column: span 8; }}
    .span-12 {{ grid-column: span 12; }}
    .score {{
      font-size: 52px;
      font-weight: 700;
      color: var(--primary);
      line-height: 1;
    }}
    .muted {{
      color: var(--muted);
      font-size: 14px;
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 600;
      background: #edf2ff;
      color: #1f45b8;
    }}
    .badge.success {{
      background: #e8f7ee;
      color: var(--success);
    }}
    .badge.warn {{
      background: #fff4df;
      color: var(--warn);
    }}
    .badge.danger {{
      background: #ffe8e4;
      color: var(--danger);
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
      line-height: 1.7;
    }}
    li + li {{
      margin-top: 8px;
    }}
    .kpi-row {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-top: 18px;
    }}
    .kpi {{
      min-width: 180px;
      padding: 14px 16px;
      border-radius: 16px;
      background: #f6f8fc;
      border: 1px solid var(--line);
    }}
    .kpi-label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 6px;
    }}
    .kpi-value {{
      font-size: 22px;
      font-weight: 700;
    }}
    .summary {{
      white-space: pre-wrap;
      line-height: 1.8;
      color: #21304f;
    }}
    @media (max-width: 900px) {{
      body {{ padding: 18px; }}
      .span-4, .span-6, .span-8, .span-12 {{ grid-column: span 12; }}
      h1 {{ font-size: 28px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="snapshot-hero">
      <div class="eyebrow">E2E Interview Snapshot</div>
      <h1>{html_escape(title)}</h1>
      <p class="subtitle">{html_escape(subtitle)}</p>
    </section>
    {body}
  </div>
</body>
</html>
"""


def write_result_snapshot(*, output_dir: Path, round_index: int, round_item: dict[str, Any]) -> Path:
    summary = round_item["result_summary"]
    result_payload = round_item["result_payload"]
    result = result_payload.get("result") or {}
    highlights = summary.get("report_highlights") or []
    body = f"""
    <section class="grid">
      <article class="card span-4">
        <h2>综合表现</h2>
        <div class="score">{html_escape(summary.get("overall_score") or "--")}</div>
        <div class="muted">岗位：{html_escape(round_item["position"])} / 轮次：{html_escape(round_item["round"])}</div>
        <div class="kpi-row">
          <div class="kpi">
            <div class="kpi-label">线程 ID</div>
            <div class="kpi-value" style="font-size:14px">{html_escape(round_item["thread_id"])}</div>
          </div>
          <div class="kpi">
            <div class="kpi-label">状态</div>
            <div class="kpi-value">{html_escape(result.get("status") or "unknown")}</div>
          </div>
        </div>
      </article>
      <article class="card span-4">
        <h2>表现亮点</h2>
        <div class="badges">{render_badge_list(summary.get("strengths") or [], "badge success")}</div>
      </article>
      <article class="card span-4">
        <h2>主要风险</h2>
        <div class="badges">{render_badge_list(summary.get("risks") or [], "badge danger")}</div>
      </article>
      <article class="card span-6">
        <h2>改进建议</h2>
        <ul>{render_list(summary.get("suggestions") or [], "暂无建议")}</ul>
      </article>
      <article class="card span-6">
        <h2>行动步骤</h2>
        <ul>{render_action_steps(summary.get("action_steps") or [])}</ul>
      </article>
      <article class="card span-12">
        <h2>高价值结论</h2>
        <ul>{
        render_list(
            [item.get("title") + "：" + item.get("summary") for item in highlights if item.get("title")],
            "暂无高价值结论",
        )
    }</ul>
      </article>
      <article class="card span-12">
        <h2>原始总结</h2>
        <div class="summary">{html_escape(summary.get("summary_markdown") or "暂无总结")}</div>
      </article>
    </section>
    """
    html = build_snapshot_shell(
        title=f"第 {round_index} 轮面试结果快照",
        subtitle=f"{round_item['position']} / {round_item['round']} 的真实 API 评分结果",
        body=body,
    )
    html_path = output_dir / f"result_round_{round_index}.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def write_records_snapshot(
    *, output_dir: Path, personalized_path: dict[str, Any], rounds: list[dict[str, Any]]
) -> Path:
    path_payload = personalized_path.get("personalized_path") or {}
    path_summary = path_payload.get("summary") or {}
    weaknesses = path_payload.get("weaknesses") or []
    next_focus = path_payload.get("next_assessment_focus") or []
    resources = path_payload.get("recommended_resources") or []
    related_records = path_payload.get("related_records") or []

    body = f"""
    <section class="grid personalized-path">
      <article class="card span-4">
        <h2>当前阶段</h2>
        <div class="score" style="font-size:38px">{html_escape(path_summary.get("stage_label") or "未生成")}</div>
        <div class="muted">{html_escape(path_summary.get("message") or "暂无阶段总结")}</div>
      </article>
      <article class="card span-4">
        <h2>主要短板</h2>
        <ul>{render_list([item.get("title") for item in weaknesses if item.get("title")], "暂无明显短板")}</ul>
      </article>
      <article class="card span-4">
        <h2>下次回测重点</h2>
        <ul>{render_list([item.get("title") for item in next_focus if item.get("title")], "暂无重点")}</ul>
      </article>
      <article class="card span-6">
        <h2>推荐资源</h2>
        <ul>{render_list([item.get("title") for item in resources if item.get("title")], "暂无推荐资源")}</ul>
      </article>
      <article class="card span-6">
        <h2>关联记录</h2>
        <ul>{render_list([item.get("title") for item in related_records if item.get("title")], "暂无关联记录")}</ul>
      </article>
      <article class="card span-12">
        <h2>本次纳入分析的面试轮次</h2>
        <div class="badges">{
        render_badge_list(
            [f"{item['position']} / {item['round']}" for item in rounds],
            "badge",
        )
    }</div>
      </article>
    </section>
    """
    html = build_snapshot_shell(
        title="个性化提升路径快照",
        subtitle="基于真实面试结果生成的长期改进建议",
        body=body,
    )
    html_path = output_dir / "records_overview.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def write_result_png_snapshot(*, output_dir: Path, round_index: int, round_item: dict[str, Any]) -> Path:
    summary = round_item["result_summary"]
    sections = [
        (
            "综合信息",
            [
                f"岗位：{round_item['position']} / 轮次：{round_item['round']}",
                f"综合分：{summary.get('overall_score') or '--'}",
                f"线程 ID：{round_item['thread_id']}",
            ],
        ),
        ("表现亮点", summary.get("strengths") or ["暂无明确亮点"]),
        ("主要风险", summary.get("risks") or ["暂无明显风险"]),
        ("改进建议", summary.get("suggestions") or ["暂无建议"]),
        (
            "行动步骤",
            [
                (
                    f"{item.get('title') or '未命名步骤'}｜"
                    f"目标：{item.get('objective') or '无'}｜"
                    f"预计 {item.get('estimated_minutes') or '--'} 分钟"
                )
                for item in (summary.get("action_steps") or [])
            ]
            or ["暂无结构化行动步骤"],
        ),
    ]
    output_path = output_dir / f"result_round_{round_index}.png"
    create_snapshot_image(
        title=f"第 {round_index} 轮面试结果快照",
        subtitle="真实 API 生成的评分与反馈摘要",
        sections=sections,
        output_path=output_path,
    )
    return output_path


def write_records_png_snapshot(
    *, output_dir: Path, personalized_path: dict[str, Any], rounds: list[dict[str, Any]]
) -> Path:
    path_payload = personalized_path.get("personalized_path") or {}
    path_summary = path_payload.get("summary") or {}
    sections = [
        (
            "当前阶段",
            [
                f"阶段：{path_summary.get('stage_label') or '未生成'}",
                f"总结：{path_summary.get('message') or '暂无总结'}",
            ],
        ),
        (
            "主要短板",
            [item.get("title") or "未命名短板" for item in (path_payload.get("weaknesses") or [])[:5]]
            or ["暂无明显短板"],
        ),
        (
            "下次回测重点",
            [item.get("title") or "未命名重点" for item in (path_payload.get("next_assessment_focus") or [])[:5]]
            or ["暂无重点"],
        ),
        (
            "推荐资源",
            [item.get("title") or "未命名资源" for item in (path_payload.get("recommended_resources") or [])[:5]]
            or ["暂无推荐资源"],
        ),
        (
            "纳入分析的轮次",
            [f"{item['position']} / {item['round']}" for item in rounds] or ["暂无轮次"],
        ),
    ]
    output_path = output_dir / "records_overview.png"
    create_snapshot_image(
        title="个性化提升路径快照",
        subtitle="基于真实面试结果生成的长期提升建议",
        sections=sections,
        output_path=output_path,
    )
    return output_path


def write_markdown_report(*, output_dir: Path, rounds: list[dict[str, Any]], personalized_path: dict[str, Any]) -> Path:
    lines = ["# 本地 E2E 面试测试报告", ""]
    for index, item in enumerate(rounds, start=1):
        summary = item["result_summary"]
        lines.extend(
            [
                f"## Round {index} - {item['position']} / {item['round']}",
                f"- 线程ID：`{item['thread_id']}`",
                f"- 综合分：`{summary['overall_score']}`",
                f"- 优势：{'；'.join(summary['strengths']) if summary['strengths'] else '无'}",
                f"- 风险：{'；'.join(summary['risks']) if summary['risks'] else '无'}",
                f"- 改进建议：{'；'.join(summary['suggestions']) if summary['suggestions'] else '无'}",
                "",
            ]
        )

    path_payload = personalized_path.get("personalized_path") or {}
    path_summary = path_payload.get("summary") or {}
    weaknesses = path_payload.get("weaknesses") or []
    next_focus = path_payload.get("next_assessment_focus") or []
    resources = path_payload.get("recommended_resources") or []

    lines.extend(
        [
            "## 个性化提升路径",
            f"- 阶段：{path_summary.get('stage_label', '无')}",
            f"- 总结：{path_summary.get('message', '无')}",
            (f"- 主要短板：{'；'.join(item.get('title', '') for item in weaknesses[:3] if item.get('title')) or '无'}"),
            (
                f"- 下次回测重点："
                f"{'；'.join(item.get('title', '') for item in next_focus[:3] if item.get('title')) or '无'}"
            ),
            (f"- 推荐资源：{'；'.join(item.get('title', '') for item in resources[:3] if item.get('title')) or '无'}"),
            "",
        ]
    )

    report_path = output_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    run_dir = OUTPUT_ROOT / now_label()
    run_dir.mkdir(parents=True, exist_ok=True)

    ensure_clean_file(DB_PATH)

    api_process = None

    try:
        python_exe = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            raise RuntimeError(f"未找到 Python 虚拟环境：{python_exe}")

        api_env = os.environ.copy()
        api_env.update(
            {
                "POSTGRES_URL": DB_URL,
                "LANGGRAPH_CHECKPOINTER_BACKEND": "sqlite",
                "RAG_BACKEND": "",
                "OPENVIKING_ENABLED": "0",
                "REDIS_URL": "redis://127.0.0.1:6399/0",
            }
        )

        print_step("启动本地 API 服务")
        api_process = start_process(
            "api",
            [str(python_exe), "-m", "uvicorn", "server.main:app", "--host", API_HOST, "--port", str(API_PORT)],
            cwd=ROOT_DIR,
            env=api_env,
            log_path=run_dir / "api.log",
        )

        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            wait_for_http_ready(client, "/api/auth/check-first-run", timeout_seconds=90, process=api_process)

            print_step("初始化管理员并获取令牌")
            auth_payload = initialize_admin(client)
            token = auth_payload["access_token"]
            user_id = int(auth_payload["user_id"])

            print_step("注入测试简历")
            resume_id = seed_resume(user_id=user_id, output_dir=run_dir)

            print_step("获取默认面试智能体")
            default_agent_resp = client.get(
                "/api/chat/default_agent",
                headers={"Authorization": f"Bearer {token}"},
            )
            default_agent_resp.raise_for_status()
            agent_id = default_agent_resp.json()["default_agent_id"]

            executed_rounds = []
            for round_config in ROUNDS:
                print_step(f"执行真实面试：{round_config['position']} / {round_config['round']}")
                executed_rounds.append(
                    run_round(
                        client,
                        agent_id=agent_id,
                        token=token,
                        resume_id=resume_id,
                        round_config=round_config,
                    )
                )

            print_step("拉取个性化提升路径")
            personalized_path = fetch_personalized_path(client, token=token)

        raw_results_path = run_dir / "raw_results.json"
        raw_results_path.write_text(
            json.dumps(
                {
                    "resume_id": resume_id,
                    "rounds": executed_rounds,
                    "personalized_path": personalized_path,
                    "api_base_url": API_BASE_URL,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        for index, item in enumerate(executed_rounds, start=1):
            write_result_snapshot(output_dir=run_dir, round_index=index, round_item=item)
        write_records_snapshot(
            output_dir=run_dir,
            personalized_path=personalized_path,
            rounds=executed_rounds,
        )

        print_step("抓取结果页与记录页截图")
        for index, round_item in enumerate(executed_rounds, start=1):
            write_result_png_snapshot(output_dir=run_dir, round_index=index, round_item=round_item)
        write_records_png_snapshot(output_dir=run_dir, personalized_path=personalized_path, rounds=executed_rounds)

        report_path = write_markdown_report(
            output_dir=run_dir,
            rounds=executed_rounds,
            personalized_path=personalized_path,
        )

        print_step("E2E 测试完成")
        print(
            json.dumps(
                {"output_dir": str(run_dir.resolve()), "report": str(report_path.resolve())},
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print_step(f"执行失败：{exc}")
        return 1
    finally:
        stop_process(api_process)


if __name__ == "__main__":
    if sys.platform == "win32":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    raise SystemExit(main())
