# SEP: Structured Evaluation Pipeline — Implementation Plan

> **STATUS (2026-05-29): FULLY IMPLEMENTED in the working tree.** The unchecked `- [ ]` boxes below
> are stale — they were never ticked during execution. All 13 tasks are done: backend module
> (`src/services/sep/`) with 48 passing unit tests, result-service integration (`_try_sep_scoring`),
> agent tool (`pick_sep_adaptive_question`), and frontend components, all building/passing. The
> implementation diverged from this plan: it added `session_cache.py` + `interview_result_sep_helpers.py`
> and dropped `CognitiveTimeline.vue` — see the design spec's "Implementation notes" for the full list.
> Treat this plan as historical reference, not an open TODO.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the LLM-as-judge evaluation path with a deterministic three-layer pipeline
(adaptive question selection → cognitive feature extraction → evidence-chain scoring) so that
every score point is traceable to a specific candidate utterance and results are model-independent.

**Architecture:** Layer 1 (Adaptive Selector) picks the next question by estimating candidate
ability via simplified IRT; Layer 2 (Feature Extractor) maps each answer to an 8-dim feature
vector with zero LLM calls; Layer 3 (Evidence Builder) applies rubric-based scoring to produce
a causal evidence chain. The frontend visualises the ability trajectory and evidence chain.
LLM is called once, after scoring, only for narrative generation.

**Tech Stack:** Python 3.12, `jieba` (Chinese tokenisation), ECharts 6 (already in
`web/package.json`), Vue 3 Composition API, Ant Design Vue 4.x.

---

## File Map

### New files (backend)
| Path | Responsibility |
|------|---------------|
| `src/data/question_banks/backend.json` | 20-question bank for backend positions |
| `src/data/question_banks/frontend.json` | 20-question bank for frontend positions |
| `src/data/question_banks/algorithm.json` | 20-question bank for algorithm positions |
| `src/services/sep/__init__.py` | `SEPSession` orchestrator class |
| `src/services/sep/feature_extractor.py` | Layer 2 — `AnswerFeatures`, `extract_features()` |
| `src/services/sep/ability_estimator.py` | Layer 1 algorithm — `update_ability()` |
| `src/services/sep/rubric_engine.py` | Rubric maps, `features_to_score_delta()` |
| `src/services/sep/evidence_builder.py` | Layer 3 — `EvidenceItem`, `EvaluationReport`, `build_evidence_chain()` |
| `src/services/sep/adaptive_selector.py` | Layer 1 — `load_question_bank()`, `select_next_question()` |
| `test/unit/sep/__init__.py` | Empty init for test package |
| `test/unit/sep/test_feature_extractor.py` | Unit tests for Layer 2 |
| `test/unit/sep/test_ability_estimator.py` | Unit tests for IRT update |
| `test/unit/sep/test_rubric_engine.py` | Unit tests for scoring rules |
| `test/unit/sep/test_evidence_builder.py` | Unit tests for report assembly |
| `test/unit/sep/test_adaptive_selector.py` | Unit tests for question selection |
| `test/unit/sep/test_sep_session.py` | Integration test for full session |

### New files (frontend)
| Path | Responsibility |
|------|---------------|
| `web/src/components/sep/EvidenceChain.vue` | Per-question evidence list with score deltas |
| `web/src/components/sep/AdaptiveTrajectory.vue` | Line chart of θ trajectory |

### Modified files
| Path | Change |
|------|--------|
| `pyproject.toml` | Add `jieba` dependency |
| `src/services/interview_result_service.py` | Add SEP-first scoring path in `_build_result_from_message` |
| `web/src/views/InterviewResultView.vue` | Insert `EvidenceChain` + `AdaptiveTrajectory` into evidence section |

---

## Task 1 — Add `jieba` Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add jieba to project dependencies**

Open `pyproject.toml`. Find the `[project]` `dependencies` list and add one line:

```toml
"jieba>=0.42",
```

The list will look like (existing entries abbreviated):
```toml
[project]
dependencies = [
    ...
    "jieba>=0.42",
    ...
]
```

- [ ] **Step 2: Install inside the API container**

```bash
docker compose exec api uv add jieba
```

Expected output ends with: `Resolved ... packages` and no error.

- [ ] **Step 3: Verify import works**

```bash
docker compose exec api uv run python -c "import jieba; print(jieba.__version__)"
```

