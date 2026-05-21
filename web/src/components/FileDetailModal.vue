<template>
  <a-modal
    v-model:open="visible"
    width="1200px"
    :footer="null"
    :closable="false"
    wrap-class-name="file-detail"
    @after-open-change="afterOpenChange"
    :bodyStyle="{ height: '80vh', padding: '0' }"
  >
    <template #title>
      <div class="modal-title-wrapper">
        <!-- 左侧：文件名和图标 -->
        <div class="file-title">
          <component :is="fileIcon" :style="{ color: fileIconColor, fontSize: '18px' }" />
          <div class="file-title-meta">
            <span class="file-name">{{ file?.filename || '文件详情' }}</span>
            <div v-if="detailTags.length > 0" class="detail-tags">
              <a-tag v-for="tag in detailTags" :key="tag.key" :color="tag.color">
                {{ tag.label }}
              </a-tag>
            </div>
          </div>
        </div>

        <div class="header-controls">
          <!-- 字符数/片段数显示在 segment 左边 -->
          <span class="view-info">
            {{ viewInfoText }}
          </span>

          <!-- 视图模式切换 -->
          <div class="view-controls" v-if="file && hasChunks">
            <a-segmented v-model:value="viewMode" :options="viewModeOptions" />
          </div>

          <!-- 下载按钮下拉菜单 -->
          <a-dropdown trigger="click" v-if="file">
            <a-button type="default" class="download-btn">
              <template #icon><Download :size="16" /></template>
              下载
              <ChevronDown :size="16" style="margin-left: 4px" />
            </a-button>
            <template #overlay>
              <a-menu @click="handleDownloadMenuClick">
                <a-menu-item key="original" :disabled="!file.file_id">
                  <template #icon><Download :size="16" /></template>
                  下载原文
                </a-menu-item>
                <a-menu-item
                  key="markdown"
                  :disabled="!((file.lines && file.lines.length > 0) || file.content)"
                >
                  <template #icon><FileText :size="16" /></template>
                  下载 Markdown
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>

          <!-- 自定义关闭按钮 -->
          <button class="custom-close-btn" @click="visible = false">
            <X :size="16" />
          </button>
        </div>
      </div>
    </template>
    <div v-if="loading" class="loading-container">
      <a-spin tip="正在加载文档内容..." />
    </div>
    <div v-else-if="file && hasContent" class="file-detail-content">
      <!-- Markdown 模式 -->
      <div v-if="viewMode === 'markdown'" class="content-panel flat-md-preview">
        <MdPreview
          v-if="mergedContent"
          :modelValue="mergedContent"
          :theme="theme"
          previewTheme="github"
          class="markdown-content"
        />
        <div v-else class="empty-content">
          <p>暂无文件内容</p>
        </div>
      </div>

      <!-- Chunks 模式：使用 Grid 布局 -->
      <div v-else-if="viewMode === 'chunks'" class="chunks-panel">
        <div class="chunks-overview" :class="{ qa: isQaPreset }">
          <div class="chunks-overview-main">
            <div class="chunks-overview-title-row">
              <span class="chunks-overview-label">当前分块策略</span>
              <span class="chunks-preset-badge">{{ databasePresetLabel }}</span>
            </div>
            <p class="chunks-overview-description">{{ databasePresetDescription }}</p>
          </div>
          <div class="chunks-overview-stats">
            <div class="overview-stat">
              <span class="overview-stat-label">片段数</span>
              <strong class="overview-stat-value">{{ chunkCount }}</strong>
            </div>
            <div v-if="isQaPreset" class="overview-stat">
              <span class="overview-stat-label">识别问题</span>
              <strong class="overview-stat-value">{{ qaQuestionCount }}</strong>
            </div>
            <div v-if="isQaPreset" class="overview-stat">
              <span class="overview-stat-label">识别回答</span>
              <strong class="overview-stat-value">{{ qaAnswerCount }}</strong>
            </div>
          </div>
        </div>
        <div class="chunk-grid">
          <div
            v-for="chunk in displayChunks"
            :key="chunk.id"
            class="chunk-card"
            :class="{ qa: isQaPreset, structured: chunk.isQaStructured }"
          >
            <div class="chunk-card-header">
              <span class="chunk-order">#{{ chunk.chunk_order_index }}</span>
              <span v-if="isQaPreset" class="chunk-type-badge">
                {{ chunk.isQaStructured ? '问答' : '片段' }}
              </span>
            </div>
            <template v-if="isQaPreset && chunk.isQaStructured">
              <div class="qa-section">
                <span class="qa-section-label">问题</span>
                <div class="qa-section-content">{{ chunk.question }}</div>
              </div>
              <div v-if="chunk.answer" class="qa-section answer">
                <span class="qa-section-label">回答</span>
                <div class="qa-section-content">{{ chunk.answer }}</div>
              </div>
            </template>
            <div v-else class="chunk-card-content">
              {{ chunk.preview }}
            </div>
          </div>
        </div>
        <div v-if="displayChunks.length === 0" class="empty-content">
          <p>暂无分块信息</p>
        </div>
      </div>
    </div>

    <div v-else-if="file" class="empty-content">
      <p>暂无文件内容</p>
    </div>
  </a-modal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useDatabaseStore } from '@/stores/database'
