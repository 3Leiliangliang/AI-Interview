# v0.5 数据迁移指南

v0.5 版本将数据存储从 SQLite + JSON 文件迁移到 PostgreSQL。本指南帮助你完成数据迁移。

::: tip warning
迁移脚本可能会存在问题，不建议在生产环境下尝试，生产环境下，请新建或仔细检查迁移脚本，慎重迁移。
:::

## 迁移内容

| 数据类型 | 源 | 目标 | 存储内容 |
|---------|-----|------|---------|
| 业务数据 | SQLite (`saves/database/server.db`) | PostgreSQL | 用户、部门、对话、消息、工具调用、MCP 服务器等 |
| 知识库元数据 | JSON 文件 (`saves/knowledge_base_data/`) | PostgreSQL | 知识库配置、文件信息、评估数据 |
| Tasker 任务记录 | JSON 文件 (`saves/tasks/tasks.json`) | PostgreSQL | 后台任务状态、进度、结果（独立存储） |

## 迁移前准备

### 1. 启动服务

```bash
docker compose up -d --build
```

### 2. 备份数据

**重要：** 迁移前必须备份数据！

```bash
# 备份 saves 目录（包含 SQLite 数据库和知识库元数据）
cp -r saves saves_backup_$(date +%Y%m%d)

# 如果使用外部数据库，也请备份 PostgreSQL
pg_dump -U postgres -d ai_interview > pg_backup_$(date +%Y%m%d).sql
```

### 3. 确保 PostgreSQL 已启动

```bash
docker compose up -d postgres
# 等待健康检查通过
```

## 执行迁移

### 方式一：使用统一迁移脚本（推荐）

```bash
# 1. 预览迁移（不执行）
docker compose exec api python scripts/migrate_all.py --dry-run

# 2. 执行迁移
docker compose exec api python scripts/migrate_all.py --execute

# 3. 验证迁移结果
docker compose exec api python scripts/migrate_all.py --verify
```

### 方式二：分阶段迁移

```bash
# 只迁移业务数据
docker compose exec api python scripts/migrate_all.py --execute --stage business

# 只迁移知识库元数据
docker compose exec api python scripts/migrate_all.py --execute --stage knowledge

# 只迁移 Tasker 任务记录
docker compose exec api python scripts/migrate_all.py --execute --stage tasker
```

## 重启服务

```bash
docker compose up -d
```

## 验证迁移

### 检查服务状态

```bash
# 查看 API 服务日志
docker logs api-dev --tail 50

# 检查健康状态
curl http://localhost:5050/api/system/health
```

### 验证数据

```bash
# 使用迁移脚本验证
docker compose exec api python scripts/migrate_all.py --verify
```

预期输出：

```
============================================================
📊 验证结果汇总
============================================================
✅ departments: SQLite=X, PostgreSQL=X
✅ users: SQLite=X, PostgreSQL=X
✅ conversations: SQLite=X, PostgreSQL=X
...
全部匹配: ✅ 是
```
