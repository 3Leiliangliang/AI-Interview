<template>
  <div class="learn-database">
    <div class="page-header">
      <a-button type="text" class="back-btn" @click="router.push('/learn')">返回知识专题</a-button>
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

    <template v-else-if="database">
      <section class="overview-card">
        <div class="overview-top">
          <div class="overview-main">
            <span class="hero-badge">{{ database.position || '知识专题' }}</span>
            <h1>{{ database.name }}</h1>
            <p>{{ database.description || '浏览该专题下的知识文档，进入后可按分块或全文阅读。' }}</p>
          </div>

          <div class="overview-action">
            <a-button type="primary" class="continue-btn" :disabled="!lastLearnDoc" @click="continueLearning">
              继续上次学习
            </a-button>
            <p v-if="lastLearnDoc" class="continue-hint">上次学习：{{ lastLearnDoc.title }}</p>
          </div>
        </div>

        <div class="stats-row">
          <div class="stat-card">
            <FileText :size="16" />
            <div>
              <strong>{{ totalDocuments }}</strong>
              <span>篇文档</span>
            </div>
          </div>
          <div class="stat-card">
            <Folders :size="16" />
            <div>
              <strong>{{ categoryOptions.length - 1 }}</strong>
              <span>个分类</span>
            </div>
          </div>
          <div class="stat-card">
            <Clock3 :size="16" />
            <div>
              <strong>{{ totalReadHours }}</strong>
              <span>总阅读时长</span>
            </div>
          </div>
        </div>

        <div class="learning-path">
          <div class="learning-path__head">
            <span>推荐学习路径：{{ recommendedPathText }}</span>
            <span>{{ learnedCount }}/{{ totalDocuments }} 已学习</span>
          </div>
          <div class="learning-path__track">
            <span class="learning-path__fill" :style="{ width: `${pathProgress}%` }"></span>
          </div>
        </div>

        <div class="toolbar-grid">
          <a-input
            v-model:value="keyword"
            allow-clear
            size="large"
            placeholder="搜索文档名称、摘要或分类"
          >
            <template #prefix><SearchOutlined /></template>
          </a-input>

          <a-select v-model:value="selectedCategory" size="large" :options="categorySelectOptions" />

          <a-select v-model:value="sortMode" size="large" :options="sortOptions" />

          <a-button :type="favoriteOnly ? 'primary' : 'default'" size="large" @click="favoriteOnly = !favoriteOnly">
            <template #icon>
              <StarOutlined />
            </template>
            我的收藏
          </a-button>
        </div>

        <div class="quick-filter-row">
          <button
            v-for="tag in quickTags"
            :key="tag.value"
            type="button"
            :class="['quick-tag', { active: activeQuickTag === tag.value }]"
            @click="activeQuickTag = tag.value"
          >
            {{ tag.label }}
          </button>
        </div>
      </section>

      <section class="content-shell">
        <aside class="category-sidebar desktop-only">
          <div class="side-title">分类导航</div>
          <button
            v-for="item in categoryOptions"
            :key="item.value"
            type="button"
            :class="['category-item', { active: selectedCategory === item.value }]"
            @click="selectedCategory = item.value"
          >
            <span>{{ item.label }}</span>
            <span>{{ item.count }}</span>
          </button>
        </aside>

        <div class="list-panel">
          <div class="list-meta">
            <span>共 {{ filteredDocuments.length }} 篇文档</span>
            <span>已加载 {{ visibleDocuments.length }}/{{ filteredDocuments.length }}</span>
          </div>

          <div v-if="visibleDocuments.length" class="document-list">
            <article
              v-for="document in visibleDocuments"
              :key="document.file_id"
              class="document-row"
              @click="goToDocument(document.file_id)"
            >
              <div class="doc-type-icon">
                <component :is="document.typeIcon" :size="18" />
              </div>

              <div class="doc-main">
                <div class="doc-title-row">
                  <h3>{{ document.displayName }}</h3>
                  <div class="doc-actions">
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
                    <button type="button" class="icon-btn" title="复制学习链接" @click.stop="shareDocument(document)">
                      <ShareAltOutlined />
                    </button>
                    <a-button type="link" @click.stop="goToDocument(document.file_id)">进入学习</a-button>
                  </div>
                </div>

                <p class="doc-preview">{{ document.preview }}</p>

                <div class="doc-meta">
                  <span class="meta-tag" :style="{ '--tag-color': document.categoryColor, '--tag-bg': document.categoryBg }">
                    {{ document.categoryLabel }}
                  </span>
                  <a-tooltip :title="document.fullTime">
                    <span>{{ document.relativeTime }}</span>
                  </a-tooltip>
                  <span>预计阅读 {{ document.readMinutes }} 分钟</span>
                  <span v-if="document.isReadLater">稍后读</span>
                </div>

                <div class="doc-progress">
                  <span class="doc-progress__fill" :style="{ width: `${document.progress}%` }"></span>
                </div>
              </div>
            </article>
          </div>

          <a-empty v-else>
            <template #description>
              <div class="empty-state">
                <p>未找到“{{ keyword }}”相关文档</p>
                <div class="empty-suggestions">
                  <button
                    v-for="item in emptySuggestions"
                    :key="item"
                    type="button"
                    class="suggest-btn"
                    @click="keyword = item"
                  >
                    {{ item }}
                  </button>
                </div>
              </div>
            </template>
          </a-empty>

          <div v-if="filteredDocuments.length" class="load-footer">
            <span>已加载 {{ visibleDocuments.length }}/{{ filteredDocuments.length }} 篇</span>
            <a-button v-if="hasMore" @click="loadMore">加载更多</a-button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ClockCircleOutlined, SearchOutlined, ShareAltOutlined, StarFilled, StarOutlined } from '@ant-design/icons-vue'
