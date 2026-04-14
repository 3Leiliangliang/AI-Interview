![伯乐 Logo](docx/images/logo_with_word.png)

# 伯乐 Bole

伯乐是一个基于大模型的智能知识库与智能体开发平台，聚焦 RAG、知识库检索与面试场景，基于 LangGraph v1 + Vue.js + FastAPI 架构构建。项目完全通过 Docker Compose 进行管理，支持热重载开发。

## 🌟 核心特性

- **智能体开发**：基于 LangGraph，支持子智能体、Skills、MCPs、Tools 与中间件机制的设计与开发。
- **模拟面试系统**：内置专业的 AI 模拟面试工作区，提供真实的面试记录侧边栏，支持多岗位、多轮次（初试、复试、HR面）面试推演和基于用户真实简历的深度追问。
- **智能知识库（RAG）**：支持丰富的多格式文档上传（PDF、Word、Markdown、图片压缩包等），内置 Embedding / Rerank 及知识库检索能力的自动评估。
- **知识库分块与检索**：支持通用、QA、书籍、法条等分块预设，结合 Embedding / Rerank 提供稳定的知识检索能力。
- **平台化与工程化**：Vue3 + FastAPI 现代技术架构，UI 设计深度推敲（支持暗色模式），完全 Docker 化管理，极大降低二次开发与生产级部署的门槛。

## 🛠 技术栈

- **前端**: Vue.js 3, Vue Router, Pinia, Ant Design Vue, Lucide Icons, Vite
- **后端**: Python 3.12+, FastAPI, LangChain, LangGraph v1
- **运维部署**: Docker, Docker Compose

## 🚀 快速开始

本项目完全依托于 Docker Compose 进行容器化管理，通过以下简单指令即可完整体验该平台。

### 1. 获取代码与初始化配置

```bash
https://gitcode.com/HEUwings/AI-Interview.git
cd Bole

# Linux / macOS 下执行：
./scripts/init.sh

# Windows PowerShell 下执行：
.\scripts\init.ps1
```

### 2. 构建并启动容器服务

```bash
docker compose up -d --build
```

等待构建与服务启动完成后，在浏览器中访问：`http://localhost:5173` 即可进入系统。

### 3. 面试知识库初始化说明

- `.knowledge/` 目录仅作为运行时缓存，**已加入 gitignore，不需要提交到 Git**。
- 启用知识库自动导入后，`kb-import` 容器会先同步精选的上游面试资料到 `.knowledge/interview_sources/`，再走现有 `/knowledge/*` 文件上传、解析、分块与索引流程：
  - `Snailclimb/JavaGuide`：后端面试、Java 基础、数据库、系统设计，以及 `docs/ai` 下的 LLM/RAG/Agent/AI Coding 内容
  - `sudheerj/reactjs-interview-questions`：React 问答与 coding exercise
  - `yangshun/front-end-interview-handbook`：前端面试手册、行为面试、React playbook
  - `yangshun/tech-interview-handbook`：行为面试、编码面试准备、系统设计准备、自我介绍与简历
  - `donnemartin/system-design-primer`：系统设计基础与经典系统设计案例
  - `TharunKumarReddyPolu/DSA-Handbook-for-Coding-Interviews`：算法与数据结构高频题型手册
  - `aswanth6000/nodejs-interview-questions`：Node.js 一问一答题库与进阶问答
  - `xoraus/CrackingTheSQLInterview`：SQL 基础、事务、索引与高频 SQL 问答
- 若 `.env` 或 `.env.prod` 中开启了 `AUTO_IMPORT_INTERVIEW_KB=true`，启动后会自动：
  1. 同步并清洗上游 Markdown/MDX 面试资料，生成本地精选知识源
  2. 调用现有知识库 API 导入多个知识库（JavaGuide 后端面试、AI 应用开发面试、React 面试题库、前端面试手册、通用技术面试手册、系统设计面试题库、DSA 面试手册、Node.js 面试题库、SQL 面试题库）
  3. 导入完成后写入 sentinel，后续重启默认不重复导入
- 首次启用或更新了导入镜像后，建议执行：

```bash
docker compose up -d --build
```

### 4. 语音面试配置

语音面试功能依赖豆包双向流式 TTS，以及阿里云 DashScope Fun-ASR 实时语音识别。启动前请在项目根目录 `.env` 中至少配置以下变量：

```env
DOUBAO_VOICE_APP_ID=your_app_id
DOUBAO_VOICE_API_KEY=your_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
```

当前仓库中的语音面试后端已固定使用以下豆包音色组合：

```env
speaker=zh_male_m191_uranus_bigtts
resource_id=seed-tts-2.0
```

注意事项：

- 这组 `speaker` / `resource_id` 需要保持匹配，否则语音面试 WebSocket 可以建立，但不会返回可播放的音频分片。
- 前端浏览器需要先经过用户点击触发音频上下文恢复与麦克风授权，因此需要在页面中点击“开启语音面试”后才会开始播放并准备候选人语音输入。
- 候选人语音会通过浏览器麦克风实时转写，句子结束后的最终修正文案会自动提交给原面试 Agent 继续追问。
- 当前默认使用阿里云 Fun-ASR 的 VAD 断句，候选人回答时连续约 3 秒无声音，才会将该句最终修正文案提交给面试 Agent，避免短暂停顿被过早发送。
- 修改 `.env` 后，需重新构建或重启后端容器以确保配置生效。


## 👨‍💻 开发与调试指南

本项目极力推崇**保持专注**与**拒绝过度设计**。所有的开发和调试均可以在 `docker compose up` 运行的容器环境热重载中完成，确保了不同设备间的高度一致性。

### 日常调试命令

```bash
# 查看各个容器的状态
docker compose ps

# 跟进后端实时日志
docker compose logs -f api

# 在容器内直接执行特定脚本 (如使用 uv run test)
docker compose exec api uv run python test/your_script.py

# 后端代码规范检查与格式化 (宿主机执行)
make lint
make format
```

### 编码规范

**前端规范**：
- 所有的 API 接口调用需统一定义在 `web/src/apis` 目录下，禁止在组件中散落 HTTP 请求。
- 图标优先使用 `lucide-vue-next`。
- 样式通过 `less` 进行编写，须严格使用 `web/src/assets/css/base.css` 中的全局颜色主题变量。UI 坚守简洁与一致性原则，禁止滥用重阴影、悬停位移与高饱和度渐变色。

**后端规范**：
- 严格遵循 Pythonic 代码风格，合理借助 Python 3.12+ 带来的现代语法特性。
- 在接口调试与权限验证阶段，可通过查阅或修改 `.env` 环境变量文件中的 `AI_INTERVIEW_SUPER_ADMIN_NAME` / `AI_INTERVIEW_SUPER_ADMIN_PASSWORD` 使用对应的超级管理员身份进行访问。

## 📝 证书说明

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解更多详情。
