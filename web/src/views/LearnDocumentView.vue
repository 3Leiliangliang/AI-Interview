<template>
  <div class="learn-document">
    <!-- 左：专题目录 -->
    <aside class="doc-tree desktop-only">
      <div class="doc-tree__head">
        <div class="doc-tree__title">{{ database?.name || '知识库' }}</div>
        <div class="doc-tree__progress-head">
          <span>专题进度</span>
          <span class="strong">{{ learningProgress }}%</span>
        </div>
        <div class="bar">
          <span
            v-if="learningProgress > 0"
            class="bar__fill"
            :style="{ width: `${learningProgress}%` }"
          ></span>
        </div>
      </div>

      <div class="doc-tree__body">
        <section v-for="group in groupedDocuments" :key="group.key">
          <button type="button" class="tree-group" @click="toggleGroup(group.key)">
            <span>{{ group.label }}</span>
            <span class="tree-group__count"
              >{{ group.masteredCount }} / {{ group.items.length }}</span
            >
          </button>
          <template v-if="expandedGroups[group.key]">
            <button
              v-for="item in group.items"
              :key="item.file_id"
              type="button"
              :class="['tree-doc', { on: item.file_id === currentFileId }]"
              @click="goToDocument(item.file_id)"
            >
              <span class="tree-doc__title">{{ item.displayName }}</span>
              <span v-if="item.file_id === currentFileId" class="tree-doc__dot"></span>
              <span v-else-if="item.status === 'mastered'" class="tree-doc__tag">已读</span>
              <span v-else-if="item.status === 'review'" class="tree-doc__tag">复习</span>
            </button>
          </template>
        </section>
      </div>
    </aside>

    <!-- 右：正文 -->
    <div class="doc-main">
      <div class="page-topbar">
        <div class="topbar-left">
          <div class="breadcrumbs">
            <span>知识学习</span>
            <span>/</span>
            <span>{{ database?.name || '知识专题' }}</span>
            <span>/</span>
            <span>{{ currentCategory }}</span>
          </div>
          <h1 class="page-title">{{ currentDocTitle }}</h1>
          <p class="page-subtitle">{{ subtitleText }}</p>
        </div>
        <div class="topbar-actions">
          <a-button class="btn-secondary mobile-only" @click="treeDrawerOpen = true">目录</a-button>
          <a-button class="btn-secondary mobile-only" @click="sideDrawerOpen = true"
            >大纲与笔记</a-button
          >
          <a-button class="btn-secondary" @click="router.push(`/learn/${dbId}`)">返回专题</a-button>
          <a-button
            class="btn-secondary"
            :class="{ 'btn-secondary--on': currentMastery === 'review' }"
            @click="toggleReviewMark"
          >
            标记复习
          </a-button>
          <a-button type="primary" class="btn-primary" @click="setMastery('mastered')">
            {{ currentMastery === 'mastered' ? '已掌握' : '掌握了' }}
          </a-button>
        </div>
      </div>

      <div v-if="loading" class="state-panel">
        <a-spin size="large" />
        <p>正在加载学习内容...</p>
      </div>

      <a-result
        v-else-if="errorMessage"
        status="warning"
        title="学习内容加载失败"
        :sub-title="errorMessage"
      />

      <div v-else-if="documentPayload" class="doc-body">
        <!-- 阅读区 -->
        <div class="reading-col">
          <div class="reading-col__bar">
            <div class="mode-tabs">
              <button
                v-for="option in viewOptions"
                :key="option.value"
                type="button"
                :class="['opt', { on: viewMode === option.value }]"
                @click="viewMode = option.value"
              >
                {{ option.label }}
              </button>
            </div>
            <div class="reading-progress">
              <span class="reading-progress__label">阅读进度</span>
              <div class="bar bar--wide">
                <span
                  v-if="currentProgress > 0"
                  class="bar__fill"
                  :style="{ width: `${currentProgress}%` }"
                ></span>
              </div>
              <span class="reading-progress__value">{{ currentProgress }}%</span>
            </div>
          </div>

          <div ref="readingScrollRef" class="reading-col__content" @scroll="handleContentScroll">
            <section v-if="viewMode === 'chunks'" ref="chunksContainerRef" class="chunk-list">
              <article
                v-for="chunk in parsedChunks"
                :key="chunk.id || chunk.chunk_order_index"
                :data-chunk-index="chunk.chunk_order_index"
                :class="['chunk-card', { active: activeChunkIndex === chunk.chunk_order_index }]"
              >
                <div class="chunk-card__top">
                  <span class="lab">要点 #{{ chunk.chunk_order_index }}</span>
                  <span
                    v-if="activeChunkIndex === chunk.chunk_order_index"
                    class="badge badge--current"
                    >当前阅读</span
                  >
                </div>

                <template v-if="chunk.isQaStructured">
                  <div class="lab">问题</div>
                  <div class="qa-question">{{ chunk.question }}</div>
                  <div class="lab">回答与要点</div>
                  <MdPreview
                    :model-value="chunk.answer"
                    :theme="theme"
                    preview-theme="github"
                    class="markdown-preview"
                  />
                </template>

                <div v-else class="chunk-card__content">{{ chunk.preview }}</div>
              </article>
            </section>

            <section v-else ref="articleContainerRef" class="markdown-panel">
              <MdPreview
                :model-value="documentPayload.content || ''"
                :theme="theme"
                preview-theme="github"
                class="markdown-preview"
              />
            </section>
          </div>

          <div class="reading-col__footer">
            <div class="footer-actions">
              <button type="button" class="row-btn" @click="askQuestion('我对这节还有疑问：')">
                有疑问，去提问
              </button>
              <button type="button" class="row-btn" @click="toggleFavoriteCurrent">
                {{ isFavorite ? '取消收藏' : '收藏本篇' }}
              </button>
              <button type="button" class="row-btn" @click="shareCurrent">复制链接</button>
              <button type="button" class="row-btn" @click="printCurrent">打印</button>
            </div>
            <div class="footer-next">
              <span class="footer-next__hint">
                {{
                  nextDocument
                    ? `下一篇：${formatDisplayName(nextDocument.filename)}`
                    : '已到本专题最后一篇'
                }}
              </span>
              <button
                type="button"
                class="row-btn row-btn--primary"
                :disabled="!nextDocument"
                @click="nextDocument && goToDocument(nextDocument.file_id)"
              >
                下一篇
              </button>
            </div>
          </div>
        </div>

        <!-- 大纲 / 相关题 / 笔记 -->
        <aside class="side-col" :class="{ 'side-col--open': sideDrawerOpen }">
          <button type="button" class="side-col__close mobile-only" @click="sideDrawerOpen = false">
            收起
          </button>

          <div class="side-block">
            <div class="lab">本页大纲</div>
            <div v-if="outlineItems.length" class="outline-list">
              <button
                v-for="item in outlineItems"
                :key="item.id"
                type="button"
                :class="[
                  'outline-item',
                  `level-${item.level}`,
                  { on: item.id === activeOutlineId }
                ]"
                @click="handleOutlineClick(item)"
              >
                {{ item.text }}
              </button>
            </div>
            <p v-else class="side-empty">本篇没有可用的小标题</p>
          </div>

          <div v-if="relatedQaCards.length" class="side-block">
            <div class="side-block__head">
              <span class="lab">相关面试题</span>
              <span class="side-block__hint">{{ relatedQaCards.length }} 道</span>
            </div>
            <div class="qa-list">
              <button
                v-for="card in relatedQaCards"
                :key="card.id"
                type="button"
                class="qa-item"
                @click="openQaCard(card)"
              >
                <span class="qa-item__q">{{ card.question }}</span>
                <span class="qa-item__a">{{ card.answerPreview }}</span>
              </button>
            </div>
          </div>

          <div class="side-block side-block--notes">
            <div class="side-block__head">
              <span class="lab">我的笔记</span>
              <span class="side-block__hint">自动保存</span>
            </div>
            <textarea
              v-model="currentNote"
              class="notes-input"
              maxlength="3000"
              placeholder="记录你的理解、疑问或面试答题思路..."
            ></textarea>
          </div>
        </aside>
      </div>
    </div>

    <a-drawer v-model:open="treeDrawerOpen" title="知识目录" placement="left" width="320">
      <div class="drawer-tree">
        <section v-for="group in groupedDocuments" :key="group.key">
          <button type="button" class="tree-group" @click="toggleGroup(group.key)">
            <span>{{ group.label }}</span>
            <span class="tree-group__count"
              >{{ group.masteredCount }} / {{ group.items.length }}</span
            >
          </button>
          <template v-if="expandedGroups[group.key]">
            <button
              v-for="item in group.items"
              :key="item.file_id"
              type="button"
              :class="['tree-doc', { on: item.file_id === currentFileId }]"
              @click="handleTreeDrawerDocClick(item.file_id)"
            >
              <span class="tree-doc__title">{{ item.displayName }}</span>
            </button>
          </template>
        </section>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import { learnApi } from '@/apis/learn_api'
