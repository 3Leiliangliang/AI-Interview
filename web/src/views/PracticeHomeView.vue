<template>
  <div class="practice-home">
    <section class="overview-card">
      <div class="overview-main">
        <span class="overview-eyebrow">算法专题练习</span>
        <h1>{{ plan.title || '代码练习' }}</h1>
        <p>
          {{ plan.description || '从已导入题库中按专题分段练习，支持样例运行和在线判题。' }}
        </p>
        <div class="overview-actions">
          <a-button type="primary" size="large" @click="startRecommendedProblem">
            <template #icon>
              <ThunderboltOutlined />
            </template>
            智能推荐练习
          </a-button>
          <a-button size="large" @click="continueLastProblem">
            <template #icon>
              <ClockCircleOutlined />
            </template>
            继续上次进度
          </a-button>
          <a-button size="large" @click="focusFavoriteProblems">
            <template #icon>
              <StarOutlined />
            </template>
            收藏题目
          </a-button>
        </div>
      </div>

      <div class="overview-stats">
        <div class="metric-card">
          <div class="metric-label">已练习</div>
          <div class="metric-value">{{ practicedCount }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">待练习</div>
          <div class="metric-value">{{ pendingCount }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">今日目标</div>
          <div class="metric-value">{{ todayProgress }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">连续打卡</div>
          <div class="metric-value">{{ streakDays }}天</div>
        </div>
      </div>

      <div class="recommend-row">
        <div class="recommend-info">
          <span class="recommend-label">推荐题目</span>
          <strong>{{ recommendedProblem?.title || '暂无推荐题目' }}</strong>
          <span v-if="recommendedProblem" class="recommend-meta">
            #{{ recommendedProblem.problem_index }} · {{ recommendedProblem.primary_topic_tag }}
          </span>
        </div>
        <a-button v-if="recommendedProblem" type="link" @click="openProblem(recommendedProblem)">
          去练习
          <RightOutlined />
        </a-button>
      </div>
    </section>

    <section class="filter-card">
      <a-input v-model:value="filters.keyword" allow-clear size="large" placeholder="搜索题目标题或专题标签">
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input>

      <div class="filter-group">
        <span class="filter-label">难度</span>
        <button
          v-for="item in difficultyOptions"
          :key="item.value"
          type="button"
          class="filter-chip"
          :class="{ active: filters.difficulty === item.value }"
          @click="filters.difficulty = item.value"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="filter-group">
        <span class="filter-label">状态</span>
        <button
          v-for="item in statusOptions"
          :key="item.value"
          type="button"
          class="filter-chip"
          :class="{ active: filters.status === item.value }"
          @click="filters.status = item.value"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="filter-group compact">
        <span class="filter-label">题面语言</span>
        <button
          v-for="item in languageOptions"
          :key="item.value"
          type="button"
          class="filter-chip"
          :class="{ active: filters.language === item.value }"
          @click="filters.language = item.value"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="filter-footer">
        <a-switch v-model:checked="showTags" />
        <span class="switch-label">显示标签</span>
        <span class="filter-summary">当前显示 {{ filteredProblemCount }} 道题 · {{ filteredTopics.length }} 个专题</span>
        <a-button size="small" @click="resetFilters">重置筛选</a-button>
      </div>
    </section>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
    </div>

    <div v-else-if="!filteredProblemCount" class="state-panel">
      <a-empty description="当前筛选条件下暂无题目" />
    </div>

    <template v-else>
      <section class="topic-cloud-card">
        <div class="topic-cloud-header">
          <div>
            <span class="cloud-title">专题热度</span>
            <h2>按题量分层浏览专题</h2>
          </div>
          <a-button type="link" @click="showAllTopicRows = !showAllTopicRows">
            {{ showAllTopicRows ? '收起' : '展开全部' }}
          </a-button>
        </div>

        <button
          v-for="topic in visibleTopicRows"
          :key="`cloud-${topic.topic_key}`"
          type="button"
          class="topic-cloud-row"
          :class="topic.tierClass"
          @click="goToTopic(topic.topic_key)"
        >
          <div class="topic-cloud-name">
            <span>{{ topic.topic_name }}</span>
            <small>{{ topic.problem_count }}题</small>
          </div>
          <div class="topic-cloud-bar">
            <div class="topic-cloud-fill" :style="{ width: `${topic.percent}%` }" />
          </div>
          <span class="topic-cloud-tier">{{ topic.tierLabel }}</span>
        </button>
      </section>

      <div class="topic-nav">
        <button
          v-for="topic in filteredTopics"
          :key="topic.topic_key"
          type="button"
          class="topic-chip"
          :class="{ active: topic.topic_key === activeTopicKey }"
          @click="goToTopic(topic.topic_key)"
        >
          {{ topic.topic_name }} · {{ topic.problem_count }}
        </button>
      </div>

      <section
        v-for="topic in filteredTopics"
        :id="`topic-${topic.topic_key}`"
        :key="topic.topic_key"
        class="topic-section"
      >
        <div class="topic-header">
          <div>
            <div class="topic-caption">专题</div>
            <h2>{{ topic.topic_name }}</h2>
          </div>
          <div class="topic-header-right">
            <span class="topic-count">{{ topic.problem_count }}题</span>
            <a-button size="small" @click="toggleTopicExpand(topic.topic_key)">
              {{ isTopicExpanded(topic.topic_key) ? '收起专题' : '展开专题' }}
            </a-button>
            <a-button type="link" @click="startTopicPractice(topic)">
              继续本专题
              <RightOutlined />
            </a-button>
          </div>
        </div>

        <div v-if="isTopicExpanded(topic.topic_key)" class="problem-grid">
          <article
            v-for="problem in getVisibleProblems(topic)"
            :key="problem.problem_ref"
            class="problem-card"
            @click="openProblem(problem)"
          >
            <div class="problem-card-head">
              <div class="problem-title-wrap">
                <span class="problem-index">#{{ problem.problem_index }}</span>
                <h3>{{ problem.title }}</h3>
              </div>
              <a-tag :color="difficultyColorMap[problem.difficulty_tag] || 'default'">
                {{ difficultyLabelMap[problem.difficulty_tag] || '中等' }}
              </a-tag>
            </div>

            <p class="problem-summary" :class="{ collapsed: !isExpanded(problem.problem_ref) }">
              {{ problem.summary || '点击进入题目后查看完整描述与示例。' }}
            </p>

            <div class="problem-meta-row">
              <span class="meta-item">
                <BookOutlined />
                {{ languageLabelMap[problem.statement_language] || '未知题面' }}
              </span>
              <span class="meta-item" :class="statusClassMap[getProblemStatus(problem)]">
                <CheckCircleOutlined />
                {{ statusLabelMap[getProblemStatus(problem)] }}
              </span>
              <button
                type="button"
                class="favorite-btn"
                :class="{ active: isFavorite(problem) }"
                @click.stop="toggleFavorite(problem)"
              >
                <StarFilled v-if="isFavorite(problem)" />
                <StarOutlined v-else />
                {{ isFavorite(problem) ? '已收藏' : '收藏' }}
              </button>
            </div>

            <div v-if="showTags && problem.topic_tags?.length" class="problem-tags">
              <a-tag v-for="tag in problem.topic_tags" :key="`${problem.problem_ref}-${tag}`">{{ tag }}</a-tag>
            </div>

            <div class="problem-actions">
              <a-button size="small" @click.stop="toggleExpanded(problem.problem_ref)">
                {{ isExpanded(problem.problem_ref) ? '收起预览' : '题目预览' }}
              </a-button>
              <a-button type="primary" size="small" @click.stop="openProblem(problem)">
                {{ getProblemStatus(problem) === 'attempted' ? '继续练习' : '开始挑战' }}
              </a-button>
            </div>
          </article>
        </div>
        <div v-else class="topic-collapsed-hint">专题已折叠，点击“展开专题”后再浏览题目。</div>

        <div v-if="isTopicExpanded(topic.topic_key) && canLoadMoreTopicProblems(topic)" class="topic-load-more">
          <a-button @click="loadMoreTopicProblems(topic.topic_key)">
            加载更多（{{ getVisibleProblemCount(topic.topic_key) }}/{{ topic.problem_count }}）
          </a-button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  RightOutlined,
  SearchOutlined,
  StarFilled,
  StarOutlined,
  ThunderboltOutlined
} from '@ant-design/icons-vue'

import { practiceApi } from '@/apis/practice_api'

const router = useRouter()
const route = useRoute()

const LOCAL_PROGRESS_KEY = 'practice-home-progress-v1'
const DAILY_GOAL = 10
const TOPIC_RENDER_BATCH_SIZE = 20

const loading = ref(false)
const plan = ref({})
const topics = ref([])
const showTags = ref(true)
const showAllTopicRows = ref(false)
const activeTopicKey = ref('')
const expandedRefs = ref(new Set())
const topicPanelState = reactive({})

// Seed keyword from `?q=` so the interview result page can deep-link
// learners straight to a pre-filtered practice list.
const filters = reactive({
  keyword: String(route.query.q || '').trim(),
  difficulty: 'all',
  status: 'all',
  language: 'all'
})

const difficultyLabelMap = {
  easy: '简单',
  medium: '中等',
  hard: '困难'
}

const difficultyColorMap = {
  easy: 'green',
  medium: 'gold',
  hard: 'red'
}

const statusLabelMap = {
  new: '未做',
  attempted: '练习中'
}

const statusClassMap = {
  new: 'status-new',
  attempted: 'status-attempted'
}

const languageLabelMap = {
  zh: '中文题面',
  en: '英文题面',
  mixed: '中英混合',
  unknown: '未知题面'
}

const difficultyOptions = [
  { label: '全部', value: 'all' },
  { label: '简单', value: 'easy' },
  { label: '中等', value: 'medium' },
  { label: '困难', value: 'hard' }
]

const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '未做', value: 'new' },
  { label: '练习中', value: 'attempted' },
  { label: '已收藏', value: 'favorite' }
]

