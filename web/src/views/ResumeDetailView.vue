<template>
  <div class="resume-detail-page">
    <HeaderComponent
      :title="resume?.filename || '简历详情'"
      description="左侧展示提取出的关键信息，右侧展示原始解析结果。"
      :loading="loading"
    >
      <template #left>
        <a-button @click="goBack">
          <ArrowLeft :size="14" />
          返回列表
        </a-button>
      </template>
      <template #actions>
        <a-button :loading="loading" @click="loadResumeDetail">
          <RefreshCw :size="14" />
          刷新
        </a-button>
        <a-popconfirm
          title="确认删除这份简历吗？"
          ok-text="删除"
          cancel-text="取消"
          @confirm="handleDelete"
        >
          <a-button danger :loading="deleting">
            <Trash2 :size="14" />
            删除
          </a-button>
        </a-popconfirm>
      </template>
    </HeaderComponent>

    <div class="resume-detail-content">
      <div v-if="loading" class="state-wrapper">
        <a-spin />
      </div>

      <template v-else-if="resume">
        <div class="detail-grid">
          <div class="summary-panel">
            <div class="summary-hero">
              <div class="hero-name">{{ summary.name }}</div>
              <div class="hero-contact" v-if="summary.phone || summary.email">
                <div v-if="summary.phone" class="contact-item">
                  <Phone :size="14" />
                  <span>{{ summary.phone }}</span>
                </div>
                <div v-if="summary.email" class="contact-item">
                  <Mail :size="14" />
                  <span>{{ summary.email }}</span>
                </div>
              </div>
            </div>

            <div class="summary-body">
              <div class="summary-main">
                <section v-if="basicInfoEntries.length" class="summary-section">
                  <div class="section-title">基本信息</div>
                  <div class="basic-info-grid">
                    <div v-for="item in basicInfoEntries" :key="item.key" class="basic-info-item">
                      <div class="basic-info-label">{{ item.label }}</div>
                      <div class="basic-info-value">{{ item.value }}</div>
                    </div>
                  </div>
                </section>

                <section v-if="summary.education.length" class="summary-section">
                  <div class="section-title">教育经历</div>
                  <div
                    v-for="(item, index) in summary.education"
                    :key="`education-${index}`"
                    class="timeline-item"
                  >
                    <div class="timeline-head">
                      <div class="timeline-title">{{ item.title }}</div>
                      <div v-if="item.date" class="timeline-date">
                        <CalendarDays :size="14" />
                        <span>{{ item.date }}</span>
                      </div>
                    </div>
                    <div v-if="item.subtitle" class="timeline-subtitle">{{ item.subtitle }}</div>
                    <div v-if="item.details.length" class="timeline-details">
                      <p v-for="(detail, detailIndex) in item.details" :key="detailIndex">{{ detail }}</p>
                    </div>
                  </div>
                </section>

                <section v-if="summary.work.length" class="summary-section">
                  <div class="section-title">工作经历</div>
                  <div
                    v-for="(item, index) in summary.work"
                    :key="`work-${index}`"
                    class="timeline-item"
                  >
                    <div class="timeline-head">
                      <div class="timeline-title">{{ item.title }}</div>
                      <div v-if="item.date" class="timeline-date">
                        <CalendarDays :size="14" />
                        <span>{{ item.date }}</span>
                      </div>
                    </div>
                    <div v-if="item.subtitle" class="timeline-subtitle">{{ item.subtitle }}</div>
                    <div v-if="item.details.length" class="timeline-details">
                      <p v-for="(detail, detailIndex) in item.details" :key="detailIndex">{{ detail }}</p>
                    </div>
                  </div>
                </section>

                <section v-if="summary.projects.length" class="summary-section">
                  <div class="section-title">项目经历</div>
                  <div
                    v-for="(item, index) in summary.projects"
                    :key="`project-${index}`"
                    class="timeline-item"
                  >
                    <div class="timeline-head">
                      <div class="timeline-title">{{ item.title }}</div>
                      <div v-if="item.date" class="timeline-date">
                        <CalendarDays :size="14" />
                        <span>{{ item.date }}</span>
                      </div>
                    </div>
                    <div v-if="item.subtitle" class="timeline-subtitle">{{ item.subtitle }}</div>
                    <div v-if="item.details.length" class="timeline-details">
                      <p v-for="(detail, detailIndex) in item.details" :key="detailIndex">{{ detail }}</p>
                    </div>
                  </div>
                </section>

                <section
                  v-if="!hasStructuredContent"
                  class="summary-section empty-summary"
                >
                  <div class="section-title">关键信息</div>
                  <a-empty description="暂未从当前简历中提取到结构化经历信息" />
                </section>
              </div>

              <div class="summary-side">
                <section v-if="summary.skills.length" class="summary-section">
                  <div class="section-title">技能</div>
                  <div class="skills-wrap">
                    <a-tag v-for="skill in summary.skills" :key="skill" class="skill-tag">
                      {{ skill }}
                    </a-tag>
                  </div>
                </section>

                <section v-if="summary.awards.length" class="summary-section">
                  <div class="section-title">获奖情况</div>
                  <div class="awards-wrap">
                    <div v-for="(award, index) in summary.awards" :key="`award-${index}`" class="award-card">
                      {{ award }}
                    </div>
                  </div>
                </section>

                <section class="summary-section">
                  <div class="section-title">基础信息</div>
                  <a-descriptions :column="1" size="small">
                    <a-descriptions-item
                      v-for="item in basicInfoEntries"
                      :key="item.key"
                      :label="item.label"
                    >
                      {{ item.value }}
                    </a-descriptions-item>
                    <a-descriptions-item label="文件名">{{ resume.filename }}</a-descriptions-item>
                    <a-descriptions-item label="文件大小">{{ formatFileSize(resume.file_size) }}</a-descriptions-item>
                    <a-descriptions-item label="解析引擎">{{ resume.parser_name }}</a-descriptions-item>
                    <a-descriptions-item label="更新时间">
                      {{ formatDateTime(resume.updated_at || resume.created_at) }}
                    </a-descriptions-item>
                  </a-descriptions>
                </section>
              </div>
            </div>
          </div>

          <a-card class="panel-card preview-card" title="解析结果 Markdown" :bordered="false">
            <div v-if="resume.markdown_content" class="markdown-panel">
              <MdPreview
                :editorId="`resume-preview-${resume.id}`"
                :modelValue="resume.markdown_content"
                previewTheme="default"
              />
            </div>
            <a-empty v-else description="当前简历暂无解析内容" />
          </a-card>
        </div>
      </template>

      <div v-else class="state-wrapper">
        <a-empty description="未找到该简历" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'
