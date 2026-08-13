# UI v3 · 面试工作台设计（Issue #2 / 锚点 2a）

## 背景与目标

当前候选人主线被拆成四个互相跳转的路由：配置（`/agent`）→ 进行中（`/agent/interview`）→ 编程（`/agent/interview/code`）→ 报告（`/agent/interview/result`）。用户每一步都要离开上一屏，看不到自己的整体进度。

本设计新建**面试工作台**页面，把「配置」收进一个常驻左栏，把「主线状态 + 能力趋势」放中栏，把「历史记录」放右栏，让候选人在一屏内决定下一步做什么。这是 v3 信息架构的第一屏。

设计稿：`templates/新版界面 v3.dc.html` 锚点 `#2a`。

## 范围

**在范围内**：新建工作台页面、新增路由、旧配置页入口重定向、后端补两个历史记录字段。

**不在范围内**：面试进行中页（`#2b`）、编程页（`#2c`）、报告页（`#2d`）的改造——各自有独立 issue。侧边栏与色板已在 `feat/rail-sidebar-redesign` 完成，本设计不动。

## 一、路由与入口

新增：

```js
{ path: '/interview', name: 'interview', component: AppLayout, children: [
  { path: '', name: 'InterviewWorkbench',
    component: () => import('../views/InterviewWorkbenchView.vue'),
    meta: { keepAlive: false, requiresAuth: true } }
]}
```

旧配置页入口重定向。**`redirect` 写在 `path: ''` 这个子路由上**，写到父级 `/agent` 会连带打掉所有子路由：

```js
{ path: '/agent', name: 'AgentMain', component: AppLayout, children: [
  { path: '', redirect: '/interview' },              // 原 AgentComp
  { path: 'interview', name: 'AgentInterviewComp', ... },       // 不动
  { path: 'interview/voice', name: 'AgentVoiceInterviewComp', ... },  // 不动
  { path: 'interview/code', ... }, { path: 'interview/result', ... },
  { path: 'records', ... }, { path: ':agent_id', redirect: '/agent' },
]}
```

`AgentView.vue` 文件保留不删（其它 issue 分支可能仍在引用），仅失去路由入口，后续统一清理。

路由名 `AgentComp` 消失后，以下 6 处引用必须同步改为 `InterviewWorkbench`，漏改会在运行时抛路由解析错误：

| 文件 | 行 | 场景 |
|---|---|---|
| `web/src/views/InterviewSessionView.vue` | 151 | 「调整配置」按钮 |
| `web/src/views/InterviewSessionView.vue` | 332 | 无 `session` 且无 `threadId` 时的兜底回跳（最关键） |
| `web/src/views/VoiceInterviewView.vue` | 933 | 同上语音版 |
| `web/src/views/VoiceInterviewView.vue` | 1182 | 同上语音版 |
| `web/src/views/InterviewResultView.vue` | 800 | 报告页返回配置 |
| `web/src/layouts/AppLayout.vue` | 100 | 侧栏「开始面试」`matchNames` |

侧栏「开始面试」的 `path` 由 `/agent` 改为 `/interview`，`matchNames` 中 `AgentComp` 换成 `InterviewWorkbench`。

「开始面试」的跳转目标不变：文本 → `AgentInterviewComp`，语音 → `AgentVoiceInterviewComp`，query 与现有 `AgentView.startInterview` 完全一致（`mode` / `position` / `round` / `resumeId` / `session`）。

## 二、后端改动

`/api/interview/history` 目前不返回题数，工作台的「已回答 N 题」与最近记录的「N 题」都依赖它。补两个字段：

1. `ConversationRepository` 新增：

```python
async def count_messages_by_role_for_thread_ids(
    self, thread_ids: list[str]
) -> dict[str, dict[str, int]]
```

一条 `GROUP BY Conversation.thread_id, Message.role` 聚合查询，返回 `{thread_id: {"user": n, "assistant": m}}`。空入参直接返回 `{}`（与同文件 `get_latest_assistant_messages_by_thread_ids` 的写法保持一致）。

2. `_build_history_record` 增加入参 `message_counts: dict[str, int]`，输出两个字段：

- `question_count` = assistant 消息数——面试官发言轮次，用作最近记录的「N 题」
- `answered_count` = `max(0, user 消息数 - 1)`——扣掉 `maybeStartInterview` 自动注入的开场 prompt（它是一条 user 消息，不是候选人的回答）

3. `get_interview_history` 在已有的 `conversations` 循环外，对全部 `thread_id` 调用一次上述聚合，逐条传给 `_build_history_record`。无 N+1。

`_build_history_chart` / `_build_history_profile` 不受影响，新字段不参与打分。

## 三、页面布局

`InterviewWorkbenchView.vue`。根容器 `height: 100%; display: flex; flex-direction: column; overflow: hidden`（`AppLayout` 的 `.app-router-view` 已经是 `height:100%; overflow-y:auto`，工作台自己接管滚动，三栏各自 `overflow-y: auto`）。

顶栏：标题「面试工作台」+ 副标题 + 右侧 `导出记录` / `继续面试` 两个按钮。