Expected: a version string like `0.42.1`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(sep): add jieba dependency for Chinese tokenisation"
```

---

## Task 2 — Question Bank Data Files

**Files:**
- Create: `src/data/question_banks/backend.json`
- Create: `src/data/question_banks/frontend.json`
- Create: `src/data/question_banks/algorithm.json`

- [ ] **Step 1: Create directory**

```bash
mkdir -p src/data/question_banks
```

- [ ] **Step 2: Create `src/data/question_banks/backend.json`**

```json
[
  {
    "id": "net-tcp-001",
    "domain": "networking",
    "concept": "TCP三次握手",
    "difficulty": 0.40,
    "question_template": "请解释TCP建立连接的过程",
    "rubric": {
      "required": ["SYN", "SYN-ACK", "ACK"],
      "bonus": ["TIME_WAIT", "半连接队列", "SYN flood"],
      "misconceptions": ["四次握手建立连接", "握手传输数据"]
    }
  },
  {
    "id": "net-http-001",
    "domain": "networking",
    "concept": "HTTP与HTTPS的区别",
    "difficulty": 0.35,
    "question_template": "HTTP和HTTPS有什么区别？为什么要用HTTPS？",
    "rubric": {
      "required": ["加密", "TLS", "SSL", "证书"],
      "bonus": ["中间人攻击", "CA", "对称加密", "非对称加密", "握手"],
      "misconceptions": ["HTTPS更慢所以不推荐", "HTTP也能加密"]
    }
  },
  {
    "id": "db-index-001",
    "domain": "database",
    "concept": "数据库索引",
    "difficulty": 0.45,
    "question_template": "请解释数据库索引的作用，以及什么情况下不应该建索引？",
    "rubric": {
      "required": ["查询加速", "B+树", "写入开销"],
      "bonus": ["覆盖索引", "联合索引最左前缀", "索引失效", "回表"],
      "misconceptions": ["索引越多越好", "索引不占空间"]
    }
  },
  {
    "id": "db-tx-001",
    "domain": "database",
    "concept": "数据库事务ACID",
    "difficulty": 0.50,
    "question_template": "请描述数据库事务的ACID特性，各自解决什么问题？",
    "rubric": {
      "required": ["原子性", "一致性", "隔离性", "持久性"],
      "bonus": ["脏读", "幻读", "不可重复读", "MVCC", "undo log"],
      "misconceptions": ["ACID只有MySQL支持", "持久性靠内存实现"]
    }
  },
  {
    "id": "algo-sort-001",
    "domain": "algorithms",
    "concept": "排序算法对比",
    "difficulty": 0.40,
    "question_template": "快速排序和归并排序有什么区别？各自适用于什么场景？",
    "rubric": {
      "required": ["时间复杂度", "O(n log n)", "稳定性"],
      "bonus": ["原地排序", "缓存友好", "链表用归并", "分治"],
      "misconceptions": ["快速排序总比归并排序快", "快速排序是稳定的"]
    }
  },
  {
    "id": "algo-dp-001",
    "domain": "algorithms",
    "concept": "动态规划",
    "difficulty": 0.70,
    "question_template": "什么是动态规划？请举例说明如何用动态规划解决问题。",
    "rubric": {
      "required": ["最优子结构", "重叠子问题", "状态转移"],
      "bonus": ["记忆化搜索", "滚动数组", "背包问题", "边界条件"],
      "misconceptions": ["DP就是递归", "所有递归都能改DP"]
    }
  },
  {
    "id": "sys-cache-001",
    "domain": "system_design",
    "concept": "缓存策略",
    "difficulty": 0.55,
    "question_template": "在系统设计中，你如何设计缓存策略？常见的缓存问题有哪些？",
    "rubric": {
      "required": ["缓存击穿", "缓存雪崩", "缓存穿透"],
      "bonus": ["布隆过滤器", "互斥锁", "热点key", "TTL", "LRU"],
      "misconceptions": ["缓存能解决所有性能问题", "缓存和数据库强一致"]
    }
  },
  {
    "id": "sys-mq-001",
    "domain": "system_design",
    "concept": "消息队列使用场景",
    "difficulty": 0.60,
    "question_template": "消息队列解决了什么问题？使用消息队列有哪些注意事项？",
    "rubric": {
      "required": ["解耦", "异步", "削峰填谷"],
      "bonus": ["消息幂等", "消息丢失", "消费顺序", "死信队列", "背压"],
      "misconceptions": ["消息队列保证exactly-once默认", "同步场景也适合MQ"]
    }
  },
  {
    "id": "lang-gc-001",
    "domain": "language",
    "concept": "垃圾回收机制",
    "difficulty": 0.65,
    "question_template": "请描述你熟悉的语言的垃圾回收机制，它有什么优缺点？",
    "rubric": {
      "required": ["引用计数", "标记清除", "内存泄漏"],
      "bonus": ["分代回收", "STW", "增量GC", "循环引用", "finalizer"],
      "misconceptions": ["GC彻底解决了内存问题", "引用计数能处理循环引用"]
    }
  },
  {
    "id": "beh-conflict-001",
    "domain": "behavioral",
    "concept": "团队冲突处理",
    "difficulty": 0.45,
    "question_template": "描述一次你和团队成员产生意见分歧的经历，你是如何处理的？",
    "rubric": {
      "required": ["沟通", "解决", "结果"],
      "bonus": ["倾听", "数据支撑", "妥协", "共识"],
      "misconceptions": []
    }
  },
  {
    "id": "net-dns-001",
    "domain": "networking",
    "concept": "DNS解析过程",
    "difficulty": 0.55,
    "question_template": "请描述在浏览器中输入URL到页面显示的完整过程，重点说明DNS解析。",
    "rubric": {
      "required": ["本地缓存", "递归查询", "A记录"],
      "bonus": ["根域名服务器", "TTL", "CDN", "CNAME", "负载均衡"],
      "misconceptions": ["DNS直接返回IP内容", "DNS查询是TCP"]
    }
  },
  {
    "id": "db-redis-001",
    "domain": "database",
    "concept": "Redis数据结构",
    "difficulty": 0.50,
    "question_template": "Redis有哪些数据结构？各自适合什么场景？",
    "rubric": {
      "required": ["String", "Hash", "List", "Set", "ZSet"],
      "bonus": ["HyperLogLog", "Bitmap", "Stream", "地理位置", "跳表"],
      "misconceptions": ["Redis只能存字符串", "ZSet用二叉树实现"]
    }
  },
  {
    "id": "algo-graph-001",
    "domain": "algorithms",
    "concept": "图算法",
    "difficulty": 0.72,
    "question_template": "如何判断一个有向图中是否存在环？请描述算法并分析复杂度。",
    "rubric": {
      "required": ["DFS", "拓扑排序", "时间复杂度O(V+E)"],
      "bonus": ["三色标记", "Kahn算法", "强连通分量", "SCC"],
      "misconceptions": ["BFS可以检测有向图环", "只需检查邻接矩阵对角线"]
    }
  },
  {
    "id": "sys-lb-001",
    "domain": "system_design",
    "concept": "负载均衡",
    "difficulty": 0.60,
    "question_template": "常见的负载均衡算法有哪些？它们各有什么优缺点？",
    "rubric": {
      "required": ["轮询", "加权", "一致性哈希"],
      "bonus": ["最少连接", "IP哈希", "会话保持", "健康检查", "虚拟节点"],
      "misconceptions": ["一致性哈希能完全避免缓存失效", "轮询适合所有场景"]
    }
  },
  {
    "id": "lang-thread-001",
    "domain": "language",
    "concept": "并发与线程安全",
    "difficulty": 0.68,
    "question_template": "什么是线程安全？如何实现线程安全？请举例说明。",
    "rubric": {
      "required": ["竞态条件", "锁", "原子操作"],
      "bonus": ["CAS", "volatile", "ThreadLocal", "无锁数据结构", "死锁"],
      "misconceptions": ["加锁一定线程安全", "Python的GIL使所有操作线程安全"]
    }
  },
  {
    "id": "beh-failure-001",
    "domain": "behavioral",
    "concept": "失败经历与学习",
    "difficulty": 0.40,
    "question_template": "描述一个你犯过的技术错误，你从中学到了什么？",
    "rubric": {
      "required": ["错误", "影响", "改进"],
      "bonus": ["根因分析", "预防措施", "团队分享", "复盘"],
      "misconceptions": []
    }
  },
  {
    "id": "net-tcp-002",
    "domain": "networking",
    "concept": "TCP四次挥手",
    "difficulty": 0.58,
    "question_template": "请描述TCP关闭连接的四次挥手过程，为什么是四次而不是三次？",
    "rubric": {
      "required": ["FIN", "ACK", "半关闭状态"],
      "bonus": ["TIME_WAIT等待2MSL", "close_wait堆积", "FIN_WAIT"],
      "misconceptions": ["四次挥手可以合并为三次", "TIME_WAIT是bug"]
    }
  },
  {
    "id": "db-mysql-001",
    "domain": "database",
    "concept": "MySQL InnoDB与MyISAM",
    "difficulty": 0.52,
    "question_template": "InnoDB和MyISAM存储引擎有什么区别？什么时候选择各自？",
    "rubric": {
      "required": ["事务", "行锁", "外键", "崩溃恢复"],
      "bonus": ["MVCC", "聚簇索引", "全文索引", "表锁", "redo log"],
      "misconceptions": ["MyISAM更快所以更好", "InnoDB不支持全文索引（MySQL5.7+已支持）"]
    }
  },
  {
    "id": "algo-search-001",
    "domain": "algorithms",
    "concept": "二分查找",
    "difficulty": 0.35,
    "question_template": "请实现二分查找，并说明边界条件的处理方式。",
    "rubric": {
      "required": ["有序数组", "mid计算", "左闭右闭或左闭右开"],
      "bonus": ["防止整数溢出用low+(high-low)/2", "旋转数组变种", "浮点二分"],
      "misconceptions": ["mid=(low+high)/2在大数时溢出没问题", "二分只能用于整数"]
    }
  },
  {
    "id": "sys-design-001",
    "domain": "system_design",
    "concept": "短链接系统设计",
    "difficulty": 0.75,
    "question_template": "请设计一个短链接服务，支持每天1亿次点击，说明关键设计决策。",
    "rubric": {
      "required": ["哈希映射", "数据库存储", "重定向"],
      "bonus": ["Base62编码", "缓存热点", "自定义短链", "统计分析", "分库分表", "布隆过滤器"],
      "misconceptions": ["用UUID做短链", "不需要考虑哈希冲突"]
    }
  }
]
```

- [ ] **Step 3: Create `src/data/question_banks/frontend.json`**

```json
[
  {
    "id": "js-closure-001",
    "domain": "javascript",
    "concept": "闭包",
    "difficulty": 0.45,
    "question_template": "什么是JavaScript闭包？请举例说明其应用场景。",
    "rubric": {
      "required": ["词法作用域", "内层函数", "外部变量引用"],
      "bonus": ["内存泄漏", "模块模式", "柯里化", "事件监听器"],
      "misconceptions": ["闭包就是匿名函数", "闭包会导致内存一定泄漏"]
    }
  },
  {
    "id": "js-event-001",
    "domain": "javascript",
    "concept": "事件循环",
    "difficulty": 0.65,
    "question_template": "请解释JavaScript的事件循环机制，宏任务和微任务有什么区别？",
    "rubric": {
      "required": ["调用栈", "宏任务", "微任务", "执行顺序"],
      "bonus": ["Promise.then", "queueMicrotask", "requestAnimationFrame", "Node.js差异"],
      "misconceptions": ["setTimeout(fn,0)立即执行", "微任务在宏任务之后"]
    }
  },
  {
    "id": "css-box-001",
    "domain": "css",
    "concept": "CSS盒模型",
    "difficulty": 0.35,
    "question_template": "请解释CSS盒模型，标准盒模型和IE盒模型有什么区别？",
    "rubric": {
      "required": ["content", "padding", "border", "margin", "box-sizing"],
      "bonus": ["BFC", "外边距折叠", "border-box", "inline-block"],
      "misconceptions": ["margin是盒子的一部分（内部）", "padding包含content"]
    }
  },
  {
    "id": "fw-vue-001",
    "domain": "frameworks",
    "concept": "Vue响应式原理",
    "difficulty": 0.60,
    "question_template": "请解释Vue3的响应式原理，与Vue2有什么不同？",
    "rubric": {
      "required": ["Proxy", "Reflect", "依赖收集", "派发更新"],
      "bonus": ["Object.defineProperty局限", "嵌套对象", "数组监听", "WeakMap存储"],
      "misconceptions": ["Vue3用Object.defineProperty", "Proxy比defineProperty慢"]
    }
  },
  {
    "id": "perf-render-001",
    "domain": "performance",
    "concept": "浏览器渲染优化",
    "difficulty": 0.55,
    "question_template": "如何优化前端页面的首屏加载速度？",
    "rubric": {
      "required": ["懒加载", "代码分割", "缓存"],
      "bonus": ["Critical CSS", "预加载preload", "Tree Shaking", "CDN", "SSR/SSG"],
      "misconceptions": ["压缩图片就够了", "所有资源都应该懒加载"]
    }
  },
  {
    "id": "js-proto-001",
    "domain": "javascript",
    "concept": "原型链",
    "difficulty": 0.58,
    "question_template": "请解释JavaScript的原型链机制，instanceof是如何工作的？",
    "rubric": {
      "required": ["prototype", "__proto__", "原型链查找"],
      "bonus": ["Object.create", "constructor属性", "寄生组合继承", "ES6 class语法糖"],
      "misconceptions": ["class是全新机制与原型链无关", "所有对象都有prototype"]
    }
  },
  {
    "id": "fw-vdom-001",
    "domain": "frameworks",
    "concept": "虚拟DOM与Diff算法",
    "difficulty": 0.68,
    "question_template": "虚拟DOM解决了什么问题？React/Vue的Diff算法有哪些优化策略？",
    "rubric": {
      "required": ["批量更新", "减少真实DOM操作", "同层比较"],
      "bonus": ["key的作用", "O(n)复杂度优化", "双端对比", "最长递增子序列"],
      "misconceptions": ["虚拟DOM一定比直接操作DOM快", "Diff算法是O(n³)"]
    }
  },
  {
    "id": "css-flex-001",
    "domain": "css",
    "concept": "Flex布局",
    "difficulty": 0.30,
    "question_template": "请说明Flex布局的核心概念，如何用Flex实现常见的居中布局？",
    "rubric": {
      "required": ["flex-container", "flex-item", "主轴", "交叉轴"],
      "bonus": ["flex-grow/shrink/basis", "align-self", "order", "flex-wrap"],
      "misconceptions": ["flex只能水平布局", "flex-direction默认是column"]
    }
  },
  {
    "id": "perf-memory-001",
    "domain": "performance",
    "concept": "内存泄漏排查",
    "difficulty": 0.70,
    "question_template": "前端应用中常见的内存泄漏场景有哪些？如何排查？",
    "rubric": {
      "required": ["未清除事件监听", "定时器", "闭包引用"],
      "bonus": ["WeakMap/WeakRef", "Chrome Memory面板", "Heap Snapshot", "分离DOM节点"],
      "misconceptions": ["SPA不存在内存泄漏", "垃圾回收能处理所有泄漏"]
    }
  },
  {
    "id": "beh-review-001",
    "domain": "behavioral",
    "concept": "代码审查经验",
    "difficulty": 0.40,
    "question_template": "描述一次你参与代码审查的经历，你关注哪些方面？",
    "rubric": {
      "required": ["可读性", "正确性", "反馈"],
      "bonus": ["性能考量", "安全问题", "测试覆盖", "建设性建议"],
      "misconceptions": []
    }
  },
  {
    "id": "js-promise-001",
    "domain": "javascript",
    "concept": "Promise与async/await",
    "difficulty": 0.50,
    "question_template": "Promise和async/await有什么关系？如何处理并发请求？",
    "rubric": {
      "required": ["异步", "链式调用", "错误处理"],
      "bonus": ["Promise.all", "Promise.race", "Promise.allSettled", "取消请求AbortController"],
      "misconceptions": ["async/await比Promise性能更好", "await可以用在普通函数中"]
    }
  },
  {
    "id": "css-bfc-001",
    "domain": "css",
    "concept": "BFC块级格式上下文",
    "difficulty": 0.62,
    "question_template": "什么是BFC？它能解决哪些CSS布局问题？",
    "rubric": {
      "required": ["独立渲染区域", "清除浮动", "外边距折叠"],
      "bonus": ["overflow:hidden触发", "float触发", "flex触发", "position:absolute"],
      "misconceptions": ["BFC只能用overflow:hidden触发", "BFC影响外部布局"]
    }
  },
  {
    "id": "fw-state-001",
    "domain": "frameworks",
    "concept": "前端状态管理",
    "difficulty": 0.58,
    "question_template": "什么情况下需要引入全局状态管理？Pinia和Vuex有什么区别？",
    "rubric": {
      "required": ["组件间通信", "单向数据流", "状态集中"],
      "bonus": ["组合式API支持", "TypeScript推断", "插件系统", "持久化"],
      "misconceptions": ["所有状态都要放在store里", "Pinia需要mutation"]
    }
  },
  {
    "id": "perf-bundle-001",
    "domain": "performance",
    "concept": "构建优化",
    "difficulty": 0.65,
    "question_template": "如何减小前端应用的bundle体积？请说明具体优化手段。",
    "rubric": {
      "required": ["Tree Shaking", "Code Splitting", "懒加载路由"],
      "bonus": ["动态import", "scope hoisting", "externals", "gzip/br", "按需引入"],
      "misconceptions": ["压缩=优化完成", "所有第三方库都应打包进bundle"]
    }
  },
  {
    "id": "js-this-001",
    "domain": "javascript",
    "concept": "this指向",
    "difficulty": 0.55,
    "question_template": "请解释JavaScript中this的绑定规则，箭头函数和普通函数有什么区别？",
    "rubric": {
      "required": ["调用位置", "显式绑定", "箭头函数继承this"],
      "bonus": ["new绑定", "call/apply/bind", "严格模式", "class中的this"],
      "misconceptions": ["this在定义时确定（普通函数）", "箭头函数可以被bind改变this"]
    }
  },
  {
    "id": "fw-lifecycle-001",
    "domain": "frameworks",
    "concept": "组件生命周期",
    "difficulty": 0.42,
    "question_template": "请描述Vue3组件的生命周期钩子，onMounted和onUpdated分别适合做什么？",
    "rubric": {
      "required": ["setup", "onMounted", "onUnmounted", "onUpdated"],
      "bonus": ["onBeforeMount", "onActivated", "keep-alive", "watchEffect"],
      "misconceptions": ["setup替代了created和beforeCreate", "onMounted在服务端也执行"]
    }
  },
  {
    "id": "beh-deadline-001",
    "domain": "behavioral",
    "concept": "时间压力下的工作",
    "difficulty": 0.38,
    "question_template": "描述一次你在紧迫截止日期下完成项目的经历，你是如何安排优先级的？",
    "rubric": {
      "required": ["优先级", "沟通", "完成"],
      "bonus": ["MVP思路", "及时同步进度", "技术债记录", "团队协作"],
      "misconceptions": []
    }
  },
  {
    "id": "css-animation-001",
    "domain": "css",
    "concept": "CSS动画性能",
    "difficulty": 0.60,
    "question_template": "CSS动画如何避免触发重排（reflow）？哪些属性对性能友好？",
    "rubric": {
      "required": ["transform", "opacity", "合成层", "重排重绘"],
      "bonus": ["will-change", "GPU加速", "requestAnimationFrame", "FLIP技术"],
      "misconceptions": ["所有CSS动画都在合成线程", "margin动画和transform动画性能一样"]
    }
  },
  {
    "id": "js-module-001",
    "domain": "javascript",
    "concept": "ES模块vs CommonJS",
    "difficulty": 0.52,
    "question_template": "ES模块和CommonJS模块有什么区别？为什么现代项目推荐ES模块？",
    "rubric": {
      "required": ["静态分析", "tree shaking", "异步加载", "实时绑定"],
      "bonus": ["循环依赖处理差异", "顶层await", "import.meta", "动态import"],
      "misconceptions": ["两者完全兼容可以混用", "require是同步的所以更快"]
    }
  },
  {
    "id": "perf-security-001",
    "domain": "performance",
    "concept": "前端安全",
    "difficulty": 0.68,
    "question_template": "前端常见的安全漏洞有哪些？如何防范XSS和CSRF攻击？",
    "rubric": {
      "required": ["XSS", "CSRF", "输入转义"],
      "bonus": ["CSP", "SameSite Cookie", "HTTPS", "Token验证", "iframe沙箱"],
      "misconceptions": ["前端验证够用不需要后端验证", "HTTPS能防止XSS"]
    }
  }
]
```

- [ ] **Step 4: Create `src/data/question_banks/algorithm.json`**

```json
[
  {
    "id": "algo-complexity-001",
    "domain": "algorithms",
    "concept": "时间复杂度分析",
    "difficulty": 0.35,
    "question_template": "如何分析一个算法的时间复杂度？请分析冒泡排序和快速排序的区别。",
    "rubric": {
      "required": ["大O记号", "最坏情况", "平均情况"],
      "bonus": ["摊还分析", "空间换时间", "常数因子", "主定理"],
      "misconceptions": ["O(n)一定比O(n²)快", "最好情况才是真实复杂度"]
    }
  },
  {
    "id": "algo-two-ptr-001",
    "domain": "algorithms",
    "concept": "双指针技巧",
    "difficulty": 0.50,
    "question_template": "请说明双指针技巧的核心思想，给出一个你用过的典型题目。",
    "rubric": {
      "required": ["两端向中间", "快慢指针", "有序数组"],
      "bonus": ["滑动窗口", "三数之和去重", "链表判环", "反转链表"],
      "misconceptions": ["双指针只能用于数组", "双指针比暴力解法慢"]
    }
  },
  {
    "id": "ds-tree-001",
    "domain": "data_structures",
    "concept": "二叉树遍历",
    "difficulty": 0.40,
    "question_template": "请说明二叉树的三种遍历方式，并给出非递归实现思路。",
    "rubric": {
      "required": ["前序", "中序", "后序", "栈模拟"],
      "bonus": ["Morris遍历O(1)空间", "层序遍历", "迭代器模式", "线索二叉树"],
      "misconceptions": ["非递归遍历需要额外O(n)空间（Morris不需要）", "后序遍历只能递归实现"]
    }
  },
  {
    "id": "ds-hash-001",
    "domain": "data_structures",
    "concept": "哈希表原理",
    "difficulty": 0.45,
    "question_template": "请解释哈希表的实现原理，如何处理哈希冲突？",
    "rubric": {
      "required": ["哈希函数", "冲突处理", "负载因子"],
      "bonus": ["开放地址法", "链地址法", "动态扩容rehash", "一致性哈希"],
      "misconceptions": ["哈希表查找一定是O(1)", "哈希冲突无法避免但可消除"]
    }
  },
  {
    "id": "algo-bfs-001",
    "domain": "algorithms",
    "concept": "BFS最短路径",
    "difficulty": 0.52,
    "question_template": "如何用BFS求无权图的最短路径？多源BFS如何处理？",
    "rubric": {
      "required": ["队列", "visited标记", "层序扩展"],
      "bonus": ["双向BFS", "0-1BFS", "Dijkstra对比", "多源同时入队"],
      "misconceptions": ["BFS只能用于树", "DFS也能找最短路径（无权图）"]
    }
  },
  {
    "id": "algo-dp-002",
    "domain": "algorithms",
    "concept": "背包问题",
    "difficulty": 0.68,
    "question_template": "请描述0-1背包问题和完全背包问题的区别，如何用DP求解？",
    "rubric": {
      "required": ["状态定义", "转移方程", "01背包逆序遍历"],
      "bonus": ["完全背包正序遍历", "滚动数组优化", "分组背包", "多维背包"],
      "misconceptions": ["0-1背包也可以正序遍历", "背包容量必须是整数"]
    }
  },
  {
    "id": "ds-heap-001",
    "domain": "data_structures",
    "concept": "堆与优先队列",
    "difficulty": 0.55,
    "question_template": "堆的核心操作是什么？如何用堆解决TopK问题？",
    "rubric": {
      "required": ["上浮下沉", "O(log n)插入删除", "O(1)查看最值"],
      "bonus": ["建堆O(n)", "堆排序", "K路归并", "延迟删除", "双堆维护中位数"],
      "misconceptions": ["堆是有序的", "堆排序稳定"]
    }
  },
  {
    "id": "algo-string-001",
    "domain": "algorithms",
    "concept": "字符串匹配",
    "difficulty": 0.65,
    "question_template": "请解释KMP算法的核心思路，next数组是如何构建的？",
    "rubric": {
      "required": ["失配时回退", "next数组", "O(n+m)复杂度"],
      "bonus": ["前缀函数含义", "部分匹配表", "Rabin-Karp哈希", "AC自动机扩展"],
      "misconceptions": ["KMP只适用于单模式匹配", "next数组构建是O(m²)"]
    }
  },
  {
    "id": "algo-divide-001",
    "domain": "algorithms",
    "concept": "分治算法",
    "difficulty": 0.60,
    "question_template": "分治算法的三个步骤是什么？请举一个除排序外的分治应用。",
    "rubric": {
      "required": ["分解", "解决", "合并"],
      "bonus": ["最大子数组和", "逆序对计数", "大数乘法Karatsuba", "主定理分析"],
      "misconceptions": ["分治一定比迭代慢", "分治子问题必须等规模"]
    }
  },
  {
    "id": "ds-union-001",
    "domain": "data_structures",
    "concept": "并查集",
    "difficulty": 0.58,
    "question_template": "请说明并查集的实现原理，路径压缩和按秩合并各自的作用是什么？",
    "rubric": {
      "required": ["find操作", "union操作", "父节点数组"],
      "bonus": ["路径压缩O(α(n))", "按秩合并", "连通分量计数", "带权并查集"],
      "misconceptions": ["并查集只能判断连通性", "不用路径压缩也有近似O(1)"]
    }
  },
  {
    "id": "algo-greedy-001",
    "domain": "algorithms",
    "concept": "贪心算法",
    "difficulty": 0.62,
    "question_template": "贪心算法的适用条件是什么？请举例说明如何证明贪心选择的正确性。",
    "rubric": {
      "required": ["局部最优", "全局最优", "贪心选择性质"],
      "bonus": ["交换论证法", "活动选择问题", "Huffman编码", "最小生成树"],
      "misconceptions": ["贪心算法一定正确", "能给出反例就说明贪心不可用"]
    }
  },
  {
    "id": "math-prob-001",
    "domain": "math",
    "concept": "概率与期望",
    "difficulty": 0.70,
    "question_template": "随机洗牌算法（Fisher-Yates）的原理是什么？如何证明其均匀性？",
    "rubric": {
      "required": ["每种排列等概率", "O(n)时间", "原地交换"],
      "bonus": ["数学归纳法证明", "伪随机数影响", "水库抽样", "蒙特卡洛方法"],
      "misconceptions": ["直接random.shuffle就是Fisher-Yates", "朴素方法(random位置插入)等价"]
    }
  },
  {
    "id": "ds-skiplist-001",
    "domain": "data_structures",
    "concept": "跳表",
    "difficulty": 0.72,
    "question_template": "跳表解决了什么问题？它和平衡二叉树相比有什么优缺点？",
    "rubric": {
      "required": ["多层索引", "O(log n)查找", "空间换时间"],
      "bonus": ["随机层数", "Redis ZSet使用跳表的原因", "范围查询优势", "并发友好"],
      "misconceptions": ["跳表性能不如红黑树", "跳表只能用于整数"]
    }
  },
  {
    "id": "algo-monotone-001",
    "domain": "algorithms",
    "concept": "单调栈",
    "difficulty": 0.65,
    "question_template": "单调栈的核心思想是什么？如何用单调栈解决「下一个更大元素」问题？",
    "rubric": {
      "required": ["维护单调性", "弹出时记录答案", "O(n)摊还"],
      "bonus": ["接雨水", "柱状图最大矩形", "滑动窗口最大值（单调队列）", "股票价格跨度"],
      "misconceptions": ["单调栈只能找下一个更大元素", "单调栈每次操作是O(1)"]
    }
  },
  {
    "id": "sys-oo-001",
    "domain": "system_design",
    "concept": "面向对象设计原则",
    "difficulty": 0.55,
    "question_template": "请说明SOLID原则中的开闭原则，并举例说明违反它的危害。",
    "rubric": {
      "required": ["对扩展开放", "对修改关闭", "抽象"],
      "bonus": ["策略模式实现OCP", "接口隔离", "依赖注入", "里氏替换"],
      "misconceptions": ["所有if-else都违反OCP", "OCP要求零修改"]
    }
  },
  {
    "id": "algo-bits-001",
    "domain": "algorithms",
    "concept": "位运算技巧",
    "difficulty": 0.60,
    "question_template": "位运算在算法中有哪些常见应用？请说明如何用位运算找出数组中唯一出现奇数次的数。",
    "rubric": {
      "required": ["XOR消除相同元素", "与/或/非操作", "移位"],
      "bonus": ["n&(n-1)消最低位1", "lowbit=n&(-n)", "状态压缩DP", "Brian Kernighan"],
      "misconceptions": ["位运算只能操作整数（Python大整数也可以）", "移位比乘除法一定快（现代CPU已优化）"]
    }
  },
  {
    "id": "ds-trie-001",
    "domain": "data_structures",
    "concept": "字典树Trie",
    "difficulty": 0.62,
    "question_template": "请说明Trie树的结构和应用场景，与哈希表相比有什么优势？",
    "rubric": {
      "required": ["公共前缀", "字符节点", "isEnd标记"],
      "bonus": ["压缩Trie", "自动补全", "IP路由", "XOR最大值"],
      "misconceptions": ["Trie只能存储字符串", "Trie比哈希表更省空间"]
    }
  },
  {
    "id": "beh-algo-001",
    "domain": "behavioral",
    "concept": "算法问题解题过程",
    "difficulty": 0.35,
    "question_template": "当你遇到一道陌生的算法题时，你的解题思路是什么？如何从暴力解到最优解？",
    "rubric": {
      "required": ["读题理解", "暴力解", "优化方向"],
      "bonus": ["举例验证", "边界条件", "复杂度分析", "多种方法对比"],
      "misconceptions": []
    }
  },
  {
    "id": "algo-segment-001",
    "domain": "algorithms",
    "concept": "线段树",
    "difficulty": 0.80,
    "question_template": "线段树解决了什么类型的问题？请说明区间查询和单点更新的实现思路。",
    "rubric": {
      "required": ["区间查询O(log n)", "单点更新O(log n)", "递归建树"],
      "bonus": ["懒标记区间更新", "动态开点", "持久化线段树", "树状数组对比"],
      "misconceptions": ["线段树只能存最大值", "线段树适合频繁插入删除"]
    }
  },
  {
    "id": "math-matrix-001",
    "domain": "math",
    "concept": "矩阵快速幂",
    "difficulty": 0.75,
    "question_template": "如何用矩阵快速幂优化斐波那契数列的计算？请描述原理。",
    "rubric": {
      "required": ["矩阵乘法", "快速幂O(log n)", "状态转移矩阵"],
      "bonus": ["线性递推通用化", "图的路径计数", "模运算", "Cayley-Hamilton定理"],
      "misconceptions": ["矩阵快速幂只用于斐波那契", "快速幂必须用递归实现"]
    }
  }
]
```

- [ ] **Step 5: Commit**

```bash
git add src/data/question_banks/
git commit -m "feat(sep): add question banks for backend, frontend, algorithm positions"
```

---

## Task 3 — Layer 2: Feature Extractor (TDD)

**Files:**
- Create: `src/services/sep/__init__.py` (empty for now)
- Create: `src/services/sep/feature_extractor.py`
- Create: `test/unit/sep/__init__.py`
- Create: `test/unit/sep/test_feature_extractor.py`

- [ ] **Step 1: Create package skeleton**

```bash
mkdir -p src/services/sep
mkdir -p test/unit/sep
touch src/services/sep/__init__.py
touch test/unit/sep/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `test/unit/sep/test_feature_extractor.py`:

