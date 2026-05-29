from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services import interview_result_service as service  # noqa: E402


def test_generate_improvement_plan_builds_structured_sections(monkeypatch):
    async def fake_get_databases_by_raw_id(_user_id: int):
        return {"databases": [{"db_id": "kb-1", "name": "后端知识库"}]}

    async def fake_get_databases_by_user_id(_user_id: str):
        return {"databases": [{"db_id": "kb-1", "name": "后端知识库"}]}

    async def fake_aquery(_query_text: str, db_id: str, **_kwargs):
        return [
            {
                "content": "JVM 垃圾回收机制需要从分代回收、可达性分析和典型收集器角度理解。",
                "score": 0.91,
                "metadata": {
                    "source": "jvm-guide.md",
                    "file_id": "file-1",
                    "chunk_id": "chunk-1",
                    "chunk_index": 3,
                },
            }
        ]

    monkeypatch.setattr(service.knowledge_base, "get_databases_by_raw_id", fake_get_databases_by_raw_id)
    monkeypatch.setattr(service.knowledge_base, "get_databases_by_user_id", fake_get_databases_by_user_id)
    monkeypatch.setattr(service.knowledge_base, "aquery", fake_aquery)
    monkeypatch.setattr(
        service,
        "list_imported_problem_packages",
        lambda: {
            "problems": [
                {
                    "title": "二叉树层序遍历",
                    "summary": "考察队列、层次遍历和边界处理",
                    "topic_tags": ["算法", "边界"],
                    "primary_position_tag": "backend",
                    "difficulty_tag": "medium",
                    "package_path": "demo.xml",
                    "problem_index": 1,
                }
            ]
        },
    )

    conversation = SimpleNamespace(user_id="user-1", extra_metadata={"target_position": "后端工程师"})
    scorecard = {
        "role": "后端工程师",
        "round": "初试",
        "dimensions": [
            {"name": "技术能力", "score": 62},
            {"name": "问题解决", "score": 68},
            {"name": "沟通表达", "score": 82},
            {"name": "综合素质", "score": 79},
        ],
        "risks": ["技术基础回答不够扎实", "算法边界条件覆盖不足"],
        "suggestions": ["建议补强基础原理和题目拆解能力"],
    }
    coding_session = {
        "target_position": "后端工程师",
        "difficulty_level": "medium",
        "judge_status": "WRONG_ANSWER",
        "judge_result": {"score": 55},
    }
    expression_analysis = {
        "summary": "本轮语音回答表达较清晰，但结论先行不足。",
    }

    plan = asyncio.run(
        service._generate_improvement_plan(
            conversation=conversation,
            scorecard=scorecard,
            expression_analysis=expression_analysis,
            coding_session=coding_session,
        )
    )

    assert plan is not None
    assert len(plan["weaknesses"]) >= 2
    assert len(plan["recommended_resources"]) >= 2
    assert len(plan["practice_tasks"]) >= 2
    assert len(plan["next_assessment_focus"]) >= 2
    assert {item["resource_type"] for item in plan["recommended_resources"]} >= {"knowledge", "interview_question"}
    knowledge_resource = next(item for item in plan["recommended_resources"] if item["resource_type"] == "knowledge")
    assert knowledge_resource["source_type"] == "knowledge_chunk"
    assert knowledge_resource["locator"] == {
        "db_id": "kb-1",
        "file_id": "file-1",
        "chunk_id": "chunk-1",
        "chunk_index": 3,
        "keyword": "基础",
        "query_text": "技术基础回答不够扎实",
    }
    assert "action_plan" in plan
    assert [step["step_type"] for step in plan["action_plan"]["steps"]] == ["learn", "practice", "recheck"]


