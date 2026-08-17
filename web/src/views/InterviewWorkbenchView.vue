<template>
  <div class="wb-root">
    <header class="wb-top">
      <div>
        <h1 class="wb-title">开始面试</h1>
        <p class="wb-sub">{{ headerSummary }}</p>
      </div>
      <div class="wb-top-actions">
        <button class="wb-btn" type="button" @click="openRecords">面试记录</button>
        <button
          class="wb-btn wb-btn--primary"
          type="button"
          :disabled="!activeRecord"
          @click="continueInterview"
        >
          继续未结束的面试
        </button>
      </div>
    </header>

    <div class="wb-grid">
      <!-- 左栏 · 新面试配置 -->
      <section class="wb-col wb-col--left">
        <div class="wb-lab">新面试配置</div>
        <div class="wb-config">
          <div class="wb-field">
            <div class="wb-lab">形式</div>
            <div class="wb-seg">
              <button
                v-for="item in interviewModeOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedInterviewMode === item.value }"
                @click="selectedInterviewMode = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">岗位</div>
            <div class="wb-seg wb-seg--wrap">
              <button
                v-for="item in positionTypeOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedPosition === item.value }"
                @click="selectedPosition = item.value"
              >
                {{ item.shortLabel }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">轮次</div>
            <div class="wb-seg">
              <button
                v-for="item in roundOptions"
                :key="item.value"
                type="button"
                class="wb-opt"
                :class="{ 'is-on': selectedRound === item.value }"
                @click="selectedRound = item.value"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">简历</div>
            <template v-if="resumeOptions.length">
              <button
                v-for="item in resumeOptions"
                :key="item.id"
                type="button"
                class="wb-opt wb-opt--block"
                :class="{ 'is-on': selectedResumeId === item.id }"
                @click="selectedResumeId = item.id"
              >
                <span class="wb-opt-title">{{ item.filename }}</span>
                <span class="wb-opt-meta">
                  {{ formatFileSize(item.file_size) }} · {{ formatUpdatedAt(item.updated_at || item.created_at) }}
                </span>
              </button>
            </template>
            <div v-else class="wb-empty">
              还没有已上传简历
              <button class="wb-link" type="button" @click="openResumeCenter">去上传</button>
            </div>
          </div>

          <div class="wb-field">
            <div class="wb-lab">出题知识库</div>
            <div class="wb-kb">
              <span class="wb-kb-name">{{ matchedKnowledge.names || '按岗位自动匹配' }}</span>
              <span v-if="matchedKnowledge.fileCount" class="wb-kb-count">{{ matchedKnowledge.fileCount }} 文件</span>
            </div>
          </div>

          <button
            class="wb-btn wb-btn--primary wb-btn--start"
            type="button"
            :disabled="!canStartInterview"
            @click="startInterview"
          >
            开始面试
          </button>
        </div>
      </section>

      <!-- 右栏 · 主线 -->
      <section class="wb-col wb-col--main">
        <div v-if="activeRecord" class="wb-active">
          <div class="wb-active-info">
            <div class="wb-lab wb-lab--accent">未结束</div>
            <div class="wb-active-title">{{ activeRecord.position }} · {{ activeRecord.round }}</div>
            <div class="wb-active-meta">
              <template v-if="activeProgress.questionCount">停在第 {{ activeProgress.questionCount }} 问 · </template>
              已答 {{ activeProgress.answered }} / {{ activeProgress.total }} 题
              <template v-if="activeProgress.duration"> · 用时 {{ activeProgress.duration }}</template>
            </div>
            <div class="wb-bar">
              <div class="wb-bar-done" :style="{ flex: activeProgress.answered || 0.01 }"></div>
              <div class="wb-bar-rest" :style="{ flex: activeProgress.remaining || 0.01 }"></div>
            </div>
          </div>
          <div class="wb-active-actions">
            <button class="wb-btn wb-btn--primary" type="button" @click="continueInterview">继续面试</button>
            <button class="wb-btn" type="button" @click="finishAndReport">直接结束并出报告</button>
          </div>
        </div>
        <div v-else class="wb-active wb-active--empty">
          <div class="wb-active-info">
            <div class="wb-lab">未结束</div>
            <div class="wb-active-title wb-active-title--empty">没有未结束的面试</div>
            <div class="wb-active-meta">在左侧选好岗位与简历，或从下面的快速开始直接进入。</div>
          </div>
        </div>

        <div class="wb-block">
          <div class="wb-block-hd">
            <span class="wb-lab">快速开始</span>
            <span class="wb-block-hint">选一个直接进面试，不用改左边的配置</span>
          </div>
          <div class="wb-quick">
            <button
              v-for="card in quickStartCards"
              :key="card.key"
              type="button"
              class="wb-quick-card"
              :class="{ 'is-disabled': card.disabled }"
              :disabled="card.disabled"
              @click="runQuickStart(card)"
            >
              <div class="wb-quick-hd">
                <span class="wb-quick-title">{{ card.title }}</span>
                <span class="wb-badge" :class="{ 'is-accent': card.accent }">{{ card.badge }}</span>
              </div>
              <div class="wb-quick-desc">{{ card.desc }}</div>
            </button>
          </div>
        </div>

        <div class="wb-block">
          <div class="wb-lab">面试前检查</div>
          <div class="wb-check">
            <div v-for="item in preflightChecks" :key="item.key" class="wb-check-row">
              <span class="wb-check-label">{{ item.label }}</span>
              <span class="wb-check-state" :class="{ 'is-ready': item.ready }">{{ item.text }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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

const router = useRouter()
const route = useRoute()
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

const activeRecord = computed(() => records.value.find((item) => item.status === 'in_progress') || null)

const formatDuration = (record) => {
  const start = parseToShanghai(record.created_at)
  const end = parseToShanghai(record.updated_at)
  if (!start || !end) return ''
  const minutes = Math.floor(end.diff(start, 'minute'))
  return minutes < 1 ? '不到 1 分钟' : `${minutes} 分钟`
}

const lastRecord = computed(() => records.value[0] || null)

const lastScoredRecord = computed(
  () =>
    records.value.find((item) => item.has_result && typeof item.overall_score === 'number') || null
)

const headerSummary = computed(() => {
  const scoreText = lastScoredRecord.value
    ? `上次得分 ${Math.round(lastScoredRecord.value.overall_score)}`
    : ''
  if (activeRecord.value) {
    return scoreText ? `有一场未结束的面试 · ${scoreText}` : '有一场未结束的面试'
  }
  return scoreText || '还没有面试记录'
})

const activeProgress = computed(() => {
  const record = activeRecord.value
  if (!record) return null
  const answered = Math.min(Number(record.answered_count || 0), EXPECTED_QUESTION_COUNT)
  return {
    answered,
    total: EXPECTED_QUESTION_COUNT,
    remaining: EXPECTED_QUESTION_COUNT - answered,
    questionCount: Number(record.question_count || 0),
    duration: formatDuration(record)
  }
})

const selectedResume = computed(
  () => resumeOptions.value.find((item) => item.id === selectedResumeId.value) || null
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

const preflightChecks = computed(() => {
  const resume = selectedResume.value
  let resumeState = { text: '未选择', ready: false }
  if (resume?.summary_status === 'completed') {
    resumeState = { text: '就绪', ready: true }
  } else if (resume?.summary_status === 'failed') {
    resumeState = { text: '解析失败', ready: false }
  } else if (resume) {
    resumeState = { text: '解析中', ready: false }
  }

  const fileCount = matchedKnowledge.value.fileCount
  return [
    { key: 'resume', label: '简历已解析完成，项目经历可被追问', ...resumeState },
    {
      key: 'knowledge',
      label: fileCount
        ? `出题知识库 ${matchedKnowledge.value.names} 已索引 ${fileCount} 个文件`
        : '出题知识库尚未配置',
      text: fileCount ? '就绪' : '未配置',
      ready: Boolean(fileCount)
    },
    { key: 'mic', label: '语音面试需要麦克风权限', text: '选语音时再申请', ready: false }
  ]
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

const pushInterview = ({ mode, position, round }) => {
  router.push({
    name: mode === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode,
      position,
      round,
      resumeId: String(selectedResumeId.value),
      session: `${Date.now()}`
    }
  })
}

const startInterview = () => {
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  pushInterview({
    mode: selectedInterviewMode.value,
    position: selectedPosition.value,
    round: selectedRound.value
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

const finishAndReport = () => {
  const record = activeRecord.value
  if (!record) return
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: record.thread_id,
      position: record.position,
      round: record.round,
      autoGenerate: '1'
    }
  })
}

const runQuickStart = (card) => {
  if (card.disabled) return
  if (!selectedResumeId.value) {
    message.warning('请先选择一份简历')
    return
  }
  pushInterview(card.config)
}

const quickStartCards = computed(() => [
  {
    key: 'reuse',
    title: '沿用上次配置',
    badge: lastRecord.value
      ? `${lastRecord.value.interview_mode === 'voice' ? '语音' : '文本'} · ${lastRecord.value.question_count || 0} 题`
      : '暂无记录',
    accent: false,
    desc: lastRecord.value
      ? [
          lastRecord.value.position,
          lastRecord.value.round,
          selectedResume.value?.filename || '未选择简历',
          matchedKnowledge.value.names
        ]
          .filter(Boolean)
          .join(' · ')
      : '完成一场面试后，这里会带出上次的岗位与轮次',
    disabled: !lastRecord.value,
    config: lastRecord.value
      ? {
          mode: lastRecord.value.interview_mode === 'voice' ? 'voice' : 'text',
          position: lastRecord.value.position,
          round: lastRecord.value.round
        }
      : null
  },
  {
    key: 'weakness',
    title: '按弱项出题',
    badge: '即将上线',
    accent: true,
    desc: '只问你反复失分的知识点',
    disabled: true,
    config: null
  },
  {
    key: 'voice',
    title: '语音复试',
    badge: '语音 · 复试',
    accent: false,
    desc: '带摄像头，练表达节奏与追问应对',
    disabled: false,
    config: { mode: 'voice', position: selectedPosition.value, round: '复试' }
  },
  {
    key: 'coding',
    title: '纯编程考核',
    badge: '即将上线',
    accent: false,
    desc: '跳过问答，直接做题并判题',
    disabled: true,
    config: null
  }
])

const openRecords = () => router.push('/agent/records')
const openResumeCenter = () => router.push('/resume')

const loadResumes = async () => {
  const data = await resumeApi.getMyResumes()
  resumeOptions.value = Array.isArray(data?.resumes) ? data.resumes : []
  const routeResumeId = Number(route.query.resumeId)
  if (Number.isFinite(routeResumeId) && resumeOptions.value.some((item) => item.id === routeResumeId)) {
    selectedResumeId.value = routeResumeId
    return
  }
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
    const routeMode = String(route.query.mode || '').trim()
    if (interviewModeOptions.some((item) => item.value === routeMode)) {
      selectedInterviewMode.value = routeMode
    }

    const routePosition = String(route.query.position || '').trim()
    selectedPosition.value = normalizePositionType(
      routePosition || selectedPosition.value,
      positionTypes.value
    ).label

    const routeRound = String(route.query.round || '').trim()
    if (roundOptions.some((item) => item.value === routeRound)) {
      selectedRound.value = routeRound
    }

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
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--gray-1000);
}

.wb-top {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--gray-100);
}
.wb-title { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.01em; }
.wb-sub { margin: 6px 0 0; font-size: 13px; color: var(--gray-500); }
.wb-top-actions { display: flex; gap: 12px; flex: 0 0 auto; }

.wb-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-700);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  &:disabled { color: var(--gray-500); cursor: not-allowed; }
}
.wb-btn--primary {
  border-color: var(--main-color);
  background: var(--main-color);
  color: #fff;
  &:disabled { border-color: var(--gray-200); background: var(--gray-100); color: var(--gray-500); }
}
.wb-btn--start { width: 100%; height: 46px; }

