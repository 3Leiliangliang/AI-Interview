<template>
  <div class="resume-detail-page" @keydown="handleKeydown">
    <HeaderComponent
      :title="resume?.filename || '简历详情'"
      description="智能提取简历关键信息，全面展示个人背景与能力"
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
            <!-- Extracting animation overlay -->
            <ResumeExtractingAnimation
              v-if="extractStage === 'parsing' || extractStage === 'extracting'"
              :stage="extractStage"
              :stats="extractStats"
            />

            <!-- Extraction failed state -->
            <div v-else-if="extractStage === 'failed'" class="extract-failed-card">
              <div class="extract-failed__icon">
                <AlertCircle :size="32" />
              </div>
              <div class="extract-failed__title">简历分析失败</div>
              <div class="extract-failed__error" v-if="resume?.summary_error">
                {{ resume.summary_error }}
              </div>
              <div class="extract-failed__hint">请检查简历文件是否完整，或点击下方按钮重试</div>
              <a-button
                type="primary"
                :loading="retrying"
                @click="handleRetryExtract"
              >
                <RefreshCw :size="14" />
                重新分析
              </a-button>
            </div>

            <template v-else>
              <div class="summary-hero">
                <div class="hero-top slide-up">
                  <div class="hero-avatar">
                    <img v-if="summary.basicInfo?.photo_url && !photoLoadError" :src="summary.basicInfo.photo_url" alt="证件照" class="avatar-photo" @error="photoLoadError = true" />
                    <span v-else>{{ summary.name?.charAt(0) || '姓' }}</span>
                  </div>
                  <div class="hero-main">
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
                      <div v-if="summary.basicInfo?.location" class="contact-item">
                        <MapPin :size="14" />
                        <span>{{ summary.basicInfo.location }}</span>
                      </div>
                      <div v-if="summary.basicInfo?.github" class="contact-item">
                        <Github :size="14" />
                        <a :href="summary.basicInfo.github" target="_blank" class="hero-link">
                          {{ formatGithubUrl(summary.basicInfo.github) }}
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="highlightTags.length" class="hero-tags slide-up" style="--delay: 0.1s">
                  <a-tag v-for="tag in highlightTags" :key="tag.text" :color="tag.color" class="highlight-tag">
                    <component :is="tag.icon" :size="12" />
                    {{ tag.text }}
                  </a-tag>
                </div>
              </div>

              <div v-if="hasSummaryData" class="completeness-bar slide-up" style="--delay: 0.15s">
                <div class="completeness-header">
                  <span class="completeness-label">简历完整度</span>
                  <span class="completeness-score" :class="completenessClass">{{ completenessScore }}%</span>
                </div>
                <a-progress
                  :percent="completenessScore"
                  :show-info="false"
                  :stroke-color="completenessColor"
                  :trail-color="'rgba(30, 58, 95, 0.1)'"
                  size="small"
                />
                <div v-if="completenessTips.length" class="completeness-tips">
                  <span v-for="tip in completenessTips" :key="tip" class="tip-item">
                    <Plus :size="12" /> {{ tip }}
                  </span>
                </div>
              </div>

              <div class="summary-body">
                <div class="summary-main">
                  <section v-if="summary.education.length" class="summary-section slide-up" style="--delay: 0.2s">
                    <div class="section-title section-title--education">
                      <GraduationCap :size="16" />
                      教育经历
                    </div>
                    <div
                      v-for="(item, index) in summary.education"
                      :key="`education-${index}`"
                      class="timeline-item timeline-item--education"
                    >
                      <div class="timeline-head">
                        <div class="timeline-title">{{ item.school }}</div>
                        <div v-if="item.duration" class="timeline-date">
                          <CalendarDays :size="13" />
                          <span>{{ item.duration }}</span>
                        </div>
                      </div>
                      <div v-if="item.major || item.degree" class="timeline-subtitle">
                        {{ item.major }}{{ item.degree ? ` · ${item.degree}` : '' }}
                      </div>
                      <div v-if="item.gpa || item.ranking" class="timeline-tags">
                        <a-tag v-if="item.gpa" color="blue" class="info-tag">GPA: {{ item.gpa }}</a-tag>
                        <a-tag v-if="item.ranking" color="cyan" class="info-tag">{{ item.ranking }}</a-tag>
                      </div>
                    </div>
                  </section>

                  <section v-if="summary.work.length" class="summary-section slide-up" style="--delay: 0.25s">
                    <div class="section-title section-title--work">
                      <Briefcase :size="16" />
                      工作经历
                    </div>
                    <div
                      v-for="(item, index) in summary.work"
                      :key="`work-${index}`"
                      class="timeline-item timeline-item--work"
                    >
                      <div class="timeline-head">
                        <div class="timeline-title">{{ item.company }}</div>
                        <div v-if="item.duration" class="timeline-date">
                          <CalendarDays :size="13" />
                          <span>{{ item.duration }}</span>
                        </div>
                      </div>
                      <div v-if="item.position" class="timeline-subtitle">{{ item.position }}</div>
                      <div v-if="item.highlights?.length" class="timeline-details">
                        <p v-for="(h, hi) in item.highlights" :key="hi">
                          <span class="bullet">·</span> {{ h }}
                        </p>
                      </div>
                    </div>
                  </section>

                  <section v-if="summary.projects.length" class="summary-section slide-up" style="--delay: 0.3s">
                    <div class="section-title section-title--project">
                      <FolderGit :size="16" />
                      项目经历
                    </div>
                    <div
                      v-for="(item, index) in summary.projects"
                      :key="`project-${index}`"
                      class="timeline-item timeline-item--project"
                    >
                      <div class="timeline-head">
                        <div class="timeline-title">{{ item.name }}</div>
                        <div v-if="item.duration" class="timeline-date">
                          <CalendarDays :size="13" />
                          <span>{{ item.duration }}</span>
                        </div>
                      </div>
                      <div v-if="item.role" class="timeline-subtitle">{{ item.role }}</div>
                      <div v-if="item.tech_stack?.length" class="timeline-tags">
                        <a-tag v-for="tech in item.tech_stack" :key="tech" color="purple" class="info-tag">
                          {{ tech }}
                        </a-tag>
                      </div>
                      <div v-if="item.description" class="timeline-desc">{{ item.description }}</div>
                      <div v-if="item.results?.length" class="timeline-details">
                        <p v-for="(r, ri) in item.results" :key="ri">
                          <span class="bullet green">✓</span> {{ r }}
                        </p>
                      </div>
                    </div>
                  </section>

                  <section v-if="summary.awards.length" class="summary-section slide-up" style="--delay: 0.35s">
                    <div class="section-title">
                      <Award :size="16" />
                      获奖情况
                    </div>
                    <div class="awards-grid">
                      <div v-for="(award, index) in summary.awards" :key="`award-${index}`" class="award-card">
                        <Trophy :size="14" class="award-icon" />
                        {{ award }}
                      </div>
                    </div>
                  </section>

                  <section v-if="summary.training.length" class="summary-section slide-up" style="--delay: 0.4s">
                    <div class="section-title">
                      <BookOpen :size="16" />
                      培训经历
                    </div>
                    <div class="training-list">
                      <div v-for="(t, i) in summary.training" :key="i" class="training-item">
                        {{ t }}
                      </div>
                    </div>
                  </section>
                </div>

                <div class="summary-side">
                  <section v-if="summary.jobPreference" class="summary-section side-card slide-up" style="--delay: 0.2s">
                    <div class="section-title">
                      <Target :size="16" />
                      求职偏好
                    </div>
                    <div class="preference-list">
                      <div v-if="summary.jobPreference.job_intention" class="pref-item">
                        <span class="pref-label">意向岗位</span>
                        <span class="pref-value">{{ summary.jobPreference.job_intention }}</span>
                      </div>
                      <div v-if="summary.jobPreference.expected_salary" class="pref-item">
                        <span class="pref-label">期望薪资</span>
                        <span class="pref-value">{{ summary.jobPreference.expected_salary }}</span>
                      </div>
                      <div v-if="summary.jobPreference.desired_location" class="pref-item">
                        <span class="pref-label">期望地点</span>
                        <span class="pref-value">{{ summary.jobPreference.desired_location }}</span>
                      </div>
                    </div>
                  </section>

                  <section class="summary-section side-card slide-up" style="--delay: 0.25s">
                    <div class="section-title">
                      <Crosshair :size="16" />
                      岗位匹配
                    </div>
                    <template v-if="resume?.match_status === 'completed' && resume?.match_result">
                      <div class="match-panel__card--inline">
                        <div class="match-inline__score-ring">
                          <svg viewBox="0 0 36 36" class="match-ring-svg">
                            <path
                              class="match-ring-bg"
                              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                            />
                            <path
                              class="match-ring-fill"
                              :stroke-dasharray="`${resume.match_result.overall_score || 0}, 100`"
                              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                            />
                          </svg>
                          <span class="match-ring-text">{{ Math.round(resume.match_result.overall_score) }}</span>
                        </div>
                        <div class="match-inline__info">
                          <a-tag :color="matchLevelColor" class="match-level-tag">{{ matchLevelText }}</a-tag>
                          <div class="match-inline__job" v-if="resume.matched_job_title">{{ resume.matched_job_title }}</div>
                        </div>
                      </div>
                      <div class="match-actions-row">
                        <span class="match-detail-link" @click="showMatchDetail = true">查看匹配详情</span>
                        <a-button size="small" type="link" @click="handleChangeJob">
                          <RotateCcw :size="12" />
                          更换岗位
                        </a-button>
                      </div>
                    </template>
                    <template v-else-if="resume?.match_status === 'pending' || resume?.match_status === 'processing'">
                      <div class="match-loading">
                        <a-spin size="small" />
                        <span>正在匹配中...</span>
                      </div>
                    </template>
                    <template v-else>
                      <a-button type="primary" ghost block @click="openMatchModal">
                        <Crosshair :size="14" />
                        匹配岗位
                      </a-button>
                    </template>
                  </section>

                  <section v-if="skillTagsFlat.length" class="summary-section side-card slide-up" style="--delay: 0.3s">
                    <div class="section-title">
                      <Wrench :size="16" />
                      技能标签
                    </div>
                    <div class="skill-cloud">
                      <span
                        v-for="skill in skillCloudItems"
                        :key="skill.name"
                        class="skill-cloud__tag"
                        :class="`skill-cloud__tag--${skill.category}`"
                        :style="{ fontSize: skill.size + 'px' }"
                      >
                        {{ skill.name }}
                      </span>
                    </div>
                  </section>

                  <section v-if="summary.selfEvaluation" class="summary-section side-card slide-up" style="--delay: 0.35s">
                    <div class="section-title">
                      <MessageSquare :size="16" />
                      自我评价
                    </div>
                    <div class="self-eval-text">{{ summary.selfEvaluation }}</div>
                  </section>

                  <section class="summary-section side-card meta-section slide-up" style="--delay: 0.4s">
                    <div class="section-title">
                      <FileText :size="16" />
                      简历信息
                    </div>
                    <a-descriptions :column="1" size="small" class="meta-descriptions">
                      <a-descriptions-item label="文件名">{{ resume.filename }}</a-descriptions-item>
                      <a-descriptions-item label="文件大小">{{ formatFileSize(resume.file_size) }}</a-descriptions-item>
                      <a-descriptions-item label="解析状态">
                        <a-tag :color="resume.summary_status === 'completed' ? 'success' : 'warning'" size="small">
                          {{ statusText }}
                        </a-tag>
                      </a-descriptions-item>
                      <a-descriptions-item label="更新时间">
                        {{ formatDateTime(resume.updated_at || resume.created_at) }}
                      </a-descriptions-item>
                    </a-descriptions>
                  </section>
                </div>
              </div>

              <div v-if="!hasSummaryData && extractStage !== 'parsing' && extractStage !== 'extracting'" class="empty-state">
                <a-empty description="暂未从当前简历中提取到结构化信息">
                  <template #image>
                    <FileSearch :size="48" class="empty-icon" />
                  </template>
                </a-empty>
                <p class="empty-hint">简历正在解析中，请稍后刷新页面</p>
              </div>
            </template>
          </div>
        </div>
      </template>

      <div v-else class="state-wrapper">
        <a-empty description="未找到该简历" />
      </div>
    </div>

    <a-modal
      v-model:open="matchModalVisible"
      title="选择目标岗位进行匹配"
      :confirm-loading="matchLoading"
      ok-text="开始匹配"
      cancel-text="取消"
      @ok="handleMatch"
    >
      <p style="color: var(--gray-600); margin-bottom: 12px;">
        选择目标岗位，系统将分析简历与岗位要求的匹配程度。
      </p>
      <a-select
        v-model:value="selectedJobId"
        placeholder="请选择目标岗位"
        :loading="jobsLoading"
        allow-clear
        show-search
        :filter-option="filterJobOption"
        style="width: 100%"
      >
        <a-select-option v-for="job in availableJobs" :key="job.id" :value="job.id">
          {{ job.title }}{{ job.department ? ` - ${job.department}` : '' }}
        </a-select-option>
      </a-select>
    </a-modal>

    <a-drawer
      v-model:open="showMatchDetail"
      title="岗位匹配详情"
      :width="640"
      placement="right"
      @afterOpenChange="onDrawerOpenChange"
    >
      <MatchResultPanel v-if="resume?.match_result" :match-result="resume.match_result" />
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeft,
  CalendarDays,
  Mail,
  Phone,
  RefreshCw,
  Trash2,
  MapPin,
  Github,
  GraduationCap,
  Briefcase,
  FolderGit,
  Award,
  Trophy,
  BookOpen,
  Target,
  Wrench,
  MessageSquare,
  FileText,
  FileSearch,
  Plus,
  Star,
  Zap,
  Code2,
  Globe,
  TrendingUp,
  Crosshair,
  RotateCcw,
  AlertCircle
} from 'lucide-vue-next'

