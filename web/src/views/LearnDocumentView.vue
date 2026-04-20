<template>
  <div class="learn-document-page">
    <div class="page-shell">
      <aside class="tree-sidebar desktop-only">
        <div class="tree-header">
          <div class="tree-header__title">
            <BookOutlined />
            <span>{{ database?.name || '知识库' }}</span>
          </div>
          <div class="tree-progress">
            <div class="tree-progress__meta">
              <span>学习进度</span>
              <span>{{ learningProgress }}%</span>
            </div>
            <div class="tree-progress__track">
              <span class="tree-progress__fill" :style="{ width: `${learningProgress}%` }"></span>
            </div>
          </div>
        </div>

        <div class="tree-groups">
          <section v-for="group in groupedDocuments" :key="group.key" class="tree-group">
            <button type="button" class="tree-group__head" @click="toggleGroup(group.key)">
              <span class="tree-group__left">
                <component :is="expandedGroups[group.key] ? FolderOpen : Folder" :size="14" />
                <span>{{ group.label }}</span>
              </span>
              <span>{{ group.items.length }}</span>
            </button>

            <div v-if="expandedGroups[group.key]" class="tree-group__body">
              <button
                v-for="item in group.items"
                :key="item.file_id"
                type="button"
                :class="['tree-doc', `status-${item.status}`, { active: item.file_id === currentFileId }]"
                @click="goToDocument(item.file_id)"
              >
                <span class="tree-doc__status">
                  <AimOutlined v-if="item.status === 'current'" />
                  <CheckCircleFilled v-else-if="item.status === 'mastered'" />
                  <ExclamationCircleOutlined v-else-if="item.status === 'review'" />
                  <MinusCircleOutlined v-else />
                </span>
                <span class="tree-doc__title">{{ item.displayName }}</span>
              </button>
            </div>
          </section>
        </div>
      </aside>

      <main class="content-panel">
        <div class="content-header">
          <div class="content-header__left">
            <a-button type="text" class="back-btn" @click="router.push(`/learn/${dbId}`)">返回专题</a-button>
            <a-button type="text" class="mobile-btn" @click="treeDrawerOpen = true">目录</a-button>
            <a-button type="text" class="mobile-btn" @click="outlineDrawerOpen = true">大纲</a-button>
            <div class="breadcrumbs">
              <span>{{ database?.name || '知识专题' }}</span>
              <span>/</span>
              <span>{{ currentCategory }}</span>
              <span>/</span>
              <span>{{ currentDocTitle }}</span>
            </div>
          </div>

          <a-segmented v-if="viewOptions.length > 1" v-model:value="viewMode" :options="viewOptions" />
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

        <template v-else-if="documentPayload">
          <section class="hero-card">
            <div class="hero-card__topline">
              <span class="hero-badge">{{ database?.position || '知识学习' }}</span>
              <span class="hero-estimate">预计 {{ estimatedMinutes }} 分钟</span>
              <span class="hero-estimate">已读 {{ readMinutes }} 分钟</span>
            </div>

            <h1>{{ currentDocTitle }}</h1>
            <p>{{ currentDocument?.summary || '掌握核心要点，支持正文阅读与导读卡片模式切换。' }}</p>

            <div class="hero-tags">
              <span v-for="tag in topicTags" :key="tag" class="hero-tag">{{ tag }}</span>
            </div>

            <div class="hero-actions">
              <a-button :type="isFavorite ? 'primary' : 'default'" size="small" @click="toggleFavoriteCurrent">
                <template #icon>
                  <StarFilled v-if="isFavorite" />
                  <StarOutlined v-else />
                </template>
                收藏
              </a-button>
              <a-button size="small" @click="notesDrawerOpen = true">
                <template #icon><EditOutlined /></template>
                记笔记
              </a-button>
              <a-button size="small" @click="askQuestion()">
                <template #icon><QuestionCircleOutlined /></template>
                提问
              </a-button>
              <a-button size="small" @click="shareCurrent">
                <template #icon><ShareAltOutlined /></template>
                分享
              </a-button>
              <a-button size="small" @click="printCurrent">
                <template #icon><PrinterOutlined /></template>
                打印
              </a-button>
            </div>

            <div class="hero-reading-progress">
              <span class="hero-reading-progress__label">阅读进度</span>
              <span class="hero-reading-progress__value">{{ currentProgress }}%</span>
            </div>
            <div class="hero-reading-progress__track">
              <span class="hero-reading-progress__fill" :style="{ width: `${currentProgress}%` }"></span>
            </div>
          </section>

          <section class="reading-shell">
            <div class="reading-main">
              <section v-if="viewMode === 'chunks'" ref="chunksContainerRef" class="chunk-list">
                <article
                  v-for="chunk in parsedChunks"
                  :key="chunk.id || chunk.chunk_order_index"
                  :data-chunk-index="chunk.chunk_order_index"
                  :class="['chunk-card', { active: activeChunkIndex === chunk.chunk_order_index }]"
                >
                  <div class="chunk-card__top">
                    <span class="chunk-index">优化要点 #{{ chunk.chunk_order_index }}</span>
                    <a-tag v-if="activeChunkIndex === chunk.chunk_order_index" color="processing">当前阅读</a-tag>
                  </div>

                  <template v-if="chunk.isQaStructured">
                    <div class="qa-section">
                      <span class="qa-label">问题</span>
                      <div class="qa-content">{{ chunk.question }}</div>
                    </div>
                    <div v-if="chunk.answer" class="qa-section answer">
                      <span class="qa-label">回答与要点</span>
                      <MdPreview
                        :model-value="chunk.answer"
                        :theme="theme"
                        preview-theme="github"
                        class="markdown-preview"
                      />
                    </div>
                  </template>

                  <div v-else class="chunk-card__content">{{ chunk.preview }}</div>
                </article>
              </section>

              <section v-else ref="articleContainerRef" class="markdown-panel">
                <div class="reading-article">
                  <MdPreview
                    :model-value="documentPayload.content || ''"
                    :theme="theme"
                    preview-theme="github"
                    class="markdown-preview"
                  />
                </div>
              </section>

              <section v-if="relatedQaCards.length" class="qa-panel">
                <div class="qa-panel__head">
                  <span>相关面试题（{{ relatedQaCards.length }}）</span>
                </div>
                <div class="qa-panel__list">
                  <article v-for="card in relatedQaCards" :key="card.id" class="qa-panel__item">
                    <h4>{{ card.question }}</h4>
                    <p>{{ card.answerPreview }}</p>
                    <a-button type="link" @click="openQaCard(card)">查看完整答案</a-button>
                  </article>
                </div>
              </section>

              <section class="study-footer">
                <div class="study-footer__top">
                  <span>已读完本节？</span>
                  <div class="study-footer__actions">
                    <a-button size="small" type="primary" @click="setMastery('mastered')">掌握了</a-button>
                    <a-button size="small" @click="setMastery('review')">标记复习</a-button>
                    <a-button size="small" @click="askQuestion('我对这节还有疑问：')">有疑问，去提问</a-button>
                  </div>
                </div>
                <div class="study-footer__next">
                  <span v-if="nextDocument">下一节：{{ formatDisplayName(nextDocument.filename) }}</span>
                  <span v-else>已到本专题最后一篇</span>
                  <a-button v-if="nextDocument" type="primary" @click="goToDocument(nextDocument.file_id)">
                    继续学习
                  </a-button>
                </div>
              </section>
            </div>

            <aside class="tool-rail desktop-only">
              <a-tooltip title="文档大纲" placement="left">
                <button type="button" class="tool-btn" @click="outlineDrawerOpen = true">
                  <MenuOutlined />
                </button>
              </a-tooltip>
              <a-tooltip title="我的笔记" placement="left">
                <button type="button" class="tool-btn" @click="notesDrawerOpen = true">
                  <EditOutlined />
                </button>
              </a-tooltip>
              <a-tooltip title="相关问答" placement="left">
                <button type="button" class="tool-btn" @click="focusQaPanel">
                  <QuestionCircleOutlined />
                </button>
              </a-tooltip>
              <a-tooltip title="重点标记" placement="left">
                <button type="button" class="tool-btn" @click="toggleReviewMark">
                  <PushpinOutlined />
                </button>
              </a-tooltip>
              <a-tooltip title="回到顶部" placement="left">
                <button type="button" class="tool-btn" @click="scrollToTop">
                  <VerticalAlignTopOutlined />
                </button>
              </a-tooltip>
            </aside>
          </section>
        </template>
      </main>
    </div>

    <a-drawer v-model:open="treeDrawerOpen" title="知识目录" placement="left" width="320">
      <div class="drawer-tree">
        <section v-for="group in groupedDocuments" :key="group.key" class="tree-group">
          <button type="button" class="tree-group__head" @click="toggleGroup(group.key)">
            <span class="tree-group__left">
              <component :is="expandedGroups[group.key] ? FolderOpen : Folder" :size="14" />
              <span>{{ group.label }}</span>
            </span>
            <span>{{ group.items.length }}</span>
          </button>

          <div v-if="expandedGroups[group.key]" class="tree-group__body">
            <button
              v-for="item in group.items"
              :key="item.file_id"
              type="button"
              :class="['tree-doc', { active: item.file_id === currentFileId }]"
              @click="handleTreeDrawerDocClick(item.file_id)"
            >
              <span class="tree-doc__title">{{ item.displayName }}</span>
            </button>
          </div>
        </section>
      </div>
    </a-drawer>

    <a-drawer v-model:open="outlineDrawerOpen" title="文档大纲" placement="right" width="320">
      <div class="outline-drawer">
        <button
          v-for="item in outlineItems"
          :key="item.id"
          type="button"
          :class="['outline-item', { active: item.id === activeOutlineId }]"
          @click="handleOutlineClick(item)"
        >
          <span :class="['outline-item__text', `level-${item.level}`]">{{ item.text }}</span>
        </button>
      </div>
    </a-drawer>

    <a-drawer v-model:open="notesDrawerOpen" title="我的笔记" placement="right" width="420">
      <div class="notes-drawer">
        <a-textarea
          v-model:value="currentNote"
          :rows="14"
          show-count
          :maxlength="3000"
          placeholder="记录你的理解、疑问或面试答题思路..."
        />
        <p class="notes-hint">笔记会自动保存到本地。</p>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  AimOutlined,
  BookOutlined,
  CheckCircleFilled,
  EditOutlined,
  ExclamationCircleOutlined,
  MenuOutlined,
  MinusCircleOutlined,
  PrinterOutlined,
  PushpinOutlined,
  QuestionCircleOutlined,
  ShareAltOutlined,
  StarFilled,
  StarOutlined,
  VerticalAlignTopOutlined
} from '@ant-design/icons-vue'
import { FileCode2, FileText, Folder, FolderOpen } from 'lucide-vue-next'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import { learnApi } from '@/apis/learn_api'
import { interviewCodeApi } from '@/apis/interview_code'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const loading = ref(false)
const errorMessage = ref('')
const treeDrawerOpen = ref(false)
const outlineDrawerOpen = ref(false)
const notesDrawerOpen = ref(false)
const viewMode = ref('markdown')
const database = ref(null)
const documentPayload = ref(null)
const chunksContainerRef = ref(null)
const articleContainerRef = ref(null)
const activeChunkIndex = ref(null)
const activeHeadingId = ref('')
const activeOutlineId = ref('')
const readingProgress = ref(0)
const expandedGroups = ref({})
const scrollContainer = ref(null)