const emptyProgress = () => ({
  attempted_map: {},
  favorite_refs: [],
  last_problem_ref: ''
})

const loadProgress = () => {
  try {
    const raw = localStorage.getItem(LOCAL_PROGRESS_KEY)
    if (!raw) return emptyProgress()
    const parsed = JSON.parse(raw)
    return {
      attempted_map: parsed?.attempted_map || {},
      favorite_refs: Array.isArray(parsed?.favorite_refs) ? parsed.favorite_refs : [],
      last_problem_ref: String(parsed?.last_problem_ref || '')
    }
  } catch {
    return emptyProgress()
  }
}

const progress = ref(emptyProgress())

const saveProgress = () => {
  localStorage.setItem(LOCAL_PROGRESS_KEY, JSON.stringify(progress.value))
}

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
  topic_tags: (problem?.topic_tags || []).map((tag) => decodeHtmlText(tag))
})

const normalizeTopicItem = (topic) => ({
  ...topic,
  topic_name: decodeHtmlText(topic?.topic_name),
  problems: (topic?.problems || []).map((problem) => normalizeProblemItem(problem))
})

const normalizePracticePayload = (payload) => ({
  plan: {
    ...(payload?.plan || {}),
    title: decodeHtmlText(payload?.plan?.title),
    description: decodeHtmlText(payload?.plan?.description)
  },
  topics: (payload?.topics || []).map((topic) => normalizeTopicItem(topic))
})

