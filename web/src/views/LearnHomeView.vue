<template>
  <div class="learn-home">
    <!-- 顶栏 -->
    <div class="page-topbar">
      <div class="topbar-left">
        <h1 class="page-title">知识学习</h1>
        <p class="page-subtitle">{{ subtitleText }}</p>
      </div>
      <div class="topbar-actions">
        <a-button
          v-if="totalReadLater > 0"
          class="btn-secondary"
          :class="{ 'btn-secondary--on': readLaterOnly }"
          @click="readLaterOnly = !readLaterOnly"
        >
          稍后读 {{ totalReadLater }}
        </a-button>
        <a-button type="primary" class="btn-primary" :disabled="!lastDoc" @click="continueLearning">
          {{ lastDoc ? '继续上次学习' : '尚无学习记录' }}
        </a-button>
      </div>
    </div>

    <div class="page-body">
      <!-- 搜索 + 排序 -->
      <div class="search-bar">
        <div class="search-bar__input">
          <SearchOutlined class="search-icon" />
          <input v-model="keyword" class="search-input" placeholder="搜索专题、文档或知识点" />
        </div>
        <div class="search-bar__tools">
          <a-select
            v-model:value="sortMode"
            :options="sortOptions"
            :bordered="false"
            size="small"
            class="flat-select"
          />
          <span class="tools-divider">·</span>
          <a-popover
            trigger="click"
            placement="bottomRight"
            overlay-class-name="learn-more-filter-popover"
          >
            <template #content>
              <div class="more-filter-panel">
                <div class="more-filter-item">
                  <span>难度</span>
                  <a-select
                    v-model:value="selectedDifficulty"
                    size="small"
                    :options="difficultyOptions"
                  />
                </div>
                <div class="more-filter-item">
                  <span>更新时间</span>
                  <a-select
                    v-model:value="selectedUpdateRange"
                    size="small"
                    :options="updateRangeOptions"
                  />
                </div>
                <a-button type="link" size="small" class="reset-link" @click="resetAdvancedFilters">
                  重置高级筛选
                </a-button>
              </div>
            </template>
            <button type="button" class="tools-link">更多筛选</button>
          </a-popover>
        </div>
      </div>

      <!-- 岗位分类 -->
      <div class="filter-row">
        <span class="lab">岗位分类</span>
        <div class="filter-opts">
          <button
            type="button"
            :class="['opt', { on: selectedPosition === 'all' }]"
            @click="selectedPosition = 'all'"
          >
            全部 {{ enrichedDatabases.length }}
          </button>
          <button
            v-for="item in positionTabs"
            :key="item.value"
            type="button"
            :class="['opt', { on: selectedPosition === item.value }]"
            @click="selectedPosition = item.value"
          >
            {{ item.label }} {{ item.count }}
          </button>
        </div>
        <div class="filter-row__spacer"></div>
        <div class="hot-row">
          <span class="lab">热门</span>
          <button
            v-for="term in hotKeywords"
            :key="term"
            type="button"
            :class="['hot-link', { on: isHotKeywordActive(term) }]"
            @click="applyHotKeyword(term)"
          >
            {{ term }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="state-panel">
        <a-spin size="large" />
        <p>正在加载可学习知识库...</p>
      </div>

      <a-result
        v-else-if="errorMessage"
        status="warning"
        title="知识库加载失败"
        :sub-title="errorMessage"
      />

      <template v-else>
        <!-- 专题网格 -->
        <div v-if="visibleDatabases.length" class="topic-grid">
          <article
            v-for="database in visibleDatabases"
            :key="database.db_id"
            class="topic-cell"
            @click="goToDatabase(database.db_id)"
          >
            <div class="topic-cell__head">
              <span class="topic-name">{{ database.name }}</span>
              <span class="badge">{{ database._positionLabel }}</span>
            </div>
            <p class="topic-desc">{{ database.description || '进入专题后查看详细知识内容。' }}</p>
            <div class="topic-progress__head">
              <span>学习进度</span>
              <span :class="['topic-progress__value', { muted: database._progress === 0 }]">
                {{ database._progress > 0 ? `${database._progress}%` : '未开始' }}
              </span>
            </div>
            <div class="bar">
              <span
                v-if="database._progress > 0"
                class="bar__fill"
                :style="{ width: `${database._progress}%` }"
              ></span>
            </div>
            <div class="topic-meta">
              <span>{{ database.file_count || 0 }} 篇文档</span>
              <span>已读 {{ database._masteredCount }} 篇</span>
              <span v-if="database._readLaterCount">稍后读 {{ database._readLaterCount }}</span>
            </div>
          </article>
        </div>

        <div v-else class="empty-panel">
          <p>没有符合条件的专题，试试调整关键词或筛选条件。</p>
          <a-button v-if="hasActiveFilters" class="btn-secondary" @click="resetAllFilters"
            >清空全部筛选</a-button
          >
        </div>

        <!-- 从面试弱项接着学 -->
        <section v-if="weakSpots.length" class="weak-section">
          <div class="weak-section__head">
            <span class="lab">从面试弱项接着学</span>
            <span class="weak-section__hint">{{ weakSourceText }}</span>
          </div>
          <div class="weak-grid">
            <button
              v-for="item in weakSpots"
              :key="item.key"
              type="button"
              class="weak-cell"
              @click="goToWeakSpot(item)"
            >
              <div class="weak-title">{{ item.title }}</div>
              <div class="weak-sub">{{ item.subtitle }}</div>
            </button>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { SearchOutlined } from '@ant-design/icons-vue'

import { learnApi } from '@/apis/learn_api'
import { interviewHistoryApi } from '@/apis/interview_history'
import { usePositionTypes } from '@/composables/usePositionTypes'
import { normalizePositionType } from '@/utils/position_utils'
import {
  computeDbProgress,
  countMastered,
  countReadLater,
  readGlobalLastDoc
} from '@/utils/learn_progress'

const router = useRouter()
const route = useRoute()
const { positionTypeOptions, loadPositionTypes, positionTypes } = usePositionTypes()

const loading = ref(false)
const errorMessage = ref('')
// Seed the search box from `?q=` so the interview result page can
// deep-link learners straight to a pre-filtered list.
const keyword = ref(String(route.query.q || '').trim())
const selectedPosition = ref('all')
const selectedDifficulty = ref('all')
const selectedUpdateRange = ref('all')
const sortMode = ref('progress')
const readLaterOnly = ref(false)
const databases = ref([])
const lastDoc = ref(null)
const weakSpots = ref([])
const weakSourceText = ref('')

const hotKeywords = ['前端', '后端', '算法', 'RAG', '系统设计']
const difficultyOptions = [
  { label: '全部难度', value: 'all' },
  { label: '基础', value: 'basic' },
  { label: '中等', value: 'intermediate' },
  { label: '进阶', value: 'advanced' }
]
const updateRangeOptions = [
  { label: '全部时间', value: 'all' },
  { label: '最近 30 天', value: '30d' },
  { label: '最近 90 天', value: '90d' }
]
const sortOptions = [
  { label: '按学习进度', value: 'progress' },
  { label: '最近更新优先', value: 'updated_desc' },
  { label: '文档数优先', value: 'files_desc' },
  { label: '名称 A-Z', value: 'name_asc' }
]

const DAY_MS = 24 * 60 * 60 * 1000

const parseTime = (value) => {
  const timestamp = Date.parse(String(value || ''))
  return Number.isFinite(timestamp) ? timestamp : null
}

const inferDifficulty = (fileCount) => {
  if (fileCount >= 36) return 'advanced'
  if (fileCount >= 16) return 'intermediate'
  return 'basic'
}

const matchesPosition = (item, position) =>
  item.position === position || item._positionKey === position || item._positionLabel === position

const enrichedDatabases = computed(() =>
  databases.value.map((item) => {
    const normalizedPosition = normalizePositionType(item.position, positionTypes.value, {
      fallbackToDefault: false
    })
    const fileCount = Number(item.file_count || 0)

    return {
      ...item,
      _positionKey: normalizedPosition?.key || '',
      _positionLabel: normalizedPosition?.short_label || normalizedPosition?.label || '未分类',
      _difficulty: inferDifficulty(fileCount),
      _progress: computeDbProgress(item.db_id, fileCount),
      _masteredCount: countMastered(item.db_id),
      _readLaterCount: countReadLater(item.db_id)
    }
  })
)

const positionTabs = computed(() =>
  (positionTypeOptions.value || [])
    .map((option) => ({
      value: option.value,
      label: option.shortLabel || option.label,
      count: enrichedDatabases.value.filter((item) => matchesPosition(item, option.value)).length
    }))
    .filter((tab) => tab.count > 0 || selectedPosition.value === tab.value)
)

const totalDocuments = computed(() =>
  enrichedDatabases.value.reduce((sum, item) => sum + Number(item.file_count || 0), 0)
)
const totalMastered = computed(() =>
  enrichedDatabases.value.reduce((sum, item) => sum + item._masteredCount, 0)
)
const totalReadLater = computed(() =>
  enrichedDatabases.value.reduce((sum, item) => sum + item._readLaterCount, 0)
)

const subtitleText = computed(() => {
  if (loading.value) return '正在加载...'
  return `${enrichedDatabases.value.length} 个专题 · ${totalDocuments.value} 篇文档 · 已读 ${totalMastered.value} 篇`
})

const visibleDatabases = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  const now = Date.now()
  const recentDays =
    selectedUpdateRange.value === '30d' ? 30 : selectedUpdateRange.value === '90d' ? 90 : 0

  const filtered = enrichedDatabases.value.filter((item) => {
    const matchedPosition =
      selectedPosition.value === 'all' || matchesPosition(item, selectedPosition.value)

    const matchedKeyword =
      !search ||
      [item.name, item.description, item._positionLabel].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(search)
      )

    const matchedDifficulty =
      selectedDifficulty.value === 'all' || item._difficulty === selectedDifficulty.value

    const updatedAt = parseTime(item.updated_at)
    const matchedUpdate = !recentDays || !updatedAt || now - updatedAt <= recentDays * DAY_MS

    const matchedReadLater = !readLaterOnly.value || item._readLaterCount > 0

    return (
      matchedPosition && matchedKeyword && matchedDifficulty && matchedUpdate && matchedReadLater
    )
  })

  if (sortMode.value === 'progress') {
    return [...filtered].sort((a, b) => b._progress - a._progress)
  }
  if (sortMode.value === 'updated_desc') {
    return [...filtered].sort(
      (a, b) => (parseTime(b.updated_at) || 0) - (parseTime(a.updated_at) || 0)
    )
  }
  if (sortMode.value === 'files_desc') {
    return [...filtered].sort((a, b) => Number(b.file_count || 0) - Number(a.file_count || 0))
  }
  if (sortMode.value === 'name_asc') {
    return [...filtered].sort((a, b) =>
      String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN')
    )
  }
  return filtered
})

