<template>
  <div class="wb-root">
    <header class="wb-top">
      <div>
        <h1 class="wb-title">面试工作台</h1>
        <p class="wb-sub">{{ headerSummary }}</p>
      </div>
      <div class="wb-top-actions">
        <button class="wb-btn" type="button" @click="openExportRecords">导出记录</button>
        <button class="wb-btn wb-btn--primary" type="button" :disabled="!activeRecord" @click="continueInterview">
          继续面试
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

          <button class="wb-btn wb-btn--primary wb-btn--start" type="button" :disabled="!canStartInterview" @click="startInterview">
            开始面试
          </button>
        </div>
      </section>

      <!-- 中栏 · 主线 -->
      <section class="wb-col wb-col--main">
        <div v-if="activeRecord" class="wb-active" @click="continueInterview">
          <div class="wb-lab wb-lab--accent">进行中</div>
          <div class="wb-active-title">{{ activeRecord.position }} · {{ activeRecord.round }}</div>
          <div class="wb-active-meta">
            已回答 {{ activeProgress.answered }} / {{ activeProgress.total }} 题
            <template v-if="activeProgress.duration"> · 用时 {{ activeProgress.duration }}</template>
          </div>
          <div class="wb-bar">
            <div class="wb-bar-done" :style="{ flex: activeProgress.answered || 0.01 }"></div>
            <div class="wb-bar-rest" :style="{ flex: activeProgress.remaining || 0.01 }"></div>
          </div>
        </div>
        <div v-else class="wb-active wb-active--empty">
          <div class="wb-lab">进行中</div>
          <div class="wb-active-title wb-active-title--empty">还没有进行中的面试</div>
          <div class="wb-active-meta">在左侧选好岗位与简历，点「开始面试」即可开始一轮。</div>
        </div>

        <div class="wb-block">
          <div class="wb-lab">能力趋势 · 近 {{ trendPoints.length || 4 }} 场</div>
          <svg v-if="trendPoints.length >= 2" class="wb-chart" viewBox="0 0 560 200" preserveAspectRatio="none">
            <line x1="40" x2="550" y1="20" y2="20" class="wb-chart-grid" />
            <line x1="40" x2="550" y1="70" y2="70" class="wb-chart-grid" />
            <line x1="40" x2="550" y1="120" y2="120" class="wb-chart-grid" />
            <line x1="40" x2="550" y1="170" y2="170" class="wb-chart-axis" />
            <text x="30" y="24" text-anchor="end" class="wb-chart-tick">100</text>
            <text x="30" y="74" text-anchor="end" class="wb-chart-tick">75</text>
            <text x="30" y="124" text-anchor="end" class="wb-chart-tick">50</text>
            <polyline :points="trendPolyline" class="wb-chart-line" />
            <rect
              v-for="(point, index) in trendCoords"
              :key="`dot-${index}`"
              :x="point.x - 4"
              :y="point.y - 4"
              width="8"
              height="8"
              class="wb-chart-dot"
            />
            <text
              v-for="(point, index) in trendCoords"
              :key="`label-${index}`"
              :x="point.x"
              y="192"
              text-anchor="middle"
              class="wb-chart-label"
            >
              {{ point.label }}
            </text>
          </svg>
          <div v-else class="wb-empty">完成至少 2 场并生成报告后，这里会显示能力趋势。</div>
        </div>

        <div class="wb-block">
          <div class="wb-lab">反复偏弱</div>
          <div v-if="weakDimensions.length" class="wb-weak">
            <div v-for="item in weakDimensions" :key="item.key" class="wb-weak-cell">
              <div class="wb-weak-label">{{ item.label }}</div>
              <div class="wb-weak-score" :class="{ 'is-low': item.isLow }">{{ item.score }}</div>
              <div class="wb-weak-hint">低分 {{ item.lowCount }} 次</div>
            </div>
          </div>
          <div v-else class="wb-empty">还没有足够数据判断薄弱维度。</div>
        </div>
      </section>

      <!-- 右栏 · 最近记录 -->
      <section class="wb-col wb-col--right">
        <div class="wb-lab">最近记录</div>
        <div v-if="recentRecords.length" class="wb-records">
          <button
            v-for="item in recentRecords"
            :key="item.threadId"
            type="button"
            class="wb-record"
            @click="openRecord(item.raw)"
          >
            <div class="wb-record-hd">
              <span class="wb-record-title">{{ item.title }}</span>
              <span v-if="item.score !== null && item.score !== undefined" class="wb-record-score">
                {{ Math.round(item.score) }}
              </span>
              <span v-else class="wb-record-undone">未完成</span>
            </div>
            <div class="wb-record-meta">{{ item.meta }}</div>
          </button>
        </div>
        <div v-else class="wb-empty">还没有面试记录。</div>
      </section>
    </div>
  </div>
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