const normalizeText = (value) => String(value || '').trim().toLowerCase()

const allProblems = computed(() => (topics.value || []).flatMap((topic) => topic.problems || []))

const problemRefMap = computed(() => {
  const map = new Map()
  for (const problem of allProblems.value) {
    map.set(problem.problem_ref, problem)
  }
  return map
})

const languageOptions = computed(() => {
  const values = new Set()
  for (const problem of allProblems.value) {
    values.add(problem.statement_language || 'unknown')
  }
  const base = [{ label: '全部', value: 'all' }]
  const ordered = ['zh', 'en', 'mixed', 'unknown']
  for (const key of ordered) {
    if (values.has(key)) {
      base.push({ label: languageLabelMap[key], value: key })
    }
  }
  return base
})

const isAttemptedRef = (problemRef) => Boolean(progress.value.attempted_map?.[problemRef])

const isFavoriteRef = (problemRef) => (progress.value.favorite_refs || []).includes(problemRef)

const getProblemStatus = (problem) => (isAttemptedRef(problem.problem_ref) ? 'attempted' : 'new')

const matchStatusFilter = (problem) => {
  if (filters.status === 'all') return true
  if (filters.status === 'favorite') return isFavoriteRef(problem.problem_ref)
  return getProblemStatus(problem) === filters.status
}

