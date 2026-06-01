<template>
  <div class="learn-home">
    <section class="hero-card enter-fade-up">
      <div class="hero-copy">
        <span class="hero-badge">知识学习</span>
        <div class="hero-title-wrap">
          <span class="title-accent"></span>
          <h1>
            按专题学习管理员维护的
            <span>知识库内容</span>
          </h1>
        </div>
        <p>面向面试者的轻学习入口，支持按岗位筛选、专题浏览和文档学习。</p>
        <div class="hero-sub-meta">当前共 {{ databases.length }} 个专题，筛选后 {{ visibleDatabases.length }} 个</div>
      </div>

      <div class="hero-search">
        <a-input
          v-model:value="keyword"
          size="large"
          allow-clear
          placeholder="搜索知识库名称或简介"
        >
          <template #prefix>
            <SearchOutlined />
          </template>
        </a-input>

        <div class="hot-search">
          <span class="hot-search__label">热门搜索</span>
          <div class="hot-search__pills">
            <button
              v-for="term in hotKeywords"
              :key="term"
              type="button"
              :class="['hot-pill', { active: isHotKeywordActive(term) }]"
              @click="applyHotKeyword(term)"
            >
              {{ term }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section class="filter-card enter-fade-up enter-delay-1">
      <div class="filter-header">
        <div class="filter-label">岗位分类</div>
        <a-popover trigger="click" placement="bottomRight" overlay-class-name="learn-more-filter-popover">
          <template #content>
            <div class="more-filter-panel">
              <div class="more-filter-item">
                <span>难度</span>
                <a-select v-model:value="selectedDifficulty" size="small" :options="difficultyOptions" />
              </div>
              <div class="more-filter-item">
                <span>更新时间</span>
                <a-select v-model:value="selectedUpdateRange" size="small" :options="updateRangeOptions" />
              </div>
              <div class="more-filter-item">
                <span>排序</span>
                <a-select v-model:value="sortMode" size="small" :options="sortOptions" />
              </div>
              <a-button type="link" size="small" class="reset-link" @click="resetAdvancedFilters">
                重置高级筛选
              </a-button>
            </div>
          </template>
          <a-button class="more-filter-btn">
            更多筛选
            <DownOutlined />
          </a-button>
        </a-popover>
      </div>

      <div class="filter-pills">
        <button
          type="button"
          :class="['pill', { active: selectedPosition === 'all' }]"
          @click="selectedPosition = 'all'"
        >
          全部
        </button>
        <button
          v-for="item in positionOptions"
          :key="item.value"
          type="button"
          :class="['pill', { active: selectedPosition === item.value }]"
          @click="selectedPosition = item.value"
        >
          {{ item.shortLabel || item.label }}
        </button>
      </div>
    </section>

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
      <transition-group v-if="visibleDatabases.length" name="database-list" tag="div" class="database-grid">
        <article
          v-for="(database, index) in visibleDatabases"
          :key="database.db_id"
          class="database-card"
          :style="{ '--stagger-index': index }"
          @click="goToDatabase(database.db_id)"
        >
          <div class="database-card__top">
            <div
              class="database-card__icon"
              :style="{ background: database._theme.softBg, color: database._theme.color }"
            >
              <component :is="database._theme.icon" :size="20" />
            </div>

            <div class="database-card__meta">
              <h3>{{ database.name }}</h3>
              <p>{{ database.description || '进入专题后查看详细知识内容。' }}</p>
            </div>
          </div>

          <div class="database-card__progress">
            <div class="progress-head">
              <span>学习进度</span>
              <span>{{ database._progress }}%</span>
            </div>
            <div class="progress-track">
              <span class="progress-fill" :style="{ width: `${database._progress}%`, background: database._theme.color }"></span>
            </div>
          </div>

          <div class="database-card__footer">
            <span
              class="role-tag"
              :style="{ '--role-color': database._theme.color, '--role-bg': database._theme.tagBg }"
            >
              <span class="dot"></span>
              {{ database._position.short_label || database._position.label || '未分类' }}
            </span>
            <span class="doc-count">
              <FileText :size="14" />
              {{ database.file_count || 0 }}
            </span>
          </div>
        </article>
      </transition-group>

      <a-empty v-else>
        <template #description>
          <div class="empty-state">
            <p>没有符合条件的专题，试试调整关键词或筛选条件。</p>
            <a-button v-if="hasActiveFilters" type="link" @click="resetAllFilters">清空全部筛选</a-button>
          </div>
        </template>
      </a-empty>
    </template>

    <a-tooltip title="返回顶部">
      <button type="button" class="floating-action" @click="scrollToTop">
        <UpOutlined />
      </button>
    </a-tooltip>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DownOutlined, SearchOutlined, UpOutlined } from '@ant-design/icons-vue'
