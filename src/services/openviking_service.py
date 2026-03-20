from __future__ import annotations

import json
import os
import tempfile
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

    @staticmethod
    def build_kb_root_uri(db_id: str) -> str:
        return f"viking://resources/kbs/{db_id}"

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
        base_uri = cls.build_kb_root_uri(db_id)
        folder_segments = cls._build_folder_segments(record, records_by_id)
        file_segment = cls._sanitize_uri_segment(record.filename or record.file_id)
        folder_prefix = f"{'/'.join(folder_segments)}/" if folder_segments else ""
        return f"{base_uri}/{folder_prefix}{file_segment}__{record.file_id}.md"

    @staticmethod
    def _truncate_text(text: str, limit: int = 1200) -> str:
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit].rstrip()}..."

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
                build_index=True,
                summarize=False,
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

    async def remove_resume(self, resume: UserResume) -> None:
        await self.remove_resource(self.build_resume_uri(resume.user_id, resume.id))

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
