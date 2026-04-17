<template>
  <div class="learn-document-page">
    <div class="page-shell">
      <aside class="sidebar desktop-only">
        <div class="sidebar-section">
          <div class="sidebar-label">专题文档</div>
          <button
            v-for="item in documents"
            :key="item.file_id"
            type="button"
            :class="['doc-link', { active: item.file_id === currentFileId }]"
            @click="goToDocument(item.file_id)"
          >
            <span class="doc-link__title">{{ formatDisplayName(item.filename) }}</span>
            <span v-if="item.folder_path" class="doc-link__meta">{{ item.folder_path }}</span>
          </button>
        </div>

        <div v-if="hasQaStructured && viewMode === 'chunks'" class="sidebar-section outline">
          <div class="sidebar-label">当前文档导读</div>
          <button
            v-for="chunk in parsedChunks"
            :key="chunk.id || chunk.chunk_order_index"
            type="button"
            :class="['outline-link', { active: activeChunkIndex === chunk.chunk_order_index }]"
            @click="scrollToChunk(chunk.chunk_order_index)"
          >
            <span>#{{ chunk.chunk_order_index }}</span>
            <span>{{ chunk.question || chunk.preview }}</span>
          </button>
        </div>
      </aside>

      <main class="content-panel">
        <div class="content-header">
          <div class="content-header__left">
            <a-button type="text" class="back-btn" @click="router.push(`/learn/${dbId}`)">
              返回专题
            </a-button>
            <a-button type="text" class="mobile-outline" @click="drawerOpen = true">
              目录
            </a-button>
            <div class="breadcrumbs">
              <span>{{ database?.name || '知识专题' }}</span>
              <span>/</span>
              <span>{{
                formatDisplayName(documentPayload?.file_name || currentDocument?.filename || '文档学习')
              }}</span>
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
            <div class="hero-card__title">
              <span class="hero-badge">{{ database?.position || '知识学习' }}</span>
              <h1>{{ formatDisplayName(documentPayload.file_name || currentDocument?.filename) }}</h1>
              <p>{{ currentDocument?.summary || '支持分块学习和全文预览两种阅读方式。' }}</p>
            </div>
            <div class="hero-card__stats">
              <div class="stat-box">
                <strong>{{ hasQaStructured ? parsedChunks.length : 1 }}</strong>
                <span>个内容分块</span>
              </div>
              <div class="stat-box">
                <strong>{{ qaStructuredCount }}</strong>
                <span>个 QA 卡片</span>
              </div>
            </div>
          </section>

          <section v-if="hasQaStructured && viewMode === 'chunks'" ref="chunksContainerRef" class="chunk-list">
            <article
              v-for="chunk in parsedChunks"
              :key="chunk.id || chunk.chunk_order_index"
              :data-chunk-index="chunk.chunk_order_index"
              :class="['chunk-card', { active: activeChunkIndex === chunk.chunk_order_index }]"
            >
              <div class="chunk-card__top">
                <span class="chunk-index">#{{ chunk.chunk_order_index }}</span>
                <a-tag v-if="activeChunkIndex === chunk.chunk_order_index" color="processing">
                  当前阅读
                </a-tag>
              </div>

              <template v-if="chunk.isQaStructured">
                <div class="qa-section">
                  <span class="qa-label">问题</span>
                  <div class="qa-content">{{ chunk.question }}</div>
                </div>
                <div v-if="chunk.answer" class="qa-section answer">
                  <span class="qa-label">学习要点</span>
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

          <section v-else class="markdown-panel">
            <MdPreview
              :model-value="documentPayload.content || ''"
              :theme="theme"
              preview-theme="github"
              class="markdown-preview"
            />
          </section>
        </template>
      </main>
    </div>

    <a-drawer v-model:open="drawerOpen" title="学习目录" placement="left" width="320">
      <div class="sidebar-section">
        <div class="sidebar-label">专题文档</div>
        <button
          v-for="item in documents"
          :key="item.file_id"
          type="button"
          :class="['doc-link', { active: item.file_id === currentFileId }]"
          @click="handleDrawerDocumentClick(item.file_id)"
        >
          <span class="doc-link__title">{{ formatDisplayName(item.filename) }}</span>
          <span v-if="item.folder_path" class="doc-link__meta">{{ item.folder_path }}</span>
        </button>
      </div>

      <div v-if="hasQaStructured && viewMode === 'chunks'" class="sidebar-section outline">
        <div class="sidebar-label">当前文档导读</div>
        <button
          v-for="chunk in parsedChunks"
          :key="chunk.id || chunk.chunk_order_index"
          type="button"
          :class="['outline-link', { active: activeChunkIndex === chunk.chunk_order_index }]"
          @click="handleDrawerChunkClick(chunk.chunk_order_index)"
        >
          <span>#{{ chunk.chunk_order_index }}</span>
          <span>{{ chunk.question || chunk.preview }}</span>
        </button>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const drawerOpen = ref(false)
const viewMode = ref('chunks')
const database = ref(null)
const documentPayload = ref(null)
const chunksContainerRef = ref(null)
const activeChunkIndex = ref(null)

const formatDisplayName = (value) => String(value || '').replace(/\.md$/i, '')

const dbId = computed(() => String(route.params.db_id || '').trim())
const currentFileId = computed(() => String(route.params.file_id || '').trim())
const documents = computed(() => (Array.isArray(database.value?.documents) ? database.value.documents : []))
const currentDocument = computed(() =>
  documents.value.find((item) => item.file_id === currentFileId.value) || null
)
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))

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
        { label: '分块学习', value: 'chunks' },
        { label: '全文预览', value: 'markdown' }
      ]
    : [{ label: '全文预览', value: 'markdown' }]
)

