import pytest
from src.services.sep.feature_extractor import AnswerFeatures
from src.services.sep.rubric_engine import features_to_score_delta, POSITION_DIMENSION_MAP


def make_features(
    required_hit_rate=1.0,
    bonus_hit_count=0,
    misconception_count=0,
    star_scores=None,
    hedge_ratio=0.0,
) -> AnswerFeatures:
    return AnswerFeatures(
        required_hit_rate=required_hit_rate,
        bonus_hit_count=bonus_hit_count,
        misconception_count=misconception_count,
        star_scores=star_scores or {"S": False, "T": False, "A": False, "R": False},
        hedge_ratio=hedge_ratio,
    )


def test_perfect_required_hit_gives_max_required_score():
    features = make_features(required_hit_rate=1.0)
    delta, evidence = features_to_score_delta(features)
    required_ev = next(e for e in evidence if e["evidence_type"] == "keyword_hit")
    assert required_ev["score_delta"] == 15


def test_zero_required_hit_gives_zero():
    features = make_features(required_hit_rate=0.0)
    delta, evidence = features_to_score_delta(features)
    keyword_evs = [e for e in evidence if e["evidence_type"] == "keyword_hit"]
    assert len(keyword_evs) == 0 or all(e["score_delta"] == 0 for e in keyword_evs)


def test_misconception_gives_negative_delta():
    features = make_features(misconception_count=1)
    delta, evidence = features_to_score_delta(features)
    misc_ev = next(e for e in evidence if e["evidence_type"] == "misconception")
    assert misc_ev["score_delta"] < 0


def test_misconception_capped_at_minus_fifteen():
    features = make_features(misconception_count=5)
    delta, evidence = features_to_score_delta(features)
    misc_ev = next(e for e in evidence if e["evidence_type"] == "misconception")
    assert misc_ev["score_delta"] >= -15


def test_full_star_gives_positive_delta():
    features = make_features(star_scores={"S": True, "T": True, "A": True, "R": True})
    delta, evidence = features_to_score_delta(features)
    star_ev = next(e for e in evidence if e["evidence_type"] == "star_complete")
    assert star_ev["score_delta"] == 8


def test_high_hedge_gives_negative_delta():
    features = make_features(hedge_ratio=0.3)
    delta, evidence = features_to_score_delta(features)
    hedge_ev = next(e for e in evidence if e["evidence_type"] == "hedge")
    assert hedge_ev["score_delta"] < 0


def test_low_hedge_has_no_evidence():
    features = make_features(hedge_ratio=0.02)
    _, evidence = features_to_score_delta(features)
    assert not any(e["evidence_type"] == "hedge" for e in evidence)


def test_bonus_capped_at_ten():
    features = make_features(bonus_hit_count=10)
    _, evidence = features_to_score_delta(features)
    bonus_ev = next(e for e in evidence if e["evidence_type"] == "bonus_keyword")
    assert bonus_ev["score_delta"] <= 10


def test_position_dimension_map_has_backend():
    assert "backend" in POSITION_DIMENSION_MAP
    assert "networking" in POSITION_DIMENSION_MAP["backend"]
    assert POSITION_DIMENSION_MAP["backend"]["networking"] == "technical_competence"
