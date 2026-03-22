from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath

import wcmatch.glob as wcglob
from deepagents.backends.protocol import (
    BackendProtocol,
    EditResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)
from deepagents.backends.utils import check_empty_content, format_content_with_line_numbers

from src.services.openviking_service import openviking_service


def _run_async_sync(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, awaitable)
        return future.result()


class OpenVikingReadonlyBackend(BackendProtocol):
    def __init__(self, runtime, *, agent_id: str) -> None:
        self.runtime = runtime
        self.agent_id = agent_id

    def _user_id(self) -> str:
        runtime_context = getattr(self.runtime, "context", None)
        user_id = getattr(runtime_context, "user_id", None)
        if user_id in (None, ""):
            configurable = getattr(self.runtime, "config", None) or {}
            user_id = configurable.get("configurable", {}).get("user_id")
        return str(user_id or "")

    def _thread_id(self) -> str:
        runtime_context = getattr(self.runtime, "context", None)
        thread_id = getattr(runtime_context, "thread_id", None)
        if thread_id in (None, ""):
            configurable = getattr(self.runtime, "config", None) or {}
            thread_id = configurable.get("configurable", {}).get("thread_id")
        return str(thread_id or "")

    def _normalize_uri(self, path: str) -> str:
        alias_map = {
            "/agent": "/agent/current",
            "/agent/": "/agent/current",
            "/session": "/session/current",
            "/session/": "/session/current",
            "/user": "/user/current",
            "/user/": "/user/current",
        }
        path = alias_map.get(path, path)
        return openviking_service.normalize_context_uri(
            path,
            user_id=self._user_id(),
            thread_id=self._thread_id() or None,
            agent_id=self.agent_id,
        )

    def _session_root_uri(self) -> str:
        return openviking_service.build_session_root_uri(self._user_id(), self._thread_id())

    def _user_root_uri(self) -> str:
        return f"viking://user/{openviking_service._sanitize_uri_segment(self._user_id())}"

    def _agent_root_uri(self) -> str:
        return openviking_service.build_agent_scope_uri(self._user_id(), self.agent_id)

    def _uri_to_virtual_path(self, uri: str) -> str:
        normalized = (uri or "").rstrip("/")
        if not normalized.startswith("viking://"):
            return normalized or "/"

        mappings = [
            (self._session_root_uri().rstrip("/"), "/session/current"),
            (self._user_root_uri().rstrip("/"), "/user/current"),
            (self._agent_root_uri().rstrip("/"), "/agent/current"),
        ]
        for base_uri, virtual_root in mappings:
            if normalized == base_uri:
                return virtual_root
            if normalized.startswith(f"{base_uri}/"):
                return f"{virtual_root}{normalized[len(base_uri):]}"

        return f"/{normalized.removeprefix('viking://')}"

    @staticmethod
    def _with_dir_suffix(path: str, *, is_dir: bool) -> str:
        if is_dir and path != "/" and not path.endswith("/"):
            return f"{path}/"
        return path

    def _resolve_child_path(self, parent_path: str, raw_path: str, name: str, *, is_dir: bool) -> str:
        if raw_path.startswith("viking://"):
            return self._with_dir_suffix(self._uri_to_virtual_path(raw_path), is_dir=is_dir)

        base = PurePosixPath(parent_path.rstrip("/") or "/")
        child_name = (name or raw_path or "").strip("/")
        child_path = str(base / child_name) if child_name else str(base)
        if not child_path.startswith("/"):
            child_path = f"/{child_path}"
        return self._with_dir_suffix(child_path, is_dir=is_dir)

    def _matches_glob(self, path: str, pattern: str, root: str) -> bool:
        root_path = PurePosixPath(root.rstrip("/") or "/")
        target_path = PurePosixPath(path.rstrip("/") or "/")
        try:
            relative = target_path.relative_to(root_path)
            candidate = relative.as_posix() or target_path.name
        except ValueError:
            candidate = target_path.as_posix().lstrip("/")

        return wcglob.globmatch(candidate, pattern, flags=wcglob.GLOBSTAR) or wcglob.globmatch(
            path.lstrip("/"),
            pattern,
            flags=wcglob.GLOBSTAR,
        )

    def ls_info(self, path: str) -> list[FileInfo]:
        if path == "/":
            return [
                {"path": "/agent/", "is_dir": True, "size": 0, "modified_at": ""},
                {"path": "/resources/", "is_dir": True, "size": 0, "modified_at": ""},
                {"path": "/session/", "is_dir": True, "size": 0, "modified_at": ""},
                {"path": "/user/", "is_dir": True, "size": 0, "modified_at": ""},
            ]
        if path in {"/agent", "/agent/"}:
            return [{"path": "/agent/current/", "is_dir": True, "size": 0, "modified_at": ""}]
        if path in {"/session", "/session/"}:
            return [{"path": "/session/current/", "is_dir": True, "size": 0, "modified_at": ""}]
        if path in {"/user", "/user/"}:
            return [{"path": "/user/current/", "is_dir": True, "size": 0, "modified_at": ""}]

        try:
            items = _run_async_sync(openviking_service.list_uri(self._normalize_uri(path)))
        except Exception:
            return []

        infos: list[FileInfo] = []
        for item in items:
            is_dir = bool(item.get("is_dir"))
            infos.append(
                {
                    "path": self._resolve_child_path(
                        path,
                        str(item.get("path") or ""),
                        str(item.get("name") or ""),
                        is_dir=is_dir,
                    ),
                    "is_dir": is_dir,
                    "size": int(item.get("size") or 0),
                    "modified_at": str(item.get("modified_at") or ""),
                }
            )

        infos.sort(key=lambda item: item.get("path", ""))
        return infos

    async def als_info(self, path: str) -> list[FileInfo]:
        if path in {"/", "/agent", "/agent/", "/session", "/session/", "/user", "/user/"}:
            return self.ls_info(path)

        try:
            items = await openviking_service.list_uri(self._normalize_uri(path))
        except Exception:
            return []

        infos: list[FileInfo] = []
        for item in items:
            is_dir = bool(item.get("is_dir"))
            infos.append(
                {
                    "path": self._resolve_child_path(
                        path,
                        str(item.get("path") or ""),
                        str(item.get("name") or ""),
                        is_dir=is_dir,
                    ),
                    "is_dir": is_dir,
                    "size": int(item.get("size") or 0),
                    "modified_at": str(item.get("modified_at") or ""),
                }
            )

        infos.sort(key=lambda item: item.get("path", ""))
        return infos

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        try:
            content = _run_async_sync(openviking_service.read_uri(self._normalize_uri(file_path), offset=offset, limit=limit))
        except Exception as exc:
            return f"Error: Failed to read '{file_path}': {exc}"

        empty_msg = check_empty_content(content)
        if empty_msg:
            return empty_msg
        return format_content_with_line_numbers(content.splitlines(), start_line=offset + 1)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        try:
            content = await openviking_service.read_uri(self._normalize_uri(file_path), offset=offset, limit=limit)
        except Exception as exc:
            return f"Error: Failed to read '{file_path}': {exc}"

        empty_msg = check_empty_content(content)
        if empty_msg:
            return empty_msg
        return format_content_with_line_numbers(content.splitlines(), start_line=offset + 1)

    def grep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[GrepMatch] | str:
        search_path = path or "/"
        try:
            matches = _run_async_sync(openviking_service.grep_uri(self._normalize_uri(search_path), pattern))
        except Exception as exc:
            return f"Error: grep failed for '{search_path}': {exc}"

        normalized: list[GrepMatch] = []
        for item in matches:
            match_path = self._resolve_child_path(
                search_path,
                str(item.get("path") or item.get("uri") or ""),
                str(item.get("name") or ""),
                is_dir=False,
            )
            if glob and not self._matches_glob(match_path, glob, search_path):
                continue
            normalized.append(
                {
                    "path": match_path,
                    "line": int(item.get("line") or item.get("line_number") or 1),
                    "text": str(item.get("text") or item.get("content") or item.get("excerpt") or ""),
                }
            )
        return normalized

    async def agrep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[GrepMatch] | str:
        search_path = path or "/"
        try:
            matches = await openviking_service.grep_uri(self._normalize_uri(search_path), pattern)
        except Exception as exc:
            return f"Error: grep failed for '{search_path}': {exc}"

        normalized: list[GrepMatch] = []
        for item in matches:
            match_path = self._resolve_child_path(
                search_path,
                str(item.get("path") or item.get("uri") or ""),
                str(item.get("name") or ""),
                is_dir=False,
            )
            if glob and not self._matches_glob(match_path, glob, search_path):
                continue
            normalized.append(
                {
                    "path": match_path,
                    "line": int(item.get("line") or item.get("line_number") or 1),
                    "text": str(item.get("text") or item.get("content") or item.get("excerpt") or ""),
                }
            )
        return normalized

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        try:
            matches = _run_async_sync(openviking_service.glob_uri(pattern=pattern, uri=self._normalize_uri(path)))
        except Exception:
            return []

        infos: list[FileInfo] = []
        for item in matches:
            raw_path = str(item.get("path") or item.get("uri") or "")
            is_dir = bool(item.get("is_dir") or raw_path.endswith("/"))
            infos.append(
                {
                    "path": self._resolve_child_path(path, raw_path, str(item.get("name") or ""), is_dir=is_dir),
                    "is_dir": is_dir,
                    "size": int(item.get("size") or 0),
                    "modified_at": str(item.get("modified_at") or ""),
                }
            )
        infos.sort(key=lambda item: item.get("path", ""))
        return infos

    async def aglob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        try:
            matches = await openviking_service.glob_uri(pattern=pattern, uri=self._normalize_uri(path))
        except Exception:
            return []

        infos: list[FileInfo] = []
        for item in matches:
            raw_path = str(item.get("path") or item.get("uri") or "")
            is_dir = bool(item.get("is_dir") or raw_path.endswith("/"))
            infos.append(
                {
                    "path": self._resolve_child_path(path, raw_path, str(item.get("name") or ""), is_dir=is_dir),
                    "is_dir": is_dir,
                    "size": int(item.get("size") or 0),
                    "modified_at": str(item.get("modified_at") or ""),
                }
            )
        infos.sort(key=lambda item: item.get("path", ""))
        return infos

    def write(self, file_path: str, content: str) -> WriteResult:
        return WriteResult(error=f"Cannot write to {file_path}: /viking is read-only")

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        return EditResult(error=f"Cannot edit {file_path}: /viking is read-only")

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return [FileUploadResponse(path=path, error="permission_denied") for path, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                content = _run_async_sync(openviking_service.read_uri(self._normalize_uri(path), offset=0, limit=200000))
            except Exception:
                responses.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
                continue
            responses.append(FileDownloadResponse(path=path, content=content.encode("utf-8"), error=None))
        return responses

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                content = await openviking_service.read_uri(self._normalize_uri(path), offset=0, limit=200000)
            except Exception:
                responses.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
                continue
            responses.append(FileDownloadResponse(path=path, content=content.encode("utf-8"), error=None))
        return responses