import { Clock3, FileCode2, FileText, Folders, Video } from 'lucide-vue-next'

import { learnApi } from '@/apis/learn_api'
import { formatDateTime, formatRelative } from '@/utils/time'

const PAGE_STEP = 40

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const errorMessage = ref('')
const keyword = ref('')
const selectedCategory = ref('all')
const sortMode = ref('updated_desc')
const favoriteOnly = ref(false)
const activeQuickTag = ref('all')
const visibleCount = ref(PAGE_STEP)
const database = ref(null)
const favoriteIds = ref(new Set())
const readLaterIds = ref(new Set())
const visitCounts = ref({})
const lastLearnDoc = ref(null)
const previousVisitAt = ref(0)

const quickTags = [
  { label: '全部文档', value: 'all' },
  { label: '本周热门', value: 'hot' },
  { label: '未读更新', value: 'updated' },
  { label: '面试高频', value: 'interview' }
]

const sortOptions = [
  { label: '最近更新', value: 'updated_desc' },
  { label: '最早更新', value: 'updated_asc' },
  { label: '名称 A-Z', value: 'title_asc' },
  { label: '阅读时长长优先', value: 'read_desc' }
]

const categoryPalette = [
  { color: '#3B82F6', bg: 'rgba(59, 130, 246, 0.14)' },
  { color: '#10B981', bg: 'rgba(16, 185, 129, 0.14)' },
  { color: '#8B5CF6', bg: 'rgba(139, 92, 246, 0.14)' },
  { color: '#EC4899', bg: 'rgba(236, 72, 153, 0.14)' },
  { color: '#F59E0B', bg: 'rgba(245, 158, 11, 0.14)' },
  { color: '#14B8A6', bg: 'rgba(20, 184, 166, 0.14)' },
  { color: '#64748B', bg: 'rgba(100, 116, 139, 0.14)' }
]

const dbId = computed(() => String(route.params.db_id || '').trim())
const totalDocuments = computed(() => normalizedDocuments.value.length)
const learnedCount = computed(() => normalizedDocuments.value.filter((item) => item.progress >= 100).length)
const pathProgress = computed(() =>
  totalDocuments.value ? Math.round((learnedCount.value / totalDocuments.value) * 100) : 0
)
const totalReadHours = computed(() => {
  const totalMinutes = normalizedDocuments.value.reduce((sum, item) => sum + item.readMinutes, 0)
  const hours = totalMinutes / 60
  if (hours >= 10) return `${Math.round(hours)} 小时`
  return `${hours.toFixed(1)} 小时`
})

