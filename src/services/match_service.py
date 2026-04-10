"""简历-JD智能匹配服务"""

import re
from datetime import datetime
from typing import Any

from src.utils import logger

DEFAULT_WEIGHTS = {
    "skills": 0.45,
    "experience": 0.35,
    "education": 0.20,
}

EDUCATION_LEVELS = {
    "高中": 1,
    "中专": 2,
    "大专": 3,
    "本科": 4,
    "硕士": 5,
    "博士": 6,
}


class SkillMatchResult:
    """技能匹配结果"""

    def __init__(
        self,
        score: float,
        matched: list[str],
        missing: list[str],
        matched_count: int,
        total_count: int,
    ):
        self.score = score
        self.matched = matched
        self.missing = missing
        self.matched_count = matched_count
        self.total_count = total_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "matched": self.matched,
            "missing": self.missing,
            "matched_count": self.matched_count,
            "total_count": self.total_count,
        }

class ExperienceMatchResult:
    """经验匹配结果"""

    def __init__(
        self,
        score: float,
        years_match: bool | None,
        project_relevance: float,
        details: list[str],
    ):
        self.score = score
        self.years_match = years_match
        self.project_relevance = project_relevance
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "years_match": self.years_match,
            "project_relevance": self.project_relevance,
            "details": self.details,
        }


class MatchResult:
    """完整匹配结果"""

    def __init__(
        self,
        overall_score: float,
        skill_match: SkillMatchResult,
        experience_match: ExperienceMatchResult,
        risk_points: list[str],
        summary: str,
    ):
        self.overall_score = overall_score
        self.skill_match = skill_match
        self.experience_match = experience_match
        self.risk_points = risk_points
        self.summary = summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "skill_match": self.skill_match.to_dict(),
            "experience_match": self.experience_match.to_dict(),
            "risk_points": self.risk_points,
            "summary": self.summary,
        }