import { BookOpen, BrainCircuit, Code2, Database, FileText, Network, Sparkles } from 'lucide-vue-next'

import { learnApi } from '@/apis/learn_api'
import { usePositionTypes } from '@/composables/usePositionTypes'
import { normalizePositionType } from '@/utils/position_utils'

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
const sortMode = ref('default')
const databases = ref([])

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
  { label: '默认排序', value: 'default' },
  { label: '最近更新优先', value: 'updated_desc' },
  { label: '文档数优先', value: 'files_desc' },
  { label: '名称 A-Z', value: 'name_asc' }
]

const POSITION_THEME_MAP = {
  frontend: {
    color: '#F59E0B',
    softBg: 'rgba(245, 158, 11, 0.16)',
    tagBg: 'rgba(245, 158, 11, 0.12)',
    icon: Code2
  },
  backend: {
    color: '#10B981',
    softBg: 'rgba(16, 185, 129, 0.16)',
    tagBg: 'rgba(16, 185, 129, 0.12)',
    icon: Database
  },
  algorithm: {
    color: '#8B5CF6',
    softBg: 'rgba(139, 92, 246, 0.16)',
    tagBg: 'rgba(139, 92, 246, 0.12)',
    icon: BrainCircuit
  },
  ai_app: {
    color: '#EC4899',
    softBg: 'rgba(236, 72, 153, 0.16)',
    tagBg: 'rgba(236, 72, 153, 0.12)',
    icon: Sparkles
  },
  system_design: {
    color: '#3B82F6',
    softBg: 'rgba(59, 130, 246, 0.16)',
    tagBg: 'rgba(59, 130, 246, 0.12)',
    icon: Network
  },
  unclassified: {
    color: '#64748B',
    softBg: 'rgba(100, 116, 139, 0.16)',
    tagBg: 'rgba(100, 116, 139, 0.12)',
    icon: BookOpen
  }
}

const DAY_MS = 24 * 60 * 60 * 1000

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const parseTime = (value) => {
  const timestamp = Date.parse(String(value || ''))
  return Number.isFinite(timestamp) ? timestamp : null
}

const inferDifficulty = (fileCount) => {
  if (fileCount >= 36) return 'advanced'
  if (fileCount >= 16) return 'intermediate'
  return 'basic'
}

const positionOptions = computed(() => positionTypeOptions.value || [])

const maxFileCount = computed(() =>
  databases.value.reduce((max, item) => Math.max(max, Number(item.file_count || 0)), 0)
)

const toProgressPercent = (item) => {
  const rawProgress = Number(item.learning_progress ?? item.progress)
  if (Number.isFinite(rawProgress)) {
    return clamp(Math.round(rawProgress), 0, 100)
  }

  const fileCount = Number(item.file_count || 0)
  if (fileCount <= 0 || maxFileCount.value <= 0) {
    return 0
  }

  const normalized = Math.round((fileCount / maxFileCount.value) * 100)
  return clamp(Math.max(20, normalized), 0, 100)
}

const enrichedDatabases = computed(() =>
  databases.value.map((item) => {
    const normalizedPosition = normalizePositionType(item.position, positionTypes.value, {
      fallbackToDefault: false
    })
    const theme = POSITION_THEME_MAP[normalizedPosition?.key] || POSITION_THEME_MAP.unclassified
    const fileCount = Number(item.file_count || 0)

    return {
      ...item,
      _position: normalizedPosition,
      _theme: theme,
      _difficulty: inferDifficulty(fileCount),
      _progress: toProgressPercent(item)
    }
  })
)

