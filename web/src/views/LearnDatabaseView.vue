<template>
  <div class="learn-database">
    <!-- 顶栏 -->
    <div class="page-topbar">
      <div class="topbar-left">
        <h1 class="page-title">{{ database?.name || '知识专题' }}</h1>
        <p class="page-subtitle">{{ subtitleText }}</p>
      </div>
      <div class="topbar-actions">
        <a-button class="btn-secondary" @click="router.push('/learn')">返回专题列表</a-button>
        <a-button
          type="primary"
          class="btn-primary"
          :disabled="!lastLearnDoc"
          @click="continueLearning"
        >
          {{ lastLearnDoc ? `继续学习：${lastLearnDoc.title}` : '尚无学习记录' }}
        </a-button>
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
      <p>正在加载专题内容...</p>
    </div>

    <a-result
      v-else-if="errorMessage"
      status="warning"
      title="专题加载失败"
      :sub-title="errorMessage"
    />

    <div v-else-if="database" class="page-body">
      <!-- 左：分类导航 + 专题进度 -->
      <aside class="side-nav">
        <div class="side-nav__list">
          <div class="lab side-nav__lab">分类导航</div>
          <button
            v-for="item in categoryOptions"
            :key="item.value"
            type="button"
            :class="['nav-item', { on: selectedCategory === item.value }]"
            @click="selectedCategory = item.value"
          >
            <span class="nav-item__label">{{ item.label }}</span>
            <span class="nav-item__count">{{ item.count }}</span>
          </button>
        </div>

        <div class="side-nav__progress">
          <div class="lab">专题进度</div>
          <div class="progress-number">
            <span class="progress-number__value">{{ topicProgress }}</span>
            <span class="progress-number__unit">%</span>
          </div>
          <div class="bar">
            <span
              v-if="topicProgress > 0"
              class="bar__fill"
              :style="{ width: `${topicProgress}%` }"
            ></span>
          </div>
          <div class="progress-hint">
            已读 {{ masteredCount }} / {{ totalDocuments }} 篇<br />
            累计 {{ readDurationText }}
          </div>
        </div>
      </aside>

      <!-- 右：文档列表 -->
      <section class="doc-panel">
        <div class="doc-panel__filters">
          <button
            v-for="tab in statusTabs"
            :key="tab.value"
            type="button"
            :class="['opt', { on: activeStatus === tab.value }]"
            @click="activeStatus = tab.value"
          >
            {{ tab.label }}{{ tab.value === 'all' ? '' : ` ${tab.count}` }}
          </button>
          <div class="doc-panel__spacer"></div>
          <div class="doc-search">
            <SearchOutlined class="search-icon" />
            <input v-model="keyword" class="search-input" placeholder="搜索文档" />
          </div>
          <a-select
            v-model:value="sortMode"
            :options="sortOptions"
            :bordered="false"
            size="small"
            class="flat-select"
          />
        </div>

        <div class="doc-panel__body" @scroll="handleAutoLoad">
          <template v-if="visibleGroups.length">
            <div v-for="group in visibleGroups" :key="group.key" class="doc-group">
              <div class="doc-group__head">
                <span class="doc-group__title">{{ group.label }}</span>
                <span class="doc-group__meta"
                  >{{ group.total }} 篇 · 已读 {{ group.masteredCount }} 篇</span
                >
              </div>
              <div class="doc-group__list">
                <article
                  v-for="document in group.items"
                  :key="document.file_id"
                  class="doc-row"
                  @click="goToDocument(document.file_id)"
                >
                  <div class="doc-row__main">
                    <div class="doc-row__title">
                      <span class="doc-title">{{ document.displayName }}</span>
                      <span :class="['badge', `badge--${document.status}`]">{{
                        document.statusLabel
                      }}</span>
                      <span v-if="document.isFavorite" class="badge badge--fav">已收藏</span>
                    </div>
                    <p class="doc-preview">{{ document.preview }}</p>
                    <div class="doc-meta">
                      <span>{{ document.categoryLabel }}</span>
                      <span>{{ document.readMinutes }} 分钟</span>
                      <a-tooltip :title="document.fullTime">
                        <span>{{ document.relativeTime }}</span>
                      </a-tooltip>
                      <span v-if="document.isReadLater">稍后读</span>
                    </div>
                  </div>

                  <div class="doc-row__progress">
                    <div class="doc-row__progress-head">
                      <span>阅读进度</span>
                      <span :class="['doc-row__progress-value', { muted: !document.progress }]">
                        {{ document.progress ? `${document.progress}%` : '—' }}
                      </span>
                    </div>
                    <div class="bar bar--thin">
                      <span
                        v-if="document.progress"
                        class="bar__fill"
                        :class="{ 'bar__fill--done': document.progress >= 100 }"
                        :style="{ width: `${document.progress}%` }"
                      ></span>
                    </div>
                  </div>

                  <div class="doc-row__actions">
                    <button
                      type="button"
                      class="icon-btn"
                      :title="document.isFavorite ? '取消收藏' : '收藏'"
                      @click.stop="toggleFavorite(document.file_id)"
                    >
                      <StarFilled v-if="document.isFavorite" />
                      <StarOutlined v-else />
                    </button>
                    <button
                      type="button"
                      class="icon-btn"
                      :title="document.isReadLater ? '取消稍后读' : '加入稍后读'"
                      @click.stop="toggleReadLater(document.file_id)"
                    >
                      <ClockCircleOutlined />
                    </button>
                    <button
                      type="button"
                      class="icon-btn"
                      title="复制学习链接"
                      @click.stop="shareDocument(document)"
                    >
                      <ShareAltOutlined />
                    </button>
                    <button
                      type="button"
                      :class="['row-btn', { 'row-btn--primary': document.status === 'review' }]"
                      @click.stop="goToDocument(document.file_id)"
                    >
                      {{ document.actionLabel }}
                    </button>
                  </div>
                </article>
              </div>
            </div>

            <div class="load-footer">
              <span>已加载 {{ visibleDocuments.length }} / {{ filteredDocuments.length }} 篇</span>
              <button v-if="hasMore" type="button" class="row-btn" @click="loadMore">
                加载更多
              </button>
            </div>
          </template>

          <div v-else class="empty-panel">
            <p>{{ keyword ? `未找到“${keyword}”相关文档` : '当前筛选条件下没有文档' }}</p>
            <button type="button" class="row-btn" @click="resetFilters">清空筛选</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ClockCircleOutlined,
  SearchOutlined,
  ShareAltOutlined,
  StarFilled,
  StarOutlined
} from '@ant-design/icons-vue'