const parseTimestamp = (value) => {
  const timestamp = Date.parse(String(value || ''))
  return Number.isFinite(timestamp) ? timestamp : 0
}

const formatDisplayName = (value) => String(value || '').replace(/\.md$/i, '')

const getStorageKey = (name) => `learn-db-${dbId.value}-${name}`

const readStoredJson = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

const persistSet = (key, sourceSet) => {
  localStorage.setItem(key, JSON.stringify([...sourceSet]))
}

const getDocumentTypeIcon = (filename) => {
  const lower = String(filename || '').toLowerCase()
  if (/\.(mp4|mov|avi|mkv|webm)$/.test(lower)) return Video
  if (/\.(java|py|go|js|ts|sql|sh|yaml|yml|json)$/.test(lower)) return FileCode2
  return FileText
}

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

const getCategoryColor = (key) => {
  let hash = 0
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  }
  return categoryPalette[hash % categoryPalette.length]
}

const normalizedDocuments = computed(() => {
  const documents = Array.isArray(database.value?.documents) ? database.value.documents : []
  return documents.map((item) => {
    const id = String(item.file_id || '')
    const displayName = formatDisplayName(item.filename)
    const summary = String(item.summary || '').trim()
    const previewBase = summary || '暂无摘要，点击进入学习。'
    const preview = previewBase.length > 88 ? `${previewBase.slice(0, 88)}...` : previewBase
    const categoryKey = getCategoryKey(item)
    const categoryLabel = categoryKey === 'root' ? '根目录' : categoryKey
    const colorToken = getCategoryColor(categoryKey)
    const readMinutes = estimateReadMinutes(displayName, summary)
    const progress = Math.min(100, Math.max(0, Number(visitCounts.value[id] || 0) * 25))
    const updatedTs = parseTimestamp(item.updated_at)

    return {
      ...item,
      displayName,
      preview,
      categoryKey,
      categoryLabel,
      categoryColor: colorToken.color,
      categoryBg: colorToken.bg,
      typeIcon: getDocumentTypeIcon(item.filename),
      readMinutes,
      progress,
      updatedTs,
      relativeTime: updatedTs ? formatRelative(item.updated_at) : '-',
      fullTime: updatedTs ? formatDateTime(item.updated_at, 'YYYY-MM-DD HH:mm:ss') : '-',
      isFavorite: favoriteIds.value.has(id),
      isReadLater: readLaterIds.value.has(id)
    }
  })
})

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

  return [{ value: 'all', label: '全部分类', count: normalizedDocuments.value.length }, ...entries]
})

const categorySelectOptions = computed(() =>
  categoryOptions.value.map((item) => ({
    value: item.value,
    label: `${item.label} (${item.count})`
  }))
)

const hotDocumentIdSet = computed(() => {
  const sortedByVisit = [...normalizedDocuments.value]
    .sort((a, b) => Number(visitCounts.value[b.file_id] || 0) - Number(visitCounts.value[a.file_id] || 0))
    .filter((item) => Number(visitCounts.value[item.file_id] || 0) > 0)
  const source = sortedByVisit.length ? sortedByVisit : [...normalizedDocuments.value].sort((a, b) => b.updatedTs - a.updatedTs)
  return new Set(source.slice(0, 10).map((item) => item.file_id))
})

const interviewKeywords = ['面试', 'interview', 'java', 'jvm', 'mysql', 'redis', '算法', '并发', 'network']

