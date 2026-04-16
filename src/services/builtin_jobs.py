"""内置岗位数据与统一岗位类型配置。"""

from __future__ import annotations

import copy

from src.services.position_types import (
    DEFAULT_POSITION_KEY,
    get_all_position_types,
    get_default_position_label,
    get_default_position_type,
    get_position_type,
    normalize_position_key,
)

BUILTIN_JOBS = [
    {
        "id": 1,
        "position_key": "frontend",
        "title": "前端开发工程师",
        "department": "技术部",
        "description": "负责 Web 前端开发与维护，参与前端架构设计与性能优化。",
        "requirements": (
            "1. 熟练掌握 HTML/CSS/JavaScript；\n"
            "2. 熟悉 Vue.js 或 React 等主流前端框架；\n"
            "3. 了解前端工程化、性能优化和组件化开发；\n"
            "4. 具备良好的编码习惯和协作意识。"
        ),
        "required_skills": ["HTML5", "CSS3", "JavaScript", "Vue.js", "React", "TypeScript", "Vite"],
        "preferred_skills": ["Node.js", "Jest", "Cypress", "Ant Design Vue", "性能优化"],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "15K-30K",
        "status": "active",
    },
    {
        "id": 2,
        "position_key": "backend",
        "title": "后端开发工程师",
        "department": "技术部",
        "description": "负责后端服务开发与维护，参与系统架构设计与数据库设计。",
        "requirements": (
            "1. 熟练掌握 Java / Python / Go 中至少一种语言及其常用框架；\n"
            "2. 熟悉关系型数据库设计、SQL 优化与缓存技术；\n"
            "3. 扎实掌握操作系统、网络、数据结构等计算机基础；\n"
            "4. 具备服务治理与线上问题排查能力。"
        ),
        "required_skills": ["Java", "Python", "Go", "MySQL", "PostgreSQL", "Redis", "FastAPI", "Spring Boot"],
        "preferred_skills": ["Kafka", "Docker", "分布式系统", "CI/CD", "Linux"],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "18K-35K",
        "status": "active",
    },
    {
        "id": 3,
        "position_key": "backend",
        "title": "数据库工程师",
        "department": "基础架构部",
        "description": "负责数据库设计、SQL 优化、索引治理与高可用架构落地。",
        "requirements": (
            "1. 熟悉 MySQL / PostgreSQL 等数据库原理；\n"
            "2. 理解事务、索引、锁、日志和主从复制；\n"
            "3. 能定位慢查询并完成数据库性能优化；\n"
            "4. 具备数据库容量规划和稳定性治理经验。"
        ),
        "required_skills": ["SQL", "MySQL", "PostgreSQL", "索引", "事务", "锁机制", "慢查询优化"],
        "preferred_skills": ["主从复制", "高可用", "备份恢复", "监控告警"],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "18K-32K",
        "status": "active",
    },
    {
        "id": 4,
        "position_key": "algorithm",
        "title": "算法工程师",
        "department": "技术部",
        "description": "负责算法题设计、数据结构分析与复杂度优化相关能力建设。",
        "requirements": (
            "1. 熟练掌握常见数据结构与基础算法；\n"
            "2. 能独立完成复杂度分析和边界条件设计；\n"
            "3. 熟悉树、图、动态规划、搜索等常见题型；\n"
            "4. 具备良好的代码实现与调试能力。"
        ),
        "required_skills": ["数组", "链表", "树", "图", "动态规划", "贪心", "搜索", "复杂度分析"],
        "preferred_skills": ["LeetCode", "竞赛经验", "数学建模"],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "18K-35K",
        "status": "active",
    },
    {
        "id": 5,
        "position_key": "system_design",
        "title": "系统架构师",
        "department": "架构部",
        "description": "负责高并发系统方案设计、容量评估与关键模块架构拆解。",
        "requirements": (
            "1. 熟悉缓存、消息队列、数据库分库分表等常见架构组件；\n"
            "2. 能完成系统建模、流量估算与瓶颈分析；\n"
            "3. 理解一致性、可用性与扩展性之间的权衡；\n"
            "4. 具备服务容灾与监控治理意识。"
        ),
        "required_skills": ["系统设计", "高并发", "缓存", "消息队列", "分布式系统", "一致性"],
        "preferred_skills": ["限流熔断", "可观测性", "容灾演练"],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "22K-40K",
        "status": "active",
    },
    {
        "id": 6,
        "position_key": "ai_app",
        "title": "AI 应用开发工程师",
        "department": "AI 平台部",
        "description": "负责 LLM、RAG、Agent 等 AI 应用能力的产品化与工程落地。",
        "requirements": (
            "1. 熟悉 LLM 应用开发、Prompt 设计与工具调用链路；\n"
            "2. 理解 RAG、Embedding、向量检索与知识库构建流程；\n"
            "3. 能基于 LangChain / LangGraph 等框架完成应用编排；\n"
            "4. 关注模型效果评估、延迟与成本优化。"
        ),
        "required_skills": ["LLM", "RAG", "Agent", "Prompt Engineering", "Embedding", "LangGraph"],
        "preferred_skills": ["MCP", "多模态", "模型评测", "FastAPI"],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "20K-40K",
        "status": "active",
    },
]

_BUILTIN_JOBS_MAP = {job["id"]: job for job in BUILTIN_JOBS}


def _enrich_job(job: dict) -> dict:
    position_type = get_position_type(job.get("position_key")) or get_default_position_type()
    enriched = copy.deepcopy(job)
    enriched["position_key"] = position_type["key"]
    enriched["position_label"] = position_type["label"]
    return enriched


def get_builtin_job(job_id: int) -> dict | None:
    job = _BUILTIN_JOBS_MAP.get(job_id)
    return _enrich_job(job) if job else None


def get_all_builtin_jobs() -> list[dict]:
    return [_enrich_job(job) for job in BUILTIN_JOBS]


def get_public_position_types() -> list[dict]:
    return get_all_position_types()


def get_default_position_config() -> dict:
    return get_default_position_type()


def normalize_job_position(value: str | None) -> dict:
    key = normalize_position_key(value, fallback_to_default=True)
    return get_position_type(key) or get_default_position_type()


__all__ = [
    "DEFAULT_POSITION_KEY",
    "BUILTIN_JOBS",
    "get_all_builtin_jobs",
    "get_builtin_job",
    "get_default_position_config",
    "get_default_position_label",
    "get_position_type",
    "get_public_position_types",
    "normalize_job_position",
]