const hasActiveFilters = computed(
  () =>
    keyword.value.trim() ||
    selectedPosition.value !== 'all' ||
    selectedDifficulty.value !== 'all' ||
    selectedUpdateRange.value !== 'all' ||
    readLaterOnly.value
)

const loadDatabases = async () => {
  loading.value = true
  errorMessage.value = ''

  try {
    const [data] = await Promise.all([learnApi.getDatabases(), loadPositionTypes()])
    databases.value = Array.isArray(data?.databases) ? data.databases : []
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

// 面试报告里的弱项：优先用带知识库定位的推荐资料，其次退回弱项标题搜索。
const loadWeakSpots = async () => {
  try {
    const path = await interviewHistoryApi.getPersonalizedPath()
    const resources = Array.isArray(path?.recommended_resources) ? path.recommended_resources : []
    const located = resources
      .filter((item) => item?.locator?.db_id && item?.locator?.file_id)
      .slice(0, 3)
      .map((item, index) => ({
        key: `resource-${index}`,
        title: String(item.title || '推荐资料').trim(),
        subtitle: String(item.source_ref || item.summary || '来自面试报告推荐').trim(),
        locator: item.locator
      }))

    const weaknesses = Array.isArray(path?.weaknesses) ? path.weaknesses : []
    const fallback = weaknesses.slice(0, 3).map((item, index) => ({
      key: `weakness-${index}`,
      title: String(item.title || '').trim(),
      subtitle: '在知识库中搜索相关文档',
      searchText: String(item.title || '').trim()
    }))

    weakSpots.value = (located.length ? located : fallback).filter((item) => item.title)
    weakSourceText.value = path?.source_round_count
      ? `来自最近 ${path.source_round_count} 轮面试`
      : '来自面试报告'
  } catch {
    weakSpots.value = []
  }
}

const applyHotKeyword = (term) => {
  keyword.value = term
}

const isHotKeywordActive = (term) => keyword.value.trim().toLowerCase() === term.toLowerCase()

const resetAdvancedFilters = () => {
  selectedDifficulty.value = 'all'
  selectedUpdateRange.value = 'all'
}

const resetAllFilters = () => {
  keyword.value = ''
  selectedPosition.value = 'all'
  readLaterOnly.value = false
  resetAdvancedFilters()
}

const goToDatabase = (dbId) => {
  router.push(`/learn/${dbId}`)
}

const continueLearning = () => {
  if (!lastDoc.value?.dbId || !lastDoc.value?.fileId) return
  router.push(`/learn/${lastDoc.value.dbId}/doc/${lastDoc.value.fileId}`)
}

const goToWeakSpot = (item) => {
  if (item.locator) {
    router.push(`/learn/${item.locator.db_id}/doc/${item.locator.file_id}`)
    return
  }
  keyword.value = item.searchText || ''
}

onMounted(() => {
  lastDoc.value = readGlobalLastDoc()
  loadDatabases()
  loadWeakSpots()
})
</script>

<style scoped lang="less">
// 设计稿 [UI v3][2k] 知识学习 · 一级
.learn-home {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

// ===================== 顶栏 =====================
.page-topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0;
  color: var(--gray-1000);
}

.page-subtitle {
  font-size: 13px;
  color: var(--gray-500);
  margin: 6px 0 0;
}

.topbar-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.topbar-actions,
.empty-panel {
  :deep(.btn-secondary.ant-btn) {
    display: inline-flex;
    align-items: center;
    height: 34px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid var(--gray-200);
    background: var(--gray-0);
    color: var(--gray-700);
    border-radius: 0;
    box-shadow: none;

    &:hover,
    &:focus {
      border-color: var(--gray-500) !important;
      color: var(--gray-1000) !important;
    }
  }

  :deep(.btn-secondary--on.ant-btn) {
    background: var(--gray-100);
    color: var(--gray-1000);
    font-weight: 700;
  }

  :deep(.btn-primary.ant-btn) {
    display: inline-flex;
    align-items: center;
    height: 34px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 0;
    background: var(--main-color);
    border-color: var(--main-color);
    color: #fff;
    box-shadow: none;

    &:hover,
    &:focus {
      background: var(--main-700) !important;
      border-color: var(--main-700) !important;
      color: #fff !important;
    }
  }

  :deep(.btn-primary.ant-btn[disabled]) {
    background: var(--gray-100);
    border-color: var(--gray-200);
    color: var(--gray-500);
  }
}

// ===================== 主体 =====================
.page-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 24px 32px;
}

.lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
  white-space: nowrap;
}

