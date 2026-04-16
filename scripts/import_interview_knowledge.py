from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.position_types import get_position_type

try:
    from interview_knowledge_sources import (
        CURATED_KNOWLEDGE_ROOT,
        CURATED_MANIFEST_PATH,
        ensure_interview_knowledge_sources,
    )
except ModuleNotFoundError:
    from scripts.interview_knowledge_sources import (
        CURATED_KNOWLEDGE_ROOT,
        CURATED_MANIFEST_PATH,
        ensure_interview_knowledge_sources,
    )

DEFAULT_BASE_URL = "http://127.0.0.1:5050/api"
DEFAULT_EMBED_MODEL = "siliconflow/Pro/BAAI/bge-m3"
REPORT_PATH = ROOT / "scripts" / "tmp" / "import_interview_knowledge_report.json"
TERMINAL_TASK_STATUSES = {"success", "failed", "cancelled"}
INDEXED_STATUSES = {"indexed", "done"}
QA_SEPARATOR = "\n\n\n"


@dataclass(frozen=True)
class FolderImportPlan:
    name: str
    files: tuple[Path, ...]


@dataclass(frozen=True)
class KnowledgeDocumentPlan:
    source_path: Path
    target_filename: str
    chunk_preset_id: str
    topic_name: str


@dataclass(frozen=True)
class KnowledgeImportPlan:
    name: str
    description: str
    position: str
    documents: tuple[KnowledgeDocumentPlan, ...]
    folders: tuple[FolderImportPlan, ...] = ()
    root_files: tuple[Path, ...] = ()


class ImportError(RuntimeError):
    pass


def _position_label(key: str) -> str:
    return get_position_type(key)["label"]


POSITION_DATABASE_DESCRIPTIONS = {
    "frontend": "前端岗位面试知识库，覆盖前端基础、框架、工程化与常见面试主题。",
    "backend": "后端岗位面试知识库，覆盖后端基础、数据库、分布式与高频面试主题。",
    "algorithm": "算法岗位面试知识库，覆盖数据结构、算法题型与编码思路。",
    "system_design": "系统架构岗位知识库，覆盖系统设计方法、经典案例与架构权衡。",
    "ai_app": "AI 应用开发知识库，覆盖 LLM、RAG、Agent、MCP 与 AI Coding。",
}

ALL_SELECTABLE_POSITION_KEYS = ("frontend", "backend", "algorithm", "system_design", "ai_app")
LEGACY_PACKAGE_DATABASE_NAMES = (
    "JavaGuide 后端面试",
    "AI 应用开发面试",
    "React 面试题库",
    "前端面试手册",
    "通用技术面试手册",
    "系统设计面试题库",
    "DSA 面试手册",
    "Node.js 面试题库",
    "SQL 面试题库",
)


def get_legacy_package_database_names() -> list[str]:
    return list(LEGACY_PACKAGE_DATABASE_NAMES)


def get_managed_interview_database_names() -> list[str]:
    return get_legacy_package_database_names() + [_position_label(key) for key in ALL_SELECTABLE_POSITION_KEYS]


def _sanitize_filename_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', " ", str(value or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(". ") or "untitled"


def extract_markdown_title(source_path: Path) -> str:
    content = source_path.read_text(encoding="utf-8")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return source_path.stem


def build_target_filename(
    source_path: Path,
    curated_root: Path = CURATED_KNOWLEDGE_ROOT,
    *,
    used_filenames: set[str] | None = None,
) -> str:
    base_name = _sanitize_filename_segment(extract_markdown_title(source_path))
    extension = source_path.suffix or ".md"
    candidate = f"{base_name}{extension}"
    if used_filenames is None:
        return candidate

    index = 2
    while candidate.lower() in used_filenames:
        candidate = f"{base_name}__{index}{extension}"
        index += 1
    used_filenames.add(candidate.lower())
    return candidate


def infer_chunk_preset_id(source_path: Path, curated_root: Path = CURATED_KNOWLEDGE_ROOT) -> str:
    return "qa"