import { useThemeStore } from '@/stores/theme'
import { message } from 'ant-design-vue'
import { documentApi } from '@/apis/knowledge_api'
import { mergeChunks } from '@/utils/chunkUtils'
import { getFileIcon, getFileIconColor } from '@/utils/file_utils'
import { CHUNK_PRESET_LABEL_MAP, getChunkPresetDescription } from '@/utils/chunk_presets'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'
import { Download, ChevronDown, FileText, X } from 'lucide-vue-next'

const store = useDatabaseStore()
const themeStore = useThemeStore()

const visible = computed({
  get: () => store.state.fileDetailModalVisible,
  set: (value) => (store.state.fileDetailModalVisible = value)
})

const file = computed(() => store.selectedFile)
const loading = computed(() => store.state.fileDetailLoading)
const detailTags = computed(() => {
  const processingParams = file.value?.processing_params || {}
  const tags = []
  for (const tag of processingParams.position_tags || []) {
    tags.push({ key: `position-${tag}`, label: tag, color: 'geekblue' })
  }
  for (const tag of processingParams.topic_tags || []) {
    tags.push({ key: `topic-${tag}`, label: tag, color: 'green' })
  }
  if (processingParams.content_kind) {
    tags.push({ key: `kind-${processingParams.content_kind}`, label: processingParams.content_kind, color: 'cyan' })
  }
  return tags
})

// 文件图标
const fileIcon = computed(() => getFileIcon(file.value?.filename))
const fileIconColor = computed(() => getFileIconColor(file.value?.filename))

const downloadingOriginal = ref(false)
const downloadingMarkdown = ref(false)

// 主题设置
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))

// 视图模式
const viewMode = ref('markdown')
const hasIndexed = computed(() => ['done', 'indexed'].includes(file.value?.status))
const hasContent = computed(
  () => (file.value?.lines && file.value?.lines.length > 0) || file.value?.content
)
const databasePresetId = computed(
  () => store.database?.additional_params?.chunk_preset_id || 'general'
)
const databasePresetLabel = computed(
  () => CHUNK_PRESET_LABEL_MAP[databasePresetId.value] || 'General'
)
const databasePresetDescription = computed(() => getChunkPresetDescription(databasePresetId.value))
const isQaPreset = computed(() => databasePresetId.value === 'qa')
// 是否有实际的分块数据
const hasChunks = computed(() => mappedChunks.value && mappedChunks.value.length > 0)

const viewModeOptions = computed(() => {
  const options = [{ label: 'Markdown', value: 'markdown' }]
  // 只有当有实际的分块数据时才显示 Chunks 选项
  if (hasChunks.value) {
    options.push({ label: isQaPreset.value ? 'QA Chunks' : 'Chunks', value: 'chunks' })
  }
  return options
})

// 监听文件变化，如果没有 chunks 则重置为 markdown
watch(file, (newFile) => {
  if (newFile && !hasChunks.value) {
    viewMode.value = 'markdown'
  }
})

