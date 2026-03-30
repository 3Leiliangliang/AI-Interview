from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
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
class KnowledgeImportPlan:
    name: str
    description: str
    chunk_preset_id: str
    folders: tuple[FolderImportPlan, ...] = ()
    root_files: tuple[Path, ...] = ()


def build_import_plan() -> tuple[KnowledgeImportPlan, ...]:
    javaguide_root = ROOT / ".knowledge" / "JavaGuide" / "docs"
    react_root = ROOT / ".knowledge" / "reactjs-interview-questions"
    waking_root = ROOT / ".knowledge" / "Waking-Up"

    def md_files(path: Path) -> tuple[Path, ...]:
        return tuple(sorted(path.rglob("*.md")))

    return (
        KnowledgeImportPlan(
            name="JavaGuide",
            description="Java 面试核心知识库，包含 Java、数据库、计算机基础、分布式与系统设计等主题。",
            chunk_preset_id="qa",
            folders=(
                FolderImportPlan("interview-preparation", md_files(javaguide_root / "interview-preparation")),
                FolderImportPlan("java", md_files(javaguide_root / "java")),
                FolderImportPlan("database", md_files(javaguide_root / "database")),
                FolderImportPlan("cs-basics", md_files(javaguide_root / "cs-basics")),
                FolderImportPlan("distributed-system", md_files(javaguide_root / "distributed-system")),
                FolderImportPlan("system-design", md_files(javaguide_root / "system-design")),
                FolderImportPlan("high-availability", md_files(javaguide_root / "high-availability")),
                FolderImportPlan("high-performance", md_files(javaguide_root / "high-performance")),
            ),
        ),
        KnowledgeImportPlan(
            name="React Interview Questions",
            description="React 面试题与答案知识库，包含核心问答和代码练习题。",
            chunk_preset_id="qa",
            folders=(
                FolderImportPlan(
                    "coding-exercise",
                    (react_root / "coding-exercise" / "README.md",),
                ),
            ),
            root_files=(react_root / "README.md",),
        ),
        KnowledgeImportPlan(
            name="Waking-Up",
            description="后端面试笔记知识库，包含计网、操作系统、数据库、设计模式、Git 与 Python 手册。",
            chunk_preset_id="qa",
            root_files=(
                waking_root / "Computer Network.md",
                waking_root / "Database.md",
                waking_root / "Design Pattern.md",
                waking_root / "Git-ComdLine-REST.md",
                waking_root / "Operating Systems.md",
                waking_root / "Python Handbook.md",
            ),
        ),
    )