const favoriteIds = ref(new Set())
const masteryMap = ref({})
const notesMap = ref({})
const readSecondsMap = ref({})
const liveReadSeconds = ref(0)
const sessionStartedAt = ref(0)

let readTimer = null

const formatDisplayName = (value) => String(value || '').replace(/\.md$/i, '')
const clamp = (value, min, max) => Math.min(max, Math.max(min, value))
const getScrollContainer = () => scrollContainer.value || document.getElementById('app-router-view')

const dbId = computed(() => String(route.params.db_id || '').trim())
const currentFileId = computed(() => String(route.params.file_id || '').trim())
const documents = computed(() => (Array.isArray(database.value?.documents) ? database.value.documents : []))
const currentDocument = computed(() => documents.value.find((item) => item.file_id === currentFileId.value) || null)
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))
const currentDocTitle = computed(() =>
  formatDisplayName(documentPayload.value?.file_name || currentDocument.value?.filename || '文档学习')
)
const currentCategory = computed(() => {
  const folder = String(currentDocument.value?.folder_path || '').trim()
  if (!folder) return '根目录'
  return folder.split('/').filter(Boolean)[0] || '根目录'
})
const currentTagsText = computed(
  () => `${currentDocTitle.value} ${currentDocument.value?.summary || ''} ${currentDocument.value?.filename || ''}`
)
const isFavorite = computed(() => favoriteIds.value.has(currentFileId.value))
const readMinutes = computed(() => {
  const stored = Number(readSecondsMap.value[currentFileId.value] || 0)
  const totalSeconds = stored + liveReadSeconds.value
  if (!totalSeconds) return 0
  return Math.max(1, Math.round(totalSeconds / 60))
})
const estimatedMinutes = computed(() => {
  const source = String(documentPayload.value?.content || '').trim()
  const fallback = parsedChunks.value.map((chunk) => chunk.preview).join('\n')
  const text = source || fallback
  const minutes = Math.round(text.length / 420)
  return clamp(minutes || 5, 5, 60)
})