import { interviewCodeApi } from '@/apis/interview_code'
import { useThemeStore } from '@/stores/theme'
import {
  persistFavoriteIds,
  persistGlobalLastDoc,
  persistLastDoc,
  persistMasteryMap,
  persistNotesMap,
  persistSecondsMap,
  readFavoriteIds,
  readMasteryMap,
  readNotesMap,
  readSecondsMap
} from '@/utils/learn_progress'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const loading = ref(false)
const errorMessage = ref('')
const treeDrawerOpen = ref(false)
const sideDrawerOpen = ref(false)
const viewMode = ref('markdown')
const database = ref(null)
const documentPayload = ref(null)
const chunksContainerRef = ref(null)
const articleContainerRef = ref(null)
const readingScrollRef = ref(null)
const activeChunkIndex = ref(null)
const activeOutlineId = ref('')
const readingProgress = ref(0)
const expandedGroups = ref({})

const favoriteIds = ref(new Set())
const masteryMap = ref({})
const notesMap = ref({})
const readSeconds = ref({})
const liveReadSeconds = ref(0)
const sessionStartedAt = ref(0)

let readTimer = null

const formatDisplayName = (value) => String(value || '').replace(/\.md$/i, '')
const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const dbId = computed(() => String(route.params.db_id || '').trim())
const currentFileId = computed(() => String(route.params.file_id || '').trim())
const documents = computed(() =>
  Array.isArray(database.value?.documents) ? database.value.documents : []
)
const currentDocument = computed(
  () => documents.value.find((item) => item.file_id === currentFileId.value) || null
)
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))
const currentDocTitle = computed(() =>
  formatDisplayName(
    documentPayload.value?.file_name || currentDocument.value?.filename || '文档学习'
  )
)
const currentCategory = computed(() => {
  const folder = String(currentDocument.value?.folder_path || '').trim()
  if (!folder) return '根目录'
  return folder.split('/').filter(Boolean)[0] || '根目录'
})
const isFavorite = computed(() => favoriteIds.value.has(currentFileId.value))
const currentMastery = computed(() => masteryMap.value[currentFileId.value] || 'todo')

