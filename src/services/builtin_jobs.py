"""内置岗位数据 - 三种校招级别岗位（前端、后端、算法工程师）"""

import copy

BUILTIN_JOBS = [
    {
        "id": 1,
        "title": "前端开发工程师",
        "department": "技术部",
        "description": (
            "负责 Web 前端开发与维护，参与前端架构设计与性能优化，"
            "与设计师和后端工程师协作完成产品功能开发。"
        ),
        "requirements": (
            "1. 熟练掌握 HTML/CSS/JavaScript 前端基础技术；\n"
            "2. 掌握至少一种主流前端框架（Vue.js / React）；\n"
            "3. 了解前端工程化和模块化开发（Webpack / Vite）；\n"
            "4. 计算机基础扎实（数据结构、算法、网络）；\n"
            "5. 具备良好的编程习惯和代码质量意识；\n"
            "6. 学习能力强，对新技术保持热情和好奇心。"
        ),
        "required_skills": [
            "HTML5",
            "CSS3",
            "JavaScript",
            "Vue.js",
            "React",
            "Git",
            "HTTP",
            "Webpack",
            "Vite",
            "ES6",
            "Flex布局",
            "响应式设计",
        ],
        "preferred_skills": [
            "TypeScript",
            "Node.js",
            "小程序",
            "React Native",
            "Less",
            "Sass",
            "前端性能优化",
            "Element UI",
            "Ant Design",
            "XSS防护",
            "CSRF防护",
            "Jest",
            "Cypress",
        ],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "15K-30K",
        "status": "active",
    },
    {
        "id": 2,
        "title": "后端开发工程师",
        "department": "技术部",
        "description": (
            "负责后端服务开发与维护，参与系统架构设计与数据库设计，"
            "编写高质量的 RESTful API，保障线上系统稳定性。"
        ),
        "requirements": (
            "1. 熟练掌握至少一种后端开发语言（Java / Python / Go）及常用框架；\n"
            "2. 扎实的计算机基础（数据结构与算法、操作系统、计算机网络）；\n"
            "3. 熟悉关系型数据库（MySQL / PostgreSQL）设计和 SQL 优化；\n"
            "4. 了解 Redis 等缓存技术；\n"
            "5. 熟悉常用网络协议（HTTP / TCP/IP）和 Linux 基础；\n"
            "6. 良好的编码习惯、沟通协作能力和责任心。"
        ),
        "required_skills": [
            "Java",
            "Python",
            "Go",
            "MySQL",
            "PostgreSQL",
            "SQL",
            "Redis",
            "Spring Boot",
            "Django",
            "FastAPI",
            "Gin",
            "Git",
            "Linux",
            "数据结构与算法",
            "计算机网络",
        ],
        "preferred_skills": [
            "微服务",
            "Spring Cloud",
            "Dubbo",
            "Kafka",
            "RabbitMQ",
            "Docker",
            "CI/CD",
            "分布式系统",
            "Nginx",
            "单元测试",
            "MyBatis",
            "JPA",
        ],
        "min_experience_years": 0,
        "education_level": "本科及以上",
        "salary_range": "18K-35K",
        "status": "active",
    },
    {
        "id": 3,
        "title": "算法工程师",
        "department": "AI 研究院",
        "description": (
            "负责机器学习 / 深度学习算法研究与落地，参与模型训练与调优，"
            "阅读和复现前沿论文算法，与工程团队配合实现算法产品化。"
        ),
        "requirements": (
            "1. 硕士及以上学历，计算机 / 数学 / 统计 / AI 相关专业；\n"
            "2. 扎实的编程能力（Python / C++）和数学基础（线性代数、概率论、优化）；\n"
            "3. 熟悉机器学习和深度学习算法原理与实战；\n"
            "4. 熟练使用 PyTorch 或 TensorFlow 等深度学习框架；\n"
            "5. 有论文发表或竞赛获奖经验优先；\n"
            "6. 良好的英文文献阅读能力和创新意识。"
        ),
        "required_skills": [
            "Python",
            "PyTorch",
            "TensorFlow",
            "机器学习",
            "深度学习",
            "CNN",
            "RNN",
            "Transformer",
            "NumPy",
            "Pandas",
            "Scikit-learn",
            "线性代数",
            "概率论",
            "Linux",
        ],
        "preferred_skills": [
            "C++",
            "BERT",
            "GPT",
            "LLM",
            "YOLO",
            "目标检测",
            "图像分割",
            "推荐系统",
            "DeepSpeed",
            "HuggingFace",
            "NLP",
            "计算机视觉",
            "Kaggle",
            "ACM",
            "论文发表",
        ],
        "min_experience_years": 0,
        "education_level": "硕士及以上",
        "salary_range": "25K-50K",
        "status": "active",
    },
]

# 按 ID 索引的查找字典
_BUILTIN_JOBS_MAP = {job["id"]: job for job in BUILTIN_JOBS}


def get_builtin_job(job_id: int) -> dict | None:
    """根据 ID 获取内置岗位数据（返回深拷贝），未找到返回 None"""
    job = _BUILTIN_JOBS_MAP.get(job_id)
    return copy.deepcopy(job) if job else None


def get_all_builtin_jobs() -> list[dict]:
    """获取所有内置岗位数据（返回深拷贝）"""
    return copy.deepcopy(BUILTIN_JOBS)