def test_generate_improvement_plan_includes_filtered_external_resources(monkeypatch):
    async def fake_get_databases_by_raw_id(_user_id: int):
        return {"databases": [{"db_id": "kb-1", "name": "后端知识库"}]}

    async def fake_get_databases_by_user_id(_user_id: str):
        return {"databases": [{"db_id": "kb-1", "name": "后端知识库"}]}

    async def fake_aquery(_query_text: str, db_id: str, **_kwargs):
        return [
            {
                "content": "Redis 缓存一致性要从延迟双删、旁路缓存和更新顺序理解。",
                "score": 0.91,
                "metadata": {
                    "source": "redis-guide.md",
                    "file_id": "file-1",
                    "chunk_id": "chunk-1",
                    "chunk_index": 1,
                },
            }
        ]

    class FakeSearcher:
        def search(self, query: str, max_results: int = 1, search_depth: str = "basic", timeout: int = 20):
            assert "后端工程师" in query
            assert search_depth == "advanced"
            if "官方文档 教程 博客" in query:
                return [
                    {
                        "title": "缓存模式入门",
                        "content": "泛泛介绍缓存模式，不包含关键细节。",
                        "url": "https://juejin.cn/post/cache-intro",
                        "score": 0.41,
                    },
                    {
                        "title": "Redis 官方文档：缓存一致性与 Cache Aside",
                        "content": "官方解释 Cache Aside、延迟双删和缓存一致性策略。",
                        "url": "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/",
                        "score": 0.92,
                    },
                    {
                        "title": "低质量来源",
                        "content": "不应进入推荐结果。",
                        "url": "https://example.com/random-post",
                        "score": 0.99,
                    },
                ][:max_results]
            if "视频 讲解 实战" in query:
                return [
                    {
                        "title": "缓存一致性泛读视频",
                        "content": "简单介绍缓存一致性。",
                        "url": "https://www.bilibili.com/video/BV1low000000",
                        "score": 0.2,
                    },
                    {
                        "title": "B 站缓存一致性实战视频",
                        "content": "通过案例讲缓存一致性、延迟双删和旁路缓存。",
                        "url": "https://www.bilibili.com/video/BV1abc411111",
                        "score": 0.88,
                    },
                ][:max_results]
            return []

    monkeypatch.setattr(service.knowledge_base, "get_databases_by_raw_id", fake_get_databases_by_raw_id)
    monkeypatch.setattr(service.knowledge_base, "get_databases_by_user_id", fake_get_databases_by_user_id)
    monkeypatch.setattr(service.knowledge_base, "aquery", fake_aquery)
    monkeypatch.setattr(service, "_create_web_searcher", lambda: FakeSearcher())
    monkeypatch.setattr(service.config, "enable_web_search", True)
    monkeypatch.setattr(
        service,
        "list_imported_problem_packages",
        lambda: {
            "problems": [
                {
                    "title": "LRU 缓存实现",
                    "summary": "考察链表和哈希表",
                    "topic_tags": ["缓存", "设计"],
                    "primary_position_tag": "backend",
                    "difficulty_tag": "medium",
                    "package_path": "demo.xml",
                    "problem_index": 1,
                }
            ]
        },
    )

    conversation = SimpleNamespace(user_id="user-1", extra_metadata={"target_position": "后端工程师"})
    scorecard = {
        "role": "后端工程师",
        "round": "初试",
        "dimensions": [
            {"name": "技术能力", "score": 58},
            {"name": "问题解决", "score": 70},
            {"name": "沟通表达", "score": 82},
            {"name": "综合素质", "score": 80},
        ],
        "risks": ["缓存一致性回答不够扎实"],
        "suggestions": ["建议补强 Redis 缓存一致性和缓存模式"],
    }
    technical_question_reviews = [
        {
            "question_index": 1,
            "question": "什么是缓存一致性",
            "score": 42,
            "level": "待提升",
            "matched_keywords": ["Redis"],
            "suggested_keywords": ["缓存一致性", "延迟双删"],
            "strengths": [],
            "gaps": ["缺少关键机制"],
        }
    ]

    plan = asyncio.run(
        service._generate_improvement_plan(
            conversation=conversation,
            scorecard=scorecard,
            expression_analysis=None,
            coding_session=None,
            technical_question_reviews=technical_question_reviews,
        )
    )

    assert plan is not None
    external_resources = [item for item in plan["recommended_resources"] if item["source_type"] == "web_search"]
    assert len(external_resources) == 2
    assert {item["resource_type"] for item in external_resources} == {"article", "video"}
    assert all(item["is_external"] is True for item in external_resources)
    assert all(item["url"].startswith("https://") for item in external_resources)
    assert all(item["provider"] for item in external_resources)
    assert all(item["reason"] for item in external_resources)
    assert not any("example.com" in item["url"] for item in external_resources)
    article_resource = next(item for item in external_resources if item["resource_type"] == "article")
    video_resource = next(item for item in external_resources if item["resource_type"] == "video")
    assert article_resource["title"] == "Redis 官方文档：缓存一致性与 Cache Aside"
    assert video_resource["title"] == "B 站缓存一致性实战视频"
    assert article_resource["search_score"] > video_resource["search_score"] > service.EXTERNAL_RESOURCE_MIN_SCORE
    assert "延迟双删" in article_resource["reason"]
    # Reason should cite the actual low score (was: "当前维度得分约为 58 分");
    # P1 wording change kept the score grounded but rephrased the sentence.
    assert "58 分" in article_resource["reason"]


def test_search_external_learning_resources_prioritizes_high_score_and_diverse_types(monkeypatch):
    class FakeSearcher:
        def search(self, query: str, max_results: int = 1, search_depth: str = "basic", timeout: int = 20):
            assert search_depth == "advanced"
            if "官方文档 教程 博客" in query:
                return [
                    {
                        "title": "低分博客",
                        "content": "泛泛介绍缓存。",
                        "url": "https://juejin.cn/post/cache-low",
                        "score": 0.4,
                    },
                    {
                        "title": "Redis 缓存一致性文章",
                        "content": "详细说明延迟双删、Cache Aside 和更新顺序。",
                        "url": "https://www.redis.io/docs/latest/develop/clients/patterns/distributed-locks/",
                        "score": 0.96,
                    },
                ][:max_results]
            if "视频 讲解 实战" in query:
                return [
                    {
                        "title": "缓存一致性泛读视频",
                        "content": "简单介绍缓存一致性。",
                        "url": "https://www.bilibili.com/video/BV1low000000",
                        "score": 0.22,
                    },
                    {
                        "title": "B 站缓存一致性实战视频",
                        "content": "通过案例讲延迟双删和旁路缓存。",
                        "url": "https://www.bilibili.com/video/BV1high00000",
                        "score": 0.89,
                    },
                ][:max_results]
            return [
                {
                    "title": "缓存一致性案例复盘",
                    "content": "从面试问答复盘延迟双删与更新顺序。",
                    "url": "https://infoq.cn/article/cache-case",
                    "score": 0.87,
                }
            ][:max_results]

    monkeypatch.setattr(service, "_create_web_searcher", lambda: FakeSearcher())

    resources = asyncio.run(
        service._search_external_learning_resources(
            target_position="后端工程师",
            dimension_key="technical_competence",
            weakness_reason="缓存一致性回答不够扎实",
            technical_question_reviews=[
                {
                    "question": "什么是缓存一致性",
                    "score": 40,
                    "matched_keywords": ["Redis"],
                    "suggested_keywords": ["缓存一致性", "延迟双删"],
                }
            ],
        )
    )

    assert {item["resource_type"] for item in resources[:3]} == {"article", "video", "case"}
    assert resources[0]["title"] == "Redis 缓存一致性文章"
    assert resources[0]["search_score"] >= resources[1]["search_score"] >= resources[2]["search_score"]
    assert all(item["search_score"] >= service.EXTERNAL_RESOURCE_MIN_SCORE for item in resources)
    assert not any(item["title"] == "缓存一致性泛读视频" for item in resources)


