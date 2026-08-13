<template>
  <div class="rd-root" tabindex="-1" @keydown="handleKeydown">
    <header class="rd-top">
      <div class="rd-top__copy">
        <h1 class="rd-title">{{ resume?.filename || '简历解析详情' }}</h1>
        <p class="rd-subtitle">{{ headerSubtitle }}</p>
      </div>
      <div class="rd-top__actions">
        <button class="rd-button" type="button" @click="goBack">返回列表</button>
        <button
          class="rd-button"
          type="button"
          :disabled="!canRetryExtract"
          @click="handleRetryExtract"
        >
          {{ retrying ? '重新解析中…' : '重新解析' }}
        </button>
        <button
          class="rd-button rd-button--primary"
          type="button"
          :disabled="!resume?.id || extractStage !== 'completed'"
          @click="startInterviewWithResume"
        >
          用这份简历面试
        </button>
      </div>
    </header>

    <main class="rd-content">
      <div v-if="loading" class="rd-state">
        <a-spin />
        <span>正在加载简历详情…</span>
      </div>

      <div v-else-if="!resume" class="rd-state">
        <a-empty description="未找到该简历" />
      </div>

      <ResumeExtractingAnimation
        v-else-if="extractStage === 'parsing' || extractStage === 'extracting'"
        :stage="extractStage"
        :stats="extractStats"
      />

      <section v-else-if="extractStage === 'failed'" class="rd-failed">
        <AlertCircle :size="32" />
        <h2>简历分析失败</h2>
        <p v-if="resume.summary_error" class="rd-failed__error">{{ resume.summary_error }}</p>
        <p>请检查简历文件是否完整，或重新解析后再试。</p>
        <button class="rd-button rd-button--primary" type="button" :disabled="retrying" @click="handleRetryExtract">
          {{ retrying ? '重新解析中…' : '重新解析' }}
        </button>
      </section>

      <template v-else>
        <section class="rd-overview">
          <div class="rd-profile">
            <div class="rd-avatar">
              <img
                v-if="summary.basicInfo.photo_url && !photoLoadError"
                :src="summary.basicInfo.photo_url"
                alt="简历证件照"
                @error="photoLoadError = true"
              />
              <span v-else>{{ summary.name.charAt(0) || '简' }}</span>
            </div>
            <div class="rd-profile__body">
              <h2 class="rd-name">{{ summary.name }}</h2>
              <div v-if="contactItems.length" class="rd-contact">
                <template v-for="item in contactItems" :key="item.key">
                  <a
                    v-if="item.href"
                    class="rd-contact__link"
                    :href="item.href"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {{ item.text }}
                  </a>
                  <span v-else>{{ item.text }}</span>
                </template>
              </div>
              <div v-if="highlightTags.length" class="rd-highlights">
                <span
                  v-for="(tag, index) in highlightTags"
                  :key="tag"
                  class="rd-highlight"
                  :class="`rd-highlight--${index % 3}`"
                >
                  {{ tag }}
                </span>
              </div>
            </div>
          </div>

          <div class="rd-completeness">
            <div class="rd-metric__head">
              <span>简历完整度</span>
              <strong :class="`is-${completenessLevel}`">{{ completenessScore }}%</strong>
            </div>
            <div class="rd-progress" aria-hidden="true">
              <span :class="`is-${completenessLevel}`" :style="{ width: `${completenessScore}%` }" />
            </div>
            <p class="rd-metric__hint">
              {{ completenessTips.length ? `建议补充：${completenessTips.join('、')}` : '关键信息已较完整' }}
            </p>
          </div>

          <div class="rd-match">
            <template v-if="resume.match_status === 'completed' && resume.match_result">
              <div class="rd-match__ring">
                <svg viewBox="0 0 36 36" aria-hidden="true">
                  <circle class="rd-match__track" cx="18" cy="18" r="15.9" />
                  <circle
                    class="rd-match__value"
                    cx="18"
                    cy="18"
                    r="15.9"
                    :stroke-dasharray="`${matchScore} 100`"
                  />
                </svg>
                <strong>{{ matchScore }}</strong>
              </div>
              <div class="rd-match__copy">
                <span class="rd-match__label">岗位匹配</span>
                <span class="rd-match__badge" :class="`is-${matchLevelTone}`">{{ matchLevelText }}</span>
                <button class="rd-link" type="button" @click="showMatchDetail = true">查看匹配详情</button>
              </div>
            </template>
            <template v-else-if="resume.match_status === 'pending' || resume.match_status === 'processing'">
              <a-spin size="small" />
              <div class="rd-match__copy">
                <span class="rd-match__label">岗位匹配</span>
                <strong>正在匹配中…</strong>
              </div>
            </template>
            <template v-else>
              <Crosshair :size="28" />
              <div class="rd-match__copy">
                <span class="rd-match__label">岗位匹配</span>
                <button class="rd-link" type="button" @click="openMatchModal">选择岗位开始匹配</button>
              </div>
            </template>
          </div>
        </section>

        <div v-if="hasSummaryData" class="rd-columns">
          <section class="rd-card rd-experience">
            <h2 class="rd-card__title">工作与项目经历</h2>
            <div v-if="timelineItems.length" class="rd-timeline">
              <article v-for="item in timelineItems" :key="item.key" class="rd-timeline__item">
                <div class="rd-timeline__head">
                  <h3>{{ item.title }}</h3>
                  <time v-if="item.duration">{{ item.duration }}</time>
                </div>
                <p v-if="item.subtitle" class="rd-timeline__subtitle">{{ item.subtitle }}</p>
                <div v-if="item.tags.length" class="rd-timeline__tags">
                  <span
                    v-for="tag in item.tags"
                    :key="tag"
                    class="rd-chip"
                    :class="item.kind === 'project' ? 'rd-chip--project' : 'rd-chip--education'"
                  >
                    {{ tag }}
                  </span>
                </div>
                <p v-if="item.description" class="rd-timeline__description">{{ item.description }}</p>
                <ul v-if="item.details.length" class="rd-timeline__details">
                  <li v-for="detail in item.details" :key="detail">{{ detail }}</li>
                </ul>
              </article>
            </div>
            <div v-else class="rd-card__empty">当前简历未提取到工作、项目或教育经历。</div>
          </section>

          <aside class="rd-aside">
            <section v-if="jobPreferenceItems.length" class="rd-card rd-card--side">
              <h2 class="rd-card__title">求职意向</h2>
              <dl class="rd-key-values">
                <div v-for="item in jobPreferenceItems" :key="item.label">
                  <dt>{{ item.label }}</dt>
                  <dd>{{ item.value }}</dd>
                </div>
              </dl>
            </section>

            <section v-if="skillTagsFlat.length" class="rd-card rd-card--side">
              <h2 class="rd-card__title">技能</h2>
              <div class="rd-skills">
                <span v-for="skill in skillTagsFlat" :key="skill" class="rd-chip rd-chip--skill">{{ skill }}</span>
              </div>
            </section>

            <section v-if="summary.selfEvaluation" class="rd-card rd-card--side">
              <h2 class="rd-card__title">自我评价</h2>
              <p class="rd-aside__text">{{ summary.selfEvaluation }}</p>
            </section>

            <section v-if="summary.awards.length || summary.training.length" class="rd-card rd-card--side">
              <h2 class="rd-card__title">补充经历</h2>
              <ul class="rd-simple-list">
                <li v-for="item in [...summary.awards, ...summary.training]" :key="item">{{ item }}</li>
              </ul>
            </section>

            <section class="rd-card rd-card--side">
              <h2 class="rd-card__title">文件信息</h2>
              <dl class="rd-key-values">
                <div>
                  <dt>文件名</dt>
                  <dd class="rd-key-values__filename">{{ resume.filename }}</dd>
                </div>
                <div>
                  <dt>文件大小</dt>
                  <dd>{{ formatFileSize(resume.file_size) }}</dd>
                </div>
                <div>
                  <dt>解析状态</dt>
                  <dd><span class="rd-status" :class="`is-${resume.summary_status}`">{{ statusText }}</span></dd>
                </div>
              </dl>
            </section>
          </aside>
        </div>

        <div v-else class="rd-state rd-state--card">
          <a-empty description="暂未从当前简历中提取到结构化信息" />
        </div>
      </template>
    </main>

    <a-modal
      v-model:open="matchModalVisible"
      title="选择目标岗位进行匹配"
      :confirm-loading="matchLoading"
      ok-text="开始匹配"
      cancel-text="取消"
      @ok="handleMatch"
    >
      <p class="rd-modal__hint">选择目标岗位，系统将分析简历与岗位要求的匹配程度。</p>
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
      :width="matchDrawerWidth"
      placement="right"
      @after-open-change="onDrawerOpenChange"
    >
      <MatchResultPanel v-if="resume?.match_result" :match-result="resume.match_result" />
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { AlertCircle, Crosshair } from 'lucide-vue-next'