内容区 `display: grid; grid-template-columns: 340px 1fr 320px; min-height: 0`。

### 数据映射

| 区域 | 数据源 |
|---|---|
| 顶栏副标题 `N 场 · 已出报告 M 场 · 平均 X 分` | `records.length` / `has_result` 计数 / 有 `overall_score` 的记录均值（无则显示 `—`） |
| 左栏 形式 / 岗位 / 轮次 / 简历 | `usePositionTypes` + `resumeApi.getMyResumes()`，逻辑照搬 `AgentView.vue` |
| 左栏 出题知识库 | `learnApi.getDatabases()`，按当前岗位过滤，显示 `名称 · 名称` + 文件数合计 |
| 中栏 进行中卡片 | `records.find(r => r.status === 'in_progress')` |
| 中栏 能力趋势 | `chart.categories` + `chart.series` 中 `key === 'overall'`，取最后 4 点 |
| 中栏 反复偏弱 | `profile.top_weakness_dimensions` 前 3 项 |
| 右栏 最近记录 | `records.slice(0, 6)` |

`records` 的 `title` / `position` / `round` 含 HTML 实体，沿用 `InterviewRecordsView.vue` 的 `decodeHtmlEntities` 处理（提取到 `web/src/utils/` 复用，避免两处各写一遍）。

### 左栏 · 新面试配置

三组分段选择器（形式 文本/语音、岗位、轮次 初试/复试/HR）：相邻项 `border-left: none` 拼接，选中态 `--gray-100` 底 + 加粗。岗位来自 `positionTypeOptions`，超过 2 项时按 grid 自动换行，不强行塞成一行。

简历项：文件名 + `大小 · 更新于 M/D HH:mm` 两行。复用 `AgentView` 的 `formatFileSize`。无简历时显示「还没有已上传简历」+ 跳 `/resume`。

出题知识库项：**只读展示**，不是选择器。后端按岗位自动挂载知识库，前端没有可写入口；做成可点的选择器会是假交互。显示当前岗位匹配到的知识库名与文件数合计，无匹配时显示「按岗位自动匹配」。

底部 46px 高主按钮「开始面试」，未选简历时禁用。

### 中栏 · 主线

进行中卡片：`--gray-200` 边框 + `--gray-25` 底；「进行中」小标签用深蓝 `--main-700`；岗位轮次 26px 大字；`已回答 N / 8 题 · 用时 M 分钟`；两段式进度条。

**进度条分母**：任何接口都没有真实的「计划题量」——面试 agent 只有固定 6 步 todo，实际题量随对话浮动。采用 UI 常量 `EXPECTED_QUESTION_COUNT = 8`（预计题量），`N` 取 `min(answered_count, 8)`，进度 `N / 8`。这是一个明确的展示约定，不是从数据推导出来的值，需在 issue 下留言说明。

用时 = `updated_at - created_at`，向下取整到分钟，不足 1 分钟显示「不到 1 分钟」。

无进行中会话时显示空态：「还没有进行中的面试」+ 一句引导。

能力趋势：手写 SVG 折线（`viewBox="0 0 560 200"`），方块数据点，横轴日期。不引 echarts——只有 4 个点的单条折线，引图表库不划算，且 echarts 的默认样式与零圆角规范冲突。少于 2 个点时显示空态（一个点连不成趋势）。

反复偏弱：三格，`标签 / 分数 / 低分 N 次`。分数 `<= 75`（对齐后端 `LOW_SCORE_THRESHOLD = 75`）时用 `--main-color`，否则墨色。无数据时空态。

### 右栏 · 最近记录

6 行，行间 1px `--gray-100` 分隔（首行 `--gray-200`）。第一行「岗位 · 轮次」+ 右侧分数；`has_result` 为 false 时右侧显示灰色「未完成」文字而非分数。第二行 `M/D HH:mm · 文本|语音 · question_count 题`。

## 四、交互

- 「继续面试」按钮 / 进行中卡片点击 → 进行中会话的 `AgentInterviewComp`（`interview_mode === 'voice'` 则 `AgentVoiceInterviewComp`），带 `threadId` / `position` / `round`。无进行中会话时「继续面试」禁用。
- 最近记录行点击：`has_result` → `InterviewResultPage`；否则 → 续面（同上跳转）。
- 「导出记录」→ `/agent/records`（完整记录页）。工作台没有可导出的对话上下文，这里做导航而不是导出动作。
- 「开始面试」→ 按形式跳文本/语音面试页。

## 五、样式约束

- 零圆角，1px 分隔线（`--gray-200` / `--gray-100`），栏间 `border-right: 1px solid --gray-100`
- 色值全部走 `web/src/assets/css/base.css` 变量，不写死 hex；暗色靠 `base.dark.css` 的同名变量自动适配
- 主色只出现在四处：`开始面试` 主按钮、进行中标签与进度条、趋势折线与数据点、偏弱维度的低分数字
- 小标签 `.lab` 用 11px + `letter-spacing: .12em` + 700
- 无悬停位移、无阴影、无渐变

## 六、验收