import HeaderComponent from '@/components/HeaderComponent.vue'
import MatchResultPanel from '@/components/MatchResultPanel.vue'
import ResumeExtractingAnimation from '@/components/ResumeExtractingAnimation.vue'
import { resumeApi, watchExtractProgress } from '@/apis/resume_api'
import { jobApi } from '@/apis/job_api'

const emit = defineEmits(['changeJob'])

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const deleting = ref(false)
const retrying = ref(false)
const photoLoadError = ref(false)
const resume = ref(null)

const matchModalVisible = ref(false)
const matchLoading = ref(false)
const jobsLoading = ref(false)
const availableJobs = ref([])
const selectedJobId = ref(null)
const showMatchDetail = ref(false)

function onDrawerOpenChange(open) {
  // Drawer 动画完成后，触发窗口 resize 事件让 ECharts 重新计算尺寸
  if (open) {
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'))
    }, 100)
  }
}

const extractStage = ref('idle')
const extractStats = ref({ skills: 0, projects: 0, experience: 0 })
let extractEventSource = null

const FAMOUS_COMPANIES = ['腾讯', '阿里', '字节', '百度', '京东', '美团', '拼多多', '华为', '网易', '滴滴', '快手', '哔哩', '小米', 'OPPO', 'vivo', '蚂蚁', '饿了么']