const filteredTopics = computed(() => {
  const keyword = normalizeText(filters.keyword)

  return (topics.value || [])
    .map((topic) => {
      const problems = (topic.problems || []).filter((problem) => {
        if (filters.difficulty !== 'all' && (problem.difficulty_tag || 'medium') !== filters.difficulty) {
          return false
        }
        if (filters.language !== 'all' && (problem.statement_language || 'unknown') !== filters.language) {
          return false
        }
        if (!matchStatusFilter(problem)) {
          return false
        }
        if (!keyword) {
          return true
        }
        const haystack = [problem.title, topic.topic_name, ...(problem.topic_tags || [])]
          .map(normalizeText)
          .join(' ')
        return haystack.includes(keyword)
      })

      return {
        ...topic,
        problem_count: problems.length,
        problems
      }
    })
    .filter((topic) => topic.problems.length)
})

const filteredProblemCount = computed(() =>
  filteredTopics.value.reduce((total, topic) => total + Number(topic.problem_count || 0), 0)
)

const practicedCount = computed(() => {
  const availableRefs = new Set(allProblems.value.map((problem) => problem.problem_ref))
  return Object.keys(progress.value.attempted_map || {}).filter((problemRef) => availableRefs.has(problemRef)).length
})

const pendingCount = computed(() => Math.max(filteredProblemCount.value - practicedCount.value, 0))

const formatDateKey = (value) => {
  const date = new Date(value)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const todayKey = () => formatDateKey(new Date())

const todayAttemptCount = computed(() => {
  const target = todayKey()
  return Object.values(progress.value.attempted_map || {}).filter((value) => formatDateKey(value) === target).length
})

const todayProgress = computed(() => `${todayAttemptCount.value}/${DAILY_GOAL}`)

const streakDays = computed(() => {
  const daySet = new Set(Object.values(progress.value.attempted_map || {}).map((value) => formatDateKey(value)))
  if (!daySet.size) {
    return 0
  }

  let streak = 0
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)

  while (daySet.has(formatDateKey(cursor))) {
    streak += 1
    cursor.setDate(cursor.getDate() - 1)
  }

  return streak
})

const recommendedProblem = computed(() => {
  const unattempted = filteredTopics.value
    .flatMap((topic) => topic.problems || [])
    .filter((problem) => !isAttemptedRef(problem.problem_ref))

  if (unattempted.length) {
    return unattempted[0]
  }

  return filteredTopics.value[0]?.problems?.[0] || null
})

