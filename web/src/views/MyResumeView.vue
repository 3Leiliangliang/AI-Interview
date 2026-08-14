<template>
  <div class="resume-page">
    <HeaderComponent :title="'我的简历'" :loading="loading || uploading">
      <template #description>
        <p>{{ resumeSummaryText }}</p>
      </template>
      <template #actions>
        <a-button :loading="loading" @click="loadResumes">
          <RefreshCw :size="14" />
          刷新
        </a-button>
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
      </template>
    </HeaderComponent>

    <div class="resume-content">
      <a-upload-dragger
        class="resume-upload-band"
        :show-upload-list="false"
        accept=".pdf,application/pdf"
        :disabled="uploading"
        :multiple="false"
        :before-upload="beforeUpload"
        :custom-request="handleUpload"
      >
        <div class="upload-band-inner">
          <div class="upload-band-copy">
            <div class="upload-band-title">把 PDF 拖到这里上传</div>
            <div class="upload-band-desc">单个文件不超过 20 MB，上传后由 mineru 解析出结构化信息</div>
          </div>
          <button class="select-file-btn" type="button" :disabled="uploading">选择文件</button>
        </div>
      </a-upload-dragger>

      <div v-if="loading" class="state-wrapper">
        <a-spin />
      </div>

      <div v-else-if="resumes.length > 0" class="resume-table-wrap">
        <table class="resume-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th class="status-col">解析状态</th>
              <th class="sortable progress-col" @click="setSort('completeness')">
                <span>完整度</span>
                <SortIcon :active="sortKey === 'completeness'" :order="sortOrder" />
              </th>
              <th class="sortable match-col" @click="setSort('match')">
                <span>岗位匹配</span>
                <SortIcon :active="sortKey === 'match'" :order="sortOrder" />
              </th>
              <th class="size-col">大小</th>
              <th class="sortable time-col" @click="setSort('updated')">
                <span>更新时间</span>
                <SortIcon :active="sortKey === 'updated'" :order="sortOrder" />
              </th>
              <th class="default-col">默认</th>
              <th class="action-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in sortedResumes" :key="item.id" @click="openDetail(item.id)">
              <td>
                <div class="file-cell">
                  <div class="file-name">{{ item.filename }}</div>
                  <div class="file-subtitle">{{ getResumeSubtitle(item) }}</div>
                </div>
              </td>
              <td>
                <span class="status-badge" :class="getStatusClass(item.summary_status)">
                  {{ getStatusText(item.summary_status) }}
                </span>
              </td>
              <td>
                <div v-if="isParsed(item)" class="progress-cell">
                  <div class="progress-track">
                    <div class="progress-fill" :style="{ width: `${getCompleteness(item)}%` }"></div>
                  </div>
                  <span>{{ getCompleteness(item) }}%</span>
                </div>
                <span v-else class="muted-text">—</span>
              </td>
              <td>
                <div v-if="getMatchScore(item) !== null" class="match-cell">
                  <span>{{ getMatchScore(item) }}</span>
                  <small>{{ getMatchJob(item) }}</small>
                </div>
                <span v-else class="muted-text">—</span>
              </td>
              <td class="muted-text">{{ formatFileSize(item.file_size) }}</td>
              <td class="muted-text">{{ formatDateTime(item.updated_at || item.created_at) }}</td>
              <td class="default-col">
                <span v-if="isDefaultResume(item)" class="default-badge">默认</span>
                <button v-else class="default-action" type="button" @click.stop="setDefaultResume(item.id)">
                  设为默认
                </button>
              </td>
              <td class="action-col">
                <div class="row-actions" @click.stop>
                  <button
                    class="text-action"
                    type="button"
                    :disabled="isExtracting(item) || retryingId === item.id"
                    @click="handleRetryExtract(item)"
                  >
                    重新分析
                  </button>
                  <a-popconfirm
                    title="确认删除这份简历吗？"
                    ok-text="删除"
                    cancel-text="取消"
                    @confirm="handleDelete(item.id)"
                  >
                    <button class="text-action danger" type="button">删除</button>
                  </a-popconfirm>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message, Upload } from 'ant-design-vue'
import { FileUp, RefreshCw } from 'lucide-vue-next'

import HeaderComponent from '@/components/HeaderComponent.vue'
import { resumeApi } from '@/apis/resume_api'

const MAX_UPLOAD_SIZE = 20 * 1024 * 1024
const DEFAULT_RESUME_KEY = 'ai-interview-default-resume-id'
const POLL_INTERVAL = 2000

const router = useRouter()