// 统计信息
const mergeResult = computed(() => mergeChunks(file.value?.lines || []))
const mappedChunks = computed(() => mergeResult.value.chunks)
const parseQaChunk = (content) => {
  const raw = String(content || '').trim()
  const preview = raw.replace(/\n+/g, ' ').trim()
  const questionMatch = raw.match(/(?:问题|Question)\s*[:：]\s*([\s\S]*?)(?=(?:回答|Answer)\s*[:：]|$)/i)
  const answerMatch = raw.match(/(?:回答|Answer)\s*[:：]\s*([\s\S]*)$/i)
  const question = questionMatch?.[1]?.trim() || ''
  const answer = answerMatch?.[1]?.trim() || ''

  return {
    question,
    answer,
    isQaStructured: Boolean(question || answer),
    preview
  }
}
const displayChunks = computed(() =>
  mappedChunks.value.map((chunk) => ({
    ...chunk,
    ...parseQaChunk(chunk.content)
  }))
)
const mergedContent = computed(() => file.value?.content || mergeResult.value.content || '')
const charCount = computed(() => mergedContent.value.length)
const chunkCount = computed(() => mappedChunks.value.length || file.value?.lines?.length || 0)
const qaQuestionCount = computed(() => displayChunks.value.filter((chunk) => chunk.question).length)
const qaAnswerCount = computed(() => displayChunks.value.filter((chunk) => chunk.answer).length)
const viewInfoText = computed(() =>
  viewMode.value === 'chunks'
    ? `${chunkCount.value} 个片段 · ${databasePresetLabel.value} 分块`
    : `${formatTextLength(charCount.value)} 字符`
)

// 格式化文本长度
function formatTextLength(length) {
  if (!length && length !== 0) return '0 字符'

  if (length < 1000) {
    return `${length}`
  } else {
    return `${(length / 1000).toFixed(1)}k`
  }
}

const afterOpenChange = (open) => {
  if (!open) {
    store.selectedFile = null
    viewMode.value = 'markdown'
  }
}

// 下载菜单点击处理
const handleDownloadMenuClick = ({ key }) => {
  if (key === 'original') {
    handleDownloadOriginal()
  } else if (key === 'markdown') {
    handleDownloadMarkdown()
  }
}

// 下载原文
const handleDownloadOriginal = async () => {
  if (!file.value || !file.value.file_id) {
    message.error('文件信息不完整')
    return
  }

  const dbId = store.databaseId
  if (!dbId) {
    message.error('无法获取数据库ID，请刷新页面后重试')
    return
  }

  downloadingOriginal.value = true
  try {
    const response = await documentApi.downloadDocument(dbId, file.value.file_id)

    // 获取文件名
    const contentDisposition = response.headers.get('content-disposition')
    let filename = file.value.filename
    if (contentDisposition) {
      // 首先尝试匹配RFC 2231格式 filename*=UTF-8''...
      const rfc2231Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
      if (rfc2231Match) {
        try {
          filename = decodeURIComponent(rfc2231Match[1])
        } catch (error) {
          console.warn('Failed to decode RFC2231 filename:', rfc2231Match[1], error)
        }
      } else {
        // 回退到标准格式 filename="..."
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/['"]/g, '')
          // 解码URL编码的文件名
          try {
            filename = decodeURIComponent(filename)
          } catch (error) {
            console.warn('Failed to decode filename:', filename, error)
          }
        }
      }
    }

    // 创建blob并下载
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success('下载成功')
  } catch (error) {
    console.error('下载文件时出错:', error)
    message.error(error.message || '下载文件失败')
  } finally {
    downloadingOriginal.value = false
  }
}

// 下载 Markdown
const handleDownloadMarkdown = () => {
  const content = mergedContent.value

  if (!content) {
    message.error('没有可下载的 Markdown 内容')
    return
  }

  downloadingMarkdown.value = true
  try {
    // 生成文件名（如果原文件没有 .md 扩展名，则添加）
    let filename = file.value.filename || 'document.md'
    if (!filename.toLowerCase().endsWith('.md')) {
      // 移除原扩展名，添加 .md
      const lastDotIndex = filename.lastIndexOf('.')
      if (lastDotIndex > 0) {
        filename = filename.substring(0, lastDotIndex) + '.md'
      } else {
        filename = filename + '.md'
      }
    }

    // 创建 blob 并下载
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    message.success('下载成功')
  } catch (error) {
    console.error('下载 Markdown 时出错:', error)
    message.error(error.message || '下载 Markdown 失败')
  } finally {
    downloadingMarkdown.value = false
  }
}
</script>