const topicTags = computed(() => {
  const text = currentTagsText.value.toLowerCase()
  const tags = [currentCategory.value]
  if (text.includes('sql') || text.includes('mysql')) tags.push('MySQL')
  if (text.includes('优化') || text.includes('performance')) tags.push('性能优化')
  if (text.includes('索引') || text.includes('index')) tags.push('索引')
  return [...new Set(tags)].slice(0, 4)
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

  const questionMatch = raw.match(/(?:问题|question)\s*[:：]\s*([\s\S]*?)(?=(?:回答|answer)\s*[:：]|$)/i)
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

const qaStructuredCount = computed(() => parsedChunks.value.filter((chunk) => chunk.isQaStructured).length)
const hasQaStructured = computed(() => qaStructuredCount.value > 0)
const viewOptions = computed(() =>
  hasQaStructured.value
    ? [
        { label: '阅读正文', value: 'markdown' },
        { label: '导读卡片', value: 'chunks' }
      ]
    : [{ label: '阅读正文', value: 'markdown' }]
)

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
      status:
        item.file_id === currentFileId.value
          ? 'current'
          : masteryMap.value[item.file_id] === 'mastered'
            ? 'mastered'
            : masteryMap.value[item.file_id] === 'review'
              ? 'review'
              : 'todo'
    })
  })

  return [...groups.values()]
    .map((group) => ({
      ...group,
      items: group.items.sort((a, b) => a.displayName.localeCompare(b.displayName, 'zh-Hans-CN'))
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN'))
})

const masteredCount = computed(() => {
  const docIds = new Set(documents.value.map((item) => item.file_id))
  return Object.entries(masteryMap.value).filter(([id, status]) => docIds.has(id) && status === 'mastered').length
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
      text: chunk.question || chunk.preview || `导读卡片 ${chunk.chunk_order_index}`,
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
    const index = parsedChunks.value.findIndex((chunk) => chunk.chunk_order_index === activeChunkIndex.value)
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
    persistJson(storageKey('notes'), notesMap.value)
  }
})

