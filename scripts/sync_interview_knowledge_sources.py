from __future__ import annotations

import argparse
import json

try:
    from interview_knowledge_sources import ensure_interview_knowledge_sources
except ModuleNotFoundError:
    from scripts.interview_knowledge_sources import ensure_interview_knowledge_sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync curated upstream interview resources into .knowledge/interview_sources."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-clone upstream repositories before syncing local sources.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = ensure_interview_knowledge_sources(force=args.force)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