def test_build_external_resource_reason_uses_content_and_weakness_context():
    reason = service._build_external_resource_reason(
        dimension_label="技术能力",
        focus_keyword="延迟双删",
        weakness_reason="缓存一致性回答不够扎实，缺少对延迟双删和 Cache Aside 的说明。",
        resource_title="Redis 缓存一致性深入讲解",
        resource_content="文章详细拆解延迟双删、Cache Aside、更新顺序和常见面试追问。",
        resource_type="article",
    )

    assert "延迟双删" in reason
    assert "Cache Aside" in reason
    assert "缓存一致性回答不够扎实" in reason


def test_clean_resource_text_decodes_html_entities():
    assert service._clean_resource_text("BRT&nbsp;Contract &amp; Cache") == "BRT Contract & Cache"


def test_build_history_profile_aggregates_recent_completed_records():
    records = [
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 60},
                {"key": "problem_solving", "score": 70},
            ],
            "improvement_plan": {
                "practice_tasks": [{"title": "task-1"}],
                "next_assessment_focus": [
                    {
                        "dimension_key": "technical_competence",
                        "title": "技术细节表达",
                        "focus": "关注原理说明",
                    }
                ],
            },
        },
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 65},
                {"key": "problem_solving", "score": 85},
            ],
            "improvement_plan": {
                "practice_tasks": [{"title": "task-2"}, {"title": "task-3"}],
                "next_assessment_focus": [
                    {
                        "dimension_key": "problem_solving",
                        "title": "解题思路完整度",
                        "focus": "关注边界覆盖",
                    }
                ],
            },
        },
    ]

    profile = service._build_history_profile(records)

    assert profile["pending_practice_count"] == 1
    assert profile["latest_focus"][0]["dimension_key"] == "technical_competence"
    assert profile["top_weakness_dimensions"][0]["dimension_key"] == "technical_competence"
    assert profile["top_strength_dimensions"][0]["dimension_key"] == "problem_solving"


def test_build_history_profile_keeps_weakness_and_strength_dimensions_disjoint():
    records = [
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 70},
                {"key": "problem_solving", "score": 74},
                {"key": "communication", "score": 80},
                {"key": "soft_skills", "score": 86},
            ],
            "improvement_plan": {"practice_tasks": [], "next_assessment_focus": []},
        },
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 72},
                {"key": "problem_solving", "score": 75},
                {"key": "communication", "score": 82},
                {"key": "soft_skills", "score": 84},
            ],
            "improvement_plan": {"practice_tasks": [], "next_assessment_focus": []},
        },
    ]

    profile = service._build_history_profile(records)

    weakness_keys = {item["dimension_key"] for item in profile["top_weakness_dimensions"]}
    strength_keys = {item["dimension_key"] for item in profile["top_strength_dimensions"]}

    assert weakness_keys == {"technical_competence", "problem_solving"}
    assert strength_keys == {"communication", "soft_skills"}
    assert weakness_keys.isdisjoint(strength_keys)


def test_build_history_profile_returns_empty_strengths_when_all_dimensions_are_weaknesses():
    records = [
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 70},
                {"key": "problem_solving", "score": 72},
            ],
            "improvement_plan": {"practice_tasks": [], "next_assessment_focus": []},
        },
        {
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 71},
                {"key": "problem_solving", "score": 73},
            ],
            "improvement_plan": {"practice_tasks": [], "next_assessment_focus": []},
        },
    ]

    profile = service._build_history_profile(records)

    assert [item["dimension_key"] for item in profile["top_weakness_dimensions"]] == [
        "technical_competence",
        "problem_solving",
    ]
    assert profile["top_strength_dimensions"] == []


