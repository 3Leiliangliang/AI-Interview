"""Unit tests for internal observation sanitization helpers."""

from src.utils.internal_observation import (
    InternalObservationStreamSanitizer,
    strip_internal_observation_text,
)


def test_strip_internal_observation_block():
    text = (
        "您好。\n"
        "<internal_interview_observation>\n"
        "[[video_observation_internal]] internal_only=true\n"
        "[[video_observation_internal]] 情绪=愉悦\n"
        "</internal_interview_observation>\n"
        "现在开始提问。"
    )

    cleaned = strip_internal_observation_text(text)
    assert "<internal_interview_observation>" not in cleaned
    assert "</internal_interview_observation>" not in cleaned
    assert "[[video_observation_internal]]" not in cleaned
    assert "现在开始提问。" in cleaned


def test_strip_orphan_closing_tag():
    text = "面试继续进行。</internal_interview_observation>请介绍项目。"
    cleaned = strip_internal_observation_text(text)
    assert cleaned == "面试继续进行。请介绍项目。"


def test_stream_sanitizer_filters_split_internal_block():
    sanitizer = InternalObservationStreamSanitizer()
    first = sanitizer.feed("您好，状态不错。<internal_interview_obs")
    second = sanitizer.feed(
        "ervation>\n[[video_observation_internal]] 情绪=愉悦\n</internal_interview_observation>现在开始提问。"
    )
    tail = sanitizer.flush()

    assert "<internal_interview_observation>" not in first + second + tail
    assert "</internal_interview_observation>" not in first + second + tail
    assert "您好，状态不错。" in first + second + tail
    assert "现在开始提问。" in first + second + tail


def test_stream_sanitizer_no_leak_when_start_tag_unclosed():
    sanitizer = InternalObservationStreamSanitizer()
    first = sanitizer.feed("继续。<internal_interview_observ")
    tail = sanitizer.flush()

    assert first == "继续。"
    assert tail == ""