const filteredDocuments = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  let result = [...normalizedDocuments.value]

  if (search) {
    result = result.filter((item) => {
      const targets = [item.displayName, item.preview, item.categoryLabel, item.filename, item.folder_path]
      return targets.some((value) => String(value || '').toLowerCase().includes(search))
    })
  }

  if (selectedCategory.value !== 'all') {
    result = result.filter((item) => item.categoryKey === selectedCategory.value)
  }

  if (favoriteOnly.value) {
    result = result.filter((item) => item.isFavorite)
  }

  if (activeQuickTag.value === 'hot') {
    result = result.filter((item) => hotDocumentIdSet.value.has(item.file_id))
  }
  if (activeQuickTag.value === 'updated') {
    result = result.filter((item) => item.updatedTs && item.updatedTs > previousVisitAt.value && item.progress < 100)
  }
  if (activeQuickTag.value === 'interview') {
    result = result.filter((item) => {
      const text = `${item.displayName} ${item.preview}`.toLowerCase()
      return interviewKeywords.some((word) => text.includes(word))
    })
  }

  if (sortMode.value === 'updated_desc') {
    result.sort((a, b) => b.updatedTs - a.updatedTs)
  }
  if (sortMode.value === 'updated_asc') {
    result.sort((a, b) => a.updatedTs - b.updatedTs)
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

const recommendedPathText = computed(() => {
  const tags = categoryOptions.value.filter((item) => item.value !== 'all').slice(0, 4).map((item) => item.label)
  if (!tags.length) return 'Java基础 → 集合框架 → 多线程 → JVM'
  return tags.join(' → ')
})

const emptySuggestions = computed(() => {
  const value = keyword.value.trim()
  if (!value) return ['spring-boot', 'MySQL', 'JVM']
  const variants = [value, value.toLowerCase(), value.replace(/\s+/g, '-')]
  return [...new Set(variants)].slice(0, 3)
})

const initPreferences = () => {
  if (!dbId.value) return

  const favorite = readStoredJson(getStorageKey('favorites'), [])
  const readLater = readStoredJson(getStorageKey('read-later'), [])
  const visits = readStoredJson(getStorageKey('visits'), {})
  const lastDoc = readStoredJson(getStorageKey('last-doc'), null)
  const prevSeen = Number(localStorage.getItem(getStorageKey('last-open-at')) || 0)

  favoriteIds.value = new Set(Array.isArray(favorite) ? favorite.map(String) : [])
  readLaterIds.value = new Set(Array.isArray(readLater) ? readLater.map(String) : [])
  visitCounts.value = visits && typeof visits === 'object' ? visits : {}
  lastLearnDoc.value = lastDoc && typeof lastDoc === 'object' ? lastDoc : null
  previousVisitAt.value = Number.isFinite(prevSeen) ? prevSeen : 0

  localStorage.setItem(getStorageKey('last-open-at'), String(Date.now()))
}

const resetFilters = () => {
  keyword.value = ''
  selectedCategory.value = 'all'
  sortMode.value = 'updated_desc'
  favoriteOnly.value = false
  activeQuickTag.value = 'all'
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
    initPreferences()
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

const persistVisits = () => {
  if (!dbId.value) return
  localStorage.setItem(getStorageKey('visits'), JSON.stringify(visitCounts.value))
}

const markDocumentVisited = (document) => {
  const id = String(document.file_id || '')
  if (!id) return
  visitCounts.value = {
    ...visitCounts.value,
    [id]: Number(visitCounts.value[id] || 0) + 1
  }
  persistVisits()

  lastLearnDoc.value = {
    file_id: id,
    title: document.displayName
  }
  localStorage.setItem(getStorageKey('last-doc'), JSON.stringify(lastLearnDoc.value))
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
  persistSet(getStorageKey('favorites'), next)
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
  persistSet(getStorageKey('read-later'), next)
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

const handleAutoLoad = () => {
  if (!hasMore.value || loading.value) return
  const distanceToBottom = document.documentElement.scrollHeight - (window.scrollY + window.innerHeight)
  if (distanceToBottom <= 180) {
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
  () => [keyword.value, selectedCategory.value, sortMode.value, favoriteOnly.value, activeQuickTag.value],
  () => {
    visibleCount.value = PAGE_STEP
  }
)

onMounted(() => {
  window.addEventListener('scroll', handleAutoLoad, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleAutoLoad)
})
</script>

<style scoped lang="less">
.learn-database {
  min-height: 100%;
  padding: 24px 28px 32px;
  background:
    linear-gradient(180deg, var(--main-10) 0%, var(--gray-10) 180px, var(--gray-25) 100%);
}

.page-header {
  margin-bottom: 14px;
}

.back-btn {
  padding-left: 0;
  color: var(--gray-700);
}

.overview-card,
.list-panel,
.category-sidebar {
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 20px;
  box-shadow: 0 10px 26px var(--shadow-0);
}

.overview-card {
  padding: 22px 24px;
  margin-bottom: 16px;
}

.overview-top {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.overview-main {
  min-width: 0;

  h1 {
    margin: 12px 0 10px;
    font-size: 34px;
    color: var(--gray-2000);
    line-height: 1.2;
  }

  p {
    margin: 0;
    color: var(--gray-600);
    line-height: 1.7;
    font-size: 15px;
  }
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 12px;
  background: var(--main-50);
  color: var(--main-700);
  font-size: 13px;
  font-weight: 600;
}

.overview-action {
  min-width: 220px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.continue-btn {
  min-width: 140px;
}

.continue-hint {
  margin: 0;
  max-width: 220px;
  color: var(--gray-500);
  font-size: 12px;
  text-align: right;
  line-height: 1.6;
}

.stats-row {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  border-radius: 14px;
  border: 1px solid var(--gray-150);
  background: var(--gray-10);
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--gray-700);

  strong {
    display: block;
    font-size: 22px;
    color: var(--gray-2000);
    line-height: 1.2;
  }

  span {
    font-size: 12px;
    color: var(--gray-600);
  }
}

.learning-path {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--main-100);
  background: var(--main-10);
}

.learning-path__head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--main-800);
  font-size: 13px;
}

.learning-path__track {
  margin-top: 8px;
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.14);
  overflow: hidden;
}

.learning-path__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--main-500), var(--main-300));
}