const summary = computed(() => {
  const llmData = resume.value?.summary_json
  const legacyData = resume.value?.structured_resume
  const data = llmData || legacyData || {}

  const education = (data.education || []).map(item => ({
    school: item.school || item.title || '',
    major: item.major || item.subtitle || '',
    degree: item.degree || '',
    gpa: item.gpa || '',
    ranking: item.ranking || '',
    duration: item.duration || item.date || ''
  }))

  const work = (data.work_experience || data.work || []).map(item => ({
    company: item.company || item.title || '',
    position: item.position || item.subtitle || '',
    duration: item.duration || item.date || '',
    highlights: item.highlights || item.details || []
  }))

  const projects = (data.project_experience || data.projects || []).map(item => ({
    name: item.name || item.title || '',
    role: item.role || item.subtitle || '',
    tech_stack: item.tech_stack || [],
    description: item.description || '',
    results: item.results || [],
    duration: item.duration || item.date || ''
  }))

  return {
    name: data.basic_info?.name || data.name || resume.value?.filename?.replace(/\.pdf$/i, '') || '简历',
    phone: data.basic_info?.phone || data.phone || '',
    email: data.basic_info?.email || data.email || '',
    basicInfo: data.basic_info || {},
    education,
    work,
    projects,
    skills: data.skills || {},
    awards: data.awards || [],
    training: data.training || [],
    selfEvaluation: data.self_evaluation || '',
    jobPreference: data.job_preference || {}
  }
})

