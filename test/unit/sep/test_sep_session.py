import pytest
from src.services.sep import SEPSession


def test_session_produces_report_after_answers():
    session = SEPSession(position="backend")
    for _ in range(5):
        q = session.next_question()
        if q is None:
            break
        session.record_answer(q, "SYN SYN-ACK ACK，三次握手，我实现过连接池，最终降低了延迟。")
    report = session.build_report()
    assert 0 <= report.overall <= 100
    assert len(report.evidence_chain) > 0


def test_theta_updates_with_each_answer():
    session = SEPSession(position="backend")
    q = session.next_question()
    initial_theta = session.theta
    session.record_answer(q, "SYN SYN-ACK ACK TIME_WAIT 半连接队列全部覆盖。")
    assert session.theta != initial_theta


def test_asked_ids_tracked():
    session = SEPSession(position="backend")
    q = session.next_question()
    session.record_answer(q, "some answer")
    assert q["id"] in session.asked_ids


def test_theta_trajectory_grows():
    session = SEPSession(position="backend")
    q = session.next_question()
    session.record_answer(q, "SYN SYN-ACK ACK")
    assert len(session.theta_trajectory) == 2  # initial + after first answer


def test_no_duplicate_questions():
    session = SEPSession(position="backend")
    seen = set()
    for _ in range(10):
        q = session.next_question()
        if q is None:
            break
        assert q["id"] not in seen
        seen.add(q["id"])
        session.record_answer(q, "answer")