const storageKey = (name) => `learn-doc-${dbId.value}-${name}`

const readJson = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

const persistJson = (key, value) => {
  localStorage.setItem(key, JSON.stringify(value))
}

const initLocalState = () => {
  if (!dbId.value) return
  favoriteIds.value = new Set(readJson(storageKey('favorites'), []))
  masteryMap.value = readJson(storageKey('mastery'), {})
  notesMap.value = readJson(storageKey('notes'), {})
  readSecondsMap.value = readJson(storageKey('read-seconds'), {})
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
    readSecondsMap.value = {
      ...readSecondsMap.value,
      [fileId]: Number(readSecondsMap.value[fileId] || 0) + elapsed
    }
    persistJson(storageKey('read-seconds'), readSecondsMap.value)
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
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
  const container = articleContainerRef.value
  if (!container) return
  const scroller = getScrollContainer()
  if (!scroller) return

  const rect = container.getBoundingClientRect()
  const scrollerRect = scroller.getBoundingClientRect()
  const viewportHeight = scrollerRect.height || window.innerHeight
  const total = container.offsetHeight + viewportHeight * 0.5
  const seen = scrollerRect.bottom - rect.top
  readingProgress.value = clamp(Math.round((seen / total) * 100), 0, 100)
}

const updateOutlineByScroll = () => {
  if (viewMode.value !== 'markdown' || !markdownOutline.value.length) return
  const scroller = getScrollContainer()
  if (!scroller) return
  const scrollerRect = scroller.getBoundingClientRect()
  const currentY = scrollerRect.top + 120
  let activeId = markdownOutline.value[0].id
  markdownOutline.value.forEach((item) => {
    const element = document.getElementById(item.id)
    if (!element) return
    const elementTop = element.getBoundingClientRect().top
    if (elementTop <= currentY) {
      activeId = item.id
    }
  })
  activeHeadingId.value = activeId
  activeOutlineId.value = activeId
}

