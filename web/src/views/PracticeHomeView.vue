<template>
  <div class="ph-root">
    <!-- 顶栏 -->
    <header class="ph-top">
      <div class="ph-top__title">
        <h1>代码练习</h1>
        <p class="ph-sub">{{ subtitle }}</p>
      </div>
      <div class="ph-top__actions">
        <button type="button" class="ph-btn" @click="continueLastProblem">继续上次</button>
        <button type="button" class="ph-btn" @click="resetToAllTopics">全部题目</button>
        <button type="button" class="ph-btn ph-btn--primary" @click="randomProblem">随机一题</button>
      </div>
    </header>

    <!-- 四格统计 -->
    <div class="ph-stats">
      <div class="ph-stat">
        <span class="ph-lab">已完成</span>
        <span class="ph-num">{{ completedCount ?? '—' }}</span>
        <span class="ph-note">已练习 {{ practicedCount }} 题</span>
      </div>
      <div class="ph-stat">
        <span class="ph-lab">个人通过率</span>
        <span class="ph-num">{{ personalPassRate ?? '—' }}<span v-if="personalPassRate !== null" class="ph-num-suffix">%</span></span>
        <span class="ph-note">本机判题记录</span>
      </div>
      <div class="ph-stat">
        <span class="ph-lab">连续天数</span>
        <span class="ph-num">{{ streakDays }}</span>
        <span class="ph-note">本机练习记录</span>
      </div>
      <div class="ph-stat">
        <span class="ph-lab">待练弱项</span>
        <span class="ph-num ph-num--accent">{{ pendingWeaknessCount }}</span>
        <span class="ph-note">已匹配专题的弱项数</span>
      </div>
    </div>

    <!-- Tab -->
    <div class="ph-tabs">
      <button
        v-for="tab in tabItems"
        :key="tab.key"
        type="button"
        class="ph-tab"
        :class="{ 'ph-tab--active': activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 筛选工具条 -->
    <div class="ph-toolbar">
      <div class="ph-search">
        <input v-model="filters.keyword" type="text" placeholder="搜索题目标题或专题标签" />
      </div>
      <div class="ph-filters">
        <div class="ph-fg">
          <span class="ph-fg-label">难度</span>
          <button
            v-for="item in difficultyOptions"
            :key="item.value"
            type="button"
            class="ph-chip"
            :class="{ active: filters.difficulty === item.value }"
            @click="filters.difficulty = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <div class="ph-fg">
          <span class="ph-fg-label">状态</span>
          <button
            v-for="item in statusOptions"
            :key="item.value"
            type="button"
            class="ph-chip"
            :class="{ active: filters.status === item.value }"
            @click="filters.status = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <div class="ph-fg">
          <span class="ph-fg-label">题面语言</span>
          <button
            v-for="item in languageOptions"
            :key="item.value"
            type="button"
            class="ph-chip"
            :class="{ active: filters.language === item.value }"
            @click="filters.language = item.value"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
      <div class="ph-toolbar__foot">
        <label class="ph-switch"><input v-model="showTags" type="checkbox" /> 显示标签</label>
        <span class="ph-count">当前 {{ filteredProblemCount }} 题 · {{ filteredTopics.length }} 个专题</span>
        <button type="button" class="ph-btn ph-btn--sm" @click="resetFilters">重置筛选</button>
      </div>
    </div>

    <!-- 状态区 -->
    <div v-if="loading" class="ph-state">
      <a-spin size="large" />
    </div>
    <div v-else-if="error" class="ph-state ph-state--error">
      <p>{{ error }}</p>
      <button type="button" class="ph-btn" @click="loadPlan">重试</button>
    </div>
    <div v-else-if="!topics.length" class="ph-state">
      <p>暂无题目</p>
    </div>
    <div v-else-if="!filteredTopics.length" class="ph-state">
      <p v-if="activeTab === 'weakness'">当前弱项未匹配到可用专题</p>
      <p v-else>当前筛选条件下暂无题目</p>
      <ul v-if="unresolvedWeakness.length" class="ph-unresolved">
        <li v-for="item in unresolvedWeakness" :key="item.query">未匹配：{{ item.label }}</li>
      </ul>
      <button v-if="activeTab === 'weakness'" type="button" class="ph-btn" @click="resetToAllTopics">
        查看全部题目
      </button>
    </div>

    <!-- 专题分组表格 -->
    <template v-else>
      <section
        v-for="topic in filteredTopics"
        :id="`topic-${topic.topic_key}`"
        :key="topic.topic_key"
        class="ph-topic"
      >
        <div class="ph-topic__hd">
          <span class="ph-topic__name">{{ topic.topic_name }}</span>
          <div class="ph-topic__meta">
            <span>{{ topicMetaNote(topic) }}</span>
            <button type="button" class="ph-btn ph-btn--sm" @click="startTopicPractice(topic)">继续本专题</button>
          </div>
        </div>
        <div class="ph-table-wrap">
          <table class="ph-table">
            <thead>
              <tr>
                <th>#</th>
                <th>题目</th>
                <th>难度</th>
                <th>专题</th>
                <th>通过率</th>
                <th class="ph-th--right">状态</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="problem in getVisibleProblems(topic)" :key="problem.problem_ref">
                <tr class="ph-row">
                  <td class="ph-cell--ref">{{ problem.problem_ref }}</td>
                  <td>
                    <div class="ph-title-cell">
                      <button type="button" class="ph-title-btn" @click="openProblem(problem)">{{ problem.title }}</button>
                      <button
                        type="button"
                        class="ph-fav-btn"
                        :class="{ active: isFavorite(problem) }"
                        @click.stop="toggleFavorite(problem)"
                      >
                        {{ isFavorite(problem) ? '★ 已收藏' : '☆ 收藏' }}
                      </button>
                      <button type="button" class="ph-preview-btn" @click.stop="toggleExpanded(problem.problem_ref)">
                        {{ isExpanded(problem.problem_ref) ? '收起' : '预览' }}
                      </button>
                    </div>
                  </td>
                  <td>{{ difficultyLabel(problem.difficulty_tag) }}</td>
                  <td class="ph-muted">{{ problem.primary_topic_tag || topic.topic_name }}</td>
                  <td class="ph-muted">
                    {{ demoPassRate(problem) }}
                    <span class="ph-tip" title="题库暂未提供全站通过率，此值为按难度估算的演示数据">演示</span>
                  </td>
                  <td class="ph-th--right">
                    <span class="ph-status" :class="`ph-status--${problemStatus(problem)}`">
                      {{ problemStatusLabel(problem) }}
                    </span>
                  </td>
                </tr>
                <tr v-if="isExpanded(problem.problem_ref)" class="ph-preview-row">
                  <td></td>
                  <td colspan="5">
                    <p>{{ problem.summary || '暂无摘要' }}</p>
                    <div v-if="showTags && problem.topic_tags?.length" class="ph-tags">
                      <span v-for="tag in problem.topic_tags" :key="`${problem.problem_ref}-${tag}`" class="ph-tag">{{ tag }}</span>
                    </div>
                    <div class="ph-preview-meta">
                      <span>{{ languageLabel(problem.statement_language) }}</span>
                      <span v-if="problem.supports_online_judge">在线判题</span>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div v-if="canLoadMoreTopicProblems(topic)" class="ph-load-more">
          <button type="button" class="ph-btn ph-btn--sm" @click="loadMoreTopicProblems(topic.topic_key)">
            加载更多（{{ getVisibleProblemCount(topic.topic_key) }}/{{ topic.problems.length }}）
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