// ===================== 搜索栏 =====================
.search-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  border: 1px solid var(--gray-200);
}

.search-bar__input {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 46px;
  padding: 0 18px;
  border-right: 1px solid var(--gray-100);

  .search-icon {
    color: var(--gray-500);
    font-size: 15px;
  }

  .search-input {
    flex: 1;
    min-width: 0;
    border: none;
    outline: none;
    background: transparent;
    font-size: 14px;
    color: var(--gray-1000);

    &::placeholder {
      color: var(--gray-500);
    }
  }
}

.search-bar__tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  padding: 0 14px;
}

.flat-select {
  min-width: 128px;

  :deep(.ant-select-selector) {
    padding-right: 0 !important;
  }

  :deep(.ant-select-selection-item) {
    font-size: 13px;
    color: var(--gray-600);
  }
}

.tools-divider {
  color: var(--gray-400);
  font-size: 13px;
}

.tools-link {
  border: none;
  background: transparent;
  padding: 0 4px;
  font-size: 13px;
  color: var(--gray-600);
  cursor: pointer;

  &:hover {
    color: var(--gray-1000);
  }
}

.more-filter-panel {
  width: 220px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.more-filter-item {
  display: flex;
  flex-direction: column;
  gap: 6px;

  > span {
    font-size: 12px;
    color: var(--gray-500);
  }
}

.reset-link {
  align-self: flex-start;
  padding: 0;
}

// ===================== 岗位分类 =====================
.filter-row {
  display: flex;
  align-items: center;
  gap: 22px;
  padding: 18px 0 0;
}

.filter-row__spacer {
  flex: 1;
}

.filter-opts {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.opt {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 14px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  font-size: 13px;
  color: var(--gray-700);
  cursor: pointer;

  &:hover {
    color: var(--gray-1000);
  }

  &.on {
    background: var(--gray-100);
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.hot-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hot-link {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 13px;
  color: var(--gray-600);
  cursor: pointer;

  &:hover {
    color: var(--gray-1000);
  }

  &.on {
    color: var(--main-color);
    font-weight: 700;
  }
}

// ===================== 专题网格 =====================
.topic-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid var(--gray-200);
  margin-top: 20px;
}

.topic-cell {
  padding: 24px 26px 26px;
  border-right: 1px solid var(--gray-100);
  border-bottom: 1px solid var(--gray-100);
  cursor: pointer;

  &:nth-child(3n) {
    border-right: none;
    padding-right: 0;
  }

  &:nth-child(3n + 1) {
    padding-left: 0;
  }

  &:hover .topic-name {
    color: var(--main-color);
  }
}

.topic-cell__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.topic-name {
  font-size: 20px;
  font-weight: 800;
  color: var(--gray-1000);
  line-height: 1.3;
}

.badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid var(--gray-200);
  color: var(--gray-600);
  white-space: nowrap;
  flex-shrink: 0;
}

.topic-desc {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.topic-progress__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 20px;
}

.topic-progress__value {
  color: var(--gray-1000);
  font-weight: 700;

  &.muted {
    color: var(--gray-500);
  }
}

.bar {
  height: 6px;
  background: var(--gray-100);
  margin-top: 8px;
}

.bar__fill {
  display: block;
  height: 100%;
  background: var(--main-color);
}

.topic-meta {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--gray-600);
  margin-top: 16px;
}

// ===================== 面试弱项 =====================
.weak-section {
  border-top: 1px solid var(--gray-200);
  margin-top: 8px;
  padding: 24px 0 0;
}

.weak-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.weak-section__hint {
  font-size: 12px;
  color: var(--gray-500);
}

.weak-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 14px;
}