// SVG viewBox 为 0 0 560 200：x 从 80 起、点距 150；y 轴 50 分→170，100 分→20
const trendCoords = computed(() =>
  trendPoints.value.map((point, index) => ({
    x: 80 + index * 150,
    y: 170 - ((Math.min(100, Math.max(50, point.score)) - 50) / 50) * 150,
    label: point.label
  }))
)

const trendPolyline = computed(() => trendCoords.value.map((point) => `${point.x},${point.y}`).join(' '))

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
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: var(--gray-1000);
}

.wb-top {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 2px solid var(--gray-1000);
}
.wb-title { margin: 0; font-size: 22px; font-weight: 800; }
.wb-sub { margin: 4px 0 0; font-size: 13px; color: var(--gray-600); }
.wb-top-actions { display: flex; gap: 12px; flex: 0 0 auto; }

.wb-btn {
  height: 34px;
  padding: 0 16px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: transparent;
  color: var(--gray-1000);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  &:disabled { color: var(--gray-500); cursor: not-allowed; }
}
.wb-btn--primary {
  border-color: var(--main-color);
  background: var(--main-color);
  color: #fff;
  &:disabled { border-color: var(--gray-200); background: var(--gray-100); color: var(--gray-500); }
}
.wb-btn--start { width: 100%; height: 46px; justify-content: flex-start; }

.wb-grid {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 340px 1fr 320px;
  min-height: 0;
}
.wb-col { padding: 24px; overflow-y: auto; min-width: 0; }
.wb-col--left, .wb-col--main { border-right: 1px solid var(--gray-100); }
.wb-col--main { display: flex; flex-direction: column; gap: 22px; }

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
  color: var(--main-color);
  font-size: 13px;
  cursor: pointer;
}

.wb-active {
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  padding: 22px 24px;
  cursor: pointer;
}
.wb-active--empty { cursor: default; }
.wb-active-title { font-size: 26px; font-weight: 800; margin: 10px 0 6px; }
.wb-active-title--empty { font-size: 18px; font-weight: 700; color: var(--gray-600); }
.wb-active-meta { font-size: 13px; color: var(--gray-600); }
.wb-bar { display: flex; gap: 2px; margin-top: 18px; }
.wb-bar-done { height: 8px; background: var(--main-color); }
.wb-bar-rest { height: 8px; background: var(--gray-100); }

.wb-block { display: flex; flex-direction: column; gap: 10px; }
.wb-chart { width: 100%; height: 210px; }
.wb-chart-grid { stroke: var(--gray-200); }
.wb-chart-axis { stroke: var(--gray-1000); stroke-width: 2; }
.wb-chart-tick, .wb-chart-label { font-size: 11px; fill: var(--gray-500); }
.wb-chart-label { fill: var(--gray-600); }
.wb-chart-line { fill: none; stroke: var(--main-color); stroke-width: 2; }
.wb-chart-dot { fill: var(--main-color); }

.wb-weak {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--gray-200);
}
.wb-weak-cell {
  padding: 14px 16px;
  &:not(:last-child) { border-right: 1px solid var(--gray-100); }
  &:first-child { padding-left: 0; }
  &:last-child { padding-right: 0; }
}
.wb-weak-label { font-size: 13px; color: var(--gray-600); }
.wb-weak-score { font-size: 28px; font-weight: 800; margin-top: 4px; }
.wb-weak-score.is-low { color: var(--main-color); }
.wb-weak-hint { font-size: 12px; color: var(--gray-500); }

.wb-records { display: flex; flex-direction: column; margin-top: 14px; }
.wb-record {
  width: 100%;
  padding: 14px 0;
  border: none;
  border-top: 1px solid var(--gray-100);
  background: none;
  text-align: left;
  cursor: pointer;
  &:first-child { border-top-color: var(--gray-200); }
}
.wb-record-hd { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.wb-record-title { font-size: 15px; font-weight: 700; color: var(--gray-1000); }
.wb-record-score { font-size: 19px; font-weight: 800; color: var(--gray-1000); }
.wb-record-undone { font-size: 13px; color: var(--gray-500); }
.wb-record-meta { font-size: 12px; color: var(--gray-500); margin-top: 5px; }
</style>