import { practiceApi } from '@/apis/practice_api'
import { interviewHistoryApi } from '@/apis/interview_history'
import { extractPersonalizedWeaknesses, matchWeaknessCandidates, parseWeaknessTokens } from '@/utils/weaknessPractice'
import {
  PROBLEM_STATUS,
  PROBLEM_STATUS_LABEL,
  emptyProgress,
  getProblemStatus,
  hasRealResult,
  loadProgress,
  markOpened,
  saveProgress,
} from '@/utils/practiceProgress'

const router = useRouter()
const route = useRoute()

const TOPIC_RENDER_BATCH_SIZE = 20

const loading = ref(false)
const error = ref('')
const plan = ref({})
const topics = ref([])
const showTags = ref(true)
const activeTab = ref('all')
const expandedRefs = ref(new Set())
const topicPanelState = reactive({})

// 弱项上下文：来自 URL（报告 CTA）或个性化路线（直接访问 fallback）
const weaknessCandidates = ref([])
const weaknessSource = ref('') // 'report' | 'personalized' | ''

const progress = ref(emptyProgress())

const filters = reactive({
  keyword: String(route.query.q || '').trim(),
  difficulty: 'all',
  status: 'all',
  language: 'all',
})

const tabItems = [
  { key: 'weakness', label: '按弱项推荐' },
  { key: 'all', label: '全部专题' },
  { key: 'failed', label: '未通过' },
  { key: 'favorite', label: '收藏' },
]

