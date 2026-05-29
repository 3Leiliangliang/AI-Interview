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

---

# 快速索引 (Token-Efficient Lookup)

以下章节是紧凑的索引表，用于快速定位代码位置，减少盲目搜索。

## 后端：Router → 功能/前缀

| Router 文件 | API 前缀 | 核心功能 | 对应 Service |
|---|---|---|---|
| `system_router.py` | `/api/system/*` | 系统配置、模型列表、提供商管理 | 直接读 `src/config/app.py` |
| `auth_router.py` | `/api/auth/*` | 登录/注册/Token/用户信息 | `user_repository.py` |
| `chat_router.py` | `/api/chat/*` | SSE 对话流、消息历史 | `chat_stream_service.py` |
| `knowledge_router.py` | `/api/knowledge/*` | 知识库 CRUD、文件上传/解析/检索 | `knowledge/base.py`, `openviking_service.py` |
| `interview_router.py` | `/api/interview/*` | 面试会话、问题生成、编码评估 | `interview_agent/`, `interview_coding_service.py` |
| `resume_router.py` | `/api/resume/*` | 简历上传/解析/匹配 | `match_service.py`, `resume_summary_service.py` |
| `job_router.py` | `/api/job/*` | JD 管理、职位类型 | `position_types.py` |
| `video_router.py` | `/api/video/*` | 视频面试、语音面试 | `video_event_service.py`, `video_report_service.py` |
| `evaluation_router.py` | `/api/evaluation/*` | 面试评估、反馈 | `evaluation_service.py`, `feedback_service.py` |
| `dashboard_router.py` | `/api/dashboard/*` | 仪表盘统计 | `dashboard_api.js` 调用 |
| `mcp_router.py` | `/api/mcp/*` | MCP 服务器配置 | `mcp_service.py` |
| `skill_router.py` | `/api/skill/*` | 技能管理 | `skill_service.py` |
| `tool_router.py` | `/api/tool/*` | 工具管理 | `tool_service.py` |
| `task_router.py` | `/api/task/*` | 后台任务状态 | `task_service.py`, `run_queue_service.py` |
| `mindmap_router.py` | `/api/mindmap/*` | 思维导图 | — |

## 后端：Service → 职责 (一行描述)

| Service 文件 | 职责 |
|---|---|
| `chat_stream_service.py` | **核心文件**：LangGraph SSE 流式对话，消息持久化，中断/恢复处理 |
| `agent_run_service.py` | Agent Run 的创建、状态轮询、取消 |
| `run_worker.py` | ARQ 队列 worker，执行 Agent Run 的实际逻辑 |
| `run_queue_service.py` | Redis 队列管理：enqueue run、分发 event、线程池执行 |
| `match_service.py` | 简历-JD 匹配打分（技能45% + 经验35% + 教育20%） |
| `interview_coding_service.py` | 编程题评估、代码运行沙箱 |
| `interview_result_service.py` | 面试结果汇总、评分计算（SEP 优先路径，LLM 评分卡兜底） |
| `interview_result_sep_helpers.py` | SEP 报告→评分卡转换、确定性叙述生成、题库 slug 解析、Jaccard 兜底匹配（纯函数，无 IO） |
| `sep/`（目录） | SEP 结构化评估流水线：自适应选题、认知特征抽取、证据链构建、IRT 能力估计、会话缓存 |
| `interview_resume_service.py` | 面试中的简历解析与信息提取 |
| `video_event_service.py` | 视频面试事件流处理 |
| `video_report_service.py` | 视频面试报告生成 |
| `voice_interview_service.py` | 语音面试（TTS/STT） |
| `evaluation_service.py` | 面试评估维度与指标 |
| `feedback_service.py` | 用户反馈收集与存储 |
| `conversation_service.py` | 对话元数据管理 |
| `history_query_service.py` | 对话历史查询 |
| `resume_summary_service.py` | 简历内容摘要提取 |
| `openviking_service.py` | OpenViking 知识库后端操作 |
| `mcp_service.py` | MCP Server 生命周期管理 |
| `skill_service.py` | 技能注册与查询 |
| `tool_service.py` | 工具注册与查询 |
| `task_service.py` | 后台任务状态跟踪 |
| `builtin_jobs.py` | 定时任务（知识库清理等） |
| `doc_converter.py` | 文档格式转换（DOCX→MD 等） |
| `position_types.py` | 职位类型常量定义 |

## 后端：Repository → 数据库表