import { learnApi } from '@/apis/learn_api'
import { formatDateTime, formatRelative } from '@/utils/time'
import {
  countReadMinutes,
  persistFavoriteIds,
  persistGlobalLastDoc,
  persistLastDoc,
  persistReadLaterIds,
  persistVisitCounts,
  readFavoriteIds,
  readLastDoc,
  readMasteryMap,
  readReadLaterIds,
  readVisitCounts
} from '@/utils/learn_progress'

const PAGE_STEP = 40

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const errorMessage = ref('')
const keyword = ref('')
const selectedCategory = ref('all')
const sortMode = ref('category')
const activeStatus = ref('all')
const visibleCount = ref(PAGE_STEP)
const database = ref(null)
const favoriteIds = ref(new Set())
const readLaterIds = ref(new Set())
const masteryMap = ref({})
const visitCounts = ref({})
const lastLearnDoc = ref(null)
const readMinutesTotal = ref(0)

const sortOptions = [
  { label: '按分类顺序', value: 'category' },
  { label: '最近更新', value: 'updated_desc' },
  { label: '名称 A-Z', value: 'title_asc' },
  { label: '阅读时长长优先', value: 'read_desc' }
]

const STATUS_LABELS = {
  mastered: '已读',
  progress: '进行中',
  review: '标记复习',
  todo: '未读'
}