const topicCloudRows = computed(() => {
  const maxCount = Math.max(...filteredTopics.value.map((topic) => Number(topic.problem_count || 0)), 1)

  return [...filteredTopics.value]
    .sort((a, b) => Number(b.problem_count || 0) - Number(a.problem_count || 0))
    .map((topic, index) => {
      const count = Number(topic.problem_count || 0)
      const percent = Math.max(Math.round((count / maxCount) * 100), 5)
      if (index < 3) {
        return { ...topic, percent, tierLabel: '热门', tierClass: 'tier-hot' }
      }
      if (index < 8) {
        return { ...topic, percent, tierLabel: '进阶', tierClass: 'tier-mid' }
      }
      return { ...topic, percent, tierLabel: '专项', tierClass: 'tier-base' }
    })
})

const visibleTopicRows = computed(() => (showAllTopicRows.value ? topicCloudRows.value : topicCloudRows.value.slice(0, 8)))

const getTopicPanel = (topicKey) => {
  if (!topicPanelState[topicKey]) {
    topicPanelState[topicKey] = {
      expanded: false,
      visibleCount: TOPIC_RENDER_BATCH_SIZE
    }
  }
  return topicPanelState[topicKey]
}

const syncTopicPanels = (topicList) => {
  const keys = new Set((topicList || []).map((topic) => String(topic.topic_key || '')))
  for (const key of Object.keys(topicPanelState)) {
    if (!keys.has(key)) {
      delete topicPanelState[key]
    }
  }

  for (const topic of topicList || []) {
    const panel = getTopicPanel(topic.topic_key)
    if (!Number.isFinite(panel.visibleCount) || panel.visibleCount < TOPIC_RENDER_BATCH_SIZE) {
      panel.visibleCount = TOPIC_RENDER_BATCH_SIZE
    }
  }

  if (!topicList?.length) return
  const hasExpanded = topicList.some((topic) => getTopicPanel(topic.topic_key).expanded)
  if (!hasExpanded) {
    getTopicPanel(topicList[0].topic_key).expanded = true
  }
}

const isTopicExpanded = (topicKey) => Boolean(getTopicPanel(topicKey).expanded)

const expandTopic = (topicKey) => {
  for (const topic of filteredTopics.value) {
    getTopicPanel(topic.topic_key).expanded = false
  }
  const panel = getTopicPanel(topicKey)
  panel.expanded = true
  panel.visibleCount = Math.max(panel.visibleCount, TOPIC_RENDER_BATCH_SIZE)
}

const toggleTopicExpand = (topicKey) => {
  if (isTopicExpanded(topicKey)) {
    getTopicPanel(topicKey).expanded = false
    return
  }
  expandTopic(topicKey)
}

const getVisibleProblems = (topic) => {
  const count = getTopicPanel(topic.topic_key).visibleCount
  return (topic.problems || []).slice(0, count)
}

const getVisibleProblemCount = (topicKey) => getTopicPanel(topicKey).visibleCount

const canLoadMoreTopicProblems = (topic) => getVisibleProblemCount(topic.topic_key) < Number(topic.problem_count || 0)

const loadMoreTopicProblems = (topicKey) => {
  const panel = getTopicPanel(topicKey)
  panel.visibleCount += TOPIC_RENDER_BATCH_SIZE
}

const markAttempt = (problemRef) => {
  progress.value = {
    ...progress.value,
    attempted_map: {
      ...(progress.value.attempted_map || {}),
      [problemRef]: new Date().toISOString()
    },
    last_problem_ref: problemRef
  }
  saveProgress()
}

const isFavorite = (problem) => isFavoriteRef(problem.problem_ref)

const toggleFavorite = (problem) => {
  const current = new Set(progress.value.favorite_refs || [])
  if (current.has(problem.problem_ref)) {
    current.delete(problem.problem_ref)
  } else {
    current.add(problem.problem_ref)
  }

  progress.value = {
    ...progress.value,
    favorite_refs: [...current]
  }
  saveProgress()
}

const isExpanded = (problemRef) => expandedRefs.value.has(problemRef)