const loading = ref(false)
const uploading = ref(false)
const retryingId = ref(null)
const resumes = ref([])
const sortKey = ref('updated')
const sortOrder = ref('desc')
const defaultResumeId = ref(null)
let pollTimer = null

const SortIcon = defineComponent({
  name: 'SortIcon',
  props: {
    active: {
      type: Boolean,
      default: false,
    },
    order: {
      type: String,
      default: 'desc',
    },
  },
  setup(props) {
    return () =>
      h('span', { class: ['sort-icon', { active: props.active }] }, props.active && props.order === 'asc' ? '↑' : '↓')
  },
})

const resumeSummaryText = computed(() => {
  const count = resumes.value.length
  const defaultResume = defaultResumeId.value
    ? resumes.value.find((item) => item.id === defaultResumeId.value)
    : resumes.value[0]
  const defaultText = defaultResume?.filename || '暂无'
  return `${count} 份 · 默认用于面试：${defaultText}`
})

const sortedResumes = computed(() => {
  const direction = sortOrder.value === 'asc' ? 1 : -1
  return [...resumes.value].sort((left, right) => {
    const leftValue = getSortValue(left, sortKey.value)
    const rightValue = getSortValue(right, sortKey.value)

    if (leftValue === rightValue) {
      return Number(right.id || 0) - Number(left.id || 0)
    }

    return leftValue > rightValue ? direction : -direction
  })
})

const hasExtractingResume = computed(() => resumes.value.some((item) => isExtracting(item)))

const loadDefaultResume = () => {
  const storedValue = window.localStorage.getItem(DEFAULT_RESUME_KEY)
  const parsedValue = Number(storedValue)
  defaultResumeId.value = Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : null
}

const persistDefaultResume = () => {
  if (defaultResumeId.value) {
    window.localStorage.setItem(DEFAULT_RESUME_KEY, String(defaultResumeId.value))
  } else {
    window.localStorage.removeItem(DEFAULT_RESUME_KEY)
  }
}

const syncDefaultResume = () => {
  if (!resumes.value.length) {
    defaultResumeId.value = null
    persistDefaultResume()
    return
  }

  const exists = resumes.value.some((item) => item.id === defaultResumeId.value)
  if (!exists) {
    defaultResumeId.value = resumes.value[0].id
    persistDefaultResume()
  }
}

const loadResumes = async () => {
  loading.value = true
  try {
    const data = await resumeApi.getMyResumes()
    resumes.value = data?.resumes || []
    syncDefaultResume()
  } catch (error) {
    console.error('加载简历列表失败:', error)
    message.error(error.message || '加载简历列表失败')
  } finally {
    loading.value = false
  }
}

const silentRefreshResumes = async () => {
  try {
    const data = await resumeApi.getMyResumes()
    resumes.value = data?.resumes || []
    syncDefaultResume()
  } catch (error) {
    console.error('刷新简历解析状态失败:', error)
  }
}

const beforeUpload = (file) => {
  const fileName = file?.name || ''
  if (!fileName.toLowerCase().endsWith('.pdf')) {
    message.error('仅支持上传 PDF 简历')
    return Upload.LIST_IGNORE
  }

  if (file.size > MAX_UPLOAD_SIZE) {
    message.error('单个文件不能超过 20 MB')
    return Upload.LIST_IGNORE
  }

  return true
}

const handleUpload = async ({ file, onSuccess, onError }) => {
  try {
    uploading.value = true
    const result = await resumeApi.uploadResume(file)
    message.success('简历上传成功，正在分析中...')
    onSuccess?.(result)

    if (result?.resume?.id) {
      const uploadedResume = {
        ...result.resume,
        summary_status: result.resume.summary_status || 'pending',
      }
      resumes.value = [uploadedResume, ...resumes.value.filter((item) => item.id !== uploadedResume.id)]
      syncDefaultResume()
    } else {
      await loadResumes()
    }
  } catch (error) {
    console.error('上传简历失败:', error)
    message.error(error.message || '上传简历失败')
    onError?.(error)
  } finally {
    uploading.value = false
  }
}

const openDetail = (resumeId) => {
  router.push(`/resume/${resumeId}`)
}

const handleDelete = async (resumeId) => {
  try {
    await resumeApi.deleteResume(resumeId)
    resumes.value = resumes.value.filter((item) => item.id !== resumeId)
    syncDefaultResume()
    message.success('简历已删除')
  } catch (error) {
    console.error('删除简历失败:', error)
    message.error(error.message || '删除简历失败')
  }
}

