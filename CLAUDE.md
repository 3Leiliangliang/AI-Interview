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
# 启动/停止服务（需要 .env 文件，从 .env.template 创建）
make start              # docker compose up -d
make stop                # docker compose down

# 查看容器状态和日志
docker compose ps
docker compose logs api-dev -f --tail 100
docker compose logs web-dev -f --tail 100
make logs               # 显示最近日志 + 当前分支/提交信息

# 后端代码检查和格式化
make lint               # ruff check + format check + isort check
make format             # ruff format + fix + isort fix (含前端 npm run format)

# 运行测试
make router-tests                                    # pytest test/api/（需容器运行中）
docker compose exec api uv run --group test pytest test/your_script.py  # 运行单个测试文件
docker compose exec api uv run --group test pytest test/your_script.py::test_func -k "keyword"  # 运行单个测试

# 在容器内执行 Python 脚本
docker compose exec api uv run python scripts/your_script.py

# 前端开发
cd web && pnpm install     # 安装前端依赖
cd web && pnpm run dev     # 本地开发（非 Docker 环境时）
cd web && pnpm run build   # 构建
```

**热重载**: api-dev 和 web-dev 服务均配置了热重载，修改代码后无需重启容器。

## 架构概览

### 后端分层架构

```
server/                   # FastAPI 应用层
├── main.py              # 应用入口，CORS/日志/限流/认证中间件
├── worker_main.py       # arq 后台任务 worker（处理 Agent Run）
├── routers/             # API 路由：auth, chat, knowledge, resume, job, video,
│                        #   dashboard, evaluation, mcp, mindmap, skill, tool, system, department, task
└── utils/               # 中间件、认证、工具函数

src/                      # 核心业务逻辑
├── agents/              # LangGraph 智能体
│   ├── common/          # 基础设施
│   │   ├── base.py      # BaseAgent：图管理、checkpointer、消息流
│   │   ├── context.py   # BaseContext：运行时配置（模型、工具、知识库、技能）
│   │   ├── state.py     # BaseState：messages 状态定义
│   │   ├── middlewares/  # 中间件栈（注入知识库/技能/摘要/附件/动态工具）
│   │   ├── backends/     # 后端组合（composite + openviking + skills）
│   │   └── toolkits/     # 工具集：内置工具、MySQL、知识库检索
│   ├── interview_agent/ # 模拟面试（6步任务清单：简历确认→开场→项目→技术→匹配→评分）
│   ├── chatbot/         # 通用聊天智能体
│   ├── reporter/        # 报表生成智能体
│   ├── deep_agent/      # 深度分析智能体
│   └── skills/          # 技能定义 (每个技能目录含 SKILLS.md)
├── knowledge/           # 知识库系统 (RAG)
│   ├── base.py          # 抽象基类（文件生命周期：UPLOADED→PARSING→PARSED→INDEXING→INDEXED）
│   ├── factory.py       # 知识库工厂
│   ├── implementations/ # 具体实现（openviking）
│   └── chunking/        # 分块策略（ragflow_like: book/general/laws/qa）
├── models/              # 模型封装 (chat, embed, rerank)
├── repositories/        # 数据访问层 (SQLAlchemy async)
├── storage/             # 存储层：minio/（对象存储）、postgres/（数据库连接管理）
├── plugins/             # 文档解析插件：MinerU、PaddleX OCR、DeepSeek OCR、RapidOCR
└── services/            # 业务服务层
    ├── chat_stream_service.py   # 核心流式对话（SSE、消息保存、中断检测）
    ├── agent_run_service.py     # Run 创建/轮询/取消（通过 ARQ 队列）
    ├── run_worker.py            # ARQ worker 处理 agent runs
    ├── run_queue_service.py     # Redis 队列管理 run events
    ├── match_service.py         # 简历-JD 匹配（权重：技能45%、经验35%、教育20%）
    ├── video_event_service.py   # 视频面试事件处理
    └── ...                      # conversation, evaluation, mcp, skill, openviking 等
```

### 前端架构

```
web/src/
├── apis/                # API 层：base.js 定义 apiGet/apiPost/apiAdminGet 等，按模块拆分
├── views/               # 页面：Agent, InterviewSession, Resume, Database, Dashboard, Extensions
├── components/          # 组件：AgentChat, ToolCallingResult(按工具类型分), dashboard/, modals/, sources/
├── stores/              # Pinia：user(认证), agent(智能体), chatUI, config, database, tasker, theme
├── router/              # Vue Router：AppLayout(认证)+BlankLayout 布局，权限守卫
└── assets/css/base.css  # 设计变量：颜色/阴影/滚动条，Ant Design 兼容
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
| kb-import | 知识库初始化导入 (一次性) | - |

可选服务 (需 `docker compose --profile all up`): mineru-vllm-server, mineru-api, paddlex

