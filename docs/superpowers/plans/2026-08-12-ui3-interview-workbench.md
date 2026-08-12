# UI v3 面试工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `/interview` 面试工作台三栏页面，把「新面试配置 / 主线进度 / 最近记录」收进一屏，并把旧配置页入口重定向过来。

**Architecture:** 后端在 `/api/interview/history` 的每条记录上补 `question_count` / `answered_count` 两个字段（一次 `GROUP BY` 聚合，无 N+1）。前端新增单文件视图 `InterviewWorkbenchView.vue`，消费 `/api/interview/history`（记录、趋势、偏弱）、`resumeApi.getMyResumes()`（简历）、`learnApi.getDatabases()`（出题知识库）、`usePositionTypes()`（岗位）。旧路由名 `AgentComp` 被删除，5 处引用同步改名。

**Tech Stack:** Vue 3 (`<script setup>`) + Vue Router 4 + Ant Design Vue 4 + less；后端 FastAPI + SQLAlchemy async + pytest。

## Global Constraints

- 设计稿：`templates/新版界面 v3.dc.html` 锚点 `#2a`；设计文档：`docs/superpowers/specs/2026-08-12-ui3-interview-workbench-design.md`
- 色值一律走 `web/src/assets/css/base.css` 的 CSS 变量，**不写死 hex**。暗色靠 `base.dark.css` 同名变量自动适配。
- 零圆角（`border-radius: 0`）、1px 分隔线（`--gray-200` / `--gray-100`）
- 主色（`--main-color`）只允许出现在四处：`开始面试` 主按钮、进行中标签与进度条、能力趋势折线与数据点、反复偏弱的低分数字
- 禁止悬停位移（`transform: translate*`）、阴影（`box-shadow`）、渐变（`linear-gradient`）
- 小标签统一样式：`font-size: 11px; letter-spacing: .12em; font-weight: 700; color: var(--gray-500)`
- 后端 ruff 行宽 120，规则 F/E/W/UP；新代码不许出现裸 `except Exception`
- 前端无单元测试框架（只有 Playwright e2e），前端任务的验证方式是 `pnpm run lint` + `pnpm run build` + 手工核对验收标准
- 后端测试命令：`docker compose exec api uv run --group test pytest <path> -v`（需容器运行中）
- 关键常量：`EXPECTED_QUESTION_COUNT = 8`（前端 UI 常量，预计题量）、`LOW_SCORE_THRESHOLD = 75`（后端已有，前端偏弱判定与之对齐）

---

### Task 1: 后端 — 按 thread_id 聚合各角色消息数

**Files:**
- Modify: `src/repositories/conversation_repository.py`（在 `get_latest_assistant_messages_by_thread_ids` 之后，约第 229 行）
- Test: `test/test_conversation_repository.py`

**Interfaces:**
- Produces: `ConversationRepository.count_messages_by_role_for_thread_ids(thread_ids: list[str]) -> dict[str, dict[str, int]]`，返回形如 `{"t-1": {"user": 5, "assistant": 6}}`。Task 3 会调用它。

- [ ] **Step 1: 写失败测试**

在 `test/test_conversation_repository.py` 末尾追加。这里用假 `db`：SQLAlchemy 的 `db.execute()` 返回一个有 `.all()` 的结果对象，我们只关心方法怎么把行折叠成字典，不测 SQL 本身。

```python
import pytest


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    async def execute(self, query):
        self.executed.append(query)
        return _FakeResult(self._rows)


@pytest.mark.asyncio
async def test_count_messages_by_role_groups_rows_by_thread():
    session = _FakeSession(
        [
            ("t-1", "user", 5),
            ("t-1", "assistant", 6),
            ("t-2", "assistant", 2),
        ]
    )
    repo = ConversationRepository(session)  # type: ignore[arg-type]

    counts = await repo.count_messages_by_role_for_thread_ids(["t-1", "t-2"])

    assert counts == {
        "t-1": {"user": 5, "assistant": 6},
        "t-2": {"assistant": 2},
    }


@pytest.mark.asyncio
async def test_count_messages_by_role_returns_empty_without_querying():
    session = _FakeSession([])
    repo = ConversationRepository(session)  # type: ignore[arg-type]

    counts = await repo.count_messages_by_role_for_thread_ids(["", "   "])

    assert counts == {}
    assert session.executed == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker compose exec api uv run --group test pytest test/test_conversation_repository.py -v`
Expected: FAIL — `AttributeError: 'ConversationRepository' object has no attribute 'count_messages_by_role_for_thread_ids'`

- [ ] **Step 3: 实现方法**

插到 `src/repositories/conversation_repository.py` 中 `get_latest_assistant_messages_by_thread_ids` 方法结束之后（第 228 行 `return {...}` 的下一行）：

```python
    async def count_messages_by_role_for_thread_ids(self, thread_ids: list[str]) -> dict[str, dict[str, int]]:
        normalized_thread_ids = [str(thread_id).strip() for thread_id in thread_ids if str(thread_id).strip()]
        if not normalized_thread_ids:
            return {}

        query = (
            select(
                Conversation.thread_id,
                Message.role,
                func.count(Message.id),
            )
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.thread_id.in_(normalized_thread_ids))
            .group_by(Conversation.thread_id, Message.role)
        )
        result = await self.db.execute(query)

        counts: dict[str, dict[str, int]] = {}
        for thread_id, role, count in result.all():
            counts.setdefault(str(thread_id), {})[str(role)] = int(count)
        return counts
```

`select` / `func` 已在文件顶部第 7 行导入，无需新增 import。

- [ ] **Step 4: 运行测试确认通过**

Run: `docker compose exec api uv run --group test pytest test/test_conversation_repository.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add src/repositories/conversation_repository.py test/test_conversation_repository.py
git commit -m "feat(repo): 按 thread_id 聚合各角色消息数"
```

---

### Task 2: 后端 — 历史记录补 question_count / answered_count

**Files:**
- Modify: `src/services/interview_result_service.py:3409`（`_build_history_record` 函数签名与返回值）
- Test: `test/unit/test_interview_result_service.py`

**Interfaces:**
- Consumes: 无（纯函数改造）
- Produces: `_build_history_record(*, conversation, result_payload, message_counts: dict[str, int])`，返回字典新增 `question_count: int`、`answered_count: int`。Task 3 负责传入 `message_counts`。

`message_counts` 是**单个 thread 的**角色计数（即 Task 1 返回值中的一项），形如 `{"user": 5, "assistant": 6}`。

- [ ] **Step 1: 写失败测试**

追加到 `test/unit/test_interview_result_service.py` 末尾。`_build_history_record` 只读 `conversation` 的几个属性，用 `SimpleNamespace` 造即可（文件顶部已导入 `SimpleNamespace`）。

```python
def _make_history_conversation():
    return SimpleNamespace(
        thread_id="t-1",
        title="后端工程师 · 初试",
        created_at=None,
        updated_at=None,
        extra_metadata={"interview_mode": "text", "target_position": "后端工程师", "interview_round": "初试"},
    )


def test_build_history_record_exposes_question_and_answered_counts():
    record = service._build_history_record(
        conversation=_make_history_conversation(),
        result_payload=None,
        message_counts={"user": 6, "assistant": 8},
    )

    assert record["question_count"] == 8
    # 扣掉自动注入的开场 prompt（一条 user 消息，不是候选人的回答）
    assert record["answered_count"] == 5


def test_build_history_record_counts_are_zero_without_messages():
    record = service._build_history_record(
        conversation=_make_history_conversation(),
        result_payload=None,
        message_counts={},
    )

    assert record["question_count"] == 0
    assert record["answered_count"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker compose exec api uv run --group test pytest test/unit/test_interview_result_service.py -k "question_and_answered or counts_are_zero" -v`