const handleWindowScroll = () => {
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
  viewMode.value = 'markdown'

  try {
    const [databaseData, documentData] = await Promise.all([
      learnApi.getDatabaseDetail(dbId.value),
      interviewCodeApi.getLearningDocument(dbId.value, currentFileId.value)
    ])
    database.value = databaseData
    documentPayload.value = documentData
    initLocalState()
    activeChunkIndex.value = parsedChunks.value[0]?.chunk_order_index ?? documentData?.target_chunk_index ?? null
    await collectMarkdownOutline()
    startReadSession()
    updateReadingProgress()
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
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
  persistJson(storageKey('favorites'), [...next])
}

const setMastery = (status) => {
  if (!currentFileId.value) return
  masteryMap.value = {
    ...masteryMap.value,
    [currentFileId.value]: status
  }
  persistJson(storageKey('mastery'), masteryMap.value)
  message.success(status === 'mastered' ? '已标记为掌握' : '已标记为复习')
}

const toggleReviewMark = () => {
  const current = masteryMap.value[currentFileId.value]
  setMastery(current === 'review' ? 'todo' : 'review')
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

const focusQaPanel = () => {
  const panel = document.querySelector('.qa-panel')
  panel?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const scrollToTop = () => {
  const scroller = getScrollContainer()
  if (scroller && 'scrollTo' in scroller) {
    scroller.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const handleOutlineClick = async (item) => {
  outlineDrawerOpen.value = false
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
  scrollContainer.value = document.getElementById('app-router-view')
  const scroller = getScrollContainer()
  scroller?.addEventListener('scroll', handleWindowScroll, { passive: true })
  window.addEventListener('resize', collectMarkdownOutline, { passive: true })
})

onUnmounted(() => {
  commitReadDuration()
  stopReadSession()
  const scroller = getScrollContainer()
  scroller?.removeEventListener('scroll', handleWindowScroll)
  window.removeEventListener('resize', collectMarkdownOutline)
})
</script>

<style scoped lang="less">
.learn-document-page {
  min-height: 100%;
  background: var(--gray-25);
}

.page-shell {
  display: flex;
  min-height: 100%;
}

.tree-sidebar {
  width: 320px;
  border-right: 1px solid var(--gray-150);
  background: var(--gray-0);
  padding: 16px 14px;
  overflow-y: auto;
}

.tree-header {
  border-radius: 14px;
  border: 1px solid var(--gray-150);
  background: var(--gray-10);
  padding: 12px;
}

.tree-header__title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-800);
  font-size: 14px;
  font-weight: 700;
}

.tree-progress {
  margin-top: 10px;
}

.tree-progress__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--gray-500);
}

