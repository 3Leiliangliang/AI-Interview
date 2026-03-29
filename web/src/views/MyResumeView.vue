<template>
  <div class="resume-page">
    <HeaderComponent
      title="我的简历"
      description="统一管理已上传的 PDF 简历，点击列表项可查看解析详情。"
      :loading="loading || uploading"
    >
      <template #actions>
        <a-upload
          :show-upload-list="false"
          accept=".pdf,application/pdf"
          :disabled="uploading"
          :multiple="false"
          :before-upload="beforeUpload"
          :custom-request="handleUpload"
        >
          <a-button type="primary" :loading="uploading">
            <FileUp :size="14" />
            上传简历
          </a-button>
        </a-upload>
        <a-button :loading="loading" @click="loadResumes">
          <RefreshCw :size="14" />
          刷新
        </a-button>
      </template>
    </HeaderComponent>

    <div class="resume-content">
      <!-- 上传动画覆盖层 -->
      <div v-if="showUploadingAnimation" class="upload-animation-overlay">
        <ResumeExtractingAnimation :stage="uploadStage" />
      </div>

      <div v-if="loading" class="state-wrapper">
        <a-spin />
      </div>

      <div v-else-if="resumes.length === 0" class="empty-wrapper">
        <a-empty description="还没有上传简历">
          <a-upload
            :show-upload-list="false"
            accept=".pdf,application/pdf"
            :disabled="uploading"
            :multiple="false"
            :before-upload="beforeUpload"
            :custom-request="handleUpload"
          >
            <a-button type="primary" :loading="uploading">
              <FileUp :size="14" />
              上传第一份简历
            </a-button>
          </a-upload>
        </a-empty>
      </div>

      <div v-else class="resume-list">
        <a-card
          v-for="item in resumes"
          :key="item.id"
          class="resume-card"
          :bordered="false"
          @click="openDetail(item.id)"
        >
          <div class="card-header">
            <div class="card-title">
              <FileText :size="18" />
              <span class="filename">{{ item.filename }}</span>
            </div>
            <a-tag color="blue">{{ item.parser_name }}</a-tag>
          </div>

          <div class="card-meta">
            <span>文件大小：{{ formatFileSize(item.file_size) }}</span>
            <span>更新时间：{{ formatDateTime(item.updated_at || item.created_at) }}</span>
          </div>

          <div class="card-footer">
            <span class="detail-link">查看详情</span>
            <a-popconfirm
              title="确认删除这份简历吗？"
              ok-text="删除"
              cancel-text="取消"
              @confirm="handleDelete(item.id)"
            >
              <a-button type="text" danger :loading="deletingId === item.id" @click.stop>
                <Trash2 :size="14" />
                删除
              </a-button>
            </a-popconfirm>
          </div>
        </a-card>
      </div>
    </div>

  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message, Upload } from 'ant-design-vue'
import { FileText, FileUp, RefreshCw, Trash2 } from 'lucide-vue-next'

import HeaderComponent from '@/components/HeaderComponent.vue'
import ResumeExtractingAnimation from '@/components/ResumeExtractingAnimation.vue'
import { resumeApi } from '@/apis/resume_api'

const router = useRouter()

const loading = ref(false)
const uploading = ref(false)
const deletingId = ref(null)
const resumes = ref([])
const showUploadingAnimation = ref(false)
const uploadStage = ref('idle')

const loadResumes = async () => {
  loading.value = true
  try {
    const data = await resumeApi.getMyResumes()
    resumes.value = data?.resumes || []
  } catch (error) {
    console.error('加载简历列表失败:', error)
    message.error(error.message || '加载简历列表失败')
  } finally {
    loading.value = false
  }
}

const beforeUpload = (file) => {
  const fileName = file?.name || ''
  if (!fileName.toLowerCase().endsWith('.pdf')) {
    message.error('仅支持上传 PDF 简历')
    return Upload.LIST_IGNORE
  }
  return true
}

const handleUpload = async ({ file, onSuccess, onError }) => {
  try {
    uploadStage.value = 'parsing'
    showUploadingAnimation.value = true
    uploading.value = true
    const result = await resumeApi.uploadResume(file)
    uploadStage.value = 'extracting'
    message.success('简历上传成功，正在分析中...')
    onSuccess?.(result)

    if (result?.resume?.id) {
      router.push({ path: `/resume/${result.resume.id}`, query: { extracting: '1' } })
    } else {
      showUploadingAnimation.value = false
      uploadStage.value = 'idle'
      await loadResumes()
    }
  } catch (error) {
    console.error('上传简历失败:', error)
    message.error(error.message || '上传简历失败')
    onError?.(error)
    showUploadingAnimation.value = false
    uploadStage.value = 'idle'
  } finally {
    uploading.value = false
  }
}

const openDetail = (resumeId) => {
  router.push(`/resume/${resumeId}`)
}

const handleDelete = async (resumeId) => {
  try {
    deletingId.value = resumeId
    await resumeApi.deleteResume(resumeId)
    resumes.value = resumes.value.filter((item) => item.id !== resumeId)
    message.success('简历已删除')
  } catch (error) {
    console.error('删除简历失败:', error)
    message.error(error.message || '删除简历失败')
  } finally {
    deletingId.value = null
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) {
    return '0 B'
  }

  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }

  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

const formatDateTime = (value) => {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

onMounted(() => {
  loadResumes()
})
</script>

<style scoped lang="less">
.resume-page {
  min-height: 100%;
  background: var(--gray-25);
}

.resume-content {
  padding: 16px;
  position: relative;
  min-height: calc(100vh - 140px);
}

.resume-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.resume-card {
  cursor: pointer;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  box-shadow: none;

  :deep(.ant-card-body) {
    padding: 16px;
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--gray-900);
}

.filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 500;
}

.card-meta {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: var(--gray-600);
  font-size: 13px;
}

.card-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--gray-150);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-link {
  color: var(--main-color);
  font-size: 13px;
}

.state-wrapper,
.empty-wrapper {
  min-height: calc(100vh - 220px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-animation-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(4px);
  border-radius: 12px;
}
</style>
