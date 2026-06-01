from __future__ import annotations
import math


def update_ability(theta: float, question_difficulty: float, answer_score: float) -> float:
    """
    Bayesian IRT update: move theta toward answer_score, scaled by how surprising the result was.

    Args:
        theta: Current ability estimate in [0.1, 0.9].
        question_difficulty: Question difficulty in [0.1, 0.9].
        answer_score: Normalised answer quality in [0.0, 1.0].

    Returns:
        Updated theta clamped to [0.1, 0.9].
    """
    expected = 1.0 / (1.0 + math.exp(-3.0 * (theta - question_difficulty)))
    error = answer_score - expected
    return max(0.1, min(0.9, theta + 0.3 * error))