```python
from src.services.sep.feature_extractor import AnswerFeatures, extract_features

SAMPLE_RUBRIC = {
    "required": ["SYN", "SYN-ACK", "ACK"],
    "bonus": ["TIME_WAIT", "半连接队列"],
    "misconceptions": ["四次握手建立连接"],
}


def test_full_required_hit():
    answer = "TCP建立连接需要三次握手：客户端发SYN，服务器回SYN-ACK，客户端再发ACK。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.required_hit_rate == 1.0


def test_partial_required_hit():
    answer = "TCP握手需要发SYN包。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.required_hit_rate == pytest.approx(1 / 3, abs=0.01)


def test_bonus_hit():
    answer = "完成握手后进入TIME_WAIT状态，还有半连接队列的概念。SYN SYN-ACK ACK都要走。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.bonus_hit_count == 2


def test_misconception_detected():
    answer = "TCP需要四次握手建立连接，发SYN后还要再发一次。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.misconception_count == 1


def test_star_action_detected():
    answer = "在项目中（背景）我负责优化连接池（任务），我实现了连接复用机制（行动），最终降低了30%延迟（结果）。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.star_scores["S"] is True
    assert feat.star_scores["T"] is True
    assert feat.star_scores["A"] is True
    assert feat.star_scores["R"] is True


def test_hedge_ratio():
    answer = "可能是SYN，也许还有ACK，大概是这样的流程，我觉得差不多。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.hedge_ratio > 0.15


def test_empty_answer():
    feat = extract_features("", SAMPLE_RUBRIC)
    assert feat.required_hit_rate == 0.0
    assert feat.bonus_hit_count == 0
    assert feat.misconception_count == 0
    assert feat.hedge_ratio == 0.0


def test_answer_score_high_for_complete_answer():
    answer = "SYN SYN-ACK ACK都走一遍，TIME_WAIT和半连接队列我也知道。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.to_answer_score() > 0.7


def test_answer_score_low_for_misconception():
    answer = "四次握手建立连接，可能是这样的。"
    feat = extract_features(answer, SAMPLE_RUBRIC)
    assert feat.to_answer_score() < 0.3


import pytest
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_feature_extractor.py -v
```

