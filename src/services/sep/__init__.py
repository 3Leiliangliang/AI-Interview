from __future__ import annotations

from dataclasses import dataclass, field

from src.services.sep.ability_estimator import update_ability
from src.services.sep.adaptive_selector import load_question_bank, select_next_question
from src.services.sep.evidence_builder import EvaluationReport, build_evidence_chain
from src.services.sep.feature_extractor import extract_features

__all__ = ["SEPSession"]


@dataclass
class SEPSession:
    position: str
    theta: float = 0.5
    asked_ids: set[str] = field(default_factory=set)
    asked_domains: set[str] = field(default_factory=set)
    _answer_features: list = field(default_factory=list, repr=False)
    _answered_questions: list = field(default_factory=list, repr=False)
    theta_trajectory: list[float] = field(default_factory=lambda: [0.5])
    _question_bank: list[dict] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._question_bank = load_question_bank(self.position)

    def next_question(self) -> dict | None:
        return select_next_question(
            self.theta,
            self.asked_ids,
            self._question_bank,
            self.asked_domains,
        )

    def record_answer(self, question: dict, answer_text: str) -> None:
        q_id = question.get("id")
        difficulty = question.get("difficulty")
        if q_id is None or difficulty is None:
            raise ValueError(f"Question must contain 'id' and 'difficulty', got: {list(question.keys())}")
        features = extract_features(answer_text, question.get("rubric", {}))
        answer_score = features.to_answer_score()
        self.theta = update_ability(self.theta, difficulty, answer_score)
        self.theta_trajectory.append(round(self.theta, 4))
        self.asked_ids.add(q_id)
        self.asked_domains.add(question.get("domain", "behavioral"))
        self._answer_features.append(features)
        self._answered_questions.append(question)

    def build_report(self) -> EvaluationReport:
        return build_evidence_chain(
            self._answer_features,
            self._answered_questions,
            self.position,
            self.theta_trajectory,
        )