<style scoped>
.file-detail-content {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.content-panel,
.chunks-panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
  min-height: 0;
}

.markdown-content {
  min-height: 100%;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}

.empty-content {
  text-align: center;
  padding: 40px 0;
  color: var(--gray-400);
  width: 100%;
}

/* Chunks 面板样式 */
.chunks-overview {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: stretch;
  padding: 0 16px 16px;
  margin-bottom: 4px;
}

.chunks-overview.qa .chunks-overview-main,
.chunks-overview.qa .chunks-overview-stats {
  border-color: rgba(8, 145, 178, 0.2);
  background: linear-gradient(135deg, rgba(236, 254, 255, 0.95) 0%, rgba(248, 250, 252, 1) 100%);
}

.chunks-overview-main,
.chunks-overview-stats {
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--gray-0);
  padding: 14px 16px;
}

.chunks-overview-main {
  flex: 1;
}

.chunks-overview-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.chunks-overview-label {
  font-size: 13px;
  color: var(--gray-500);
}

.chunks-preset-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(8, 145, 178, 0.12);
  color: rgb(14, 116, 144);
  font-size: 12px;
  font-weight: 700;
}

.chunks-overview-description {
  margin: 0;
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.6;
}

.chunks-overview-stats {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: fit-content;
}

.overview-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.overview-stat-label {
  font-size: 12px;
  color: var(--gray-500);
}

.overview-stat-value {
  font-size: 18px;
  line-height: 1;
  color: var(--gray-900);
}

.chunk-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  padding: 0 16px 16px;
}

.chunk-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s ease;
}

.chunk-card.qa.structured {
  border-color: rgba(8, 145, 178, 0.18);
  background: linear-gradient(180deg, rgba(248, 252, 255, 0.95) 0%, var(--gray-0) 100%);
}

.chunk-card:hover {
  border-color: var(--main-color);
  box-shadow: 0 2px 8px rgba(1, 97, 121, 0.1);
}

.chunk-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chunk-order {
  font-weight: 600;
  color: var(--main-color);
  font-size: 12px;
}

.chunk-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(8, 145, 178, 0.1);
  color: rgb(14, 116, 144);
  font-size: 12px;
  font-weight: 600;
}

.qa-section {
  border-radius: 10px;
  background: var(--gray-10);
  padding: 10px 12px;
}

.qa-section + .qa-section {
  margin-top: 10px;
}

.qa-section.answer {
  background: rgba(8, 145, 178, 0.05);
}

.qa-section-label {
  display: inline-flex;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--gray-500);
}

.qa-section-content {
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chunk-card-content {
  font-size: 13px;
  color: var(--gray-600);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}

@media (max-width: 900px) {
  .chunks-overview {
    flex-direction: column;
  }

  .chunks-overview-stats {
    justify-content: space-between;
  }
}
</style>

<style lang="less">
.file-detail {
  .ant-modal {
    top: 20px;
  }

  .ant-modal-header {
    .ant-modal-title {
      width: 100%;
    }
  }
}

.modal-title-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

/* 文件标题样式 */
.file-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-title-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--gray-900);
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.title-info {
  font-size: 13px;
  color: var(--gray-600);
  font-weight: 500;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

/* 下载按钮样式 */
.download-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  height: 28px;
  font-size: 13px;
  line-height: 1;
  border-radius: 6px;
  gap: 4px;

  svg {
    vertical-align: middle;
  }
}

/* 自定义关闭按钮 */
.custom-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  color: var(--gray-500);
  transition: all 0.2s;

  &:hover {
    background: var(--gray-100);
    color: var(--gray-700);
  }
}

/* 视图切换控件 */
.view-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.view-info {
  font-size: 12px;
  color: var(--gray-500);
  white-space: nowrap;
}

/* 下拉菜单样式 */
.ant-dropdown-menu {
  border-radius: 8px;
  padding: 4px;
}

.ant-dropdown-menu-item {
  border-radius: 6px;
  display: flex;
  align-items: center;
  padding: 8px 12px;

  svg {
    margin-right: 8px;
  }
}
</style>