def infer_position_keys_for_file(source_path: Path, curated_root: Path = CURATED_KNOWLEDGE_ROOT) -> tuple[str, ...]:
    relative_path = source_path.relative_to(curated_root)
    top_level = relative_path.parts[0]
    relative_text = relative_path.as_posix()

    if top_level == "javaguide-backend":
        if "/cs-basics/" in f"/{relative_text}":
            return ("backend", "algorithm")
        if "/system-design/" in f"/{relative_text}":
            return ("backend", "system_design")
        return ("backend",)

    if top_level == "javaguide-ai":
        return ("ai_app",)

    if top_level in {"react-interview", "frontend-handbook"}:
        return ("frontend",)

    if top_level == "system-design-primer":
        return ("system_design",)

    if top_level == "dsa-handbook":
        return ("algorithm",)

    if top_level in {"nodejs-interview", "sql-interview"}:
        return ("backend",)

    if top_level == "tech-interview-handbook":
        return ALL_SELECTABLE_POSITION_KEYS

    return ()


def infer_topic_names_for_file(
    source_path: Path,
    position_keys: tuple[str, ...],
    curated_root: Path = CURATED_KNOWLEDGE_ROOT,
) -> dict[str, str]:
    relative_path = source_path.relative_to(curated_root)
    top_level = relative_path.parts[0]
    path_parts = relative_path.parts[1:]

    if top_level == "javaguide-backend":
        first_part = path_parts[0] if path_parts else ""
        if first_part == "interview-preparation":
            return {"backend": "面试准备"}
        if first_part == "java":
            return {"backend": "Java"}
        if first_part == "database":
            return {"backend": "数据库"}
        if first_part == "cs-basics":
            return {
                "backend": "计算机基础",
                "algorithm": "算法与数据结构",
            }
        if first_part == "distributed-system":
            return {"backend": "分布式"}
        if first_part == "system-design":
            return {
                "backend": "系统设计",
                "system_design": "系统设计",
            }
        if first_part == "high-availability":
            return {"backend": "高可用"}
        if first_part == "high-performance":
            return {"backend": "高性能"}

    if top_level == "javaguide-ai":
        first_part = path_parts[0] if path_parts else ""
        topic_map = {
            "README.md": "AI 总览",
            "llm-basis": "LLM基础",
            "rag": "RAG",
            "agent": "Agent",
            "ai-coding": "AI Coding",
        }
        topic = topic_map.get(first_part or relative_path.name, "AI 应用开发")
        return {"ai_app": topic}

    if top_level == "react-interview":
        return {"frontend": "React"}

    if top_level == "frontend-handbook":
        first_part = path_parts[0] if path_parts else ""
        topic_map = {
            "frontend-guide": "前端基础",
            "behavioral": "行为面试",
            "react-playbook": "React",
        }
        return {"frontend": topic_map.get(first_part, "前端基础")}

    if top_level == "tech-interview-handbook":
        first_part = path_parts[0] if path_parts else ""
        topic_map = {
            "behavioral": "行为面试",
            "coding": "编程面试",
            "general": "通用基础",
        }
        topic = topic_map.get(first_part, "通用基础")
        return {position_key: topic for position_key in position_keys}

    if top_level == "system-design-primer":
        return {"system_design": "系统设计"}

    if top_level == "dsa-handbook":
        return {"algorithm": "算法与数据结构"}

    if top_level == "nodejs-interview":
        return {"backend": "Node.js"}

    if top_level == "sql-interview":
        return {"backend": "数据库"}

    return {position_key: "未分类" for position_key in position_keys}