.wb-grid {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 340px 1fr;
  min-height: 0;
}
.wb-col { overflow-y: auto; min-width: 0; }
.wb-col--left { padding: 24px; border-right: 1px solid var(--gray-100); }
.wb-col--main { padding: 24px 32px; display: flex; flex-direction: column; gap: 26px; }

.wb-lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}
.wb-lab--accent { color: var(--main-700); }

.wb-config { margin-top: 20px; display: flex; flex-direction: column; gap: 20px; }
.wb-field { display: flex; flex-direction: column; gap: 8px; }

.wb-seg { display: flex; }
.wb-seg--wrap { flex-wrap: wrap; }
.wb-opt {
  flex: 1;
  min-width: 0;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-700);
  font-size: 13px;
  cursor: pointer;
  &:not(:first-child) { border-left: none; }
  &.is-on { background: var(--gray-100); color: var(--gray-1000); font-weight: 700; }
}
.wb-opt--block {
  flex: none;
  height: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
  & + .wb-opt--block { border-top: none; border-left: 1px solid var(--gray-200); }
}
.wb-opt-title { font-size: 13px; word-break: break-all; }
.wb-opt-meta { font-size: 12px; color: var(--gray-600); font-weight: 400; }

.wb-kb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--gray-200);
  font-size: 13px;
  color: var(--gray-700);
}
.wb-kb-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wb-kb-count { flex: 0 0 auto; font-size: 12px; color: var(--gray-500); }