- 1600×900 下三栏无横向滚动、不裁切
- 切换形式/岗位/轮次、选简历后「开始面试」能真正发起面试
- 有进行中会话显示卡片，无则空态
- 亮/暗主题正常
- 从工作台进入面试页、再点「调整配置」能回到工作台（验证路由名替换无遗漏）

## 七、文件清单

新增：
- `web/src/views/InterviewWorkbenchView.vue`

修改：
- `web/src/router/index.js`
- `web/src/layouts/AppLayout.vue`
- `web/src/views/InterviewSessionView.vue`、`VoiceInterviewView.vue`、`InterviewResultView.vue`（路由名）
- `web/src/utils/`（`decodeHtmlEntities` 提取）+ `InterviewRecordsView.vue` 改为引用
- `src/repositories/conversation_repository.py`
- `src/services/interview_result_service.py`
- `test/unit/test_interview_result_service.py`（新字段断言）

---

## 修订 · 2026-08-12（设计稿更新）

`templates/新版界面 v3.dc.html` 锚点 `#2a` 被重做：页面从「面试工作台」收窄为「开始面试」，定位改为**只做一件事：让人尽快进入面试**，记录归记录页与侧边栏。以下取代上文中与之冲突的部分，其余（路由、后端补字段、样式约束）不变。

### 布局变更

栅格 `340px 1fr 320px` → `340px 1fr`。左栏「新面试配置」保持不变。

**删除**（已实现，本次移除，含其数据层）：能力趋势 SVG 折线图、反复偏弱三格、右栏最近记录六行。这些内容在 `/agent/records` 面试记录页已经具备。随之删除 `trendPoints` / `trendCoords` / `trendPolyline` / `weakDimensions` / `recentRecords` / `openRecord` / `LOW_SCORE_THRESHOLD`。

### 顶栏

标题「开始面试」。副标题按状态：有未结束会话且有历史分数 → `有一场未结束的面试 · 上次得分 {n}`；无未结束会话但有分数 → `上次得分 {n}`；都没有 → `还没有面试记录`。

右侧按钮：`面试记录`（次要，跳 `/agent/records`）+ `继续未结束的面试`（主，无未结束会话时禁用）。

### 中栏（三块，gap 26px，padding 24px 32px）

**1. 未结束卡片**（横向：左信息 + 右侧两个竖排按钮）

- 小标签「未结束」用 `--main-700`
- 26px 大字 `{position} · {round}`
- 说明行 `停在第 {question_count} 问 · 已答 {answered_count} / 8 题 · 用时 {M} 分钟`
  - **偏离设计稿**：设计稿写作 `停在第 5 问「分布式事务」`。引号里的话题名没有数据源——最后一条 assistant 消息是完整的面试官发言（长句散文），不是话题标签，截断展示会很难看。省略引号部分。
- 两段式进度条，`max-width: 420px`
- 右侧按钮：`继续面试`（主）+ `直接结束并出报告`（次，跳 `InterviewResultPage` 并带 `autoGenerate=1`，与 `InterviewSessionView` 面试完成时的跳转一致）
- 无未结束会话时整块换成空态

**2. 快速开始**（表头行 + 2×2 网格四张卡）

| 卡 | 状态 | 行为 |
|---|---|---|
| 沿用上次配置 | 可用 | 用 `records[0]` 的 position / round / interview_mode 直接发起 |
| 按弱项出题（推荐） | **置灰禁用** | 面试 agent 走 SEP 自适应选题，没有限定话题的入参；`personalized_path.weaknesses[].title` 是维度级描述而非知识点，且无处传入 |
| 语音复试 | 可用 | 预设 mode=voice / round=复试 发起 |
| 纯编程考核 | **置灰禁用** | `start_code_assessment` 是 agent 在面试第 4 阶段自行调用的工具，没有用户发起纯编程会话的入口；`InterviewCodingWorkbench` 依赖 agent 已建好的 coding session |

两张禁用卡按设计稿完整渲染（标题、badge、描述），加 `即将上线` 标记，`cursor: not-allowed`，不可点击。宁可诚实置灰，也不做假交互。

badge 文案对齐真实数据：沿用上次配置 → `{文本|语音} · {question_count} 题`；语音复试 → `语音 · 复试`；另两张沿用设计稿文案。

**3. 面试前检查**（三行，左说明 + 右状态）

| 行 | 数据源 | 就绪判据 |
|---|---|---|
| 简历已解析完成，项目经历可被追问 | 选中简历的 `summary_status` | `completed` → 就绪；`pending`/`processing` → 解析中；`failed` → 解析失败；未选简历 → 未选择 |
| 出题知识库 {names} 已索引 {n} 个文件 | `matchedKnowledge` | `fileCount > 0` → 就绪，否则 未配置 |
| 语音面试需要麦克风权限 | 静态 | 恒为 `选语音时再申请`（弱化色） |

「就绪」用 `--main-700`，非就绪用 `--gray-500`。

### 主色使用（取代上文的四处约束）

主色允许出现的位置：主操作按钮（`开始面试` / `继续未结束的面试` / `继续面试`）、未结束卡片的「未结束」标签与进度条、「推荐」badge 的描边与文字、面试前检查的「就绪」状态字。趋势图与偏弱分数随模块一并删除。