import MatchResultPanel from '@/components/MatchResultPanel.vue'
import ResumeExtractingAnimation from '@/components/ResumeExtractingAnimation.vue'
import { resumeApi, watchExtractProgress } from '@/apis/resume_api'
import { jobApi } from '@/apis/job_api'

const route = useRoute()
const router = useRouter()
const matchDrawerWidth = 'min(640px, 100vw)'

const loading = ref(false)
const retrying = ref(false)
const photoLoadError = ref(false)
const resume = ref(null)
const matchModalVisible = ref(false)
const matchLoading = ref(false)
const jobsLoading = ref(false)
const availableJobs = ref([])
const selectedJobId = ref(null)
const showMatchDetail = ref(false)
const extractStage = ref('idle')
const extractStats = ref({ skills: 0, projects: 0, experience: 0 })
let extractListener = null

const toArray = (value) => {
  if (Array.isArray(value)) return value.filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

const summary = computed(() => {
  const data = resume.value?.summary_json || resume.value?.structured_resume || {}
  const basicInfo = data.basic_info || {}

  return {
    name: basicInfo.name || data.name || resume.value?.filename?.replace(/\.pdf$/i, '') || '简历',
    phone: basicInfo.phone || data.phone || '',
    email: basicInfo.email || data.email || '',
    basicInfo,
    education: toArray(data.education).map((item) => ({
      school: item.school || item.title || '',
      major: item.major || item.subtitle || '',
      degree: item.degree || '',
      gpa: item.gpa || '',
      ranking: item.ranking || '',
      duration: item.duration || item.date || '',
      details: toArray(item.details)
    })),
    work: toArray(data.work_experience || data.work).map((item) => ({
      company: item.company || item.title || '',
      position: item.position || item.subtitle || '',
      duration: item.duration || item.date || '',
      highlights: toArray(item.highlights || item.details),
      techStack: toArray(item.tech_stack)
    })),
    projects: toArray(data.project_experience || data.projects).map((item) => ({
      name: item.name || item.title || '',
      role: item.role || item.subtitle || '',
      techStack: toArray(item.tech_stack),
      description: item.description || '',
      results: toArray(item.results || item.details),
      duration: item.duration || item.date || ''
    })),
    skills: data.skills || {},
    awards: toArray(data.awards),
    training: toArray(data.training),
    selfEvaluation: data.self_evaluation || '',
    jobPreference: data.job_preference || {}
  }
})

const skillTagsFlat = computed(() => {
  const skills = summary.value.skills
  if (Array.isArray(skills)) return skills.filter(Boolean)
  return [...toArray(skills.technical), ...toArray(skills.languages), ...toArray(skills.certifications)]
})

const hasSummaryData = computed(() => {
  const data = summary.value
  return Boolean(
    data.basicInfo.name ||
      data.education.length ||
      data.work.length ||
      data.projects.length ||
      skillTagsFlat.value.length ||
      data.selfEvaluation
  )
})

const completenessScore = computed(() => {
  const data = summary.value
  let score = 0
  if (data.name) score += 5
  if (data.phone) score += 3
  if (data.email) score += 3
  if (data.basicInfo.location) score += 3
  if (data.basicInfo.github || data.basicInfo.linkedin) score += 6
  if (data.education.length) score += 15
  if (data.work.length) score += 20
  if (data.projects.length) score += 20
  if (skillTagsFlat.value.length) score += 10
  if (data.awards.length) score += 5
  if (data.training.length) score += 5
  if (data.selfEvaluation) score += 5
  return score
})

const completenessLevel = computed(() => {
  if (completenessScore.value >= 80) return 'high'
  if (completenessScore.value >= 60) return 'medium'
  return 'low'
})

const completenessTips = computed(() => {
  const data = summary.value
  const tips = []
  if (!data.basicInfo.github && !data.basicInfo.linkedin) tips.push('项目链接')
  if (!data.projects.length) tips.push('项目经历')
  if (!data.awards.length) tips.push('获奖经历')
  if (!data.selfEvaluation) tips.push('自我评价')
  return tips.slice(0, 2)
})

const contactItems = computed(() => {
  const data = summary.value
  const location = [data.basicInfo.location, data.jobPreference.desired_location ? `期望${data.jobPreference.desired_location}` : '']
    .filter(Boolean)
    .join(' · ')
  const github = data.basicInfo.github
  return [
    { key: 'phone', text: data.phone },
    { key: 'email', text: data.email },
    { key: 'location', text: location },
    {
      key: 'github',
      text: github ? github.replace(/^https?:\/\/github\.com\/?/i, 'github.com/').replace(/\/$/, '') : '',
      href: github ? (/^https?:\/\//i.test(github) ? github : `https://${github}`) : ''
    }
  ].filter((item) => item.text)
})

const highlightTags = computed(() => {
  const data = summary.value
  const tags = []
  if (data.work.length) tags.push(`${data.work.length} 段工作经历`)
  if (data.education[0]?.degree) tags.push(data.education[0].degree)
  if (data.projects.length) tags.push(`${data.projects.length} 个项目`)
  return tags
})

const timelineItems = computed(() => {
  const data = summary.value
  const work = data.work.map((item, index) => ({
    key: `work-${index}`,
    kind: 'work',
    title: item.company || '工作经历',
    subtitle: item.position,
    duration: item.duration,
    tags: item.techStack,
    description: '',
    details: item.highlights
  }))
  const projects = data.projects.map((item, index) => ({
    key: `project-${index}`,
    kind: 'project',
    title: item.name || '项目经历',
    subtitle: item.role,
    duration: item.duration,
    tags: item.techStack,
    description: item.description,
    details: item.results
  }))
  const education = data.education.map((item, index) => ({
    key: `education-${index}`,
    kind: 'education',
    title: item.school || '教育经历',
    subtitle: [item.major, item.degree].filter(Boolean).join(' · '),
    duration: item.duration,
    tags: [item.gpa ? `GPA: ${item.gpa}` : '', item.ranking].filter(Boolean),
    description: '',
    details: item.details
  }))
  return [...work, ...projects, ...education]
})

const jobPreferenceItems = computed(() => {
  const preference = summary.value.jobPreference
  return [
    { label: '意向岗位', value: preference.job_intention },
    { label: '期望薪资', value: preference.expected_salary },
    { label: '期望地点', value: preference.desired_location }
  ].filter((item) => item.value)
})

const statusText = computed(() => {
  const map = {
    completed: '已完成',
    processing: '处理中',
    failed: '失败',
    pending: '等待中',
    extracting: '提取中'
  }
  return map[resume.value?.summary_status] || '未知'
})

const parserStatusText = computed(() => {
  const parser = resume.value?.parser_name || '解析器'
  const map = {
    completed: '解析完成',
    processing: '解析中',
    failed: '解析失败',
    pending: '等待解析',
    extracting: '解析中'
  }
  return `${parser} ${map[resume.value?.summary_status] || '状态未知'}`
})

const headerSubtitle = computed(() => {
  if (!resume.value) return '正在读取简历信息…'
  return [
    formatFileSize(resume.value.file_size),
    `更新于 ${formatDateTime(resume.value.updated_at || resume.value.created_at)}`,
    parserStatusText.value
  ].join(' · ')
})

const matchScore = computed(() => {
  const value = Number(resume.value?.match_result?.overall_score || 0)
  return Math.round(Math.max(0, Math.min(100, value)))
})

const matchLevelText = computed(() => {
  if (matchScore.value >= 80) return '高度匹配'
  if (matchScore.value >= 60) return '较匹配'
  if (matchScore.value >= 40) return '一般匹配'
  return '匹配较低'
})

const matchLevelTone = computed(() => {
  if (matchScore.value >= 60) return 'good'
  if (matchScore.value >= 40) return 'medium'
  return 'low'
})

const canRetryExtract = computed(() => {
  const status = resume.value?.summary_status
  return Boolean(resume.value?.id && !retrying.value && (status === 'completed' || status === 'failed'))
})

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
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
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const stopExtractListener = () => {
  if (!extractListener) return
  extractListener.close()
  extractListener = null
}

const startExtractListener = (resumeId) => {
  stopExtractListener()
  extractStage.value = 'extracting'
  extractListener = watchExtractProgress(resumeId, {
    onProgress: (data) => {
      extractStage.value = data.stage || 'extracting'
      if (data.stats) extractStats.value = { ...extractStats.value, ...data.stats }
    },
    onCompleted: async () => {
      extractStage.value = 'completed'
      await loadResumeDetail()
    },
    onFailed: async () => {
      extractStage.value = 'failed'
      await loadResumeDetail()
    }
  })
}

const loadResumeDetail = async () => {
  loading.value = true
  try {
    const data = await resumeApi.getResumeDetail(route.params.resume_id)
    resume.value = data?.resume || null
    photoLoadError.value = false
    const status = resume.value?.summary_status
    if (status === 'completed') {
      extractStage.value = 'completed'
      stopExtractListener()
    } else if (status === 'processing' || status === 'extracting' || status === 'pending') {
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

const goBack = () => router.push('/resume')

const startInterviewWithResume = () => {
  if (!resume.value?.id) return
  router.push({ name: 'InterviewWorkbench', query: { resumeId: String(resume.value.id) } })
}

const handleRetryExtract = async () => {
  if (!canRetryExtract.value) return
  try {
    retrying.value = true
    await resumeApi.retryExtract(resume.value.id)
    extractStage.value = 'parsing'
    startExtractListener(resume.value.id)
    message.success('已重新开始解析简历')
  } catch (error) {
    message.error(error?.response?.data?.detail || '重新解析失败，请稍后再试')
  } finally {
    retrying.value = false
  }
}

const openMatchModal = async () => {
  selectedJobId.value = resume.value?.target_job_id || null
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

const onDrawerOpenChange = (open) => {
  if (!open) return
  setTimeout(() => window.dispatchEvent(new Event('resize')), 100)
}

const handleKeydown = (event) => {
  if (event.ctrlKey && event.key === 'm') {
    event.preventDefault()
    if (resume.value?.match_status === 'completed' && resume.value?.match_result) {
      showMatchDetail.value = true
    } else {
      openMatchModal()
    }
  }
  if (event.key === 'ArrowLeft' && !event.ctrlKey && !event.altKey && !event.metaKey) {
    const activeElement = document.activeElement
    if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable)) return
    goBack()
  }
}

onMounted(() => {
  if (route.query.extracting === '1') extractStage.value = 'parsing'
  loadResumeDetail()
})

onBeforeUnmount(stopExtractListener)
</script>

<style scoped lang="less">
.rd-root {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  color: var(--gray-1000);
  background: var(--gray-25);
  outline: none;
}

.rd-top {
  flex: 0 0 auto;
  min-height: 82px;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  background: var(--gray-0);
  border-bottom: 1px solid var(--gray-100);
}

.rd-top__copy { min-width: 0; }
.rd-title { margin: 0; font-size: 24px; line-height: 1.2; font-weight: 700; overflow-wrap: anywhere; }
.rd-subtitle { margin: 7px 0 0; color: var(--gray-500); font-size: 13px; line-height: 1.4; }
.rd-top__actions { flex: 0 0 auto; display: flex; gap: 12px; }

.rd-button {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: var(--gray-0);
  color: var(--gray-700);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;

  &:hover:not(:disabled), &:focus-visible { border-color: var(--main-600); color: var(--main-700); }
  &:focus-visible { outline: 2px solid var(--main-300); outline-offset: 2px; }
  &:disabled { cursor: not-allowed; opacity: 0.45; }
}

.rd-button--primary {
  border-color: var(--main-800);
  background: var(--main-800);
  color: var(--gray-0);
  &:hover:not(:disabled), &:focus-visible { border-color: var(--main-700); background: var(--main-700); color: var(--gray-0); }
}

.rd-content {
  flex: 1 1 auto;
  min-height: 0;
  padding: 20px 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.rd-overview,
.rd-card,
.rd-failed,
.rd-state--card {
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
  border-radius: 16px;
}

.rd-overview {
  flex: 0 0 auto;
  padding: 22px 26px;
  display: grid;
  grid-template-columns: minmax(360px, 1fr) 220px 190px;
  align-items: center;
  gap: 28px;
}

.rd-profile { min-width: 0; display: flex; align-items: center; gap: 18px; }
.rd-avatar {
  width: 64px;
  height: 64px;
  flex: 0 0 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 50%;
  background: var(--main-50);
  color: var(--main-700);
  font-size: 22px;
  font-weight: 700;
  img { width: 100%; height: 100%; object-fit: cover; }
}
.rd-profile__body { min-width: 0; }
.rd-name { margin: 0; font-size: 24px; line-height: 1.2; font-weight: 700; }
.rd-contact { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px 20px; color: var(--gray-600); font-size: 13px; }
.rd-contact__link { color: var(--main-600); text-decoration: none; &:hover { text-decoration: underline; } }
.rd-highlights { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.rd-highlight,
.rd-chip,
.rd-status,
.rd-match__badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 10px;
  border: 1px solid;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
}
.rd-highlight--0, .rd-chip--skill { background: var(--main-50); color: var(--main-700); border-color: var(--main-200); }
.rd-highlight--1 { background: var(--color-accent-50); color: var(--color-accent-700); border-color: var(--color-accent-100); }
.rd-highlight--2, .rd-chip--project { background: var(--color-warning-50); color: var(--color-warning-700); border-color: var(--color-warning-100); }

.rd-completeness,
.rd-match { min-width: 0; border-left: 1px solid var(--gray-100); padding-left: 24px; }
.rd-metric__head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; color: var(--gray-600); font-size: 13px; }
.rd-metric__head strong { font-size: 18px; }
.is-high { color: var(--color-success-700); }
.is-medium { color: var(--color-warning-700); }
.is-low { color: var(--color-error-700); }
.rd-progress { height: 8px; margin-top: 10px; overflow: hidden; border-radius: 4px; background: var(--gray-100); }
.rd-progress span { display: block; height: 100%; border-radius: inherit; background: currentColor; }
.rd-metric__hint { margin: 10px 0 0; color: var(--gray-500); font-size: 12px; line-height: 1.6; }

.rd-match { display: flex; align-items: center; gap: 14px; }
.rd-match__ring { position: relative; width: 66px; height: 66px; flex: 0 0 66px; }
.rd-match__ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.rd-match__ring circle { fill: none; stroke-width: 3.4; }
.rd-match__track { stroke: var(--gray-100); }
.rd-match__value { stroke: var(--main-600); stroke-linecap: round; }
.rd-match__ring strong { position: absolute; inset: 0; display: grid; place-items: center; font-size: 16px; }
.rd-match__copy { min-width: 0; display: flex; align-items: flex-start; flex-direction: column; gap: 7px; }
.rd-match__label { color: var(--gray-600); font-size: 13px; }
.rd-match__badge.is-good { color: var(--color-success-700); background: var(--color-success-50); border-color: var(--color-success-100); }
.rd-match__badge.is-medium { color: var(--color-warning-700); background: var(--color-warning-50); border-color: var(--color-warning-100); }
.rd-match__badge.is-low { color: var(--color-error-700); background: var(--color-error-50); border-color: var(--color-error-100); }
.rd-link { padding: 0; border: 0; background: none; color: var(--main-600); font: inherit; font-size: 12px; cursor: pointer; text-align: left; &:hover { text-decoration: underline; } }

.rd-columns { flex: 1 0 auto; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start; }
.rd-card { padding: 20px 26px; }
.rd-card__title { margin: 0; display: flex; align-items: center; gap: 8px; color: var(--gray-1000); font-size: 16px; line-height: 1.3; font-weight: 700; }
.rd-card__title::before { content: ''; width: 3px; height: 15px; flex: 0 0 3px; background: var(--main-600); }
.rd-card__empty { margin-top: 20px; color: var(--gray-500); font-size: 14px; }
.rd-timeline { margin-top: 18px; padding-left: 20px; display: flex; flex-direction: column; gap: 22px; border-left: 2px solid var(--gray-100); }
.rd-timeline__item { min-width: 0; }
.rd-timeline__head { display: flex; align-items: baseline; justify-content: space-between; gap: 18px; }
.rd-timeline__head h3 { margin: 0; color: var(--gray-1000); font-size: 16px; font-weight: 700; }
.rd-timeline__head time { flex: 0 0 auto; color: var(--gray-500); font-size: 13px; }
.rd-timeline__subtitle { margin: 5px 0 0; color: var(--gray-700); font-size: 14px; }
.rd-timeline__tags { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; }
.rd-chip--education { background: var(--color-accent-50); color: var(--color-accent-700); border-color: var(--color-accent-100); }
.rd-timeline__description { margin: 10px 0 0; color: var(--gray-700); font-size: 14px; line-height: 1.75; }
.rd-timeline__details { margin: 10px 0 0; padding: 0; list-style: none; color: var(--gray-700); font-size: 14px; line-height: 1.8; }
.rd-timeline__details li::before { content: '·'; margin-right: 7px; color: var(--gray-500); }

.rd-aside { min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.rd-card--side { padding: 14px 18px; }
.rd-card--side .rd-card__title { font-size: 15px; }
.rd-card--side .rd-card__title::before { height: 14px; }
.rd-key-values { margin: 14px 0 0; display: flex; flex-direction: column; gap: 10px; font-size: 14px; }
.rd-key-values > div { min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.rd-key-values dt { flex: 0 0 auto; color: var(--gray-500); }
.rd-key-values dd { min-width: 0; margin: 0; color: var(--gray-1000); text-align: right; overflow-wrap: anywhere; }
.rd-key-values__filename { max-width: 210px; }
.rd-skills { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; }
.rd-chip--skill { min-height: 26px; font-size: 13px; }
.rd-aside__text { margin: 12px 0 0; color: var(--gray-700); font-size: 14px; line-height: 1.75; }
.rd-simple-list { margin: 12px 0 0; padding-left: 18px; color: var(--gray-700); font-size: 14px; line-height: 1.7; }
.rd-status.is-completed { color: var(--color-success-700); background: var(--color-success-50); border-color: var(--color-success-100); }
.rd-status.is-failed { color: var(--color-error-700); background: var(--color-error-50); border-color: var(--color-error-100); }
.rd-status:not(.is-completed):not(.is-failed) { color: var(--color-warning-700); background: var(--color-warning-50); border-color: var(--color-warning-100); }

.rd-state { flex: 1; min-height: 320px; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 12px; color: var(--gray-500); font-size: 14px; }
.rd-state--card { flex: 0 0 auto; padding: 40px; }
.rd-failed { margin: auto; width: min(560px, 100%); padding: 40px; display: flex; align-items: center; flex-direction: column; text-align: center; color: var(--gray-600); }
.rd-failed h2 { margin: 12px 0 0; color: var(--gray-1000); font-size: 20px; }
.rd-failed p { margin: 8px 0 16px; }
.rd-failed__error { color: var(--color-error-700); }
.rd-modal__hint { margin: 0 0 12px; color: var(--gray-600); }

@media (max-width: 1240px) {
  .rd-overview { grid-template-columns: minmax(300px, 1fr) 190px 175px; gap: 20px; padding-inline: 22px; }
  .rd-completeness, .rd-match { padding-left: 20px; }
}

@media (max-width: 1024px) {
  .rd-top { align-items: flex-start; padding-inline: 24px; }
  .rd-overview { grid-template-columns: 1fr 1fr; }
  .rd-profile { grid-column: 1 / -1; }
  .rd-completeness { border-left: 0; padding-left: 0; }
  .rd-columns { grid-template-columns: 1fr; }
  .rd-aside { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
}

@media (max-width: 760px) {
  .rd-top { flex-direction: column; gap: 14px; }
  .rd-top__actions { width: 100%; flex-wrap: wrap; }
  .rd-content { padding: 16px; }
  .rd-overview { grid-template-columns: 1fr; }
  .rd-profile { grid-column: auto; align-items: flex-start; }
  .rd-completeness, .rd-match { border-left: 0; border-top: 1px solid var(--gray-100); padding: 18px 0 0; }
  .rd-aside { grid-template-columns: 1fr; }
  .rd-timeline__head { flex-direction: column; gap: 4px; }
}
</style>