import { ArrowLeft, CalendarDays, Mail, Phone, RefreshCw, Trash2 } from 'lucide-vue-next'

import HeaderComponent from '@/components/HeaderComponent.vue'
import { resumeApi } from '@/apis/resume_api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const deleting = ref(false)
const resume = ref(null)

const summary = computed(() => {
  const data = resume.value?.structured_resume || {}

  return {
    name: data.name || resume.value?.filename?.replace(/\.pdf$/i, '') || '简历',
    phone: data.phone || '',
    email: data.email || '',
    basicInfo: data.basic_info || {},
    education: Array.isArray(data.education) ? data.education : [],
    work: Array.isArray(data.work) ? data.work : [],
    projects: Array.isArray(data.projects) ? data.projects : [],
    skills: Array.isArray(data.skills) ? data.skills : [],
    awards: Array.isArray(data.awards) ? data.awards : []
  }
})

const basicInfoEntries = computed(() => {
  const mapping = [
    { key: 'school', label: '学校' },
    { key: 'major', label: '专业' },
    { key: 'degree', label: '学历' },
    { key: 'grade', label: '年级' },
    { key: 'location', label: '所在地' },
    { key: 'intention', label: '求职意向' },
    { key: 'github', label: 'GitHub' }
  ]

  return mapping
    .map((item) => ({
      ...item,
      value: summary.value.basicInfo?.[item.key] || ''
    }))
    .filter((item) => item.value)
})