const difficultyLabelMap = { easy: '简单', medium: '中等', hard: '困难' }
const languageLabelMap = { zh: '中文题面', en: '英文题面', mixed: '中英混合', unknown: '未知题面' }

const difficultyOptions = [
  { label: '全部', value: 'all' },
  { label: '简单', value: 'easy' },
  { label: '中等', value: 'medium' },
  { label: '困难', value: 'hard' },
]

const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '未开始', value: PROBLEM_STATUS.NEW },
  { label: '练习中', value: PROBLEM_STATUS.ATTEMPTING },
  { label: '未通过', value: PROBLEM_STATUS.FAILED },
  { label: '已通过', value: PROBLEM_STATUS.PASSED },
  { label: '判题异常', value: PROBLEM_STATUS.ERROR },
  { label: '已收藏', value: 'favorite' },
]

const htmlDecoder =
  typeof window !== 'undefined' && typeof document !== 'undefined' ? document.createElement('textarea') : null

const decodeHtmlText = (value) => {
  let text = String(value || '')
  if (!text || !text.includes('&')) return text
  for (let index = 0; index < 3; index += 1) {
    const before = text
    if (htmlDecoder) {
      htmlDecoder.innerHTML = text
      text = htmlDecoder.value
    } else {
      text = text
        .replace(/&amp;/gi, '&')
        .replace(/&#x([0-9a-f]+);?/gi, (_, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
        .replace(/&#(\d+);?/g, (_, code) => String.fromCodePoint(Number.parseInt(code, 10)))
    }
    if (text === before) break
  }
  return text
}

const normalizeProblemItem = (problem) => ({
  ...problem,
  title: decodeHtmlText(problem?.title),
  summary: decodeHtmlText(problem?.summary),
  topic_tags: (problem?.topic_tags || []).map((tag) => decodeHtmlText(tag)),
})

const normalizeTopicItem = (topic) => ({
  ...topic,
  topic_name: decodeHtmlText(topic?.topic_name),
  problems: (topic?.problems || []).map((problem) => normalizeProblemItem(problem)),
})

const normalizePracticePayload = (payload) => ({
  plan: {
    ...(payload?.plan || {}),
    title: decodeHtmlText(payload?.plan?.title),
    description: decodeHtmlText(payload?.plan?.description),
  },
  topics: (payload?.topics || []).map((topic) => normalizeTopicItem(topic)),
})

const normalizeText = (value) => String(value || '').trim().toLowerCase()

const allProblems = computed(() => (topics.value || []).flatMap((topic) => topic.problems || []))

const problemRefMap = computed(() => {
  const map = new Map()
  for (const problem of allProblems.value) map.set(problem.problem_ref, problem)
  return map
})

const languageOptions = computed(() => {
  const values = new Set()
  for (const problem of allProblems.value) values.add(problem.statement_language || 'unknown')
  const base = [{ label: '全部', value: 'all' }]
  for (const key of ['zh', 'en', 'mixed', 'unknown']) {
    if (values.has(key)) base.push({ label: languageLabelMap[key], value: key })
  }
  return base
})

const difficultyLabel = (tag) => difficultyLabelMap[tag] || '中等'
const languageLabel = (lang) => languageLabelMap[lang] || '未知题面'

// ---------------------------------------------------------------------------
// 练习状态（五态）与收藏
// ---------------------------------------------------------------------------

const problemStatus = (problem) => getProblemStatus(progress.value, problem.problem_ref)
const problemStatusLabel = (problem) => PROBLEM_STATUS_LABEL[problemStatus(problem)] || '未知'

const isFavorite = (problem) => (progress.value.favorite_refs || []).includes(problem.problem_ref)

const toggleFavorite = (problem) => {
  const current = new Set(progress.value.favorite_refs || [])
  if (current.has(problem.problem_ref)) current.delete(problem.problem_ref)
  else current.add(problem.problem_ref)
  progress.value = { ...progress.value, favorite_refs: [...current] }
  saveProgress(progress.value)
}

const isExpanded = (problemRef) => expandedRefs.value.has(problemRef)

const toggleExpanded = (problemRef) => {
  const next = new Set(expandedRefs.value)
  if (next.has(problemRef)) next.delete(problemRef)
  else next.add(problemRef)
  expandedRefs.value = next
}

const openProblem = (problem) => {
  progress.value = markOpened(progress.value, problem.problem_ref)
  saveProgress(progress.value)
  router.push({
    name: 'PracticeProblemPage',
    params: { problem_ref: problem.problem_ref },
    query: problem.primary_topic_key ? { topic: problem.primary_topic_key } : {},
  })
}

// ---------------------------------------------------------------------------
// 弱项上下文解析
// ---------------------------------------------------------------------------

const hasRouteWeakness = computed(() => {
  const value = route.query.topic ?? route.query.q
  return value !== undefined && value !== null && String(value).trim() !== ''
})

const parsedUrlTokens = computed(() => parseWeaknessTokens(route.query.topic ?? route.query.q))

// URL 弱项优先作为候选来源（报告 CTA 直接带 topic 进来）
const urlWeaknessCandidates = computed(() =>
  parsedUrlTokens.value.map((token) => ({ query: token, label: token, type: 'report' })),
)

const weaknessMatch = computed(() =>
  matchWeaknessCandidates(
    hasRouteWeakness.value ? urlWeaknessCandidates.value : weaknessCandidates.value,
    topics.value,
  ),
)
const unresolvedWeakness = computed(() => weaknessMatch.value.unresolved)
const pendingWeaknessCount = computed(() => weaknessMatch.value.matchedTopicKeys.length)

const weaknessDisplayTokens = computed(() => {
  const names = weaknessMatch.value.matched
    .map((item) => {
      const topic = topics.value.find((t) => t.topic_key === item.topic_key)
      return topic ? topic.topic_name : item.label
    })
    .filter(Boolean)
  const pool = names.length ? names : parsedUrlTokens.value
  return pool.slice(0, 2)
})

const formatReportDate = (iso) => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${month}/${day}`
}

const subtitle = computed(() => {
  if (String(route.params.topic_key || '').trim()) {
    const topic = topics.value.find((t) => t.topic_key === route.params.topic_key)
    return topic ? `${topic.topic_name} · ${topic.problem_count} 题` : ''
  }
  if (activeTab.value === 'weakness') {
    const names = weaknessDisplayTokens.value.join('、')
    const more = weaknessMatch.value.matched.length > 2 ? ` 等 ${weaknessMatch.value.matched.length} 项` : ''
    if (weaknessSource.value === 'report') {
      const date = formatReportDate(String(route.query.reportAt || ''))
      const prefix = date ? `来自 ${date} 生成的面试报告` : '按报告弱项推荐'
      return names ? `${prefix}：${names}${more}` : prefix
    }
    if (weaknessSource.value === 'personalized') {
      return names ? `基于最近几轮面试的个性化路线：${names}${more}` : '基于最近几轮面试的个性化路线'
    }
  }
  return plan.value.description || '从已导入题库中按专题分段练习'
})

const topicMetaNote = (topic) => {
  if (activeTab.value === 'weakness') {
    const hits = weaknessMatch.value.matched.filter((item) => item.topic_key === topic.topic_key)
    return hits.length ? `来自报告弱项 · ${hits.length} 个来源` : '弱项推荐'
  }
  return '全部题目'
}

// ---------------------------------------------------------------------------
// Tab 数据集 → 筛选
// ---------------------------------------------------------------------------

const tabTopicFilter = computed(() => {
  if (activeTab.value === 'weakness') {
    const keys = new Set(weaknessMatch.value.matchedTopicKeys)
    return (topics.value || []).filter((topic) => keys.has(topic.topic_key))
  }
  if (activeTab.value === 'failed') {
    return (topics.value || [])
      .map((topic) => ({
        ...topic,
        problems: (topic.problems || []).filter((problem) => problemStatus(problem) === PROBLEM_STATUS.FAILED),
      }))
      .filter((topic) => topic.problems.length)
  }
  if (activeTab.value === 'favorite') {
    return (topics.value || [])
      .map((topic) => ({
        ...topic,
        problems: (topic.problems || []).filter((problem) => isFavorite(problem)),
      }))
      .filter((topic) => topic.problems.length)
  }
  return topics.value || []
})

const matchStatusFilter = (problem) => {
  if (filters.status === 'all') return true
  if (filters.status === 'favorite') return isFavorite(problem)
  return problemStatus(problem) === filters.status
}

const filteredTopics = computed(() => {
  const keyword = normalizeText(filters.keyword)
  return tabTopicFilter.value
    .map((topic) => ({
      ...topic,
      problems: (topic.problems || []).filter((problem) => {
        if (filters.difficulty !== 'all' && (problem.difficulty_tag || 'medium') !== filters.difficulty) return false
        if (filters.language !== 'all' && (problem.statement_language || 'unknown') !== filters.language) return false
        if (!matchStatusFilter(problem)) return false
        if (!keyword) return true
        const haystack = [problem.title, topic.topic_name, ...(problem.topic_tags || [])]
          .map(normalizeText)
          .join(' ')
        return haystack.includes(keyword)
      }),
    }))
    .filter((topic) => topic.problems.length)
})

const filteredProblemCount = computed(() =>
  filteredTopics.value.reduce((total, topic) => total + (topic.problems || []).length, 0),
)

// ---------------------------------------------------------------------------
// 统计
// ---------------------------------------------------------------------------

const practicedCount = computed(() => {
  const availableRefs = new Set(allProblems.value.map((problem) => problem.problem_ref))
  return Object.keys(progress.value.attempted_map || {}).filter((ref) => availableRefs.has(ref)).length
})

// 有真实判题终态的唯一次数；无历史时显示 —，小字保留"已练习 N 题"
const completedCount = computed(() => {
  const refs = [...new Set(allProblems.value.map((problem) => problem.problem_ref))]
  const withResult = refs.filter((ref) => hasRealResult(progress.value, ref))
  return withResult.length ? withResult.length : null
})

// 本机个人通过率：仅通过/未通过计入分母，排除练习中与判题异常
const personalPassRate = computed(() => {
  const refs = [...new Set(allProblems.value.map((problem) => problem.problem_ref))]
  const withResult = refs.filter((ref) => hasRealResult(progress.value, ref))
  if (!withResult.length) return null
  const passed = withResult.filter((ref) => getProblemStatus(progress.value, ref) === PROBLEM_STATUS.PASSED).length
  return Math.round((passed / withResult.length) * 100)
})

const streakDays = computed(() => {
  const daySet = new Set(Object.values(progress.value.attempted_map || {}).map((value) => String(value).slice(0, 10)))
  if (!daySet.size) return 0
  let streak = 0
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)
  const formatKey = (date) => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  while (daySet.has(formatKey(cursor))) {
    streak += 1
    cursor.setDate(cursor.getDate() - 1)
  }
  return streak
})

// 通过率列：题库暂未提供全站通过率，按难度给出稳定的演示值（用户已确认）。
const hashStr = (value) => {
  let hash = 0
  const text = String(value || '')
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  return hash
}

const demoPassRate = (problem) => {
  const base = { easy: 68, medium: 50, hard: 32 }[problem.difficulty_tag] ?? 50
  const spread = (hashStr(problem.problem_ref) % 17) - 8
  return `${Math.max(20, Math.min(90, base + spread))}%`
}

// ---------------------------------------------------------------------------
// 动作
// ---------------------------------------------------------------------------

const randomProblem = () => {
  const pool = filteredTopics.value.flatMap((topic) => topic.problems || [])
  if (!pool.length) {
    message.warning('当前条件下暂无可练习题目')
    return
  }
  const unattempted = pool.filter((problem) => problemStatus(problem) === PROBLEM_STATUS.NEW)
  const target = unattempted.length ? unattempted[Math.floor(Math.random() * unattempted.length)] : pool[0]
  openProblem(target)
}

const continueLastProblem = () => {
  const lastRef = String(progress.value.last_problem_ref || '').trim()
  const target = lastRef ? problemRefMap.value.get(lastRef) : null
  if (!target) {
    message.warning('暂未记录上次练习，请先开始一道题目')
    randomProblem()
    return
  }
  openProblem(target)
}

const startTopicPractice = (topic) => {
  const target =
    (topic.problems || []).find((problem) => problemStatus(problem) === PROBLEM_STATUS.NEW) || topic.problems?.[0]
  if (!target) {
    message.warning('该专题暂无可练习题目')
    return
  }
  openProblem(target)
}

const resetToAllTopics = () => {
  activeTab.value = 'all'
  router.replace({ name: 'PracticeHomePage' })
}

const switchTab = (key) => {
  activeTab.value = key
}

const resetFilters = () => {
  filters.keyword = ''
  filters.difficulty = 'all'
  filters.status = 'all'
  filters.language = 'all'
}

// ---------------------------------------------------------------------------
// 专题分组渲染（每专题加载更多）
// ---------------------------------------------------------------------------

const getTopicPanel = (topicKey) => {
  if (!topicPanelState[topicKey]) {
    topicPanelState[topicKey] = { visibleCount: TOPIC_RENDER_BATCH_SIZE }
  }
  return topicPanelState[topicKey]
}

const getVisibleProblems = (topic) => (topic.problems || []).slice(0, getTopicPanel(topic.topic_key).visibleCount)
const getVisibleProblemCount = (topicKey) => getTopicPanel(topicKey).visibleCount
const canLoadMoreTopicProblems = (topic) => getVisibleProblemCount(topic.topic_key) < (topic.problems || []).length
const loadMoreTopicProblems = (topicKey) => {
  getTopicPanel(topicKey).visibleCount += TOPIC_RENDER_BATCH_SIZE
}

const syncTopicPanels = (topicList) => {
  const keys = new Set((topicList || []).map((topic) => String(topic.topic_key || '')))
  for (const key of Object.keys(topicPanelState)) {
    if (!keys.has(key)) delete topicPanelState[key]
  }
  for (const topic of topicList || []) {
    const panel = getTopicPanel(topic.topic_key)
    if (!Number.isFinite(panel.visibleCount) || panel.visibleCount < TOPIC_RENDER_BATCH_SIZE) {
      panel.visibleCount = TOPIC_RENDER_BATCH_SIZE
    }
  }
}

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------

const loadPersonalizedWeakness = async () => {
  if (hasRouteWeakness.value || String(route.params.topic_key || '').trim()) return
  try {
    const data = await interviewHistoryApi.getPersonalizedPath()
    weaknessCandidates.value = extractPersonalizedWeaknesses(data)
    weaknessSource.value = 'personalized'
  } catch {
    weaknessCandidates.value = []
    weaknessSource.value = ''
  }
}

const initActiveTab = () => {
  if (String(route.params.topic_key || '').trim()) {
    activeTab.value = 'all'
    return
  }
  if (hasRouteWeakness.value) {
    weaknessSource.value = 'report'
    activeTab.value = 'weakness'
    return
  }
  activeTab.value = weaknessMatch.value.matchedTopicKeys.length ? 'weakness' : 'all'
}

const loadPlan = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await practiceApi.getDefaultPlan()
    const normalized = normalizePracticePayload(data)
    plan.value = normalized.plan
    topics.value = normalized.topics
    await loadPersonalizedWeakness()
    initActiveTab()
    syncTopicPanels(topics.value)
    await nextTick()
    syncTopicAnchor()
  } catch (err) {
    error.value = err.message || '加载练习题单失败'
  } finally {
    loading.value = false
  }
}

const syncTopicAnchor = async () => {
  const topicKey = String(route.params.topic_key || '').trim()
  if (!topicKey) return
  await nextTick()
  document.getElementById(`topic-${topicKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(
  () => route.params.topic_key,
  () => {
    if (route.params.topic_key) activeTab.value = 'all'
    if (topics.value.length) syncTopicAnchor()
  },
)

watch(
  filteredTopics,
  (list) => syncTopicPanels(list),
  { immediate: true },
)

onMounted(() => {
  progress.value = loadProgress()
  loadPlan()
})
</script>

<style lang="less" scoped>
.ph-root {
  height: 100%;
  overflow-y: auto;
  padding: 0 32px;
  font-size: 15px;
  color: var(--gray-1000);
}

/* 顶栏 */
.ph-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 26px 0 18px;
  border-bottom: 1px solid var(--gray-100);
}
.ph-top h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--gray-1000);
}
.ph-sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--gray-600);
}
.ph-top__actions {
  display: flex;
  gap: 10px;
}

