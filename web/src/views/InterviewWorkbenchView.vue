<template>
  <div class="wb-root">面试工作台</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

import { interviewHistoryApi } from '@/apis/interview_history'
import { learnApi } from '@/apis/learn_api'
import { resumeApi } from '@/apis/resume_api'
import { usePositionTypes } from '@/composables/usePositionTypes'
import { useUserStore } from '@/stores/user'
import { decodeHtmlEntities } from '@/utils/html'
import { normalizePositionType } from '@/utils/position_utils'
import { parseToShanghai } from '@/utils/time'

// 面试 agent 只有固定 6 步 todo，实际题量随对话浮动，接口没有「计划题量」。
// 这是一个展示约定，不是从数据推导出来的值。
const EXPECTED_QUESTION_COUNT = 8
// 与后端 interview_result_service.LOW_SCORE_THRESHOLD 对齐
const LOW_SCORE_THRESHOLD = 75

const router = useRouter()
const userStore = useUserStore()
const { positionTypes, positionTypeOptions, defaultPositionType, loadPositionTypes } = usePositionTypes()

const loading = ref(false)
const historyPayload = ref(null)
const resumeOptions = ref([])
const knowledgeDatabases = ref([])

const interviewModeOptions = [
  { label: '文本', value: 'text' },
  { label: '语音', value: 'voice' }
]
const roundOptions = [
  { label: '初试', value: '初试' },
  { label: '复试', value: '复试' },
  { label: 'HR', value: 'HR' }
]

const selectedInterviewMode = ref('text')
const selectedPosition = ref(defaultPositionType.value.label)
const selectedRound = ref('初试')
const selectedResumeId = ref(null)

const records = computed(() => historyPayload.value?.records || [])
const profile = computed(() => historyPayload.value?.profile || {})
const chart = computed(() => historyPayload.value?.chart || {})

const headerSummary = computed(() => {
  const total = records.value.length
  const reported = records.value.filter((item) => item.has_result).length
  const scores = records.value
    .map((item) => item.overall_score)
    .filter((score) => typeof score === 'number' && Number.isFinite(score))
  const average = scores.length ? Math.round(scores.reduce((sum, s) => sum + s, 0) / scores.length) : null
  return `${total} 场 · 已出报告 ${reported} 场 · 平均 ${average === null ? '—' : `${average} 分`}`
})

const activeRecord = computed(() => records.value.find((item) => item.status === 'in_progress') || null)

const formatDuration = (record) => {
  const start = parseToShanghai(record.created_at)
  const end = parseToShanghai(record.updated_at)
  if (!start || !end) return ''
  const minutes = Math.floor(end.diff(start, 'minute'))
  return minutes < 1 ? '不到 1 分钟' : `${minutes} 分钟`
}

const activeProgress = computed(() => {
  const record = activeRecord.value
  if (!record) return null
  const answered = Math.min(Number(record.answered_count || 0), EXPECTED_QUESTION_COUNT)
  return {
    answered,
    total: EXPECTED_QUESTION_COUNT,
    remaining: EXPECTED_QUESTION_COUNT - answered,
    duration: formatDuration(record)
  }
})

// 只有总分这条线，取最近 4 场
const trendPoints = computed(() => {
  const categories = chart.value.categories || []
  const overall = (chart.value.series || []).find((item) => item.key === 'overall')
  if (!overall) return []
  const points = categories
    .map((category, index) => ({ category, score: overall.data?.[index] }))
    .filter((item) => typeof item.score === 'number' && Number.isFinite(item.score))
  return points.slice(-4).map((item) => {
    const parsed = parseToShanghai(item.category)
    return { label: parsed ? parsed.format('MM/DD') : '', score: item.score }
  })
})

const weakDimensions = computed(() =>
  (profile.value.top_weakness_dimensions || []).slice(0, 3).map((item) => ({
    key: item.dimension_key,
    label: item.label,
    score: item.average_score,
    lowCount: item.low_score_count,
    isLow: Number(item.average_score) <= LOW_SCORE_THRESHOLD
  }))
)