const toggleExpanded = (problemRef) => {
  const next = new Set(expandedRefs.value)
  if (next.has(problemRef)) {
    next.delete(problemRef)
  } else {
    next.add(problemRef)
  }
  expandedRefs.value = next
}

const openProblem = (problem) => {
  markAttempt(problem.problem_ref)
  router.push({
    name: 'PracticeProblemPage',
    params: { problem_ref: problem.problem_ref },
    query: problem.primary_topic_key ? { topic: problem.primary_topic_key } : {}
  })
}

const startTopicPractice = (topic) => {
  const target = (topic.problems || []).find((problem) => !isAttemptedRef(problem.problem_ref)) || topic.problems?.[0]
  if (!target) {
    message.warning('该专题暂无可练习题目')
    return
  }
  openProblem(target)
}

const startRecommendedProblem = () => {
  if (!recommendedProblem.value) {
    message.warning('暂无可练习题目')
    return
  }
  openProblem(recommendedProblem.value)
}

const continueLastProblem = () => {
  const lastRef = String(progress.value.last_problem_ref || '').trim()
  const target = lastRef ? problemRefMap.value.get(lastRef) : null
  if (!target) {
    message.warning('暂未记录上次练习，请先开始一道题目')
    startRecommendedProblem()
    return
  }
  openProblem(target)
}

const focusFavoriteProblems = () => {
  filters.status = 'favorite'
  if (!(progress.value.favorite_refs || []).length) {
    message.info('你还没有收藏题目，先挑一道题开始吧')
  }
}

const goToTopic = (topicKey) => {
  expandTopic(topicKey)
  router.replace({ name: 'PracticeTopicPage', params: { topic_key: topicKey } })
}

const resetFilters = () => {
  filters.keyword = ''
  filters.difficulty = 'all'
  filters.status = 'all'
  filters.language = 'all'
}

