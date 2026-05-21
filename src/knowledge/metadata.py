from __future__ import annotations

from typing import Any

from src.knowledge.chunking.ragflow_like.presets import ensure_chunk_defaults_in_additional_params

POSITION_LABELS = {"前端工程师", "后端工程师"}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_tag_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        candidates = [values]
    elif isinstance(values, (list, tuple, set)):
        candidates = list(values)
    else:
        candidates = [values]

    normalized: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        text = _normalize_text(value)
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def normalize_position_tags(values: Any, fallback_position: Any = None) -> list[str]:
    tags = [tag for tag in normalize_tag_list(values) if tag in POSITION_LABELS]
    fallback = _normalize_text(fallback_position)
    if fallback in POSITION_LABELS and fallback not in tags:
        tags.append(fallback)
    return tags


def normalize_kb_additional_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """KB 元数据规范化的唯一公开入口。

    合并两层职责：分块默认值（委托 ``ensure_chunk_defaults_in_additional_params``）
    + position/topic_tags/source 字段归一化。所有 KB CRUD / router / base 持久化
    路径都应通过本函数，避免新增的分块或标签字段在某个入口被遗漏。
    """
    normalized = ensure_chunk_defaults_in_additional_params(dict(params or {}))
    normalized["position"] = (
        _normalize_text(normalized.get("position")) if _normalize_text(normalized.get("position")) in POSITION_LABELS else ""
    )
    normalized["position_tags"] = normalize_position_tags(
        normalized.get("position_tags"),
        fallback_position=normalized.get("position"),
    )
    normalized["topic_tags"] = normalize_tag_list(normalized.get("topic_tags"))
    normalized["source_key"] = _normalize_text(normalized.get("source_key"))
    normalized["source_path"] = _normalize_text(normalized.get("source_path"))
    return normalized


def normalize_file_processing_params(
    params: dict[str, Any] | None,
    *,
    fallback_position_tags: list[str] | None = None,
    fallback_topic_tags: list[str] | None = None,
) -> dict[str, Any]:
    normalized = dict(params or {})
    normalized["position_tags"] = normalize_position_tags(
        normalized.get("position_tags"),
    ) or list(fallback_position_tags or [])
    normalized["topic_tags"] = normalize_tag_list(normalized.get("topic_tags")) or list(fallback_topic_tags or [])

    content_kind = _normalize_text(normalized.get("content_kind"))
    if not content_kind:
        content_type = _normalize_text(normalized.get("content_type"))
        content_kind = "url" if content_type == "url" else "document"
    normalized["content_kind"] = content_kind
    return normalized
