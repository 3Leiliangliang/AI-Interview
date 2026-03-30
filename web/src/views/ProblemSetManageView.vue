<template>
  <div class="problemset-page layout-container">
    <HeaderComponent title="题库管理" :description="headerDescription" :loading="loading" />

    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-label">已导入题包</div>
        <div class="summary-value">{{ summary.imported_package_count }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">已导入题目</div>
        <div class="summary-value">{{ summary.imported_problem_count }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">已追踪题包</div>
        <div class="summary-value">{{ summary.tracked_package_count }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">已追踪题目</div>
        <div class="summary-value">{{ summary.tracked_problem_count }}</div>
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
    </div>

    <div v-else-if="!problems.length" class="empty-state">
      <h3 class="empty-title">暂无已导入题目</h3>
      <p class="empty-description">先使用 freeproblemset 导入脚本导入题目，这里会按岗位适配类型展示题库。</p>
    </div>

    <a-row v-else :gutter="[16, 16]" class="position-grid">
      <a-col v-for="group in problemGroups" :key="group.key" :xs="24" :md="12" :xl="8">
        <a-card class="position-card" :bordered="false">
          <template #title>
            <div class="card-title-row">
              <div class="position-title">{{ group.title }}</div>
              <a-tag :color="group.color">{{ group.items.length }} 题</a-tag>
            </div>
          </template>

          <div class="position-description">{{ group.description }}</div>

          <div class="position-stats">
            <span>题目数 {{ group.items.length }}</span>
            <span>题包数 {{ group.packageCount }}</span>
          </div>

          <div v-if="group.languageStats.length" class="language-row">
            <div class="section-label">题面语言</div>
            <div class="topic-tags">
              <a-tag v-for="item in group.languageStats" :key="`${group.key}-${item.key}`" :color="item.color">
                {{ item.label }} · {{ item.count }}
              </a-tag>
            </div>
          </div>

          <div v-if="group.difficultyStats.length" class="difficulty-row">
            <div class="section-label">题目难度</div>
            <div class="topic-tags">
              <a-tag v-for="item in group.difficultyStats" :key="`${group.key}-${item.key}`" :color="item.color">
                {{ item.label }} · {{ item.count }}
              </a-tag>
            </div>
          </div>

          <div v-if="group.topTopicTags.length" class="topic-row">
            <div class="section-label">高频主题</div>
            <div class="topic-tags">
              <a-tag v-for="tag in group.topTopicTags" :key="`${group.key}-${tag.tag}`">
                {{ tag.tag }} · {{ tag.count }}
              </a-tag>
            </div>
          </div>

          <div v-if="group.previewTitles.length" class="preview-row">
            <div class="section-label">题目预览</div>
            <div class="preview-list">
              <div v-for="title in group.previewTitles" :key="`${group.key}-${title}`" class="preview-item">
                {{ decodeHtml(title) }}
              </div>
            </div>
          </div>

          <div class="card-actions">
            <a-button type="primary" ghost @click="openGroupDetail(group)">查看题目</a-button>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <a-drawer
      :open="detailVisible"
      width="min(1200px, 92vw)"
      placement="right"
      title="题目详情"
      @close="closeDetail"
    >
      <div v-if="detailLoading && !detailProblems.length" class="drawer-state">
        <a-spin size="large" />
      </div>

      <div v-else-if="!detailProblems.length" class="drawer-state">
        <a-empty description="暂无题目详情" />
      </div>

      <div v-else class="detail-layout">
        <aside class="problem-list-panel">
          <div class="problem-list-header">
            <div class="drawer-group-title">{{ activeGroup?.title }}</div>
            <div class="drawer-group-meta">{{ detailProblems.length }} 题</div>
          </div>
          <div class="problem-list">
            <button
              v-for="problem in detailProblems"
              :key="problemKey(problem)"
              type="button"
              class="problem-list-item"
              :class="{ active: activeProblemKey === problemKey(problem) }"
              @click="selectProblem(problem)"
            >
              <span class="problem-index">#{{ problem.problem_index }}</span>
              <span class="problem-name">{{ decodeHtml(problem.title) }}</span>
              <span class="problem-meta-row">
                <span class="problem-package">{{ fileName(problem.package_path) }}</span>
                <span class="meta-tag-group">
                  <a-tag size="small" :color="statementLanguageColorMap[problem.statement_language] || 'default'">
                    {{ statementLanguageLabelMap[problem.statement_language] || '未知' }}
                  </a-tag>
                  <a-tag size="small" :color="difficultyColorMap[problem.difficulty_tag] || 'default'">
                    {{ difficultyLabelMap[problem.difficulty_tag] || '中等' }}
                  </a-tag>
                </span>
              </span>
            </button>
          </div>
        </aside>

        <section class="problem-detail-panel">
          <template v-if="activeProblem">
            <div class="detail-header">
              <div>
                <h2 class="detail-title">{{ decodeHtml(activeProblem.title) }}</h2>
                <div class="detail-meta">
                  <span>来源：{{ decodeHtml(activeProblem.source || '未知') }}</span>
                  <span>题包：{{ activeProblem.package_path }}</span>
                  <span v-if="activeProblem.oj_display_ids?.length">
                    OJ：{{ activeProblem.oj_display_ids.join(', ') }}
                  </span>
                </div>
              </div>
            </div>

            <div class="detail-tag-row">
              <a-tag
                v-for="tag in activeProblem.position_tags || []"
                :key="`position-${tag}`"
                :color="tag === 'frontend' ? 'geekblue' : tag === 'backend' ? 'green' : 'gold'"
              >
                {{ positionLabelMap[tag] || tag }}
              </a-tag>
              <a-tag :color="statementLanguageColorMap[activeProblem.statement_language] || 'default'">
                {{ statementLanguageLabelMap[activeProblem.statement_language] || '未知' }}
              </a-tag>
              <a-tag :color="difficultyColorMap[activeProblem.difficulty_tag] || 'default'">
                {{ difficultyLabelMap[activeProblem.difficulty_tag] || '中等' }}
              </a-tag>
              <a-tag v-for="tag in activeProblem.topic_tags || []" :key="`topic-${tag}`">{{ tag }}</a-tag>
              <a-tag v-for="lang in activeProblem.allowed_languages || []" :key="`lang-${lang}`" color="purple">
                {{ languageLabelMap[lang] || lang }}
              </a-tag>
            </div>

            <div v-if="activeProblem.summary" class="summary-box">{{ decodeHtml(activeProblem.summary) }}</div>

            <div class="detail-section">
              <h3>题目描述</h3>
              <p>{{ decodeHtml(activeProblem.description || '暂无描述') }}</p>
            </div>

            <div v-if="activeProblem.input_description" class="detail-section">
              <h3>输入说明</h3>
              <p>{{ decodeHtml(activeProblem.input_description) }}</p>
            </div>

            <div v-if="activeProblem.output_description" class="detail-section">
              <h3>输出说明</h3>
              <p>{{ decodeHtml(activeProblem.output_description) }}</p>
            </div>

            <div v-if="activeProblem.examples?.length" class="detail-section">
              <h3>示例</h3>
              <div v-for="(example, index) in activeProblem.examples" :key="index" class="example-card">
                <div>
                  <strong>输入</strong>
                  <pre>{{ decodeHtml(example.input || '(空)') }}</pre>
                </div>
                <div>
                  <strong>输出</strong>
                  <pre>{{ decodeHtml(example.output || '(空)') }}</pre>
                </div>
              </div>
            </div>

            <div v-if="starterCodeEntries.length" class="detail-section">
              <h3>模板代码</h3>
              <div v-for="entry in starterCodeEntries" :key="entry.language" class="starter-card">
                <div class="starter-header">{{ languageLabelMap[entry.language] || entry.language }}</div>
                <pre>{{ entry.code }}</pre>
              </div>
            </div>
          </template>
        </section>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'

import HeaderComponent from '@/components/HeaderComponent.vue'
import { problemsetApi } from '@/apis/problemset_api'

const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const problems = ref([])
const summary = ref({
  imported_package_count: 0,
  imported_problem_count: 0,
  tracked_package_count: 0,
  tracked_problem_count: 0
})

const activeGroup = ref(null)
const detailProblems = ref([])
const activeProblem = ref(null)
const activeProblemKey = ref('')
const packageDetailCache = new Map()

const languageLabelMap = {
  javascript: 'JavaScript',
  c: 'C',
  cpp: 'C++',
  java: 'Java',
  python: 'Python'
}

const statementLanguageLabelMap = {
  zh: '中文题面',
  en: '英文题面',
  mixed: '中英混合',
  unknown: '语言未知'
}

const statementLanguageColorMap = {
  zh: 'blue',
  en: 'green',
  mixed: 'purple',
  unknown: 'default'
}

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

const positionLabelMap = {
  frontend: '前端',
  backend: '后端',
  algorithm_general: '通用'
}

const positionGroupDefs = [
  { key: 'frontend', title: '前端', color: 'geekblue', description: '优先适配前端岗位的题目。' },
  { key: 'backend', title: '后端', color: 'green', description: '优先适配后端岗位的题目。' },
  { key: 'algorithm_general', title: '通用', color: 'gold', description: '算法与通用编程能力题目。' }
]

const decodeHtml = (value) => {
  const text = String(value || '')
  if (!text) return ''
  if (typeof window === 'undefined') return text
  const textarea = document.createElement('textarea')
  textarea.innerHTML = text
  return textarea.value
}

const headerDescription = computed(() => {
  if (!summary.value.imported_problem_count) {
    return '按前端 / 后端 / 通用分类查看已导入到 OJ 与面试题池的题目。'
  }
  return `当前已导入 ${summary.value.imported_problem_count} 道题，点击卡片查看对应题目列表。`
})

const starterCodeEntries = computed(() => {
  const starterCode = activeProblem.value?.starter_code || {}
  return Object.entries(starterCode).map(([language, code]) => ({ language, code }))
})

const problemGroups = computed(() =>
  positionGroupDefs.map((group) => {
    const items = problems.value.filter((item) => item.primary_position_tag === group.key)
    const topicCounter = {}
    const packageSet = new Set()
    items.forEach((item) => {
      packageSet.add(item.package_path)
      ;(item.topic_tags || []).forEach((tag) => {
        topicCounter[tag] = (topicCounter[tag] || 0) + 1
      })
    })
    return {
      ...group,
      items,
      packageCount: packageSet.size,
      languageStats: ['zh', 'en', 'mixed', 'unknown']
        .map((key) => ({
          key,
          label: statementLanguageLabelMap[key],
          color: statementLanguageColorMap[key],
          count: items.filter((item) => (item.statement_language || 'unknown') === key).length
        }))
        .filter((item) => item.count > 0),
      difficultyStats: ['easy', 'medium', 'hard']
        .map((key) => ({
          key,
          label: difficultyLabelMap[key],
          color: difficultyColorMap[key],
          count: items.filter((item) => (item.difficulty_tag || 'medium') === key).length
        }))
        .filter((item) => item.count > 0),
      topTopicTags: Object.entries(topicCounter)
        .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))
        .slice(0, 5)
        .map(([tag, count]) => ({ tag, count })),
      previewTitles: items.slice(0, 3).map((item) => item.title)
    }
  })
)

const fileName = (packagePath) => {
  const normalized = String(packagePath || '').replace(/\\/g, '/')
  return normalized.split('/').pop() || normalized
}

const problemKey = (item) => `${item.package_path}::${item.problem_index}`

const loadProblemsets = async () => {
  loading.value = true
  try {
    const data = await problemsetApi.getImportedProblemsets()
    problems.value = data?.problems || []
    summary.value = {
      ...summary.value,
      ...(data?.summary || {})
    }
  } catch (error) {
    message.error(error.message || '加载题库失败')
  } finally {
    loading.value = false
  }
}

const loadProblemDetail = async (item) => {
  if (!packageDetailCache.has(item.package_path)) {
    const data = await problemsetApi.getProblemsetDetail(item.package_path)
    packageDetailCache.set(item.package_path, data?.problems || [])
  }
  const packageProblems = packageDetailCache.get(item.package_path) || []
  return packageProblems.find((problem) => Number(problem.problem_index) === Number(item.problem_index)) || null
}

const selectProblem = async (problemSummary) => {
  detailLoading.value = true
  try {
    const detail = await loadProblemDetail(problemSummary)
    activeProblem.value = detail ? { ...problemSummary, ...detail } : { ...problemSummary }
    activeProblemKey.value = problemKey(problemSummary)
  } catch (error) {
    message.error(error.message || '加载题目详情失败')
  } finally {
    detailLoading.value = false
  }
}

const openGroupDetail = async (group) => {
  detailVisible.value = true
  activeGroup.value = group
  detailProblems.value = [...group.items]
  activeProblem.value = null
  activeProblemKey.value = ''
  if (detailProblems.value.length) {
    await selectProblem(detailProblems.value[0])
  }
}

const closeDetail = () => {
  detailVisible.value = false
  activeGroup.value = null
  detailProblems.value = []
  activeProblem.value = null
  activeProblemKey.value = ''
}

onMounted(() => {
  loadProblemsets()
})
</script>

<style scoped lang="less">
.problemset-page {
  min-height: 100%;
  background: var(--gray-50);
}

.summary-grid {
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card,
.state-panel,
.empty-state,
.problem-list-panel,
.problem-detail-panel {
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
}

.summary-card {
  padding: 18px 20px;
}

.summary-label {
  font-size: 13px;
  color: var(--gray-600);
}

.summary-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
  color: var(--gray-1000);
}

.position-grid {
  padding: 0 20px 20px;
}

:deep(.position-card) {
  height: 100%;
  border-radius: 16px;
  border: 1px solid var(--gray-200);
  box-shadow: none;
}

:deep(.position-card .ant-card-body) {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.card-title-row,
.position-stats,
.problem-list-header,
.detail-header,
.detail-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.position-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-1000);
}