Expected: FAIL — `TypeError: _build_history_record() got an unexpected keyword argument 'message_counts'`

- [ ] **Step 3: 实现**

改 `src/services/interview_result_service.py:3409` 的签名：

```python
def _build_history_record(
    *,
    conversation,
    result_payload: dict[str, Any] | None,
    message_counts: dict[str, int],
) -> dict[str, Any]:
```

在函数体末尾 `return {` 之前插入：

```python
    question_count = int(message_counts.get("assistant") or 0)
    # 开场 prompt 由前端自动注入，是一条 user 消息但不是候选人的回答
    answered_count = max(0, int(message_counts.get("user") or 0) - 1)
```

在返回字典中 `"result_generated_at"` 之后追加两项：

```python
        "question_count": question_count,
        "answered_count": answered_count,
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker compose exec api uv run --group test pytest test/unit/test_interview_result_service.py -v`
Expected: PASS（新增 2 个通过；若 `get_interview_history` 的调用点还没改，本步不受影响，因为它不在单测覆盖内）

- [ ] **Step 5: 提交**

```bash
git add src/services/interview_result_service.py test/unit/test_interview_result_service.py
git commit -m "feat(interview): 历史记录补 question_count 与 answered_count"
```

---

### Task 3: 后端 — get_interview_history 接上消息计数

**Files:**
- Modify: `src/services/interview_result_service.py:3742-3810`（`get_interview_history`）

**Interfaces:**
- Consumes: Task 1 的 `count_messages_by_role_for_thread_ids`、Task 2 的 `_build_history_record(..., message_counts=...)`
- Produces: `/api/interview/history` 每条 record 含 `question_count` / `answered_count`

本任务是把 Task 1 和 Task 2 接起来，改动只有 3 行，没有独立的单测切面（需要真实 DB），验证靠调用真实接口。

- [ ] **Step 1: 接上计数**

在 `get_interview_history` 中，`latest_assistant_messages_by_thread` 那次查询之后、`records: list[dict[str, Any]] = []` 之前，插入：

```python
    message_counts_by_thread = await conv_repo.count_messages_by_role_for_thread_ids(
        [conversation.thread_id for conversation in conversations]
    )
```

然后把循环里的 `_build_history_record` 调用（约第 3802 行）改成：

```python
        record = _build_history_record(
            conversation=conversation,
            result_payload=result_payload,
            message_counts=message_counts_by_thread.get(conversation.thread_id, {}),
        )
```

- [ ] **Step 2: 确认没有遗漏的调用点**

Run: `grep -rn "_build_history_record(" src/ server/ test/`
Expected: 只有 `src/services/interview_result_service.py` 的定义处与这一处调用，加上 Task 2 新增的两个测试。任何其它调用点都必须补 `message_counts=` 参数。

- [ ] **Step 3: 跑后端检查与相关测试**

Run: `make lint`
Expected: ruff check / format / isort 全通过

Run: `docker compose exec api uv run --group test pytest test/unit/test_interview_result_service.py test/test_conversation_repository.py -v`
Expected: PASS

- [ ] **Step 4: 真实接口验证**

确认容器在跑（`docker compose ps`），然后登录取 token 调接口：

```bash
docker compose logs api-dev --tail 20
curl -s -X POST http://localhost:5050/api/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$AI_INTERVIEW_SUPER_ADMIN_NAME&password=$AI_INTERVIEW_SUPER_ADMIN_PASSWORD" | head -c 400
```

拿到 `access_token` 后：

```bash
curl -s http://localhost:5050/api/interview/history \
  -H "Authorization: Bearer <token>" | python3 -m json.tool | head -60
```

Expected: `records[]` 中每项都含 `question_count` 与 `answered_count`，且为非负整数。若账号没有面试记录，`records` 为空数组也算通过（只要接口 200 且不报错）。

- [ ] **Step 5: 提交**

```bash
git add src/services/interview_result_service.py
git commit -m "feat(interview): get_interview_history 返回题数与回答数"
```

---

### Task 4: 前端 — 提取 decodeHtmlEntities 到共享 utils

**Files:**
- Create: `web/src/utils/html.js`
- Modify: `web/src/views/InterviewRecordsView.vue:208`（删掉本地定义，改为 import）

**Interfaces:**
- Produces: `export const decodeHtmlEntities = (value: string) => string`，从 `@/utils/html` 导出。Task 6 的工作台会 import 它。

后端返回的 `title` / `position` / `round` 含 HTML 实体（如 `&middot;`），两个页面都要解码。先提取，避免抄第二份。

- [ ] **Step 1: 建共享文件**

Create `web/src/utils/html.js`：

```js
export const decodeHtmlEntities = (value) => {
  const text = String(value || '')
  if (typeof window === 'undefined' || !text.includes('&')) return text
  const doc = new DOMParser().parseFromString(text, 'text/html')
  return doc.body.textContent || ''
}
```

- [ ] **Step 2: 改 InterviewRecordsView 引用**

删除 `web/src/views/InterviewRecordsView.vue:208` 这一整行（`const decodeHtmlEntities = (value) => {...}`），并在 script 的 import 区（`import { formatDateTime, parseToShanghai } from '@/utils/time'` 那行之后）加：

```js
import { decodeHtmlEntities } from '@/utils/html'
```

- [ ] **Step 3: 验证**

Run: `cd web && pnpm run lint`
Expected: 无 error（尤其无 `no-undef` / `no-unused-vars`）

Run: `cd web && pnpm run build`
Expected: 构建成功

- [ ] **Step 4: 提交**

```bash
git add web/src/utils/html.js web/src/views/InterviewRecordsView.vue
git commit -m "refactor(web): 提取 decodeHtmlEntities 到共享 utils"
```

---

### Task 5: 前端 — 新增 /interview 路由并重定向旧入口

**Files:**
- Modify: `web/src/router/index.js:30-72`
- Modify: `web/src/layouts/AppLayout.vue:95-106`
- Modify: `web/src/views/InterviewSessionView.vue:151,332`
- Modify: `web/src/views/VoiceInterviewView.vue:933,1182`
- Modify: `web/src/views/InterviewResultView.vue:800`
- Create: `web/src/views/InterviewWorkbenchView.vue`（本任务只建占位骨架，Task 6 填内容）

**Interfaces:**
- Produces: 路由名 `InterviewWorkbench`（路径 `/interview`）。Task 6 在这个组件里实现页面。

本任务先把路由骨架和所有引用改名一次做完，避免中间态跑不起来。

- [ ] **Step 1: 建占位视图**

Create `web/src/views/InterviewWorkbenchView.vue`：

```vue
<template>
  <div class="wb-root">面试工作台</div>
</template>

<script setup></script>

<style lang="less" scoped>
.wb-root {
  height: 100%;
  padding: 24px;
  color: var(--gray-1000);
}
</style>
```

- [ ] **Step 2: 改路由表**

在 `web/src/router/index.js` 中，把 `/agent` 下 `path: ''` 的那个子路由（第 34-38 行，`name: 'AgentComp'`）整体替换为：

```js
        {
          path: '',
          redirect: '/interview'
        },
```

**注意：`redirect` 必须写在这个 `path: ''` 子路由上。写到父级 `/agent` 会连带打掉 `interview` / `interview/voice` / `interview/code` / `interview/result` / `records` 全部子路由。**

然后在 `/agent` 这个顶层路由块之后、`/resume` 之前，插入新顶层路由：

```js
    {
      path: '/interview',
      name: 'interview',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'InterviewWorkbench',
          component: () => import('../views/InterviewWorkbenchView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
```

- [ ] **Step 3: 改 5 处路由名引用**

`web/src/layouts/AppLayout.vue` 第 96-97 行，「开始面试」项：`path: '/agent'` 改为 `path: '/interview'`；`matchNames` 数组里的 `'AgentComp'` 改为 `'InterviewWorkbench'`。