/* 按钮 */
.ph-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  padding: 0 14px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-700);
  background: transparent;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  cursor: pointer;
  white-space: nowrap;
}
.ph-btn:hover {
  background: var(--gray-100);
}
.ph-btn:focus-visible {
  outline: 2px solid var(--main-600);
  outline-offset: 1px;
}
.ph-btn--primary {
  background: var(--main-600);
  border-color: var(--main-600);
  color: var(--main-0);
}
.ph-btn--primary:hover {
  background: var(--main-700);
}
.ph-btn--sm {
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
}

/* 四格统计 */
.ph-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-bottom: 1px solid var(--gray-200);
}
.ph-stat {
  padding: 20px 20px 20px 0;
}
.ph-stat + .ph-stat {
  border-left: 1px solid var(--gray-100);
  padding-left: 20px;
}
.ph-lab {
  display: block;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--gray-600);
}
.ph-num {
  display: block;
  margin-top: 6px;
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: var(--gray-1000);
}
.ph-num--accent {
  color: var(--main-600);
}
.ph-num-suffix {
  font-size: 20px;
}
.ph-note {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  font-weight: 400;
  color: var(--gray-500);
}

/* Tab */
.ph-tabs {
  display: flex;
  border-bottom: 1px solid var(--gray-200);
}
.ph-tab {
  padding: 12px 20px 11px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-600);
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}
.ph-tab:hover {
  color: var(--gray-1000);
}
.ph-tab--active {
  color: var(--gray-1000);
  border-bottom-color: var(--main-600);
}

