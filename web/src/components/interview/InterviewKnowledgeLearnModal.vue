<template>
  <a-modal
    v-model:open="visible"
    width="1100px"
    :footer="null"
    :destroyOnClose="true"
    wrap-class-name="interview-knowledge-learn-modal"
    :bodyStyle="{ padding: '0', height: '78vh', overflow: 'hidden' }"
  >
    <template #title>
      <div class="modal-title">
        <div class="modal-title__main">一键学习</div>
        <div class="modal-title__sub">{{ headerSubtitle }}</div>
      </div>
    </template>

    <div class="learning-modal">
      <div v-if="loading" class="state-panel">
        <a-spin tip="正在加载知识点内容..." />
      </div>

      <a-result
        v-else-if="errorMessage"
        status="warning"
        title="加载学习内容失败"
        :sub-title="errorMessage"
      />

      <template v-else-if="documentPayload">
        <div class="learning-banner">
          <div class="learning-banner__meta">
            <a-tag color="blue">{{ documentPayload.db_name || '知识库' }}</a-tag>
            <span class="learning-banner__file">{{ documentPayload.file_name || resource?.title || '文档' }}</span>
          </div>
          <div v-if="documentPayload.keyword" class="learning-banner__keyword">
            当前命中知识点：{{ documentPayload.keyword }}
          </div>
        </div>

        <div class="learning-toolbar">
          <a-segmented v-model:value="viewMode" :options="viewOptions" />
          <div v-if="viewMode === 'chunks'" class="learning-toolbar__meta">
            {{ qaStructuredCount ? `${qaStructuredCount} 个 QA 卡片` : `${parsedChunks.length} 个片段` }}
          </div>
        </div>

        <div class="learning-body" :class="viewMode">
          <div v-if="viewMode === 'chunks'" ref="chunksContainerRef" class="chunk-list">
            <div
              v-for="chunk in parsedChunks"
              :key="chunk.id || chunk.chunk_order_index"
              :data-chunk-id="chunk.id || ''"
              :data-chunk-index="chunk.chunk_order_index"
              :class="['chunk-card', { active: isTargetChunk(chunk) }]"
            >
              <div class="chunk-card__top">
                <span class="chunk-card__index">#{{ chunk.chunk_order_index }}</span>
                <a-tag v-if="isTargetChunk(chunk)" color="processing">当前定位</a-tag>
              </div>
              <template v-if="chunk.isQaStructured">
                <div class="qa-section">
                  <span class="qa-section__label">问题</span>
                  <div class="qa-section__content">{{ chunk.question }}</div>
                </div>
                <div v-if="chunk.answer" class="qa-section answer">
                  <span class="qa-section__label">学习要点</span>
                  <MdPreview
                    :model-value="chunk.answer"
                    :theme="theme"
                    preview-theme="github"
                    class="qa-section__markdown"
                  />
                </div>
              </template>
              <div v-else class="chunk-card__content">{{ chunk.preview }}</div>
            </div>
          </div>

          <div v-else ref="markdownContainerRef" class="markdown-panel">
            <MdPreview
              :model-value="documentPayload.content || ''"
              :theme="theme"
              preview-theme="github"
              class="markdown-preview"
            />
          </div>
        </div>
      </template>
    </div>
  </a-modal>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import { interviewCodeApi } from '@/apis/interview_code'
import { useThemeStore } from '@/stores/theme'

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  resource: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:open'])

const themeStore = useThemeStore()

const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))
const viewMode = ref('chunks')
const loading = ref(false)
const errorMessage = ref('')
const documentPayload = ref(null)
const chunksContainerRef = ref(null)
const markdownContainerRef = ref(null)

const viewOptions = [
  { label: 'QA 学习', value: 'chunks' },
  { label: '全文预览', value: 'markdown' }
]

const headerSubtitle = computed(() => {
  const locator = props.resource?.locator || {}
  const fileName = documentPayload.value?.file_name || props.resource?.title || '知识文档'
  const keyword = String(locator.keyword || '').trim()
  return keyword ? `${fileName} · ${keyword}` : fileName
})

const lines = computed(() => documentPayload.value?.lines || [])

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

  const question =
    questionMatch?.[1]?.trim() ||
    fields.title ||
    fields.question ||
    ''
  const answer =
    answerMatch?.[1]?.trim() ||
    body ||
    fields.description ||
    ''

  return {
    question,
    answer,
    preview,
    isQaStructured: Boolean(question && answer)
  }
}

const parsedChunks = computed(() =>
  lines.value.map((chunk) => ({
    ...chunk,
    ...parseQaChunk(chunk.content)
  }))
)

