import pytest
from src.services.sep.feature_extractor import AnswerFeatures
from src.services.sep.evidence_builder import EvidenceItem, EvaluationReport, build_evidence_chain


def perfect_features() -> AnswerFeatures:
    return AnswerFeatures(
        required_hit_rate=1.0,
        bonus_hit_count=2,
        misconception_count=0,
        star_scores={"S": True, "T": True, "A": True, "R": True},
        hedge_ratio=0.0,
    )


def poor_features() -> AnswerFeatures:
    return AnswerFeatures(
        required_hit_rate=0.0,
        bonus_hit_count=0,
        misconception_count=2,
        star_scores={"S": False, "T": False, "A": False, "R": False},
        hedge_ratio=0.4,
    )


SAMPLE_QUESTIONS = [
    {"id": "net-001", "domain": "networking", "concept": "TCP握手", "question_template": "解释TCP三次握手", "difficulty": 0.5},
    {"id": "algo-001", "domain": "algorithms", "concept": "排序", "question_template": "比较排序算法", "difficulty": 0.6},
]


def test_report_has_overall_score():
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.6, 0.7],
    )
    assert isinstance(report.overall, int)
    assert 0 <= report.overall <= 100


def test_perfect_answers_give_high_score():
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.6, 0.7],
    )
    assert report.overall > 70


def test_poor_answers_give_low_score():
    report = build_evidence_chain(
        [poor_features(), poor_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.4, 0.3],
    )
    assert report.overall < 50


def test_evidence_chain_is_non_empty():
    report = build_evidence_chain(
        [perfect_features()],
        SAMPLE_QUESTIONS[:1],
        position="backend",
        theta_trajectory=[0.5, 0.6],
    )
    assert len(report.evidence_chain) > 0


def test_evidence_item_has_required_fields():
    report = build_evidence_chain(
        [perfect_features()],
        SAMPLE_QUESTIONS[:1],
        position="backend",
        theta_trajectory=[0.5, 0.6],
    )
    item = report.evidence_chain[0]
    assert hasattr(item, "dimension")
    assert hasattr(item, "question")
    assert hasattr(item, "concept")
    assert hasattr(item, "score_delta")
    assert hasattr(item, "evidence_text")
    assert hasattr(item, "evidence_type")


def test_dimensions_keys_are_valid():
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.6, 0.7],
    )
    valid = {"technical_competence", "problem_solving", "communication", "soft_skills"}
    assert all(k in valid for k in report.dimensions)


def test_theta_trajectory_preserved():
    trajectory = [0.5, 0.6, 0.7]
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=trajectory,
    )
    assert report.theta_trajectory == trajectory