const hasSummaryData = computed(() => {
  const s = summary.value
  return (
    s.basicInfo?.name ||
    s.education?.length ||
    s.work?.length ||
    s.projects?.length ||
    s.skills?.technical?.length ||
    s.awards?.length
  )
})

const completenessScore = computed(() => {
  const s = summary.value
  let score = 0
  let total = 0

  if (s.basicInfo?.name) score += 5
  if (s.basicInfo?.phone) score += 3
  if (s.basicInfo?.email) score += 3
  if (s.basicInfo?.location) score += 3
  if (s.basicInfo?.github || s.basicInfo?.linkedin) score += 6
  total += 20

  if (s.education?.length) score += 15
  total += 15

  if (s.work?.length) score += 20
  total += 20

  if (s.projects?.length) score += 20
  total += 20

  if (s.skills?.technical?.length) score += 10
  total += 10

  if (s.awards?.length) score += 5
  if (s.training?.length) score += 5
  if (s.selfEvaluation) score += 5
  total += 15

  return Math.round((score / total) * 100)
})

const completenessClass = computed(() => {
  const score = completenessScore.value
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
})

const completenessColor = computed(() => {
  const score = completenessScore.value
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#f5222d'
})

const completenessTips = computed(() => {
  const tips = []
  const s = summary.value
  if (!s.basicInfo?.github && !s.basicInfo?.linkedin) tips.push('添加 GitHub/LinkedIn')
  if (!s.basicInfo?.phone) tips.push('补充手机号')
  if (!s.basicInfo?.email) tips.push('补充邮箱')
  if (!s.education?.length) tips.push('补充教育经历')
  if (!s.work?.length) tips.push('补充工作经历')
  if (!s.projects?.length) tips.push('补充项目经历')
  if (!s.awards?.length) tips.push('补充获奖情况')
  if (!s.selfEvaluation) tips.push('添加自我评价')
  return tips.slice(0, 3)
})