def test_build_personalized_path_aggregates_multi_round_improvement_plans():
    records = [
        {
            "thread_id": "thread-1",
            "title": "后端工程师 · 一面",
            "updated_at": "2026-04-18T10:00:00Z",
            "position": "后端工程师",
            "round": "一面",
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 60},
                {"key": "problem_solving", "score": 72},
                {"key": "communication", "score": 80},
            ],
            "strengths": ["项目表达比较完整"],
            "improvement_plan": {
                "weaknesses": [
                    {
                        "dimension_key": "technical_competence",
                        "title": "技术基础还需要补强",
                        "reason": "缓存一致性解释不够扎实。",
                    }
                ],
                "recommended_resources": [
                    {
                        "resource_type": "knowledge",
                        "title": "缓存一致性知识卡",
                        "summary": "回看缓存一致性与延迟双删。",
                        "source_type": "knowledge_chunk",
                        "source_ref": "knowledge-chunk://kb-1/file-1#chunk-1",
                        "locator": {
                            "db_id": "kb-1",
                            "file_id": "file-1",
                            "chunk_id": "chunk-1",
                            "chunk_index": 1,
                            "keyword": "缓存一致性",
                            "query_text": "缓存一致性解释不够扎实",
                        },
                    }
                ],
                "practice_tasks": [
                    {
                        "title": "梳理关键知识点",
                        "objective": "复盘缓存一致性关键机制。",
                        "action_type": "knowledge_review",
                        "estimated_minutes": 35,
                    }
                ],
                "next_assessment_focus": [
                    {
                        "dimension_key": "technical_competence",
                        "title": "技术细节表达",
                        "focus": "下次重点看是否能解释缓存模式差异。",
                    }
                ],
                "action_plan": {
                    "title": "7 天提升路径",
                    "summary": "先补知识，再练习。",
                    "steps": [
                        {
                            "step_type": "learn",
                            "title": "先补技术基础",
                            "objective": "补缓存一致性知识。",
                            "estimated_minutes": 25,
                            "related_dimension_key": "technical_competence",
                            "resource_refs": ["knowledge-chunk://kb-1/file-1#chunk-1"],
                            "success_signal": "能解释核心机制。",
                        }
                    ],
                },
            },
        },
        {
            "thread_id": "thread-2",
            "title": "后端工程师 · 二面",
            "updated_at": "2026-04-17T10:00:00Z",
            "position": "后端工程师",
            "round": "二面",
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 62},
                {"key": "problem_solving", "score": 68},
                {"key": "communication", "score": 78},
            ],
            "strengths": ["项目表达比较完整", "沟通节奏稳定"],
            "improvement_plan": {
                "weaknesses": [
                    {
                        "dimension_key": "technical_competence",
                        "title": "技术基础还需要补强",
                        "reason": "基础原理回答还是偏泛。",
                    },
                    {
                        "dimension_key": "problem_solving",
                        "title": "题目拆解与实现稳定性偏弱",
                        "reason": "边界覆盖不完整。",
                    },
                ],
                "recommended_resources": [
                    {
                        "resource_type": "knowledge",
                        "title": "缓存一致性知识卡",
                        "summary": "回看缓存一致性与延迟双删。",
                        "source_type": "knowledge_chunk",
                        "source_ref": "knowledge-chunk://kb-1/file-1#chunk-1",
                        "locator": {
                            "db_id": "kb-1",
                            "file_id": "file-1",
                            "chunk_id": "chunk-1",
                            "chunk_index": 1,
                            "keyword": "缓存一致性",
                            "query_text": "基础原理回答还是偏泛",
                        },
                    },
                    {
                        "resource_type": "interview_question",
                        "title": "LRU 缓存实现",
                        "summary": "练习链表和哈希表。",
                        "source_type": "problem_package",
                        "source_ref": "problem://backend/demo.xml#1",
                        "problem_ref": "backend/demo.xml#1",
                    },
                ],
                "practice_tasks": [
                    {
                        "title": "完成定向算法练习",
                        "objective": "完成一道缓存结构题。",
                        "action_type": "coding_practice",
                        "estimated_minutes": 45,
                    }
                ],
                "next_assessment_focus": [
                    {
                        "dimension_key": "problem_solving",
                        "title": "解题思路完整度",
                        "focus": "下次重点看边界覆盖和复杂度说明。",
                    }
                ],
            },
        },
        {
            "thread_id": "thread-3",
            "title": "后端工程师 · 三面",
            "updated_at": "2026-04-16T10:00:00Z",
            "position": "后端工程师",
            "round": "三面",
            "has_result": False,
            "status": "in_progress",
            "dimensions": [],
            "improvement_plan": None,
        },
    ]

    path = service._build_personalized_path(records)

    assert path["summary"]["top_priority_dimension"] == "technical_competence"
    assert path["summary"]["top_priority_label"] == "技术能力"
    assert path["source_round_count"] == 2
    assert len(path["recommended_resources"]) == 2
    assert path["recommended_resources"][0]["source_ref"] == "problem://backend/demo.xml#1"
    assert path["recommended_resources"][1]["source_ref"] == "knowledge-chunk://kb-1/file-1#chunk-1"
    assert len(path["practice_tasks"]) == 2
    assert path["next_assessment_focus"][0]["dimension_key"] == "technical_competence"
    assert path["action_plan"] is not None
    assert [step["step_type"] for step in path["action_plan"]["steps"]] == ["learn", "practice", "recheck"]
    assert path["strengths"] == ["项目表达比较完整", "沟通节奏稳定"]
    assert [item["thread_id"] for item in path["related_records"]] == ["thread-1", "thread-2"]


def test_build_personalized_path_returns_empty_state_for_no_completed_records():
    path = service._build_personalized_path(
        [
            {
                "thread_id": "thread-1",
                "has_result": False,
                "status": "in_progress",
                "dimensions": [],
                "improvement_plan": None,
            }
        ]
    )

    assert path["summary"]["stage_label"] == "待生成"
    assert path["source_round_count"] == 0
    assert path["weaknesses"] == []
    assert path["recommended_resources"] == []
    assert path["strengths"] == []
    assert path["action_plan"] is None