.tree-progress__track {
  margin-top: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--gray-100);
  overflow: hidden;
}

.tree-progress__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--main-500), var(--main-300));
}

.tree-groups {
  margin-top: 14px;
}

.tree-group + .tree-group {
  margin-top: 10px;
}

.tree-group__head {
  width: 100%;
  border: 0;
  background: transparent;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--gray-600);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 2px;
}

.tree-group__left {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
}

.tree-group__body {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tree-doc {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--gray-700);
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
  padding: 8px 10px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;

  &:hover {
    border-color: var(--gray-200);
    background: var(--gray-10);
  }

  &.active {
    border-color: var(--main-200);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.tree-doc__status {
  width: 14px;
  display: inline-flex;
  justify-content: center;
}

.status-current .tree-doc__status {
  color: var(--main-600);
}

.status-mastered .tree-doc__status {
  color: #16a34a;
}

.status-review .tree-doc__status {
  color: #d97706;
}

.status-todo .tree-doc__status {
  color: var(--gray-300);
}

.tree-doc__title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.content-panel {
  flex: 1;
  min-width: 0;
  padding: 18px 22px 32px;
}

.content-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
  margin-bottom: 14px;
}

.content-header__left {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.back-btn,
.mobile-btn {
  color: var(--gray-700);
}

.mobile-btn {
  display: none;
}

.breadcrumbs {
  min-width: 0;
  color: var(--gray-500);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;

  span:last-child {
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.hero-card {
  border: 1px solid var(--gray-150);
  border-radius: 20px;
  background: var(--gray-0);
  box-shadow: 0 10px 24px var(--shadow-0);
  padding: 20px 22px;
}

.hero-card__topline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  background: var(--main-50);
  color: var(--main-700);
  font-size: 12px;
  font-weight: 600;
}

.hero-estimate {
  font-size: 12px;
  color: var(--gray-500);
}

.hero-card h1 {
  margin: 12px 0 8px;
  font-size: 30px;
  color: var(--gray-2000);
  line-height: 1.2;
}

.hero-card p {
  margin: 0;
  color: var(--gray-600);
  line-height: 1.8;
}

.hero-tags {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-tag {
  border-radius: 999px;
  border: 1px solid var(--gray-200);
  background: var(--gray-10);
  color: var(--gray-700);
  padding: 2px 10px;
  font-size: 12px;
}

.hero-actions {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-reading-progress {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--gray-500);
}

.hero-reading-progress__track {
  margin-top: 6px;
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: var(--gray-50);
  overflow: hidden;
}

.hero-reading-progress__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--main-500), var(--main-300));
}

.reading-shell {
  margin-top: 14px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 46px;
  gap: 14px;
}

.reading-main {
  min-width: 0;
}

.markdown-panel {
  border: 1px solid var(--gray-150);
  border-radius: 18px;
  background: var(--gray-0);
  box-shadow: 0 10px 22px var(--shadow-0);
  padding: 20px;
}

.reading-article {
  max-width: 760px;
  margin: 0 auto;
}

:deep(.markdown-preview) {
  background: transparent;
}

:deep(.markdown-preview h1) {
  margin-top: 0;
}

:deep(.markdown-preview h2) {
  margin-top: 2em;
  margin-bottom: 0.9em;
  padding-left: 10px;
  border-left: 4px solid var(--main-300);
}

:deep(.markdown-preview h3) {
  margin-top: 1.5em;
  margin-bottom: 0.8em;
}

:deep(.markdown-preview p),
:deep(.markdown-preview li) {
  line-height: 1.85;
  font-size: 16px;
}

:deep(.markdown-preview pre) {
  border: 1px solid var(--gray-200);
  border-radius: 14px;
  padding: 12px !important;
  background: #f8fafc !important;
}

:deep(.markdown-preview pre code) {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace !important;
  font-size: 13px;
  line-height: 1.7;
}

:deep(.markdown-preview blockquote) {
  border-left-color: var(--main-300);
  background: var(--main-10);
  border-radius: 0 10px 10px 0;
  padding: 10px 12px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-card {
  border: 1px solid var(--gray-150);
  border-radius: 18px;
  background: var(--gray-0);
  box-shadow: 0 8px 20px var(--shadow-0);
  padding: 18px;

  &.active {
    border-color: var(--main-300);
  }
}

.chunk-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.chunk-index {
  color: var(--main-700);
  font-weight: 700;
  font-size: 13px;
}

.qa-section + .qa-section {
  margin-top: 16px;
}

.qa-label {
  display: inline-flex;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--gray-500);
}

.qa-content,
.chunk-card__content {
  line-height: 1.8;
  color: var(--gray-800);
}

.qa-panel {
  margin-top: 12px;
  border: 1px solid var(--gray-150);
  border-radius: 18px;
  background: var(--gray-0);
  box-shadow: 0 8px 20px var(--shadow-0);
  padding: 16px;
}

.qa-panel__head {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-800);
  margin-bottom: 10px;
}

