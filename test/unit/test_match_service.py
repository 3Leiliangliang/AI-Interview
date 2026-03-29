"""
Unit tests for MatchService - skill matching improvements
Tests for:
- Project experience tech_stack aggregation into skill pool
- Chinese skill alias mapping
- Education match dimension
- Weight normalization and score bounds
"""

from __future__ import annotations

import pytest

from src.services.match_service import MatchService


@pytest.fixture
def svc() -> MatchService:
    return MatchService()


# ============================================================
# Task 1: 项目经验 tech_stack 聚合到技能池
# ============================================================


class TestProjectExperienceSkillAggregation:
    """测试从 project_experience 的 tech_stack 中提取技能补充到技能池"""

    def test_project_tech_stack_added_to_skills(
        self, svc: MatchService
    ):
        """项目经验中的 tech_stack 应被聚合到技能池中参与匹配"""
        job_dict = {
            "required_skills": ["Python", "PyTorch", "深度学习"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": None,
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [
                {
                    "name": "图像分类系统",
                    "tech_stack": ["PyTorch", "深度学习"],
                }
            ],
            "education": [],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["skill_match"]["matched_count"] >= 2
        assert result["overall_score"] > 50

    def test_project_tech_stack_dedup_with_skills(
        self, svc: MatchService
    ):
        """项目经验中与 skills 重复的技能不应导致重复计数"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": None,
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [
                {
                    "name": "项目A",
                    "tech_stack": ["Python"],
                }
            ],
            "education": [],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["skill_match"]["matched_count"] == 1

    def test_empty_project_experience_no_crash(
        self, svc: MatchService
    ):
        """project_experience 为空列表时不应报错"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["skill_match"]["matched_count"] == 1

    def test_project_experience_missing_tech_stack(
        self, svc: MatchService
    ):
        """project_experience 中没有 tech_stack 字段时不应报错"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [{"name": "项目A"}],
            "education": [],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["skill_match"]["matched_count"] == 1

    def test_deep_learning_project_identified(
        self, svc: MatchService
    ):
        """深度学习项目经验应被正确识别"""
        job_dict = {
            "required_skills": ["深度学习", "PyTorch", "计算机视觉"],
            "preferred_skills": ["TensorFlow"],
            "min_experience_years": None,
            "education_level": None,
        }
        resume_summary = {
            "skills": {"technical": ["Python", "C++"]},
            "work_experience": [],
            "project_experience": [
                {
                    "name": "目标检测系统",
                    "tech_stack": ["深度学习", "PyTorch", "计算机视觉"],
                },
                {
                    "name": "推荐系统",
                    "tech_stack": ["TensorFlow"],
                },
            ],
            "education": [],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["skill_match"]["matched_count"] >= 3
        assert result["overall_score"] >= 60


# ============================================================
# Task 2: 中文技能别名映射
# ============================================================


class TestChineseSkillAliases:
    """测试中文技能别名映射"""

    def test_deep_learning_alias(self, svc: MatchService):
        """'深度学习' 应匹配 'deep learning'"""
        result = svc._calculate_skill_match(
            ["deep learning"],
            ["深度学习"],
        )
        assert result.matched_count == 1

    def test_machine_learning_alias(self, svc: MatchService):
        """'机器学习' 应匹配 'machine learning'"""
        result = svc._calculate_skill_match(
            ["machine learning"],
            ["机器学习"],
        )
        assert result.matched_count == 1

    def test_nlp_alias(self, svc: MatchService):
        """'自然语言处理' 应匹配 'nlp'"""
        result = svc._calculate_skill_match(
            ["nlp"],
            ["自然语言处理"],
        )
        assert result.matched_count == 1

    def test_computer_vision_alias(self, svc: MatchService):
        """'计算机视觉' 应匹配 'computer vision'"""
        result = svc._calculate_skill_match(
            ["computer vision"],
            ["计算机视觉"],
        )
        assert result.matched_count == 1

    def test_llm_alias(self, svc: MatchService):
        """'大模型' 和 '大语言模型' 都应匹配 'large language model'"""
        result1 = svc._calculate_skill_match(
            ["large language model"],
            ["大模型"],
        )
        assert result1.matched_count == 1

        result2 = svc._calculate_skill_match(
            ["large language model"],
            ["大语言模型"],
        )
        assert result2.matched_count == 1

    def test_chinese_alias_bidirectional(self, svc: MatchService):
        """中文别名应双向匹配（JD用中文，简历用英文）"""
        result = svc._calculate_skill_match(
            ["深度学习"],
            ["deep learning"],
        )
        assert result.matched_count == 1

    def test_existing_aliases_not_broken(self, svc: MatchService):
        """现有英文别名映射不应被破坏"""
        result = svc._calculate_skill_match(
            ["javascript", "typescript", "vue"],
            ["js", "ts", "vuejs"],
        )
        assert result.matched_count == 3


# ============================================================
# Task 3: 教育匹配维度
# ============================================================


class TestEducationMatch:
    """测试教育匹配维度"""

    def test_education_meets_requirement(self, svc: MatchService):
        """学历满足要求时，应有加分"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "本科",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "硕士"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert "education_match" in result
        assert result["education_match"]["score"] >= 50

    def test_education_below_requirement(self, svc: MatchService):
        """学历低于要求时，应为低分"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "硕士",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "大专"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["education_match"]["score"] < 50

    def test_education_exact_match(self, svc: MatchService):
        """学历恰好满足时，应得基础分"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "本科",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "本科"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["education_match"]["score"] == 50.0

    def test_education_no_requirement(self, svc: MatchService):
        """岗位无学历要求时，教育匹配应给中性分"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": None,
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "本科"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["education_match"]["score"] == 50.0

    def test_education_overall_score_includes_education(
        self, svc: MatchService
    ):
        """overall_score 应包含教育匹配权重"""
        job_high_edu = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "博士",
        }
        job_no_edu = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": None,
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "博士"}],
        }

        result_high = svc.calculate_match(job_high_edu, resume_summary)
        result_no = svc.calculate_match(job_no_edu, resume_summary)
        assert result_high["overall_score"] >= result_no["overall_score"]

    def test_education_result_has_required_fields(self, svc: MatchService):
        """education_match 结果应包含 score 和 meets_requirement"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "本科",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "本科"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        edu = result["education_match"]
        assert "score" in edu
        assert "meets_requirement" in edu


# ============================================================
# 权重归一化与分数边界
# ============================================================


class TestScoreBounds:
    """测试权重归一化后总分不超 100"""

    def test_overall_score_never_exceeds_100(self, svc: MatchService):
        """所有维度满分时总分不应超过 100"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": 1,
            "education_level": "本科",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [{"duration": "2020年 - 至今"}],
            "project_experience": [{"name": "p1"}, {"name": "p2"}, {"name": "p3"}],
            "education": [{"degree": "博士"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert 0 <= result["overall_score"] <= 100

    def test_overall_score_never_below_0(self, svc: MatchService):
        """最差情况下总分不应低于 0"""
        job_dict = {
            "required_skills": ["Rust", "Haskell", "Erlang"],
            "preferred_skills": ["OCaml"],
            "min_experience_years": 10,
            "education_level": "博士",
        }
        resume_summary = {
            "skills": {},
            "work_experience": [],
            "project_experience": [],
            "education": [{"degree": "高中"}],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["overall_score"] >= 0

    def test_weights_sum_to_one(self):
        """权重总和应为 1.0"""
        total = sum(MatchService().weights.values())
        assert abs(total - 1.0) < 1e-9


# ============================================================
# 教育边界测试
# ============================================================


class TestEducationEdgeCases:
    """测试教育匹配的边界情况"""

    def test_multiple_education_takes_highest(self, svc: MatchService):
        """多条学历记录时应取最高学历"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "硕士",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [
                {"degree": "大专"},
                {"degree": "博士"},
                {"degree": "本科"},
            ],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["education_match"]["meets_requirement"] is True
        assert result["education_match"]["score"] >= 50

    def test_education_no_resume_education(self, svc: MatchService):
        """简历无学历记录但有学历要求时，应为低分"""
        job_dict = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "min_experience_years": None,
            "education_level": "本科",
        }
        resume_summary = {
            "skills": {"technical": ["Python"]},
            "work_experience": [],
            "project_experience": [],
            "education": [],
        }

        result = svc.calculate_match(job_dict, resume_summary)
        assert result["education_match"]["score"] < 50
        assert result["education_match"]["meets_requirement"] is False