def test_build_personalized_path_prioritizes_clickable_external_resources():
    records = [
        {
            "thread_id": "thread-1",
            "title": "后端工程师 · 一面",
            "updated_at": "2026-04-18T10:00:00Z",
            "position": "后端工程师",
            "round": "一面",
            "has_result": True,
            "status": "completed",
            "dimensions": [
                {"key": "technical_competence", "score": 60},
                {"key": "problem_solving", "score": 78},
                {"key": "communication", "score": 82},
                {"key": "soft_skills", "score": 80},
            ],
            "strengths": ["表达稳定"],
            "improvement_plan": {
                "weaknesses": [
                    {
                        "dimension_key": "technical_competence",
                        "title": "技术基础还需要补强",
                        "reason": "缓存一致性解释不够扎实。",
                    }
                ],
                "recommended_resources": [
                    {
                        "resource_type": "knowledge",
                        "title": "内部知识卡",
                        "summary": "回看知识库片段。",
                        "source_type": "knowledge_chunk",
                        "source_ref": "knowledge-chunk://kb-1/file-1#chunk-1",
                        "locator": {
                            "db_id": "kb-1",
                            "file_id": "file-1",
                            "chunk_id": "chunk-1",
                            "chunk_index": 1,
                            "keyword": "缓存一致性",
                            "query_text": "缓存一致性",
                        },
                    },
                    {
                        "resource_type": "article",
                        "title": "Redis 官方文档",
                        "summary": "外部官方资料。",
                        "source_type": "web_search",
                        "source_ref": "web-search://redis.io/1",
                        "provider": "redis.io",
                        "url": "https://redis.io/docs/latest/",
                        "is_external": True,
                    },
                    {
                        "resource_type": "video",
                        "title": "B站讲解视频",
                        "summary": "视频讲解。",
                        "source_type": "web_search",
                        "source_ref": "web-search://bilibili.com/1",
                        "provider": "bilibili.com",
                        "url": "https://www.bilibili.com/video/BV1demo",
                        "is_external": True,
                    },
                ],
                "practice_tasks": [],
                "next_assessment_focus": [],
            },
        }
    ]

    path = service._build_personalized_path(records)

    assert len(path["recommended_resources"]) >= 2
    assert path["recommended_resources"][0]["is_external"] is True
    assert path["recommended_resources"][1]["is_external"] is True


def test_normalize_improvement_plan_keeps_learning_locator():
    payload = {
        "recommended_resources": [
            {
                "resource_type": "knowledge",
                "title": "JVM 精准学习",
                "summary": "回看垃圾回收机制相关片段。",
                "source_type": "knowledge_chunk",
                "source_id": "kb-1",
                "source_ref": "knowledge-chunk://kb-1/file-1#chunk-1",
                "locator": {
                    "db_id": "kb-1",
                    "file_id": "file-1",
                    "chunk_id": "chunk-1",
                    "chunk_index": 2,
                    "keyword": "JVM",
                    "query_text": "JVM 垃圾回收机制",
                },
            }
        ]
    }

    normalized = service._normalize_improvement_plan(payload)

    assert normalized is not None
    assert normalized["recommended_resources"][0]["locator"]["file_id"] == "file-1"
    assert normalized["recommended_resources"][0]["locator"]["chunk_index"] == 2


def test_normalize_improvement_plan_keeps_external_resources_and_action_plan():
    payload = {
        "recommended_resources": [
            {
                "resource_type": "article",
                "title": "Redis 官方文档",
                "summary": "理解缓存模式与一致性。",
                "source_type": "web_search",
                "source_id": "redis.io",
                "source_ref": "web-search://redis.io/cache-aside",
                "provider": "redis.io",
                "url": "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/",
                "reason": "与你这轮低分题里的缓存一致性直接相关。",
                "estimated_minutes": 18,
                "language": "zh",
                "difficulty": "进阶",
                "is_external": True,
            }
        ],
        "action_plan": {
            "title": "7 天提升路径",
            "summary": "先补知识，再做练习，最后回测。",
            "steps": [
                {
                    "step_type": "learn",
                    "title": "补缓存一致性知识",
                    "objective": "先把概念和常见策略讲清楚。",
                    "estimated_minutes": 25,
                    "related_dimension_key": "technical_competence",
                    "resource_refs": ["web-search://redis.io/cache-aside"],
                    "success_signal": "能独立解释 Cache Aside 和延迟双删。",
                }
            ],
        },
    }

    normalized = service._normalize_improvement_plan(payload)

    assert normalized is not None
    resource = normalized["recommended_resources"][0]
    assert resource["resource_type"] == "article"
    assert resource["provider"] == "redis.io"
    assert resource["url"].startswith("https://redis.io/")
    assert resource["reason"]
    assert resource["is_external"] is True
    assert normalized["action_plan"]["steps"][0]["step_type"] == "learn"
    assert normalized["action_plan"]["steps"][0]["resource_refs"] == ["web-search://redis.io/cache-aside"]


def test_normalize_improvement_plan_skips_invalid_learning_locator():
    payload = {
        "recommended_resources": [
            {
                "resource_type": "knowledge",
                "title": "无效资源",
                "summary": "缺少 file_id",
                "source_type": "knowledge_chunk",
                "locator": {"db_id": "kb-1", "chunk_id": "chunk-1"},
            }
        ]
    }

    normalized = service._normalize_improvement_plan(payload)

    assert normalized is not None
    assert "locator" not in normalized["recommended_resources"][0]


def test_normalize_improvement_plan_decodes_html_entities_in_resource_fields():
    payload = {
        "recommended_resources": [
            {
                "resource_type": "article",
                "title": "BRT&nbsp;Contract",
                "summary": "Cache&nbsp;Aside &amp; 延迟双删",
                "source_type": "web_search",
                "source_ref": "web-search://example/1",
                "provider": "redis.io",
                "url": "https://redis.io/docs/latest/",
                "reason": "适合补强&nbsp;缓存一致性",
                "is_external": True,
            }
        ]
    }

    normalized = service._normalize_improvement_plan(payload)

    assert normalized is not None
    resource = normalized["recommended_resources"][0]
    assert resource["title"] == "BRT Contract"
    assert resource["summary"] == "Cache Aside & 延迟双删"
    assert resource["reason"] == "适合补强 缓存一致性"


def test_get_accessible_databases_for_learning_prefers_raw_id(monkeypatch):
    captured = {}

    async def fake_get_databases_by_raw_id(user_id: int):
        captured["user_id"] = user_id
        return {"databases": []}

    monkeypatch.setattr(service.knowledge_base, "get_databases_by_raw_id", fake_get_databases_by_raw_id)

    result = asyncio.run(service._get_accessible_databases_for_learning("42"))

    assert result == {"databases": []}
    assert captured["user_id"] == 42


