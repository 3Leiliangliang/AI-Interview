from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.config import config
from src.knowledge.utils.kb_utils import parse_minio_url
from src.storage.minio import get_minio_client
from src.utils import logger

try:
    from openviking import AsyncOpenViking
except ImportError as exc:  # pragma: no cover - exercised by runtime env
    AsyncOpenViking = None
    OPENVIKING_IMPORT_ERROR = exc
else:
    OPENVIKING_IMPORT_ERROR = None

    try:
        from openviking.storage.viking_fs import VikingFS
    except ImportError:  # pragma: no cover - exercised by runtime env
        VikingFS = None
    else:
        if not hasattr(VikingFS, "exists"):
            async def _vikingfs_exists(self, uri: str, ctx=None) -> bool:
                try:
                    await self.stat(uri, ctx=ctx)
                    return True
                except Exception:
                    return False

            VikingFS.exists = _vikingfs_exists

    try:
        from openviking.models.embedder import OpenAIDenseEmbedder
    except ImportError:  # pragma: no cover - exercised by runtime env
        OpenAIDenseEmbedder = None
    else:
        _orig_openai_dense_init = OpenAIDenseEmbedder.__init__

        def _patched_openai_dense_init(self, *args, **kwargs):
            _orig_openai_dense_init(self, *args, **kwargs)
            # SiliconFlow 的 BAAI/bge-m3 不接受 `dimensions` 参数（HTTP 400, code 20015）。
            # 保留 `_dimension` 供 get_dimension() 使用，但不再把它转发给 embeddings API。
            self.dimension = None

        OpenAIDenseEmbedder.__init__ = _patched_openai_dense_init

if TYPE_CHECKING:
    from src.storage.postgres.models_business import UserResume
    from src.storage.postgres.models_knowledge import KnowledgeFile


OPENVIKING_BACKEND = "openviking"
OPENVIKING_ENABLED_VALUES = {"1", "true", "yes", "on"}
DEFAULT_FIND_LIMIT = 5
FALLBACK_READ_LINES = 200
DEFAULT_OPENVIKING_API_BASE = "https://api.siliconflow.cn/v1"
DEFAULT_OPENVIKING_EMBEDDING_MODEL = "Pro/BAAI/bge-m3"
DEFAULT_OPENVIKING_VLM_MODEL = "Pro/deepseek-ai/DeepSeek-V3.2"


