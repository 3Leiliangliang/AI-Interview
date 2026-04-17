<template>
  <div class="practice-home">
    <div class="hero-card">
      <div class="hero-main">
        <span class="hero-eyebrow">算法专题练习</span>
        <h1>{{ plan.title || '代码练习' }}</h1>
        <p>{{ plan.description || '从已导入题库中按专题刷题，支持样例运行和在线判题。' }}</p>
        <div class="hero-actions">
          <a-button type="primary" size="large" @click="startFirstProblem">开始练习</a-button>
          <span class="hero-hint">当前共 {{ filteredProblemCount }} 道题，{{ filteredTopics.length }} 个专题</span>
        </div>
      </div>
      <div class="hero-stats">
        <div class="stat-card">
          <div class="stat-value">{{ filteredProblemCount }}</div>
          <div class="stat-label">题目数量</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ filteredTopics.length }}</div>
          <div class="stat-label">专题数量</div>
        </div>
      </div>
    </div>

    <div class="toolbar-card">
      <a-input v-model:value="filters.keyword" allow-clear size="large" placeholder="搜索题目标题或专题标签">
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input>
      <a-select v-model:value="filters.difficulty" :options="difficultyOptions" size="large" />
      <a-switch v-model:checked="showTags" />
      <span class="switch-label">显示标签</span>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
    </div>

    <div v-else-if="!filteredProblemCount" class="state-panel">
      <a-empty description="当前筛选条件下暂无题目" />
    </div>

    <template v-else>
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
          <span class="topic-count">{{ topic.problem_count }} 题</span>
        </div>

        <div class="problem-list">
          <button
            v-for="problem in topic.problems"
            :key="problem.problem_ref"
            type="button"
            class="problem-row"
            @click="openProblem(problem)"
          >
            <div class="problem-main">
              <span class="problem-index">#{{ problem.problem_index }}</span>
              <span class="problem-title">{{ problem.title }}</span>
            </div>
            <div class="problem-meta">
              <a-tag :color="difficultyColorMap[problem.difficulty_tag] || 'default'">
                {{ difficultyLabelMap[problem.difficulty_tag] || '中等' }}
              </a-tag>
              <template v-if="showTags">
                <a-tag v-for="tag in problem.topic_tags" :key="`${problem.problem_ref}-${tag}`">{{ tag }}</a-tag>
              </template>
            </div>
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
import { SearchOutlined } from '@ant-design/icons-vue'

import { practiceApi } from '@/apis/practice_api'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const plan = ref({})
const topics = ref([])
const showTags = ref(true)
const activeTopicKey = ref('')
const filters = reactive({
  keyword: '',
  difficulty: 'all'
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

const difficultyOptions = [
  { label: '全部难度', value: 'all' },
  { label: '简单', value: 'easy' },
  { label: '中等', value: 'medium' },
  { label: '困难', value: 'hard' }
]

const normalizeText = (value) => String(value || '').trim().toLowerCase()

const filteredTopics = computed(() => {
  const keyword = normalizeText(filters.keyword)
  return (topics.value || [])
    .map((topic) => {
      const problems = (topic.problems || []).filter((problem) => {
        if (filters.difficulty !== 'all' && (problem.difficulty_tag || 'medium') !== filters.difficulty) {
          return false
        }
        if (!keyword) {
          return true
        }
        const haystack = [
          problem.title,
          topic.topic_name,
          ...(problem.topic_tags || [])
        ]
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

const loadPlan = async () => {
  loading.value = true
  try {
    const data = await practiceApi.getDefaultPlan()
    plan.value = data?.plan || {}
    topics.value = data?.topics || []
  } catch (error) {
    message.error(error.message || '加载练习题单失败')
  } finally {
    loading.value = false
  }
}

const openProblem = (problem) => {
  router.push({
    name: 'PracticeProblemPage',
    params: { problem_ref: problem.problem_ref },
    query: problem.primary_topic_key ? { topic: problem.primary_topic_key } : {}
  })
}

const startFirstProblem = () => {
  const firstProblem = filteredTopics.value[0]?.problems?.[0]
  if (!firstProblem) {
    message.warning('暂无可练习的题目')
    return
  }
  openProblem(firstProblem)
}

const goToTopic = (topicKey) => {
  router.replace({ name: 'PracticeTopicPage', params: { topic_key: topicKey } })
}

const syncTopicAnchor = async () => {
  const topicKey = String(route.params.topic_key || '').trim()
  activeTopicKey.value = topicKey || filteredTopics.value[0]?.topic_key || ''
  if (!topicKey) {
    return
  }
  await nextTick()
  document.getElementById(`topic-${topicKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(
  () => [route.params.topic_key, filteredTopics.value.length],
  () => {
    syncTopicAnchor()
  }
)

onMounted(() => {
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

.hero-card,
.toolbar-card,
.state-panel,
.topic-section {
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 20px;
}

.hero-card {
  padding: 24px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 20px;
  align-items: stretch;
}

.hero-eyebrow,
.topic-caption,
.hero-hint,
.switch-label,
.topic-count {
  font-size: 13px;
  color: var(--gray-600);
}

.hero-main h1,
.topic-header h2 {
  margin: 0;
  color: var(--gray-1000);
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hero-main h1 {
  font-size: 32px;
  line-height: 1.2;
}

.hero-main p {
  margin: 0;
  max-width: 760px;
  color: var(--gray-700);
  line-height: 1.8;
}

.hero-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-stats {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.stat-card {
  padding: 18px;
  border-radius: 18px;
  background: var(--gray-25);
  border: 1px solid var(--gray-200);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--gray-1000);
}

.stat-label {
  margin-top: 6px;
  font-size: 13px;
  color: var(--gray-600);
}

.toolbar-card {
  padding: 16px 18px;
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 180px auto auto;
  gap: 12px;
  align-items: center;
}

.state-panel {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
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
  padding: 20px;
}

.topic-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-end;
  margin-bottom: 14px;
}

.problem-list {
  display: flex;
  flex-direction: column;
}

.problem-row {
  padding: 14px 0;
  border: none;
  border-top: 1px solid var(--gray-150);
  background: transparent;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  text-align: left;
  cursor: pointer;
}

.problem-row:first-child {
  border-top: none;
}

.problem-main,
.problem-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.problem-index {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--main-20);
  color: var(--main-color);
  font-size: 12px;
}

.problem-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--gray-1000);
}

@media (max-width: 960px) {
  .hero-card,
  .toolbar-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .practice-home {
    padding: 12px;
  }

  .hero-card,
  .topic-section {
    padding: 16px;
  }

  .problem-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