const handleRetryExtract = async (item) => {
  if (!item?.id || retryingId.value) return
  try {
    retryingId.value = item.id
    await resumeApi.retryExtract(item.id)
    resumes.value = resumes.value.map((resume) =>
      resume.id === item.id ? { ...resume, summary_status: 'pending', summary_error: null } : resume,
    )
    message.success('已重新开始分析简历')
  } catch (error) {
    message.error(error?.response?.data?.detail || '重试失败，请稍后再试')
  } finally {
    retryingId.value = null
  }
}

const setDefaultResume = (resumeId) => {
  defaultResumeId.value = resumeId
  persistDefaultResume()
  message.success('已设为默认简历')
}

const isDefaultResume = (item) => item.id === defaultResumeId.value

const setSort = (key) => {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    return
  }

  sortKey.value = key
  sortOrder.value = 'desc'
}

const getSortValue = (item, key) => {
  if (key === 'completeness') {
    return isParsed(item) ? getCompleteness(item) : -1
  }
  if (key === 'match') {
    return getMatchScore(item) ?? -1
  }
  return Date.parse(item.updated_at || item.created_at || '') || 0
}

const isParsed = (item) => item.summary_status === 'completed'

const isExtracting = (item) => ['pending', 'processing', 'extracting'].includes(item.summary_status)

const getStatusText = (status) => {
  const map = {
    completed: '已解析',
    processing: '解析中',
    extracting: '解析中',
    pending: '解析中',
    failed: '解析失败',
  }
  return map[status] || '未解析'
}

const getStatusClass = (status) => {
  if (status === 'completed') return 'is-completed'
  if (status === 'failed') return 'is-failed'
  if (['pending', 'processing', 'extracting'].includes(status)) return 'is-processing'
  return ''
}

const getSummaryData = (item) => item.summary_json || item.structured_resume || {}

const normalizeSkills = (skills) => {
  if (Array.isArray(skills)) return skills
  if (!skills || typeof skills !== 'object') return []
  return [...(skills.technical || []), ...(skills.languages || []), ...(skills.certifications || [])]
}

const getResumeSubtitle = (item) => {
  if (isExtracting(item)) return '正在提取结构化信息…'
  if (item.summary_status === 'failed') return item.summary_error || '解析失败，可重新分析'

  const summary = getSummaryData(item)
  const job =
    item.detected_position ||
    summary.job_preference?.position ||
    summary.jobPreference?.position ||
    summary.basic_info?.intention ||
    '岗位未识别'
  const skills = normalizeSkills(summary.skills).slice(0, 4).join(' / ')
  return skills ? `${job} · ${skills}` : `${job} · 技能摘要待补充`
}

const getCompleteness = (item) => {
  const summary = getSummaryData(item)
  let score = 0
  let total = 0

  const basicInfo = summary.basic_info || summary.basicInfo || {}
  if (summary.name || basicInfo.name) score += 5
  if (summary.phone || basicInfo.phone) score += 3
  if (summary.email || basicInfo.email) score += 3
  if (basicInfo.location || summary.location) score += 3
  total += 14

  if (Array.isArray(summary.education) && summary.education.length) score += 15
  total += 15

  if (
    (Array.isArray(summary.work) && summary.work.length) ||
    (Array.isArray(summary.work_experience) && summary.work_experience.length)
  ) {
    score += 20
  }
  total += 20

  if (Array.isArray(summary.projects) && summary.projects.length) score += 20
  total += 20

  if (normalizeSkills(summary.skills).length) score += 10
  total += 10

  if (Array.isArray(summary.awards) && summary.awards.length) score += 5
  if (Array.isArray(summary.training) && summary.training.length) score += 5
  if (summary.self_evaluation || summary.selfEvaluation) score += 5
  total += 15

  return Math.min(100, Math.round((score / total) * 100))
}

const getMatchScore = (item) => {
  if (item.match_status !== 'completed' || !item.match_result) return null
  const score = Number(item.match_result.overall_score)
  return Number.isFinite(score) ? Math.round(score) : null
}

