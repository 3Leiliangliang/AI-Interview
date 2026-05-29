from __future__ import annotations

from src.services.sep.feature_extractor import AnswerFeatures

POSITION_DIMENSION_MAP: dict[str, dict[str, str]] = {
    "backend": {
        "networking": "technical_competence",
        "database": "technical_competence",
        "algorithms": "problem_solving",
        "system_design": "problem_solving",
        "language": "technical_competence",
        "behavioral": "soft_skills",
    },
    "frontend": {
        "javascript": "technical_competence",
        "css": "technical_competence",
        "frameworks": "technical_competence",
        "algorithms": "problem_solving",
        "performance": "problem_solving",
        "behavioral": "soft_skills",
    },
    "algorithm": {
        "algorithms": "problem_solving",
        "data_structures": "problem_solving",
        "math": "technical_competence",
        "system_design": "technical_competence",
        "behavioral": "soft_skills",
    },
}


def features_to_score_delta(features: AnswerFeatures) -> tuple[int, list[dict]]:
    """
    Convert an AnswerFeatures into a (total_delta, evidence_items) pair.

    Returns:
        total_delta: int to be added to a 50-point baseline to get raw score.
        evidence_items: list of dicts with keys evidence_type, score_delta, evidence_text.
    """
    evidence: list[dict] = []
    total_delta = 0

    # Required keyword coverage: max +15
    req_score = round(features.required_hit_rate * 15)
    if req_score > 0:
        total_delta += req_score
        evidence.append(
            {
                "evidence_type": "keyword_hit",
                "score_delta": req_score,
                "evidence_text": f"覆盖了 {round(features.required_hit_rate * 100)}% 的核心知识点",
            }
        )

    # Bonus keyword hits: max +10
    if features.bonus_hit_count > 0:
        bonus_score = min(10, features.bonus_hit_count * 3)
        total_delta += bonus_score
        evidence.append(
            {
                "evidence_type": "bonus_keyword",
                "score_delta": bonus_score,
                "evidence_text": f"提及了 {features.bonus_hit_count} 个加分知识点",
            }
        )

    # Misconception penalty: max -15
    if features.misconception_count > 0:
        penalty = -min(15, features.misconception_count * 8)
        total_delta += penalty
        evidence.append(
            {
                "evidence_type": "misconception",
                "score_delta": penalty,
                "evidence_text": f"包含 {features.misconception_count} 处概念误区",
            }
        )

    # STAR structure: max +8
    star_count = sum(features.star_scores.values())
    star_score = round(star_count / 4 * 8)
    if star_score > 0:
        total_delta += star_score
        completed = [k for k, v in features.star_scores.items() if v]
        evidence.append(
            {
                "evidence_type": "star_complete",
                "score_delta": star_score,
                "evidence_text": f"回答包含 STAR 结构中的 {'/'.join(completed)} 部分",
            }
        )

    # Hedge penalty: triggered only above 5% hedge ratio
    if features.hedge_ratio > 0.05:
        hedge_penalty = -round(features.hedge_ratio * 5)
        if hedge_penalty != 0:
            total_delta += hedge_penalty
            evidence.append(
                {
                    "evidence_type": "hedge",
                    "score_delta": hedge_penalty,
                    "evidence_text": f"表达中含有较多不确定词（{round(features.hedge_ratio * 100)}%）",
                }
            )

    return total_delta, evidence
