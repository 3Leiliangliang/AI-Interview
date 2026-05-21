from __future__ import annotations

from pathlib import PurePosixPath
from types import SimpleNamespace
from typing import Any

from src.knowledge.base import FileStatus, KnowledgeBase
from src.knowledge.chunking.ragflow_like.dispatcher import chunk_markdown
from src.knowledge.chunking.ragflow_like.presets import resolve_chunk_processing_params
from src.services.openviking_service import openviking_service
from src.utils import logger
from src.utils.datetime_utils import utc_isoformat


INDEXED_FILE_STATUSES = {FileStatus.INDEXED, FileStatus.DONE}
MAX_VECTOR_CHUNK_CHARS = 6000


class OpenVikingKB(KnowledgeBase):
    """基于 OpenViking 的统一知识库实现。"""

    def __init__(self, work_dir: str, **kwargs):
        super().__init__(work_dir)
        # _metadata_lock is now provided by the base class (see KnowledgeBase.__init__)

    @property
    def kb_type(self) -> str:
        return "openviking"

    async def _create_kb_instance(self, db_id: str, config: dict) -> Any:
        return {"db_id": db_id, "config": config}

    async def _initialize_kb_instance(self, instance: Any) -> None:
        return None

    def _build_record_map(self, db_id: str) -> dict[str, SimpleNamespace]:
        return {
            current_file_id: SimpleNamespace(
                file_id=current_file_id,
                parent_id=meta.get("parent_id"),
                filename=meta.get("filename"),
                original_filename=meta.get("original_filename"),
                is_folder=bool(meta.get("is_folder")),
            )
            for current_file_id, meta in self.files_meta.items()
            if meta.get("database_id") == db_id
        }

    def _get_file_root_uri(self, db_id: str, file_id: str) -> str | None:
        record_map = self._build_record_map(db_id)
        record = record_map.get(file_id)
        if record is None or getattr(record, "is_folder", False):
            return None
        return openviking_service.build_kb_file_root_uri(db_id, record, record_map)

    def _get_sync_file_ids(self, db_id: str, file_id: str) -> list[str]:
        meta = self.files_meta.get(file_id)
        if meta is None:
            return []
        if not meta.get("is_folder"):
            return [file_id]

        descendants: list[str] = []

        def walk(folder_id: str) -> None:
            children = [
                child_id
                for child_id, child_meta in self.files_meta.items()
                if child_meta.get("database_id") == db_id and child_meta.get("parent_id") == folder_id
            ]
            for child_id in children:
                child_meta = self.files_meta.get(child_id) or {}
                if child_meta.get("is_folder"):
                    walk(child_id)
                    continue
                descendants.append(child_id)

        walk(file_id)
        return descendants

    async def _load_chunk_records(self, db_id: str, file_id: str) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
        if file_id not in self.files_meta:
            raise ValueError(f"File {file_id} not found")

        file_meta = self.files_meta[file_id]
        if file_meta.get("is_folder"):
            return file_meta, "", []
        if not file_meta.get("markdown_file"):
            raise ValueError("File has not been parsed yet")

        markdown_content = await self._read_markdown_from_minio(file_meta["markdown_file"])
        processing_params = resolve_chunk_processing_params(
            kb_additional_params=self.databases_meta.get(db_id, {}).get("metadata"),
            file_processing_params=file_meta.get("processing_params"),
        )
        self.files_meta[file_id]["processing_params"] = processing_params
        chunks = chunk_markdown(markdown_content, file_id, file_meta.get("filename") or file_id, processing_params)
        return file_meta, markdown_content, chunks

    @staticmethod
    def _build_vector_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        vector_chunks: list[dict[str, Any]] = []
        for chunk in chunks:
            content = str(chunk.get("content") or "")
            chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or "")
            chunk_index = int(chunk.get("chunk_index") or 0)
            if len(content) <= MAX_VECTOR_CHUNK_CHARS:
                vector_chunks.append(
                    {
                        **chunk,
                        "vector_chunk_id": chunk_id,
                        "vector_chunk_index": chunk_index,
                        "source_chunk_id": chunk_id,
                        "source_chunk_index": chunk_index,
                    }
                )
                continue

            parts = [
                content[offset : offset + MAX_VECTOR_CHUNK_CHARS]
                for offset in range(0, len(content), MAX_VECTOR_CHUNK_CHARS)
            ]
            for part_index, part_content in enumerate(parts):
                vector_chunks.append(
                    {
                        **chunk,
                        "content": part_content,
                        "vector_chunk_id": f"{chunk_id}_part_{part_index}",
                        "vector_chunk_index": chunk_index * 1000 + part_index,
                        "source_chunk_id": chunk_id,
                        "source_chunk_index": chunk_index,
                    }
                )

        return vector_chunks

    async def _sync_indexed_file(self, db_id: str, file_id: str, previous_root_uri: str | None = None) -> None:
        if not openviking_service.is_enabled():
            raise RuntimeError("OpenViking 未启用，请设置 RAG_BACKEND=openviking")

        file_meta, _, chunks = await self._load_chunk_records(db_id, file_id)
        if file_meta.get("is_folder"):
            return

        record_map = self._build_record_map(db_id)
        record = record_map.get(file_id)
        if record is None:
            raise ValueError(f"File {file_id} metadata not found")

        current_root_uri = openviking_service.build_kb_file_root_uri(db_id, record, record_map)
        stale_root_uri = previous_root_uri or current_root_uri
        await openviking_service.delete_resource_vectors(stale_root_uri)

        for chunk in self._build_vector_chunks(chunks):
            chunk_uri = openviking_service.build_kb_chunk_uri(
                db_id,
                record,
                record_map,
                chunk_id=str(chunk.get("vector_chunk_id") or chunk.get("chunk_id") or chunk.get("id") or ""),
                chunk_index=int(chunk.get("vector_chunk_index") or chunk.get("chunk_index") or 0),
            )
            await openviking_service.upsert_resource_vector(
                uri=chunk_uri,
                content=chunk.get("content", ""),
                parent_uri=current_root_uri,
                name=file_meta.get("original_filename") or file_meta.get("filename") or file_id,
                abstract=openviking_service._truncate_text(str(chunk.get("content", "")), limit=500),
            )

    async def index_file(self, db_id: str, file_id: str, operator_id: str | None = None) -> dict:
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        async with self._metadata_lock:
            if file_id not in self.files_meta:
                raise ValueError(f"File {file_id} not found")

            file_meta = self.files_meta[file_id]
            current_status = file_meta.get("status")
            allowed_statuses = {
                FileStatus.PARSED,
                FileStatus.ERROR_INDEXING,
                FileStatus.INDEXED,
                FileStatus.DONE,
            }
            if current_status not in allowed_statuses:
                raise ValueError(
                    f"Cannot index file with status '{current_status}'. "
                    f"File must be parsed first (allowed: {', '.join(sorted(allowed_statuses))})"
                )

            file_meta.pop("error", None)
            file_meta["status"] = FileStatus.INDEXING
            file_meta["updated_at"] = utc_isoformat()
            if operator_id:
                file_meta["updated_by"] = operator_id
            await self._persist_file(file_id)

        self._add_to_processing_queue(file_id)

        try:
            await self._sync_indexed_file(db_id, file_id)
            async with self._metadata_lock:
                self.files_meta[file_id]["status"] = FileStatus.INDEXED
                self.files_meta[file_id]["updated_at"] = utc_isoformat()
                if operator_id:
                    self.files_meta[file_id]["updated_by"] = operator_id
                await self._persist_file(file_id)
                return self.files_meta[file_id]
        except Exception as exc:
            logger.error(f"OpenViking indexing failed for {file_id}: {exc}")
            async with self._metadata_lock:
                self.files_meta[file_id]["status"] = FileStatus.ERROR_INDEXING
                self.files_meta[file_id]["error"] = str(exc)
                self.files_meta[file_id]["updated_at"] = utc_isoformat()
                if operator_id:
                    self.files_meta[file_id]["updated_by"] = operator_id
                await self._persist_file(file_id)
            raise
        finally:
            self._remove_from_processing_queue(file_id)

    async def update_content(self, db_id: str, file_ids: list[str], params: dict | None = None) -> list[dict]:
        results: list[dict] = []
        request_params = params or {}

        for file_id in file_ids:
            if request_params:
                await self.update_file_params(db_id, file_id, request_params)
            await self.parse_file(db_id, file_id)
            results.append(await self.index_file(db_id, file_id))

        return results

    @staticmethod
    def _parse_chunk_uri(uri: str) -> tuple[str, int | None, str]:
        path = PurePosixPath(uri.removeprefix("viking://"))
        stem = path.stem
        chunk_index: int | None = None
        chunk_id = stem
        if "__" in stem:
            maybe_index, remainder = stem.split("__", 1)
            if maybe_index.isdigit():
                chunk_index = int(maybe_index)
                chunk_id = remainder
        return path.as_posix(), chunk_index, chunk_id

    def _match_file_meta_for_uri(self, db_id: str, uri: str) -> tuple[str | None, dict[str, Any] | None]:
        matches: list[tuple[int, str, dict[str, Any]]] = []
        for file_id, meta in self.files_meta.items():
            if meta.get("database_id") != db_id or meta.get("is_folder"):
                continue
            root_uri = self._get_file_root_uri(db_id, file_id)
            if root_uri and uri.startswith(root_uri):
                matches.append((len(root_uri), file_id, meta))

        if not matches:
            return None, None

        _, file_id, meta = max(matches, key=lambda item: item[0])
        return file_id, meta

    async def _resolve_chunk_for_uri(
        self,
        db_id: str,
        uri: str,
        *,
        parent_uri: str = "",
        chunk_cache: dict[str, tuple[SimpleNamespace, dict[str, dict[str, Any]]]],
    ) -> tuple[str | None, dict[str, Any] | None, str | None, dict[str, Any] | None]:
        file_id, file_meta = self._match_file_meta_for_uri(db_id, uri or parent_uri)
        if file_id is None or file_meta is None:
            return None, None, None, None

        cached = chunk_cache.get(file_id)
        if cached is None:
            record_map = self._build_record_map(db_id)
            record = record_map.get(file_id)
            if record is None:
                return file_id, file_meta, None, None

            _, _, chunks = await self._load_chunk_records(db_id, file_id)
            chunk_uri_map: dict[str, dict[str, Any]] = {}
            for chunk in self._build_vector_chunks(chunks):
                chunk_uri = openviking_service.build_kb_chunk_uri(
                    db_id,
                    record,
                    record_map,
                    chunk_id=str(chunk.get("vector_chunk_id") or chunk.get("chunk_id") or chunk.get("id") or ""),
                    chunk_index=int(chunk.get("vector_chunk_index") or chunk.get("chunk_index") or 0),
                )
                chunk_uri_map[chunk_uri] = chunk

            cached = (record, chunk_uri_map)
            chunk_cache[file_id] = cached

        _, chunk_uri_map = cached
        candidate_uris = [value for value in [uri, parent_uri] if value]
        matches: list[tuple[int, str, dict[str, Any]]] = []
        for candidate_uri in candidate_uris:
            for chunk_uri, chunk in chunk_uri_map.items():
                if (
                    candidate_uri == chunk_uri
                    or candidate_uri.startswith(f"{chunk_uri}/")
                    or chunk_uri.startswith(f"{candidate_uri.rstrip('/')}/")
                ):
                    matches.append((len(chunk_uri), chunk_uri, chunk))

        if not matches:
            return file_id, file_meta, None, None

        _, chunk_uri, chunk = max(matches, key=lambda item: item[0])
        return file_id, file_meta, chunk_uri, chunk

    async def aquery(self, query_text: str, db_id: str, **kwargs) -> list[dict]:
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        query_params = self._get_query_params(db_id)
        merged_kwargs = {**query_params, **kwargs}

        final_top_k = max(int(merged_kwargs.get("final_top_k", 10) or 10), 1)
        recall_top_k = max(int(merged_kwargs.get("recall_top_k", final_top_k) or final_top_k), final_top_k)
        score_threshold_value = merged_kwargs.get("score_threshold", merged_kwargs.get("similarity_threshold"))
        score_threshold = float(score_threshold_value) if score_threshold_value not in {None, ""} else None
        file_name = str(merged_kwargs.get("file_name") or "").strip().lower()

        if file_name:
            target_uris = []
            for file_id, meta in self.files_meta.items():
                if meta.get("database_id") != db_id or meta.get("is_folder"):
                    continue
                candidates = [
                    str(meta.get("filename") or "").lower(),
                    str(meta.get("original_filename") or "").lower(),
                    file_id.lower(),
                ]
                if any(file_name in candidate or candidate in file_name for candidate in candidates if candidate):
                    root_uri = self._get_file_root_uri(db_id, file_id)
                    if root_uri:
                        target_uris.append(root_uri)
        else:
            target_uris = [openviking_service.build_kb_root_uri(db_id)]

        if not target_uris:
            return []

        raw_results: list[dict[str, Any]] = []
        for target_uri in target_uris:
            raw_results.extend(
                await openviking_service.search_resource_vectors(
                    query_text=query_text,
                    target_uri=target_uri,
                    limit=recall_top_k,
                    score_threshold=score_threshold,
                )
            )

        raw_results.sort(key=lambda item: item.get("score") or 0.0, reverse=True)

        seen_uris: set[str] = set()
        retrieved_chunks: list[dict[str, Any]] = []
        chunk_cache: dict[str, tuple[SimpleNamespace, dict[str, dict[str, Any]]]] = {}
        for item in raw_results:
            uri = item.get("uri") or ""
            parent_uri = item.get("parent_uri") or ""
            dedupe_uri = uri or parent_uri
            if not dedupe_uri or dedupe_uri in seen_uris:
                continue
            seen_uris.add(dedupe_uri)

            file_id, file_meta, chunk_uri, chunk = await self._resolve_chunk_for_uri(
                db_id,
                uri,
                parent_uri=parent_uri,
                chunk_cache=chunk_cache,
            )
            content = (chunk or {}).get("content", "").strip()
            if not content:
                content = (item.get("abstract") or "").strip()
            if not content:
                continue

            chunk_index = (
                chunk.get("source_chunk_index")
                if chunk
                else None
            )
            chunk_id = (
                chunk.get("source_chunk_id")
                if chunk
                else None
            )

            retrieved_chunks.append(
                {
                    "content": content,
                    "score": item.get("score") or 0.0,
                    "metadata": {
                        "source": (file_meta or {}).get("original_filename")
                        or (file_meta or {}).get("filename")
                        or uri,
                        "file_id": file_id,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk_index,
                        "uri": chunk_uri or uri or parent_uri,
                    },
                }
            )

            if len(retrieved_chunks) >= final_top_k:
                break

        return retrieved_chunks

    def get_query_params_config(self, db_id: str, **kwargs) -> dict:
        return {
            "type": "openviking",
            "options": [
                {
                    "key": "final_top_k",
                    "label": "返回结果数",
                    "type": "number",
                    "default": 10,
                    "min": 1,
                    "max": 50,
                    "description": "最终返回给前端的检索结果数量",
                },
                {
                    "key": "recall_top_k",
                    "label": "召回数量",
                    "type": "number",
                    "default": 10,
                    "min": 1,
                    "max": 100,
                    "description": "OpenViking 初始召回的候选数量",
                },
                {
                    "key": "score_threshold",
                    "label": "分数阈值",
                    "type": "number",
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "description": "过滤低于该相关度分数的结果",
                },
            ],
        }

    async def move_file(self, db_id: str, file_id: str, new_parent_id: str | None) -> dict:
        sync_file_ids = self._get_sync_file_ids(db_id, file_id)
        previous_root_uris = {current_file_id: self._get_file_root_uri(db_id, current_file_id) for current_file_id in sync_file_ids}
        result = await super().move_file(db_id, file_id, new_parent_id)

        for current_file_id in sync_file_ids:
            status = (self.files_meta.get(current_file_id) or {}).get("status")
            if status not in INDEXED_FILE_STATUSES:
                continue
            await self._sync_indexed_file(db_id, current_file_id, previous_root_uri=previous_root_uris.get(current_file_id))

        return result

    async def rename_file(self, db_id: str, file_id: str, new_name: str) -> dict:
        sync_file_ids = self._get_sync_file_ids(db_id, file_id)
        previous_root_uris = {current_file_id: self._get_file_root_uri(db_id, current_file_id) for current_file_id in sync_file_ids}
        result = await super().rename_file(db_id, file_id, new_name)

        for current_file_id in sync_file_ids:
            status = (self.files_meta.get(current_file_id) or {}).get("status")
            if status not in INDEXED_FILE_STATUSES:
                continue
            await self._sync_indexed_file(db_id, current_file_id, previous_root_uri=previous_root_uris.get(current_file_id))

        return result

    async def delete_file(self, db_id: str, file_id: str) -> None:
        file_meta = self.files_meta.get(file_id)
        if file_meta and not file_meta.get("is_folder"):
            root_uri = self._get_file_root_uri(db_id, file_id)
            if root_uri:
                await openviking_service.remove_resource(root_uri)

        async with self._metadata_lock:
            if file_id in self.files_meta:
                del self.files_meta[file_id]
                from src.repositories.knowledge_file_repository import KnowledgeFileRepository

                await KnowledgeFileRepository().delete(file_id)

    async def get_file_basic_info(self, db_id: str, file_id: str) -> dict:
        if file_id not in self.files_meta:
            raise ValueError(f"File not found: {file_id}")
        return {"meta": self.files_meta[file_id]}

    async def get_file_content(self, db_id: str, file_id: str) -> dict:
        if file_id not in self.files_meta:
            raise ValueError(f"File not found: {file_id}")

        file_meta = self.files_meta[file_id]
        if file_meta.get("is_folder"):
            return {"content": "", "lines": []}

        content = ""
        lines: list[dict[str, Any]] = []
        if file_meta.get("markdown_file"):
            content = await self._read_markdown_from_minio(file_meta["markdown_file"])
            processing_params = resolve_chunk_processing_params(
                kb_additional_params=self.databases_meta.get(db_id, {}).get("metadata"),
                file_processing_params=file_meta.get("processing_params"),
            )
            chunks = chunk_markdown(content, file_id, file_meta.get("filename") or file_id, processing_params)
            lines = [
                {
                    "id": chunk.get("chunk_id"),
                    "content": chunk.get("content", ""),
                    "chunk_order_index": chunk.get("chunk_index", 0),
                }
                for chunk in chunks
            ]

        return {"content": content, "lines": lines}

    async def get_file_info(self, db_id: str, file_id: str) -> dict:
        basic_info = await self.get_file_basic_info(db_id, file_id)
        content_info = await self.get_file_content(db_id, file_id)
        return {**basic_info, **content_info}

    async def delete_database(self, db_id: str) -> dict:
        await openviking_service.remove_resource(openviking_service.build_kb_root_uri(db_id))
        return await super().delete_database(db_id)