Expected: `ImportError: No module named 'src.services.sep.feature_extractor'`

- [ ] **Step 4: Implement `src/services/sep/feature_extractor.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

import jieba

STAR_KEYWORDS: dict[str, list[str]] = {
    "S": ["背景", "当时", "那时", "情况", "项目中", "在做", "工作中", "遇到", "有一次", "上一家"],
    "T": ["任务", "目标", "负责", "需要", "要求", "职责", "要做"],
    "A": ["我做了", "我采用", "我实现", "我设计", "我主导", "我负责", "我使用", "我开发", "我选择", "我提出"],
    "R": ["最终", "结果", "成功", "提升", "降低", "上线", "完成", "达到", "实现了", "解决了"],
}

HEDGE_WORDS = frozenset([
    "可能", "也许", "大概", "应该", "不太确定", "我猜", "我觉得", "或许", "感觉", "好像",
    "差不多", "左右", "估计", "不确定", "不一定",
])


@dataclass
class AnswerFeatures:
    required_hit_rate: float
    bonus_hit_count: int
    misconception_count: int
    star_scores: dict[str, bool]
    hedge_ratio: float

    def to_answer_score(self) -> float:
        base = self.required_hit_rate
        bonus = min(0.2, self.bonus_hit_count * 0.05)
        star_bonus = sum(self.star_scores.values()) / 4 * 0.1
        penalty = min(0.3, self.misconception_count * 0.15)
        hedge_penalty = self.hedge_ratio * 0.1
        return max(0.0, min(1.0, base + bonus + star_bonus - penalty - hedge_penalty))


def extract_features(answer: str, rubric: dict) -> AnswerFeatures:
    if not answer or not answer.strip():
        return AnswerFeatures(
            required_hit_rate=0.0,
            bonus_hit_count=0,
            misconception_count=0,
            star_scores={"S": False, "T": False, "A": False, "R": False},
            hedge_ratio=0.0,
        )

    words = list(jieba.cut(answer))
    total_words = max(len(words), 1)

    required: list[str] = rubric.get("required", [])
    bonus: list[str] = rubric.get("bonus", [])
    misconceptions: list[str] = rubric.get("misconceptions", [])

    required_hits = sum(1 for kw in required if kw in answer)
    bonus_hits = sum(1 for kw in bonus if kw in answer)
    misconception_hits = sum(1 for kw in misconceptions if kw in answer)

    star_scores = {
        letter: any(kw in answer for kw in kws)
        for letter, kws in STAR_KEYWORDS.items()
    }

    hedge_count = sum(1 for w in words if w in HEDGE_WORDS)

    return AnswerFeatures(
        required_hit_rate=required_hits / max(len(required), 1),
        bonus_hit_count=bonus_hits,
        misconception_count=misconception_hits,
        star_scores=star_scores,
        hedge_ratio=hedge_count / total_words,
    )
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_feature_extractor.py -v
```