以下 5 处把 `name: 'AgentComp'` 改为 `name: 'InterviewWorkbench'`：

| 文件 | 行 | 场景 |
|---|---|---|
| `web/src/views/InterviewSessionView.vue` | 151 | `backToSetup()`「调整配置」 |
| `web/src/views/InterviewSessionView.vue` | 332 | `onMounted` 中无 `session` 且无 `threadId` 的兜底回跳 |
| `web/src/views/VoiceInterviewView.vue` | 933 | 语音版返回配置 |
| `web/src/views/VoiceInterviewView.vue` | 1182 | 语音版返回配置 |
| `web/src/views/InterviewResultView.vue` | 800 | 报告页返回配置 |

只改 `name` 的值，各处原有的 `query` 参数保持不变。

- [ ] **Step 4: 确认没有漏网的引用**

Run: `grep -rn "AgentComp'" web/src/ | grep -v "AgentInterviewComp\|AgentVoiceInterviewComp"`
Expected: 无输出。有任何一行残留都会在运行时抛路由解析错误。

- [ ] **Step 5: 验证**

Run: `cd web && pnpm run lint && pnpm run build`
Expected: 均成功

手工验证（`make start` 后开 http://localhost:5173）：
1. 访问 `/agent` → 自动跳到 `/interview`，显示占位文字「面试工作台」
2. 侧栏「开始面试」高亮，点击停留在 `/interview`
3. 访问 `/agent/records` → 仍是面试记录页（未被重定向误伤）

- [ ] **Step 6: 提交**

```bash
git add web/src/router/index.js web/src/layouts/AppLayout.vue \
  web/src/views/InterviewWorkbenchView.vue web/src/views/InterviewSessionView.vue \
  web/src/views/VoiceInterviewView.vue web/src/views/InterviewResultView.vue
git commit -m "feat(web): 新增 /interview 工作台路由并重定向旧配置页入口"
```

---

### Task 6: 前端 — 工作台数据层

**Files:**
- Modify: `web/src/views/InterviewWorkbenchView.vue`

**Interfaces:**
- Consumes: Task 3 的 `question_count` / `answered_count`、Task 4 的 `@/utils/html`
- Produces: 组件内的响应式数据与 computed，供 Task 7 的模板消费。关键名字（Task 7 会直接引用）：
  `loading`、`records`、`profile`、`chart`、`resumeOptions`、`knowledgeDatabases`、
  `selectedInterviewMode`、`selectedPosition`、`selectedRound`、`selectedResumeId`、
  `headerSummary`、`activeRecord`、`activeProgress`、`trendPoints`、`weakDimensions`、
  `recentRecords`、`matchedKnowledge`、`canStartInterview`、
  `startInterview()`、`continueInterview()`、`openRecord(record)`、`openExportRecords()`、`openResumeCenter()`

先把 `<script setup>` 写完并跑通（页面此时仍是占位模板，只验证无报错），Task 7 再写模板与样式。

- [ ] **Step 1: 写 script setup**

把 `web/src/views/InterviewWorkbenchView.vue` 的 `<script setup></script>` 替换为：

