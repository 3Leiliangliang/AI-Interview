from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.interview_coding_service import get_problem_package_detail, list_imported_problem_packages
from src.utils import logger


INTERVIEW_SEED_PATH = ROOT / "src" / "config" / "static" / "interview_coding_problems.json"


def _sanitize_path_part(value: str, *, fallback: str) -> str:
    cleaned = "".join(" " if char in '<>:"/\\|?*' else char for char in str(value or ""))
    cleaned = " ".join(cleaned.split()).strip(". ")
    return cleaned or fallback


def _render_jsonl(records: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + ("\n" if records else "")


def _load_interview_seed_problems() -> list[dict[str, object]]:
    if not INTERVIEW_SEED_PATH.exists():
        return []
    payload = json.loads(INTERVIEW_SEED_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _build_seed_records(problems: list[dict[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index, item in enumerate(problems, start=1):
        records.append(
            {
                "source_type": "interview_seed",
                "package_path": "interview-seed/",
                "package_type": "seed",
                "problem_index": index,
                "problem_id": str(item.get("id") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "source": str(item.get("source") or "interview-seed").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "description": str(item.get("description") or "").strip(),
                "input_description": str(item.get("input_description") or "").strip(),
                "output_description": str(item.get("output_description") or "").strip(),
                "examples": list(item.get("examples") or []),
                "starter_code": dict(item.get("starter_code") or {}),
                "allowed_languages": list(item.get("allowed_languages") or []),
                "checks": dict(item.get("checks") or {}),
                "statement_language": "zh",
                "difficulty_tag": "",
                "topic_tags": [],
                "position_tags": [],
                "primary_position_tag": "",
            }
        )
    return records


def _build_package_records(
    *,
    package: dict[str, object],
    problems: list[dict[str, object]],
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for item in problems:
        records.append(
            {
                "source_type": "problem_package",
                "package_path": str(package.get("package_path") or item.get("package_path") or "").strip(),
                "package_type": str(package.get("package_type") or item.get("package_type") or "").strip(),
                "package_sha": str(package.get("package_sha") or "").strip(),
                "package_classifier": str(package.get("classifier") or "").strip(),
                "problem_index": int(item.get("problem_index") or 0),
                "problem_id": "",
                "title": str(item.get("title") or "").strip(),
                "source": str(item.get("source") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
                "description": str(item.get("description") or "").strip(),
                "input_description": str(item.get("input_description") or "").strip(),
                "output_description": str(item.get("output_description") or "").strip(),
                "examples": list(item.get("examples") or []),
                "starter_code": dict(item.get("starter_code") or {}),
                "allowed_languages": list(item.get("allowed_languages") or []),
                "checks": {},
                "statement_language": str(item.get("statement_language") or "").strip(),
                "difficulty_tag": str(item.get("difficulty_tag") or "").strip(),
                "topic_tags": list(item.get("topic_tags") or []),
                "position_tags": list(item.get("position_tags") or []),
                "primary_position_tag": str(item.get("primary_position_tag") or "").strip(),
                "oj_problem_ids": list(item.get("oj_problem_ids") or []),
                "oj_display_ids": list(item.get("oj_display_ids") or []),
                "imported_at": str(item.get("imported_at") or "").strip(),
            }
        )
    return records


def export_coding_problem_jsonl(*, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)

    seed_root = output_dir / "interview-seed"
    seed_root.mkdir(parents=True, exist_ok=True)
    seed_records = _build_seed_records(_load_interview_seed_problems())
    seed_output_path = seed_root / "problems.jsonl"
    seed_output_path.write_text(_render_jsonl(seed_records), encoding="utf-8")

    packages_root = output_dir / "packages"
    packages_root.mkdir(parents=True, exist_ok=True)

    package_summaries: list[dict[str, object]] = []
    package_records_total = 0
    package_file_count = 0

    imported = list_imported_problem_packages()
    for package in imported.get("packages") or []:
        package_path = str(package.get("package_path") or "").strip()
        if not package_path:
            continue
        detail = get_problem_package_detail(package_path)
        package_records = _build_package_records(
            package=detail.get("package") or {},
            problems=list(detail.get("problems") or []),
        )
        if not package_records:
            continue

        relative_parts = [
            _sanitize_path_part(part, fallback="unknown")
            for part in Path(package_path.rstrip("/")).parts
            if part not in {".", ""}
        ]
        package_dir = packages_root.joinpath(*relative_parts)
        package_dir.mkdir(parents=True, exist_ok=True)
        output_path = package_dir / "problems.jsonl"
        output_path.write_text(_render_jsonl(package_records), encoding="utf-8")

        package_file_count += 1
        package_records_total += len(package_records)
        package_summaries.append(
            {
                "package_path": package_path,
                "output_path": str(output_path),
                "problem_count": len(package_records),
            }
        )

    return {
        "output_dir": str(output_dir),
        "seed_problem_count": len(seed_records),
        "seed_output_path": str(seed_output_path),
        "package_file_count": package_file_count,
        "package_problem_count": package_records_total,
        "package_summaries": package_summaries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出代码题库为 JSONL")
    parser.add_argument(
        "--output-dir",
        default=str((ROOT / "output" / "coding_problem_jsonl_exports").resolve()),
        help="导出根目录",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        summary = export_coding_problem_jsonl(output_dir=Path(args.output_dir).resolve())
    except Exception as exc:
        logger.error(f"导出代码题库失败: {exc}")
        raise SystemExit(1) from exc

    print(f"导出目录: {summary['output_dir']}")
    print(f"interview-seed: {summary['seed_problem_count']} 题")
    print(f"题包文件: {summary['package_file_count']} 个")
    print(f"题包总题数: {summary['package_problem_count']} 题")
    print(f"种子题输出: {summary['seed_output_path']}")
    for item in summary["package_summaries"]:
        print(f"- {item['package_path']}: {item['problem_count']} 题")
        print(f"  {item['output_path']}")


if __name__ == "__main__":
    main()