| Repository 文件 | 对应数据表/模型 |
|---|---|
| `user_repository.py` | users |
| `agent_config_repository.py` | agent_configs |
| `agent_run_repository.py` | agent_runs |
| `conversation_repository.py` | conversations, messages |
| `knowledge_base_repository.py` | knowledge_bases |
| `knowledge_file_repository.py` | knowledge_files |
| `evaluation_repository.py` | evaluations |
| `skill_repository.py` | skills |
| `mcp_server_repository.py` | mcp_servers |
| `task_repository.py` | tasks |
| `message_feedback_repository.py` | message_feedback |
| `operation_log_repository.py` | operation_logs |
| `department_repository.py` | departments |

## 后端：Agent 中间件执行链

中间件在 `src/agents/common/middlewares/` 中定义，按 `BaseAgent._build_graph()` 中的列表顺序依次包裹 Graph：

1. `attachment_middleware.py` — 注入用户附件（文件/图片）
2. `context_middlewares.py` — 注入对话上下文（system prompt、用户信息）
3. `dynamic_tool_middleware.py` — 动态挂载工具（数据库查询、MCP）
4. `knowledge_base_middleware.py` — 注入知识库检索工具
5. `openviking_context_middleware.py` — OpenViking 特有上下文
6. `openviking_summary_middleware.py` — 长对话摘要（30000 token 阈值）
7. `runtime_config_middleware.py` — 注入运行时配置覆盖
8. `skills_middleware.py` — 注入技能定义
9. `summary_middleware.py` — 通用摘要中间件
10. `video_context_middleware.py` — 视频面试上下文

修改对话行为时，先确定是哪个中间件负责，再定位到具体中间件文件。

## 后端：关键连接点 (Wiring Files)

这些文件负责子系统之间的连接和初始化：

| 文件 | 作用 |
|---|---|
| `server/main.py` | FastAPI app 创建、CORS、全局异常 handler、启动 |
| `server/routers/__init__.py` | 所有 router 的注册和 `APIRouter` 组装 |
| `server/utils/lifespan.py` | 启动时初始化：DB、MCP、知识库、Redis、调度器 |
| `src/agents/__init__.py` | `AgentManager`：自动发现、注册、实例化所有 Agent |
| `src/knowledge/__init__.py` | 知识库管理器入口 |
| `src/storage/postgres/manager.py` | 数据库连接管理、schema 同步 |
| `src/config/app.py` | 应用全局配置类（Pydantic），TOML 读写 |
| `src/models/` | LLM/Chat 模型封装 |
| `docker/` | Dockerfile 和 compose 配置 |

## 前端：Route → View → API 映射

| URL 路径 | View 文件 | 主要 API 文件 | 权限 |
|---|---|---|---|
| `/` | `HomeView.vue` | — | 公开 |
| `/login` | `LoginView.vue` | `base.js` (auth) | 公开 |
| `/agent` | `AgentView.vue` | `agent_api.js` | 需登录 |
| `/agent/interview` | `InterviewSessionView.vue` | `agent_api.js`, `interview_history.js` | 需登录 |
| `/agent/interview/voice` | `VoiceInterviewView.vue` | `interview_voice.js` | 需登录 |
| `/agent/interview/code` | `InterviewCodingView.vue` | `interview_code.js` | 需登录 |
| `/agent/interview/result` | `InterviewResultView.vue` | `interview_history.js` | 需登录 |
| `/agent/records` | `InterviewRecordsView.vue` | `interview_history.js` | 需登录 |
| `/resume` | `MyResumeView.vue` | `resume_api.js` | 需登录 |
| `/resume/:id` | `ResumeDetailView.vue` | `resume_api.js`, `job_api.js` | 需登录 |
| `/learn` | `LearnHomeView.vue` | `learn_api.js` | 需登录 |
| `/learn/:db_id` | `LearnDatabaseView.vue` | `learn_api.js` | 需登录 |
| `/learn/:db_id/doc/:file_id` | `LearnDocumentView.vue` | `learn_api.js` | 需登录 |
| `/practice` | `PracticeHomeView.vue` | `practice_api.js` | 需登录 |
| `/practice/problem/:ref` | `PracticeProblemView.vue` | `practice_api.js` | 需登录 |
| `/oj` | `InterviewCodingView.vue` | `problemset_api.js` | 需登录 |
| `/database` | `DataBaseView.vue` | `knowledge_api.js` | 需管理员 |
| `/database/:id` | `DataBaseInfoView.vue` | `knowledge_api.js` | 需管理员 |
| `/problemsets` | `ProblemSetManageView.vue` | `problemset_api.js` | 需管理员 |
| `/dashboard` | `DashboardView.vue` | `dashboard_api.js` | 需管理员 |
| `/extensions` | `ExtensionsView.vue` | `mcp_api.js`, `skill_api.js`, `tool_api.js` | 需超管 |