const highlightTags = computed(() => {
  const tags = []
  const s = summary.value

  if (s.education?.[0]?.gpa) {
    const gpaStr = s.education[0].gpa.toString()
    if (/\b(3\.[7-9]|4\.0|前10%|前5%|前3%)\b/i.test(gpaStr)) {
      tags.push({ text: '高 GPA', color: 'gold', icon: TrendingUp })
    }
  }

  if (s.work?.some(w => FAMOUS_COMPANIES.some(c => (w.company || '').includes(c)))) {
    tags.push({ text: '名企经验', color: 'red', icon: Star })
  }

  if (s.basicInfo?.github) {
    tags.push({ text: '有开源作品', color: 'purple', icon: Code2 })
  }

  if (s.basicInfo?.linkedin) {
    tags.push({ text: '有 LinkedIn', color: 'blue', icon: Globe })
  }

  if (s.awards?.length) {
    tags.push({ text: '竞赛获奖', color: 'orange', icon: Trophy })
  }

  if (s.projects?.length >= 3) {
    tags.push({ text: '项目丰富', color: 'cyan', icon: FolderGit })
  }

  if (s.skills?.technical?.length >= 5) {
    tags.push({ text: '技术栈广', color: 'green', icon: Zap })
  }

  return tags.slice(0, 4)
})

const skillTags = computed(() => {
  const skills = summary.value.skills || {}
  return {
    technical: skills.technical || [],
    languages: skills.languages || [],
    certifications: skills.certifications || []
  }
})

const skillTagsFlat = computed(() => {
  const s = skillTags.value
  return [...s.technical, ...s.languages, ...s.certifications]
})

const skillCloudItems = computed(() => {
  const allSkills = []
  const tech = skillTags.value.technical
  const langs = skillTags.value.languages
  const certs = skillTags.value.certifications

  tech.forEach(s => allSkills.push({ name: s, category: 'technical', weight: 1 }))
  langs.forEach(s => allSkills.push({ name: s, category: 'language', weight: 0.8 }))
  certs.forEach(s => allSkills.push({ name: s, category: 'cert', weight: 0.7 }))

  const maxWeight = Math.max(1, ...allSkills.map(s => s.weight))
  return allSkills.map(s => ({
    ...s,
    size: 12 + Math.round((s.weight / maxWeight) * 6),
  }))
})

const statusText = computed(() => {
  const status = resume.value?.summary_status
  const map = {
    completed: '已完成',
    processing: '处理中',
    failed: '失败',
    pending: '等待中',
    extracting: '提取中'
  }
  return map[status] || '未知'
})

const formatGithubUrl = (url) => {
  if (!url) return ''
  return url.replace(/^https?:\/\/github\.com\/?/, '').replace(/\/$/, '')
}

const startExtractListener = (resumeId) => {
  stopExtractListener()
  extractStage.value = 'extracting'

  extractEventSource = watchExtractProgress(resumeId, {
    onProgress: (data) => {
      extractStage.value = data.stage || 'extracting'
      if (data.stats) {
        extractStats.value = { ...extractStats.value, ...data.stats }
      }
    },
    onCompleted: () => {
      extractStage.value = 'completed'
      loadResumeDetail()
      if (resume.value?.match_status !== 'completed') {
        openMatchModal()
      }
    },
    onFailed: () => {
      extractStage.value = 'failed'
    },
  })
}

const stopExtractListener = () => {
  if (extractEventSource) {
    extractEventSource.close()
    extractEventSource = null
  }
}