.wb-empty { font-size: 13px; color: var(--gray-500); line-height: 1.7; }
.wb-link {
  border: none;
  background: none;
  padding: 0 0 0 6px;
  color: var(--gray-1000);
  text-decoration: underline;
  font-size: 13px;
  cursor: pointer;
}

.wb-active {
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  padding: 24px 26px;
  display: flex;
  align-items: center;
  gap: 28px;
}
.wb-active-info { flex: 1; min-width: 0; }
.wb-active-actions { display: flex; flex-direction: column; gap: 10px; flex: 0 0 auto; }
.wb-active-title { font-size: 26px; font-weight: 800; margin: 10px 0 6px; }
.wb-active-title--empty { font-size: 18px; font-weight: 700; color: var(--gray-600); }
.wb-active-meta { font-size: 13px; color: var(--gray-600); }
.wb-bar { display: flex; gap: 2px; margin-top: 16px; max-width: 420px; }
.wb-bar-done { height: 8px; background: var(--main-color); }
.wb-bar-rest { height: 8px; background: var(--gray-100); }

.wb-block { display: flex; flex-direction: column; gap: 10px; }
.wb-block-hd { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.wb-block-hint { font-size: 12px; color: var(--gray-500); }

.wb-quick {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 1px solid var(--gray-200);
  margin-top: 2px;
}
.wb-quick-card {
  border: none;
  background: none;
  text-align: left;
  cursor: pointer;
  padding: 18px 24px 18px 0;
  &:nth-child(odd) { border-right: 1px solid var(--gray-100); }
  &:nth-child(even) { padding: 18px 0 18px 24px; }
  &:nth-child(1),
  &:nth-child(2) { border-bottom: 1px solid var(--gray-100); }
  &.is-disabled { cursor: not-allowed; }
  &.is-disabled .wb-quick-title,
  &.is-disabled .wb-quick-desc { color: var(--gray-500); }
}
.wb-quick-hd { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.wb-quick-title { font-size: 16px; font-weight: 700; color: var(--gray-1000); }
.wb-quick-desc { font-size: 13px; color: var(--gray-600); margin-top: 7px; line-height: 1.6; }

.wb-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--gray-200);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--gray-600);
  flex: 0 0 auto;
  &.is-accent { border-color: var(--main-color); color: var(--main-700); }
}

.wb-check { font-size: 13px; line-height: 1.6; }
.wb-check-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 0;
  border-top: 1px solid var(--gray-100);
}
.wb-check-label { color: var(--gray-1000); }
.wb-check-state { flex: 0 0 auto; color: var(--gray-500); }
.wb-check-state.is-ready { color: var(--main-700); font-weight: 700; }
</style>