## 前端：Store → 状态职责

| Store 文件 | 管理状态 |
|---|---|
| `user.js` | 认证 token、用户信息、登录状态、角色判断 |
| `agent.js` | 智能体列表、默认智能体、agent 信息缓存 |
| `chatUI.js` | 对话界面状态、消息列表、流式响应处理 |
| `config.js` | 系统全局配置（主题、功能开关） |
| `database.js` | 知识库列表、文件管理状态 |
| `tasker.js` | 后台任务状态轮询 |
| `theme.js` | 主题切换（亮/暗） |
| `video-analysis.js` | 视频面试分析结果 |

## 前端：Composable → 用途

| Composable | 用途 |
|---|---|
| `useAgentStreamHandler.js` | 处理 Agent SSE 流式响应 |
| `useApproval.js` | 工具调用审批流程 |
| `useMention.js` | @提及和输入提示 |
| `usePositionTypes.js` | 职位类型数据加载 |
| `useVideoAnalysis.js` | 视频面试分析逻辑 |
| `useVideoCapture.js` | 摄像头捕获 |
| `useVideoEventStream.js` | 视频面试 SSE 事件流 |
| `useVoiceInterviewSession.js` | 语音面试会话管理 |

## 后端：测试 → 源码映射

| 测试文件 | 测试目标 |
|---|---|
| `test/api/test_auth_router.py` | `auth_router.py` |
| `test/api/test_chat_router.py` | `chat_router.py`, `chat_stream_service.py` |
| `test/api/test_knowledge_router.py` | `knowledge_router.py`, 知识库系统 |
| `test/api/test_resume_match_router.py` | `resume_router.py`, `match_service.py` |
| `test/api/test_job_router.py` | `job_router.py` |
| `test/api/test_video_router.py` | `video_router.py` |
| `test/api/test_evaluation_router.py` | `evaluation_router.py` |
| `test/api/test_dashboard_router.py` | `dashboard_router.py` |
| `test/api/test_task_router.py` | `task_router.py` |
| `test/api/test_system_router.py` | `system_router.py` |
| `test/api/test_settings_router.py` | 系统配置相关 |
| `test/api/test_job_position_types_router.py` | `position_types.py` |
| `test/api/test_attachment_and_agent_state.py` | 附件处理 + Agent 状态 |
| `test/api/test_skill_router.py` | `skill_router.py` |
| `test/test_skill_service.py` | `skill_service.py` |
| `test/test_skills_backend.py` | `skills_backend.py` |
| `test/test_agent_run_service.py` | `agent_run_service.py` |
| `test/test_run_worker.py` | `run_worker.py` |
| `test/test_run_queue_service.py` | `run_queue_service.py` |
| `test/test_chat_stream_interrupt.py` | SSE 中断/恢复 |
| `test/test_conversation_repository.py` | `conversation_repository.py` |
| `test/test_conversation_service_attachment_state.py` | 对话附件状态 |
| `test/unit/test_match_service.py` | `match_service.py` |
| `test/unit/test_interview_coding_service.py` | `interview_coding_service.py` |
| `test/unit/test_interview_result_service.py` | `interview_result_service.py` |
| `test/unit/test_video_event_service.py` | `video_event_service.py` |
| `test/unit/test_video_report_service.py` | `video_report_service.py` |
| `test/unit/test_voice_interview_service.py` | `voice_interview_service.py` |
| `test/unit/test_video_context_middleware.py` | `video_context_middleware.py` |
| `test/unit/test_runtime_request_context.py` | `runtime_request_context.py` |
| `test/unit/test_position_types.py` | `position_types.py` |
| `test/unit/test_backend_e2e_workflow.py` | 端到端工作流 |
| `test/unit/test_interview_knowledge_sources.py` | 面试知识源 |
| `test/unit/test_interview_question_kb_resolution.py` | 面试问题知识库解析 |
| `test/test_ragflow_like_chunking.py` | `chunking/ragflow_like/` |
| `test/test_kb_minio_cleanup.py` | MinIO 清理 |
| `test/test_mysql_connection.py` | MySQL 连接 |
| `test/test_concurrency.py` | 并发安全 |