```vue
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

import { interviewHistoryApi } from '@/apis/interview_history'
import { learnApi } from '@/apis/learn_api'
import { resumeApi } from '@/apis/resume_api'
import { usePositionTypes } from '@/composables/usePositionTypes'
import { useUserStore } from '@/stores/user'
import { decodeHtmlEntities } from '@/utils/html'
import { normalizePositionType } from '@/utils/position_utils'
import { parseToShanghai } from '@/utils/time'

// 面试 agent 只有固定 6 步 todo，实际题量随对话浮动，接口没有「计划题量」。
// 这是一个展示约定，不是从数据推导出来的值。
const EXPECTED_QUESTION_COUNT = 8
// 与后端 interview_result_service.LOW_SCORE_THRESHOLD 对齐
const LOW_SCORE_THRESHOLD = 75

const router = useRouter()
const userStore = useUserStore()
const { positionTypes, positionTypeOptions, defaultPositionType, loadPositionTypes } = usePositionTypes()

const loading = ref(false)
const historyPayload = ref(null)
const resumeOptions = ref([])
const knowledgeDatabases = ref([])

const interviewModeOptions = [
  { label: '文本', value: 'text' },
  { label: '语音', value: 'voice' }
]
const roundOptions = [
  { label: '初试', value: '初试' },
  { label: '复试', value: '复试' },
  { label: 'HR', value: 'HR' }
]

const selectedInterviewMode = ref('text')
const selectedPosition = ref(defaultPositionType.value.label)
const selectedRound = ref('初试')
const selectedResumeId = ref(null)

const records = computed(() => historyPayload.value?.records || [])
const profile = computed(() => historyPayload.value?.profile || {})
const chart = computed(() => historyPayload.value?.chart || {})

const headerSummary = computed(() => {
  const total = records.value.length
  const reported = records.value.filter((item) => item.has_result).length
  const scores = records.value
    .map((item) => item.overall_score)
    .filter((score) => typeof score === 'number' && Number.isFinite(score))
  const average = scores.length ? Math.round(scores.reduce((sum, s) => sum + s, 0) / scores.length) : null
  return `${total} 场 · 已出报告 ${reported} 场 · 平均 ${average === null ? '—' : `${average} 分`}`
})

const activeRecord = computed(() => records.value.find((item) => item.status === 'in_progress') || null)

const formatDuration = (record) => {
  const start = parseToShanghai(record.created_at)
  const end = parseToShanghai(record.updated_at)
  if (!start || !end) return ''
  const minutes = Math.floor(end.diff(start, 'minute'))
  return minutes < 1 ? '不到 1 分钟' : `${minutes} 分钟`
}

const activeProgress = computed(() => {
  const record = activeRecord.value
  if (!record) return null
  const answered = Math.min(Number(record.answered_count || 0), EXPECTED_QUESTION_COUNT)
  return {
    answered,
    total: EXPECTED_QUESTION_COUNT,
    remaining: EXPECTED_QUESTION_COUNT - answered,
    duration: formatDuration(record)
  }
})

// 只有总分这条线，取最近 4 场
const trendPoints = computed(() => {
  const categories = chart.value.categories || []
  const overall = (chart.value.series || []).find((item) => item.key === 'overall')
  if (!overall) return []
  const points = categories
    .map((category, index) => ({ category, score: overall.data?.[index] }))
    .filter((item) => typeof item.score === 'number' && Number.isFinite(item.score))
  return points.slice(-4).map((item) => {
    const parsed = parseToShanghai(item.category)
    return { label: parsed ? parsed.format('MM/DD') : '', score: item.score }
  })
})

const weakDimensions = computed(() =>
  (profile.value.top_weakness_dimensions || []).slice(0, 3).map((item) => ({
    key: item.dimension_key,
    label: item.label,
    score: item.average_score,
    lowCount: item.low_score_count,
    isLow: Number(item.average_score) <= LOW_SCORE_THRESHOLD
  }))
)

const recentRecords = computed(() =>
  records.value.slice(0, 6).map((record) => {
    const parsed = parseToShanghai(record.updated_at || record.created_at)
    return {
      threadId: record.thread_id,
      title: `${record.position} · ${record.round}`,
      score: record.has_result ? record.overall_score : null,
      meta: [
        parsed ? parsed.format('MM/DD HH:mm') : '',
        record.interview_mode === 'voice' ? '语音' : '文本',
        `${record.question_count || 0} 题`
      ]
        .filter(Boolean)
        .join(' · '),
      raw: record
    }
  })
)

const currentPositionKey = computed(() => normalizePositionType(selectedPosition.value, positionTypes.value).key)

// 知识库按岗位自动挂载，这里只做展示：优先展示匹配当前岗位的，没有匹配则展示全部
const matchedKnowledge = computed(() => {
  const matched = knowledgeDatabases.value.filter((item) => {
    const position = String(item.position || '').trim()
    return !position || position === currentPositionKey.value || position === selectedPosition.value
  })
  const list = matched.length ? matched : knowledgeDatabases.value
  return {
    names: list.map((item) => item.name).filter(Boolean).join(' · '),
    fileCount: list.reduce((sum, item) => sum + Number(item.file_count || 0), 0)
  }
})

const canStartInterview = computed(() => Boolean(selectedResumeId.value))

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

const formatUpdatedAt = (value) => {
  const parsed = parseToShanghai(value)
  return parsed ? `更新于 ${parsed.format('M/D HH:mm')}` : ''
}

const startInterview = () => {
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  router.push({
    name: selectedInterviewMode.value === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode: selectedInterviewMode.value,
      position: selectedPosition.value,
      round: selectedRound.value,
      resumeId: String(selectedResumeId.value),
      session: `${Date.now()}`
    }
  })
}

const resumeRecord = (record) => {
  router.push({
    name: record.interview_mode === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode: record.interview_mode === 'voice' ? 'voice' : 'text',
      position: record.position,
      round: record.round,
      threadId: record.thread_id
    }
  })
}

const continueInterview = () => {
  if (!activeRecord.value) return
  resumeRecord(activeRecord.value)
}

const openRecord = (record) => {
  if (record.has_result) {
    router.push({
      name: 'InterviewResultPage',
      query: { threadId: record.thread_id, position: record.position, round: record.round }
    })
    return
  }
  resumeRecord(record)
}

const openExportRecords = () => router.push('/agent/records')
const openResumeCenter = () => router.push('/resume')

const loadResumes = async () => {
  const data = await resumeApi.getMyResumes()
  resumeOptions.value = Array.isArray(data?.resumes) ? data.resumes : []
  if (!resumeOptions.value.some((item) => item.id === selectedResumeId.value)) {
    selectedResumeId.value = resumeOptions.value[0]?.id || null
  }
}

const loadHistory = async () => {
  const payload = await interviewHistoryApi.getHistory({ userId: userStore.userId })
  historyPayload.value = {
    ...payload,
    records: (payload?.records || []).map((record) => ({
      ...record,
      title: decodeHtmlEntities(record.title),
      position: decodeHtmlEntities(record.position),
      round: decodeHtmlEntities(record.round)
    }))
  }
}

const loadKnowledgeDatabases = async () => {
  const data = await learnApi.getDatabases()
  knowledgeDatabases.value = Array.isArray(data?.databases) ? data.databases : []
}

onMounted(async () => {
  loading.value = true
  try {
    await loadPositionTypes()
    selectedPosition.value = normalizePositionType(selectedPosition.value, positionTypes.value).label
    await Promise.all([loadHistory(), loadResumes(), loadKnowledgeDatabases()])
  } catch (error) {
    message.error(error.message || '加载面试工作台数据失败')
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: 确认 normalizePositionType 返回值含 key**

Run: `grep -n "export const normalizePositionType" -A 20 web/src/utils/position_utils.js`
Expected: 返回的对象含 `key` 与 `label` 字段。若字段名不同，把 `currentPositionKey` 的 `.key` 改成实际字段名。

- [ ] **Step 3: 验证**

Run: `cd web && pnpm run lint && pnpm run build`
Expected: 均成功（模板还没用到这些变量，lint 可能报未使用——若报错，本步先跳过 lint，Task 7 写完模板后一并验证）

- [ ] **Step 4: 提交**

```bash
git add web/src/views/InterviewWorkbenchView.vue
git commit -m "feat(web): 面试工作台数据层"
```

---

### Task 7: 前端 — 工作台三栏模板与样式

**Files:**
- Modify: `web/src/views/InterviewWorkbenchView.vue`（`<template>` 与 `<style>`）

**Interfaces:**
- Consumes: Task 6 定义的全部 computed 与方法

- [ ] **Step 1: 写模板**

替换 `<template>` 整块：

```vue
<template>
  <div class="wb-root">
    <header class="wb-top">
      <div>
        <h1 class="wb-title">面试工作台</h1>
        <p class="wb-sub">{{ headerSummary }}</p>
      </div>
      <div class="wb-top-actions">
        <button class="wb-btn" type="button" @click="openExportRecords">导出记录</button>
        <button class="wb-btn wb-btn--primary" type="button" :disabled="!activeRecord" @click="continueInterview">
          继续面试
        </button>
      </div>
    </header>

    <div class="wb-grid">
      <!-- 左栏 · 新面试配置 -->
      <section class="wb-col wb-col--left">
        <div class="wb-lab">新面试配置</div>
        <div class="wb-config">
          <div class="wb-field">
            <div class="wb-lab">形式</div>
            <div class="wb-seg">
              <button
                v-for="item in interviewModeOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedInterviewMode === item.value }"
                @click="selectedInterviewMode = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">岗位</div>
            <div class="wb-seg wb-seg--wrap">
              <button
                v-for="item in positionTypeOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedPosition === item.value }"
                @click="selectedPosition = item.value"
              >
                {{ item.shortLabel }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">轮次</div>
            <div class="wb-seg">
              <button
                v-for="item in roundOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedRound === item.value }"
                @click="selectedRound = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">简历</div>
            <template v-if="resumeOptions.length">
              <button
                v-for="item in resumeOptions"
                :key="item.id"
                type="button"
                class="wb-opt wb-opt--block"
                :class="{ 'is-on': selectedResumeId === item.id }"
                @click="selectedResumeId = item.id"
              >
                <span class="wb-opt-title">{{ item.filename }}</span>
                <span class="wb-opt-meta">
                  {{ formatFileSize(item.file_size) }} · {{ formatUpdatedAt(item.updated_at || item.created_at) }}
                </span>
              </button>
            </template>
            <div v-else class="wb-empty">
              还没有已上传简历
              <button class="wb-link" type="button" @click="openResumeCenter">去上传</button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">出题知识库</div>
            <div class="wb-kb">
              <span class="wb-kb-name">{{ matchedKnowledge.names || '按岗位自动匹配' }}</span>
              <span v-if="matchedKnowledge.fileCount" class="wb-kb-count">{{ matchedKnowledge.fileCount }} 文件</span>
            </div>
          </div>

          <button class="wb-btn wb-btn--primary wb-btn--start" type="button" :disabled="!canStartInterview" @click="startInterview">
            开始面试
          </button>
        </div>
      </section>

      <!-- 中栏 · 主线 -->
      <section class="wb-col wb-col--main">
        <div v-if="activeRecord" class="wb-active" @click="continueInterview">
          <div class="wb-lab wb-lab--accent">进行中</div>
          <div class="wb-active-title">{{ activeRecord.position }} · {{ activeRecord.round }}</div>
          <div class="wb-active-meta">
            已回答 {{ activeProgress.answered }} / {{ activeProgress.total }} 题
            <template v-if="activeProgress.duration"> · 用时 {{ activeProgress.duration }}</template>
          </div>
          <div class="wb-bar">
            <div class="wb-bar-done" :style="{ flex: activeProgress.answered || 0.01 }"></div>
            <div class="wb-bar-rest" :style="{ flex: activeProgress.remaining || 0.01 }"></div>
          </div>
        </div>
        <div v-else class="wb-active wb-active--empty">
          <div class="wb-lab">进行中</div>
          <div class="wb-active-title wb-active-title--empty">还没有进行中的面试</div>
          <div class="wb-active-meta">在左侧选好岗位与简历，点「开始面试」即可开始一轮。</div>
        </div>

        <div class="wb-block">
          <div class="wb-lab">能力趋势 · 近 {{ trendPoints.length || 4 }} 场</div>
          <svg v-if="trendPoints.length >= 2" class="wb-chart" viewBox="0 0 560 200" preserveAspectRatio="none">
            <line x1="40" x2="550" y1="20" y2="20" class="wb-chart-grid" />
            <line x1="40" x2="550" y1="70" y2="70" class="wb-chart-grid" />
            <line x1="40" x2="550" y1="120" y2="120" class="wb-chart-grid" />
            <line x1="40" x2="550" y1="170" y2="170" class="wb-chart-axis" />
            <text x="30" y="24" text-anchor="end" class="wb-chart-tick">100</text>
            <text x="30" y="74" text-anchor="end" class="wb-chart-tick">75</text>
            <text x="30" y="124" text-anchor="end" class="wb-chart-tick">50</text>
            <polyline :points="trendPolyline" class="wb-chart-line" />
            <rect
              v-for="(point, index) in trendCoords"
              :key="`dot-${index}`"
              :x="point.x - 4"
              :y="point.y - 4"
              width="8"
              height="8"
              class="wb-chart-dot"
            />
            <text
              v-for="(point, index) in trendCoords"
              :key="`label-${index}`"
              :x="point.x"
              y="192"
              text-anchor="middle"
              class="wb-chart-label"
            >
              {{ point.label }}
            </text>
          </svg>
          <div v-else class="wb-empty">完成至少 2 场并生成报告后，这里会显示能力趋势。</div>
        </div>

        <div class="wb-block">
          <div class="wb-lab">反复偏弱</div>
          <div v-if="weakDimensions.length" class="wb-weak">
            <div v-for="item in weakDimensions" :key="item.key" class="wb-weak-cell">
              <div class="wb-weak-label">{{ item.label }}</div>
              <div class="wb-weak-score" :class="{ 'is-low': item.isLow }">{{ item.score }}</div>
              <div class="wb-weak-hint">低分 {{ item.lowCount }} 次</div>
            </div>
          </div>
          <div v-else class="wb-empty">还没有足够数据判断薄弱维度。</div>
        </div>
      </section>

      <!-- 右栏 · 最近记录 -->
      <section class="wb-col wb-col--right">
        <div class="wb-lab">最近记录</div>
        <div v-if="recentRecords.length" class="wb-records">
          <button
            v-for="item in recentRecords"
            :key="item.threadId"
            type="button"
            class="wb-record"
            @click="openRecord(item.raw)"
          >
            <div class="wb-record-hd">
              <span class="wb-record-title">{{ item.title }}</span>
              <span v-if="item.score !== null && item.score !== undefined" class="wb-record-score">
                {{ Math.round(item.score) }}
              </span>
              <span v-else class="wb-record-undone">未完成</span>
            </div>
            <div class="wb-record-meta">{{ item.meta }}</div>
          </button>
        </div>
        <div v-else class="wb-empty">还没有面试记录。</div>
      </section>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 补趋势图坐标 computed**

`trendPolyline` 与 `trendCoords` 在 Task 6 里还没定义。在 `<script setup>` 中 `trendPoints` 之后追加：

```js
// SVG viewBox 为 0 0 560 200：x 从 80 起、点距 150；y 轴 50 分→170，100 分→20
const trendCoords = computed(() =>
  trendPoints.value.map((point, index) => ({
    x: 80 + index * 150,
    y: 170 - ((Math.min(100, Math.max(50, point.score)) - 50) / 50) * 150,
    label: point.label
  }))
)

const trendPolyline = computed(() => trendCoords.value.map((point) => `${point.x},${point.y}`).join(' '))
```

- [ ] **Step 3: 写样式**

替换 `<style lang="less" scoped>` 整块：

```less
.wb-root {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--gray-1000);
}

.wb-top {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 2px solid var(--gray-1000);
}
.wb-title { margin: 0; font-size: 22px; font-weight: 800; }
.wb-sub { margin: 4px 0 0; font-size: 13px; color: var(--gray-600); }
.wb-top-actions { display: flex; gap: 12px; flex: 0 0 auto; }

.wb-btn {
  height: 34px;
  padding: 0 16px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-1000);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  &:disabled { color: var(--gray-500); cursor: not-allowed; }
}
.wb-btn--primary {
  border-color: var(--main-color);
  background: var(--main-color);
  color: #fff;
  &:disabled { border-color: var(--gray-200); background: var(--gray-100); color: var(--gray-500); }
}
.wb-btn--start { width: 100%; height: 46px; justify-content: flex-start; }

.wb-grid {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 340px 1fr 320px;
  min-height: 0;
}
.wb-col { padding: 24px; overflow-y: auto; min-width: 0; }
.wb-col--left, .wb-col--main { border-right: 1px solid var(--gray-100); }
.wb-col--main { display: flex; flex-direction: column; gap: 22px; }

.wb-lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}
.wb-lab--accent { color: var(--main-700); }

.wb-config { margin-top: 20px; display: flex; flex-direction: column; gap: 20px; }
.wb-field { display: flex; flex-direction: column; gap: 8px; }

.wb-seg { display: flex; }
.wb-seg--wrap { flex-wrap: wrap; }
.wb-opt {
  flex: 1;
  min-width: 0;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-700);
  font-size: 13px;
  cursor: pointer;
  &:not(:first-child) { border-left: none; }
  &.is-on { background: var(--gray-100); color: var(--gray-1000); font-weight: 700; }
}
.wb-opt--block {
  flex: none;
  height: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
  & + .wb-opt--block { border-top: none; border-left: 1px solid var(--gray-200); }
}
.wb-opt-title { font-size: 13px; word-break: break-all; }
.wb-opt-meta { font-size: 12px; color: var(--gray-600); font-weight: 400; }

.wb-kb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  font-size: 13px;
  color: var(--gray-700);
}
.wb-kb-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wb-kb-count { flex: 0 0 auto; font-size: 12px; color: var(--gray-500); }

.wb-empty { font-size: 13px; color: var(--gray-500); line-height: 1.7; }
.wb-link {
  border: none;
  background: none;
  padding: 0 0 0 6px;
  color: var(--main-color);
  font-size: 13px;
  cursor: pointer;
}

.wb-active {
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  padding: 22px 24px;
  cursor: pointer;
}
.wb-active--empty { cursor: default; }
.wb-active-title { font-size: 26px; font-weight: 800; margin: 10px 0 6px; }
.wb-active-title--empty { font-size: 18px; font-weight: 700; color: var(--gray-600); }
.wb-active-meta { font-size: 13px; color: var(--gray-600); }
.wb-bar { display: flex; gap: 2px; margin-top: 18px; }
.wb-bar-done { height: 8px; background: var(--main-color); }
.wb-bar-rest { height: 8px; background: var(--gray-100); }

.wb-block { display: flex; flex-direction: column; gap: 10px; }
.wb-chart { width: 100%; height: 210px; }
.wb-chart-grid { stroke: var(--gray-200); }
.wb-chart-axis { stroke: var(--gray-1000); stroke-width: 2; }
.wb-chart-tick, .wb-chart-label { font-size: 11px; fill: var(--gray-500); }
.wb-chart-label { fill: var(--gray-600); }
.wb-chart-line { fill: none; stroke: var(--main-color); stroke-width: 2; }
.wb-chart-dot { fill: var(--main-color); }

.wb-weak {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--gray-200);
}
.wb-weak-cell {
  padding: 14px 16px;
  &:not(:last-child) { border-right: 1px solid var(--gray-100); }
  &:first-child { padding-left: 0; }
  &:last-child { padding-right: 0; }
}
.wb-weak-label { font-size: 13px; color: var(--gray-600); }
.wb-weak-score { font-size: 28px; font-weight: 800; margin-top: 4px; }
.wb-weak-score.is-low { color: var(--main-color); }
.wb-weak-hint { font-size: 12px; color: var(--gray-500); }

.wb-records { display: flex; flex-direction: column; margin-top: 14px; }
.wb-record {
  width: 100%;
  padding: 14px 0;
  border: none;
  border-top: 1px solid var(--gray-100);
  background: none;
  text-align: left;
  cursor: pointer;
  &:first-child { border-top-color: var(--gray-200); }
}
.wb-record-hd { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.wb-record-title { font-size: 15px; font-weight: 700; color: var(--gray-1000); }
.wb-record-score { font-size: 19px; font-weight: 800; color: var(--gray-1000); }
.wb-record-undone { font-size: 13px; color: var(--gray-500); }
.wb-record-meta { font-size: 12px; color: var(--gray-500); margin-top: 5px; }
</style>
```

- [ ] **Step 4: 验证构建与规范**

Run: `cd web && pnpm run lint && pnpm run build`
Expected: 均成功

Run: `grep -nE "border-radius:\s*[1-9]|box-shadow|linear-gradient|translateY|translateX|#[0-9a-fA-F]{3,6}" web/src/views/InterviewWorkbenchView.vue`
Expected: 只有 `.wb-btn--primary` 里的 `color: #fff`（主按钮文字，无对应变量）。其余任何命中都违反全局约束，必须改成 CSS 变量。

- [ ] **Step 5: 手工验收**

`make start` 后开 http://localhost:5173/interview，窗口调到 1600×900：

1. 三栏无横向滚动、无内容裁切
2. 切换形式/岗位/轮次，选中态是 `--gray-100` 底 + 加粗，相邻项之间只有 1px 线（不是 2px）
3. 选简历后「开始面试」可点，点击进入面试页并真正发起面试
4. 有进行中会话时中栏显示进行中卡片；无则显示「还没有进行中的面试」
5. 最近记录：已出报告的行点击进报告页，「未完成」的行点击进续面
6. `/settings` 或主题开关切到暗色，页面文字/分隔线/卡片底色均正常，无不可读区域

- [ ] **Step 6: 提交**

```bash
git add web/src/views/InterviewWorkbenchView.vue
git commit -m "feat(web): 面试工作台三栏布局与样式"
```

---

### Task 8: 收尾 — 全量检查与 issue 留言

**Files:** 无代码改动（除非前几步验证暴露问题）

- [ ] **Step 1: 全量后端检查**

Run: `make lint`
Expected: 通过

Run: `docker compose exec api uv run --group test pytest test/unit/test_interview_result_service.py test/test_conversation_repository.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 全量前端检查**

Run: `cd web && pnpm run lint && pnpm run build`
Expected: 均成功

- [ ] **Step 3: 确认无残留路由引用**

Run: `grep -rn "AgentComp'" web/src/ | grep -v "AgentInterviewComp\|AgentVoiceInterviewComp"`
Expected: 无输出

- [ ] **Step 4: 逐条核对 issue 验收标准**

- [ ] 1600×900 下三栏不出现横向滚动、不裁切内容
- [ ] 配置项交互（切换形式/岗位/轮次、选简历、选知识库）可用并能真正发起面试 —— 知识库为只读展示，需在 issue 留言说明原因
- [ ] 有进行中会话时中栏显示进行中卡片，无则显示空态
- [ ] 亮/暗色主题均正常

- [ ] **Step 5: 在 issue #2 下留言说明两处设计决策**

```bash
gh issue comment 2 --repo HEU-OpenWings/AI-Interview --body "$(cat <<'EOF'
实现补充说明（数据来源确认）：

**已确认有接口支持**
- 能力趋势：`/api/interview/history` 的 `chart.series` 中 `key === "overall"`，取最近 4 场
- 反复偏弱：同接口的 `profile.top_weakness_dimensions`，低分判定阈值对齐后端 `LOW_SCORE_THRESHOLD = 75`

**需要补接口的**
- 题数：原接口不返回。已在 `_build_history_record` 补 `question_count`（assistant 消息数）与 `answered_count`（user 消息数 − 1，扣掉自动注入的开场 prompt），底层是一次 `GROUP BY` 聚合，无 N+1

**两处设计判断**
1. 进度条分母「8」没有真实数据来源——面试 agent 只有固定 6 步 todo，实际题量随对话浮动。采用前端常量 `EXPECTED_QUESTION_COUNT = 8`（预计题量），是展示约定而非推导值
2. 「出题知识库」做成**只读展示**而非选择器：后端按岗位自动挂载知识库，前端没有可写入口，做成可点选择器会是假交互。当前显示匹配岗位的知识库名与文件数合计
EOF
)"
```

- [ ] **Step 6: 推分支并开 PR**

```bash
git push -u origin feat/ui3-interview-workbench
gh pr create --repo HEU-OpenWings/AI-Interview \
  --title "feat(web): UI v3 面试工作台（closes #2）" \
  --body "$(cat <<'EOF'