def build_import_plan() -> tuple[KnowledgeImportPlan, ...]:
    source_documents: list[tuple[tuple[str, ...], Path, str, dict[str, str]]] = []

    for source_path in sorted(CURATED_KNOWLEDGE_ROOT.rglob("*.md")):
        position_keys = infer_position_keys_for_file(source_path, CURATED_KNOWLEDGE_ROOT)
        if not position_keys:
            continue
        topic_names = infer_topic_names_for_file(source_path, position_keys, CURATED_KNOWLEDGE_ROOT)
        source_documents.append(
            (
                position_keys,
                source_path,
                infer_chunk_preset_id(source_path, CURATED_KNOWLEDGE_ROOT),
                topic_names,
            )
        )

    plans: list[KnowledgeImportPlan] = []
    for position_key in ALL_SELECTABLE_POSITION_KEYS:
        used_filenames_by_topic: dict[str, set[str]] = {}
        documents_list: list[KnowledgeDocumentPlan] = []
        for position_keys, source_path, chunk_preset_id, topic_names in source_documents:
            if position_key not in position_keys:
                continue
            topic_name = topic_names[position_key]
            used_filenames = used_filenames_by_topic.setdefault(topic_name, set())
            documents_list.append(
                KnowledgeDocumentPlan(
                    source_path=source_path,
                    target_filename=build_target_filename(
                        source_path,
                        CURATED_KNOWLEDGE_ROOT,
                        used_filenames=used_filenames,
                    ),
                    chunk_preset_id=chunk_preset_id,
                    topic_name=topic_name,
                )
            )
        documents = tuple(documents_list)
        if not documents:
            continue
        plans.append(
            KnowledgeImportPlan(
                name=_position_label(position_key),
                description=POSITION_DATABASE_DESCRIPTIONS[position_key],
                position=_position_label(position_key),
                documents=documents,
            )
        )

    return tuple(plans)


class ApiClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))

    async def __aenter__(self) -> ApiClient:
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.client.aclose()

    async def login(self) -> None:
        response = await self.client.post(
            f"{self.base_url}/auth/token",
            data={"username": self.username, "password": self.password},
        )
        if response.status_code != 200:
            raise ImportError(f"Login failed: {response.status_code} {response.text}")
        token = response.json().get("access_token")
        if not token:
            raise ImportError("Login succeeded but access_token is missing")
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    async def get(self, path: str) -> dict[str, Any]:
        response = await self.client.get(f"{self.base_url}{path}")
        if response.status_code >= 400:
            raise ImportError(f"GET {path} failed: {response.status_code} {response.text}")
        return response.json()

    async def post(
        self,
        path: str,
        *,
        json_body: Any = None,
        files: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self.client.post(f"{self.base_url}{path}", json=json_body, files=files, params=params)
        if response.status_code >= 400:
            raise ImportError(f"POST {path} failed: {response.status_code} {response.text}")
        return response.json()

    async def put(self, path: str, *, json_body: Any = None) -> dict[str, Any]:
        response = await self.client.put(f"{self.base_url}{path}", json=json_body)
        if response.status_code >= 400:
            raise ImportError(f"PUT {path} failed: {response.status_code} {response.text}")
        return response.json()

    async def delete(self, path: str) -> dict[str, Any]:
        response = await self.client.delete(f"{self.base_url}{path}")
        if response.status_code >= 400:
            raise ImportError(f"DELETE {path} failed: {response.status_code} {response.text}")
        return response.json()

    async def list_databases(self) -> list[dict[str, Any]]:
        data = await self.get("/knowledge/databases")
        return data.get("databases", [])

    async def delete_database(self, db_id: str) -> dict[str, Any]:
        return await self.delete(f"/knowledge/databases/{db_id}")

    async def get_database_info(self, db_id: str) -> dict[str, Any]:
        return await self.get(f"/knowledge/databases/{db_id}")

    async def ensure_database(self, plan: KnowledgeImportPlan) -> dict[str, Any]:
        desired_params = build_index_params("qa", plan.position)
        for database in await self.list_databases():
            if database.get("name") != plan.name:
                continue

            db_id = database.get("db_id")
            if not db_id:
                return database

            db_info = await self.get_database_info(db_id)
            current_params = db_info.get("additional_params") or {}
            if current_params != desired_params:
                await self.put(
                    f"/knowledge/databases/{db_id}",
                    json_body={
                        "name": db_info.get("name") or plan.name,
                        "description": db_info.get("description") or plan.description,
                        "llm_info": db_info.get("llm_info"),
                        "additional_params": desired_params,
                        "share_config": db_info.get("share_config"),
                    },
                )
                return await self.get_database_info(db_id)

            return db_info

        return await self.post(
            "/knowledge/databases",
            json_body={
                "database_name": plan.name,
                "description": plan.description,
                "embed_model_name": DEFAULT_EMBED_MODEL,
                "kb_type": "openviking",
                "additional_params": desired_params,
                "llm_info": {
                    "provider": "siliconflow",
                    "model_name": "Pro/deepseek-ai/DeepSeek-V3",
                },
            },
        )

    async def ensure_folder(self, db_id: str, folder_name: str, parent_id: str | None = None) -> str:
        db_info = await self.get_database_info(db_id)
        for file_id, file_info in db_info.get("files", {}).items():
            if (
                file_info.get("is_folder")
                and file_info.get("filename") == folder_name
                and file_info.get("parent_id") == parent_id
            ):
                return file_id

        created = await self.post(
            f"/knowledge/databases/{db_id}/folders",
            json_body={"folder_name": folder_name, "parent_id": parent_id},
        )
        folder_id = created.get("file_id")
        if not folder_id:
            raise ImportError(f"Failed to create folder {folder_name} in {db_id}")
        return folder_id

    async def upload_file(self, db_id: str, file_path: Path, upload_name: str) -> dict[str, Any]:
        mime_type, _ = mimetypes.guess_type(upload_name)
        mime_type = mime_type or "text/markdown"
        with file_path.open("rb") as handle:
            files = {"file": (upload_name, handle, mime_type)}
            return await self.post("/knowledge/files/upload", files=files, params={"db_id": db_id})

    async def add_documents(self, db_id: str, items: list[str], params: dict[str, Any]) -> dict[str, Any]:
        return await self.post(
            f"/knowledge/databases/{db_id}/documents",
            json_body={"items": items, "params": params},
        )

    async def parse_documents(self, db_id: str, file_ids: list[str]) -> dict[str, Any]:
        return await self.post(f"/knowledge/databases/{db_id}/documents/parse", json_body=file_ids)

    async def index_documents(self, db_id: str, file_ids: list[str], params: dict[str, Any]) -> dict[str, Any]:
        return await self.post(
            f"/knowledge/databases/{db_id}/documents/index",
            json_body={"file_ids": file_ids, "params": params},
        )

    async def get_task(self, task_id: str) -> dict[str, Any]:
        data = await self.get(f"/tasks/{task_id}")
        return data.get("task", {})

    async def wait_for_task(self, task_id: str, *, poll_interval: float = 2.0) -> dict[str, Any]:
        while True:
            task = await self.get_task(task_id)
            if task.get("status") in TERMINAL_TASK_STATUSES:
                return task
            await asyncio.sleep(poll_interval)

    async def query(self, db_id: str, query: str) -> dict[str, Any]:
        return await self.post(f"/knowledge/databases/{db_id}/query", json_body={"query": query, "meta": {}})


def read_default_credentials() -> tuple[str | None, str | None]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return None, None

    env_values = dotenv_values(env_path)
    return (
        env_values.get("AI_INTERVIEW_SUPER_ADMIN_NAME"),
        env_values.get("AI_INTERVIEW_SUPER_ADMIN_PASSWORD"),
    )


def file_key(filename: str, parent_id: str | None) -> tuple[str, str]:
    return filename.lower(), parent_id or ""


def build_expected_file_map(
    documents: list[KnowledgeDocumentPlan],
    parent_id: str | None,
) -> dict[tuple[str, str], KnowledgeDocumentPlan]:
    return {file_key(document.target_filename, parent_id): document for document in documents}


def extract_current_file_map(db_info: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    current: dict[tuple[str, str], dict[str, Any]] = {}
    for file_id, file_info in db_info.get("files", {}).items():
        if file_info.get("is_folder"):
            continue
        entry = dict(file_info)
        entry["file_id"] = file_id
        current[file_key(file_info.get("filename", ""), file_info.get("parent_id"))] = entry
    return current


def build_ingest_params(
    *,
    parent_id: str | None,
    content_hashes: dict[str, str],
    chunk_preset_id: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "content_type": "file",
        "content_hashes": content_hashes,
        "parent_id": parent_id,
        "auto_index": True,
        "chunk_preset_id": chunk_preset_id,
    }
    if chunk_preset_id == "qa":
        params["qa_separator"] = QA_SEPARATOR
    return params


def build_index_params(chunk_preset_id: str, position: str) -> dict[str, Any]:
    params: dict[str, Any] = {"chunk_preset_id": chunk_preset_id, "position": position}
    if chunk_preset_id == "qa":
        params["qa_separator"] = QA_SEPARATOR
    return params


async def wait_for_queued_result(api: ApiClient, response: dict[str, Any]) -> dict[str, Any]:
    if response.get("status") != "queued":
        return response

    task_id = response.get("task_id")
    if not task_id:
        raise ImportError(f"Queued response is missing task_id: {response}")

    task = await api.wait_for_task(task_id)
    if task.get("status") != "success":
        raise ImportError(f"Task {task_id} failed: {task.get('error') or task}")
    return task


async def repair_file_states(
    api: ApiClient,
    db_id: str,
    expected_files: dict[tuple[str, str], KnowledgeDocumentPlan],
    parent_id: str | None,
    chunk_preset_id: str,
    position: str,
    force_reindex: bool,
) -> dict[str, Any]:
    db_info = await api.get_database_info(db_id)
    current_files = extract_current_file_map(db_info)

    parse_ids: list[str] = []
    index_ids: list[str] = []
    missing_documents: list[KnowledgeDocumentPlan] = []

    for key, document in expected_files.items():
        file_info = current_files.get(key)
        if not file_info:
            missing_documents.append(document)
            continue

        status = file_info.get("status")
        if status in INDEXED_STATUSES and not force_reindex:
            continue
        if status in {"uploaded", "error_parsing", "failed"}:
            parse_ids.append(file_info["file_id"])
        elif status in {"parsed", "error_indexing"} or (force_reindex and status in INDEXED_STATUSES):
            index_ids.append(file_info["file_id"])

    if parse_ids:
        await wait_for_queued_result(api, await api.parse_documents(db_id, parse_ids))

    if parse_ids or index_ids:
        refreshed = await api.get_database_info(db_id)
        refreshed_files = extract_current_file_map(refreshed)
        parse_repaired_ids = []
        for key, document in expected_files.items():
            if document in missing_documents:
                continue

            file_info = refreshed_files.get(key)
            if not file_info:
                continue

            if file_info.get("status") in {"parsed", "error_indexing"}:
                parse_repaired_ids.append(file_info["file_id"])

        all_index_ids = sorted(set(index_ids + parse_repaired_ids))
        if all_index_ids:
            await wait_for_queued_result(
                api,
                await api.index_documents(db_id, all_index_ids, build_index_params(chunk_preset_id, position)),
            )

    return {"missing_documents": missing_documents}


async def import_batch(
    api: ApiClient,
    db_id: str,
    *,
    documents: list[KnowledgeDocumentPlan],
    parent_id: str | None,
    chunk_preset_id: str,
    position: str,
    force_reindex: bool,
) -> dict[str, Any]:
    db_info = await api.get_database_info(db_id)
    current_files = extract_current_file_map(db_info)
    expected_map = build_expected_file_map(documents, parent_id)

    missing_to_upload: list[KnowledgeDocumentPlan] = []
    existing_ready = 0
    for key, document in expected_map.items():
        existing = current_files.get(key)
        if existing and existing.get("status") in INDEXED_STATUSES and not force_reindex:
            existing_ready += 1
            continue
        if existing:
            continue
        missing_to_upload.append(document)

    upload_items: list[str] = []
    content_hashes: dict[str, str] = {}
    uploaded_names: list[str] = []

    for document in missing_to_upload:
        upload_result = await api.upload_file(db_id, document.source_path, document.target_filename)
        upload_items.append(upload_result["file_path"])
        content_hashes[upload_result["file_path"]] = upload_result["content_hash"]
        uploaded_names.append(document.target_filename)

    if upload_items:
        params = build_ingest_params(
            parent_id=parent_id,
            content_hashes=content_hashes,
            chunk_preset_id=chunk_preset_id,
        )
        await wait_for_queued_result(api, await api.add_documents(db_id, upload_items, params))

    repair_result = await repair_file_states(
        api,
        db_id,
        expected_map,
        parent_id,
        chunk_preset_id,
        position,
        force_reindex,
    )

    if repair_result["missing_documents"]:
        retry_items: list[str] = []
        retry_hashes: dict[str, str] = {}
        for document in repair_result["missing_documents"]:
            upload_result = await api.upload_file(db_id, document.source_path, document.target_filename)
            retry_items.append(upload_result["file_path"])
            retry_hashes[upload_result["file_path"]] = upload_result["content_hash"]

        if retry_items:
            params = build_ingest_params(
                parent_id=parent_id,
                content_hashes=retry_hashes,
                chunk_preset_id=chunk_preset_id,
            )
            await wait_for_queued_result(api, await api.add_documents(db_id, retry_items, params))

    final_db_info = await api.get_database_info(db_id)
    final_files = extract_current_file_map(final_db_info)
    unresolved = [
        str(document.source_path)
        for key, document in expected_map.items()
        if (final_files.get(key) or {}).get("status") not in INDEXED_STATUSES
    ]

    return {
        "uploaded": uploaded_names,
        "already_indexed": existing_ready,
        "unresolved": unresolved,
    }


async def import_knowledge_plan(
    api: ApiClient,
    plan: KnowledgeImportPlan,
    *,
    batch_size: int,
    force_reindex: bool,
) -> dict[str, Any]:
    database = await api.ensure_database(plan)
    db_id = database["db_id"]
    print(f"[{plan.name}] using database {db_id}")

    topic_folder_ids: dict[str, str] = {}
    for topic_name in sorted({document.topic_name for document in plan.documents}):
        topic_folder_ids[topic_name] = await api.ensure_folder(db_id, topic_name)

    grouped_documents: dict[tuple[str, str], list[KnowledgeDocumentPlan]] = {}
    for document in plan.documents:
        grouped_documents.setdefault((document.chunk_preset_id, document.topic_name), []).append(document)

    batches_report: list[dict[str, Any]] = []
    for (chunk_preset_id, topic_name), documents in grouped_documents.items():
        for index in range(0, len(documents), batch_size):
            batch = documents[index : index + batch_size]
            print(f"[{plan.name}] importing {topic_name}/{chunk_preset_id} batch {index // batch_size + 1}")
            result = await import_batch(
                api,
                db_id,
                documents=batch,
                parent_id=topic_folder_ids[topic_name],
                chunk_preset_id=chunk_preset_id,
                position=plan.position,
                force_reindex=force_reindex,
            )
            batches_report.append({"scope": topic_name, "chunk_preset_id": chunk_preset_id, "result": result})

    final_info = await api.get_database_info(db_id)
    status_counts: dict[str, int] = {}
    for file_info in final_info.get("files", {}).values():
        if file_info.get("is_folder"):
            continue
        status = file_info.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    unresolved = [
        unresolved_path
        for batch in batches_report
        for unresolved_path in batch["result"].get("unresolved", [])
    ]

    return {
        "name": plan.name,
        "db_id": db_id,
        "row_count": sum(1 for file in final_info.get("files", {}).values() if not file.get("is_folder")),
        "status_counts": status_counts,
        "unresolved": unresolved,
        "batches": batches_report,
    }


async def verify_queries(api: ApiClient, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queries = {
        _position_label("frontend"): "What is React Fiber?",
        _position_label("backend"): "什么是 CAS",
        _position_label("algorithm"): "When to use dynamic programming",
        _position_label("system_design"): "如何设计 Twitter 时间线",
        _position_label("ai_app"): "什么是 RAG",
    }
    results: list[dict[str, Any]] = []
    for report in reports:
        query = queries.get(report["name"])
        if not query:
            continue
        response = await api.query(report["db_id"], query)
        items = response.get("result", [])
        results.append(
            {
                "database": report["name"],
                "query": query,
                "result_count": len(items),
                "top_source": items[0]["metadata"]["source"] if items else None,
            }
        )
    return results


def count_expected_files(plans: tuple[KnowledgeImportPlan, ...]) -> int:
    return sum(len(plan.documents) for plan in plans)


async def run_import(
    base_url: str,
    username: str,
    password: str,
    batch_size: int,
    force_reindex: bool,
    force_sync: bool,
    delete_legacy_package_databases: bool,
) -> dict[str, Any]:
    if force_sync or not CURATED_MANIFEST_PATH.exists():
        source_manifest = ensure_interview_knowledge_sources(force=force_sync)
    else:
        source_manifest = json.loads(CURATED_MANIFEST_PATH.read_text(encoding="utf-8"))
    plans = build_import_plan()

    async with ApiClient(base_url, username, password) as api:
        deleted_databases: list[str] = []
        if delete_legacy_package_databases:
            legacy_names = set(get_managed_interview_database_names())
            for database in await api.list_databases():
                if str(database.get("name") or "").strip() not in legacy_names:
                    continue
                db_id = str(database.get("db_id") or "").strip()
                if not db_id:
                    continue
                await api.delete_database(db_id)
                deleted_databases.append(database["name"])

        database_reports = []
        for plan in plans:
            database_reports.append(
                await import_knowledge_plan(api, plan, batch_size=batch_size, force_reindex=force_reindex)
            )

        all_databases = await api.list_databases()
        total_files = 0
        for report in database_reports:
            db_info = await api.get_database_info(report["db_id"])
            total_files += sum(1 for file in db_info.get("files", {}).values() if not file.get("is_folder"))

        return {
            "source_manifest": source_manifest,
            "deleted_legacy_databases": deleted_databases,
            "database_count": len(all_databases),
            "expected_database_count": len(plans),
            "total_file_count": total_files,
            "expected_total_file_count": count_expected_files(plans),
            "databases": database_reports,
            "queries": await verify_queries(api, database_reports),
        }


def parse_args() -> argparse.Namespace:
    default_username, default_password = read_default_credentials()
    parser = argparse.ArgumentParser(
        description=(
            "Sync curated interview sources into .knowledge"
            " and import them into the AI-interview knowledge base."
        )
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=default_username)
    parser.add_argument("--password", default=default_password)
    parser.add_argument("--batch-size", default=20, type=int)
    parser.add_argument("--force-reindex", action="store_true")
    parser.add_argument(
        "--force-sync",
        action="store_true",
        help="Re-clone upstream repositories before syncing local knowledge sources.",
    )
    parser.add_argument(
        "--delete-legacy-package-databases",
        action="store_true",
        help="Delete managed interview knowledge bases before importing the new position/topic-based ones.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.username or not args.password:
        raise SystemExit(
            "Missing admin credentials. Provide --username/--password or set AI_INTERVIEW_SUPER_ADMIN_* in .env."
        )

    summary = asyncio.run(
        run_import(
            args.base_url,
            args.username,
            args.password,
            args.batch_size,
            args.force_reindex,
            args.force_sync,
            args.delete_legacy_package_databases,
        )
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
