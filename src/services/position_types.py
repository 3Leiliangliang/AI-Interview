from __future__ import annotations

import copy
from typing import Any

DEFAULT_POSITION_KEY = "backend"
UNCLASSIFIED_POSITION_KEY = "unclassified"

POSITION_TYPES = [
    {
        "key": "frontend",
        "label": "前端工程师",
        "short_label": "前端",
        "order": 10,
        "selectable": True,
        "aliases": ["前端", "前端开发", "前端开发工程师", "frontend", "fe", "react", "vue"],
        "keywords": ["前端", "frontend", "react", "vue", "javascript", "typescript", "html", "css"],
        "problemset_tag": "frontend",
    },
    {
        "key": "backend",
        "label": "后端工程师",
        "short_label": "后端",
        "order": 20,
        "selectable": True,
        "aliases": [
            "后端",
            "后端开发",
            "后端开发工程师",
            "backend",
            "be",
            "java",
            "golang",
            "python",
            "数据库",
            "database",
            "db",
            "sql",
            "mysql",
            "postgresql",
        ],
        "keywords": [
            "后端",
            "backend",
            "java",
            "spring",
            "go",
            "golang",
            "python",
            "redis",
            "微服务",
            "数据库",
            "database",
            "sql",
            "mysql",
            "postgresql",
            "postgres",
            "索引",
            "事务",
        ],
        "problemset_tag": "backend",
    },
    {
        "key": "algorithm",
        "label": "算法工程师",
        "short_label": "算法",
        "order": 30,
        "selectable": True,
        "aliases": ["算法", "算法工程师", "数据结构", "算法与数据结构", "dsa", "algorithm", "leetcode"],
        "keywords": ["算法", "数据结构", "dsa", "leetcode", "二叉树", "链表", "动态规划", "图", "数组"],
        "problemset_tag": "algorithm_general",
    },
    {
        "key": "system_design",
        "label": "系统架构师",
        "short_label": "架构",
        "order": 40,
        "selectable": True,
        "aliases": ["系统设计", "system design", "架构设计", "分布式系统"],
        "keywords": ["系统设计", "system design", "架构", "分布式", "高并发", "缓存", "消息队列"],
        "problemset_tag": "backend",
    },
    {
        "key": "ai_app",
        "label": "AI 应用开发",
        "short_label": "AI应用",
        "order": 60,
        "selectable": True,
        "aliases": ["ai 应用开发", "ai应用开发", "llm", "rag", "agent", "mcp", "ai app"],
        "keywords": ["ai", "llm", "rag", "agent", "mcp", "prompt", "embedding", "向量数据库"],
        "problemset_tag": "backend",
    },
    {
        "key": UNCLASSIFIED_POSITION_KEY,
        "label": "未分类",
        "short_label": "未分类",
        "order": 999,
        "selectable": False,
        "aliases": ["未分类", "unknown", "other"],
        "keywords": [],
        "problemset_tag": "algorithm_general",
    },
]

_POSITION_TYPE_MAP = {item["key"]: item for item in POSITION_TYPES}
_POSITION_ALIAS_MAP: dict[str, str] = {}
for item in POSITION_TYPES:
    candidates = [item["key"], item["label"], item["short_label"], *(item.get("aliases") or [])]
    for candidate in candidates:
        normalized = str(candidate or "").strip().lower()
        if normalized:
            _POSITION_ALIAS_MAP[normalized] = item["key"]


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _public_position_type(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": item["key"],
        "label": item["label"],
        "short_label": item["short_label"],
        "order": item["order"],
        "selectable": item["selectable"],
        "aliases": list(item.get("aliases") or []),
        "keywords": list(item.get("keywords") or []),
        "problemset_tag": item.get("problemset_tag") or "",
    }


def get_position_type(key: str | None) -> dict[str, Any] | None:
    normalized_key = _normalized_text(key)
    if not normalized_key:
        return None
    item = _POSITION_TYPE_MAP.get(normalized_key)
    return copy.deepcopy(_public_position_type(item)) if item else None


def get_all_position_types(*, selectable_only: bool = False) -> list[dict[str, Any]]:
    items = [_public_position_type(item) for item in POSITION_TYPES]
    if selectable_only:
        items = [item for item in items if item["selectable"]]
    return copy.deepcopy(items)


def get_default_position_type() -> dict[str, Any]:
    return copy.deepcopy(_public_position_type(_POSITION_TYPE_MAP[DEFAULT_POSITION_KEY]))


def get_default_position_label() -> str:
    return _POSITION_TYPE_MAP[DEFAULT_POSITION_KEY]["label"]


def get_selectable_position_labels() -> list[str]:
    return [item["label"] for item in get_all_position_types(selectable_only=True)]


def get_unclassified_position_type() -> dict[str, Any]:
    return copy.deepcopy(_public_position_type(_POSITION_TYPE_MAP[UNCLASSIFIED_POSITION_KEY]))


def normalize_position_key(value: Any, *, fallback_to_default: bool = True) -> str:
    normalized = _normalized_text(value)
    if not normalized:
        return DEFAULT_POSITION_KEY if fallback_to_default else UNCLASSIFIED_POSITION_KEY

    exact_match = _POSITION_ALIAS_MAP.get(normalized)
    if exact_match:
        return exact_match

    for item in POSITION_TYPES:
        keywords = [_normalized_text(keyword) for keyword in item.get("keywords") or []]
        if any(keyword and keyword in normalized for keyword in keywords):
            return item["key"]

    return DEFAULT_POSITION_KEY if fallback_to_default else UNCLASSIFIED_POSITION_KEY


def normalize_position_label(value: Any, *, fallback_to_default: bool = True) -> str:
    key = normalize_position_key(value, fallback_to_default=fallback_to_default)
    return _POSITION_TYPE_MAP[key]["label"]


def match_position_type_from_text(*parts: Any, fallback_to_default: bool = False) -> dict[str, Any]:
    joined = " ".join(str(part or "").strip() for part in parts if str(part or "").strip())
    key = normalize_position_key(joined, fallback_to_default=fallback_to_default)
    return copy.deepcopy(_public_position_type(_POSITION_TYPE_MAP[key]))


def get_problemset_tag_for_position(value: Any) -> str:
    key = normalize_position_key(value)
    item = _POSITION_TYPE_MAP.get(key) or _POSITION_TYPE_MAP[DEFAULT_POSITION_KEY]
    return str(item.get("problemset_tag") or "")