## 变更

按 `templates/新版界面 v3.dc.html` 锚点 `#2a` 新建面试工作台，把「配置 / 主线 / 记录」收进一屏。

- 新增路由 `/interview` → `InterviewWorkbenchView.vue`；`/agent` 空路径子路由重定向过来，其余 `/agent/*` 子路由不受影响
- 路由名 `AgentComp` 删除，5 处引用改为 `InterviewWorkbench`
- 后端 `/api/interview/history` 每条记录补 `question_count` / `answered_count`
- `decodeHtmlEntities` 提取到 `web/src/utils/html.js`

## 设计判断

- 进度条分母用前端常量 `EXPECTED_QUESTION_COUNT = 8`（接口无「计划题量」）
- 「出题知识库」为只读展示（后端按岗位自动挂载，前端无可写入口）

详见 issue #2 下的补充说明与 `docs/superpowers/specs/2026-08-12-ui3-interview-workbench-design.md`。

Closes #2

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

### Task 9: 前端 — 按更新后的 2a 设计稿重做工作台（开始面试）

设计稿 `templates/新版界面 v3.dc.html` 锚点 `#2a` 被重做。页面从「面试工作台」收窄为「开始面试」：右栏删除、中栏整体替换。设计修订记录见 `docs/superpowers/specs/2026-08-12-ui3-interview-workbench-design.md` 的「修订 · 2026-08-12」一节。

