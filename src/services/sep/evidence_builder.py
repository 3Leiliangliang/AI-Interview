from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from src.services.sep.feature_extractor import AnswerFeatures
from src.services.sep.rubric_engine import POSITION_DIMENSION_MAP, features_to_score_delta


@dataclass
class EvidenceItem:
    dimension: str
    question: str
    concept: str
    score_delta: int
    evidence_text: str
    evidence_type: str
    difficulty: float = 0.5


@dataclass
class EvaluationReport:
    overall: int
    dimensions: dict[str, int]
    evidence_chain: list[EvidenceItem]
    theta_trajectory: list[float]


def build_evidence_chain(
    answers: list[AnswerFeatures],
    questions: list[dict],
    position: str,
    theta_trajectory: list[float],
) -> EvaluationReport:
    if len(answers) != len(questions):
        raise ValueError(f"answers ({len(answers)}) and questions ({len(questions)}) must have the same length")

    dim_map = POSITION_DIMENSION_MAP.get(position, POSITION_DIMENSION_MAP["backend"])
    evidence_items: list[EvidenceItem] = []
    dimension_scores: dict[str, list[int]] = defaultdict(list)

    for features, question in zip(answers, questions):
        domain = question.get("domain", "behavioral")
        dimension = dim_map.get(domain, "soft_skills")
        delta, raw_evidence = features_to_score_delta(features)
        raw_score = max(0, min(100, 50 + delta))
        dimension_scores[dimension].append(raw_score)
        question_difficulty = question.get("difficulty", 0.5)

        for ev in raw_evidence:
            evidence_items.append(
                EvidenceItem(
                    dimension=dimension,
                    question=question.get("question_template", ""),
                    concept=question.get("concept", ""),
                    score_delta=ev["score_delta"],
                    evidence_text=ev["evidence_text"],
                    evidence_type=ev["evidence_type"],
                    difficulty=question_difficulty,
                )
            )

    final_dims = {d: round(mean(scores)) for d, scores in dimension_scores.items()}
    overall = max(0, min(100, round(sum(final_dims.values()) / max(len(final_dims), 1))))

    return EvaluationReport(
        overall=overall,
        dimensions=final_dims,
        evidence_chain=evidence_items,
        theta_trajectory=theta_trajectory,
    )