const visibleDatabases = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  const now = Date.now()
  const recentDays = selectedUpdateRange.value === '30d' ? 30 : selectedUpdateRange.value === '90d' ? 90 : 0

  const filtered = enrichedDatabases.value.filter((item) => {
    const matchesPosition =
      selectedPosition.value === 'all' ||
      item.position === selectedPosition.value ||
      item._position?.label === selectedPosition.value ||
      item._position?.short_label === selectedPosition.value

    const matchesKeyword =
      !search ||
      [item.name, item.description, item._position?.label, item._position?.short_label].some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(search)
      )

    const matchesDifficulty = selectedDifficulty.value === 'all' || item._difficulty === selectedDifficulty.value

    const updatedAt = parseTime(item.updated_at)
    const matchesUpdate = !recentDays || !updatedAt || now - updatedAt <= recentDays * DAY_MS

    return matchesPosition && matchesKeyword && matchesDifficulty && matchesUpdate
  })

  if (sortMode.value === 'updated_desc') {
    return [...filtered].sort((a, b) => (parseTime(b.updated_at) || 0) - (parseTime(a.updated_at) || 0))
  }
  if (sortMode.value === 'files_desc') {
    return [...filtered].sort((a, b) => Number(b.file_count || 0) - Number(a.file_count || 0))
  }
  if (sortMode.value === 'name_asc') {
    return [...filtered].sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN'))
  }
  return filtered
})

const hasActiveFilters = computed(
  () =>
    keyword.value.trim() ||
    selectedPosition.value !== 'all' ||
    selectedDifficulty.value !== 'all' ||
    selectedUpdateRange.value !== 'all' ||
    sortMode.value !== 'default'
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

const applyHotKeyword = (term) => {
  keyword.value = term
}

const isHotKeywordActive = (term) => keyword.value.trim().toLowerCase() === term.toLowerCase()

const resetAdvancedFilters = () => {
  selectedDifficulty.value = 'all'
  selectedUpdateRange.value = 'all'
  sortMode.value = 'default'
}

const resetAllFilters = () => {
  keyword.value = ''
  selectedPosition.value = 'all'
  resetAdvancedFilters()
}

const goToDatabase = (dbId) => {
  router.push(`/learn/${dbId}`)
}

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  loadDatabases()
})
</script>

<style scoped lang="less">
.learn-home {
  position: relative;
  min-height: 100%;
  padding: 28px;
  background: linear-gradient(180deg, #f5f9ff 0%, #eef4ff 42%, #f8fafc 100%);

  &::before {
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 220px;
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.14), rgba(59, 130, 246, 0));
    pointer-events: none;
  }

  &::after {
    content: '';
    position: absolute;
    right: -120px;
    top: 120px;
    width: 360px;
    height: 360px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.14) 0%, rgba(99, 102, 241, 0) 70%);
    pointer-events: none;
  }

  > * {
    position: relative;
    z-index: 1;
  }
}

.enter-fade-up {
  animation: fade-up-in 0.4s ease both;
}

.enter-delay-1 {
  animation-delay: 0.08s;
}

.hero-card,
.filter-card {
  position: relative;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.74);
  border-radius: 24px;
  box-shadow:
    0 10px 28px rgba(15, 23, 42, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px) saturate(145%);
  -webkit-backdrop-filter: blur(16px) saturate(145%);
}

.hero-card::before,
.filter-card::before,
.database-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 44%;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0));
  pointer-events: none;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 28px;
  padding: 30px 32px;
  margin-bottom: 20px;
}

.hero-copy {
  max-width: 760px;

  p {
    margin: 0;
    font-size: 15px;
    line-height: 1.8;
    color: var(--gray-600);
  }
}

.hero-title-wrap {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin: 12px 0 10px;

  h1 {
    margin: 0;
    font-size: 32px;
    line-height: 1.2;
    color: var(--gray-2000);
  }

  span {
    background: linear-gradient(90deg, #2563eb, #7c3aed);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
}

.title-accent {
  width: 4px;
  height: 36px;
  border-radius: 999px;
  background: var(--main-400);
  margin-top: 2px;
}

.hero-sub-meta {
  margin-top: 14px;
  font-size: 14px;
  color: var(--gray-500);
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--main-50);
  color: var(--main-700);
  font-size: 13px;
  font-weight: 600;
}

.hero-search {
  width: 420px;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;

  :deep(.ant-input-affix-wrapper) {
    min-height: 46px;
    border-radius: 14px;
    border-color: var(--gray-200);
    background: var(--gray-0);
    transition:
      border-color 0.2s ease,
      box-shadow 0.2s ease,
      background-color 0.2s ease;
  }

  :deep(.ant-input-prefix) {
    color: var(--gray-500);
  }

  :deep(.ant-input-affix-wrapper-focused) {
    border-color: var(--main-300);
    box-shadow: 0 0 0 2px var(--main-50);
  }
}

.hot-search {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.46);
  box-shadow:
    0 8px 18px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px) saturate(130%);
  -webkit-backdrop-filter: blur(10px) saturate(130%);
}