**Files:**
- Modify: `web/src/views/InterviewWorkbenchView.vue`（`<script setup>` / `<template>` / `<style>` 三块都要改）

**Interfaces:**
- Consumes: `question_count` / `answered_count`（Task 1-3，尚未落地，读到 `undefined` 时由 `|| 0` 兜底）
- Produces: 无下游任务

- [ ] **Step 1: 删除被移除模块的数据层**

在 `<script setup>` 中删除这些已经没有消费者的定义：`LOW_SCORE_THRESHOLD` 常量、`trendPoints`、`trendCoords`、`trendPolyline`、`weakDimensions`、`recentRecords`、`openRecord`。

`chart` 与 `profile` 两个 computed 也一并删除（趋势图和偏弱是它们唯二的消费者）。`historyPayload` 保留，`records` 保留。

- [ ] **Step 2: 改写顶栏摘要并新增本任务需要的 computed 与方法**

把现有的 `headerSummary` 整个替换为下面这段，并把 `activeProgress` 也替换为带 `questionCount` 的版本。`activeRecord` 保持不变。

```js
const lastRecord = computed(() => records.value[0] || null)

const lastScoredRecord = computed(
  () =>
    records.value.find((item) => item.has_result && typeof item.overall_score === 'number') || null
)

const headerSummary = computed(() => {
  const scoreText = lastScoredRecord.value
    ? `上次得分 ${Math.round(lastScoredRecord.value.overall_score)}`
    : ''
  if (activeRecord.value) {
    return scoreText ? `有一场未结束的面试 · ${scoreText}` : '有一场未结束的面试'
  }
  return scoreText || '还没有面试记录'
})

const activeProgress = computed(() => {
  const record = activeRecord.value
  if (!record) return null
  const answered = Math.min(Number(record.answered_count || 0), EXPECTED_QUESTION_COUNT)
  return {
    answered,
    total: EXPECTED_QUESTION_COUNT,
    remaining: EXPECTED_QUESTION_COUNT - answered,
    questionCount: Number(record.question_count || 0),
    duration: formatDuration(record)
  }
})

const selectedResume = computed(
  () => resumeOptions.value.find((item) => item.id === selectedResumeId.value) || null
)

const preflightChecks = computed(() => {
  const resume = selectedResume.value
  let resumeState = { text: '未选择', ready: false }
  if (resume?.summary_status === 'completed') {
    resumeState = { text: '就绪', ready: true }
  } else if (resume?.summary_status === 'failed') {
    resumeState = { text: '解析失败', ready: false }
  } else if (resume) {
    resumeState = { text: '解析中', ready: false }
  }

  const fileCount = matchedKnowledge.value.fileCount
  return [
    { key: 'resume', label: '简历已解析完成，项目经历可被追问', ...resumeState },
    {
      key: 'knowledge',
      label: fileCount
        ? `出题知识库 ${matchedKnowledge.value.names} 已索引 ${fileCount} 个文件`
        : '出题知识库尚未配置',
      text: fileCount ? '就绪' : '未配置',
      ready: Boolean(fileCount)
    },
    { key: 'mic', label: '语音面试需要麦克风权限', text: '选语音时再申请', ready: false }
  ]
})
```