def test_get_interview_learning_document_returns_readonly_payload(monkeypatch):
    async def fake_check_accessible(_user, _db_id: str):
        return True

    async def fake_get_database_info(_db_id: str):
        return {
            "db_id": "kb-1",
            "name": "后端知识库",
            "files": {
                "file-1": {
                    "file_id": "file-1",
                    "filename": "jvm-guide.md",
                    "is_folder": False,
                }
            },
        }

    async def fake_get_file_info(_db_id: str, _file_id: str):
        return {
            "meta": {"filename": "jvm-guide.md", "is_folder": False},
            "content": "# JVM",
            "lines": [{"id": "chunk-1", "content": "垃圾回收机制", "chunk_order_index": 1}],
        }

    monkeypatch.setattr(service.knowledge_base, "check_accessible", fake_check_accessible)
    monkeypatch.setattr(service.knowledge_base, "get_database_info", fake_get_database_info)
    monkeypatch.setattr(service.knowledge_base, "get_file_info", fake_get_file_info)

    payload = asyncio.run(
        service.get_interview_learning_document(
            db_id="kb-1",
            file_id="file-1",
            current_user=SimpleNamespace(role="user"),
        )
    )

    assert payload["db_name"] == "后端知识库"
    assert payload["file_name"] == "jvm-guide.md"
    assert payload["lines"][0]["id"] == "chunk-1"


def test_collect_technical_question_reviews_tracks_question_answer_pairs():
    tool_call = SimpleNamespace(
        tool_name="pick_random_technical_question",
        status="success",
        tool_output=str(
            {
                "question": "什么是 Redis 持久化",
                "kb_name": "后端知识库",
                "db_id": "kb-1",
                "file_id": "file-1",
                "file_name": "redis.md",
                "chunk_id": "chunk-1",
                "chunk_index": 4,
            }
        ),
    )
    messages = [
        SimpleNamespace(
            role="assistant",
            content="",
            created_at=None,
            extra_metadata={},
            tool_calls=[tool_call],
        ),
        SimpleNamespace(
            role="assistant",
            content="我们来一道技术题：什么是 Redis 持久化？请分别说明 RDB 和 AOF。",
            created_at=None,
            extra_metadata={},
            tool_calls=[],
        ),
        SimpleNamespace(
            role="user",
            content="Redis 持久化主要有 RDB 和 AOF。RDB 适合做快照恢复，AOF 记录写命令，恢复更完整。",
            created_at=None,
            extra_metadata={},
            tool_calls=[],
        ),
    ]

    reviews = service._collect_technical_question_reviews(messages)

    assert len(reviews) == 1
    assert reviews[0]["question"] == "什么是 Redis 持久化"
    assert reviews[0]["kb_name"] == "后端知识库"
    assert reviews[0]["file_name"] == "redis.md"
    assert reviews[0]["locator"] == {
        "db_id": "kb-1",
        "file_id": "file-1",
        "chunk_id": "chunk-1",
        "chunk_index": 4,
        "keyword": "Redis",
        "query_text": "什么是 Redis 持久化",
    }
    assert reviews[0]["score"] is not None
    assert reviews[0]["answer"].startswith("Redis 持久化主要有 RDB 和 AOF")
    assert "Redis" in reviews[0]["matched_keywords"]


def test_normalize_result_payload_keeps_technical_question_reviews():
    conversation = SimpleNamespace(title="后端 · 初试")
    payload = {
        "status": "completed",
        "generated_at": "2026-04-17T12:00:00Z",
        "summary_markdown": "summary",
        "scorecard": {"overall": 82, "dimensions": [{"name": "技术能力", "score": 82}]},
        "technical_question_reviews": [
            {
                "question_index": 1,
                "question": "什么是 Redis 持久化",
                "kb_name": "后端知识库",
                "file_name": "redis.md",
                "score": 78,
                "level": "良好",
                "answer": "回答内容",
                "matched_keywords": ["Redis"],
                "suggested_keywords": ["AOF"],
                "strengths": ["覆盖了关键概念"],
                "gaps": ["还可以补充恢复流程"],
                "locator": {
                    "db_id": "kb-1",
                    "file_id": "file-1",
                    "chunk_id": "chunk-1",
                    "chunk_index": 4,
                    "keyword": "Redis",
                    "query_text": "什么是 Redis 持久化",
                },
            }
        ],
    }

    normalized = service._normalize_result_payload(
        payload,
        conversation=conversation,
        coding_session=None,
    )

    assert normalized is not None
    assert normalized["technical_question_reviews"][0]["question"] == "什么是 Redis 持久化"
    assert normalized["technical_question_reviews"][0]["locator"]["file_id"] == "file-1"


def test_normalize_result_payload_keeps_report_highlights():
    conversation = SimpleNamespace(title="后端 · 初试")
    payload = {
        "status": "completed",
        "generated_at": "2026-04-17T12:00:00Z",
        "summary_markdown": "summary",
        "scorecard": {"overall": 82, "dimensions": [{"name": "技术能力", "score": 82}]},
        "report_highlights": [
            {
                "title": "缓存一致性是当前最大短板",
                "summary": "低分技术题和维度分数都指向这里。",
                "tone": "risk",
                "dimension_key": "technical_competence",
                "priority": 1,
                "evidence_refs": [
                    {"kind": "question_review", "key": "question_review:1", "label": "技术题 1 · 42 分"},
                    {"kind": "dimension", "key": "technical_competence", "label": "技术能力 · 58 分"},
                ],
            }
        ],
    }

    normalized = service._normalize_result_payload(
        payload,
        conversation=conversation,
        coding_session=None,
    )

    assert normalized is not None
    assert normalized["report_highlights"][0]["tone"] == "risk"
    assert normalized["report_highlights"][0]["priority"] == 1
    assert normalized["report_highlights"][0]["evidence_refs"][0]["kind"] == "question_review"