const dbId = computed(() => String(route.params.db_id || '').trim())

const parseTimestamp = (value) => {
  const timestamp = Date.parse(String(value || ''))
  return Number.isFinite(timestamp) ? timestamp : 0
}

const formatDisplayName = (value) => String(value || '').replace(/\.md$/i, '')

const estimateReadMinutes = (title, summary) => {
  const text = `${title || ''} ${summary || ''}`
  const minutes = Math.round(text.length / 45)
  return Math.min(45, Math.max(5, minutes))
}

const getCategoryKey = (document) => {
  const folderPath = String(document.folder_path || '').trim()
  if (!folderPath) return 'root'
  return folderPath.split('/').filter(Boolean)[0] || 'root'
}

const normalizedDocuments = computed(() => {
  const documents = Array.isArray(database.value?.documents) ? database.value.documents : []
  return documents.map((item) => {
    const id = String(item.file_id || '')
    const displayName = formatDisplayName(item.filename)
    const summary = String(item.summary || '').trim()
    const previewBase = summary || '暂无摘要，点击进入学习。'
    const preview = previewBase.length > 120 ? `${previewBase.slice(0, 120)}...` : previewBase
    const categoryKey = getCategoryKey(item)
    const mastery = masteryMap.value[id]
    const visitProgress = Math.min(100, Math.max(0, Number(visitCounts.value[id] || 0) * 25))
    const progress = mastery === 'mastered' ? 100 : visitProgress
    const status =
      mastery === 'mastered'
        ? 'mastered'
        : mastery === 'review'
          ? 'review'
          : progress > 0
            ? 'progress'
            : 'todo'
    const updatedTs = parseTimestamp(item.updated_at)

    return {
      ...item,
      displayName,
      preview,
      categoryKey,
      categoryLabel: categoryKey === 'root' ? '根目录' : categoryKey,
      readMinutes: estimateReadMinutes(displayName, summary),
      progress,
      status,
      statusLabel: STATUS_LABELS[status],
      actionLabel: status === 'mastered' ? '重读' : status === 'todo' ? '开始学习' : '继续学习',
      updatedTs,
      relativeTime: updatedTs ? formatRelative(item.updated_at) : '—',
      fullTime: updatedTs ? formatDateTime(item.updated_at, 'YYYY-MM-DD HH:mm:ss') : '—',
      isFavorite: favoriteIds.value.has(id),
      isReadLater: readLaterIds.value.has(id)
    }
  })
})

const totalDocuments = computed(() => normalizedDocuments.value.length)
const masteredCount = computed(
  () => normalizedDocuments.value.filter((item) => item.status === 'mastered').length
)
const topicProgress = computed(() =>
  totalDocuments.value ? Math.round((masteredCount.value / totalDocuments.value) * 100) : 0
)

const categoryOptions = computed(() => {
  const counter = new Map()
  normalizedDocuments.value.forEach((item) => {
    counter.set(item.categoryKey, (counter.get(item.categoryKey) || 0) + 1)
  })

  const entries = [...counter.entries()]
    .map(([value, count]) => ({
      value,
      count,
      label: value === 'root' ? '根目录' : value
    }))
    .sort((a, b) => b.count - a.count)

  return [{ value: 'all', label: '全部文档', count: normalizedDocuments.value.length }, ...entries]
})

const statusTabs = computed(() => {
  const countBy = (predicate) => normalizedDocuments.value.filter(predicate).length
  return [
    { value: 'all', label: '全部', count: totalDocuments.value },
    { value: 'todo', label: '未读', count: countBy((item) => item.status === 'todo') },
    { value: 'progress', label: '进行中', count: countBy((item) => item.status === 'progress') },
    { value: 'review', label: '标记复习', count: countBy((item) => item.status === 'review') },
    { value: 'readLater', label: '稍后读', count: countBy((item) => item.isReadLater) },
    { value: 'favorite', label: '收藏', count: countBy((item) => item.isFavorite) }
  ]
})