Expected: all 9 tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add src/services/sep/ test/unit/sep/
git commit -m "feat(sep): implement Layer 2 feature extractor with tests"
```

---

## Task 4 — Layer 1 Algorithm: Ability Estimator (TDD)

**Files:**
- Create: `src/services/sep/ability_estimator.py`
- Create: `test/unit/sep/test_ability_estimator.py`

- [ ] **Step 1: Write failing tests**

Create `test/unit/sep/test_ability_estimator.py`:

```python
import pytest
from src.services.sep.ability_estimator import update_ability


def test_ability_increases_on_easy_correct():
    """Answering an easy question (diff=0.3) correctly should raise ability above 0.5."""
    theta = 0.5
    new_theta = update_ability(theta, question_difficulty=0.3, answer_score=1.0)
    assert new_theta > theta


def test_ability_decreases_on_hard_wrong():
    """Failing a hard question (diff=0.8) should lower ability below 0.5."""
    theta = 0.5
    new_theta = update_ability(theta, question_difficulty=0.8, answer_score=0.0)
    assert new_theta < theta


def test_ability_clamped_at_max():
    """Ability must never exceed 0.9."""
    theta = 0.88
    new_theta = update_ability(theta, question_difficulty=0.1, answer_score=1.0)
    assert new_theta <= 0.9


def test_ability_clamped_at_min():
    """Ability must never fall below 0.1."""
    theta = 0.12
    new_theta = update_ability(theta, question_difficulty=0.9, answer_score=0.0)
    assert new_theta >= 0.1


def test_moderate_answer_keeps_ability_close():
    """A 0.5 score on a difficulty=0.5 question leaves theta nearly unchanged."""
    theta = 0.5
    new_theta = update_ability(theta, question_difficulty=0.5, answer_score=0.5)
    assert abs(new_theta - theta) < 0.05


def test_output_is_float():
    result = update_ability(0.5, 0.5, 0.8)
    assert isinstance(result, float)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_ability_estimator.py -v
```

Expected: `ImportError: No module named 'src.services.sep.ability_estimator'`

- [ ] **Step 3: Implement `src/services/sep/ability_estimator.py`**

```python
from __future__ import annotations
import math


def update_ability(theta: float, question_difficulty: float, answer_score: float) -> float:
    """
    Bayesian IRT update: move theta toward answer_score, scaled by how surprising the result was.

    Args:
        theta: Current ability estimate in [0.1, 0.9].
        question_difficulty: Question difficulty in [0.1, 0.9].
        answer_score: Normalised answer quality in [0.0, 1.0] from AnswerFeatures.to_answer_score().

    Returns:
        Updated theta clamped to [0.1, 0.9].
    """
    expected = 1.0 / (1.0 + math.exp(-3.0 * (theta - question_difficulty)))
    error = answer_score - expected
    return max(0.1, min(0.9, theta + 0.3 * error))
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_ability_estimator.py -v
```

Expected: all 6 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/services/sep/ability_estimator.py test/unit/sep/test_ability_estimator.py
git commit -m "feat(sep): implement IRT ability estimator with tests"
```

---

## Task 5 — Layer 3: Rubric Engine (TDD)

**Files:**
- Create: `src/services/sep/rubric_engine.py`
- Create: `test/unit/sep/test_rubric_engine.py`

- [ ] **Step 1: Write failing tests**

Create `test/unit/sep/test_rubric_engine.py`:

```python
import pytest
from src.services.sep.feature_extractor import AnswerFeatures
from src.services.sep.rubric_engine import features_to_score_delta, POSITION_DIMENSION_MAP


def make_features(
    required_hit_rate=1.0,
    bonus_hit_count=0,
    misconception_count=0,
    star_scores=None,
    hedge_ratio=0.0,
) -> AnswerFeatures:
    return AnswerFeatures(
        required_hit_rate=required_hit_rate,
        bonus_hit_count=bonus_hit_count,
        misconception_count=misconception_count,
        star_scores=star_scores or {"S": False, "T": False, "A": False, "R": False},
        hedge_ratio=hedge_ratio,
    )


def test_perfect_required_hit_gives_max_required_score():
    features = make_features(required_hit_rate=1.0)
    delta, evidence = features_to_score_delta(features)
    required_ev = next(e for e in evidence if e["evidence_type"] == "keyword_hit")
    assert required_ev["score_delta"] == 15


def test_zero_required_hit_gives_zero():
    features = make_features(required_hit_rate=0.0)
    delta, evidence = features_to_score_delta(features)
    keyword_evs = [e for e in evidence if e["evidence_type"] == "keyword_hit"]
    assert len(keyword_evs) == 0 or all(e["score_delta"] == 0 for e in keyword_evs)


def test_misconception_gives_negative_delta():
    features = make_features(misconception_count=1)
    delta, evidence = features_to_score_delta(features)
    misc_ev = next(e for e in evidence if e["evidence_type"] == "misconception")
    assert misc_ev["score_delta"] < 0


def test_misconception_capped_at_minus_fifteen():
    features = make_features(misconception_count=5)
    delta, evidence = features_to_score_delta(features)
    misc_ev = next(e for e in evidence if e["evidence_type"] == "misconception")
    assert misc_ev["score_delta"] >= -15


def test_full_star_gives_positive_delta():
    features = make_features(star_scores={"S": True, "T": True, "A": True, "R": True})
    delta, evidence = features_to_score_delta(features)
    star_ev = next(e for e in evidence if e["evidence_type"] == "star_complete")
    assert star_ev["score_delta"] == 8


def test_high_hedge_gives_negative_delta():
    features = make_features(hedge_ratio=0.3)
    delta, evidence = features_to_score_delta(features)
    hedge_ev = next(e for e in evidence if e["evidence_type"] == "hedge")
    assert hedge_ev["score_delta"] < 0


def test_low_hedge_has_no_evidence():
    features = make_features(hedge_ratio=0.02)
    _, evidence = features_to_score_delta(features)
    assert not any(e["evidence_type"] == "hedge" for e in evidence)


def test_bonus_capped_at_ten():
    features = make_features(bonus_hit_count=10)
    _, evidence = features_to_score_delta(features)
    bonus_ev = next(e for e in evidence if e["evidence_type"] == "bonus_keyword")
    assert bonus_ev["score_delta"] <= 10


def test_position_dimension_map_has_backend():
    assert "backend" in POSITION_DIMENSION_MAP
    assert "networking" in POSITION_DIMENSION_MAP["backend"]
    assert POSITION_DIMENSION_MAP["backend"]["networking"] == "technical_competence"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_rubric_engine.py -v
```

Expected: `ImportError: No module named 'src.services.sep.rubric_engine'`

- [ ] **Step 3: Implement `src/services/sep/rubric_engine.py`**