## 常见任务 → 起点文件

| 任务 | 首选阅读文件 (按顺序) |
|---|---|
| 添加新 API 端点 | `server/routers/<module>_router.py` → 对应 `src/services/<module>_service.py` |
| 添加新聊天工具 | `src/agents/common/toolkits/` → 在 `middlewares/dynamic_tool_middleware.py` 注册 |
| 添加新 Agent 技能 | `src/agents/skills/<skill>/SKILLS.md` + 对应 Agent 的 `metadata.toml` |
| 修改对话行为 | `src/agents/common/middlewares/` — 先确定是哪个中间件 |
| 修改知识库分块 | `src/knowledge/chunking/ragflow_like/presets.py` |
| 修改文档解析 | `src/plugins/` — 工厂入口 `document_processor_factory.py` |
| 修改前端页面 | 查上面的 "Route → View → API 映射" 表 |
| 修改数据库 schema | `src/storage/postgres/manager.py` (表创建) + 对应 repository |
| 添加配置项 | `src/config/app.py` (Config 类) + `saves/config/base.toml` |
| 修改 Agent 图结构 | 对应 Agent 的 `graph.py` (如 `interview_agent/graph.py`) |
| 修改 SEP 评分/选题逻辑 | `src/services/sep/`（核心算法） → `interview_result_sep_helpers.py`（转换/叙述） → `interview_result_service.py` 的 `_try_sep_scoring`（集成） |
| 调整 SEP 题库 | `src/data/question_banks/{backend,frontend,algorithm}.json`（注意：`src/data` 默认 gitignore，题库通过 `.gitignore` 负向规则显式纳入版本控制） |
| 添加前端 API 调用 | `web/src/apis/base.js` (看已有模式) → 新建或修改 API 文件 |
| 排查启动错误 | `server/utils/lifespan.py` (启动顺序) → `docker compose logs api-dev` |

---

# SEP 结构化评估流水线 (Structured Evaluation Pipeline)

**设计目标**：把面试评分路径从"答案→LLM→分数"（LLM 既当考官又当裁判，分数不可解释、不可复现、随模型版本漂移）改造为**确定性、可溯源、模型无关**的三层流水线。LLM 仅负责自然语言 I/O（题目润色、叙述生成），所有打分逻辑均为规则化计算。

**三层架构**（`src/services/sep/`）：

1. **自适应选题** (`adaptive_selector.py` + `ability_estimator.py`)：基于简化 IRT 估计候选人能力 θ，结合领域覆盖率选信息增益最大的题。
2. **认知特征抽取** (`feature_extractor.py`)：将答案文本映射为 8 维特征向量（关键词命中率、STAR 完整度、误区计数、模糊词比例等），**零 LLM 调用**，用 jieba 中文分词。
3. **证据链构建** (`evidence_builder.py` + `rubric_engine.py`)：rubric 映射打分，产出可溯源的证据项（每一分的加减都对应一句候选人原话）。

**运行时接入**：
- **提问时** Agent 调用 `pick_sep_adaptive_question`（`src/agents/common/toolkits/kbs/tools.py`），由 `session_cache.py` 维护线程级 `SEPSession`，把选中题 id 缓存；SEP 题库耗尽时降级到 `pick_random_technical_question`。
- **评分时** `interview_result_service.py` 的 `_try_sep_scoring` 优先用缓存的 adaptive 会话精准评分；旧会话走 Jaccard 模糊匹配兜底。低覆盖率时 `score_source` 标记为 `sep_partial`，前端会提示。
- **前端**：`web/src/components/sep/{EvidenceChain,AdaptiveTrajectory}.vue` 在 `InterviewResultView.vue` 中展示证据链与 θ 轨迹。

**关键约束**：题库 JSON 在 `src/data/question_banks/`，依赖 `.gitignore` 负向规则纳入版本控制（`src/data` 整体被忽略）；`jieba` 缺失时分词降级为 2-gram 字符窗口，不会崩溃。

> 设计文档：[docs/superpowers/specs/2026-05-23-sep-structured-evaluation-pipeline-design.md](docs/superpowers/specs/2026-05-23-sep-structured-evaluation-pipeline-design.md)；实现计划：[docs/superpowers/plans/2026-05-23-sep-structured-evaluation-pipeline.md](docs/superpowers/plans/2026-05-23-sep-structured-evaluation-pipeline.md)。