const recentRecords = computed(() =>
  records.value.slice(0, 6).map((record) => {
    const parsed = parseToShanghai(record.updated_at || record.created_at)
    return {
      threadId: record.thread_id,
      title: `${record.position} · ${record.round}`,
      score: record.has_result ? record.overall_score : null,
      meta: [
        parsed ? parsed.format('MM/DD HH:mm') : '',
        record.interview_mode === 'voice' ? '语音' : '文本',
        `${record.question_count || 0} 题`
      ]
        .filter(Boolean)
        .join(' · '),
      raw: record
    }
  })
)

const currentPositionKey = computed(() => normalizePositionType(selectedPosition.value, positionTypes.value).key)

// 知识库按岗位自动挂载，这里只做展示：优先展示匹配当前岗位的，没有匹配则展示全部
const matchedKnowledge = computed(() => {
  const matched = knowledgeDatabases.value.filter((item) => {
    const position = String(item.position || '').trim()
    return !position || position === currentPositionKey.value || position === selectedPosition.value
  })
  const list = matched.length ? matched : knowledgeDatabases.value
  return {
    names: list.map((item) => item.name).filter(Boolean).join(' · '),
    fileCount: list.reduce((sum, item) => sum + Number(item.file_count || 0), 0)
  }
})

const canStartInterview = computed(() => Boolean(selectedResumeId.value))

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

const formatUpdatedAt = (value) => {
  const parsed = parseToShanghai(value)
  return parsed ? `更新于 ${parsed.format('M/D HH:mm')}` : ''
}

const startInterview = () => {
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  router.push({
    name: selectedInterviewMode.value === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode: selectedInterviewMode.value,
      position: selectedPosition.value,
      round: selectedRound.value,
      resumeId: String(selectedResumeId.value),
      session: `${Date.now()}`
    }
  })
}

const resumeRecord = (record) => {
  router.push({
    name: record.interview_mode === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode: record.interview_mode === 'voice' ? 'voice' : 'text',
      position: record.position,
      round: record.round,
      threadId: record.thread_id
    }
  })
}

const continueInterview = () => {
  if (!activeRecord.value) return
  resumeRecord(activeRecord.value)
}

const openRecord = (record) => {
  if (record.has_result) {
    router.push({
      name: 'InterviewResultPage',
      query: { threadId: record.thread_id, position: record.position, round: record.round }
    })
    return
  }
  resumeRecord(record)
}

const openExportRecords = () => router.push('/agent/records')
const openResumeCenter = () => router.push('/resume')

const loadResumes = async () => {
  const data = await resumeApi.getMyResumes()
  resumeOptions.value = Array.isArray(data?.resumes) ? data.resumes : []
  if (!resumeOptions.value.some((item) => item.id === selectedResumeId.value)) {
    selectedResumeId.value = resumeOptions.value[0]?.id || null
  }
}

const loadHistory = async () => {
  const payload = await interviewHistoryApi.getHistory({ userId: userStore.userId })
  historyPayload.value = {
    ...payload,
    records: (payload?.records || []).map((record) => ({
      ...record,
      title: decodeHtmlEntities(record.title),
      position: decodeHtmlEntities(record.position),
      round: decodeHtmlEntities(record.round)
    }))
  }
}

const loadKnowledgeDatabases = async () => {
  const data = await learnApi.getDatabases()
  knowledgeDatabases.value = Array.isArray(data?.databases) ? data.databases : []
}

onMounted(async () => {
  loading.value = true
  try {
    await loadPositionTypes()
    selectedPosition.value = normalizePositionType(selectedPosition.value, positionTypes.value).label
    await Promise.all([loadHistory(), loadResumes(), loadKnowledgeDatabases()])
  } catch (error) {
    message.error(error.message || '加载面试工作台数据失败')
  } finally {
    loading.value = false
  }
})
</script>

<style lang="less" scoped>
.wb-root {
  height: 100%;
  padding: 24px;
  color: var(--gray-1000);
}
</style>