.qa-panel__list {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 10px;
}

.qa-panel__item {
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-10);
  padding: 12px;

  h4 {
    margin: 0;
    font-size: 14px;
    color: var(--gray-800);
  }

  p {
    margin: 8px 0 0;
    color: var(--gray-600);
    font-size: 13px;
    line-height: 1.7;
  }
}

.study-footer {
  margin-top: 12px;
  border: 1px solid var(--gray-150);
  border-radius: 18px;
  background: var(--gray-0);
  box-shadow: 0 8px 20px var(--shadow-0);
  padding: 14px;
}

.study-footer__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;

  > span {
    color: var(--gray-700);
    font-weight: 600;
  }
}

.study-footer__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.study-footer__next {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--gray-200);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  color: var(--gray-600);
  font-size: 13px;
}

.tool-rail {
  position: fixed;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 20;
}

.tool-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--gray-0);
  color: var(--gray-600);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.outline-drawer,
.drawer-tree {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.outline-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  padding: 8px 10px;
  cursor: pointer;
  color: var(--gray-700);

  &.active {
    border-color: var(--main-200);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.outline-item__text.level-3 {
  padding-left: 14px;
  font-size: 13px;
}

.notes-hint {
  margin: 10px 0 0;
  color: var(--gray-500);
  font-size: 12px;
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

  .mobile-btn {
    display: inline-flex;
  }

  .reading-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .content-panel {
    padding: 16px;
  }

  .content-header {
    flex-direction: column;
    align-items: stretch;
  }

  .content-header__left {
    flex-wrap: wrap;
  }

  .hero-card h1 {
    font-size: 26px;
  }

  .hero-actions,
  .study-footer__actions {
    width: 100%;
  }

  .study-footer__top,
  .study-footer__next {
    flex-direction: column;
    align-items: flex-start;
  }

  .markdown-panel {
    padding: 14px;
  }

  :deep(.markdown-preview p),
  :deep(.markdown-preview li) {
    font-size: 15px;
  }
}
</style>
