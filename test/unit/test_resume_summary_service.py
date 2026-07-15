from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.resume_summary_service import ResumeSummaryService


@pytest.fixture
def service() -> ResumeSummaryService:
    return ResumeSummaryService()


@pytest.mark.parametrize(
    "content",
    [
        '[{"skills": []}]',
        '```json\n[{"skills": []}]\n```',
        '"summary"',
        "42",
        "true",
        "null",
    ],
)
def test_parse_json_response_rejects_non_object_values(service: ResumeSummaryService, content: str) -> None:
    assert service._parse_json_response(content) is None


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"skills": {"technical": ["Python"]}}', {"skills": {"technical": ["Python"]}}),
        ('```json\n{"skills": {}}\n```', {"skills": {}}),
        ('Result: {"skills": {}}', {"skills": {}}),
    ],
)
def test_parse_json_response_accepts_objects(service: ResumeSummaryService, content: str, expected: dict) -> None:
    assert service._parse_json_response(content) == expected


async def test_extract_summary_retries_after_array_response(
    service: ResumeSummaryService,
) -> None:
    model = AsyncMock()
    first_response = MagicMock(content='[{"skills": []}]')
    expected = {"skills": {"technical": ["Python"]}}
    second_response = MagicMock(content=json.dumps(expected))
    model.ainvoke.side_effect = [first_response, second_response]

    with (
        patch("src.services.resume_summary_service.load_chat_model", return_value=model),
        patch("src.services.resume_summary_service.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await service.extract_summary("Python developer resume")

    assert result == expected
    assert model.ainvoke.await_count == 2