def test_extract_scorecard_accepts_generic_json_code_block_with_interview_scorecard_key():
    content = """
面试总结已经完成。

```json
{
  "interview_scorecard": {
    "基本信息": {
      "目标岗位": "后端工程师",
      "面试轮次": "初试"
    },
    "评估维度": {
      "技术能力": {
        "分数": 8,
        "权重": 0.4,
        "评价": "基础扎实"
      },
      "问题解决": {
        "分数": 7,
        "权重": 0.2,
        "评价": "拆解较完整"
      },
      "沟通表达": {
        "分数": 7,
        "权重": 0.15,
        "评价": "表达清楚"
      },
      "综合素质": {
        "分数": 8,
        "权重": 0.25,
        "评价": "匹配度较好"
      }
    },
    "综合评分": 7.65,
    "主要亮点": ["基础扎实"],
    "主要风险点": ["技术广度待提升"],
    "推荐方向": ["补强系统设计"]
  }
}
```
"""

    scorecard = service._extract_scorecard(content)
    stripped = service._strip_scorecard_block(content)

    assert scorecard is not None
    assert scorecard["role"] == "后端工程师"
    assert scorecard["round"] == "初试"
    assert scorecard["overall"] == 76
    assert "interview_scorecard" not in stripped


def test_build_report_highlights_prioritizes_low_score_question_review():
    scorecard = {
        "overall": 76,
        "role": "后端工程师",
        "dimensions": [
            {"name": "技术能力", "score": 58},
            {"name": "问题解决", "score": 71},
            {"name": "沟通表达", "score": 84},
            {"name": "综合素质", "score": 88},
        ],
        "strengths": ["项目经验表达较完整"],
        "risks": ["缓存一致性解释不清楚"],
        "suggestions": ["优先补强缓存一致性和表达结构"],
    }
    technical_question_reviews = [
        {
            "question_index": 1,
            "question": "什么是缓存一致性",
            "score": 42,
            "level": "待提升",
            "matched_keywords": ["Redis"],
            "suggested_keywords": ["缓存一致性", "延迟双删"],
            "strengths": [],
            "gaps": ["缺少关键机制"],
        },
        {
            "question_index": 2,
            "question": "说一下项目亮点",
            "score": 86,
            "level": "良好",
            "matched_keywords": ["项目"],
            "suggested_keywords": [],
            "strengths": ["表达完整"],
            "gaps": [],
        },
    ]
    plan = {
        "action_plan": {
            "steps": [
                {
                    "step_type": "learn",
                    "title": "先补缓存一致性",
                    "objective": "梳理核心机制",
                    "estimated_minutes": 25,
                    "related_dimension_key": "technical_competence",
                    "resource_refs": ["knowledge-chunk://kb-1/file-1#chunk-1"],
                    "success_signal": "能解释核心机制",
                }
            ]
        }
    }

    highlights = service._build_report_highlights(
        scorecard=scorecard,
        technical_question_reviews=technical_question_reviews,
        expression_analysis=None,
        coding_session=None,
        improvement_plan=plan,
    )

    assert [item["tone"] for item in highlights] == ["risk", "strength", "action"]
    assert highlights[0]["evidence_refs"][0]["kind"] == "question_review"
    assert highlights[0]["title"] == "最低分技术题暴露出关键短板"
    assert "缓存一致性" in highlights[0]["summary"]
    assert highlights[2]["title"] == "先补缓存一致性"


def test_extract_question_keywords_filters_conversational_prefix_and_english_stopwords():
    question = (
        "感谢分享，你的回答很具体。"
        "How can you ensure the scalability of a Node.js application, particularly when dealing with CPU-bound tasks? "
        "Mention specific techniques or modules you would use."
    )

    keywords = service._extract_question_keywords(question)

    assert "感谢分享" not in keywords
    assert "How" not in keywords
    assert "can" not in [item.lower() for item in keywords]
    assert "Node.js" in keywords
    assert "scalability" in keywords


def test_collect_technical_question_reviews_skips_question_interrupted_by_finalize_control():
    tool_call = SimpleNamespace(
        tool_name="pick_random_technical_question",
        status="success",
        tool_output={
            "question": "How can you ensure the scalability of a Node.js application?",
            "kb_name": "Node.js 面试题库",
            "file_name": "nodejs-interview-questions.md",
        },
    )
    messages = [
        SimpleNamespace(
            role="assistant",
            content="",
            tool_calls=[tool_call],
            created_at=None,
            extra_metadata={},
        ),
        SimpleNamespace(
            role="assistant",
            content="感谢分享，你的回答很具体。现在我们来聊一些技术知识方面的问题。作为一个后端工程师，你如何评估Node.js应用的可扩展性？",
            tool_calls=[],
            created_at=None,
            extra_metadata={},
        ),
        SimpleNamespace(
            role="user",
            content="代码考核已经结束，请你现在直接完成第 6、7 阶段。完整结果已生成，可在面试结果页查看。",
            tool_calls=[],
            created_at=None,
            extra_metadata={"hidden_from_history": True, "internal_prompt_type": "interview_finalize_result"},
        ),
    ]

    reviews = service._collect_technical_question_reviews(messages)

    assert reviews == []


