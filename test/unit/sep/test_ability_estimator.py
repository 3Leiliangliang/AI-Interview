import pytest
from src.services.sep.ability_estimator import update_ability


def test_ability_increases_on_easy_correct():
    """Answering an easy question (diff=0.3) correctly should raise ability above 0.5."""
    theta = 0.5
    new_theta = update_ability(theta, question_difficulty=0.3, answer_score=1.0)
    assert new_theta > theta


def test_ability_decreases_on_hard_wrong():
    """Failing a hard question (diff=0.8) should lower ability below 0.5."""
    theta = 0.5
    new_theta = update_ability(theta, question_difficulty=0.8, answer_score=0.0)
    assert new_theta < theta


def test_ability_clamped_at_max():
    """Ability must never exceed 0.9."""
    theta = 0.88
    new_theta = update_ability(theta, question_difficulty=0.1, answer_score=1.0)
    assert new_theta <= 0.9


def test_ability_clamped_at_min():
    """Ability must never fall below 0.1."""
    theta = 0.12
    new_theta = update_ability(theta, question_difficulty=0.9, answer_score=0.0)
    assert new_theta >= 0.1


def test_moderate_answer_keeps_ability_close():
    """A 0.5 score on a difficulty=0.5 question leaves theta nearly unchanged."""
    theta = 0.5
    new_theta = update_ability(theta, question_difficulty=0.5, answer_score=0.5)
    assert abs(new_theta - theta) < 0.05


def test_output_is_float():
    result = update_ability(0.5, 0.5, 0.8)
    assert isinstance(result, float)