class ImportError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))

    async def __aenter__(self) -> "ApiClient":
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

    async def post(self, path: str, *, json_body: Any = None, files: Any = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.client.post(f"{self.base_url}{path}", json=json_body, files=files, params=params)
        if response.status_code >= 400:
            raise ImportError(f"POST {path} failed: {response.status_code} {response.text}")
        return response.json()

    async def put(self, path: str, *, json_body: Any = None) -> dict[str, Any]:
        response = await self.client.put(f"{self.base_url}{path}", json=json_body)
        if response.status_code >= 400:
            raise ImportError(f"PUT {path} failed: {response.status_code} {response.text}")
        return response.json()

    async def list_databases(self) -> list[dict[str, Any]]:
        data = await self.get("/knowledge/databases")
        return data.get("databases", [])

    async def get_database_info(self, db_id: str) -> dict[str, Any]:
        return await self.get(f"/knowledge/databases/{db_id}")

    async def ensure_database(self, plan: KnowledgeImportPlan) -> dict[str, Any]:
        for database in await self.list_databases():
            if database.get("name") == plan.name:
                db_id = database.get("db_id")
                if not db_id:
                    return database

                db_info = await self.get_database_info(db_id)
                current_params = db_info.get("additional_params") or {}
                desired_params = build_index_params(plan.chunk_preset_id)

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

        created = await self.post(
            "/knowledge/databases",
            json_body={
                "database_name": plan.name,
                "description": plan.description,
                "embed_model_name": DEFAULT_EMBED_MODEL,
                "kb_type": "openviking",
                "additional_params": build_index_params(plan.chunk_preset_id),
                "llm_info": {
                    "provider": "siliconflow",
                    "model_name": "Pro/deepseek-ai/DeepSeek-V3",
                },
            },
        )
        return created

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

    async def upload_file(self, db_id: str, file_path: Path) -> dict[str, Any]:
        mime_type, _ = mimetypes.guess_type(file_path.name)
        mime_type = mime_type or "text/markdown"
        with file_path.open("rb") as handle:
            files = {"file": (file_path.name, handle, mime_type)}
            return await self.post(f"/knowledge/files/upload", files=files, params={"db_id": db_id})

    async def add_documents(
        self,
        db_id: str,
        items: list[str],
        params: dict[str, Any],
    ) -> dict[str, Any]:
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
            status = task.get("status")
            if status in TERMINAL_TASK_STATUSES:
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
    return (filename.lower(), parent_id or "")


def build_expected_file_map(
    file_paths: list[Path],
    parent_id: str | None,
) -> dict[tuple[str, str], Path]:
    return {file_key(path.name, parent_id): path for path in file_paths}


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


def build_index_params(chunk_preset_id: str) -> dict[str, Any]:
    params: dict[str, Any] = {"chunk_preset_id": chunk_preset_id}
    if chunk_preset_id == "qa":
        params["qa_separator"] = QA_SEPARATOR
    return params


async def wait_for_queued_result(api: ApiClient, response: dict[str, Any]) -> dict[str, Any]:
    if response.get("status") == "queued":
        task_id = response.get("task_id")
        if not task_id:
            raise ImportError(f"Queued response is missing task_id: {response}")
        task = await api.wait_for_task(task_id)
        if task.get("status") != "success":
            raise ImportError(f"Task {task_id} failed: {task.get('error') or task}")
        return task
    return response


async def repair_file_states(
    api: ApiClient,
    db_id: str,
    expected_files: dict[tuple[str, str], Path],
    parent_id: str | None,
    chunk_preset_id: str,
    force_reindex: bool,
) -> dict[str, Any]:
    db_info = await api.get_database_info(db_id)
    current_files = extract_current_file_map(db_info)

    parse_ids: list[str] = []
    index_ids: list[str] = []
    missing_paths: list[Path] = []

    for key, source_path in expected_files.items():
        file_info = current_files.get(key)
        if not file_info:
            missing_paths.append(source_path)
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
        for key, source_path in expected_files.items():
            if source_path in missing_paths:
                continue
            file_info = refreshed_files.get(key)
            if not file_info:
                continue
            status = file_info.get("status")
            if status in {"parsed", "error_indexing"}:
                parse_repaired_ids.append(file_info["file_id"])

        all_index_ids = sorted(set(index_ids + parse_repaired_ids))
        if all_index_ids:
            await wait_for_queued_result(api, await api.index_documents(db_id, all_index_ids, build_index_params(chunk_preset_id)))

    return {"missing_paths": missing_paths}


async def import_batch(
    api: ApiClient,
    db_id: str,
    *,
    parent_id: str | None,
    file_paths: list[Path],
    chunk_preset_id: str,
    force_reindex: bool,
) -> dict[str, Any]:
    db_info = await api.get_database_info(db_id)
    current_files = extract_current_file_map(db_info)
    expected_map = build_expected_file_map(file_paths, parent_id)

    missing_to_upload: list[Path] = []
    existing_ready = 0
    for key, path in expected_map.items():
        existing = current_files.get(key)
        if existing and existing.get("status") in INDEXED_STATUSES and not force_reindex:
            existing_ready += 1
            continue
        if existing:
            continue
        missing_to_upload.append(path)

    upload_items: list[str] = []
    content_hashes: dict[str, str] = {}
    uploaded_names: list[str] = []

    for file_path in missing_to_upload:
        upload_result = await api.upload_file(db_id, file_path)
        upload_items.append(upload_result["file_path"])
        content_hashes[upload_result["file_path"]] = upload_result["content_hash"]
        uploaded_names.append(file_path.name)

    if upload_items:
        params = build_ingest_params(
            parent_id=parent_id,
            content_hashes=content_hashes,
            chunk_preset_id=chunk_preset_id,
        )
        await wait_for_queued_result(api, await api.add_documents(db_id, upload_items, params))

    repair_result = await repair_file_states(api, db_id, expected_map, parent_id, chunk_preset_id, force_reindex)

    unresolved: list[str] = []
    if repair_result["missing_paths"]:
        retry_items: list[str] = []
        retry_hashes: dict[str, str] = {}
        for file_path in repair_result["missing_paths"]:
            upload_result = await api.upload_file(db_id, file_path)
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
    for key, source_path in expected_map.items():
        file_info = final_files.get(key)
        if not file_info or file_info.get("status") not in INDEXED_STATUSES:
            unresolved.append(str(source_path))

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

    folder_ids: dict[str, str] = {}
    for folder in plan.folders:
        folder_ids[folder.name] = await api.ensure_folder(db_id, folder.name)

    batches_report: list[dict[str, Any]] = []

    for folder in plan.folders:
        parent_id = folder_ids[folder.name]
        folder_files = list(folder.files)
        for index in range(0, len(folder_files), batch_size):
            batch = folder_files[index : index + batch_size]
            print(f"[{plan.name}] importing folder {folder.name} batch {index // batch_size + 1}")
            result = await import_batch(
                api,
                db_id,
                parent_id=parent_id,
                file_paths=batch,
                chunk_preset_id=plan.chunk_preset_id,
                force_reindex=force_reindex,
            )
            batches_report.append({"scope": folder.name, "result": result})

    if plan.root_files:
        root_file_list = list(plan.root_files)
        for index in range(0, len(root_file_list), batch_size):
            batch = root_file_list[index : index + batch_size]
            print(f"[{plan.name}] importing root batch {index // batch_size + 1}")
            result = await import_batch(
                api,
                db_id,
                parent_id=None,
                file_paths=batch,
                chunk_preset_id=plan.chunk_preset_id,
                force_reindex=force_reindex,
            )
            batches_report.append({"scope": "root", "result": result})

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
        "JavaGuide": "什么是 CAS",
        "React Interview Questions": "What is React Fiber?",
        "Waking-Up": "TCP 三次握手为什么不是两次？",
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


async def run_import(base_url: str, username: str, password: str, batch_size: int, force_reindex: bool) -> dict[str, Any]:
    plans = build_import_plan()
    async with ApiClient(base_url, username, password) as api:
        database_reports = []
        for plan in plans:
            database_reports.append(await import_knowledge_plan(api, plan, batch_size=batch_size, force_reindex=force_reindex))

        all_databases = await api.list_databases()
        total_files = 0
        for report in database_reports:
            db_info = await api.get_database_info(report["db_id"])
            total_files += sum(1 for file in db_info.get("files", {}).values() if not file.get("is_folder"))

        query_results = await verify_queries(api, database_reports)

        summary = {
            "database_count": len(all_databases),
            "expected_database_count": 3,
            "total_file_count": total_files,
            "expected_total_file_count": 227,
            "databases": database_reports,
            "queries": query_results,
        }
        return summary


def parse_args() -> argparse.Namespace:
    default_username, default_password = read_default_credentials()
    parser = argparse.ArgumentParser(description="Import curated .knowledge interview data into the AI-interview knowledge base.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=default_username)
    parser.add_argument("--password", default=default_password)
    parser.add_argument("--batch-size", default=20, type=int)
    parser.add_argument("--force-reindex", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.username or not args.password:
        raise SystemExit("Missing admin credentials. Provide --username/--password or set AI_INTERVIEW_SUPER_ADMIN_* in .env.")

    summary = asyncio.run(run_import(args.base_url, args.username, args.password, args.batch_size, args.force_reindex))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