def test_build_report_highlights_ignores_missing_dimensions_when_picking_lowest():
    scorecard = {
        "overall": 76,
        "role": "后端工程师",
        "dimensions": [
            {"name": "技术能力", "score": 80},
            {"name": "架构设计", "score": 70},
            {"name": "问题解决", "score": 80},
            {"name": "沟通表达", "score": 70},
        ],
        "strengths": ["Redis 缓存机制理解深入"],
    }

    highlights = service._build_report_highlights(
        scorecard=scorecard,
        technical_question_reviews=[],
        expression_analysis=None,
        coding_session=None,
        improvement_plan=None,
    )

    assert highlights[0]["dimension_key"] == "communication"
    assert "综合素质" not in highlights[0]["title"]


def test_generate_improvement_plan_ignores_missing_dimensions_when_selecting_weaknesses(monkeypatch):
    async def fake_get_databases_by_raw_id(_user_id: int):
        return {"databases": []}

    async def fake_get_databases_by_user_id(_user_id: str):
        return {"databases": []}

    monkeypatch.setattr(service.knowledge_base, "get_databases_by_raw_id", fake_get_databases_by_raw_id)
    monkeypatch.setattr(service.knowledge_base, "get_databases_by_user_id", fake_get_databases_by_user_id)
    monkeypatch.setattr(service, "list_imported_problem_packages", lambda: {"problems": []})
    monkeypatch.setattr(service, "_create_web_searcher", lambda: None)

    conversation = SimpleNamespace(user_id="user-1", extra_metadata={"target_position": "后端工程师"})
    scorecard = {
        "role": "后端工程师",
        "round": "初试",
        "dimensions": [
            {"name": "技术能力", "score": 80},
            {"name": "架构设计", "score": 70},
            {"name": "问题解决", "score": 80},
            {"name": "沟通表达", "score": 70},
        ],
        "strengths": ["Redis 缓存机制理解深入"],
    }

    plan = asyncio.run(
        service._generate_improvement_plan(
            conversation=conversation,
            scorecard=scorecard,
            expression_analysis=None,
            coding_session=None,
            technical_question_reviews=[],
        )
    )

    assert plan is not None
    assert all(item["dimension_key"] != "soft_skills" for item in plan["weaknesses"])


def test_improvement_plan_needs_refresh_when_referring_missing_dimension():
    scorecard = {
        "dimensions": [
            {"name": "技术能力", "score": 80},
            {"name": "问题解决", "score": 75},
            {"name": "沟通表达", "score": 70},
        ]
    }
    plan = {
        "weaknesses": [
            {
                "dimension_key": "soft_skills",
                "title": "岗位匹配表达不够充分",
                "reason": "旧计划错误引用了缺失维度。",
            }
        ],
        "recommended_resources": [],
        "practice_tasks": [],
        "next_assessment_focus": [],
        "action_plan": {
            "title": "7 天提升路径",
            "summary": "先补知识，再做练习。",
            "steps": [
                {
                    "step_type": "learn",
                    "title": "先补岗位匹配表达",
                    "objective": "补表达",
                    "estimated_minutes": 20,
                    "related_dimension_key": "soft_skills",
                    "resource_refs": [],
                    "success_signal": "能说明岗位匹配。",
                }
            ],
        },
    }

    assert service._improvement_plan_needs_refresh(plan, scorecard) is True


def test_parse_thread_context_supports_legacy_separator():
    assert service._parse_thread_context("backend engineer ? first round") == (
        "backend engineer",
        "first round",
    )


def test_normalize_result_payload_fills_role_round_from_legacy_title_separator():
    conversation = SimpleNamespace(title="backend engineer ? first round")

    payload = service._normalize_result_payload(
        {
            "status": "completed",
            "scorecard": {
                "summary": "候选人基础较扎实，但仍有提升空间。",
            },
        },
        conversation=conversation,
        coding_session=None,
    )

    assert payload is not None
    assert payload["scorecard"]["role"] == "backend engineer"
    assert payload["scorecard"]["round"] == "first round"


def test_normalize_result_payload_splits_legacy_title_when_role_contains_full_title():
    conversation = SimpleNamespace(title="backend engineer ? first round")

    payload = service._normalize_result_payload(
        {
            "status": "completed",
            "scorecard": {
                "role": "backend engineer ? first round",
                "summary": "候选人基础较扎实，但仍有提升空间。",
            },
        },
        conversation=conversation,
        coding_session=None,
    )

    assert payload is not None
    assert payload["scorecard"]["role"] == "backend engineer"
    assert payload["scorecard"]["round"] == "first round"


def test_normalize_result_payload_recovers_overall_from_dimensions():
    """V3-001 fix: when LLM forgets `overall` but emits dimension scores,
    we average them instead of letting the UI render '—'."""
    conversation = SimpleNamespace(title="后端工程师 · 初试")

    payload = service._normalize_result_payload(
        {
            "status": "completed",
            "scorecard": {
                "dimensions": [
                    {"name": "技术能力", "score": 60},
                    {"name": "沟通表达", "score": 78},
                    {"name": "综合素质", "score": 72},
                ],
            },
        },
        conversation=conversation,
        coding_session=None,
    )

    assert payload is not None
    assert payload["scorecard"]["overall"] == 70  # round((60+78+72)/3)


def test_normalize_result_payload_preserves_null_overall_when_no_dimensions():
    """V3-001 fix corollary: if we have no dimensions either, leave overall
    as None so the UI can show the 'incomplete scorecard' banner."""
    conversation = SimpleNamespace(title="后端工程师 · 初试")

    payload = service._normalize_result_payload(
        {
            "status": "completed",
            "scorecard": {
                "strengths": ["候选人表达清晰"],
            },
        },
        conversation=conversation,
        coding_session=None,
    )

    assert payload is not None
    assert payload["scorecard"].get("overall") is None
