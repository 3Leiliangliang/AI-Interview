# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 项目概览

伯乐（Bole）是一个基于大模型的智能知识库与智能体开发平台，聚焦 RAG、知识库检索与面试场景，基于 LangGraph v1 + Vue.js + FastAPI 架构构建。项目完全通过 Docker Compose 进行管理，支持热重载开发。

## 开发准则

Avoid over-engineering. Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused.

Don't add features, refactor code, or make "improvements" beyond what was asked. A bug fix doesn't need surrounding code cleaned up. A simple feature doesn't need extra configurability.

Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code and framework guarantees. Only validate at system boundaries (user input, external APIs). Don't use backwards-compatibility shims when you can just change the code.

Don't create helpers, utilities, or abstractions for one-time operations. Don't design for hypothetical future requirements. The right amount of complexity is the minimum needed for the current task. Reuse existing abstractions where possible and follow the DRY principle.

## 常用命令

```bash
# 启动/停止服务
make start              # docker compose up -d
make stop                # docker compose down

# 查看容器状态和日志
docker compose ps
docker compose logs api-dev -f --tail 100
docker compose logs web-dev -f --tail 100

# 后端代码检查和格式化
make lint               # ruff check + format check
make format             # ruff format + fix + isort

# 运行测试
make router-tests       # pytest test/api/
docker compose exec api uv run --group test pytest test/your_script.py

# 在容器内执行 Python 脚本
docker compose exec api uv run python test/your_script.py
```

**热重载**: api-dev 和 web-dev 服务均配置了热重载，修改代码后无需重启容器。

## 技能系统 (Skills)

Agent 的能力通过 `src/agents/skills/*/SKILLS.md` 定义。修改或新增 Agent 技能时，需同时更新对应的 SKILLS.md 文件。

## 架构概览

### 后端目录结构

```
server/                   # FastAPI 应用层
├── main.py              # 应用入口，中间件配置
├── worker_main.py       # arq 后台任务 worker
├── routers/             # API 路由 (auth, chat, knowledge, resume, job, dashboard, evaluation 等)
└── utils/               # 中间件、认证、工具函数

src/                      # 核心业务逻辑
├── agents/              # LangGraph 智能体
│   ├── common/          # 基础设施：BaseAgent、中间件、工具集
│   ├── interview_agent/ # 模拟面试智能体 (6步任务清单)
│   ├── chatbot/         # 通用聊天智能体
│   ├── reporter/        # 报表生成智能体
│   ├── deep_agent/      # 深度分析智能体
│   └── skills/          # 技能定义 (SKILLS.md)
├── knowledge/           # 知识库系统 (RAG)
├── models/              # 模型封装 (chat, embed, rerank)
├── repositories/        # 数据访问层 (SQLAlchemy)
└── services/            # 业务服务层
```

### 前端目录结构

```
web/src/
├── apis/                # API 接口定义 (统一管理 HTTP 请求)
├── views/                # 页面视图
├── components/           # 通用组件
├── router/               # Vue Router 配置
└── stores/               # Pinia 状态管理
```

### Docker 服务

| 服务 | 说明 | 端口 |
|------|------|------|
| api-dev | FastAPI 后端 | 5050 |
| worker-dev | arq 后台任务处理 | - |
| web-dev | Vue.js 前端 (热重载) | 5173 |
| postgres | PostgreSQL 16 | 5432 |
| redis | Redis 7 | - |
| minio | 对象存储 | 9000/9001 |

可选服务 (需 `docker compose --profile all up`): mineru-vllm-server, mineru-api, paddlex

### 核心概念

- **LangGraph State**: Agent 间共享状态通过 `src/agents/common/state.py` 定义
- **Middlewares**: 请求/响应拦截处理，位于 `src/agents/common/middlewares/`
- **Toolkits**: 工具集注册与调用，位于 `src/agents/common/toolkits/`
- **Knowledge Base**: 知识库抽象基类 `src/knowledge/base.py`，分块策略 `src/knowledge/chunking/`

## 开发规范

### 前端

- API 接口定义在 `web/src/apis/` 下
- 图标使用 `@ant-design/icons-vue` 或 `lucide-vue-next`
- 样式使用 less，通过 `web/src/assets/css/base.css` 中的变量保持一致性
- UI 简洁，禁止悬停位移、过度阴影和渐变色

### 后端

- Python 3.12+，遵循 pythonic 风格
- 使用 `uv` 管理依赖
- 超级管理员调试：`BOLE_SUPER_ADMIN_NAME` / `BOLE_SUPER_ADMIN_PASSWORD`

### 文档

- 开发者文档保存在 `docs/vibe/`
- 文档目录定义在 `docs/.vitepress/config.mts`，更新到 `docs/latest`

### 知识库初始化

- `.knowledge/` 为运行时缓存，已加入 gitignore
- 设置 `AUTO_IMPORT_INTERVIEW_KB=true` 可自动导入 JavaGuide、reactjs-interview-questions、Waking-Up