.hot-search__label {
  margin: 0;
  color: var(--gray-700);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
}

.hot-search__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hot-pill {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--gray-0);
  color: var(--gray-600);
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  line-height: 1;
  cursor: pointer;
  transition:
    color 0.2s ease,
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    color: var(--main-700);
    box-shadow: 0 4px 12px var(--shadow-0);
  }

  &.active {
    color: var(--main-800);
    border-color: var(--main-300);
    background: var(--main-50);
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.18);
  }
}

.filter-card {
  padding: 18px 20px;
  margin-bottom: 24px;
}

.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.filter-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.more-filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 10px;
  color: var(--gray-700);
}

:deep(.learn-more-filter-popover .ant-popover-inner) {
  border-radius: 14px;
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

.filter-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.pill {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--gray-10);
  color: var(--gray-700);
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;

  &.active {
    border-color: var(--main-300);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.database-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
}

.database-card {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 248px;
  padding: 22px;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.55);
  box-shadow:
    0 12px 26px rgba(15, 23, 42, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  cursor: pointer;
  transition:
    transform 0.22s ease,
    border-color 0.22s ease,
    box-shadow 0.22s ease;

  &:hover {
    transform: translateY(-4px);
    border-color: rgba(147, 197, 253, 0.9);
    box-shadow:
      0 20px 40px rgba(59, 130, 246, 0.14),
      inset 0 1px 0 rgba(255, 255, 255, 0.82);
  }
}

.database-card__top {
  display: flex;
  gap: 14px;
}

.database-card__icon {
  width: 50px;
  height: 50px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.database-card__meta {
  min-width: 0;

  h3 {
    margin: 0 0 8px;
    font-size: 19px;
    color: var(--gray-2000);
  }

  p {
    margin: 0;
    color: var(--gray-600);
    line-height: 1.7;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

.database-card__progress {
  margin-top: 16px;
}

.progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  color: var(--gray-600);
  font-size: 12px;
}

.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.68);
  overflow: hidden;
}

.progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  transition: width 0.25s ease;
}

.database-card__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.role-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 4px 10px;
  color: var(--role-color);
  background: var(--role-bg);
  font-size: 12px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--role-color);
}

.doc-count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--gray-600);
  font-size: 13px;
}

.database-list-enter-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease,
    filter 0.28s ease;
  transition-delay: calc(var(--stagger-index, 0) * 0.03s);
}

.database-list-enter-from {
  opacity: 0;
  transform: translateY(10px);
  filter: blur(2px);
}

.database-list-leave-active {
  transition: opacity 0.15s ease;
}

.database-list-leave-to {
  opacity: 0;
}

.state-panel {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--gray-600);
}

.empty-state {
  color: var(--gray-600);

  p {
    margin: 0 0 6px;
  }
}

.floating-action {
  position: fixed;
  right: 30px;
  bottom: 30px;
  width: 42px;
  height: 42px;
  border: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: var(--main-600);
  color: var(--gray-0);
  box-shadow: 0 12px 26px rgba(59, 130, 246, 0.32);
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;

  &:hover {
    background: var(--main-700);
    transform: translateY(-2px);
  }
}

@keyframes fade-up-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  .learn-home {
    padding: 18px;
  }

  .hero-card {
    flex-direction: column;
    padding: 22px;
  }

  .hero-title-wrap h1 {
    font-size: 28px;
  }

  .hero-search {
    width: 100%;
  }

  .hot-search {
    padding: 10px;
  }

  .database-grid {
    gap: 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .enter-fade-up,
  .database-list-enter-active,
  .database-list-leave-active,
  .database-card,
  .floating-action,
  .progress-fill,
  .hero-search :deep(.ant-input-affix-wrapper) {
    animation: none !important;
    transition: none !important;
    transform: none !important;
  }
}
</style>