.weak-cell {
  border: none;
  border-right: 1px solid var(--gray-100);
  background: transparent;
  text-align: left;
  padding: 14px 24px;
  cursor: pointer;

  &:first-child {
    padding-left: 0;
  }

  &:last-child {
    border-right: none;
    padding-right: 0;
  }

  &:hover .weak-title {
    color: var(--main-color);
  }
}

.weak-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-1000);
}

.weak-sub {
  font-size: 13px;
  color: var(--gray-600);
  margin-top: 5px;
}

// ===================== 状态 =====================
.state-panel {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--gray-600);
}

.empty-panel {
  border-top: 1px solid var(--gray-200);
  margin-top: 20px;
  padding: 40px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--gray-600);

  p {
    margin: 0;
    font-size: 14px;
  }
}

@media (max-width: 1280px) {
  .topic-grid,
  .weak-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .topic-cell {
    &:nth-child(3n),
    &:nth-child(3n + 1) {
      padding-left: 26px;
      padding-right: 26px;
      border-right: 1px solid var(--gray-100);
    }

    &:nth-child(2n) {
      border-right: none;
      padding-right: 0;
    }

    &:nth-child(2n + 1) {
      padding-left: 0;
    }
  }
}

@media (max-width: 900px) {
  .page-topbar,
  .page-body {
    padding-left: 18px;
    padding-right: 18px;
  }

  .search-bar {
    grid-template-columns: 1fr;
  }

  .search-bar__input {
    border-right: none;
    border-bottom: 1px solid var(--gray-100);
  }

  .filter-row {
    flex-wrap: wrap;
    gap: 12px;
  }

  .topic-grid,
  .weak-grid {
    grid-template-columns: 1fr;
  }

  .topic-cell {
    &:nth-child(n) {
      padding: 20px 0;
      border-right: none;
    }
  }

  .weak-cell {
    &:nth-child(n) {
      padding: 14px 0;
      border-right: none;
      border-bottom: 1px solid var(--gray-100);
    }
  }
}
</style>