把 `openExportRecords` 重命名为 `openRecords`（按钮文案由「导出记录」改为「面试记录」，跳转目标不变）：

```js
const openRecords = () => router.push('/agent/records')
```

新增三个动作。`pushInterview` 抽出来是因为下面三处发起面试只有参数不同：

```js
const pushInterview = ({ mode, position, round }) => {
  router.push({
    name: mode === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode,
      position,
      round,
      resumeId: String(selectedResumeId.value),
      session: `${Date.now()}`
    }
  })
}

const finishAndReport = () => {
  const record = activeRecord.value
  if (!record) return
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: record.thread_id,
      position: record.position,
      round: record.round,
      autoGenerate: '1'
    }
  })
}

const runQuickStart = (card) => {
  if (card.disabled) return
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  pushInterview(card.config)
}
```

把已有的 `startInterview` 改为复用 `pushInterview`（行为不变）：

```js
const startInterview = () => {
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  pushInterview({
    mode: selectedInterviewMode.value,
    position: selectedPosition.value,
    round: selectedRound.value
  })
}
```

最后新增四张快速开始卡。`按弱项出题` 与 `纯编程考核` 后端能力不存在（面试 agent 无限定话题入参；无用户发起纯编程会话的入口），按设计稿完整渲染但禁用：

```js
const quickStartCards = computed(() => [
  {
    key: 'reuse',
    title: '沿用上次配置',
    badge: lastRecord.value
      ? `${lastRecord.value.interview_mode === 'voice' ? '语音' : '文本'} · ${lastRecord.value.question_count || 0} 题`
      : '暂无记录',
    accent: false,
    desc: lastRecord.value
      ? `${lastRecord.value.position} · ${lastRecord.value.round} · ${selectedResume.value?.filename || '未选择简历'}`
      : '完成一场面试后，这里会带出上次的岗位与轮次',
    disabled: !lastRecord.value,
    config: lastRecord.value
      ? {
          mode: lastRecord.value.interview_mode === 'voice' ? 'voice' : 'text',
          position: lastRecord.value.position,
          round: lastRecord.value.round
        }
      : null
  },
  {
    key: 'weakness',
    title: '按弱项出题',
    badge: '即将上线',
    accent: true,
    desc: '只问你反复失分的知识点',
    disabled: true,
    config: null
  },
  {
    key: 'voice',
    title: '语音复试',
    badge: '语音 · 复试',
    accent: false,
    desc: '带摄像头，练表达节奏与追问应对',
    disabled: false,
    config: { mode: 'voice', position: selectedPosition.value, round: '复试' }
  },
  {
    key: 'coding',
    title: '纯编程考核',
    badge: '即将上线',
    accent: false,
    desc: '跳过问答，直接做题并判题',
    disabled: true,
    config: null
  }
])
```

- [ ] **Step 3: 替换模板**

`<template>` 整块替换：

```vue
<template>
  <div class="wb-root">
    <header class="wb-top">
      <div>
        <h1 class="wb-title">开始面试</h1>
        <p class="wb-sub">{{ headerSummary }}</p>
      </div>
      <div class="wb-top-actions">
        <button class="wb-btn" type="button" @click="openRecords">面试记录</button>
        <button
          class="wb-btn wb-btn--primary"
          type="button"
          :disabled="!activeRecord"
          @click="continueInterview"
        >
          继续未结束的面试
        </button>
      </div>
    </header>

    <div class="wb-grid">
      <!-- 左栏 · 新面试配置 -->
      <section class="wb-col wb-col--left">
        <div class="wb-lab">新面试配置</div>
        <div class="wb-config">
          <div class="wb-field">
            <div class="wb-lab">形式</div>
            <div class="wb-seg">
              <button
                v-for="item in interviewModeOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedInterviewMode === item.value }"
                @click="selectedInterviewMode = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">岗位</div>
            <div class="wb-seg wb-seg--wrap">
              <button
                v-for="item in positionTypeOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedPosition === item.value }"
                @click="selectedPosition = item.value"
              >
                {{ item.shortLabel }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">轮次</div>
            <div class="wb-seg">
              <button
                v-for="item in roundOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedRound === item.value }"
                @click="selectedRound = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">简历</div>
            <template v-if="resumeOptions.length">
              <button
                v-for="item in resumeOptions"
                :key="item.id"
                type="button"
                class="wb-opt wb-opt--block"
                :class="{ 'is-on': selectedResumeId === item.id }"
                @click="selectedResumeId = item.id"
              >
                <span class="wb-opt-title">{{ item.filename }}</span>
                <span class="wb-opt-meta">
                  {{ formatFileSize(item.file_size) }} · {{ formatUpdatedAt(item.updated_at || item.created_at) }}
                </span>
              </button>
            </template>
            <div v-else class="wb-empty">
              还没有已上传简历
              <button class="wb-link" type="button" @click="openResumeCenter">去上传</button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">出题知识库</div>
            <div class="wb-kb">
              <span class="wb-kb-name">{{ matchedKnowledge.names || '按岗位自动匹配' }}</span>
              <span v-if="matchedKnowledge.fileCount" class="wb-kb-count">{{ matchedKnowledge.fileCount }} 文件</span>
            </div>
          </div>

          <button
            class="wb-btn wb-btn--primary wb-btn--start"
            type="button"
            :disabled="!canStartInterview"
            @click="startInterview"
          >
            开始面试
          </button>
        </div>
      </section>

      <!-- 右栏 · 主线 -->
      <section class="wb-col wb-col--main">
        <div v-if="activeRecord" class="wb-active">
          <div class="wb-active-info">
            <div class="wb-lab wb-lab--accent">未结束</div>
            <div class="wb-active-title">{{ activeRecord.position }} · {{ activeRecord.round }}</div>
            <div class="wb-active-meta">
              <template v-if="activeProgress.questionCount">停在第 {{ activeProgress.questionCount }} 问 · </template>
              已答 {{ activeProgress.answered }} / {{ activeProgress.total }} 题
              <template v-if="activeProgress.duration"> · 用时 {{ activeProgress.duration }}</template>
            </div>
            <div class="wb-bar">
              <div class="wb-bar-done" :style="{ flex: activeProgress.answered || 0.01 }"></div>
              <div class="wb-bar-rest" :style="{ flex: activeProgress.remaining || 0.01 }"></div>
            </div>
          </div>
          <div class="wb-active-actions">
            <button class="wb-btn wb-btn--primary" type="button" @click="continueInterview">继续面试</button>
            <button class="wb-btn" type="button" @click="finishAndReport">直接结束并出报告</button>
          </div>
        </div>
        <div v-else class="wb-active wb-active--empty">
          <div class="wb-active-info">
            <div class="wb-lab">未结束</div>
            <div class="wb-active-title wb-active-title--empty">没有未结束的面试</div>
            <div class="wb-active-meta">在左侧选好岗位与简历，或从下面的快速开始直接进入。</div>
          </div>
        </div>

        <div class="wb-block">
          <div class="wb-block-hd">
            <span class="wb-lab">快速开始</span>
            <span class="wb-block-hint">选一个直接进面试，不用改左边的配置</span>
          </div>
          <div class="wb-quick">
            <button
              v-for="card in quickStartCards"
              :key="card.key"
              type="button"
              class="wb-quick-card"
              :class="{ 'is-disabled': card.disabled }"
              :disabled="card.disabled"
              @click="runQuickStart(card)"
            >
              <div class="wb-quick-hd">
                <span class="wb-quick-title">{{ card.title }}</span>
                <span class="wb-badge" :class="{ 'is-accent': card.accent }">{{ card.badge }}</span>
              </div>
              <div class="wb-quick-desc">{{ card.desc }}</div>
            </button>
          </div>
        </div>

        <div class="wb-block">
          <div class="wb-lab">面试前检查</div>
          <div class="wb-check">
            <div v-for="item in preflightChecks" :key="item.key" class="wb-check-row">
              <span class="wb-check-label">{{ item.label }}</span>
              <span class="wb-check-state" :class="{ 'is-ready': item.ready }">{{ item.text }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
```