```python
from __future__ import annotations

from src.services.sep.feature_extractor import AnswerFeatures

POSITION_DIMENSION_MAP: dict[str, dict[str, str]] = {
    "backend": {
        "networking": "technical_competence",
        "database": "technical_competence",
        "algorithms": "problem_solving",
        "system_design": "problem_solving",
        "language": "technical_competence",
        "behavioral": "soft_skills",
    },
    "frontend": {
        "javascript": "technical_competence",
        "css": "technical_competence",
        "frameworks": "technical_competence",
        "algorithms": "problem_solving",
        "performance": "problem_solving",
        "behavioral": "soft_skills",
    },
    "algorithm": {
        "algorithms": "problem_solving",
        "data_structures": "problem_solving",
        "math": "technical_competence",
        "system_design": "technical_competence",
        "behavioral": "soft_skills",
    },
}


def features_to_score_delta(features: AnswerFeatures) -> tuple[int, list[dict]]:
    """
    Convert an AnswerFeatures into a (total_delta, evidence_items) pair.

    Returns:
        total_delta: int to be added to a 50-point baseline to get raw score.
        evidence_items: list of dicts with keys evidence_type, score_delta, evidence_text.
    """
    evidence: list[dict] = []
    total_delta = 0

    # Required keyword coverage: max +15
    req_score = round(features.required_hit_rate * 15)
    if req_score > 0:
        total_delta += req_score
        evidence.append({
            "evidence_type": "keyword_hit",
            "score_delta": req_score,
            "evidence_text": f"覆盖了 {round(features.required_hit_rate * 100)}% 的核心知识点",
        })

    # Bonus keyword hits: max +10
    if features.bonus_hit_count > 0:
        bonus_score = min(10, features.bonus_hit_count * 3)
        total_delta += bonus_score
        evidence.append({
            "evidence_type": "bonus_keyword",
            "score_delta": bonus_score,
            "evidence_text": f"提及了 {features.bonus_hit_count} 个加分知识点",
        })

    # Misconception penalty: max -15
    if features.misconception_count > 0:
        penalty = -min(15, features.misconception_count * 8)
        total_delta += penalty
        evidence.append({
            "evidence_type": "misconception",
            "score_delta": penalty,
            "evidence_text": f"包含 {features.misconception_count} 处概念误区",
        })

    # STAR structure: max +8
    star_count = sum(features.star_scores.values())
    star_score = round(star_count / 4 * 8)
    if star_score > 0:
        total_delta += star_score
        completed = [k for k, v in features.star_scores.items() if v]
        evidence.append({
            "evidence_type": "star_complete",
            "score_delta": star_score,
            "evidence_text": f"回答包含 STAR 结构中的 {'/'.join(completed)} 部分",
        })

    # Hedge penalty: triggered only above 5% hedge ratio
    if features.hedge_ratio > 0.05:
        hedge_penalty = -round(features.hedge_ratio * 5)
        if hedge_penalty != 0:
            total_delta += hedge_penalty
            evidence.append({
                "evidence_type": "hedge",
                "score_delta": hedge_penalty,
                "evidence_text": f"表达中含有较多不确定词（{round(features.hedge_ratio * 100)}%）",
            })

    return total_delta, evidence
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_rubric_engine.py -v
```

Expected: all 9 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/services/sep/rubric_engine.py test/unit/sep/test_rubric_engine.py
git commit -m "feat(sep): implement rubric engine with position-dimension mapping and tests"
```

---

## Task 6 — Layer 3: Evidence Builder (TDD)

**Files:**
- Create: `src/services/sep/evidence_builder.py`
- Create: `test/unit/sep/test_evidence_builder.py`

- [ ] **Step 1: Write failing tests**

Create `test/unit/sep/test_evidence_builder.py`:

```python
import pytest
from src.services.sep.feature_extractor import AnswerFeatures
from src.services.sep.evidence_builder import EvidenceItem, EvaluationReport, build_evidence_chain


def perfect_features() -> AnswerFeatures:
    return AnswerFeatures(
        required_hit_rate=1.0,
        bonus_hit_count=2,
        misconception_count=0,
        star_scores={"S": True, "T": True, "A": True, "R": True},
        hedge_ratio=0.0,
    )


def poor_features() -> AnswerFeatures:
    return AnswerFeatures(
        required_hit_rate=0.0,
        bonus_hit_count=0,
        misconception_count=2,
        star_scores={"S": False, "T": False, "A": False, "R": False},
        hedge_ratio=0.4,
    )


SAMPLE_QUESTIONS = [
    {"id": "net-001", "domain": "networking", "concept": "TCP握手", "question_template": "解释TCP三次握手", "difficulty": 0.5},
    {"id": "algo-001", "domain": "algorithms", "concept": "排序", "question_template": "比较排序算法", "difficulty": 0.6},
]


def test_report_has_overall_score():
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.6, 0.7],
    )
    assert isinstance(report.overall, int)
    assert 0 <= report.overall <= 100


def test_perfect_answers_give_high_score():
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.6, 0.7],
    )
    assert report.overall > 70


def test_poor_answers_give_low_score():
    report = build_evidence_chain(
        [poor_features(), poor_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.4, 0.3],
    )
    assert report.overall < 50


def test_evidence_chain_is_non_empty():
    report = build_evidence_chain(
        [perfect_features()],
        SAMPLE_QUESTIONS[:1],
        position="backend",
        theta_trajectory=[0.5, 0.6],
    )
    assert len(report.evidence_chain) > 0


def test_evidence_item_has_required_fields():
    report = build_evidence_chain(
        [perfect_features()],
        SAMPLE_QUESTIONS[:1],
        position="backend",
        theta_trajectory=[0.5, 0.6],
    )
    item = report.evidence_chain[0]
    assert hasattr(item, "dimension")
    assert hasattr(item, "question")
    assert hasattr(item, "concept")
    assert hasattr(item, "score_delta")
    assert hasattr(item, "evidence_text")
    assert hasattr(item, "evidence_type")


def test_dimensions_keys_are_valid():
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=[0.5, 0.6, 0.7],
    )
    valid = {"technical_competence", "problem_solving", "communication", "soft_skills"}
    assert all(k in valid for k in report.dimensions)


def test_theta_trajectory_preserved():
    trajectory = [0.5, 0.6, 0.7]
    report = build_evidence_chain(
        [perfect_features(), perfect_features()],
        SAMPLE_QUESTIONS,
        position="backend",
        theta_trajectory=trajectory,
    )
    assert report.theta_trajectory == trajectory
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_evidence_builder.py -v
```

Expected: `ImportError: No module named 'src.services.sep.evidence_builder'`

- [ ] **Step 3: Implement `src/services/sep/evidence_builder.py`**

```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean

from src.services.sep.feature_extractor import AnswerFeatures
from src.services.sep.rubric_engine import POSITION_DIMENSION_MAP, features_to_score_delta


@dataclass
class EvidenceItem:
    dimension: str
    question: str
    concept: str
    score_delta: int
    evidence_text: str
    evidence_type: str


@dataclass
class EvaluationReport:
    overall: int
    dimensions: dict[str, int]
    evidence_chain: list[EvidenceItem]
    theta_trajectory: list[float]


