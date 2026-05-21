from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CS_NOTES_ROOT = ROOT / ".knowledge" / "CS-Notes" / "notes"
OUTPUT_PATH = ROOT / "src" / "config" / "static" / "cs_notes_coding_problems.json"

LEETCODE_TOPIC_MAP = {
    "数组与矩阵": ["array"],
    "链表": ["linked_list"],
    "树": ["tree"],
    "图": ["graph"],
    "栈和队列": ["stack", "queue"],
    "搜索": ["graph"],
    "字符串": ["string"],
    "哈希表": ["hash_table"],
    "动态规划": ["dynamic_programming"],
    "二分查找": ["binary_search"],
    "排序": ["sorting"],
    "数学": ["math"],
    "双指针": ["array", "string"],
    "位运算": ["math"],
    "贪心思想": ["greedy"],
}

SWORD_TOPIC_MAP = {
    "数组": ["array"],
    "矩阵": ["array"],
    "字符串": ["string"],
    "链表": ["linked_list"],
    "树": ["tree"],
    "二叉树": ["tree"],
    "栈": ["stack"],
    "队列": ["queue"],
    "图": ["graph"],
    "数字": ["math"],
    "排序": ["sorting"],
}


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def detect_topics(text: str, fallback: list[str] | None = None) -> list[str]:
    normalized = text.lower()
    topics: list[str] = []
    for key, values in SWORD_TOPIC_MAP.items():
        if key.lower() in normalized:
            topics.extend(values)
    for value in fallback or []:
        if value not in topics:
            topics.append(value)
    if not topics:
        topics.append("algorithm")
    deduped: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        if topic in seen:
            continue
        deduped.append(topic)
        seen.add(topic)
    return deduped[:4]


def normalize_summary(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        if stripped.startswith("```"):
            continue
        return stripped[:180]
    return ""


def extract_code_block(text: str) -> str:
    match = re.search(r"```(?:java|python|javascript|cpp|c)?\n([\s\S]*?)```", text)
    return match.group(1).strip() if match else ""


def parse_leetcode_file(path: Path) -> list[dict]:
    title_suffix = path.stem.replace("Leetcode 题解 - ", "")
    fallback_topics = LEETCODE_TOPIC_MAP.get(title_suffix, ["algorithm"])
    content = path.read_text(encoding="utf-8")
    sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
    problems: list[dict] = []
    for index, section in enumerate(sections[1:], start=1):
        lines = section.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        if not title or not body:
            continue
        difficulty_match = re.search(r"\((Easy|Medium|Hard)\)", body, flags=re.IGNORECASE)
        difficulty = (difficulty_match.group(1).lower() if difficulty_match else "medium")
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"
        problems.append(
            {
                "package_path": f"cs-notes/leetcode/{slugify(title_suffix)}",
                "package_type": "curated",
                "problem_index": index,
                "title": title,
                "source": f"CS-Notes / {path.name}",
                "summary": normalize_summary(body),
                "description": body[:4000],
                "input_description": "",
                "output_description": "",
                "examples": [],
                "starter_code": {"java": extract_code_block(body)} if extract_code_block(body) else {},
                "allowed_languages": ["java"] if extract_code_block(body) else [],
                "statement_language": "zh",
                "difficulty_tag": difficulty,
                "topic_tags": detect_topics(f"{title_suffix} {title}", fallback_topics),
                "position_tags": ["algorithm_general"],
                "primary_position_tag": "algorithm_general",
                "oj_problem_ids": [],
                "oj_display_ids": [],
                "imported_at": "",
                "classifier": "cs_notes_rule",
            }
        )
    return problems


def parse_sword_offer_files() -> list[dict]:
    problem_files = sorted(path for path in CS_NOTES_ROOT.glob("*.md") if re.match(r"^\d", path.name))
    problems: list[dict] = []
    for index, path in enumerate(problem_files, start=1):
        content = path.read_text(encoding="utf-8")
        stem = path.stem
        title = re.sub(r"^\d+(\.\d+)?\s*", "", stem).strip()
        problems.append(
            {
                "package_path": "cs-notes/sword-offer",
                "package_type": "curated",
                "problem_index": index,
                "title": title,
                "source": f"CS-Notes / {path.name}",
                "summary": normalize_summary(content),
                "description": content[:4000],
                "input_description": "",
                "output_description": "",
                "examples": [],
                "starter_code": {"java": extract_code_block(content)} if extract_code_block(content) else {},
                "allowed_languages": ["java"] if extract_code_block(content) else [],
                "statement_language": "zh",
                "difficulty_tag": "medium",
                "topic_tags": detect_topics(title, ["algorithm"]),
                "position_tags": ["algorithm_general"],
                "primary_position_tag": "algorithm_general",
                "oj_problem_ids": [],
                "oj_display_ids": [],
                "imported_at": "",
                "classifier": "cs_notes_rule",
            }
        )
    return problems


def main() -> None:
    problems: list[dict] = []
    for path in sorted(CS_NOTES_ROOT.glob("Leetcode 题解 - *.md")):
        if "目录" in path.name:
            continue
        problems.extend(parse_leetcode_file(path))
    problems.extend(parse_sword_offer_files())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(problems, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(problems)} curated problems to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