const loadResumeDetail = async () => {
  loading.value = true
  try {
    const data = await resumeApi.getResumeDetail(route.params.resume_id)
    resume.value = data?.resume || null

    const status = resume.value?.summary_status
    if (status === 'completed') {
      extractStage.value = 'completed'
    } else if (status === 'processing' || status === 'extracting' || status === 'pending') {
      if (extractStage.value !== 'parsing' && extractStage.value !== 'extracting') {
        extractStage.value = 'extracting'
      }
      startExtractListener(route.params.resume_id)
    } else if (status === 'failed') {
      extractStage.value = 'failed'
    }
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

const handleRetryExtract = async () => {
  if (!resume.value?.id || retrying.value) return
  try {
    retrying.value = true
    await resumeApi.retryExtract(resume.value.id)
    extractStage.value = 'parsing'
    startExtractListener(resume.value.id)
    message.success('已重新开始分析简历')
  } catch (error) {
    message.error(error?.response?.data?.detail || '重试失败，请稍后再试')
  } finally {
    retrying.value = false
  }
}

const matchLevelText = computed(() => {
  const score = resume.value?.match_result?.overall_score || 0
  if (score >= 80) return '优秀'
  if (score >= 60) return '良好'
  if (score >= 40) return '一般'
  return '较差'
})

const matchLevelColor = computed(() => {
  const score = resume.value?.match_result?.overall_score || 0
  if (score >= 80) return 'green'
  if (score >= 60) return 'blue'
  if (score >= 40) return 'orange'
  return 'red'
})

const openMatchModal = async () => {
  selectedJobId.value = null
  matchModalVisible.value = true
  jobsLoading.value = true
  try {
    const data = await jobApi.getJobs({ status: 'active', limit: 100 })
    availableJobs.value = data?.jobs || []
  } catch (error) {
    console.error('加载岗位列表失败:', error)
    message.error('加载岗位列表失败')
  } finally {
    jobsLoading.value = false
  }
}

const filterJobOption = (input, option) => {
  const title = option.children?.[0]?.children || ''
  return title.toLowerCase().includes(input.toLowerCase())
}

const handleMatch = async () => {
  if (!selectedJobId.value || !resume.value?.id) {
    message.warning('请先选择目标岗位')
    return
  }
  matchLoading.value = true
  try {
    await resumeApi.matchResume(resume.value.id, selectedJobId.value)
    message.success('匹配完成')
    matchModalVisible.value = false
    await loadResumeDetail()
    showMatchDetail.value = true
  } catch (error) {
    console.error('匹配失败:', error)
    message.error(error.message || '匹配失败')
  } finally {
    matchLoading.value = false
  }
}

const handleChangeJob = () => {
  const oldJobId = resume.value?.matched_job_id || null
  emit('changeJob', { jobId: null, oldJobId })
  openMatchModal()
}

const handleKeydown = (e) => {
  if (e.ctrlKey && e.key === 'm') {
    e.preventDefault()
    if (resume.value?.match_status === 'completed' && resume.value?.match_result) {
      showMatchDetail.value = true
    } else {
      openMatchModal()
    }
  }
  if (e.key === 'ArrowLeft' && !e.ctrlKey && !e.altKey && !e.metaKey) {
    const el = document.activeElement
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
    goBack()
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
  const shouldAnimate = route.query.extracting === '1'
  if (shouldAnimate) {
    extractStage.value = 'parsing'
  }
  loadResumeDetail()
})

onBeforeUnmount(() => {
  stopExtractListener()
})
</script>

<style scoped lang="less">
.resume-detail-page {
  min-height: 100%;
  background: var(--gray-25);
  outline: none;
}

.resume-detail-content {
  padding: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  align-items: start;
}

.summary-panel {
  border: 1px solid var(--gray-200);
  border-radius: 20px;
  background: var(--gray-0);
  overflow: hidden;
  box-shadow: 0 4px 24px var(--shadow-1);
}

.summary-hero {
  position: relative;
  padding: 36px 40px 28px;
  background: linear-gradient(135deg, #1e3a5f 0%, #2d4a6f 50%, #1a365d 100%);
  color: #fff;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    pointer-events: none;
  }
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 24px;
}

.hero-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0.1) 100%);
  backdrop-filter: blur(12px);
  border: 3px solid rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  position: relative;
  overflow: hidden;

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, transparent 50%);
    pointer-events: none;
  }

  .avatar-photo {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: 50%;
  }
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.hero-name {
  font-size: 32px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: 1px;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.hero-contact {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 28px;
  margin-top: 16px;
}

.contact-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  opacity: 0.95;
  background: rgba(255, 255, 255, 0.12);
  padding: 6px 14px;
  border-radius: 20px;
  backdrop-filter: blur(8px);
  transition: background 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  a {
    color: inherit;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}

.hero-link {
  color: #fff !important;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.highlight-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  backdrop-filter: blur(8px);
  transition: background 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
  }
}

.completeness-bar {
  padding: 20px 40px;
  background: linear-gradient(180deg, rgba(30, 58, 95, 0.04) 0%, transparent 100%);
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
}

