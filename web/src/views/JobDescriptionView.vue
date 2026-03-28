<template>
  <div class="job-page">
    <HeaderComponent
      title="职位描述管理"
      description="创建和管理职位描述（JD），为简历匹配提供依据。"
      :loading="loading"
    >
      <template #actions>
        <a-button type="primary" @click="openCreateModal">
          <Plus :size="14" />
          新建职位
        </a-button>
        <a-button :loading="loading" @click="loadJobs">
          <RefreshCw :size="14" />
          刷新
        </a-button>
      </template>
    </HeaderComponent>

    <div class="job-content">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <a-select
          v-model:value="filterStatus"
          placeholder="按状态筛选"
          allow-clear
          style="width: 140px"
          @change="handleFilterChange"
        >
          <a-select-option value="active">进行中</a-select-option>
          <a-select-option value="closed">已关闭</a-select-option>
          <a-select-option value="draft">草稿</a-select-option>
        </a-select>
        <span class="total-count">共 {{ total }} 个职位</span>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="state-wrapper">
        <a-spin />
      </div>

      <!-- 空状态 -->
      <div v-else-if="jobs.length === 0" class="empty-wrapper">
        <a-empty description="还没有创建职位描述">
          <a-button type="primary" @click="openCreateModal">
            <Plus :size="14" />
            创建第一个职位
          </a-button>
        </a-empty>
      </div>

      <!-- 职位列表 -->
      <div v-else class="job-list">
        <a-card
          v-for="item in jobs"
          :key="item.id"
          class="job-card"
          :bordered="false"
        >
          <div class="card-header">
            <div class="card-title">
              <Briefcase :size="18" />
              <span class="job-title">{{ item.title }}</span>
            </div>
            <a-tag :color="getStatusColor(item.status)">{{ getStatusText(item.status) }}</a-tag>
          </div>

          <div class="card-meta">
            <div v-if="item.department" class="meta-item">
              <Building2 :size="14" />
              {{ item.department }}
            </div>
            <div v-if="item.salary_range" class="meta-item">
              <DollarSign :size="14" />
              {{ item.salary_range }}
            </div>
            <div v-if="item.required_skills?.length" class="meta-item skills-count">
              <Tags :size="14" />
              {{ item.required_skills.length }} 项技能要求
            </div>
          </div>

          <div v-if="item.required_skills?.length" class="skill-preview">
            <a-tag v-for="skill in item.required_skills.slice(0, 4)" :key="skill" size="small">
              {{ skill }}
            </a-tag>
            <span v-if="item.required_skills.length > 4" class="more-skills">
              +{{ item.required_skills.length - 4 }}
            </span>
          </div>

          <div class="card-footer">
            <span class="update-time">更新于 {{ formatDateTime(item.updated_at || item.created_at) }}</span>
            <div class="card-actions">
              <a-button type="text" size="small" @click.stop="openMatchModal(item)">
                <Target :size="14" />
                匹配
              </a-button>
              <a-button type="text" size="small" @click.stop="openEditModal(item)">
                <Pencil :size="14" />
                编辑
              </a-button>
              <a-popconfirm
                title="确认删除这个职位吗？"
                ok-text="删除"
                cancel-text="取消"
                @confirm="handleDelete(item.id)"
              >
                <a-button type="text" danger size="small" @click.stop>
                  <Trash2 :size="14" />
                  删除
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 分页 -->
      <div v-if="total > limit" class="pagination-wrapper">
        <a-pagination
          v-model:current="page"
          :total="total"
          :page-size="limit"
          show-quick-jumper
          @change="handlePageChange"
        />
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="isEditing ? '编辑职位' : '新建职位'"
      width="600px"
      :footer="null"
      @cancel="closeModal"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
        @finish="handleSubmit"
      >
        <a-form-item label="职位名称" name="title">
          <a-input v-model:value="formData.title" placeholder="如：Java后端开发工程师" />
        </a-form-item>

        <a-form-item label="部门" name="department">
          <a-input v-model:value="formData.department" placeholder="如：技术部" />
        </a-form-item>

        <a-form-item label="薪资范围" name="salary_range">
          <a-input v-model:value="formData.salary_range" placeholder="如：20k-35k" />
        </a-form-item>

        <a-form-item label="最低工作年限" name="min_experience_years">
          <a-input-number
            v-model:value="formData.min_experience_years"
            :min="0"
            :max="50"
            placeholder="如：3"
            style="width: 100%"
          />
        </a-form-item>

        <a-form-item label="学历要求" name="education_level">
          <a-select v-model:value="formData.education_level" placeholder="选择学历要求" allow-clear>
            <a-select-option value="大专">大专</a-select-option>
            <a-select-option value="本科">本科</a-select-option>
            <a-select-option value="硕士">硕士</a-select-option>
            <a-select-option value="博士">博士</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="必备技能" name="required_skills">
          <a-select
            v-model:value="formData.required_skills"
            mode="tags"
            placeholder="输入技能后按回车添加"
            :token-separators="[',', '，']"
          />
        </a-form-item>

        <a-form-item label="加分技能" name="preferred_skills">
          <a-select
            v-model:value="formData.preferred_skills"
            mode="tags"
            placeholder="输入技能后按回车添加"
            :token-separators="[',', '，']"
          />
        </a-form-item>

        <a-form-item label="岗位职责" name="description">
          <a-textarea
            v-model:value="formData.description"
            placeholder="描述岗位职责和工作内容"
            :rows="3"
          />
        </a-form-item>

        <a-form-item label="任职要求" name="requirements">
          <a-textarea
            v-model:value="formData.requirements"
            placeholder="描述任职要求"
            :rows="3"
          />
        </a-form-item>

        <a-form-item v-if="isEditing" label="状态" name="status">
          <a-select v-model:value="formData.status">
            <a-select-option value="draft">草稿</a-select-option>
            <a-select-option value="active">进行中</a-select-option>
            <a-select-option value="closed">已关闭</a-select-option>
          </a-select>
        </a-form-item>

        <div class="form-footer">
          <a-button @click="closeModal">取消</a-button>
          <a-button type="primary" html-type="submit" :loading="submitting">
            {{ isEditing ? '保存' : '创建' }}
          </a-button>
        </div>
      </a-form>
    </a-modal>

    <!-- 匹配弹窗 -->
    <a-modal
      v-model:open="matchModalVisible"
      title="简历-JD匹配分析"
      width="900px"
      :footer="null"
      @cancel="closeMatchModal"
    >
      <div v-if="selectedJob" class="match-modal-content">
        <div class="match-job-info">
          <span class="match-job-title">{{ selectedJob.title }}</span>
          <span class="match-job-dept">{{ selectedJob.department }}</span>
        </div>

        <!-- 简历选择 -->
        <div class="resume-select-section">
          <div class="section-label">选择简历</div>
          <a-select
            v-model:value="selectedResumeId"
            placeholder="请选择要匹配的简历"
            style="width: 100%"
            @change="handleResumeChange"
          >
            <a-select-option
              v-for="resume in resumes"
              :key="resume.id"
              :value="resume.id"
              :disabled="!isResumeReady(resume)"
            >
              <div class="resume-option">
                <FileText :size="14" />
                <span>{{ resume.filename }}</span>
                <span
                  class="resume-status"
                  :class="{
                    'resume-status-ready': isResumeReady(resume),
                    'resume-status-pending': resume.summary_status === 'pending',
                    'resume-status-failed': resume.summary_status === 'failed',
                  }"
                >
                  {{ getResumeStatusText(resume.summary_status) }}
                </span>
              </div>
            </a-select-option>
          </a-select>
        </div>

        <!-- 匹配按钮 -->
        <div class="match-action">
          <a-button
            type="primary"
            :loading="matching"
            :disabled="!selectedResumeId || !selectedResumeSummary"
            @click="handleMatch"
          >
            <Target :size="14" />
            开始匹配
          </a-button>
        </div>

        <!-- 匹配结果 -->
        <div v-if="matchResult" class="match-result-wrapper">
          <MatchResultPanel :match-result="matchResult" />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  Plus,
  RefreshCw,
  Briefcase,
  Building2,
  DollarSign,
  Tags,
  Pencil,
  Trash2,
  Target,
  FileText,
} from 'lucide-vue-next'