class MatchService:
    """匹配服务"""

    # 常见技能别名映射
    SKILL_ALIASES = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "k8s": "kubernetes",
        # 保留 db 作为一个通用类别，但具体数据库技能不映射到它（避免误匹配）
        "db": "database",
        # 具体数据库技能保持独立，不应映射为通用的 "database"
        # "mysql": "database",  # 删除 - MySQL是独立技能
        # "postgresql": "database",  # 删除 - PostgreSQL是独立技能
        # "sql": "database",  # 删除 - SQL是查询语言，不等于database
        # "nosql": "database",  # 删除 - NoSQL是独立概念
        "mongo": "mongodb",
        "psql": "postgresql",
        "reactjs": "react",
        "react.js": "react",
        "vuejs": "vue",
        "vue.js": "vue",
        "angularjs": "angular",
        "angular.js": "angular",
        "node": "nodejs",
        "node.js": "nodejs",
        "go": "golang",
        "cs": "csharp",
        "c#": "csharp",
        "jquery": "javascript",
        "boot": "bootstrap",
        # 中文技能同义词映射（中文 -> 标准英文名）
        "深度学习": "deep learning",
        "机器学习": "machine learning",
        "神经网络": "neural network",
        "人工智能": "artificial intelligence",
        "前端开发": "frontend",
        "后端开发": "backend",
        "数据分析": "data analysis",
        "自然语言处理": "nlp",
        "计算机视觉": "computer vision",
        "推荐系统": "recommendation system",
        "大模型": "large language model",
        "大语言模型": "large language model",
    }

    # 需要特殊处理的短技能词（避免模糊匹配误匹配）
    # 短技能词需要满足最小长度要求，避免匹配到不相关的词
    SHORT_SKILL_MIN_LENGTHS = {
        "go": 4,  # "go" 只能匹配长度>=4的词（避免匹配 "ago", "good"等）
        "js": 3,  # "js" 需要匹配 "javascript" 等
        "ts": 3,
        "py": 3,
        "db": 3,
    }

    def __init__(self):
        self.weights = DEFAULT_WEIGHTS
        assert abs(sum(self.weights.values()) - 1.0) < 1e-6, f"权重总和必须为 1.0，当前为 {sum(self.weights.values())}"

    def _extract_skill_names(self, skills_data: list[str] | dict | None) -> list[str]:
        """
        从技能数据中提取技能名称

        支持从长描述文本中提取关键技能名，例如：
        - "产品设计：熟练掌握用户调研、需求分析..." -> ["产品设计"]
        - "熟练掌握java" -> ["java"]
        - "Python, Django, Flask" -> ["python", "django", "flask"]
        """
        if not skills_data:
            return []

        # 如果是字典，合并所有技能列表
        if isinstance(skills_data, dict):
            all_skills = []
            for key in ["technical", "tools", "languages", "soft_skills"]:
                skills = skills_data.get(key, [])
                if isinstance(skills, list):
                    all_skills.extend(skills)
            skills_data = all_skills

        if not isinstance(skills_data, list):
            return []

        skill_names = []
        for skill_text in skills_data:
            if not skill_text or not isinstance(skill_text, str):
                continue

            # 按冒号分割，取第一部分作为技能名
            if "：" in skill_text:
                # 中文冒号
                main_part = skill_text.split("：")[0].strip()
            elif ":" in skill_text:
                # 英文冒号
                main_part = skill_text.split(":")[0].strip()
            else:
                main_part = skill_text.strip()

            # 清理和提取关键词
            # 移除常见的前缀词
            prefixes_to_remove = ["熟练掌握", "熟悉", "掌握", "了解", "精通", "使用", "运用", "具有"]
            for prefix in prefixes_to_remove:
                if main_part.startswith(prefix):
                    main_part = main_part[len(prefix):].strip()
                    break

            # 如果太长（超过10个字符），尝试提取前几个关键词
            if len(main_part) > 10:
                # 按常见分隔符分割
                parts = re.split(r'[,，、和与及\s]+', main_part)
                if len(parts) > 1:
                    # 取第一个关键词
                    main_part = parts[0].strip()
                else:
                    # 取前几个字符作为技能名
                    main_part = main_part[:6].strip()

            # 只有非空且长度合理的才添加
            if main_part and len(main_part) >= 2:
                skill_names.append(main_part)

        return skill_names

    def _is_fuzzy_match_valid(self, jd_skill: str, resume_skill: str) -> bool:
        """
        改进的模糊匹配逻辑，避免误匹配
        
        规则：
        1. 精确匹配总是有效
        2. 短技能词（如 "go"）需要满足最小长度要求
        3. 避免部分匹配导致的误匹配（如 "go" 不应匹配 "good"）
        
        Examples:
            _is_fuzzy_match_valid("go", "golang") -> True  ✓
            _is_fuzzy_match_valid("go", "good") -> False   ✗
            _is_fuzzy_match_valid("java", "javascript") -> True  ✓
            _is_fuzzy_match_valid("react", "reactjs") -> True  ✓
        """
        jd_lower = jd_skill.lower()
        resume_lower = resume_skill.lower()
        
        # 精确匹配
        if jd_lower == resume_lower:
            return True
        
        # 检查 jd_skill 是否是 resume_skill 的子串
        if jd_lower in resume_lower:
            # 短技能词需要满足最小长度要求
            min_len = self.SHORT_SKILL_MIN_LENGTHS.get(jd_lower, 3)
            if len(jd_lower) < min_len:
                # 对于短技能，检查是否是合理的匹配模式
                # 例如：go -> golang ✓，但 go -> good ✗
                # 合理的模式：前缀+lang, 后缀+.js, 完整词边界
                valid_patterns = [
                    jd_lower + "lang",  # go -> golang
                    jd_lower + ".js",   # vue -> vue.js
                    jd_lower + "js",    # react -> reactjs
                ]
                
                # 检查是否匹配任何有效模式
                if resume_lower in valid_patterns:
                    return True
                
                # 如果是前缀匹配，需要检查上下文
                # go 匹配 golang（前缀+lang）
                if resume_lower.startswith(jd_lower) and len(resume_lower) >= min_len:
                    # 额外检查：确保不是随意匹配
                    # go -> golang ✓, go -> good ✗
                    return resume_lower.endswith('lang') or resume_lower.endswith('.js') or resume_lower.endswith('js')
                
                # 不满足条件，拒绝匹配
                return False
            
            return True
        
        # 检查 resume_skill 是否是 jd_skill 的子串
        if resume_lower in jd_lower:
            return True
        
        return False

    def _normalize_skills(self, skills: list[str] | None) -> set[str]:
        """标准化技能列表为小写集合"""
        if not skills:
            return set()
        return {s.lower().strip() for s in skills if s}

    def _extract_and_normalize_skills(self, skills: list[str] | dict | None) -> set[str]:
        """
        提取并标准化技能，包含别名映射
        """
        # 先提取技能名
        skill_names = self._extract_skill_names(skills)

        # 标准化为小写
        normalized_skills = set()
        for skill in skill_names:
            skill_lower = skill.lower().strip()
            if skill_lower in self.SKILL_ALIASES:
                normalized_skills.add(self.SKILL_ALIASES[skill_lower])
            else:
                normalized_skills.add(skill_lower)

        return normalized_skills

    def _validate_resume_summary(self, resume_summary: dict[str, Any]) -> dict[str, Any]:
        """
        验证并规范化 resume_summary

        为缺失字段提供合理默认值
        """
        if not isinstance(resume_summary, dict):
            logger.warning("resume_summary 不是字典类型，使用空字典")
            return {}

        validated = resume_summary.copy()

        # 确保 skills 字段存在
        if "skills" not in validated or not validated["skills"]:
            validated["skills"] = {}
            logger.warning("resume_summary 缺少 skills 字段，使用空字典")

        # 确保 work_experience 字段存在
        if "work_experience" not in validated:
            validated["work_experience"] = validated.get("work", [])
            if "work" in validated:
                logger.warning("resume_summary 使用 work 字段作为 work_experience")

        # 确保 project_experience 字段存在
        if "project_experience" not in validated:
            validated["project_experience"] = validated.get("projects", [])
            if "projects" in validated:
                logger.warning("resume_summary 使用 projects 字段作为 project_experience")

        # 确保 education 字段存在
        if "education" not in validated or not validated["education"]:
            validated["education"] = []
            logger.warning("resume_summary 缺少 education 字段，使用空列表")

        return validated

    def _calculate_skill_match(
        self,
        jd_skills: list[str],
        resume_skills: list[str],
    ) -> SkillMatchResult:
        """
        计算技能匹配度（使用模糊匹配）

        支持从长描述文本中提取技能名并进行模糊匹配
        """
        if not jd_skills:
            # JD没有要求技能时，返回中性分数而非0分（没有要求不应惩罚）
            return SkillMatchResult(
                score=50.0,
                matched=[],
                missing=[],
                matched_count=0,
                total_count=0,
            )

        # 提取并标准化技能
        jd_skills_set = self._extract_and_normalize_skills(jd_skills)
        resume_skills_set = self._extract_and_normalize_skills(resume_skills)

        # 模糊匹配：检查JD技能是否在简历技能中（作为子串）
        matched = set()
        missing = set()

        for jd_skill in jd_skills_set:
            # 精确匹配
            if jd_skill in resume_skills_set:
                matched.add(jd_skill)
                continue

            # 改进的模糊匹配：避免误匹配
            found = False
            for resume_skill in resume_skills_set:
                if self._is_fuzzy_match_valid(jd_skill, resume_skill):
                    matched.add(jd_skill)
                    found = True
                    break

            if not found:
                missing.add(jd_skill)

        matched_count = len(matched)
        total_count = len(jd_skills_set)

        # 计算分数：匹配的技能占总技能的百分比
        score = (matched_count / total_count * 100) if total_count > 0 else 0

        return SkillMatchResult(
            score=round(score, 1),
            matched=list(matched),
            missing=list(missing),
            matched_count=matched_count,
            total_count=total_count,
        )

    def _calculate_experience_match(
        self,
        min_years: int | None,
        work_experience: list[dict[str, Any]] | None,
        project_experience: list[dict[str, Any]] | None,
    ) -> ExperienceMatchResult:
        """计算经验匹配度"""
        details = []
        score = 50.0
        years_match = True
        project_relevance = 0.0

        total_years = 0
        has_current_job = False
        if work_experience and min_years:
            for exp in work_experience:
                if not isinstance(exp, dict):
                    continue
                duration = exp.get("duration") or ""
                if not isinstance(duration, str):
                    duration = str(duration)
                if "至今" in duration or "Present" in duration or "present" in duration:
                    has_current_job = True
                    year_match = re.search(r"20\d{2}", duration)
                    if year_match:
                        start_year = int(year_match.group())
                        current_year = datetime.now().year
                        total_years = current_year - start_year
                        break

            if has_current_job:
                if total_years >= min_years:
                    score += 25
                    details.append(f"工作年限满足要求（{total_years}年 >= {min_years}年）")
                else:
                    score -= 10
                    years_match = False
                    details.append(f"工作年限不足（{total_years}年 < {min_years}年）")
            else:
                years_match = None
                details.append("工作经历中未找到在岗信息，年限无法确定")
                score += 10
        elif min_years:
            years_match = False
            details.append(f"缺少工作经历，无法评估年限要求（需要{min_years}年）")

        if project_experience:
            project_count = len(project_experience)
            project_relevance = min(project_count * 10, 50)
            score += project_relevance
            details.append(f"有{project_count}个项目经验")

        score = min(max(score, 0), 100)

        return ExperienceMatchResult(
            score=round(score, 1),
            years_match=years_match,
            project_relevance=round(project_relevance, 1),
            details=details,
        )

    def _extract_education_level(self, degree_str: str | None) -> int:
        """从学位字符串提取学历等级"""
        if not degree_str or not isinstance(degree_str, str):
            return 0
        for level_name, level_value in EDUCATION_LEVELS.items():
            if level_name in degree_str:
                return level_value
        return 0

    def _calculate_education_match(
        self,
        required_level: str | None,
        resume_education: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """计算教育匹配度"""
        # 无学历要求时返回中性分
        if not required_level:
            return {"score": 50.0, "meets_requirement": True}

        req_level = self._extract_education_level(required_level)
        if req_level == 0:
            return {"score": 50.0, "meets_requirement": True}

        # 从简历中取最高学历
        if not resume_education:
            return {"score": 20.0, "meets_requirement": False}

        max_level = 0
        for edu in resume_education:
            if not isinstance(edu, dict):
                continue
            degree = edu.get("degree") or ""
            level = self._extract_education_level(degree)
            if level > max_level:
                max_level = level

        if max_level >= req_level:
            # 满足要求: 50-100 分，基础分 50，每高一级 +10
            score = min(100.0, 50.0 + (max_level - req_level) * 10.0)
            return {"score": score, "meets_requirement": True}
        else:
            # 不满足要求: 0-50 分，基础分 50，每低一级 -15
            score = max(0.0, 50.0 - (req_level - max_level) * 15.0)
            return {"score": score, "meets_requirement": False}

    def _identify_risk_points(
        self,
        skill_match: SkillMatchResult,
        experience_match: ExperienceMatchResult,
        education_level: str | None,
        resume_education: list[dict[str, Any]] | None,
    ) -> list[str]:
        """识别风险点"""
        risk_points = []

        if skill_match.missing:
            missing_skills = skill_match.missing[:3]
            risk_points.append("技能缺失：" + ", ".join(missing_skills))

        if not experience_match.years_match:
            risk_points.append("工作经验年限不满足要求")

        if education_level and resume_education:
            required_level = self._extract_education_level(education_level)
            if required_level > 0:
                # 取最高学历
                max_actual_level = 0
                max_degree = ""
                for edu in resume_education:
                    if not isinstance(edu, dict):
                        continue
                    degree = edu.get("degree") or ""
                    level = self._extract_education_level(degree)
                    if level > max_actual_level:
                        max_actual_level = level
                        max_degree = degree
                if max_actual_level < required_level:
                    risk_points.append(f"学历低于岗位要求（需要{education_level}，候选人为{max_degree}）")

        return risk_points

    def _generate_summary(
        self,
        overall_score: float,
        skill_match: SkillMatchResult,
        experience_match: ExperienceMatchResult,
    ) -> str:
        """生成匹配摘要"""
        if overall_score >= 80:
            level = "优秀"
        elif overall_score >= 60:
            level = "良好"
        elif overall_score >= 40:
            level = "一般"
        else:
            level = "较差"

        skill_info = "技能匹配" + str(skill_match.matched_count) + "/" + str(skill_match.total_count)
        exp_info = "经验评分" + str(experience_match.score)

        return "综合匹配" + level + "，" + skill_info + "，" + exp_info

    def calculate_match(
        self,
        job_dict: dict[str, Any],
        resume_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        计算简历与JD的匹配度

        Args:
            job_dict: JD数据字典
            resume_summary: 简历结构化摘要

        Returns:
            匹配结果字典，失败时包含 _error 标记
        """
        try:
            # 验证并规范化输入
            validated_summary = self._validate_resume_summary(resume_summary)

            jd_skills = job_dict.get("required_skills") or []
            jd_preferred_skills = job_dict.get("preferred_skills") or []
            min_experience = job_dict.get("min_experience_years")
            education_level = job_dict.get("education_level")

            if not isinstance(jd_skills, list):
                jd_skills = []
            if not isinstance(jd_preferred_skills, list):
                jd_preferred_skills = []

            # 从 skills 对象中提取所有技能列表
            skills_data = validated_summary.get("skills", {})
            if isinstance(skills_data, dict):
                # 合并所有技能类型的列表
                resume_skills = []
                for key in ["technical", "tools", "languages", "soft_skills"]:
                    skills = skills_data.get(key, [])
                    if isinstance(skills, list):
                        resume_skills.extend(skills)
            else:
                resume_skills = skills_data if isinstance(skills_data, list) else []

            work_experience = validated_summary.get("work_experience") or []
            project_experience = validated_summary.get("project_experience") or []
            education = validated_summary.get("education") or []

            if not isinstance(work_experience, list):
                work_experience = []
            if not isinstance(project_experience, list):
                project_experience = []
            if not isinstance(education, list):
                education = []

            # 从 project_experience 的 tech_stack 中提取技能补充到技能池
            if isinstance(project_experience, list):
                for proj in project_experience:
                    if not isinstance(proj, dict):
                        continue
                    tech_stack = proj.get("tech_stack") or []
                    if isinstance(tech_stack, list):
                        resume_skills.extend(tech_stack)

            all_jd_skills = jd_skills + jd_preferred_skills
            skill_match = self._calculate_skill_match(all_jd_skills, resume_skills)

            experience_match = self._calculate_experience_match(
                min_experience, work_experience, project_experience
            )

            education_match = self._calculate_education_match(
                education_level, education
            )

            # 三维度加权：技能、经验、教育
            skill_weight = self.weights["skills"]
            exp_weight = self.weights["experience"]
            edu_weight = self.weights["education"]

            overall_score = (
                skill_match.score * skill_weight
                + experience_match.score * exp_weight
                + education_match["score"] * edu_weight
            )

            risk_points = self._identify_risk_points(
                skill_match, experience_match, education_level, education
            )

            summary = self._generate_summary(overall_score, skill_match, experience_match)

            match_result = MatchResult(
                overall_score=round(overall_score, 1),
                skill_match=skill_match,
                experience_match=experience_match,
                risk_points=risk_points,
                summary=summary,
            )

            result = match_result.to_dict()
            result["education_match"] = education_match
            return result

        except Exception as e:
            logger.error("匹配计算失败: " + str(e))
            return {
                "_error": True,
                "_error_detail": str(e),
                "overall_score": 0,
                "skill_match": {
                    "score": 0,
                    "matched": [],
                    "missing": [],
                    "matched_count": 0,
                    "total_count": 0,
                },
                "experience_match": {
                    "score": 0,
                    "years_match": False,
                    "project_relevance": 0,
                    "details": ["匹配计算失败: " + str(e)],
                },
                "education_match": {
                    "score": 0,
                    "meets_requirement": False,
                },
                "risk_points": ["匹配计算过程出错"],
                "summary": "匹配失败",
            }


match_service = MatchService()