class OpenVikingService:
    def __init__(self) -> None:
        workspace = os.getenv("OPENVIKING_WORKSPACE") or str(Path(config.save_dir) / "openviking")
        self.workspace_dir = Path(workspace)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.config_file_path = Path(os.getenv("OPENVIKING_CONFIG_FILE") or (self.workspace_dir / "ov.conf"))
        self.sync_state_path = self.workspace_dir / "sync_state.json"
        self._client: AsyncOpenViking | None = None
        self._sync_state: dict[str, dict[str, str]] | None = None

    def is_enabled(self) -> bool:
        backend = (os.getenv("RAG_BACKEND") or "").strip().lower()
        enabled_flag = (os.getenv("OPENVIKING_ENABLED") or "").strip().lower()
        return backend == OPENVIKING_BACKEND or enabled_flag in OPENVIKING_ENABLED_VALUES

    def _ensure_enabled(self) -> None:
        if not self.is_enabled():
            raise RuntimeError("OpenViking 未启用，请设置 RAG_BACKEND=openviking")
        if AsyncOpenViking is None:
            raise RuntimeError(f"OpenViking 依赖未安装: {OPENVIKING_IMPORT_ERROR}")
        self._ensure_runtime_config()

    @staticmethod
    def _get_config_value(*env_names: str, default: str = "") -> str:
        for name in env_names:
            value = (os.getenv(name) or "").strip()
            if value:
                return value
        return default

    def _build_runtime_config(self) -> dict[str, Any]:
        embedding_api_key = self._get_config_value(
            "OPENVIKING_EMBEDDING_API_KEY",
            "OPENVIKING_API_KEY",
            "SILICONFLOW_API_KEY",
        )
        vlm_api_key = self._get_config_value(
            "OPENVIKING_VLM_API_KEY",
            "OPENVIKING_API_KEY",
            "SILICONFLOW_API_KEY",
        )

        if not embedding_api_key:
            raise RuntimeError("OpenViking 缺少 Embedding API Key，请配置 OPENVIKING_API_KEY 或 SILICONFLOW_API_KEY")
        if not vlm_api_key:
            raise RuntimeError("OpenViking 缺少 VLM API Key，请配置 OPENVIKING_VLM_API_KEY 或 SILICONFLOW_API_KEY")

        embedding_dimension = int(
            self._get_config_value("OPENVIKING_EMBEDDING_DIMENSION", default="1024")
        )

        return {
            "storage": {
                "workspace": str(self.workspace_dir.resolve()),
            },
            "log": {
                "level": self._get_config_value("OPENVIKING_LOG_LEVEL", default="INFO"),
                "output": self._get_config_value("OPENVIKING_LOG_OUTPUT", default="stdout"),
            },
            "embedding": {
                "dense": {
                    "api_base": self._get_config_value(
                        "OPENVIKING_EMBEDDING_API_BASE",
                        "OPENVIKING_API_BASE",
                        default=DEFAULT_OPENVIKING_API_BASE,
                    ),
                    "api_key": embedding_api_key,
                    "provider": self._get_config_value("OPENVIKING_EMBEDDING_PROVIDER", default="openai"),
                    "dimension": embedding_dimension,
                    "model": self._get_config_value(
                        "OPENVIKING_EMBEDDING_MODEL",
                        default=DEFAULT_OPENVIKING_EMBEDDING_MODEL,
                    ),
                },
                "max_concurrent": int(
                    self._get_config_value("OPENVIKING_EMBEDDING_MAX_CONCURRENT", default="10")
                ),
            },
            "vlm": {
                "api_base": self._get_config_value(
                    "OPENVIKING_VLM_API_BASE",
                    "OPENVIKING_API_BASE",
                    default=DEFAULT_OPENVIKING_API_BASE,
                ),
                "api_key": vlm_api_key,
                "provider": self._get_config_value("OPENVIKING_VLM_PROVIDER", default="openai"),
                "model": self._get_config_value("OPENVIKING_VLM_MODEL", default=DEFAULT_OPENVIKING_VLM_MODEL),
                "max_concurrent": int(self._get_config_value("OPENVIKING_VLM_MAX_CONCURRENT", default="100")),
            },
        }

    def _ensure_runtime_config(self) -> None:
        self.config_file_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = self._build_runtime_config()
        config_text = json.dumps(config_data, ensure_ascii=False, indent=2)

        current_text = ""
        if self.config_file_path.exists():
            current_text = self.config_file_path.read_text(encoding="utf-8")

        if current_text != config_text:
            self.config_file_path.write_text(config_text, encoding="utf-8")

        os.environ["OPENVIKING_CONFIG_FILE"] = str(self.config_file_path.resolve())

    async def _get_client(self) -> AsyncOpenViking:
        self._ensure_enabled()
        if self._client is None:
            self._client = AsyncOpenViking(path=str(self.workspace_dir))
            await self._client.initialize()
        return self._client

    async def _get_runtime_handles(self) -> tuple[Any, Any, Any, Any, Any]:
        client = await self._get_client()
        local_client = getattr(client, "_client", None)
        service = getattr(local_client, "service", None) or getattr(local_client, "_service", None)
        request_ctx = getattr(local_client, "_ctx", None)
        if service is None or request_ctx is None:
            raise RuntimeError("OpenViking local client is not available")

        vector_store = getattr(service, "vikingdb_manager", None)
        viking_fs = getattr(service, "viking_fs", None)
        embedder = getattr(viking_fs, "query_embedder", None) or getattr(service, "_embedder", None)
        if vector_store is None or embedder is None:
            raise RuntimeError("OpenViking vector search is not initialized")

        return client, local_client, service, request_ctx, vector_store, embedder

    def _load_sync_state(self) -> dict[str, dict[str, str]]:
        if self._sync_state is not None:
            return self._sync_state

        if not self.sync_state_path.exists():
            self._sync_state = {}
            return self._sync_state

        try:
            self._sync_state = json.loads(self.sync_state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load OpenViking sync state: %s", exc)
            self._sync_state = {}
        return self._sync_state

    def _save_sync_state(self) -> None:
        state = self._load_sync_state()
        self.sync_state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_saved_hash(self, uri: str) -> str | None:
        return self._load_sync_state().get(uri, {}).get("content_hash")

    def _set_synced(
        self,
        uri: str,
        content_hash: str,
        display_name: str = "",
        sync_metadata: dict[str, str] | None = None,
    ) -> None:
        payload = {
            "content_hash": content_hash,
            "display_name": display_name,
        }
        if sync_metadata:
            payload.update({key: value for key, value in sync_metadata.items() if value})
        self._load_sync_state()[uri] = payload
        self._save_sync_state()

    def _remove_synced(self, uri: str) -> None:
        state = self._load_sync_state()
        if uri in state:
            del state[uri]
            self._save_sync_state()

    @staticmethod
    def build_resume_uri(user_id: int, resume_id: int) -> str:
        return f"viking://resources/resumes/{user_id}/{resume_id}.md"

    @classmethod
    def build_session_root_uri(cls, user_id: str | int, thread_id: str) -> str:
        safe_user_id = cls._sanitize_uri_segment(str(user_id))
        safe_thread_id = cls._sanitize_uri_segment(thread_id)
        return f"viking://session/{safe_user_id}/{safe_thread_id}"

    @classmethod
    def build_session_attachment_uri(
        cls,
        user_id: str | int,
        thread_id: str,
        file_name: str,
    ) -> str:
        safe_name = cls._sanitize_uri_segment(file_name)
        if not safe_name.lower().endswith(".md"):
            safe_name = f"{safe_name}.md"
        return f"{cls.build_session_root_uri(user_id, thread_id)}/attachments/{safe_name}"

    @classmethod
    def build_session_archive_uri(
        cls,
        user_id: str | int,
        thread_id: str,
        archive_key: str,
    ) -> str:
        safe_key = cls._sanitize_uri_segment(archive_key)
        return f"{cls.build_session_root_uri(user_id, thread_id)}/history/{safe_key}.md"

    @classmethod
    def build_user_memory_root_uri(cls, user_id: str | int) -> str:
        safe_user_id = cls._sanitize_uri_segment(str(user_id))
        return f"viking://user/{safe_user_id}/memories"

    @classmethod
    def build_user_resume_memory_uri(cls, user_id: str | int, resume_id: int) -> str:
        return f"{cls.build_user_memory_root_uri(user_id)}/entities/resume-{resume_id}.md"

    @classmethod
    def build_agent_memory_root_uri(cls, user_id: str | int, agent_id: str) -> str:
        scope = cls._sanitize_uri_segment(f"{agent_id}-{user_id}")
        return f"viking://agent/{scope}/memories"

    @classmethod
    def build_agent_scope_uri(cls, user_id: str | int, agent_id: str) -> str:
        scope = cls._sanitize_uri_segment(f"{agent_id}-{user_id}")
        return f"viking://agent/{scope}"

    @classmethod
    def build_agent_case_memory_uri(
        cls,
        user_id: str | int,
        agent_id: str,
        thread_id: str,
    ) -> str:
        safe_thread_id = cls._sanitize_uri_segment(thread_id)
        return f"{cls.build_agent_memory_root_uri(user_id, agent_id)}/cases/{safe_thread_id}.md"

    @staticmethod
    def build_kb_root_uri(db_id: str) -> str:
        return f"viking://resources/kbs/{db_id}"

    @classmethod
    def build_kb_file_root_uri(
        cls,
        db_id: str,
        record: KnowledgeFile,
        records_by_id: dict[str, KnowledgeFile],
    ) -> str:
        base_uri = cls.build_kb_root_uri(db_id)
        folder_segments = cls._build_folder_segments(record, records_by_id)
        file_segment = cls._sanitize_uri_segment(record.filename or record.file_id)
        folder_prefix = f"{'/'.join(folder_segments)}/" if folder_segments else ""
        return f"{base_uri}/{folder_prefix}{file_segment}__{record.file_id}"

    @staticmethod
    def build_legacy_kb_file_uri(db_id: str, file_id: str) -> str:
        return f"{OpenVikingService.build_kb_root_uri(db_id)}/{file_id}.md"

    @staticmethod
    def _sanitize_uri_segment(segment: str) -> str:
        text = (segment or "").strip().strip("/")
        if not text:
            return "untitled"

        sanitized: list[str] = []
        for char in text:
            if char.isalnum() or char in {"-", "_", ".", " "}:
                sanitized.append(char)
            else:
                sanitized.append("_")

        return "".join(sanitized).strip().replace(" ", "_") or "untitled"

    @classmethod
    def _build_kb_file_resource_key(cls, db_id: str, file_id: str) -> str:
        return f"kb_file:{db_id}:{file_id}"

    @classmethod
    def _build_folder_segments(
        cls,
        record: KnowledgeFile,
        records_by_id: dict[str, KnowledgeFile],
    ) -> list[str]:
        segments: list[str] = []
        current_parent_id = record.parent_id

        while current_parent_id:
            parent = records_by_id.get(current_parent_id)
            if parent is None:
                break
            segments.append(cls._sanitize_uri_segment(parent.filename or parent.file_id))
            current_parent_id = parent.parent_id

        segments.reverse()
        return segments

    @classmethod
    def build_kb_file_uri(
        cls,
        db_id: str,
        record: KnowledgeFile,
        records_by_id: dict[str, KnowledgeFile],
    ) -> str:
        return f"{cls.build_kb_file_root_uri(db_id, record, records_by_id)}/document.md"

    @classmethod
    def build_kb_chunk_uri(
        cls,
        db_id: str,
        record: KnowledgeFile,
        records_by_id: dict[str, KnowledgeFile],
        chunk_id: str,
        chunk_index: int,
    ) -> str:
        safe_chunk_id = cls._sanitize_uri_segment(chunk_id or f"chunk-{chunk_index}")
        return (
            f"{cls.build_kb_file_root_uri(db_id, record, records_by_id)}"
            f"/chunks/{chunk_index:04d}__{safe_chunk_id}.md"
        )

    @staticmethod
    def _truncate_text(text: str, limit: int = 1200) -> str:
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit].rstrip()}..."

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha1((text or "").encode("utf-8")).hexdigest()

    @classmethod
    def normalize_context_uri(
        cls,
        uri: str,
        *,
        user_id: str | int,
        thread_id: str | None = None,
        agent_id: str | None = None,
    ) -> str:
        normalized = (uri or "").strip()
        if not normalized or normalized in {"auto", "/viking", "/viking/"}:
            return "viking://"

        if normalized.startswith("viking://"):
            return normalized.rstrip("/") or "viking://"

        if normalized.startswith("/viking/"):
            normalized = normalized.removeprefix("/viking")

        pure = PurePosixPath(normalized if normalized.startswith("/") else f"/{normalized}")
        parts = [part for part in pure.parts if part not in {"/", ""}]
        if not parts:
            return "viking://"

        if parts[0] == "session" and len(parts) >= 2 and parts[1] == "current":
            if not thread_id:
                raise ValueError("thread_id is required for /session/current paths")
            base = cls.build_session_root_uri(user_id, thread_id)
            suffix = "/".join(parts[2:])
            return f"{base}/{suffix}".rstrip("/") if suffix else base

        if parts[0] == "user" and len(parts) >= 2 and parts[1] == "current":
            base = f"viking://user/{cls._sanitize_uri_segment(str(user_id))}"
            suffix = "/".join(parts[2:])
            return f"{base}/{suffix}".rstrip("/") if suffix else base

        if parts[0] == "agent" and len(parts) >= 2 and parts[1] == "current":
            if not agent_id:
                raise ValueError("agent_id is required for /agent/current paths")
            base = cls.build_agent_scope_uri(user_id, agent_id)
            suffix = "/".join(parts[2:])
            return f"{base}/{suffix}".rstrip("/") if suffix else base

        return f"viking://{'/'.join(parts)}".rstrip("/")

    @staticmethod
    def _normalize_file_keyword(file_name: str | None) -> str:
        return (file_name or "").strip().lower()

    @staticmethod
    def _file_matches(record: KnowledgeFile, file_name: str | None = None) -> bool:
        keyword = OpenVikingService._normalize_file_keyword(file_name)
        if not keyword:
            return True

        candidates = [
            record.filename or "",
            record.original_filename or "",
            record.file_id or "",
        ]
        lowered = [item.lower() for item in candidates if item]
        return any(keyword in item or item in keyword for item in lowered)

    @staticmethod
    def _parent_uri(uri: str) -> str | None:
        normalized = uri.rstrip("/")
        if "/" not in normalized.removeprefix("viking://"):
            return None
        return normalized.rsplit("/", 1)[0]

    async def _resource_exists(self, uri: str) -> bool:
        client = await self._get_client()
        try:
            await client.stat(uri)
            return True
        except Exception:
            return False

    async def _ensure_parent_dirs(self, uri: str) -> None:
        parent_uri = self._parent_uri(uri)
        if not parent_uri:
            return

        client = await self._get_client()
        path = parent_uri.removeprefix("viking://").strip("/")
        if not path:
            return

        segments = path.split("/")
        current_uri = "viking://"
        for segment in segments:
            current_uri = f"{current_uri}{segment}" if current_uri.endswith("://") else f"{current_uri}/{segment}"
            try:
                await client.mkdir(current_uri)
            except Exception as exc:
                logger.debug("Skip creating OpenViking dir %s: %s", current_uri, exc)

    async def _write_temp_markdown(self, content: str) -> str:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".md",
            delete=False,
            dir=self.workspace_dir,
        ) as temp_file:
            temp_file.write(content)
            return temp_file.name

    def _find_synced_uri(self, *, resource_key: str) -> str | None:
        for uri, item in self._load_sync_state().items():
            if item.get("resource_key") == resource_key:
                return uri
        return None

    async def sync_text_resource(
        self,
        *,
        uri: str,
        content: str,
        content_hash: str,
        display_name: str = "",
        sync_metadata: dict[str, str] | None = None,
        summarize: bool = False,
        build_index: bool = True,
    ) -> str:
        if not content.strip():
            raise ValueError("Content synced to OpenViking cannot be empty")

        saved_hash = self._get_saved_hash(uri)
        if saved_hash == content_hash:
            return uri

        client = await self._get_client()
        await self._ensure_parent_dirs(uri)

        if await self._resource_exists(uri):
            await client.rm(uri, recursive=True)

        temp_path = await self._write_temp_markdown(content)
        try:
            await client.add_resource(
                path=temp_path,
                to=uri,
                wait=True,
                build_index=build_index,
                summarize=summarize,
            )
            self._set_synced(
                uri,
                content_hash=content_hash,
                display_name=display_name,
                sync_metadata=sync_metadata,
            )
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

        return uri

    async def remove_resource(self, uri: str) -> None:
        if not self.is_enabled():
            return

        client = await self._get_client()
        if await self._resource_exists(uri):
            await client.rm(uri, recursive=True)
        self._remove_synced(uri)

    async def build_index_resources(self, resource_uris: str | list[str]) -> dict[str, Any]:
        client = await self._get_client()
        return await client.build_index(resource_uris)

    async def find_resources(
        self,
        *,
        query_text: str,
        target_uri: str,
        limit: int = DEFAULT_FIND_LIMIT,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        client = await self._get_client()
        result = await client.find(
            query=query_text,
            target_uri=target_uri,
            limit=limit,
            score_threshold=score_threshold,
        )
        resources = getattr(result, "resources", None)
        if resources is None and isinstance(result, dict):
            resources = result.get("resources", [])
        resources = resources or []

        normalized_results: list[dict[str, Any]] = []
        for item in resources:
            normalized_results.append(
                {
                    "uri": getattr(item, "uri", None) or item.get("uri", ""),
                    "score": getattr(item, "score", None) if not isinstance(item, dict) else item.get("score"),
                    "abstract": getattr(item, "abstract", None)
                    if not isinstance(item, dict)
                    else item.get("abstract", ""),
                    "overview": getattr(item, "overview", None)
                    if not isinstance(item, dict)
                    else item.get("overview", ""),
                    "match_reason": getattr(item, "match_reason", None)
                    if not isinstance(item, dict)
                    else item.get("match_reason", ""),
                }
            )

        normalized_results.sort(key=lambda item: item.get("score") or 0.0, reverse=True)
        return normalized_results[:limit]

    async def search_resource_vectors(
        self,
        *,
        query_text: str,
        target_uri: str,
        limit: int = DEFAULT_FIND_LIMIT,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        _, _, _, request_ctx, vector_store, embedder = await self._get_runtime_handles()

        embed_result = await asyncio.to_thread(embedder.embed, query_text)
        records = await vector_store.search_in_tenant(
            ctx=request_ctx,
            query_vector=getattr(embed_result, "dense_vector", None),
            sparse_query_vector=getattr(embed_result, "sparse_vector", None) or None,
            context_type="resource",
            target_directories=[target_uri] if target_uri else None,
            limit=limit,
        )

        normalized_results: list[dict[str, Any]] = []
        for item in records or []:
            score = item.get("_score") or 0.0
            if score_threshold is not None and score <= score_threshold:
                continue
            normalized_results.append(
                {
                    "uri": item.get("uri", ""),
                    "parent_uri": item.get("parent_uri", ""),
                    "score": score,
                    "abstract": item.get("abstract", ""),
                    "name": item.get("name", ""),
                    "level": item.get("level"),
                }
            )

        normalized_results.sort(key=lambda item: item.get("score") or 0.0, reverse=True)
        return normalized_results[:limit]

    async def delete_resource_vectors(self, target_uri: str) -> int:
        if not target_uri:
            return 0

        _, _, _, request_ctx, vector_store, _ = await self._get_runtime_handles()
        from openviking.storage.expr import PathScope

        records = await vector_store.filter(
            PathScope("uri", target_uri, depth=-1),
            limit=100000,
            output_fields=["uri"],
            ctx=request_ctx,
        )
        ids = [record.get("id") for record in records if record.get("id")]
        if not ids:
            return 0
        return await vector_store.delete(ids, ctx=request_ctx)

    async def upsert_resource_vector(
        self,
        *,
        uri: str,
        parent_uri: str,
        content: str,
        name: str,
        abstract: str = "",
        level: int = 2,
    ) -> str:
        _, _, _, request_ctx, vector_store, embedder = await self._get_runtime_handles()
        embed_result = await asyncio.to_thread(embedder.embed, content)
        account_id = str(getattr(request_ctx, "account_id", "default") or "default")
        owner_space = ""
        user = getattr(request_ctx, "user", None)
        if user is not None and hasattr(user, "user_space_name"):
            owner_space = user.user_space_name() or ""

        timestamp = datetime.now(timezone.utc).isoformat()
        record_id = hashlib.md5(f"{account_id}:{uri}".encode("utf-8")).hexdigest()
        return await vector_store.upsert(
            {
                "id": record_id,
                "uri": uri,
                "type": "file",
                "context_type": "resource",
                "vector": getattr(embed_result, "dense_vector", None),
                "sparse_vector": getattr(embed_result, "sparse_vector", None) or None,
                "created_at": timestamp,
                "updated_at": timestamp,
                "active_count": 0,
                "parent_uri": parent_uri,
                "level": level,
                "name": name,
                "description": "",
                "tags": "",
                "abstract": abstract,
                "account_id": account_id,
                "owner_space": owner_space,
            },
            ctx=request_ctx,
        )

    async def sync_resume(self, resume: UserResume) -> str:
        uri = self.build_resume_uri(resume.user_id, resume.id)
        return await self.sync_text_resource(
            uri=uri,
            content=resume.markdown_content or "",
            content_hash=resume.content_hash or str(resume.id),
            display_name=resume.filename,
            sync_metadata={
                "resource_key": f"resume:{resume.user_id}:{resume.id}",
                "user_id": str(resume.user_id),
                "resume_id": str(resume.id),
            },
        )

    @staticmethod
    def _build_resume_memory_content(resume: UserResume) -> str:
        updated_at = resume.updated_at.isoformat() if resume.updated_at else ""
        return (
            f"# 简历历史\n\n"
            f"- 简历ID：{resume.id}\n"
            f"- 文件名：{resume.filename}\n"
            f"- 更新时间：{updated_at}\n\n"
            f"## 简历内容\n\n"
            f"{resume.markdown_content or ''}"
        ).strip()

    async def sync_resume_memory(self, resume: UserResume) -> str:
        uri = self.build_user_resume_memory_uri(resume.user_id, resume.id)
        content = self._build_resume_memory_content(resume)
        return await self.sync_text_resource(
            uri=uri,
            content=content,
            content_hash=resume.content_hash or self._content_hash(content),
            display_name=resume.filename,
            sync_metadata={
                "resource_key": f"user_resume_memory:{resume.user_id}:{resume.id}",
                "user_id": str(resume.user_id),
                "resume_id": str(resume.id),
                "memory_type": "resume_history",
            },
            summarize=True,
        )

    async def remove_resume(self, resume: UserResume) -> None:
        await self.remove_resource(self.build_resume_uri(resume.user_id, resume.id))

    async def remove_resume_memory(self, resume: UserResume) -> None:
        await self.remove_resource(self.build_user_resume_memory_uri(resume.user_id, resume.id))

    async def sync_thread_attachment(
        self,
        *,
        user_id: str | int,
        thread_id: str,
        file_name: str,
        markdown_content: str,
    ) -> str:
        uri = self.build_session_attachment_uri(user_id=user_id, thread_id=thread_id, file_name=file_name)
        await self.sync_text_resource(
            uri=uri,
            content=markdown_content,
            content_hash=self._content_hash(markdown_content),
            display_name=file_name,
            sync_metadata={
                "resource_key": f"thread_attachment:{user_id}:{thread_id}:{file_name}",
                "user_id": str(user_id),
                "thread_id": thread_id,
                "file_name": file_name,
            },
        )
        return uri

    async def remove_thread_attachment(
        self,
        *,
        user_id: str | int,
        thread_id: str,
        file_name: str,
    ) -> None:
        await self.remove_resource(
            self.build_session_attachment_uri(user_id=user_id, thread_id=thread_id, file_name=file_name)
        )

    async def sync_kb_file(
        self,
        db_id: str,
        record: KnowledgeFile,
        records_by_id: dict[str, KnowledgeFile],
        previous_uri: str | None = None,
    ) -> str | None:
        if record.is_folder:
            return None
        return await self._sync_kb_record(db_id, record, records_by_id, previous_uri=previous_uri)

    async def sync_kb_file_by_id(self, db_id: str, file_id: str, previous_uri: str | None = None) -> str | None:
        from src.repositories.knowledge_file_repository import KnowledgeFileRepository

        repo = KnowledgeFileRepository()
        record = await repo.get_by_file_id(file_id)
        if record is None or record.db_id != db_id:
            return None
        records_by_id = {item.file_id: item for item in await repo.list_by_db_id(db_id)}
        return await self.sync_kb_file(db_id, record, records_by_id, previous_uri=previous_uri)

    async def remove_kb_file(self, db_id: str, file_id: str) -> None:
        from src.repositories.knowledge_file_repository import KnowledgeFileRepository

        repo = KnowledgeFileRepository()
        record = await repo.get_by_file_id(file_id)
        if record is not None and record.db_id == db_id:
            records_by_id = {item.file_id: item for item in await repo.list_by_db_id(db_id)}
            await self.remove_resource(self.build_kb_file_uri(db_id, record, records_by_id))

        resource_key = self._build_kb_file_resource_key(db_id, file_id)
        synced_uri = self._find_synced_uri(resource_key=resource_key)
        if synced_uri:
            await self.remove_resource(synced_uri)

        await self.remove_resource(self.build_legacy_kb_file_uri(db_id, file_id))

    async def remove_kb_database(self, db_id: str) -> None:
        await self.remove_resource(self.build_kb_root_uri(db_id))

    async def _read_minio_text(self, file_url: str) -> str:
        bucket_name, object_name = parse_minio_url(file_url)
        minio_client = get_minio_client()
        content = await minio_client.adownload_file(bucket_name, object_name)
        return content.decode("utf-8")

    async def _load_kb_markdown(self, record: KnowledgeFile) -> str:
        if record.markdown_file:
            return await self._read_minio_text(record.markdown_file)
        return ""

    async def _sync_kb_record(
        self,
        db_id: str,
        record: KnowledgeFile,
        records_by_id: dict[str, KnowledgeFile],
        previous_uri: str | None = None,
    ) -> str | None:
        uri = self.build_kb_file_uri(db_id, record, records_by_id)
        resource_key = self._build_kb_file_resource_key(db_id, record.file_id)
        previous_synced_uri = previous_uri or self._find_synced_uri(resource_key=resource_key)
        legacy_uri = self.build_legacy_kb_file_uri(db_id, record.file_id)

        for stale_uri in {previous_synced_uri, legacy_uri}:
            if stale_uri and stale_uri != uri:
                await self.remove_resource(stale_uri)

        content_hash = record.content_hash or record.file_id
        if self._get_saved_hash(uri) == content_hash:
            return uri

        content = await self._load_kb_markdown(record)
        if not content.strip():
            return None

        return await self.sync_text_resource(
            uri=uri,
            content=content,
            content_hash=content_hash,
            display_name=record.original_filename or record.filename,
            sync_metadata={
                "resource_key": resource_key,
                "db_id": db_id,
                "file_id": record.file_id,
            },
        )

    async def _cleanup_stale_kb_resources(self, db_id: str, current_uris: set[str]) -> None:
        prefix = f"{self.build_kb_root_uri(db_id)}/"
        stale_uris = [uri for uri in self._load_sync_state() if uri.startswith(prefix) and uri not in current_uris]
        for uri in stale_uris:
            try:
                await self.remove_resource(uri)
            except Exception as exc:
                logger.warning("Failed to cleanup stale OpenViking resource %s: %s", uri, exc)

    @staticmethod
    def _stringify_message_content(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list | dict):
            return json.dumps(content, ensure_ascii=False, indent=2)
        return str(content).strip()

    def _build_session_archive_content(self, messages: list[Any]) -> str:
        lines = ["# Session Archive", ""]
        for index, msg in enumerate(messages, start=1):
            role = getattr(msg, "type", None) or getattr(msg, "role", None) or "message"
            name = getattr(msg, "name", None)
            lines.append(f"## {index}. {role}{f' ({name})' if name else ''}")

            tool_call_id = getattr(msg, "tool_call_id", None)
            if tool_call_id:
                lines.append(f"- tool_call_id: {tool_call_id}")

            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                lines.append("- tool_calls:")
                lines.append("```json")
                lines.append(json.dumps(tool_calls, ensure_ascii=False, indent=2))
                lines.append("```")

            content = self._stringify_message_content(getattr(msg, "content", ""))
            lines.append("")
            lines.append(content or "(empty)")
            lines.append("")

        return "\n".join(lines).strip()

    async def _read_summary(self, uri: str) -> dict[str, str]:
        client = await self._get_client()
        abstract = ""
        overview = ""

        try:
            abstract = (await client.abstract(uri)).strip()
        except Exception:
            abstract = ""

        try:
            overview = (await client.overview(uri)).strip()
        except Exception:
            overview = ""

        return {"abstract": abstract, "overview": overview}

    async def archive_session_messages(
        self,
        *,
        user_id: str | int,
        thread_id: str,
        messages: list[Any],
    ) -> dict[str, str]:
        content = self._build_session_archive_content(messages)
        content_hash = self._content_hash(content)
        uri = self.build_session_archive_uri(
            user_id=user_id,
            thread_id=thread_id,
            archive_key=f"archive-{content_hash[:12]}",
        )

        await self.sync_text_resource(
            uri=uri,
            content=content,
            content_hash=content_hash,
            display_name=f"{thread_id}-archive",
            sync_metadata={
                "resource_key": f"session_archive:{user_id}:{thread_id}:{content_hash[:12]}",
                "user_id": str(user_id),
                "thread_id": thread_id,
                "archive_type": "session_context",
            },
            summarize=True,
        )
        summary = await self._read_summary(uri)
        return {"uri": uri, **summary}

    async def get_context_block(
        self,
        *,
        user_id: str | int,
        thread_id: str,
        query_text: str,
        agent_id: str | None = None,
        include_session: bool = True,
        include_user_memory: bool = True,
        include_agent_memory: bool = True,
    ) -> str:
        if not self.is_enabled():
            return ""

        target_uris: list[str] = []
        if include_session:
            target_uris.append(self.build_session_root_uri(user_id, thread_id))
        if include_user_memory:
            target_uris.append(self.build_user_memory_root_uri(user_id))
        if include_agent_memory and agent_id:
            target_uris.append(self.build_agent_memory_root_uri(user_id, agent_id))

        if not target_uris:
            return ""

        results = await self._find_in_many(query_text=query_text, target_uris=target_uris)
        if not results:
            return ""

        lines = ["以下是从 OpenViking 检索到的相关上下文，请仅在确有帮助时使用：", ""]
        for index, item in enumerate(results, start=1):
            uri = item.get("uri", "")
            if uri.startswith("viking://session/"):
                source = "会话归档"
            elif uri.startswith("viking://user/"):
                source = "用户记忆"
            elif uri.startswith("viking://agent/"):
                source = "Agent 记忆"
            else:
                source = "外部上下文"

            excerpt = item.get("abstract") or item.get("overview") or item.get("match_reason") or ""
            lines.append(f"{index}. [{source}] {uri}")
            if excerpt:
                lines.append(f"   {self._truncate_text(excerpt, limit=500)}")

        return "\n".join(lines)

    async def sync_interview_case_memory(
        self,
        *,
        user_id: str | int,
        agent_id: str,
        thread_id: str,
        user_query: str,
        summary_content: str,
        scorecard: dict[str, Any] | None = None,
    ) -> str:
        uri = self.build_agent_case_memory_uri(user_id=user_id, agent_id=agent_id, thread_id=thread_id)
        scorecard_text = ""
        if scorecard:
            scorecard_text = (
                "\n\n## 评分卡\n\n```json\n"
                f"{json.dumps(scorecard, ensure_ascii=False, indent=2)}\n"
                "```"
            )

        content = (
            f"# 面试案例沉淀\n\n"
            f"- 线程ID：{thread_id}\n"
            f"- Agent：{agent_id}\n"
            f"- 触发问题：{user_query}\n\n"
            f"## 面试总结\n\n"
            f"{summary_content.strip()}"
            f"{scorecard_text}"
        ).strip()

        await self.sync_text_resource(
            uri=uri,
            content=content,
            content_hash=self._content_hash(content),
            display_name=thread_id,
            sync_metadata={
                "resource_key": f"interview_case:{user_id}:{agent_id}:{thread_id}",
                "user_id": str(user_id),
                "thread_id": thread_id,
                "agent_id": agent_id,
                "memory_type": "interview_case",
            },
            summarize=True,
        )
        return uri

    async def _find(self, query_text: str, target_uri: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        result = await client.find(query=query_text, target_uri=target_uri, limit=DEFAULT_FIND_LIMIT)
        resources = getattr(result, "resources", None)
        if resources is None and isinstance(result, dict):
            resources = result.get("resources", [])
        resources = resources or []

        normalized_results: list[dict[str, Any]] = []
        for item in resources:
            normalized_results.append(
                {
                    "uri": getattr(item, "uri", None) or item.get("uri", ""),
                    "score": getattr(item, "score", None) if not isinstance(item, dict) else item.get("score"),
                    "abstract": getattr(item, "abstract", None)
                    if not isinstance(item, dict)
                    else item.get("abstract", ""),
                    "overview": getattr(item, "overview", None)
                    if not isinstance(item, dict)
                    else item.get("overview", ""),
                    "match_reason": getattr(item, "match_reason", None)
                    if not isinstance(item, dict)
                    else item.get("match_reason", ""),
                }
            )

        normalized_results.sort(key=lambda item: item.get("score") or 0.0, reverse=True)
        return normalized_results[:DEFAULT_FIND_LIMIT]

    async def _find_in_many(self, query_text: str, target_uris: list[str]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for uri in target_uris:
            merged.extend(await self._find(query_text=query_text, target_uri=uri))

        merged.sort(key=lambda item: item.get("score") or 0.0, reverse=True)
        return merged[:DEFAULT_FIND_LIMIT]

    async def list_uri(self, uri: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        items = await client.ls(uri)
        normalized: list[dict[str, Any]] = []
        for item in items or []:
            if isinstance(item, dict):
                raw_path = item.get("path") or item.get("uri") or item.get("name") or ""
                is_dir = item.get("is_dir")
                if is_dir is None:
                    is_dir = item.get("type") == "dir" or str(raw_path).endswith("/")
                normalized.append(
                    {
                        "path": str(raw_path),
                        "name": str(item.get("name") or Path(str(raw_path).rstrip("/")).name),
                        "is_dir": bool(is_dir),
                        "size": int(item.get("size") or 0),
                        "modified_at": str(item.get("modified_at") or ""),
                    }
                )
            else:
                raw_path = str(item)
                normalized.append(
                    {
                        "path": raw_path,
                        "name": Path(raw_path.rstrip("/")).name,
                        "is_dir": raw_path.endswith("/"),
                        "size": 0,
                        "modified_at": "",
                    }
                )
        return normalized

    async def read_uri(self, uri: str, offset: int = 0, limit: int = 2000) -> str:
        client = await self._get_client()
        return await client.read(uri, offset=offset, limit=limit)

    async def grep_uri(self, uri: str, pattern: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        result = await client.grep(uri=uri, pattern=pattern, case_insensitive=False)
        if isinstance(result, dict):
            matches = result.get("matches") or result.get("results") or []
            return [item for item in matches if isinstance(item, dict)]
        return []

    async def glob_uri(self, pattern: str, uri: str = "viking://") -> list[dict[str, Any]]:
        client = await self._get_client()
        result = await client.glob(pattern=pattern, uri=uri)
        if isinstance(result, dict):
            matches = result.get("matches") or result.get("results") or result.get("paths") or []
            normalized: list[dict[str, Any]] = []
            for item in matches:
                if isinstance(item, dict):
                    normalized.append(item)
                else:
                    normalized.append({"path": str(item)})
            return normalized
        return []

    async def relations_uri(self, uri: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        result = await client.relations(uri)
        normalized: list[dict[str, Any]] = []
        for item in result or []:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "uri": str(item.get("uri") or ""),
                        "reason": str(item.get("reason") or ""),
                    }
                )
            else:
                normalized.append({"uri": str(item), "reason": ""})
        return normalized

    async def query_context(
        self,
        *,
        user_id: str | int,
        thread_id: str,
        query_text: str,
        agent_id: str | None = None,
        target_uri: str = "auto",
    ) -> str:
        if target_uri == "auto":
            target_uris = [
                self.build_session_root_uri(user_id, thread_id),
                f"viking://user/{self._sanitize_uri_segment(str(user_id))}",
            ]
            if agent_id:
                target_uris.append(self.build_agent_scope_uri(user_id, agent_id))
            results = await self._find_in_many(query_text=query_text, target_uris=target_uris)
        else:
            resolved_uri = self.normalize_context_uri(
                target_uri,
                user_id=user_id,
                thread_id=thread_id,
                agent_id=agent_id,
            )
            results = await self._find(query_text=query_text, target_uri=resolved_uri)

        if not results:
            return f"未在 OpenViking 中检索到与“{query_text}”相关的上下文。"

        lines = [f"OpenViking 检索：{query_text}", "", "命中结果："]
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {item.get('uri', '')}")
            score = item.get("score")
            if isinstance(score, int | float):
                lines.append(f"   相关度：{score:.4f}")
            excerpt = item.get("abstract") or item.get("overview") or item.get("match_reason") or ""
            if excerpt:
                lines.append(f"   内容：{self._truncate_text(excerpt, limit=500)}")
        return "\n".join(lines)

    async def _read_resource_excerpt(self, uri: str) -> str:
        client = await self._get_client()
        try:
            return await client.read(uri, limit=FALLBACK_READ_LINES)
        except Exception as exc:
            logger.warning("Failed to read OpenViking resource %s: %s", uri, exc)
            return ""

    @staticmethod
    def _resolve_display_name(uri: str, name_mapping: dict[str, str]) -> str:
        if not uri:
            return "Document excerpt"

        exact_name = name_mapping.get(uri)
        if exact_name:
            return exact_name

        for base_uri, display_name in name_mapping.items():
            normalized_base = base_uri.rstrip("/")
            if uri == normalized_base or uri.startswith(f"{normalized_base}/"):
                return display_name

        if uri.startswith("viking://resources/resumes/"):
            return "Resume excerpt"
        if uri.startswith("viking://resources/kbs/"):
            return "Knowledge excerpt"
        return "Document excerpt"

    def _format_results(
        self,
        *,
        kb_name: str,
        query_text: str,
        results: list[dict[str, Any]],
        name_mapping: dict[str, str],
    ) -> str:
        if not results:
            return f"知识库：{kb_name}\n检索问题：{query_text}\n未检索到相关内容。"

        lines = [f"知识库：{kb_name}", f"检索问题：{query_text}", "", "命中内容："]
        for index, item in enumerate(results, start=1):
            file_label = self._resolve_display_name(item.get("uri", ""), name_mapping)
            lines.append(f"{index}. 文件：{file_label}")
            score = item.get("score")
            if isinstance(score, int | float):
                lines.append(f"   相关度：{score:.4f}")

            excerpt = item.get("abstract") or item.get("overview") or item.get("match_reason") or ""
            if excerpt:
                lines.append(f"   内容：{self._truncate_text(excerpt)}")

        return "\n".join(lines)

    def _format_fallback_excerpt(self, *, kb_name: str, query_text: str, file_label: str, content: str) -> str:
        excerpt = self._truncate_text(content, limit=2000)
        return (
            f"知识库：{kb_name}\n"
            f"检索问题：{query_text}\n"
            f"未检索到高相关片段，以下是“{file_label}”的内容节选：\n\n"
            f"{excerpt}"
        )

    async def query_resume(self, resume: UserResume, query_text: str) -> str:
        uri = await self.sync_resume(resume)
        results = await self._find(query_text=query_text, target_uri=uri)
        if results:
            return self._format_results(
                kb_name="我的简历",
                query_text=query_text,
                results=results,
                name_mapping={uri: resume.filename},
            )

        content = await self._read_resource_excerpt(uri)
        if not content.strip():
            content = resume.markdown_content or ""

        return self._format_fallback_excerpt(
            kb_name="我的简历",
            query_text=query_text,
            file_label=resume.filename,
            content=content,
        )

    async def query_database(self, db_id: str, kb_name: str, query_text: str, file_name: str | None = None) -> str:
        from src.repositories.knowledge_file_repository import KnowledgeFileRepository

        repo = KnowledgeFileRepository()
        all_records = [
            record
            for record in await repo.list_by_db_id(db_id)
            if not record.is_folder and record.status != "failed"
        ]
        if not all_records:
            return f"知识库“{kb_name}”暂无可检索文件"

        matched_records = [record for record in all_records if self._file_matches(record, file_name=file_name)]
        if not matched_records:
            return f"知识库“{kb_name}”中没有匹配文件“{file_name}”"

        records_by_id = {record.file_id: record for record in all_records}
        current_uris = {self.build_kb_file_uri(db_id, record, records_by_id) for record in all_records}
        await self._cleanup_stale_kb_resources(db_id, current_uris=current_uris)

        synced_uris: list[str] = []
        name_mapping: dict[str, str] = {}
        for record in matched_records:
            try:
                uri = await self._sync_kb_record(db_id, record, records_by_id)
            except Exception as exc:
                logger.warning("Failed to sync knowledge file %s to OpenViking: %s", record.file_id, exc)
                continue

            if not uri:
                continue

            synced_uris.append(uri)
            name_mapping[uri] = record.original_filename or record.filename

        if not synced_uris:
            return f"知识库“{kb_name}”暂无可被 OpenViking 检索的解析内容"

        if file_name:
            results = await self._find_in_many(query_text=query_text, target_uris=synced_uris)
        else:
            results = await self._find(query_text=query_text, target_uri=self.build_kb_root_uri(db_id))

        if results:
            return self._format_results(
                kb_name=kb_name,
                query_text=query_text,
                results=results,
                name_mapping=name_mapping,
            )

        if len(synced_uris) == 1:
            excerpt = await self._read_resource_excerpt(synced_uris[0])
            if excerpt.strip():
                return self._format_fallback_excerpt(
                    kb_name=kb_name,
                    query_text=query_text,
                    file_label=name_mapping.get(synced_uris[0], synced_uris[0]),
                    content=excerpt,
                )

        return f"知识库：{kb_name}\n检索问题：{query_text}\n未检索到相关内容。"


openviking_service = OpenVikingService()