.toolbar-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 190px 190px 140px;
  gap: 10px;
}

.quick-filter-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-tag {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--gray-600);
  background: var(--gray-0);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    color 0.2s ease,
    background-color 0.2s ease;

  &.active {
    border-color: var(--main-300);
    color: var(--main-700);
    background: var(--main-50);
  }
}

.content-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 14px;
}

.category-sidebar {
  padding: 14px;
  align-self: start;
  position: sticky;
  top: 20px;
}

.side-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-700);
  margin-bottom: 10px;
}

.category-item {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--gray-600);
  padding: 8px 10px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;

  + .category-item {
    margin-top: 4px;
  }

  &.active {
    border-color: var(--main-200);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.list-panel {
  padding: 14px;
}

.list-meta {
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--gray-600);
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.document-row {
  border: 1px solid var(--gray-150);
  border-radius: 14px;
  background: var(--gray-0);
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background-color 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    box-shadow: 0 10px 20px var(--shadow-0);
    background: #fcfdff;
  }
}

.doc-type-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--gray-10);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-700);
  flex: 0 0 auto;
}

.doc-main {
  min-width: 0;
  width: 100%;
}

.doc-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;

  h3 {
    margin: 0;
    color: var(--gray-2000);
    font-size: 18px;
    line-height: 1.3;
  }
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--gray-500);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    color 0.2s ease,
    border-color 0.2s ease,
    background-color 0.2s ease;

  &:hover {
    color: var(--main-700);
    border-color: var(--main-200);
    background: var(--main-50);
  }
}

.doc-preview {
  margin: 6px 0 0;
  color: var(--gray-600);
  font-size: 13px;
  line-height: 1.7;
}

.doc-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--gray-500);
}

.meta-tag {
  border-radius: 999px;
  padding: 2px 10px;
  color: var(--tag-color);
  background: var(--tag-bg);
}

.doc-progress {
  margin-top: 10px;
  width: 100%;
  height: 4px;
  border-radius: 999px;
  background: var(--gray-50);
  overflow: hidden;
}

.doc-progress__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--main-500), var(--main-300));
}

.load-footer {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  color: var(--gray-500);
  font-size: 13px;
}

.empty-state {
  color: var(--gray-600);

  p {
    margin: 0 0 8px;
  }
}

.empty-suggestions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.suggest-btn {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--gray-10);
  color: var(--gray-700);
  padding: 4px 10px;
  cursor: pointer;
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

@media (max-width: 1280px) {
  .desktop-only {
    display: none;
  }

  .content-shell {
    grid-template-columns: 1fr;
  }

  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .learn-database {
    padding: 18px;
  }

  .overview-top,
  .stats-row,
  .toolbar-grid {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .overview-action {
    align-items: flex-start;
  }

  .continue-hint {
    text-align: left;
  }

  .stats-row {
    display: grid;
  }

  .doc-title-row {
    flex-direction: column;
  }

  .doc-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
