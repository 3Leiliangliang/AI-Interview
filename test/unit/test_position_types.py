from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import position_types as service  # noqa: E402


def test_get_position_types_includes_extended_categories():
    items = service.get_all_position_types()
    keys = {item["key"] for item in items}

    assert {"frontend", "backend", "algorithm", "system_design", "ai_app"} <= keys
    assert "database" not in keys


def test_normalize_position_type_accepts_legacy_and_keyword_values():
    assert service.normalize_position_key("前端") == "frontend"
    assert service.normalize_position_key("后端工程师") == "backend"
    assert service.normalize_position_key("SQL 面试题库") == "backend"
    assert service.normalize_position_key("DSA 面试手册") == "algorithm"
    assert service.normalize_position_key("系统设计面试题库") == "system_design"
    assert service.normalize_position_key("AI 应用开发面试") == "ai_app"


def test_normalize_position_label_uses_backend_as_default():
    assert service.normalize_position_label("") == "后端工程师"
    assert service.normalize_position_label(None) == "后端工程师"
    assert service.normalize_position_label("React") == "前端工程师"