- [ ] **Step 4: 替换样式**

`<style lang="less" scoped>` 整块替换：

```less
.wb-root {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--gray-1000);
}

.wb-top {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 2px solid var(--gray-1000);
}
.wb-title { margin: 0; font-size: 22px; font-weight: 800; }
.wb-sub { margin: 4px 0 0; font-size: 13px; color: var(--gray-600); }
.wb-top-actions { display: flex; gap: 12px; flex: 0 0 auto; }

.wb-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-700);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  &:disabled { color: var(--gray-500); cursor: not-allowed; }
}
.wb-btn--primary {
  border-color: var(--main-color);
  background: var(--main-color);
  color: #fff;
  &:disabled { border-color: var(--gray-200); background: var(--gray-100); color: var(--gray-500); }
}
.wb-btn--start { width: 100%; height: 46px; }

.wb-grid {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 340px 1fr;
  min-height: 0;
}
.wb-col { overflow-y: auto; min-width: 0; }
.wb-col--left { padding: 24px; border-right: 1px solid var(--gray-100); }
.wb-col--main { padding: 24px 32px; display: flex; flex-direction: column; gap: 26px; }

.wb-lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}
.wb-lab--accent { color: var(--main-700); }

.wb-config { margin-top: 20px; display: flex; flex-direction: column; gap: 20px; }
.wb-field { display: flex; flex-direction: column; gap: 8px; }

.wb-seg { display: flex; }
.wb-seg--wrap { flex-wrap: wrap; }
.wb-opt {
  flex: 1;
  min-width: 0;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-700);
  font-size: 13px;
  cursor: pointer;
  &:not(:first-child) { border-left: none; }
  &.is-on { background: var(--gray-100); color: var(--gray-1000); font-weight: 700; }
}
.wb-opt--block {
  flex: none;
  height: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
  & + .wb-opt--block { border-top: none; border-left: 1px solid var(--gray-200); }
}
.wb-opt-title { font-size: 13px; word-break: break-all; }
.wb-opt-meta { font-size: 12px; color: var(--gray-600); font-weight: 400; }

.wb-kb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  font-size: 13px;
  color: var(--gray-700);
}
.wb-kb-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wb-kb-count { flex: 0 0 auto; font-size: 12px; color: var(--gray-500); }

.wb-empty { font-size: 13px; color: var(--gray-500); line-height: 1.7; }
.wb-link {
  border: none;
  background: none;
  padding: 0 0 0 6px;
  color: var(--gray-1000);
  text-decoration: underline;
  font-size: 13px;
  cursor: pointer;
}

.wb-active {
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  padding: 24px 26px;
  display: flex;
  align-items: center;
  gap: 28px;
}
.wb-active-info { flex: 1; min-width: 0; }
.wb-active-actions { display: flex; flex-direction: column; gap: 10px; flex: 0 0 auto; }
.wb-active-title { font-size: 26px; font-weight: 800; margin: 10px 0 6px; }
.wb-active-title--empty { font-size: 18px; font-weight: 700; color: var(--gray-600); }
.wb-active-meta { font-size: 13px; color: var(--gray-600); }
.wb-bar { display: flex; gap: 2px; margin-top: 16px; max-width: 420px; }
.wb-bar-done { height: 8px; background: var(--main-color); }
.wb-bar-rest { height: 8px; background: var(--gray-100); }

.wb-block { display: flex; flex-direction: column; gap: 10px; }
.wb-block-hd { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.wb-block-hint { font-size: 12px; color: var(--gray-500); }

.wb-quick {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 1px solid var(--gray-200);
  margin-top: 2px;
}
.wb-quick-card {
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  padding: 18px 24px 18px 0;
  &:nth-child(odd) { border-right: 1px solid var(--gray-100); }
  &:nth-child(even) { padding: 18px 0 18px 24px; }
  &:nth-child(1),
  &:nth-child(2) { border-bottom: 1px solid var(--gray-100); }
  &.is-disabled { cursor: not-allowed; }
  &.is-disabled .wb-quick-title,
  &.is-disabled .wb-quick-desc { color: var(--gray-500); }
}
.wb-quick-hd { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.wb-quick-title { font-size: 16px; font-weight: 700; color: var(--gray-1000); }
.wb-quick-desc { font-size: 13px; color: var(--gray-600); margin-top: 7px; line-height: 1.6; }

.wb-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--gray-200);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--gray-600);
  flex: 0 0 auto;
  &.is-accent { border-color: var(--main-color); color: var(--main-700); }
}

.wb-check { font-size: 13px; line-height: 1.6; }
.wb-check-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 0;
  border-top: 1px solid var(--gray-100);
}
.wb-check-label { color: var(--gray-1000); }
.wb-check-state { flex: 0 0 auto; color: var(--gray-500); }
.wb-check-state.is-ready { color: var(--main-700); font-weight: 700; }
</style>
```

- [ ] **Step 5: 验证**

Run: `cd /home/fzb/code/AI-Interview/web && pnpm run lint`
Expected: `InterviewWorkbenchView.vue` 零 error。**特别确认没有 `no-unused-vars`** —— 有的话说明 Step 1 有该删没删的定义，或模板漏用了某个变量。

Run: `cd /home/fzb/code/AI-Interview/web && pnpm run build`
Expected: 成功

Run: `grep -nE "border-radius:\s*[1-9]|box-shadow|linear-gradient|translateY|translateX|#[0-9a-fA-F]{3,6}" web/src/views/InterviewWorkbenchView.vue`
Expected: 只有 `.wb-btn--primary` 的 `color: #fff`

Run: `grep -n "trendPoints\|trendCoords\|trendPolyline\|weakDimensions\|recentRecords\|openExportRecords\|LOW_SCORE_THRESHOLD" web/src/views/InterviewWorkbenchView.vue`
Expected: 无输出（全部已删除）

- [ ] **Step 6: 提交**

```bash
git add web/src/views/InterviewWorkbenchView.vue
git commit -m "feat(web): 工作台按更新后的 2a 设计稿重做为「开始面试」"
```