/* 筛选工具条 */
.ph-toolbar {
  padding: 16px 0;
  border-bottom: 1px solid var(--gray-200);
}
.ph-search input {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  font: inherit;
  font-size: 14px;
  color: var(--gray-1000);
  background: var(--gray-10);
  border: 1px solid var(--gray-200);
  border-radius: 0;
}
.ph-search input::placeholder {
  color: var(--gray-500);
}
.ph-search input:focus-visible {
  outline: 2px solid var(--main-600);
  outline-offset: -1px;
}
.ph-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin-top: 12px;
}
.ph-fg {
  display: flex;
  align-items: center;
  gap: 4px;
}
.ph-fg-label {
  margin-right: 4px;
  font-size: 12px;
  color: var(--gray-600);
}
.ph-chip {
  padding: 5px 10px;
  font: inherit;
  font-size: 13px;
  color: var(--gray-600);
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
}
.ph-chip:hover {
  color: var(--gray-1000);
  background: var(--gray-100);
}
.ph-chip.active {
  color: var(--gray-1000);
  font-weight: 700;
  background: var(--gray-100);
}
.ph-toolbar__foot {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}
.ph-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--gray-600);
  cursor: pointer;
}
.ph-switch input {
  accent-color: var(--main-600);
}
.ph-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--gray-500);
}