import HeaderComponent from '@/components/HeaderComponent.vue'
import MatchResultPanel from '@/components/MatchResultPanel.vue'
import { jobApi } from '@/apis/job_api'
import { resumeApi } from '@/apis/resume_api'

const loading = ref(false)
const submitting = ref(false)
const jobs = ref([])
const total = ref(0)
const page = ref(1)
const limit = ref(20)
const filterStatus = ref(null)

const modalVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const formData = ref({
  title: '',
  department: '',
  salary_range: '',
  min_experience_years: null,
  education_level: undefined,
  required_skills: [],
  preferred_skills: [],
  description: '',
  requirements: '',
  status: 'active',
})

const formRules = {
  title: [{ required: true, message: '请输入职位名称', trigger: 'blur' }],
}

const matchModalVisible = ref(false)
const selectedJob = ref(null)
const matching = ref(false)
const resumes = ref([])
const selectedResumeId = ref(null)
const selectedResumeSummary = ref(null)
const matchResult = ref(null)

const loadJobs = async () => {
  loading.value = true
  try {
    const params = {
      status: filterStatus.value,
      skip: (page.value - 1) * limit.value,
      limit: limit.value,
    }
    const data = await jobApi.getJobs(params)
    jobs.value = data?.jobs || []
    total.value = data?.total || 0
  } catch (error) {
    console.error('加载职位列表失败:', error)
    message.error(error.message || '加载职位列表失败')
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  page.value = 1
  loadJobs()
}

const handlePageChange = (newPage) => {
  page.value = newPage
  loadJobs()
}

const loadResumes = async () => {
  try {
    const data = await resumeApi.getMyResumes()
    resumes.value = data?.resumes || []
  } catch (error) {
    console.error('加载简历列表失败:', error)
  }
}

const openCreateModal = () => {
  isEditing.value = false
  editingId.value = null
  formData.value = {
    title: '',
    department: '',
    salary_range: '',
    min_experience_years: null,
    education_level: undefined,
    required_skills: [],
    preferred_skills: [],
    description: '',
    requirements: '',
    status: 'active',
  }
  modalVisible.value = true
}

const openEditModal = (job) => {
  isEditing.value = true
  editingId.value = job.id
  formData.value = {
    title: job.title || '',
    department: job.department || '',
    salary_range: job.salary_range || '',
    min_experience_years: job.min_experience_years || null,
    education_level: job.education_level || undefined,
    required_skills: job.required_skills || [],
    preferred_skills: job.preferred_skills || [],
    description: job.description || '',
    requirements: job.requirements || '',
    status: job.status || 'active',
  }
  modalVisible.value = true
}

const closeModal = () => {
  modalVisible.value = false
  formRef.value?.resetFields()
}

const handleSubmit = async () => {
  submitting.value = true
  try {
    const submitData = { ...formData.value }
    if (submitData.min_experience_years === null) {
      delete submitData.min_experience_years
    }

    if (isEditing.value) {
      await jobApi.updateJob(editingId.value, submitData)
      message.success('职位已更新')
    } else {
      await jobApi.createJob(submitData)
      message.success('职位已创建')
    }
    closeModal()
    loadJobs()
  } catch (error) {
    console.error('提交失败:', error)
    message.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (jobId) => {
  try {
    await jobApi.deleteJob(jobId)
    jobs.value = jobs.value.filter((item) => item.id !== jobId)
    total.value--
    message.success('职位已删除')
  } catch (error) {
    console.error('删除失败:', error)
    message.error(error.message || '删除失败')
  }
}

const openMatchModal = async (job) => {
  selectedJob.value = job
  selectedResumeId.value = null
  selectedResumeSummary.value = null
  matchResult.value = null
  matchModalVisible.value = true
  await loadResumes()
}

const closeMatchModal = () => {
  matchModalVisible.value = false
  selectedJob.value = null
  selectedResumeId.value = null
  selectedResumeSummary.value = null
  matchResult.value = null
}

const isValidSummary = (obj) => {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return false
  
  // 至少需要包含一个有效字段
  const hasValidSkills = obj.skills && typeof obj.skills === 'object'
  const hasValidWork = obj.work_experience && Array.isArray(obj.work_experience) && obj.work_experience.length > 0
  const hasValidEducation = obj.education && Array.isArray(obj.education) && obj.education.length > 0
  const hasValidProjects = obj.projects && Array.isArray(obj.projects) && obj.projects.length > 0
  
  // obj.summary 可能是字符串摘要，不是结构化数据，移除此检查
  return hasValidSkills || hasValidWork || hasValidEducation || hasValidProjects
}



const handleResumeChange = async (resumeId) => {
  if (!resumeId) {
    selectedResumeSummary.value = null
    return
  }
  try {
    const data = await resumeApi.getResumeDetail(resumeId)
    const resume = data?.resume

    // 优先使用 summary_json
    if (isValidSummary(resume?.summary_json)) {
      selectedResumeSummary.value = resume.summary_json
      return
    }

    // 其次使用 structured_resume
    if (isValidSummary(resume?.structured_resume)) {
      selectedResumeSummary.value = resume.structured_resume
      return
    }

    // 两者都不可用，不 fallback 到完整 resume 对象
    selectedResumeSummary.value = null
    message.warning('该简历的结构化摘要尚未生成，请稍后再试或重新上传')
  } catch (error) {
    console.error('加载简历详情失败:', error)
    message.error('加载简历详情失败')
    selectedResumeSummary.value = null
  }
}

const handleMatch = async () => {
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  if (!selectedResumeSummary.value) {
    message.warning('该简历的结构化摘要尚未生成，请稍后再试或重新上传')
    return
  }

  matching.value = true
  matchResult.value = null
  try {
    message.loading({ content: '正在匹配...', key: 'match' })
    const data = await jobApi.matchResume(selectedJob.value.id, selectedResumeSummary.value)
    matchResult.value = data?.match_result
    if (matchResult.value) {
      message.success({ content: '匹配完成', key: 'match', duration: 2 })
    } else {
      message.error({ content: '匹配结果为空，请稍后重试', key: 'match' })
    }
  } catch (error) {
    console.error('匹配失败:', error)
    message.error({ content: error.message || '匹配失败', key: 'match' })
  } finally {
    matching.value = false
  }
}

const isResumeReady = (resume) => {
  return resume.summary_status === 'completed'
}

const getResumeStatusText = (status) => {
  const texts = {
    completed: '可匹配',
    pending: '等待提取',
    failed: '提取失败',
  }
  return texts[status] || status
}

const getStatusColor = (status) => {
  const colors = {
    active: 'green',
    closed: 'red',
    draft: 'orange',
  }
  return colors[status] || 'default'
}

const getStatusText = (status) => {
  const texts = {
    active: '进行中',
    closed: '已关闭',
    draft: '草稿',
  }
  return texts[status] || status
}

const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

onMounted(() => {
  loadJobs()
})
</script>

<style scoped lang="less">
.job-page {
  min-height: 100%;
  background: var(--gray-25);
}

.job-content {
  padding: 16px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.total-count {
  color: var(--gray-600);
  font-size: 13px;
}

.job-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.job-card {
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

.job-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 500;
}

.card-meta {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--gray-600);
  font-size: 13px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.skill-preview {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.more-skills {
  font-size: 12px;
  color: var(--gray-500);
}

.card-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--gray-150);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.update-time {
  color: var(--gray-500);
  font-size: 12px;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.state-wrapper,
.empty-wrapper {
  min-height: calc(100vh - 220px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--gray-150);
}

.match-modal-content {
  padding: 8px 0;
}

.match-job-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--gray-150);
}

.match-job-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-900);
}

.match-job-dept {
  font-size: 13px;
  color: var(--gray-500);
}

.resume-select-section {
  margin-top: 20px;
}

.section-label {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--gray-700);
}

.resume-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.resume-status {
  margin-left: auto;
  font-size: 12px;
}

.resume-status-ready {
  color: var(--green-600, #16a34a);
}

.resume-status-pending {
  color: var(--orange-500, #f59e0b);
}

.resume-status-failed {
  color: var(--red-500, #ef4444);
}

.match-action {
  margin-top: 16px;
}

.match-result-wrapper {
  margin-top: 20px;
}
</style>