def build_evidence_chain(
    answers: list[AnswerFeatures],
    questions: list[dict],
    position: str,
    theta_trajectory: list[float],
) -> EvaluationReport:
    dim_map = POSITION_DIMENSION_MAP.get(position, POSITION_DIMENSION_MAP["backend"])
    evidence_items: list[EvidenceItem] = []
    dimension_scores: dict[str, list[int]] = defaultdict(list)

    for features, question in zip(answers, questions):
        domain = question.get("domain", "behavioral")
        dimension = dim_map.get(domain, "soft_skills")
        delta, raw_evidence = features_to_score_delta(features)
        raw_score = max(0, min(100, 50 + delta))
        dimension_scores[dimension].append(raw_score)

        for ev in raw_evidence:
            evidence_items.append(EvidenceItem(
                dimension=dimension,
                question=question.get("question_template", ""),
                concept=question.get("concept", ""),
                score_delta=ev["score_delta"],
                evidence_text=ev["evidence_text"],
                evidence_type=ev["evidence_type"],
            ))

    final_dims = {d: round(mean(scores)) for d, scores in dimension_scores.items()}
    overall = round(sum(final_dims.values()) / max(len(final_dims), 1))

    return EvaluationReport(
        overall=overall,
        dimensions=final_dims,
        evidence_chain=evidence_items,
        theta_trajectory=theta_trajectory,
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_evidence_builder.py -v
```

Expected: all 7 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/services/sep/evidence_builder.py test/unit/sep/test_evidence_builder.py
git commit -m "feat(sep): implement evidence builder and EvaluationReport with tests"
```

---

## Task 7 — Layer 1: Adaptive Selector (TDD)

**Files:**
- Create: `src/services/sep/adaptive_selector.py`
- Create: `test/unit/sep/test_adaptive_selector.py`

- [ ] **Step 1: Write failing tests**

Create `test/unit/sep/test_adaptive_selector.py`:

```python
import pytest
from src.services.sep.adaptive_selector import select_next_question

BANK = [
    {"id": "a", "domain": "networking", "difficulty": 0.3},
    {"id": "b", "domain": "networking", "difficulty": 0.6},
    {"id": "c", "domain": "database",   "difficulty": 0.4},
    {"id": "d", "domain": "algorithms", "difficulty": 0.7},
    {"id": "e", "domain": "behavioral", "difficulty": 0.4},
]


def test_selects_closest_difficulty_to_theta():
    q = select_next_question(theta=0.35, asked_ids=set(), question_bank=BANK, asked_domains=set())
    # "a" has difficulty 0.3 — closest to 0.35
    assert q["id"] == "a"


def test_skips_asked_ids():
    q = select_next_question(theta=0.35, asked_ids={"a"}, question_bank=BANK, asked_domains=set())
    assert q["id"] != "a"


def test_prefers_uncovered_domain():
    # theta=0.35 → "a" (net, diff=0.3) is closest, but networking is already covered
    q = select_next_question(
        theta=0.35,
        asked_ids=set(),
        question_bank=BANK,
        asked_domains={"networking"},
    )
    assert q["domain"] != "networking"


def test_returns_none_when_bank_exhausted():
    all_ids = {q["id"] for q in BANK}
    q = select_next_question(theta=0.5, asked_ids=all_ids, question_bank=BANK, asked_domains=set())
    assert q is None


def test_returns_dict_with_required_keys():
    q = select_next_question(theta=0.5, asked_ids=set(), question_bank=BANK, asked_domains=set())
    assert "id" in q
    assert "domain" in q
    assert "difficulty" in q
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_adaptive_selector.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `src/services/sep/adaptive_selector.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

QUESTION_BANKS_DIR = Path(__file__).parent.parent.parent / "data" / "question_banks"


def load_question_bank(position: str) -> list[dict]:
    path = QUESTION_BANKS_DIR / f"{position}.json"
    if not path.exists():
        path = QUESTION_BANKS_DIR / "backend.json"
    return json.loads(path.read_text(encoding="utf-8"))


def select_next_question(
    theta: float,
    asked_ids: set[str],
    question_bank: list[dict],
    asked_domains: set[str],
) -> dict | None:
    candidates = [q for q in question_bank if q["id"] not in asked_ids]
    if not candidates:
        return None

    # Sort by closeness of difficulty to current ability estimate
    by_info = sorted(candidates, key=lambda q: abs(q["difficulty"] - theta))

    # Prefer questions from domains not yet covered
    uncovered = [q for q in by_info if q["domain"] not in asked_domains]
    return uncovered[0] if uncovered else by_info[0]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_adaptive_selector.py -v
```

Expected: all 5 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/services/sep/adaptive_selector.py test/unit/sep/test_adaptive_selector.py
git commit -m "feat(sep): implement adaptive question selector with tests"
```

---

## Task 8 — SEP Session Orchestrator + Integration Test

**Files:**
- Modify: `src/services/sep/__init__.py`
- Create: `test/unit/sep/test_sep_session.py`

- [ ] **Step 1: Write failing integration test**

Create `test/unit/sep/test_sep_session.py`:

```python
import pytest
from src.services.sep import SEPSession


def test_session_produces_report_after_answers():
    session = SEPSession(position="backend")
    for _ in range(5):
        q = session.next_question()
        if q is None:
            break
        session.record_answer(q, "SYN SYN-ACK ACK，三次握手，我实现过连接池，最终降低了延迟。")
    report = session.build_report()
    assert 0 <= report.overall <= 100
    assert len(report.evidence_chain) > 0


def test_theta_updates_with_each_answer():
    session = SEPSession(position="backend")
    q = session.next_question()
    initial_theta = session.theta
    session.record_answer(q, "SYN SYN-ACK ACK TIME_WAIT 半连接队列全部覆盖。")
    assert session.theta != initial_theta


def test_asked_ids_tracked():
    session = SEPSession(position="backend")
    q = session.next_question()
    session.record_answer(q, "some answer")
    assert q["id"] in session.asked_ids


def test_theta_trajectory_grows():
    session = SEPSession(position="backend")
    q = session.next_question()
    session.record_answer(q, "SYN SYN-ACK ACK")
    assert len(session.theta_trajectory) == 2  # initial + after first answer


def test_no_duplicate_questions():
    session = SEPSession(position="backend")
    seen = set()
    for _ in range(10):
        q = session.next_question()
        if q is None:
            break
        assert q["id"] not in seen
        seen.add(q["id"])
        session.record_answer(q, "answer")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/test_sep_session.py -v
```

Expected: `ImportError` because `SEPSession` not yet defined.

- [ ] **Step 3: Implement `src/services/sep/__init__.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from src.services.sep.ability_estimator import update_ability
from src.services.sep.adaptive_selector import load_question_bank, select_next_question
from src.services.sep.evidence_builder import EvaluationReport, build_evidence_chain
from src.services.sep.feature_extractor import extract_features

__all__ = ["SEPSession"]


@dataclass
class SEPSession:
    position: str
    theta: float = 0.5
    asked_ids: set[str] = field(default_factory=set)
    asked_domains: set[str] = field(default_factory=set)
    _answer_features: list = field(default_factory=list, repr=False)
    _answered_questions: list = field(default_factory=list, repr=False)
    theta_trajectory: list[float] = field(default_factory=lambda: [0.5])
    _question_bank: list[dict] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._question_bank = load_question_bank(self.position)

    def next_question(self) -> dict | None:
        return select_next_question(
            self.theta,
            self.asked_ids,
            self._question_bank,
            self.asked_domains,
        )

    def record_answer(self, question: dict, answer_text: str) -> None:
        features = extract_features(answer_text, question.get("rubric", {}))
        answer_score = features.to_answer_score()
        self.theta = update_ability(self.theta, question["difficulty"], answer_score)
        self.theta_trajectory.append(round(self.theta, 4))
        self.asked_ids.add(question["id"])
        self.asked_domains.add(question["domain"])
        self._answer_features.append(features)
        self._answered_questions.append(question)

    def build_report(self) -> EvaluationReport:
        return build_evidence_chain(
            self._answer_features,
            self._answered_questions,
            self.position,
            self.theta_trajectory,
        )
```

- [ ] **Step 4: Run all SEP tests**

```bash
docker compose exec api uv run --group test pytest test/unit/sep/ -v
```

Expected: all tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add src/services/sep/__init__.py test/unit/sep/test_sep_session.py
git commit -m "feat(sep): implement SEPSession orchestrator with integration tests"
```

---

## Task 9 — Backend Integration: SEP Scoring in Result Service

**Files:**
- Modify: `src/services/interview_result_service.py` (around line 1521 — `_build_result_from_message`)

The goal is to wire the SEP `EvaluationReport` into the existing result data structure so the
frontend can display `evidence_chain` and `theta_trajectory`.

- [ ] **Step 1: Read the existing `_build_result_from_message` function**

Open `src/services/interview_result_service.py` and locate `_build_result_from_message` at
line ~1521. It currently returns a dict with keys:
`status`, `generated_at`, `source_message_id`, `summary_markdown`, `scorecard`,
`report_highlights`, `improvement_plan`, `technical_question_reviews`.

- [ ] **Step 2: Add a helper that converts `EvaluationReport` to the scorecard shape**

Add this function **before** `_build_result_from_message` in
`src/services/interview_result_service.py`:

```python
def _scorecard_from_sep_report(sep_report: "EvaluationReport") -> dict[str, Any]:
    """Convert a SEP EvaluationReport into the scorecard dict expected by the frontend."""
    from src.services.sep.evidence_builder import EvaluationReport  # local import avoids circular
    dimensions = [
        {"key": k, "name": DIMENSION_LABELS.get(k, k), "score": v}
        for k, v in sep_report.dimensions.items()
    ]
    return {
        "overall": sep_report.overall,
        "dimensions": dimensions,
        "strengths": [],
        "risks": [],
        "suggestions": [],
        "summary": "",
        # SEP-specific extras consumed by new frontend components
        "sep_evidence_chain": [
            {
                "dimension": item.dimension,
                "question": item.question,
                "concept": item.concept,
                "score_delta": item.score_delta,
                "evidence_text": item.evidence_text,
                "evidence_type": item.evidence_type,
            }
            for item in sep_report.evidence_chain
        ],
        "sep_theta_trajectory": sep_report.theta_trajectory,
    }
```

- [ ] **Step 3: Attach SEP data to conversation metadata when a SEPSession is active**

In `src/services/interview_result_service.py`, locate the function
`_normalize_result_payload` (line ~1544). At the end of it, before the `return stored_result`
line, add:

```python
    # Attach SEP data if present in metadata
    sep_evidence = value.get("sep_evidence_chain")
    sep_trajectory = value.get("sep_theta_trajectory")
    if sep_evidence is not None:
        stored_result["scorecard"] = stored_result.get("scorecard") or {}
        stored_result["scorecard"]["sep_evidence_chain"] = sep_evidence
        stored_result["scorecard"]["sep_theta_trajectory"] = sep_trajectory or []
```

- [ ] **Step 4: Verify lint passes**

```bash
make lint
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add src/services/interview_result_service.py
git commit -m "feat(sep): wire SEP evidence chain and theta trajectory into result payload"
```

---

## Task 10 — Frontend: EvidenceChain.vue

**Files:**
- Create: `web/src/components/sep/EvidenceChain.vue`

- [ ] **Step 1: Create directory**

```bash
mkdir -p web/src/components/sep
```

- [ ] **Step 2: Create `web/src/components/sep/EvidenceChain.vue`**

```vue
<template>
  <div class="evidence-chain">
    <div v-if="!items.length" class="evidence-empty">暂无证据条目</div>

    <div
      v-for="(item, idx) in items"
      :key="`${item.concept}-${idx}`"
      class="evidence-item"
    >
      <div class="evidence-header">
        <div class="evidence-header-left">
          <span class="evidence-concept">{{ item.concept }}</span>
          <a-tag color="default" size="small">{{ dimensionLabel(item.dimension) }}</a-tag>
        </div>
        <span
          :class="['evidence-delta', item.score_delta >= 0 ? 'positive' : 'negative']"
        >
          {{ item.score_delta >= 0 ? '+' : '' }}{{ item.score_delta }}
        </span>
      </div>

      <div class="evidence-text">{{ item.evidence_text }}</div>

      <div class="evidence-question">
        <span class="evidence-question-label">题目：</span>{{ item.question }}
      </div>
    </div>
  </div>
</template>

<script setup>
const DIMENSION_LABELS = {
  technical_competence: '技术能力',
  problem_solving: '问题解决',
  communication: '沟通表达',
  soft_skills: '综合素质',
}

defineProps({
  items: { type: Array, default: () => [] },
})

function dimensionLabel(key) {
  return DIMENSION_LABELS[key] ?? key
}
</script>

<style scoped>
.evidence-chain {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-empty {
  color: var(--color-text-tertiary, #999);
  font-size: 13px;
  padding: 12px 0;
}

.evidence-item {
  border: 1px solid var(--color-border, #e8e8e8);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--color-bg-base, #fff);
  transition: border-color 0.2s;
}

.evidence-item:hover {
  border-color: var(--color-primary, #1677ff);
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.evidence-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evidence-concept {
  font-weight: 600;
  font-size: 13px;
}

.evidence-delta {
  font-weight: 700;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.evidence-delta.positive {
  color: #52c41a;
}

.evidence-delta.negative {
  color: #ff4d4f;
}

.evidence-text {
  font-size: 13px;
  color: var(--color-text-secondary, #555);
  margin-bottom: 6px;
  line-height: 1.5;
}

.evidence-question {
  font-size: 12px;
  color: var(--color-text-tertiary, #999);
}

.evidence-question-label {
  font-weight: 500;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/sep/EvidenceChain.vue
git commit -m "feat(sep): add EvidenceChain frontend component"
```

---

## Task 11 — Frontend: AdaptiveTrajectory.vue

**Files:**
- Create: `web/src/components/sep/AdaptiveTrajectory.vue`

- [ ] **Step 1: Create `web/src/components/sep/AdaptiveTrajectory.vue`**

```vue
<template>
  <div class="adaptive-trajectory">
    <div class="trajectory-header">
      <span class="trajectory-title">自适应难度轨迹</span>
      <span class="trajectory-hint">纵轴为当前能力估计 θ，点的大小为题目难度</span>
    </div>
    <div ref="chartEl" class="trajectory-chart" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watchEffect } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  // Array of theta values: [initial, after_q1, after_q2, ...]
  trajectory: { type: Array, default: () => [] },
  // Array of question objects with { concept, difficulty }
  questions: { type: Array, default: () => [] },
})

const chartEl = ref(null)
let chart = null

function buildOption() {
  const labels = ['起始', ...props.questions.map((q, i) => `Q${i + 1}: ${q.concept ?? ''}`)]
  const values = props.trajectory.map((v, i) => ({
    value: v,
    symbolSize: i === 0 ? 8 : Math.round((props.questions[i - 1]?.difficulty ?? 0.5) * 24) + 4,
  }))

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        const qIdx = p.dataIndex - 1
        const q = props.questions[qIdx]
        const diffText = q ? `难度 ${q.difficulty}` : '初始值'
        return `${p.name}<br/>θ = ${p.value}<br/>${diffText}`
      },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 40 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { fontSize: 11, rotate: props.questions.length > 5 ? 20 : 0 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      name: 'θ',
      nameTextStyle: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed' } },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: 0.4,
        lineStyle: { width: 2, color: '#1677ff' },
        itemStyle: { color: '#1677ff' },
        markLine: {
          silent: true,
          data: [{ yAxis: 0.5, lineStyle: { type: 'dashed', color: '#aaa' } }],
          label: { formatter: '平均水平' },
        },
      },
    ],
  }
}

onMounted(() => {
  if (!chartEl.value) return
  chart = echarts.init(chartEl.value)
  watchEffect(() => {
    chart?.setOption(buildOption(), { notMerge: true })
  })
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  window.removeEventListener('resize', () => chart?.resize())
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.adaptive-trajectory {
  width: 100%;
}

.trajectory-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}

.trajectory-title {
  font-weight: 600;
  font-size: 13px;
}

.trajectory-hint {
  font-size: 11px;
  color: var(--color-text-tertiary, #999);
}

.trajectory-chart {
  height: 200px;
  width: 100%;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/components/sep/AdaptiveTrajectory.vue
git commit -m "feat(sep): add AdaptiveTrajectory ECharts component"
```

---

## Task 12 — Frontend: Wire SEP Components into InterviewResultView

**Files:**
- Modify: `web/src/views/InterviewResultView.vue`

The evidence section is around line 153–270. We insert SEP components inside
`#section-evidence`, between the `evidence-overview` (dimension score bars) and
the `evidence-subsection` for expression metrics.

- [ ] **Step 1: Add imports at the top of the `<script setup>` block**

Find the line in `InterviewResultView.vue` that starts the `<script setup>` section. After
the existing `import` statements, add:

```js
import EvidenceChain from '@/components/sep/EvidenceChain.vue'
import AdaptiveTrajectory from '@/components/sep/AdaptiveTrajectory.vue'
```

- [ ] **Step 2: Add computed properties for SEP data**

In the `<script setup>` section, after the existing `dimensionScoreCards` computed, add:

```js
const sepEvidenceChain = computed(() =>
  Array.isArray(scorecard.value?.sep_evidence_chain)
    ? scorecard.value.sep_evidence_chain
    : []
)

const sepThetaTrajectory = computed(() =>
  Array.isArray(scorecard.value?.sep_theta_trajectory)
    ? scorecard.value.sep_theta_trajectory
    : []
)

const sepQuestions = computed(() =>
  sepEvidenceChain.value
    .filter((item, idx, arr) => arr.findIndex(i => i.question === item.question) === idx)
    .map(item => ({ concept: item.concept, difficulty: null }))
)
```

- [ ] **Step 3: Insert SEP components into the template**

In the `<template>`, find the block:

```html
<div class="evidence-overview">
  <article v-for="item in dimensionScoreCards" ...>
```

Immediately **after** the closing `</div>` of `evidence-overview`, add:

```html
<!-- SEP: Adaptive difficulty trajectory -->
<div v-if="sepThetaTrajectory.length > 1" class="evidence-subsection">
  <div class="subsection-title">自适应难度轨迹</div>
  <AdaptiveTrajectory
    :trajectory="sepThetaTrajectory"
    :questions="sepQuestions"
  />
</div>

<!-- SEP: Evidence chain -->
<div v-if="sepEvidenceChain.length" class="evidence-subsection">
  <div class="subsection-title">评分证据链</div>
  <div class="subsection-subtitle">每一分的来源都有迹可查</div>
  <EvidenceChain :items="sepEvidenceChain" />
</div>
```

- [ ] **Step 4: Add `.subsection-subtitle` style** (if not already present)

In the `<style scoped>` section, add:

```css
.subsection-subtitle {
  font-size: 12px;
  color: var(--color-text-tertiary, #999);
  margin-bottom: 10px;
  margin-top: -4px;
}
```

- [ ] **Step 5: Run the frontend dev server and verify the page loads without errors**

```bash
docker compose logs web-dev -f --tail 50
```

Expected: no compilation errors. Open `http://localhost:5173` in browser. Navigate to an
existing interview result page. The evidence chain and trajectory sections should render
(or be hidden if `sep_evidence_chain` is empty — which is expected for old results).

- [ ] **Step 6: Commit**

```bash
git add web/src/views/InterviewResultView.vue
git commit -m "feat(sep): wire EvidenceChain and AdaptiveTrajectory into result view"
```

---

## Task 13 — Fix Issue 2.7: Remove Duplicate Highlights in Sidebar

**Files:**
- Modify: `web/src/views/InterviewResultView.vue`

Currently the sidebar renders `scorecard.strengths` even when `reportHighlights`
contains the same information. This task suppresses the duplicate.

- [ ] **Step 1: Find the sidebar strengths block**

In `InterviewResultView.vue`, find:

```html
<div v-if="scorecard?.strengths?.length" class="report-panel report-side-card">
  <div class="subsection-title">亮点</div>
  <ul class="report-list">
    <li v-for="item in scorecard.strengths" :key="`strength-${item}`">{{ item }}</li>
  </ul>
</div>
```

- [ ] **Step 2: Add the deduplication condition**

Change only the `v-if` attribute — no other lines:

```html
<div
  v-if="scorecard?.strengths?.length && !reportHighlights.length"
  class="report-panel report-side-card"
>
  <div class="subsection-title">亮点</div>
  <ul class="report-list">
    <li v-for="item in scorecard.strengths" :key="`strength-${item}`">{{ item }}</li>
  </ul>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/views/InterviewResultView.vue
git commit -m "fix(ui): hide sidebar strengths when report_highlights present (issue 2.7)"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Layer 1 (Adaptive Selector): Tasks 7, 8
- ✅ Layer 2 (Feature Extractor): Task 3
- ✅ Layer 3 (Evidence Builder): Tasks 5, 6
- ✅ Ability Estimator: Task 4
- ✅ Question Banks: Task 2
- ✅ `jieba` dependency: Task 1
- ✅ SEP Session orchestrator: Task 8
- ✅ Backend integration into result service: Task 9
- ✅ `EvidenceChain.vue`: Task 10
- ✅ `AdaptiveTrajectory.vue`: Task 11
- ✅ InterviewResultView wiring: Task 12
- ✅ Duplicate highlights fix (Issue 2.7): Task 13
- ⚠️ Issue 2.1 (scorecard extraction robustness): NOT in this plan —
  treat as a separate `src/services/interview_result_service.py` patch, can be
  done independently in < 1 hour by adding fallback paths to `_extract_scorecard`.

**Type consistency check:**
- `AnswerFeatures` defined in Task 3, consumed in Tasks 5, 6, 8 ✅
- `EvidenceItem` / `EvaluationReport` defined in Task 6, consumed in Tasks 8, 9 ✅
- `SEPSession` defined in Task 8, tested in Task 8 ✅
- `select_next_question` signature: `(theta, asked_ids, question_bank, asked_domains)` —
  consistent across Tasks 7 and 8 ✅
- `features_to_score_delta` returns `tuple[int, list[dict]]` — used consistently in Tasks 5 and 6 ✅

**Placeholder scan:** No TBD, TODO, or vague "add appropriate X" patterns found.