.completeness-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.completeness-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-700);
  display: flex;
  align-items: center;
  gap: 6px;

  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    background: #1e3a5f;
    border-radius: 2px;
  }
}

.completeness-score {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.5px;

  &.high { color: #52c41a; }
  &.medium { color: #faad14; }
  &.low { color: #f5222d; }
}

.completeness-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.tip-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--gray-600);
  background: var(--gray-50);
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid var(--gray-200);

  svg {
    color: #1e3a5f;
  }
}

.summary-body {
  padding: 28px 40px;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 32px;
  align-items: start;
}

.summary-section {
  & + .summary-section {
    margin-top: 32px;
  }
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 2px solid #1e3a5f;
  color: #1e3a5f;
  font-size: 17px;
  font-weight: 700;
  position: relative;

  svg {
    opacity: 0.8;
  }

  &--education {
    border-bottom-color: var(--color-info-700);
    color: var(--color-info-700);
  }

  &--work {
    border-bottom-color: #1e3a5f;
    color: #1e3a5f;
  }

  &--project {
    border-bottom-color: var(--color-accent-700);
    color: var(--color-accent-700);
  }
}

.timeline-item {
  padding: 20px 22px;
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  background: var(--gray-0);
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    opacity: 0;
    transition: opacity 0.25s ease;
  }

  &:hover {
    box-shadow: 0 4px 16px rgba(30, 58, 95, 0.08);

    &::before {
      opacity: 1;
    }
  }

  & + .timeline-item {
    margin-top: 16px;
  }

  &--education {
    border-left: 3px solid var(--color-info-500);

    &::before {
      background: var(--color-info-500);
    }

    &:hover {
      border-color: rgba(79, 159, 236, 0.3);
    }
  }

  &--work {
    border-left: 3px solid #1e3a5f;

    &::before {
      background: #1e3a5f;
    }

    &:hover {
      border-color: rgba(30, 58, 95, 0.3);
    }
  }

  &--project {
    border-left: 3px solid var(--color-accent-500);

    &::before {
      background: var(--color-accent-500);
    }

    &:hover {
      border-color: rgba(19, 194, 194, 0.3);
    }
  }
}

.timeline-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.timeline-title {
  color: var(--gray-950);
  font-size: 17px;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: 0.2px;
}

.timeline-date {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--gray-500);
  font-size: 13px;
  background: var(--gray-50);
  padding: 4px 10px;
  border-radius: 12px;
}

.timeline-subtitle {
  margin-top: 6px;
  color: #2d4a6f;
  font-size: 14px;
  font-weight: 600;
}

.timeline-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.info-tag {
  border-radius: 8px;
  font-size: 12px;
  padding: 3px 10px;
  font-weight: 500;
}

.timeline-desc {
  margin-top: 12px;
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.8;
  padding: 12px 16px;
  background: var(--gray-50);
  border-radius: 10px;
  border-left: 3px solid var(--gray-300);
}

.timeline-details {
  margin-top: 12px;
  color: var(--gray-800);
  font-size: 14px;
  line-height: 1.9;

  p {
    margin: 0;
    display: flex;
    align-items: flex-start;
    gap: 10px;

    & + p {
      margin-top: 8px;
    }
  }

  .bullet {
    color: #1e3a5f;
    font-weight: 700;
    font-size: 16px;
    line-height: 1.4;

    &.green {
      color: #52c41a;
    }
  }
}

.awards-grid {
  display: grid;
  gap: 12px;
}

.award-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--gray-200);
  border-left: 4px solid #faad14;
  border-radius: 12px;
  color: var(--gray-900);
  line-height: 1.6;
  background: linear-gradient(135deg, var(--gray-0) 0%, #fffbeb 100%);
  transition: border-color 0.25s ease, box-shadow 0.25s ease;

  &:hover {
    box-shadow: 0 4px 12px rgba(250, 173, 20, 0.15);
  }
}

.award-icon {
  color: #faad14;
  flex-shrink: 0;
}

.training-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.training-item {
  padding: 14px 18px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  color: var(--gray-800);
  font-size: 14px;
  background: var(--gray-0);
  transition: border-color 0.25s ease, background 0.25s ease;

  &:hover {
    border-color: #1e3a5f;
    background: rgba(30, 58, 95, 0.02);
  }
}

.side-card {
  padding: 22px;
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  background: var(--gray-0);
  transition: border-color 0.25s ease, box-shadow 0.25s ease;

  &:hover {
    border-color: rgba(30, 58, 95, 0.2);
    box-shadow: 0 4px 16px rgba(30, 58, 95, 0.06);
  }
}