/* 状态区 */
.ph-state {
  padding: 56px 0;
  text-align: center;
  color: var(--gray-600);
}
.ph-state p {
  margin: 0 0 16px;
}
.ph-state--error {
  color: var(--gray-700);
}
.ph-unresolved {
  margin: 12px 0 20px;
  padding: 0;
  list-style: none;
  font-size: 13px;
  color: var(--gray-500);
}

/* 专题分组 */
.ph-topic {
  padding: 26px 0;
  border-bottom: 1px solid var(--gray-200);
}
.ph-topic:last-child {
  border-bottom: 0;
}
.ph-topic__hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.ph-topic__name {
  font-size: 18px;
  font-weight: 800;
  color: var(--gray-1000);
}
.ph-topic__meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--gray-600);
}

/* 表格 */
.ph-table-wrap {
  overflow-x: auto;
}
.ph-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  font-size: 14px;
}
.ph-table th {
  padding: 8px 12px 8px 0;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--gray-600);
  border-bottom: 1px solid var(--gray-200);
  white-space: nowrap;
}
.ph-table td {
  padding: 12px 12px 12px 0;
  border-bottom: 1px solid var(--gray-100);
  vertical-align: top;
}
.ph-table tbody tr:hover {
  background: var(--gray-25);
}
.ph-th--right {
  text-align: right;
}
.ph-cell--ref {
  font-size: 13px;
  color: var(--gray-500);
  white-space: nowrap;
}
.ph-title-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ph-title-btn {
  padding: 0;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
  background: none;
  border: 0;
  cursor: pointer;
  text-align: left;
}
.ph-title-btn:hover {
  color: var(--main-600);
}
.ph-fav-btn,
.ph-preview-btn {
  padding: 0;
  font: inherit;
  font-size: 12px;
  color: var(--gray-500);
  background: none;
  border: 0;
  cursor: pointer;
  white-space: nowrap;
}
.ph-fav-btn:hover,
.ph-fav-btn.active {
  color: var(--main-600);
}
.ph-preview-btn:hover {
  color: var(--gray-1000);
}
.ph-muted {
  font-size: 13px;
  color: var(--gray-600);
}
.ph-tip {
  font-size: 11px;
  color: var(--gray-400);
  cursor: help;
}
.ph-status {
  display: inline-block;
  padding: 3px 8px;
  font-size: 12px;
  white-space: nowrap;
  border: 1px solid transparent;
}
.ph-status--new {
  color: var(--gray-500);
  border-color: var(--gray-300);
}
.ph-status--attempting {
  color: var(--main-800);
  border-color: var(--main-200);
  background: var(--main-50);
}
.ph-status--passed {
  color: var(--gray-1000);
  background: var(--gray-100);
}
.ph-status--failed {
  color: var(--main-0);
  background: var(--main-600);
  border-color: var(--main-600);
}
.ph-status--error {
  color: var(--color-error-500);
  border-color: var(--color-error-500);
}

/* 预览行 */
.ph-preview-row td {
  background: var(--gray-25);
}
.ph-preview-row p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-700);
}
.ph-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}
.ph-tag {
  padding: 2px 8px;
  font-size: 12px;
  color: var(--gray-700);
  background: var(--gray-100);
}
.ph-preview-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--gray-600);
}

.ph-load-more {
  margin-top: 12px;
}
</style>