const readDurationText = computed(() => {
  const minutes = readMinutesTotal.value
  if (minutes < 60) return `${minutes} 分钟`
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`
})

const subtitleText = computed(() => {
  const position = String(database.value?.position || '').trim()
  const categoryCount = Math.max(0, categoryOptions.value.length - 1)
  const parts = [
    position,
    `${totalDocuments.value} 篇文档`,
    `${categoryCount} 个分类`,
    `已读 ${masteredCount.value} 篇`
  ]
  return parts.filter(Boolean).join(' · ')
})

const filteredDocuments = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  let result = [...normalizedDocuments.value]

  if (search) {
    result = result.filter((item) => {
      const targets = [
        item.displayName,
        item.preview,
        item.categoryLabel,
        item.filename,
        item.folder_path
      ]
      return targets.some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(search)
      )
    })
  }

  if (selectedCategory.value !== 'all') {
    result = result.filter((item) => item.categoryKey === selectedCategory.value)
  }

  if (activeStatus.value === 'readLater') {
    result = result.filter((item) => item.isReadLater)
  } else if (activeStatus.value === 'favorite') {
    result = result.filter((item) => item.isFavorite)
  } else if (activeStatus.value !== 'all') {
    result = result.filter((item) => item.status === activeStatus.value)
  }

  if (sortMode.value === 'category') {
    result.sort(
      (a, b) =>
        a.categoryLabel.localeCompare(b.categoryLabel, 'zh-Hans-CN') ||
        a.displayName.localeCompare(b.displayName, 'zh-Hans-CN')
    )
  }
  if (sortMode.value === 'updated_desc') {
    result.sort((a, b) => b.updatedTs - a.updatedTs)
  }
  if (sortMode.value === 'title_asc') {
    result.sort((a, b) => a.displayName.localeCompare(b.displayName, 'zh-Hans-CN'))
  }
  if (sortMode.value === 'read_desc') {
    result.sort((a, b) => b.readMinutes - a.readMinutes)
  }

  return result
})

const visibleDocuments = computed(() => filteredDocuments.value.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < filteredDocuments.value.length)

// 列表按分类分组展示（设计稿 2k2），分组内保持当前排序。
const visibleGroups = computed(() => {
  const groups = new Map()
  visibleDocuments.value.forEach((item) => {
    if (!groups.has(item.categoryKey)) {
      groups.set(item.categoryKey, { key: item.categoryKey, label: item.categoryLabel, items: [] })
    }
    groups.get(item.categoryKey).items.push(item)
  })

  return [...groups.values()].map((group) => {
    const all = normalizedDocuments.value.filter((item) => item.categoryKey === group.key)
    return {
      ...group,
      total: all.length,
      masteredCount: all.filter((item) => item.status === 'mastered').length
    }
  })
})

const loadLocalState = () => {
  if (!dbId.value) return
  favoriteIds.value = readFavoriteIds(dbId.value)
  readLaterIds.value = readReadLaterIds(dbId.value)
  masteryMap.value = readMasteryMap(dbId.value)
  visitCounts.value = readVisitCounts(dbId.value)
  lastLearnDoc.value = readLastDoc(dbId.value)
  readMinutesTotal.value = countReadMinutes(dbId.value)
}

const resetFilters = () => {
  keyword.value = ''
  selectedCategory.value = 'all'
  sortMode.value = 'category'
  activeStatus.value = 'all'
  visibleCount.value = PAGE_STEP
}

const loadDatabase = async () => {
  if (!dbId.value) {
    database.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    database.value = await learnApi.getDatabaseDetail(dbId.value)
    loadLocalState()
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

const markDocumentVisited = (document) => {
  const id = String(document.file_id || '')
  if (!id) return

  visitCounts.value = {
    ...visitCounts.value,
    [id]: Number(visitCounts.value[id] || 0) + 1
  }
  persistVisitCounts(dbId.value, visitCounts.value)

  lastLearnDoc.value = { file_id: id, title: document.displayName }
  persistLastDoc(dbId.value, lastLearnDoc.value)
  persistGlobalLastDoc({
    dbId: dbId.value,
    fileId: id,
    title: document.displayName,
    dbName: database.value?.name || ''
  })
}

const goToDocument = (fileId) => {
  const target = normalizedDocuments.value.find((item) => String(item.file_id) === String(fileId))
  if (target) {
    markDocumentVisited(target)
  }
  router.push(`/learn/${dbId.value}/doc/${fileId}`)
}

const continueLearning = () => {
  if (!lastLearnDoc.value?.file_id) return
  router.push(`/learn/${dbId.value}/doc/${lastLearnDoc.value.file_id}`)
}

const toggleFavorite = (fileId) => {
  const id = String(fileId)
  const next = new Set(favoriteIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  favoriteIds.value = next
  persistFavoriteIds(dbId.value, next)
}

const toggleReadLater = (fileId) => {
  const id = String(fileId)
  const next = new Set(readLaterIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  readLaterIds.value = next
  persistReadLaterIds(dbId.value, next)
}

const shareDocument = async (document) => {
  try {
    const link = `${window.location.origin}/learn/${dbId.value}/doc/${document.file_id}`
    await navigator.clipboard.writeText(link)
    message.success('学习链接已复制')
  } catch {
    message.warning('复制失败，请手动复制地址栏链接')
  }
}

const loadMore = () => {
  visibleCount.value = Math.min(filteredDocuments.value.length, visibleCount.value + PAGE_STEP)
}

// 列表滚动到底部时自动加载下一页
const handleAutoLoad = (event) => {
  const container = event.currentTarget
  if (!hasMore.value || loading.value) return
  if (container.scrollHeight - (container.scrollTop + container.clientHeight) <= 180) {
    loadMore()
  }
}

watch(
  () => route.params.db_id,
  () => {
    resetFilters()
    loadDatabase()
  },
  { immediate: true }
)

watch(
  () => [keyword.value, selectedCategory.value, sortMode.value, activeStatus.value],
  () => {
    visibleCount.value = PAGE_STEP
  }
)

onMounted(() => {
  // 从阅读页返回时同步最新的掌握状态与阅读时长
  loadLocalState()
})
</script>

<style scoped lang="less">
// 设计稿 [UI v3][2k2] 专题详情 · 二级
.learn-database {
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
  gap: 20px;
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.topbar-left {
  min-width: 0;
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
  flex-shrink: 0;

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

  :deep(.btn-primary.ant-btn) {
    display: inline-flex;
    align-items: center;
    max-width: 320px;
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

  :deep(.btn-primary.ant-btn > span) {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

// ===================== 主体两栏 =====================
.page-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
}

.lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}

// ===================== 分类导航 =====================
.side-nav {
  // 分类名很长时，网格项的 min-width: auto 会把这一栏撑宽
  min-width: 0;
  overflow: hidden;
  border-right: 1px solid var(--gray-100);
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 22px 0 0;
}

.side-nav__list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-bottom: 18px;
}

.side-nav__lab {
  padding: 0 22px 12px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: none;
  background: transparent;
  padding: 9px 22px;
  font-size: 14px;
  color: var(--gray-700);
  cursor: pointer;
  text-align: left;

  &:hover {
    color: var(--gray-1000);
  }

  &.on {
    background: var(--gray-100);
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.nav-item__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-item__count {
  font-size: 12px;
  color: var(--gray-500);
  flex-shrink: 0;
}

.side-nav__progress {
  border-top: 1px solid var(--gray-100);
  padding: 18px 22px 22px;
  flex-shrink: 0;
}

.progress-number {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 10px;
}

.progress-number__value {
  font-size: 32px;
  font-weight: 800;
  color: var(--gray-1000);
  line-height: 1;
}

.progress-number__unit {
  font-size: 14px;
  color: var(--gray-600);
}

.progress-hint {
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 10px;
  line-height: 1.6;
}

.bar {
  height: 6px;
  background: var(--gray-100);
  margin-top: 10px;

  &--thin {
    height: 6px;
    margin-top: 7px;
  }
}

.bar__fill {
  display: block;
  height: 100%;
  background: var(--main-color);

  &--done {
    background: var(--gray-400);
  }
}

// ===================== 文档面板 =====================
.doc-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

.doc-panel__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 22px 32px 0;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.doc-panel__spacer {
  flex: 1;
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

.doc-search {
  display: flex;
  align-items: center;
  gap: 6px;

  .search-icon {
    color: var(--gray-500);
    font-size: 14px;
  }

  .search-input {
    width: 150px;
    border: none;
    outline: none;
    background: transparent;
    font-size: 13px;
    color: var(--gray-1000);

    &::placeholder {
      color: var(--gray-500);
    }
  }
}

.flat-select {
  min-width: 132px;

  :deep(.ant-select-selector) {
    padding-right: 0 !important;
  }

  :deep(.ant-select-selection-item) {
    font-size: 13px;
    color: var(--gray-600);
  }
}

.doc-panel__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 0 32px 24px;
}

.doc-group {
  margin-top: 26px;
}

.doc-group__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.doc-group__title {
  font-size: 17px;
  font-weight: 800;
  color: var(--gray-1000);
}

.doc-group__meta {
  font-size: 13px;
  color: var(--gray-600);
}

.doc-group__list {
  border-top: 1px solid var(--gray-200);
  margin-top: 12px;
}

.doc-row {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  padding: 16px 0;
  border-bottom: 1px solid var(--gray-100);
  cursor: pointer;

  &:hover .doc-title {
    color: var(--main-color);
  }
}

.doc-row__main {
  flex: 1;
  min-width: 0;
}

.doc-row__title {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.doc-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-1000);
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

  &--mastered {
    background: var(--gray-100);
    color: var(--gray-1000);
  }

  &--progress,
  &--review {
    border-color: var(--main-color);
    color: var(--main-color);
  }

  &--fav {
    color: var(--gray-700);
  }
}

.doc-preview {
  margin: 7px 0 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--gray-600);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.doc-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 10px;
}

.doc-row__progress {
  flex: 0 0 180px;
  padding-top: 4px;
}

.doc-row__progress-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--gray-500);
}

.doc-row__progress-value {
  color: var(--gray-1000);
  font-weight: 700;

  &.muted {
    color: var(--gray-500);
    font-weight: 400;
  }
}

.doc-row__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--gray-500);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;

  &:hover {
    border-color: var(--gray-200);
    color: var(--gray-1000);
  }
}

.row-btn {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-700);
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    border-color: var(--gray-500);
    color: var(--gray-1000);
  }

  &--primary {
    background: var(--main-color);
    border-color: var(--main-color);
    color: #fff;

    &:hover {
      background: var(--main-700);
      border-color: var(--main-700);
      color: #fff;
    }
  }
}

.load-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 0 0;
  font-size: 13px;
  color: var(--gray-500);
}

// ===================== 状态 =====================
.state-panel,
.empty-panel {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--gray-600);

  p {
    margin: 0;
    font-size: 14px;
  }
}

@media (max-width: 1100px) {
  .page-body {
    grid-template-columns: 1fr;
  }

  .side-nav {
    display: none;
  }
}

@media (max-width: 900px) {
  .page-topbar {
    flex-direction: column;
    align-items: flex-start;
    padding: 18px;
  }

  .doc-panel__filters {
    padding: 18px 18px 0;
  }

  .doc-panel__body {
    padding: 0 18px 24px;
  }

  .doc-row {
    flex-direction: column;
  }

  .doc-row__progress {
    flex: 1 1 auto;
    width: 100%;
  }
}
</style>
