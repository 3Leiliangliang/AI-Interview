from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import interview_coding_service as service  # noqa: E402


def test_build_sample_run_result_matches_semantic_output():
    result = service._build_sample_run_result(
        [{"input": "nums = [2, 7, 11, 15], target = 9", "output": "[0, 1]"}],
        {"err": False, "data": [{"result": -1, "output": "[0,1]"}]},
    )

    assert result["status"] == "ACCEPTED"
    assert result["passed"] is True
    assert result["tests"][0]["status"] == "ACCEPTED"


def test_build_seed_problem_sample_source_wraps_function_solution():
    wrapped = service._build_seed_problem_sample_source(
        {
            "source": service.OJ_PROBLEM_SOURCE,
            "starter_code": {
                "javascript": "function maxSubArray(nums) {\n  return 0\n}\n",
            },
        },
        "javascript",
        "function maxSubArray(nums) {\n  return nums[0]\n}\n",
    )

    assert "Promise.resolve(maxSubArray(...__sampleArgs))" in wrapped
    assert "__sampleParseArgs" in wrapped
    assert "require('fs').readFileSync(0, 'utf8')" in wrapped


def test_normalize_position_tag_maps_extended_categories():
    assert service._normalize_position_tag("数据库") == "backend"
    assert service._normalize_position_tag("系统设计") == "backend"
    assert service._normalize_position_tag("AI 应用开发") == "backend"
    assert service._normalize_position_tag("算法与数据结构") == service.GENERAL_POSITION_TAG