const readMinutes = computed(() => {
  const stored = Number(readSeconds.value[currentFileId.value] || 0)
  const totalSeconds = stored + liveReadSeconds.value
  if (!totalSeconds) return 0
  return Math.max(1, Math.round(totalSeconds / 60))
})

const parseFrontmatter = (raw) => {
  const trimmed = String(raw || '').trim()
  if (!trimmed.startsWith('---')) {
    return { fields: {}, body: trimmed }
  }

  const closingIndex = trimmed.indexOf('\n---', 3)
  if (closingIndex < 0) {
    return { fields: {}, body: trimmed }
  }

  const frontmatterText = trimmed.slice(3, closingIndex).trim()
  const body = trimmed.slice(closingIndex + 4).trim()
  const fields = {}

  frontmatterText.split('\n').forEach((line) => {
    const separatorIndex = line.indexOf(':')
    if (separatorIndex < 0) return
    const key = line.slice(0, separatorIndex).trim().toLowerCase()
    const value = line.slice(separatorIndex + 1).trim()
    if (key && value) {
      fields[key] = value
    }
  })

  return { fields, body }
}

const parseQaChunk = (content) => {
  const raw = String(content || '').trim()
  const preview = raw.replace(/\n+/g, ' ').trim()
  const { fields, body } = parseFrontmatter(raw)

  const questionMatch = raw.match(
    /(?:问题|question)\s*[:：]\s*([\s\S]*?)(?=(?:回答|answer)\s*[:：]|$)/i
  )
  const answerMatch = raw.match(/(?:回答|answer)\s*[:：]\s*([\s\S]*)$/i)

  const question = questionMatch?.[1]?.trim() || fields.title || fields.question || ''
  const answer = answerMatch?.[1]?.trim() || body || fields.description || ''

  return {
    question,
    answer,
    preview,
    isQaStructured: Boolean(question && answer)
  }
}