### 核心数据流

1. **对话流**: Client → SSE → `chat_stream_service` → `BaseAgent.stream_messages()` → LangGraph Graph → Middlewares → Tools/LLM → SSE Response
2. **Agent Run 流**: Client → `agent_run_service` → Redis/ARQ Queue → `run_worker` → Agent 执行 → Redis Event Stream → Client 轮询
3. **知识库流**: Upload → File Parse (docling/MinerU) → Chunk (ragflow_like strategies) → Embed & Index → Query via RAG

### 配置系统

- **应用配置**: `src/config/app.py` — Pydantic Config 类，从 `saves/config/base.toml` 加载
- **模型提供商**: `saves/config/custom_providers.toml` — 支持 siliconflow, openai, deepseek, dashscope, zhipuai 等
- **运行时数据**: `saves/` 目录（agents/、knowledge_base_data/、skills/、openviking/、logs/），由应用运行时自动生成，不在版本控制中
- **环境变量**: `.env` (从 `.env.template` 创建) — 密钥、服务 URL、功能开关
- **Agent 配置**: 每个 agent 的 `metadata.toml` + 运行时 `BaseContext` 覆盖

## 技能系统 (Skills)

Agent 的能力通过 `src/agents/skills/*/SKILLS.md` 定义。技能可声明所需工具/MCP，运行时自动挂载。修改或新增 Agent 技能时，需同时更新对应的 SKILLS.md 文件。

## 开发规范

### 前端

- API 接口统一定义在 `web/src/apis/` 下，通过 `base.js` 的 `apiGet/apiPost` 等方法调用
- UI 组件库：Ant Design Vue 4.x
- 图标使用 `@ant-design/icons-vue` 或 `lucide-vue-next`
- 样式使用 less，通过 `web/src/assets/css/base.css` 中的 CSS 变量保持一致性
- UI 简洁，禁止悬停位移、过度阴影和渐变色
- Pinia store 使用 Composition API setup 函数语法
- 路由守卫：`requiresAuth`、`requiresAdmin`、`requiresSuperAdmin`，非管理员默认重定向到智能体页面

### 后端

- Python 3.12+，遵循 pythonic 风格
- 使用 `uv` 管理依赖，pyproject.toml 中配置了清华 PyPI 镜像
- ruff 格式化，行宽 120，规则 F/E/W/UP
- **异常处理规范**：
  - 业务异常使用 `KnowledgeBaseException`/`KBNotFoundError`/`KBOperationError` 或显式 `HTTPException`，**不要**在 router 内 `try/except Exception` 后返回成功形状的占位数据——全局 exception handler 会统一为 `{"detail", "code"}` 形状（见 [server/main.py](server/main.py)）。
  - 后台/清理路径必须吞掉异常时，要捕获到具体变量并 `logger.error(..., exc)`，且加 `# noqa: BLE001` 标注故意行为。
  - 存量代码约有 ~356 处裸 `except Exception`，待集中清理后会启用 ruff `BLE001` 规则。新代码不许新增违规。
- pytest 配置：asyncio_mode=auto，markers 有 auth/slow/integration
- 路由器测试 (`test/api/`) 是集成测试，需要 API 容器运行中，通过 httpx.AsyncClient 发送真实 HTTP 请求
- 单元测试在 `test/unit/` 和 `test/` 根目录下
- 超级管理员环境变量：`AI_INTERVIEW_SUPER_ADMIN_NAME` / `AI_INTERVIEW_SUPER_ADMIN_PASSWORD`
- 测试环境变量：`TEST_BASE_URL`（默认 http://localhost:5050）、`TEST_USERNAME`、`TEST_PASSWORD`（配置在 `test/.env.test`）
- 测试隔离：`conftest.py` 提供常用 fixture（`test_client`、`admin_token`、`standard_user`、`knowledge_database`），每个测试自动创建/清理唯一资源

### 文档

- 开发者文档保存在 `docs/vibe/`
- 文档目录定义在 `docs/.vitepress/config.mts`，更新到 `docs/latest`

### 知识库初始化

- `.knowledge/` 为运行时缓存，已加入 gitignore
- 设置 `AUTO_IMPORT_INTERVIEW_KB=true` 可自动导入 JavaGuide、reactjs-interview-questions、Waking-Up

## Agent 开发要点

- 所有 Agent 继承 `BaseAgent`，通过中间件栈组合能力
- Agent 配置优先级：运行时参数 > 文件配置 > 类默认值
- 中间件执行顺序很重要，按定义的列表顺序依次应用
- Checkpointer 支持 SQLite（开发）和 Postgres（生产），通过 `LANGGRAPH_CHECKPOINTER_BACKEND` 控制
- 长对话自动触发摘要（30000 token 阈值），由 `OpenVikingSummaryMiddleware` 处理