const syncTopicAnchor = async () => {
  const topicKey = String(route.params.topic_key || '').trim()
  activeTopicKey.value = topicKey || filteredTopics.value[0]?.topic_key || ''
  if (!topicKey) {
    if (filteredTopics.value[0]?.topic_key) {
      expandTopic(filteredTopics.value[0].topic_key)
    }
    return
  }

  if (filteredTopics.value.some((topic) => topic.topic_key === topicKey)) {
    expandTopic(topicKey)
  }

  await nextTick()
  document.getElementById(`topic-${topicKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const loadPlan = async () => {
  loading.value = true
  try {
    const data = await practiceApi.getDefaultPlan()
    const normalized = normalizePracticePayload(data)
    plan.value = normalized.plan
    topics.value = normalized.topics
  } catch (error) {
    message.error(error.message || '加载练习题单失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.params.topic_key, filteredTopics.value.length],
  () => {
    syncTopicAnchor()
  }
)

watch(
  filteredTopics,
  (list) => {
    syncTopicPanels(list)
  },
  { immediate: true }
)

onMounted(() => {
  progress.value = loadProgress()
  loadPlan()
})
</script>

<style scoped lang="less">
.practice-home {
  min-height: 100%;
  padding: 20px;
  background: var(--gray-50);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overview-card,
.filter-card,
.topic-cloud-card,
.state-panel,
.topic-section {
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 20px;
}

.overview-card {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overview-eyebrow,
.filter-label,
.switch-label,
.cloud-title,
.topic-caption,
.topic-count,
.recommend-label,
.recommend-meta {
  font-size: 13px;
  color: var(--gray-600);
}

.overview-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overview-main h1 {
  margin: 0;
  font-size: 30px;
  color: var(--gray-1000);
}

.overview-main p {
  margin: 0;
  max-width: 820px;
  color: var(--gray-700);
  line-height: 1.7;
}

.overview-actions {
  margin-top: 6px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.overview-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
}

.metric-label {
  font-size: 12px;
  color: var(--gray-600);
}

.metric-value {
  margin-top: 6px;
  font-size: 26px;
  font-weight: 700;
  color: var(--gray-1000);
}

.recommend-row {
  border-top: 1px solid var(--gray-150);
  padding-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.recommend-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.recommend-info strong {
  color: var(--gray-1000);
  font-size: 15px;
}

.filter-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-group.compact {
  padding-top: 4px;
}

.filter-label {
  min-width: 62px;
}

.filter-chip {
  border: 1px solid var(--gray-200);
  background: var(--color-bg-container);
  color: var(--gray-700);
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.filter-chip:hover,
.filter-chip.active {
  border-color: var(--main-300);
  background: var(--main-20);
  color: var(--main-color);
}

.filter-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-summary {
  color: var(--gray-600);
  font-size: 13px;
  margin-right: auto;
}

.state-panel {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.topic-cloud-card {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.topic-cloud-header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.topic-cloud-header h2 {
  margin: 4px 0 0;
  color: var(--gray-1000);
  font-size: 18px;
}

.topic-cloud-row {
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  border-radius: 12px;
  padding: 10px 12px;
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 2fr) 56px;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.topic-cloud-name {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--gray-900);
  font-weight: 600;
}

.topic-cloud-name small {
  color: var(--gray-600);
  font-weight: 500;
}

.topic-cloud-bar {
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--gray-150);
}

.topic-cloud-fill {
  height: 100%;
  background: var(--main-300);
}

.topic-cloud-tier {
  font-size: 12px;
  color: var(--gray-600);
  text-align: right;
}

.topic-cloud-row.tier-hot .topic-cloud-fill {
  background: #ef5350;
}

.topic-cloud-row.tier-mid .topic-cloud-fill {
  background: #f59e0b;
}

.topic-nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.topic-chip {
  padding: 8px 14px;
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--color-bg-container);
  color: var(--gray-700);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;
}

.topic-chip:hover,
.topic-chip.active {
  border-color: var(--main-300);
  background: var(--main-20);
  color: var(--main-color);
}

.topic-section {
  padding: 18px;
}

.topic-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-end;
  margin-bottom: 14px;
}

.topic-header h2 {
  margin: 0;
  color: var(--gray-1000);
}

.topic-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topic-collapsed-hint {
  padding: 14px 12px;
  border: 1px dashed var(--gray-200);
  border-radius: 12px;
  color: var(--gray-600);
  background: var(--gray-25);
  font-size: 13px;
}

.topic-load-more {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}

.problem-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.problem-card {
  border: 1px solid var(--gray-200);
  border-radius: 14px;
  padding: 12px;
  background: var(--gray-25);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.problem-card:hover {
  border-color: var(--main-300);
  box-shadow: 0 6px 16px rgba(17, 24, 39, 0.08);
}

.problem-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.problem-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.problem-title-wrap h3 {
  margin: 0;
  font-size: 15px;
  color: var(--gray-1000);
  line-height: 1.45;
}

.problem-index {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--main-color);
  background: var(--main-20);
}

.problem-summary {
  margin: 0;
  color: var(--gray-700);
  line-height: 1.7;
}

.problem-summary.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.problem-meta-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.meta-item {
  color: var(--gray-600);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.meta-item.status-new {
  color: #2563eb;
}

.meta-item.status-attempted {
  color: #d97706;
}

.favorite-btn {
  border: none;
  background: transparent;
  padding: 0;
  color: var(--gray-600);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 12px;
}

.favorite-btn.active {
  color: #f59e0b;
}

.problem-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.problem-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

@media (max-width: 1100px) {
  .overview-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .problem-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .practice-home {
    padding: 12px;
  }

  .overview-card,
  .filter-card,
  .topic-cloud-card,
  .topic-section {
    padding: 14px;
  }

  .overview-main h1 {
    font-size: 24px;
  }

  .overview-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .topic-cloud-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .topic-cloud-tier {
    text-align: left;
  }
}
</style>