const getMatchJob = (item) => {
  return item.matched_job_title || item.detected_position || item.match_result?.job_title || '目标岗位'
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

const stopPolling = () => {
  if (pollTimer) {
    window.clearTimeout(pollTimer)
    pollTimer = null
  }
}

const schedulePolling = () => {
  stopPolling()
  if (!hasExtractingResume.value) return

  pollTimer = window.setTimeout(async () => {
    await silentRefreshResumes()
    schedulePolling()
  }, POLL_INTERVAL)
}

watch(hasExtractingResume, schedulePolling)

onMounted(() => {
  loadDefaultResume()
  loadResumes()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped lang="less">
.resume-page {
  min-height: 100%;
  background: var(--gray-0);
  color: var(--gray-1000);
  font-family: Archivo, 'Noto Sans SC', sans-serif;
}

.resume-content {
  padding: 24px 32px;
  position: relative;
  min-height: calc(100vh - 140px);
}

.upload-band-inner {
  min-height: 92px;
  box-sizing: border-box;
  border: 1px dashed var(--gray-200);
  background: var(--gray-10);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 26px;
  cursor: pointer;
  text-align: left;
}

.upload-band-copy {
  min-width: 0;
}

:deep(.resume-upload-band.ant-upload-wrapper) {
  display: block;
}

:deep(.resume-upload-band .ant-upload-drag) {
  border: 0;
  border-radius: 0;
  background: transparent;
}

:deep(.resume-upload-band .ant-upload-drag .ant-upload) {
  padding: 0;
}

:deep(.resume-upload-band .ant-upload-drag-container) {
  display: block;
  width: 100%;
  text-align: left !important;
}

.upload-band-title {
  font-size: 14px;
  line-height: 1.4;
  font-weight: 700;
  color: var(--gray-1000);
}

.upload-band-desc {
  margin-top: 3px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--gray-500);
}

.select-file-btn {
  flex: 0 0 auto;
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-700);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.select-file-btn:disabled {
  cursor: not-allowed;
  color: var(--gray-400);
  background: var(--gray-50);
}

@media (max-width: 640px) {
  .upload-band-inner {
    align-items: flex-start;
    flex-direction: column;
    padding: 14px 16px;
  }
}

.resume-table-wrap {
  margin-top: 26px;
  border-top: 2px solid var(--gray-1000);
  overflow-x: auto;
}

.resume-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.resume-table th {
  height: 38px;
  padding: 9px 14px;
  border-bottom: 1px solid var(--gray-200);
  color: var(--gray-500);
  font-size: 11px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-align: left;
  white-space: nowrap;
}

.resume-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--gray-100);
  color: var(--gray-1000);
  font-size: 13px;
  vertical-align: middle;
}

.resume-table tbody tr {
  cursor: pointer;
}

.resume-table tbody tr:hover {
  background: var(--gray-10);
}

.sortable {
  cursor: pointer;
  user-select: none;

  span {
    vertical-align: middle;
  }
}

.sort-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  margin-left: 6px;
  color: var(--gray-400);
  font-size: 11px;
  letter-spacing: 0;

  &.active {
    color: var(--main-800);
  }
}

.status-col {
  width: 110px;
}

.progress-col {
  width: 140px;
}

.match-col {
  width: 170px;
}

.size-col {
  width: 90px;
}

.time-col {
  width: 170px;
}

.default-col {
  width: 110px;
  text-align: right !important;
}

.action-col {
  width: 150px;
  text-align: right !important;
}

.file-cell {
  min-width: 0;
}

.file-name {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-1000);
}

.file-subtitle {
  max-width: 520px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 3px;
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.45;
}

.status-badge,
.default-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--gray-200);
  background: transparent;
  color: var(--gray-600);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.status-badge.is-completed,
.default-badge {
  background: var(--gray-100);
  color: var(--gray-1000);
}

.status-badge.is-processing {
  border-color: var(--main-600);
  color: var(--main-800);
}

.status-badge.is-failed {
  color: var(--gray-700);
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;

  span {
    flex: 0 0 36px;
    color: var(--gray-600);
    font-size: 12px;
  }
}

.progress-track {
  flex: 1;
  height: 6px;
  min-width: 70px;
  background: var(--gray-100);
}

.progress-fill {
  height: 6px;
  background: var(--main-600);
}

.match-cell {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;

  span {
    color: var(--gray-1000);
    font-size: 16px;
    font-weight: 800;
  }

  small {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--gray-500);
    font-size: 12px;
  }
}

.muted-text {
  color: var(--gray-600);
}

.default-action {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--gray-500);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.default-action:hover {
  color: var(--main-800);
}

.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  white-space: nowrap;
}

.text-action {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--gray-600);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.text-action:hover {
  color: var(--main-800);
}

.text-action:disabled {
  color: var(--gray-400);
  cursor: not-allowed;
}

.text-action.danger {
  color: var(--gray-700);
}

.text-action.danger:hover {
  color: var(--color-error-700);
}

.state-wrapper {
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
}

</style>