const qaStructuredCount = computed(() => parsedChunks.value.filter((chunk) => chunk.isQaStructured).length)

const isTargetChunk = (chunk) => {
  const targetChunkId = String(documentPayload.value?.target_chunk_id || '').trim()
  const targetChunkIndex = documentPayload.value?.target_chunk_index
  if (targetChunkId && String(chunk?.id || '').trim() === targetChunkId) {
    return true
  }
  return targetChunkIndex !== null && targetChunkIndex !== undefined && chunk?.chunk_order_index === targetChunkIndex
}

const scrollToTargetChunk = async () => {
  if (!visible.value || viewMode.value !== 'chunks') return
  await nextTick()
  const container = chunksContainerRef.value
  if (!container) return

  const targetChunkId = String(documentPayload.value?.target_chunk_id || '').trim()
  const targetChunkIndex = documentPayload.value?.target_chunk_index

  let selector = ''
  if (targetChunkId) {
    selector = `[data-chunk-id="${CSS.escape(targetChunkId)}"]`
  } else if (targetChunkIndex !== null && targetChunkIndex !== undefined) {
    selector = `[data-chunk-index="${targetChunkIndex}"]`
  }
  if (!selector) return

  const target = container.querySelector(selector)
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const loadDocument = async () => {
  const locator = props.resource?.locator
  if (!visible.value || !locator?.db_id || !locator?.file_id) return

  loading.value = true
  errorMessage.value = ''
  documentPayload.value = null
  viewMode.value = 'chunks'

  try {
    documentPayload.value = await interviewCodeApi.getLearningDocument(locator.db_id, locator.file_id, locator)
    await scrollToTargetChunk()
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
    message.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

watch(
  () => [visible.value, props.resource],
  async ([open]) => {
    if (!open) {
      errorMessage.value = ''
      documentPayload.value = null
      return
    }
    await loadDocument()
  },
  { deep: true }
)

watch(
  () => viewMode.value,
  async (value) => {
    if (value === 'chunks') {
      await scrollToTargetChunk()
    } else {
      await nextTick()
      markdownContainerRef.value?.scrollTo?.({ top: 0 })
    }
  }
)
</script>

<style scoped lang="less">
.modal-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.modal-title__main {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-900);
}

.modal-title__sub {
  font-size: 12px;
  color: var(--gray-500);
}

.learning-modal {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--gray-0);
}

.state-panel {
  min-height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.learning-banner {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--gray-150);
  background: var(--gray-25);
  flex-wrap: wrap;
}

.learning-banner__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.learning-banner__file {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.learning-banner__keyword {
  font-size: 13px;
  color: var(--main-color);
}

.learning-toolbar {
  padding: 12px 20px;
  border-bottom: 1px solid var(--gray-100);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.learning-toolbar__meta {
  font-size: 12px;
  color: var(--gray-500);
}

.learning-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.chunk-list,
.markdown-panel {
  height: 100%;
  overflow-y: auto;
  padding: 16px 20px 20px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chunk-card {
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 14px;
  background: var(--gray-0);
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.chunk-card.active {
  border-color: var(--main-color);
  background: var(--main-5);
  box-shadow: inset 0 0 0 1px var(--main-100);
}

.chunk-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.chunk-card__index {
  font-size: 12px;
  font-weight: 700;
  color: var(--main-color);
}

.chunk-card__content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-700);
}

.qa-section {
  padding: 12px;
  border-radius: 10px;
  background: var(--gray-25);
}

.qa-section + .qa-section {
  margin-top: 10px;
}

.qa-section.answer {
  background: var(--main-5);
}

.qa-section__label {
  display: inline-flex;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--gray-500);
}

.qa-section__content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-700);
}

.qa-section__markdown {
  background: transparent;
}

.qa-section__markdown :deep(.md-editor) {
  background: transparent;
}

.qa-section__markdown :deep(.md-editor-preview-wrapper) {
  padding: 0;
}

.qa-section__markdown :deep(.md-editor-preview) {
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-700);
}

.qa-section__markdown :deep(.md-editor-preview p:first-child) {
  margin-top: 0;
}

.qa-section__markdown :deep(.md-editor-preview p:last-child) {
  margin-bottom: 0;
}

.markdown-preview {
  min-height: 100%;
}

.markdown-panel :deep(.md-editor),
.markdown-panel :deep(.md-editor-preview),
.markdown-panel :deep(.md-editor-preview-wrapper) {
  min-height: 100%;
}

@media (max-width: 768px) {
  .learning-banner {
    align-items: flex-start;
  }

  .chunk-list,
  .markdown-panel {
    padding: 12px 16px 16px;
  }
}
</style>
