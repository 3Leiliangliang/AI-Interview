from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'config' / 'static' / 'interview_coding_problems.json'


def main() -> None:
    problems = json.loads(SOURCE.read_text(encoding='utf-8'))
    print(f'Loaded {len(problems)} interview coding problems from {SOURCE}')
    for problem in problems:
        print(f"- {problem['id']}: {problem['title']}")


if __name__ == '__main__':
    main()
