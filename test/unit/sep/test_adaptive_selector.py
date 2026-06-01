import pytest
from src.services.sep.adaptive_selector import select_next_question

BANK = [
    {"id": "a", "domain": "networking", "difficulty": 0.3},
    {"id": "b", "domain": "networking", "difficulty": 0.6},
    {"id": "c", "domain": "database",   "difficulty": 0.4},
    {"id": "d", "domain": "algorithms", "difficulty": 0.7},
    {"id": "e", "domain": "behavioral", "difficulty": 0.4},
]


def test_selects_closest_difficulty_to_theta():
    q = select_next_question(theta=0.35, asked_ids=set(), question_bank=BANK, asked_domains=set())
    # "a" has difficulty 0.3 — closest to 0.35
    assert q["id"] == "a"


def test_skips_asked_ids():
    q = select_next_question(theta=0.35, asked_ids={"a"}, question_bank=BANK, asked_domains=set())
    assert q["id"] != "a"


def test_prefers_uncovered_domain():
    # theta=0.35 → "a" (net, diff=0.3) is closest, but networking is already covered
    q = select_next_question(
        theta=0.35,
        asked_ids=set(),
        question_bank=BANK,
        asked_domains={"networking"},
    )
    assert q["domain"] != "networking"


def test_returns_none_when_bank_exhausted():
    all_ids = {q["id"] for q in BANK}
    q = select_next_question(theta=0.5, asked_ids=all_ids, question_bank=BANK, asked_domains=set())
    assert q is None


def test_returns_dict_with_required_keys():
    q = select_next_question(theta=0.5, asked_ids=set(), question_bank=BANK, asked_domains=set())
    assert "id" in q
    assert "domain" in q
    assert "difficulty" in q