.position-description,
.position-stats,
.section-label,
.drawer-group-meta,
.detail-meta,
.problem-package,
.empty-description {
  font-size: 13px;
  color: var(--gray-600);
}

.problem-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.topic-row,
.language-row,
.difficulty-row,
.preview-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.topic-tags,
.detail-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--gray-25);
  color: var(--gray-800);
  line-height: 1.6;
  word-break: break-word;
}

.card-actions {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
}

.state-panel,
.empty-state,
.drawer-state {
  margin: 0 20px 20px;
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  text-align: center;
  padding: 24px;
}

.drawer-state {
  margin: 0;
}

.empty-title {
  margin: 0 0 10px;
  font-size: 20px;
  color: var(--gray-900);
}

:deep(.ant-drawer-body) {
  padding: 24px;
  overflow: hidden;
}

.detail-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
  height: calc(100vh - 180px);
  min-height: 0;
  overflow: hidden;
}

.problem-list-panel,
.problem-detail-panel {
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.problem-list-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.problem-list-header {
  padding: 8px 8px 14px;
  border-bottom: 1px solid var(--gray-150);
  margin-bottom: 12px;
}

.drawer-group-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-1000);
}

.problem-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.problem-list-item {
  width: 100%;
  text-align: left;
  padding: 12px;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-0);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.problem-list-item.active {
  border-color: var(--main-200);
  background: var(--main-20);
}

.problem-index {
  font-size: 12px;
  color: var(--gray-600);
}

.problem-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-900);
}

.problem-detail-panel {
  padding: 20px;
}

.detail-title {
  margin: 0 0 8px;
  font-size: 22px;
  color: var(--gray-1000);
}

.summary-box,
.example-card,
.starter-card {
  border-radius: 12px;
  border: 1px solid var(--gray-150);
  background: var(--gray-25);
}

.summary-box {
  padding: 14px;
  margin-bottom: 18px;
  line-height: 1.7;
  color: var(--gray-800);
}

.detail-section {
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-section h3,
.starter-header {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--gray-900);
}

.detail-section p,
.detail-section pre,
.starter-card pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: var(--gray-800);
}

.example-card,
.starter-card {
  padding: 14px;
  margin-top: 8px;
}

.example-card {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.starter-header {
  margin-bottom: 10px;
}

.starter-card pre {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
}

@media (max-width: 1080px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .detail-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .summary-grid,
  .example-card {
    grid-template-columns: 1fr;
  }
}
</style>