const hasStructuredContent = computed(() => {
  return Boolean(
    basicInfoEntries.value.length ||
      summary.value.education.length ||
      summary.value.work.length ||
      summary.value.projects.length ||
      summary.value.skills.length ||
      summary.value.awards.length
  )
})

const loadResumeDetail = async () => {
  loading.value = true
  try {
    const data = await resumeApi.getResumeDetail(route.params.resume_id)
    resume.value = data?.resume || null
  } catch (error) {
    console.error('加载简历详情失败:', error)
    message.error(error.message || '加载简历详情失败')
    resume.value = null
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/resume')
}

const handleDelete = async () => {
  if (!resume.value?.id) {
    return
  }

  try {
    deleting.value = true
    await resumeApi.deleteResume(resume.value.id)
    message.success('简历已删除')
    router.push('/resume')
  } catch (error) {
    console.error('删除简历失败:', error)
    message.error(error.message || '删除简历失败')
  } finally {
    deleting.value = false
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
  loadResumeDetail()
})
</script>

<style scoped lang="less">
.resume-detail-page {
  min-height: 100%;
  background: var(--gray-25);
}

.resume-detail-content {
  padding: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(520px, 1.15fr) minmax(420px, 0.85fr);
  gap: 16px;
  align-items: start;
}

.summary-panel,
.panel-card {
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  background: var(--gray-0);
  overflow: hidden;
  box-shadow: none;
}

.summary-hero {
  padding: 24px 28px 20px;
  background: var(--main-color);
  color: #fff;
}

.hero-name {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
}

.hero-contact {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.contact-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  opacity: 0.98;
}

.summary-body {
  padding: 18px 20px 20px;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) 240px;
  gap: 20px;
  align-items: start;
}

.summary-section {
  & + .summary-section {
    margin-top: 22px;
  }
}

.section-title {
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(47, 94, 234, 0.2);
  color: var(--main-color);
  font-size: 16px;
  font-weight: 700;
}

.timeline-item {
  & + .timeline-item {
    margin-top: 18px;
  }
}

.basic-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.basic-info-item {
  padding: 12px 14px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--gray-0);
}

.basic-info-label {
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.4;
}

.basic-info-value {
  margin-top: 4px;
  color: var(--gray-950);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.6;
  word-break: break-word;
}

.timeline-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.timeline-title {
  color: var(--gray-950);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
}

.timeline-date {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--gray-500);
  font-size: 13px;
}

.timeline-subtitle {
  margin-top: 4px;
  color: var(--main-color);
  font-size: 14px;
  font-weight: 500;
}

.timeline-details {
  margin-top: 10px;
  color: var(--gray-800);
  font-size: 14px;
  line-height: 1.8;

  p {
    margin: 0;

    & + p {
      margin-top: 6px;
    }
  }
}

.skills-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 8px;
}

.skill-tag {
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--main-color);
  border-color: rgba(47, 94, 234, 0.28);
  background: rgba(47, 94, 234, 0.03);
}

.awards-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.award-card {
  padding: 12px 14px;
  border: 1px solid var(--gray-200);
  border-left: 4px solid var(--main-color);
  border-radius: 14px;
  color: var(--gray-900);
  line-height: 1.7;
  background: var(--gray-0);
}

.empty-summary {
  :deep(.ant-empty) {
    margin: 24px 0 8px;
  }
}

.panel-card {
  :deep(.ant-card-head) {
    border-bottom: 1px solid var(--gray-200);
    min-height: 56px;
  }

  :deep(.ant-card-body) {
    padding: 16px;
  }
}

.preview-card {
  min-height: calc(100vh - 180px);
}

.markdown-panel {
  min-height: calc(100vh - 260px);

  :deep(.md-editor) {
    background: transparent;
  }

  :deep(.md-editor-preview-wrapper) {
    padding: 0;
  }
}

.state-wrapper {
  min-height: calc(100vh - 220px);
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 1360px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .summary-body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .basic-info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
