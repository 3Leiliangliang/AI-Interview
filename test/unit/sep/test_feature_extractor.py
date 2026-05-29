import pytest
from src.services.sep.feature_extractor import AnswerFeatures, extract_features

SAMPLE_RUBRIC = {
    "required": ["SYN", "SYN-ACK", "ACK"],
    "bonus": ["TIME_WAIT", "半连接队列"],
    "misconceptions": ["四次握手建立连接"],
}


def test_full_required_hit():
    answer = "TCP建立连接需要三次握手：客户端发SYN，服务器回SYN-ACK，客户端再发ACK。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.required_hit_rate == 1.0


def test_partial_required_hit():
    answer = "TCP握手需要发SYN包。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.required_hit_rate == pytest.approx(1 / 3, abs=0.01)


def test_bonus_hit():
    answer = "完成握手后进入TIME_WAIT状态，还有半连接队列的概念。SYN SYN-ACK ACK都要走。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.bonus_hit_count == 2


def test_misconception_detected():
    answer = "TCP需要四次握手建立连接，发SYN后还要再发一次。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.misconception_count == 1


def test_star_action_detected():
    answer = "在项目中（背景）我负责优化连接池（任务），我实现了连接复用机制（行动），最终降低了30%延迟（结果）。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.star_scores["S"] is True
    assert feat.star_scores["T"] is True
    assert feat.star_scores["A"] is True
    assert feat.star_scores["R"] is True


def test_hedge_ratio():
    answer = "可能是SYN，也许还有ACK，大概是这样的流程，我觉得差不多。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.hedge_ratio > 0.15


def test_empty_answer():
    feat = extract_features("", SAMPLE_RUBRIC)
    assert feat.required_hit_rate == 0.0
    assert feat.bonus_hit_count == 0
    assert feat.misconception_count == 0
    assert feat.hedge_ratio == 0.0


def test_answer_score_high_for_complete_answer():
    answer = "SYN SYN-ACK ACK都走一遍，TIME_WAIT和半连接队列我也知道。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.to_answer_score() > 0.7


def test_answer_score_low_for_misconception():
    answer = "四次握手建立连接，可能是这样的。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.to_answer_score() < 0.3


def test_empty_rubric_yields_zero_required_hit_rate():
    """Regression: prior default of 0.5 inflated off-topic freeform answers."""
    answer = "ACID是指原子性、一致性、隔离性和持久性。"  # off-topic vs SAMPLE_RUBRIC
    feat = extract_features(answer, {})
    assert feat.required_hit_rate == 0.0


def test_off_topic_answer_with_star_words_stays_low():
    """An answer that hits STAR keywords but no rubric required keywords must NOT cross 0.5."""
    answer = "在项目中我负责实现一个功能，最终上线了。"  # all STAR words, zero TCP coverage
    feat = extract_features(answer, SAMPLE_RUBRIC)
    score = feat.to_answer_score()
    assert score <= 0.2, f"off-topic STAR-only answer must stay low, got {score}"