const parsedChunks = computed(() =>
  (documentPayload.value?.lines || []).map((chunk) => ({
    ...chunk,
    ...parseQaChunk(chunk.content)
  }))
)

const qaStructuredCount = computed(
  () => parsedChunks.value.filter((chunk) => chunk.isQaStructured).length
)
const hasQaStructured = computed(() => qaStructuredCount.value > 0)
const viewOptions = computed(() =>
  hasQaStructured.value
    ? [
        { label: 'QA 分块', value: 'chunks' },
        { label: '整篇阅读', value: 'markdown' }
      ]
    : [{ label: '整篇阅读', value: 'markdown' }]
)

const estimatedMinutes = computed(() => {
  const source = String(documentPayload.value?.content || '').trim()
  const fallback = parsedChunks.value.map((chunk) => chunk.preview).join('\n')
  const text = source || fallback
  const minutes = Math.round(text.length / 420)
  return clamp(minutes || 5, 5, 60)
})

const subtitleText = computed(() => {
  const parts = [`预计 ${estimatedMinutes.value} 分钟`, `已读 ${readMinutes.value} 分钟`]
  if (qaStructuredCount.value) {
    parts.push(`QA 分块 ${qaStructuredCount.value} 个`)
  }
  return parts.join(' · ')
})

const groupedDocuments = computed(() => {
  const groups = new Map()
  documents.value.forEach((item) => {
    const folder = String(item.folder_path || '').trim()
    const key = folder ? folder.split('/').filter(Boolean)[0] || 'root' : 'root'
    const label = key === 'root' ? '未分组' : key
    if (!groups.has(key)) {
      groups.set(key, { key, label, items: [] })
    }
    groups.get(key).items.push({
      ...item,
      displayName: formatDisplayName(item.filename),
      status: masteryMap.value[item.file_id] || 'todo'
    })
  })

  return [...groups.values()]
    .map((group) => ({
      ...group,
      masteredCount: group.items.filter((item) => item.status === 'mastered').length,
      items: group.items.sort((a, b) => a.displayName.localeCompare(b.displayName, 'zh-Hans-CN'))
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN'))
})

const masteredCount = computed(() => {
  const docIds = new Set(documents.value.map((item) => item.file_id))
  return Object.entries(masteryMap.value).filter(
    ([id, status]) => docIds.has(id) && status === 'mastered'
  ).length
})
const learningProgress = computed(() => {
  if (!documents.value.length) return 0
  return Math.round((masteredCount.value / documents.value.length) * 100)
})

const markdownOutline = ref([])

const outlineItems = computed(() => {
  if (viewMode.value === 'chunks') {
    return parsedChunks.value.map((chunk) => ({
      id: `chunk-${chunk.chunk_order_index}`,
      text: chunk.question || chunk.preview || `要点 ${chunk.chunk_order_index}`,
      level: 2,
      chunkIndex: chunk.chunk_order_index,
      type: 'chunk'
    }))
  }
  return markdownOutline.value.map((item) => ({ ...item, type: 'heading' }))
})

const relatedQaCards = computed(() =>
  parsedChunks.value
    .filter((chunk) => chunk.isQaStructured)
    .slice(0, 3)
    .map((chunk) => ({
      id: chunk.id || `qa-${chunk.chunk_order_index}`,
      question: chunk.question,
      chunkIndex: chunk.chunk_order_index,
      answerPreview: chunk.answer.length > 110 ? `${chunk.answer.slice(0, 110)}...` : chunk.answer
    }))
)

const currentProgress = computed(() => {
  if (viewMode.value === 'chunks') {
    const index = parsedChunks.value.findIndex(
      (chunk) => chunk.chunk_order_index === activeChunkIndex.value
    )
    if (index < 0 || !parsedChunks.value.length) return 0
    return Math.round(((index + 1) / parsedChunks.value.length) * 100)
  }
  return readingProgress.value
})

const nextDocument = computed(() => {
  const index = documents.value.findIndex((item) => item.file_id === currentFileId.value)
  if (index < 0 || index + 1 >= documents.value.length) return null
  return documents.value[index + 1]
})

const currentNote = computed({
  get: () => notesMap.value[currentFileId.value] || '',
  set: (value) => {
    notesMap.value = {
      ...notesMap.value,
      [currentFileId.value]: value
    }
    persistNotesMap(dbId.value, notesMap.value)
  }
})

const initLocalState = () => {
  if (!dbId.value) return
  favoriteIds.value = readFavoriteIds(dbId.value)
  masteryMap.value = readMasteryMap(dbId.value)
  notesMap.value = readNotesMap(dbId.value)
  readSeconds.value = readSecondsMap(dbId.value)
}

const startReadSession = () => {
  if (!currentFileId.value) return
  sessionStartedAt.value = Date.now()
  liveReadSeconds.value = 0
  if (readTimer) clearInterval(readTimer)
  readTimer = setInterval(() => {
    if (!sessionStartedAt.value) return
    liveReadSeconds.value = Math.floor((Date.now() - sessionStartedAt.value) / 1000)
  }, 5000)
}

const commitReadDuration = (fileId = currentFileId.value) => {
  if (!fileId || !sessionStartedAt.value) return
  const elapsed = Math.floor((Date.now() - sessionStartedAt.value) / 1000)
  if (elapsed > 2) {
    readSeconds.value = {
      ...readSeconds.value,
      [fileId]: Number(readSeconds.value[fileId] || 0) + elapsed
    }
    persistSecondsMap(dbId.value, readSeconds.value)
  }
  sessionStartedAt.value = Date.now()
  liveReadSeconds.value = 0
}

const stopReadSession = () => {
  if (readTimer) {
    clearInterval(readTimer)
    readTimer = null
  }
}

const collectMarkdownOutline = async () => {
  if (viewMode.value !== 'markdown') {
    markdownOutline.value = []
    return
  }
  await nextTick()
  const container = articleContainerRef.value
  if (!container) {
    markdownOutline.value = []
    return
  }

  const headings = Array.from(container.querySelectorAll('h2, h3'))
  markdownOutline.value = headings.map((heading, index) => {
    const id = heading.id || `learn-outline-${index}`
    heading.id = id
    return {
      id,
      text: (heading.textContent || `章节 ${index + 1}`).trim(),
      level: heading.tagName.toLowerCase() === 'h2' ? 2 : 3
    }
  })
  updateOutlineByScroll()
}

const scrollToHeading = async (id) => {
  if (!id) return
  if (viewMode.value !== 'markdown') {
    viewMode.value = 'markdown'
    await nextTick()
  }
  const target = document.getElementById(id)
  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const scrollToChunk = async (chunkIndex, { smooth = true } = {}) => {
  if (chunkIndex === null || chunkIndex === undefined) return
  if (viewMode.value !== 'chunks') {
    viewMode.value = 'chunks'
    await nextTick()
  }
  activeChunkIndex.value = chunkIndex
  await nextTick()
  const container = chunksContainerRef.value
  if (!container) return
  const target = container.querySelector(`[data-chunk-index="${chunkIndex}"]`)
  target?.scrollIntoView({
    behavior: smooth ? 'smooth' : 'auto',
    block: 'center'
  })
}

const updateReadingProgress = () => {
  if (viewMode.value !== 'markdown') return
  const scroller = readingScrollRef.value
  if (!scroller) return
  const scrollable = scroller.scrollHeight - scroller.clientHeight
  readingProgress.value =
    scrollable > 0 ? clamp(Math.round((scroller.scrollTop / scrollable) * 100), 0, 100) : 100
}

const updateOutlineByScroll = () => {
  if (viewMode.value !== 'markdown' || !markdownOutline.value.length) return
  const scroller = readingScrollRef.value
  if (!scroller) return
  const anchorY = scroller.getBoundingClientRect().top + 120
  let activeId = markdownOutline.value[0].id
  markdownOutline.value.forEach((item) => {
    const element = document.getElementById(item.id)
    if (!element) return
    if (element.getBoundingClientRect().top <= anchorY) {
      activeId = item.id
    }
  })
  activeOutlineId.value = activeId
}

const handleContentScroll = () => {
  updateReadingProgress()
  updateOutlineByScroll()
}

const loadPage = async () => {
  if (!dbId.value || !currentFileId.value) {
    database.value = null
    documentPayload.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const [databaseData, documentData] = await Promise.all([
      learnApi.getDatabaseDetail(dbId.value),
      interviewCodeApi.getLearningDocument(dbId.value, currentFileId.value)
    ])
    database.value = databaseData
    documentPayload.value = documentData
    initLocalState()
    viewMode.value = hasQaStructured.value ? 'chunks' : 'markdown'
    activeChunkIndex.value =
      parsedChunks.value[0]?.chunk_order_index ?? documentData?.target_chunk_index ?? null
    recordLastDoc()
    await collectMarkdownOutline()
    startReadSession()
    updateReadingProgress()
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

// 直接通过链接打开某篇文档时，也要更新「继续上次学习」的入口
const recordLastDoc = () => {
  const entry = { file_id: currentFileId.value, title: currentDocTitle.value }
  persistLastDoc(dbId.value, entry)
  persistGlobalLastDoc({
    dbId: dbId.value,
    fileId: currentFileId.value,
    title: currentDocTitle.value,
    dbName: database.value?.name || ''
  })
}

const toggleGroup = (groupKey) => {
  expandedGroups.value = {
    ...expandedGroups.value,
    [groupKey]: !expandedGroups.value[groupKey]
  }
}

const goToDocument = (fileId) => {
  if (!fileId || fileId === currentFileId.value) return
  commitReadDuration(currentFileId.value)
  router.push(`/learn/${dbId.value}/doc/${fileId}`)
}

const handleTreeDrawerDocClick = (fileId) => {
  treeDrawerOpen.value = false
  goToDocument(fileId)
}

const toggleFavoriteCurrent = () => {
  const id = currentFileId.value
  if (!id) return
  const next = new Set(favoriteIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  favoriteIds.value = next
  persistFavoriteIds(dbId.value, next)
}

const setMastery = (status) => {
  if (!currentFileId.value) return
  masteryMap.value = {
    ...masteryMap.value,
    [currentFileId.value]: status
  }
  persistMasteryMap(dbId.value, masteryMap.value)
  message.success(
    status === 'mastered' ? '已标记为掌握' : status === 'review' ? '已标记为复习' : '已取消标记'
  )
}

const toggleReviewMark = () => {
  setMastery(currentMastery.value === 'review' ? 'todo' : 'review')
}

const askQuestion = async (prefix = '') => {
  const prompt = `${prefix || ''}关于《${currentDocTitle.value}》我想进一步理解：`
  try {
    await navigator.clipboard.writeText(prompt)
    message.success('问题模板已复制，跳转到智能问答')
  } catch {
    message.info('已跳转到智能问答')
  }
  router.push('/agent')
}

const shareCurrent = async () => {
  try {
    const link = `${window.location.origin}/learn/${dbId.value}/doc/${currentFileId.value}`
    await navigator.clipboard.writeText(link)
    message.success('学习链接已复制')
  } catch {
    message.warning('复制失败，请手动复制地址栏链接')
  }
}

const printCurrent = () => {
  window.print()
}

const openQaCard = (card) => {
  scrollToChunk(card.chunkIndex)
}

const handleOutlineClick = async (item) => {
  if (item.type === 'chunk') {
    await scrollToChunk(item.chunkIndex)
    activeOutlineId.value = item.id
    return
  }
  await scrollToHeading(item.id)
}

watch(
  groupedDocuments,
  (groups) => {
    const next = { ...expandedGroups.value }
    groups.forEach((group) => {
      if (next[group.key] === undefined) {
        next[group.key] = true
      }
    })
    expandedGroups.value = next
  },
  { immediate: true }
)

watch(
  () => [route.params.db_id, route.params.file_id],
  (value, oldValue) => {
    const oldFileId = String(oldValue?.[1] || '').trim()
    if (oldFileId) {
      commitReadDuration(oldFileId)
    }
    loadPage()
  },
  { immediate: true }
)

watch(
  () => viewMode.value,
  async (value) => {
    if (value === 'chunks') {
      await nextTick()
      if (activeChunkIndex.value !== null && activeChunkIndex.value !== undefined) {
        scrollToChunk(activeChunkIndex.value, { smooth: false })
      }
      activeOutlineId.value = activeChunkIndex.value ? `chunk-${activeChunkIndex.value}` : ''
    } else {
      await collectMarkdownOutline()
      updateReadingProgress()
    }
  }
)

onMounted(() => {
  window.addEventListener('resize', collectMarkdownOutline, { passive: true })
})

onUnmounted(() => {
  commitReadDuration()
  stopReadSession()
  window.removeEventListener('resize', collectMarkdownOutline)
})
</script>

<style scoped lang="less">
// 设计稿 [UI v3][2k3] 文档阅读 · 三级
.learn-document {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}

.bar {
  height: 6px;
  background: var(--gray-100);
  margin-top: 7px;

  &--wide {
    width: 120px;
    margin-top: 0;
  }
}

.bar__fill {
  display: block;
  height: 100%;
  background: var(--main-color);
}

// ===================== 左侧目录 =====================
.doc-tree {
  flex: 0 0 240px;
  // 文档标题很长时，flex 项的 min-width: auto 会把这一栏撑宽，必须显式收窄
  width: 240px;
  min-width: 0;
  overflow: hidden;
  border-right: 1px solid var(--gray-100);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.doc-tree__head {
  padding: 14px 18px;
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.doc-tree__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-1000);
}

.doc-tree__progress-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 10px;

  .strong {
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.doc-tree__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 0;
}

.tree-group {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: none;
  background: transparent;
  padding: 9px 18px;
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-1000);
  cursor: pointer;
  text-align: left;
}

.tree-group__count {
  font-size: 11px;
  font-weight: 400;
  color: var(--gray-500);
  flex-shrink: 0;
}

.tree-doc {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: none;
  background: transparent;
  padding: 7px 18px 7px 30px;
  font-size: 13px;
  color: var(--gray-600);
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

.tree-doc__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-doc__dot {
  width: 6px;
  height: 6px;
  background: var(--main-color);
  flex-shrink: 0;
}

.tree-doc__tag {
  font-size: 11px;
  color: var(--gray-500);
  flex-shrink: 0;
}

// ===================== 顶栏 =====================
.doc-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

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

.breadcrumbs {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 7px;
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
}

.mobile-only {
  display: none;
}

// ===================== 正文两栏 =====================
.doc-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
}

.reading-col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  border-right: 1px solid var(--gray-100);
}

.reading-col__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 32px;
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.mode-tabs {
  display: flex;
  gap: 10px;
}

.opt {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  font-size: 12px;
  color: var(--gray-700);
  cursor: pointer;

  &.on {
    background: var(--gray-100);
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.reading-progress {
  display: flex;
  align-items: center;
  gap: 14px;
}

.reading-progress__label {
  font-size: 12px;
  color: var(--gray-500);
}

.reading-progress__value {
  font-size: 13px;
  font-weight: 800;
  color: var(--gray-1000);
}

.reading-col__content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 24px 32px;
}

.reading-col__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 16px 32px;
  border-top: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.footer-actions,
.footer-next {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.footer-next__hint {
  font-size: 13px;
  color: var(--gray-500);
}

.row-btn {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-700);
  cursor: pointer;
  white-space: nowrap;

  &:hover:not(:disabled) {
    border-color: var(--gray-500);
    color: var(--gray-1000);
  }

  &:disabled {
    color: var(--gray-500);
    cursor: not-allowed;
  }

  &--primary {
    background: var(--main-color);
    border-color: var(--main-color);
    color: #fff;

    &:hover:not(:disabled) {
      background: var(--main-700);
      border-color: var(--main-700);
      color: #fff;
    }

    &:disabled {
      background: var(--gray-100);
      border-color: var(--gray-200);
      color: var(--gray-500);
    }
  }
}

// ===================== QA 分块 =====================
.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chunk-card {
  border: 1px solid var(--gray-100);
  padding: 18px 22px;

  &.active {
    border-color: var(--gray-200);
  }
}

.chunk-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
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

  &--current {
    border-color: var(--main-color);
    color: var(--main-color);
  }
}

.qa-question {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.6;
  color: var(--gray-1000);
  margin: 8px 0 18px;
}

.chunk-card__content {
  font-size: 15px;
  line-height: 1.8;
  color: var(--gray-700);
}

.markdown-panel {
  max-width: 780px;
}

:deep(.markdown-preview) {
  background: transparent;
}

:deep(.markdown-preview h1) {
  margin-top: 0;
}

:deep(.markdown-preview h2) {
  margin-top: 1.8em;
  margin-bottom: 0.8em;
  padding-left: 10px;
  border-left: 2px solid var(--main-color);
}

:deep(.markdown-preview p),
:deep(.markdown-preview li) {
  line-height: 1.85;
  font-size: 15px;
}

:deep(.markdown-preview pre) {
  border: 1px solid var(--gray-200);
  border-radius: 0;
  padding: 12px !important;
}

:deep(.markdown-preview pre code) {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace !important;
  font-size: 13px;
  line-height: 1.7;
}

:deep(.markdown-preview blockquote) {
  border-left-color: var(--gray-200);
  border-radius: 0;
  padding: 10px 12px;
}

// ===================== 右侧栏 =====================
.side-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 0;
  overflow: auto;
  padding: 20px 22px;
}

.side-col__close {
  align-self: flex-end;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-700);
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  cursor: pointer;
}

.side-block {
  flex-shrink: 0;
}

.side-block--notes {
  flex: 1;
  min-height: 140px;
  display: flex;
  flex-direction: column;
}

.side-block__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.side-block__hint {
  font-size: 12px;
  color: var(--gray-500);
}

.side-empty {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--gray-500);
}

.outline-list {
  margin-top: 12px;
}

.outline-item {
  width: 100%;
  border: none;
  border-top: 1px solid var(--gray-100);
  background: transparent;
  text-align: left;
  padding: 9px 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-600);
  cursor: pointer;

  &:hover {
    color: var(--gray-1000);
  }

  &.on {
    color: var(--gray-1000);
    font-weight: 700;
  }

  &.level-3 {
    padding-left: 14px;
  }
}

.qa-list {
  margin-top: 12px;
}

.qa-item {
  width: 100%;
  border: none;
  border-top: 1px solid var(--gray-100);
  background: transparent;
  text-align: left;
  padding: 11px 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;

  &:hover .qa-item__q {
    color: var(--main-color);
  }
}

.qa-item__q {
  font-size: 13px;
  line-height: 1.65;
  color: var(--gray-1000);
}

.qa-item__a {
  font-size: 12px;
  color: var(--gray-500);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.notes-input {
  flex: 1;
  min-height: 90px;
  margin-top: 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-800);
  resize: none;
  outline: none;
  font-family: inherit;

  &:focus {
    border-color: var(--main-color);
  }
}

.drawer-tree {
  display: flex;
  flex-direction: column;
}

// ===================== 状态 =====================
.state-panel {
  flex: 1;
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

  .mobile-only {
    display: inline-flex;
  }

  .doc-body {
    grid-template-columns: 1fr;
  }

  .reading-col {
    border-right: none;
  }

  // 窄屏下右栏改为从右侧滑出的面板
  .side-col {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 30;
    width: min(340px, 86vw);
    background: var(--gray-0);
    border-left: 1px solid var(--gray-200);
    transform: translateX(100%);
    transition: transform 0.2s ease;
  }

  .side-col--open {
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .side-col {
    transition: none;
  }
}

@media (max-width: 900px) {
  .page-topbar {
    flex-direction: column;
    align-items: flex-start;
    padding: 18px;
  }

  .topbar-actions {
    flex-wrap: wrap;
  }

  .reading-col__bar,
  .reading-col__footer {
    padding: 12px 18px;
  }

  .reading-col__content {
    padding: 18px;
  }
}
</style>
