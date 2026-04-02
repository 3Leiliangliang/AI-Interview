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
- 启用知识库自动导入后，`kb-import` 容器会先将以下 GitHub 仓库克隆或更新到 `.knowledge/`，再执行现有导入流程：
  - `JavaGuide`
  - `reactjs-interview-questions`
  - `Waking-Up`
- 若 `.env` 或 `.env.prod` 中开启了 `AUTO_IMPORT_INTERVIEW_KB=true`，启动后会自动：
  1. 拉取 `.knowledge` 下的三份面试资料
  2. 调用现有知识库 API 导入
  3. 导入完成后写入 sentinel，后续重启默认不重复导入
- 首次启用或更新了导入镜像后，建议执行：

```bash
docker compose up -d --build
```

## 👨‍💻 开发与调试指南

本项目极力推崇**保持专注**与**拒绝过度设计**。所有的开发和调试均可以在 `docker compose up` 运行的容器环境热重载中完成，确保了不同设备间的高度一致性。

### 日常调试命令

```bash
# 查看各个容器的状态
docker compose ps

# 跟进后端实时日志
docker compose logs api-dev -f --tail 100

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
