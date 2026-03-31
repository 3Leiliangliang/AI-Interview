# 视频面试实时分析功能 E2E 测试指南

## 测试范围

### A. 后端 API 测试

#### 单元测试（可离线运行）

```bash
# 运行所有视频相关单元测试
cd AI-Interview
TEST_USERNAME=test TEST_PASSWORD=test PYTHONPATH=. uv run pytest test/unit/test_video_event_service.py test/unit/test_video_report_service.py test/unit/test_video_context_middleware.py -v
```

**覆盖内容：**
- `test_video_event_service.py` (22 tests) - Redis 事件存储服务
- `test_video_report_service.py` (21 tests) - 报告生成服务
- `test_video_context_middleware.py` (30 tests) - Agent 中间件上下文注入

#### 集成测试（需要 API 服务运行）

```bash
# 需要先启动 Docker 服务
docker compose up -d api-dev redis

# 运行集成测试
cd AI-Interview
TEST_USERNAME=<your-admin-user> TEST_PASSWORD=<your-password> PYTHONPATH=. uv run pytest test/api/test_video_router.py -v
```

**测试文件：** `test/api/test_video_router.py` (19 tests)
**覆盖 API 端点：**
- `POST /api/video/event` - 事件批次接收
- `GET /api/video/status/{session_id}` - 会话状态查询
- `GET /api/video/aggregate/{session_id}` - 聚合摘要查询
- `POST /api/video/report/{session_id}` - 报告生成

---

### B. 前端 E2E 测试

#### 环境准备

```bash
cd web

# 安装 Playwright（如果尚未安装）
npm install -D @playwright/test

# 安装浏览器
npx playwright install chromium
```

#### 运行测试

```bash
# 开发环境运行（自动启动 Vite dev server）
npm run test:e2e

# 有 UI 的测试运行器
npm run test:e2e:ui

# 有头模式（可见浏览器）
npm run test:e2e:headed

# 调试模式
npm run test:e2e:debug
```

#### 测试文件

- `web/e2e/video-interview.spec.js` (14 tests)
  - 10 个自动化测试
  - 4 个标记为 `test.skip` 的手动验证测试

**自动化测试覆盖：**
1. 视频模式切换按钮渲染
2. 视频模式开关交互
3. 视频分析卡片数据绑定
4. 报告卡片展示（分数、建议、优势）
5. API 事件发送集成
6. API 错误处理

**手动验证测试（需要真实硬件）：**
1. 摄像头访问和 MediaPipe 初始化
2. 实时情绪分析
3. 实时姿态检测
4. 注意力跟踪和警报

---

## 快速运行命令汇总

```bash
# 1. 后端单元测试（无需服务）
TEST_USERNAME=test TEST_PASSWORD=test PYTHONPATH=. uv run pytest test/unit/test_video_event_service.py test/unit/test_video_report_service.py test/unit/test_video_context_middleware.py -v

# 2. 后端集成测试（需要 Docker 服务）
# 先确保 docker compose up -d api-dev redis
TEST_USERNAME=<user> TEST_PASSWORD=<pass> PYTHONPATH=. uv run pytest test/api/test_video_router.py -v

# 3. 前端 E2E 测试（需要 Docker 服务运行前端）
cd web && npm run test:e2e

# 4. 所有测试
TEST_USERNAME=test TEST_PASSWORD=test PYTHONPATH=. uv run pytest test/unit/ -v
```

---

## 测试数据

测试使用以下 session_id 格式进行隔离：
- 格式：`test-sess-{uuid-hash}`
- 示例：`test-sess-a1b2c3d4`

---

## 已知限制

1. **摄像头依赖**：MediaPipe 分析需要真实摄像头硬件，自动化测试无法覆盖
2. **Redis 依赖**：集成测试需要 Redis 服务运行
3. **Docker Desktop**：Windows 环境下需要 Docker Desktop 运行
4. **测试数据隔离**：每个测试使用唯一 session_id，但 Redis 数据可能残留