.preference-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pref-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 14px;
  background: var(--gray-50);
  border-radius: 10px;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(30, 58, 95, 0.04);
  }
}

.pref-label {
  font-size: 12px;
  color: var(--gray-500);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pref-value {
  font-size: 15px;
  color: var(--gray-900);
  font-weight: 600;
}

// Inline match panel with ring
.match-panel__card--inline {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: var(--gray-50);
  border-radius: 12px;
  margin-bottom: 12px;
}

.match-inline__score-ring {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}

.match-ring-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.match-ring-bg {
  fill: none;
  stroke: var(--gray-200);
  stroke-width: 3;
}

.match-ring-fill {
  fill: none;
  stroke: var(--main-color);
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}

.match-ring-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #1e3a5f;
}

.match-inline__info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.match-inline__job {
  font-size: 13px;
  color: var(--gray-600);
}

.match-actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.match-detail-link {
  color: var(--main-color);
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.2s;

  &:hover {
    opacity: 0.8;
  }
}

.match-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-500);
  font-size: 13px;
}

// Skill cloud
.skill-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: center;
  justify-content: center;
  padding: 12px 0;
}

.skill-cloud__tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
  line-height: 1.4;
  transition: background 0.2s ease;

  &--technical {
    background: var(--color-info-50);
    color: var(--color-info-700);
  }

  &--language {
    background: var(--color-success-50);
    color: var(--color-success-700);
  }

  &--cert {
    background: var(--color-warning-50);
    color: var(--color-warning-700);
  }
}

.self-eval-text {
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.9;
  padding: 16px;
  background: var(--gray-50);
  border-radius: 12px;
  border-left: 4px solid #1e3a5f;
}

.match-summary-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
}

.match-score {
  font-size: 36px;
  font-weight: 700;
  color: #1e3a5f;
  line-height: 1;
}

.match-score-unit {
  font-size: 14px;
  color: var(--gray-500);
  margin-right: 8px;
}

.match-level-tag {
  margin-left: 4px;
}

.meta-section {
  background: linear-gradient(180deg, var(--gray-50) 0%, var(--gray-0) 100%);
  border-color: var(--gray-200);
}

.meta-descriptions {
  :deep(.ant-descriptions-item-label) {
    color: var(--gray-500);
    font-size: 12px;
    font-weight: 500;
  }

  :deep(.ant-descriptions-item-content) {
    font-size: 13px;
    color: var(--gray-700);
  }
}

.empty-state {
  padding: 80px 40px;
  text-align: center;
  background: linear-gradient(180deg, var(--gray-50) 0%, var(--gray-0) 100%);
}

.empty-icon {
  color: var(--gray-300);
}

.empty-hint {
  margin-top: 16px;
  color: var(--gray-500);
  font-size: 14px;
}

.state-wrapper {
  min-height: calc(100vh - 220px);
  display: flex;
  align-items: center;
  justify-content: center;
}

// Slide-up animation
.slide-up {
  animation: slideUp 0.4s ease-out both;
  animation-delay: var(--delay, 0s);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1100px) {
  .summary-body {
    grid-template-columns: 1fr;
  }

  .summary-hero {
    padding: 28px 24px 24px;
  }

  .hero-name {
    font-size: 28px;
  }

  .hero-top {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .hero-avatar {
    width: 64px;
    height: 64px;
    font-size: 24px;
  }

  .hero-contact {
    gap: 10px 16px;
  }

  .summary-body {
    padding: 20px 20px;
  }
}

@media (max-width: 780px) {
  .summary-hero {
    padding: 24px 20px 20px;
  }

  .hero-name {
    font-size: 24px;
  }

  .hero-avatar {
    width: 56px;
    height: 56px;
    font-size: 22px;
  }

  .summary-body {
    padding: 16px;
  }

  .hero-tags {
    gap: 8px;
  }

  .highlight-tag {
    font-size: 12px;
    padding: 5px 12px;
  }
}

.extract-failed-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px 24px;
  background: linear-gradient(135deg, #fff7e6 0%, var(--gray-0) 50%, #fff1f0 100%);
  border-radius: 12px;
  border: 1px solid var(--gray-150);
}

.extract-failed__icon {
  color: #faad14;
}

.extract-failed__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-800);
}

.extract-failed__error {
  font-size: 13px;
  color: var(--gray-500);
  max-width: 360px;
  text-align: center;
}

.extract-failed__hint {
  font-size: 13px;
  color: var(--gray-500);
}
</style>