const loadPage = async () => {
  if (!dbId.value || !currentFileId.value) {
    database.value = null
    documentPayload.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''
  viewMode.value = 'chunks'

  try {
    const [databaseData, documentData] = await Promise.all([
      learnApi.getDatabaseDetail(dbId.value),
      interviewCodeApi.getLearningDocument(dbId.value, currentFileId.value)
    ])
    database.value = databaseData
    documentPayload.value = documentData
    viewMode.value = hasQaStructured.value ? 'chunks' : 'markdown'
    activeChunkIndex.value = hasQaStructured.value
      ? parsedChunks.value[0]?.chunk_order_index ?? documentData?.target_chunk_index ?? null
      : null
    await nextTick()
    if (hasQaStructured.value) {
      scrollToChunk(activeChunkIndex.value, { smooth: false })
    }
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

const goToDocument = (fileId) => {
  if (!fileId || fileId === currentFileId.value) return
  router.push(`/learn/${dbId.value}/doc/${fileId}`)
}

const scrollToChunk = async (chunkIndex, { smooth = true } = {}) => {
  if (chunkIndex === null || chunkIndex === undefined) return
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

const handleDrawerDocumentClick = (fileId) => {
  drawerOpen.value = false
  goToDocument(fileId)
}

const handleDrawerChunkClick = (chunkIndex) => {
  drawerOpen.value = false
  scrollToChunk(chunkIndex)
}

watch(
  () => [route.params.db_id, route.params.file_id],
  () => {
    loadPage()
  },
  { immediate: true }
)

watch(
  () => viewMode.value,
  async (value) => {
    if (!hasQaStructured.value) {
      viewMode.value = 'markdown'
      activeChunkIndex.value = null
      return
    }

    if (value === 'chunks') {
      await scrollToChunk(activeChunkIndex.value)
    } else {
      activeChunkIndex.value = null
    }
  }
)
</script>

<style scoped lang="less">
.learn-document-page {
  height: 100%;
  background: var(--gray-25);
}

.page-shell {
  display: flex;
  min-height: 100%;
}

.sidebar {
  width: 320px;
  border-right: 1px solid var(--gray-150);
  background: var(--gray-0);
  padding: 20px 16px;
  overflow-y: auto;
}

.sidebar-section + .sidebar-section {
  margin-top: 20px;
}

.sidebar-label {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-500);
}

.doc-link,
.outline-link {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 16px;
  background: transparent;
  padding: 12px 14px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--gray-700);

  &.active {
    background: var(--main-50);
    border-color: var(--main-100);
    color: var(--main-700);
  }
}

.doc-link__title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.doc-link__meta,
.outline-link span:last-child {
  font-size: 12px;
  color: var(--gray-500);
  line-height: 1.5;
}

.outline-link {
  flex-direction: row;
  gap: 10px;

  span:first-child {
    flex: 0 0 auto;
    font-size: 12px;
    font-weight: 700;
    color: inherit;
  }
}

.content-panel {
  flex: 1;
  min-width: 0;
  padding: 20px 24px 32px;
}

.content-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
}

.content-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.back-btn,
.mobile-outline {
  color: var(--gray-700);
}

.mobile-outline {
  display: none;
}

.breadcrumbs {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-500);
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;

  span:last-child {
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 26px;
  border: 1px solid var(--gray-150);
  border-radius: 24px;
  background: var(--gray-0);
  box-shadow: 0 12px 30px var(--shadow-0);
  margin-bottom: 18px;
}

.hero-card__title {
  max-width: 860px;

  h1 {
    margin: 12px 0 10px;
    font-size: 28px;
    color: var(--gray-2000);
  }

  p {
    margin: 0;
    color: var(--gray-600);
    line-height: 1.8;
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

.hero-card__stats {
  display: flex;
  gap: 12px;
}

.stat-box {
  min-width: 120px;
  padding: 16px 18px;
  border-radius: 20px;
  background: var(--gray-10);
  display: flex;
  flex-direction: column;
  gap: 8px;

  strong {
    font-size: 24px;
    color: var(--gray-2000);
  }

  span {
    font-size: 13px;
    color: var(--gray-600);
  }
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chunk-card,
.markdown-panel {
  border: 1px solid var(--gray-150);
  border-radius: 24px;
  background: var(--gray-0);
  box-shadow: 0 10px 24px var(--shadow-0);
}

.chunk-card {
  padding: 22px;

  &.active {
    border-color: var(--main-200);
  }
}

.chunk-card__top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.chunk-index {
  font-size: 12px;
  font-weight: 700;
  color: var(--main-700);
}

.chunk-card__content,
.qa-content {
  color: var(--gray-800);
  line-height: 1.8;
  white-space: pre-wrap;
}

.qa-section + .qa-section {
  margin-top: 18px;
}

.qa-label {
  display: inline-flex;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 700;
  color: var(--gray-500);
}

.markdown-panel {
  padding: 24px;
}

:deep(.markdown-preview) {
  background: transparent;
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

@media (max-width: 1100px) {
  .desktop-only {
    display: none;
  }

  .mobile-outline {
    display: inline-flex;
  }

  .content-panel {
    padding: 18px;
  }
}

@media (max-width: 900px) {
  .content-header,
  .hero-card,
  .hero-card__stats {
    flex-direction: column;
  }

  .content-header {
    align-items: stretch;
  }

  .content-header__left {
    flex-wrap: wrap;
  }
}
</style>
