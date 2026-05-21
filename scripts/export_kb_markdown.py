from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_INTERVIEW_SKIP_APP_INIT", "1")

from src.knowledge.chunking.ragflow_like.dispatcher import chunk_markdown
from src.knowledge.chunking.ragflow_like.presets import resolve_chunk_processing_params
from src.knowledge.utils.kb_utils import parse_minio_url
from src.repositories.knowledge_base_repository import KnowledgeBaseRepository
from src.repositories.knowledge_file_repository import KnowledgeFileRepository
from src.storage.minio import get_minio_client
from src.storage.postgres.manager import pg_manager
from src.utils import logger


@dataclass(frozen=True)
class ExportTarget:
    db_id: str
    name: str
    additional_params: dict | None = None


QA_QUERY_PREFIX_RE = re.compile(r"^(?:问题|Question)\s*[:：]\s*", flags=re.IGNORECASE)
QA_ANSWER_PREFIX_RE = re.compile(r"^(?:回答|答案|Answer)\s*[:：]\s*", flags=re.IGNORECASE)


def _sanitize_path_part(value: str, *, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', " ", str(value or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(". ")
    return cleaned or fallback


def _build_output_filename(filename: str, file_id: str, suffix: str) -> str:
    source_name = _sanitize_path_part(filename, fallback=file_id)
    stem = Path(source_name).stem or source_name
    return f"{stem}{suffix}"


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}__{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _parse_qa_chunk_content(chunk_content: str) -> tuple[str, str] | None:
    text = (chunk_content or "").strip()
    if not text or "\t" not in text:
        return None

    left, right = text.split("\t", 1)
    query = QA_QUERY_PREFIX_RE.sub("", left.strip()).strip()
    answer = QA_ANSWER_PREFIX_RE.sub("", right.strip()).strip()
    if not query or not answer:
        return None
    return query, answer


def _render_jsonl_lines(records: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else "")


async def _resolve_target(*, db_id: str | None, name: str | None) -> ExportTarget:
    kb_repo = KnowledgeBaseRepository()

    if db_id:
        kb = await kb_repo.get_by_id(db_id)
        if kb is None:
            raise ValueError(f"知识库不存在: {db_id}")
        return ExportTarget(db_id=kb.db_id, name=kb.name, additional_params=kb.additional_params)

    all_kbs = await kb_repo.get_all()
    matched = [kb for kb in all_kbs if kb.name == name]
    if not matched:
        raise ValueError(f"知识库不存在: {name}")
    if len(matched) > 1:
        raise ValueError(f"知识库名称不唯一，请改用 --db-id: {name}")
    kb = matched[0]
    return ExportTarget(db_id=kb.db_id, name=kb.name, additional_params=kb.additional_params)


async def _list_all_targets() -> list[ExportTarget]:
    rows = await KnowledgeBaseRepository().get_all()
    return [ExportTarget(db_id=row.db_id, name=row.name, additional_params=row.additional_params) for row in rows]


def _collect_folder_chain(
    folder_id: str | None,
    folder_map: dict[str, object],
    cache: dict[str | None, list[str]],
) -> list[str]:
    if folder_id in cache:
        return cache[folder_id]
    if not folder_id or folder_id not in folder_map:
        cache[folder_id] = []
        return []

    folder = folder_map[folder_id]
    parent_chain = _collect_folder_chain(folder.parent_id, folder_map, cache)
    current_name = _sanitize_path_part(folder.filename, fallback=folder.file_id)
    chain = [*parent_chain, current_name]
    cache[folder_id] = chain
    return chain


async def _load_markdown_bytes(markdown_file: str) -> bytes:
    bucket_name, object_name = parse_minio_url(markdown_file)
    return await get_minio_client().adownload_file(bucket_name, object_name)


async def export_markdown(
    *,
    db_id: str | None,
    name: str | None,
    output_dir: Path,
) -> dict[str, object]:
    target = await _resolve_target(db_id=db_id, name=name)

    file_repo = KnowledgeFileRepository()
    records = await file_repo.list_by_db_id(target.db_id)
    folder_map = {record.file_id: record for record in records if record.is_folder}
    folder_cache: dict[str | None, list[str]] = {None: []}

    export_root = output_dir / _sanitize_path_part(target.name, fallback=target.db_id)
    export_root.mkdir(parents=True, exist_ok=True)

    exported_files = 0
    skipped_files: list[dict[str, str]] = []

    for record in sorted(records, key=lambda item: (bool(item.is_folder), item.filename.lower(), item.file_id)):
        if record.is_folder:
            folder_parts = _collect_folder_chain(record.file_id, folder_map, folder_cache)
            (export_root.joinpath(*folder_parts)).mkdir(parents=True, exist_ok=True)
            continue

        if not record.markdown_file:
            skipped_files.append(
                {
                    "file_id": record.file_id,
                    "filename": record.filename,
                    "reason": f"缺少 markdown_file，当前状态: {record.status or 'unknown'}",
                }
            )
            continue

        folder_parts = _collect_folder_chain(record.parent_id, folder_map, folder_cache)
        target_dir = export_root.joinpath(*folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)

        output_path = target_dir / _build_output_filename(
            record.original_filename or record.filename,
            record.file_id,
            ".md",
        )
        output_path = _ensure_unique_path(output_path)
        output_path.write_text((await _load_markdown_bytes(record.markdown_file)).decode("utf-8"), encoding="utf-8")
        exported_files += 1

    return {
        "db_id": target.db_id,
        "name": target.name,
        "output_dir": str(export_root),
        "exported_files": exported_files,
        "skipped_files": skipped_files,
    }


async def export_qa_jsonl(
    *,
    db_id: str | None,
    name: str | None,
    output_dir: Path,
) -> dict[str, object]:
    target = await _resolve_target(db_id=db_id, name=name)

    file_repo = KnowledgeFileRepository()
    records = await file_repo.list_by_db_id(target.db_id)
    folder_map = {record.file_id: record for record in records if record.is_folder}
    folder_cache: dict[str | None, list[str]] = {None: []}

    export_root = output_dir / _sanitize_path_part(target.name, fallback=target.db_id)
    export_root.mkdir(parents=True, exist_ok=True)

    exported_files = 0
    exported_qa_pairs = 0
    skipped_files: list[dict[str, str]] = []

    for record in sorted(records, key=lambda item: (bool(item.is_folder), item.filename.lower(), item.file_id)):
        if record.is_folder:
            folder_parts = _collect_folder_chain(record.file_id, folder_map, folder_cache)
            (export_root.joinpath(*folder_parts)).mkdir(parents=True, exist_ok=True)
            continue

        if not record.markdown_file:
            skipped_files.append(
                {
                    "file_id": record.file_id,
                    "filename": record.filename,
                    "reason": f"缺少 markdown_file，当前状态: {record.status or 'unknown'}",
                }
            )
            continue

        markdown_content = (await _load_markdown_bytes(record.markdown_file)).decode("utf-8")
        processing_params = resolve_chunk_processing_params(
            kb_additional_params=target.additional_params or {},
            file_processing_params=record.processing_params or {},
        )
        chunks = chunk_markdown(
            markdown_content=markdown_content,
            file_id=record.file_id,
            filename=record.original_filename or record.filename,
            processing_params=processing_params,
        )

        qa_records: list[dict[str, object]] = []
        for chunk in chunks:
            parsed = _parse_qa_chunk_content(str(chunk.get("content") or ""))
            if not parsed:
                continue
            query, answer = parsed
            qa_records.append(
                {
                    "query": query,
                    "gold_answer": answer,
                    "db_id": target.db_id,
                    "kb_name": target.name,
                    "file_id": record.file_id,
                    "filename": record.original_filename or record.filename,
                    "chunk_id": chunk.get("chunk_id"),
                    "chunk_index": chunk.get("chunk_index"),
                }
            )

        if not qa_records:
            skipped_files.append(
                {
                    "file_id": record.file_id,
                    "filename": record.filename,
                    "reason": "未解析出 QA 结构",
                }
            )
            continue

        folder_parts = _collect_folder_chain(record.parent_id, folder_map, folder_cache)
        target_dir = export_root.joinpath(*folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)

        output_path = target_dir / _build_output_filename(
            record.original_filename or record.filename,
            record.file_id,
            ".jsonl",
        )
        output_path = _ensure_unique_path(output_path)
        output_path.write_text(_render_jsonl_lines(qa_records), encoding="utf-8")

        exported_files += 1
        exported_qa_pairs += len(qa_records)

    return {
        "db_id": target.db_id,
        "name": target.name,
        "output_dir": str(export_root),
        "exported_files": exported_files,
        "exported_qa_pairs": exported_qa_pairs,
        "skipped_files": skipped_files,
    }


async def export_all_markdown(*, output_dir: Path) -> list[dict[str, object]]:
    return [await export_markdown(db_id=target.db_id, name=None, output_dir=output_dir) for target in await _list_all_targets()]


async def export_all_qa_jsonl(*, output_dir: Path) -> list[dict[str, object]]:
    return [await export_qa_jsonl(db_id=target.db_id, name=None, output_dir=output_dir) for target in await _list_all_targets()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按知识库目录结构导出已解析的内容")
    parser.add_argument("--db-id", help="知识库 db_id")
    parser.add_argument("--name", help="知识库名称")
    parser.add_argument("--all", action="store_true", help="导出当前所有知识库")
    parser.add_argument("--format", choices=["md", "qa-jsonl"], default="md", help="导出格式，默认 md")
    parser.add_argument("--output-dir", help="导出根目录；未传时按导出格式自动选择")
    args = parser.parse_args()
    selected_count = int(bool(args.db_id)) + int(bool(args.name)) + int(bool(args.all))
    if selected_count != 1:
        parser.error("必须且只能提供一个参数：--db-id、--name 或 --all")
    return args


async def _main() -> None:
    args = parse_args()

    pg_manager.initialize()
    default_output_dir = ROOT / "output" / ("kb_markdown_exports" if args.format == "md" else "kb_qa_jsonl_exports")
    resolved_output_dir = Path(args.output_dir).resolve() if args.output_dir else default_output_dir.resolve()

    if args.all:
        summaries = (
            await export_all_markdown(output_dir=resolved_output_dir)
            if args.format == "md"
            else await export_all_qa_jsonl(output_dir=resolved_output_dir)
        )

        total_exported_files = 0
        total_exported_qa_pairs = 0
        total_skipped_files = 0

        print(f"导出根目录: {resolved_output_dir}")
        print(f"导出格式: {args.format}")
        print(f"知识库数量: {len(summaries)}")
        for summary in summaries:
            total_exported_files += int(summary["exported_files"])
            total_exported_qa_pairs += int(summary.get("exported_qa_pairs") or 0)
            skipped_files = summary["skipped_files"]
            total_skipped_files += len(skipped_files)

            print(f"- {summary['name']} ({summary['db_id']})")
            print(f"  目录: {summary['output_dir']}")
            if args.format == "md":
                print(f"  成功导出: {summary['exported_files']} 个 Markdown 文件")
            else:
                print(
                    f"  成功导出: {summary['exported_files']} 个 JSONL 文件，"
                    f"{summary.get('exported_qa_pairs', 0)} 条 QA"
                )
            if skipped_files:
                print(f"  跳过: {len(skipped_files)} 个")
                for item in skipped_files:
                    print(f"    - {item['filename']} ({item['file_id']}): {item['reason']}")

        if args.format == "md":
            print(f"总计成功导出: {total_exported_files} 个 Markdown 文件")
        else:
            print(f"总计成功导出: {total_exported_files} 个 JSONL 文件")
            print(f"总计导出 QA: {total_exported_qa_pairs} 条")
        print(f"总计跳过: {total_skipped_files} 个文件")
        return

    summary = (
        await export_markdown(db_id=args.db_id, name=args.name, output_dir=resolved_output_dir)
        if args.format == "md"
        else await export_qa_jsonl(db_id=args.db_id, name=args.name, output_dir=resolved_output_dir)
    )

    print(f"知识库: {summary['name']} ({summary['db_id']})")
    print(f"导出格式: {args.format}")
    print(f"导出目录: {summary['output_dir']}")
    if args.format == "md":
        print(f"成功导出: {summary['exported_files']} 个 Markdown 文件")
    else:
        print(
            f"成功导出: {summary['exported_files']} 个 JSONL 文件，"
            f"{summary.get('exported_qa_pairs', 0)} 条 QA"
        )

    skipped_files = summary["skipped_files"]
    if skipped_files:
        print(f"跳过文件: {len(skipped_files)} 个")
        for item in skipped_files:
            print(f"- {item['filename']} ({item['file_id']}): {item['reason']}")


def main() -> None:
    try:
        asyncio.run(_main())
    except Exception as exc:
        logger.error(f"导出知识库内容失败: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
