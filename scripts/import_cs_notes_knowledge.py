from __future__ import annotations

import asyncio
import json
from pathlib import Path

from scripts.import_interview_knowledge import (
    REPORT_PATH,
    ApiClient,
    DEFAULT_BASE_URL,
    build_cs_notes_import_plan,
    import_knowledge_plan,
    parse_args,
    read_default_credentials,
    verify_queries,
)


CS_NOTES_REPORT_PATH = REPORT_PATH.with_name("import_cs_notes_knowledge_report.json")


async def run_cs_notes_import(
    base_url: str,
    username: str,
    password: str,
    batch_size: int,
    force_reindex: bool,
) -> dict:
    plan = build_cs_notes_import_plan()
    async with ApiClient(base_url, username, password) as api:
        report = await import_knowledge_plan(api, plan, batch_size=batch_size, force_reindex=force_reindex)
        return {
            "database": report,
            "queries": await verify_queries(api, [report]),
        }


def main() -> None:
    default_username, default_password = read_default_credentials()
    args = parse_args()
    username = args.username or default_username
    password = args.password or default_password
    if not username or not password:
        raise SystemExit(
            "Missing admin credentials. Provide --username/--password or set AI_INTERVIEW_SUPER_ADMIN_* in .env."
        )

    summary = asyncio.run(
        run_cs_notes_import(
            base_url=args.base_url or DEFAULT_BASE_URL,
            username=username,
            password=password,
            batch_size=args.batch_size,
            force_reindex=args.force_reindex,
        )
    )
    CS_NOTES_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CS_NOTES_REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report written to {CS_NOTES_REPORT_PATH}")


if __name__ == "__main__":
    main()
