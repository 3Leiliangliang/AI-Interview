<template>
  <div class="records-home">
    <!-- 顶栏 -->
    <div class="page-topbar">
      <div class="topbar-left">
        <h1 class="page-title">面试记录</h1>
        <p class="page-subtitle">{{ subtitleText }}</p>
      </div>
      <div class="topbar-actions">
        <a-select
          v-if="userStore.isAdmin"
          v-model:value="selectedUserId"
          class="user-pick"
          :options="userOptions"
          :loading="usersLoading"
          placeholder="选择学生"
          show-search
          :filter-option="filterUserOption"
        />
        <a-button class="btn-secondary" :loading="loading" @click="loadHistory">刷新</a-button>
        <a-button class="btn-secondary" :disabled="!weakestDimension" @click="goPractice"
          >按弱项练习</a-button
        >
        <a-button type="primary" class="btn-primary" @click="startNewInterview"
          >开始新面试</a-button
        >
      </div>
    </div>

    <div class="page-body">
      <div v-if="loading" class="state-panel">
        <a-spin size="large" />
        <p>正在加载面试记录...</p>
      </div>

      <div v-else-if="!records.length" class="state-panel">
        <p class="state-panel__title">还没有面试记录</p>
        <p class="state-panel__hint">
          在工作台选择岗位与轮次并上传简历，完成第一场模拟面试后，成长轨迹与报告会出现在这里。
        </p>
        <a-button type="primary" class="btn-primary" @click="startNewInterview"
          >开始第一场面试</a-button
        >
      </div>

      <template v-else>
        <!-- 当前水平 + 成长轨迹 -->
        <section class="level-row">
          <div class="level-row__now">
            <div class="lab">当前水平</div>
            <div class="level-row__score">
              <span class="level-row__num">{{ latestScore ?? '--' }}</span>
              <span
                v-if="totalDelta !== null"
                class="level-row__delta"
                :class="{ down: totalDelta < 0 }"
              >
                {{ formatDelta(totalDelta) }}
              </span>
            </div>
            <p class="level-row__desc">{{ levelDescription }}</p>
          </div>
          <div class="level-row__trend">
            <div class="level-row__trend-hd">
              <span class="level-row__trend-title">成长轨迹</span>
              <div class="legend">
                <span class="legend__item"><i class="legend__line"></i>总分</span>
                <span class="legend__item"
                  ><i class="legend__line legend__line--dash"></i>初试通过线 {{ PASS_LINE }}</span
                >
              </div>
            </div>
            <div v-if="scoredRecords.length" ref="chartRef" class="trend-chart"></div>
            <p v-else class="trend-empty">完成并生成报告后，这里会显示总分随时间的变化。</p>
          </div>
        </section>

        <!-- 四维度 -->
        <section class="dim-row">
          <div
            v-for="dim in dimensionStats"
            :key="dim.key"
            class="dim-cell"
            :class="{ 'dim-cell--weak': dim.key === weakestDimension?.key }"
          >
            <div class="dim-cell__hd">
              <span class="dim-cell__label">{{ dim.label }}</span>
              <span
                v-if="dim.delta !== null"
                class="dim-cell__delta"
                :class="{ down: dim.delta < 0 }"
              >
                {{ formatDelta(dim.delta) }}
              </span>
            </div>
            <div class="dim-cell__body">
              <span class="dim-cell__num">{{ dim.latest ?? '--' }}</span>
              <svg
                v-if="dim.spark"
                class="dim-cell__spark"
                viewBox="0 0 120 34"
                preserveAspectRatio="none"
              >
                <polyline
                  :points="dim.spark"
                  fill="none"
                  stroke="var(--main-color)"
                  stroke-width="2"
                />
              </svg>
            </div>
            <div class="dim-cell__hint">{{ dim.hint }}</div>
          </div>
        </section>

        <!-- 成长里程碑 -->
        <section v-if="milestones.length" class="milestone">
          <div class="milestone__hd">
            <span class="lab">成长里程碑</span>
            <span class="milestone__hint">每一次提升对应的那一场面试</span>
          </div>
          <div class="milestone__grid">
            <div v-for="item in milestones" :key="item.key" class="milestone__cell">
              <div class="milestone__cell-hd">
                <span class="milestone__date">{{ formatShortTime(item.record.created_at) }}</span>
                <span class="milestone__title">{{ item.title }}</span>
                <span class="milestone__score" :class="{ highlight: item.highlight }">{{
                  item.record.overall_score
                }}</span>
              </div>
              <p class="milestone__desc">{{ item.desc }}</p>
            </div>
          </div>
        </section>

        <!-- 历史表 -->
        <section class="history">
          <div class="history__toolbar">
            <button
              type="button"
              :class="['opt', { on: activeTab === 'scored' }]"
              @click="activeTab = 'scored'"
            >
              已出报告 {{ scoredRecords.length }}
            </button>
            <button
              type="button"
              :class="['opt', { on: activeTab === 'unfinished' }]"
              @click="activeTab = 'unfinished'"
            >
              未完成 {{ unfinishedRecords.length }}
            </button>
            <div class="history__toolbar-spacer"></div>
            <a-select
              v-model:value="selectedPosition"
              class="flat-select"
              :bordered="false"
              size="small"
              :options="positionOptions"
            />
            <span class="tools-divider">·</span>
            <span class="tools-text">最近优先</span>
          </div>

          <table class="history__table">
            <thead>
              <tr>
                <th class="col-time">时间</th>
                <th class="col-round">轮次</th>
                <th class="col-mode">形式</th>
                <th class="col-weak">{{ activeTab === 'scored' ? '弱项' : '状态' }}</th>
                <th class="col-delta">相比上一场</th>
                <th class="col-score">总分</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in visibleRows"
                :key="row.record.thread_id"
                class="history__row"
                @click="openRecord(row.record)"
              >
                <td class="col-time">
                  <span class="history__time">{{ formatShortTime(row.record.created_at) }}</span>
                  <span class="history__note">{{ row.note }}</span>
                </td>
                <td>{{ row.record.round }}</td>
                <td>{{ getInterviewModeLabel(row.record.interview_mode) }}</td>
                <td :class="{ muted: !row.weakText }">{{ row.weakText || '尚未评分' }}</td>
                <td :class="row.deltaClass">{{ row.deltaText }}</td>
                <td
                  class="col-score"
                  :class="{
                    muted:
                      row.record.overall_score === null || row.record.overall_score === undefined
                  }"
                >
                  <span
                    v-if="
                      row.record.overall_score !== null && row.record.overall_score !== undefined
                    "
                    class="history__score"
                  >
                    {{ Math.round(row.record.overall_score) }}
                  </span>
                  <span v-else>—</span>
                </td>
              </tr>
              <tr v-if="!visibleRows.length">
                <td colspan="6" class="history__empty">
                  {{
                    activeTab === 'scored'
                      ? '当前筛选下还没有已出报告的面试。'
                      : '当前筛选下没有未完成的面试。'
                  }}
                </td>
              </tr>
            </tbody>
          </table>

          <div class="history__ft">
            <span
              >共 {{ records.length }} 场面试，其中
              {{ unfinishedRecords.length }} 场未完成、未计入轨迹</span
            >
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { interviewHistoryApi } from '@/apis/interview_history'
import { useUserStore } from '@/stores/user'
import { parseToShanghai } from '@/utils/time'
import { decodeHtmlEntities } from '@/utils/html'

const PASS_LINE = 70

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const usersLoading = ref(false)
const historyPayload = ref(null)
const userOptions = ref([])
const selectedUserId = ref(null)
const userSelectionReady = ref(false)
const selectedPosition = ref('all')
const activeTab = ref('scored')
const chartRef = ref(null)
let chartInstance = null
let historyLoadSeq = 0

const records = computed(() => historyPayload.value?.records || [])
const targetUserLabel = computed(
  () =>
    String(historyPayload.value?.target_user?.username || userStore.username || '').trim() ||
    '当前用户'
)

// 按时间正序排列的、已出报告且有总分的记录：成长轨迹与所有对比都基于它
const scoredAsc = computed(() =>
  records.value
    .filter(
      (item) =>
        item.has_result &&
        typeof item.overall_score === 'number' &&
        Number.isFinite(item.overall_score)
    )
    .slice()
    .sort((l, r) => String(l.created_at || '').localeCompare(String(r.created_at || '')))
)
const scoredRecords = computed(() => scoredAsc.value.slice().reverse())
const unfinishedRecords = computed(() => {
  const scoredIds = new Set(scoredAsc.value.map((item) => item.thread_id))
  return records.value.filter((item) => !scoredIds.has(item.thread_id))
})

const latestScore = computed(() => {
  const last = scoredAsc.value[scoredAsc.value.length - 1]
  return last ? Math.round(last.overall_score) : null
})
const firstScore = computed(() =>
  scoredAsc.value.length ? Math.round(scoredAsc.value[0].overall_score) : null
)
const totalDelta = computed(() =>
  scoredAsc.value.length >= 2 ? latestScore.value - firstScore.value : null
)
const passedCount = computed(
  () => scoredAsc.value.filter((item) => item.overall_score >= PASS_LINE).length
)

const subtitleText = computed(() => {
  if (!records.value.length) return `${targetUserLabel.value} · 还没有面试记录`
  if (!scoredAsc.value.length)
    return `${targetUserLabel.value} · ${records.value.length} 场面试 · 还没有已出报告的场次`
  return `${targetUserLabel.value} · ${scoredAsc.value.length} 场已出报告 · 首次 ${firstScore.value} 分，最新 ${latestScore.value} 分`
})

const levelDescription = computed(() => {
  if (!scoredAsc.value.length) return '完成一场面试并生成报告后，这里会显示你的当前水平。'
  if (scoredAsc.value.length === 1) return `首场 ${latestScore.value} 分，再面几场才能看出趋势。`
  const days = diffDays(
    scoredAsc.value[0].created_at,
    scoredAsc.value[scoredAsc.value.length - 1].created_at
  )
  const trend =
    totalDelta.value >= 0 ? `涨了 ${totalDelta.value} 分` : `掉了 ${Math.abs(totalDelta.value)} 分`
  const span = days > 0 ? `${days} 天内` : '至今'
  return `从首次 ${firstScore.value} 分起，${span}${trend}；${scoredAsc.value.length} 场已出报告，${passedCount.value} 场过线。`
})

const DIMENSION_KEYS = [
  { key: 'technical_competence', label: '技术能力' },
  { key: 'communication', label: '沟通表达' },
  { key: 'soft_skills', label: '综合素质' },
  { key: 'problem_solving', label: '问题解决' }
]

const dimensionStats = computed(() =>
  DIMENSION_KEYS.map(({ key, label }) => {
    const series = scoredAsc.value
      .map((record) => (record.dimensions || []).find((dim) => dim.key === key)?.score)
      .filter((score) => typeof score === 'number' && Number.isFinite(score))
    const latest = series.length ? Math.round(series[series.length - 1]) : null
    const delta = series.length >= 2 ? Math.round(series[series.length - 1] - series[0]) : null
    return {
      key,
      label,
      latest,
      delta,
      spark: buildSparkPoints(series),
      hint: buildDimensionHint(series, latest, delta)
    }
  })
)

const weakestDimension = computed(() => {
  const scored = dimensionStats.value.filter((dim) => dim.latest !== null)
  if (!scored.length) return null
  return scored.reduce((low, dim) => (dim.latest < low.latest ? dim : low))
})

const milestones = computed(() => {
  const list = scoredAsc.value
  if (!list.length) return []
  const items = []
  const push = (key, record, title, desc, highlight = false) => {
    if (!record || items.some((item) => item.record.thread_id === record.thread_id)) return
    items.push({
      key,
      record: { ...record, overall_score: Math.round(record.overall_score) },
      title,
      desc,
      highlight
    })
  }

  push(
    'first',
    list[0],
    '首次面试',
    `基线 ${Math.round(list[0].overall_score)} 分，后面每一场都和它比。`
  )

  let bestJump = null
  for (let i = 1; i < list.length; i += 1) {
    const gain = list[i].overall_score - list[i - 1].overall_score
    if (gain > 0 && (!bestJump || gain > bestJump.gain))
      bestJump = { record: list[i], gain: Math.round(gain) }
  }
  if (bestJump)
    push(
      'jump',
      bestJump.record,
      '涨幅最大',
      `相比上一场提升 ${bestJump.gain} 分，是目前效果最好的一次调整。`
    )

  const firstPass = list.find((item) => item.overall_score >= PASS_LINE)
  if (firstPass) push('pass', firstPass, '首次过线', `总分越过 ${PASS_LINE} 分通过线。`)

  const best = list.reduce((top, item) => (item.overall_score > top.overall_score ? item : top))
  const weakText = weakestDimension.value
    ? `；${weakestDimension.value.label}仍是 ${weakestDimension.value.latest} 分，下一步就练这块`
    : ''
  push('best', best, '目前最好', `${Math.round(best.overall_score)} 分${weakText}。`, true)

  return items
    .sort((l, r) =>
      String(l.record.created_at || '').localeCompare(String(r.record.created_at || ''))
    )
    .slice(0, 4)
})

const positionOptions = computed(() => {
  const positions = [
    ...new Set(records.value.map((item) => String(item.position || '').trim()).filter(Boolean))
  ]
  return [
    { label: '全部岗位', value: 'all' },
    ...positions.map((item) => ({ label: item, value: item }))
  ]
})

const matchPosition = (record) =>
  selectedPosition.value === 'all' ||
  String(record.position || '').trim() === selectedPosition.value

const scoredRows = computed(() => {
  const indexInAsc = new Map(scoredAsc.value.map((item, index) => [item.thread_id, index]))
  return scoredRecords.value.filter(matchPosition).map((record) => {
    const index = indexInAsc.get(record.thread_id)
    const previous = index > 0 ? scoredAsc.value[index - 1] : null
    const delta = previous ? Math.round(record.overall_score - previous.overall_score) : null
    const weakest = pickWeakestDimension(record)
    return {
      record,
      note: buildRowNote(record, index),
      weakText: weakest ? `${weakest.label} ${Math.round(weakest.score)}` : '',
      deltaText: delta === null ? '基准' : formatDelta(delta),
      deltaClass: delta === null ? 'muted' : delta >= 0 ? 'up' : 'down'
    }
  })
})

const unfinishedRows = computed(() =>
  unfinishedRecords.value.filter(matchPosition).map((record) => ({
    record,
    note: '',
    weakText: getStatusLabel(record.status),
    deltaText: '—',
    deltaClass: 'muted'
  }))
)

const visibleRows = computed(() =>
  activeTab.value === 'scored' ? scoredRows.value : unfinishedRows.value
)

function buildSparkPoints(series) {
  if (series.length < 2) return ''
  const min = Math.min(...series)
  const max = Math.max(...series)
  const range = max - min || 1
  const step = 112 / (series.length - 1)
  return series
    .map(
      (score, index) =>
        `${(4 + index * step).toFixed(1)},${(30 - ((score - min) / range) * 26).toFixed(1)}`
    )
    .join(' ')
}

function buildDimensionHint(series, latest, delta) {
  if (!series.length) return '暂无评分数据'
  if (series.length === 1) return '仅一场数据，暂无趋势'
  const rising = series.slice(1).every((score, index) => score >= series[index])
  if (rising && delta > 0) return `${series.length} 场持续上升`
  if (Math.abs(delta) <= 2) return `${series.length} 场几乎没动`
  if (latest >= 80) return '已稳定在 80 以上'
  return delta > 0 ? `累计提升 ${delta} 分` : `较首场回落 ${Math.abs(delta)} 分`
}

function pickWeakestDimension(record) {
  const dims = (record.dimensions || []).filter(
    (dim) => typeof dim.score === 'number' && Number.isFinite(dim.score)
  )
  if (!dims.length) return null
  return dims.reduce((low, dim) => (dim.score < low.score ? dim : low))
}

function buildRowNote(record, index) {
  const list = scoredAsc.value
  if (index === 0) return '首次面试 · 基线'
  const best = list.reduce((top, item) => (item.overall_score > top.overall_score ? item : top))
  if (best.thread_id === record.thread_id) return '目前最好的一场'
  const weakest = pickWeakestDimension(record)
  return weakest && weakest.score < PASS_LINE ? `${weakest.label}偏弱` : ''
}

function diffDays(from, to) {
  const start = parseToShanghai(from)
  const end = parseToShanghai(to)
  if (!start || !end) return 0
  return Math.max(0, end.startOf('day').diff(start.startOf('day'), 'day'))
}

const formatDelta = (value) => (value >= 0 ? `↑ ${value}` : `↓ ${Math.abs(value)}`)
const formatShortTime = (value) => {
  const parsed = parseToShanghai(value)
  return parsed ? parsed.format('MM/DD HH:mm') : '--'
}
const getStatusLabel = (status) =>
  ({ in_progress: '进行中', generating: '报告生成中', completed: '已完成', failed: '生成失败' })[
    status
  ] || '进行中'
const getInterviewModeLabel = (mode) => (String(mode || '').trim() === 'voice' ? '语音' : '文本')
const filterUserOption = (input, option) =>
  String(option?.label || '')
    .toLowerCase()
    .includes(String(input || '').toLowerCase())

const buildChartOption = () => {
  const scores = scoredAsc.value.map((item) => Math.round(item.overall_score))
  return {
    grid: { left: 34, right: 16, top: 22, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#ffffff',
      borderColor: '#dfe4ea',
      borderRadius: 0,
      textStyle: { color: '#10161d', fontSize: 12 }
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: scoredAsc.value.map((item) => formatShortTime(item.created_at)),
      axisLine: { lineStyle: { color: '#dfe4ea' } },
      axisTick: { show: false },
      axisLabel: { color: '#5a6672', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      min: Math.min(40, Math.floor((Math.min(...scores) - 10) / 10) * 10),
      max: 100,
      interval: 20,
      splitLine: { lineStyle: { color: '#eef2f6' } },
      axisLabel: { color: '#98a2ac', fontSize: 11 }
    },
    series: [
      {
        type: 'line',
        data: scores,
        symbol: 'rect',
        symbolSize: 8,
        lineStyle: { width: 2, color: '#3781cf' },
        itemStyle: { color: '#3781cf' },
        areaStyle: { color: 'rgba(55, 129, 207, 0.08)' },
        label: { show: true, position: 'top', fontSize: 12, fontWeight: 700, color: '#10161d' },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ yAxis: PASS_LINE }],
          lineStyle: { color: '#98a2ac', type: 'dashed', width: 1 },
          label: { show: false }
        }
      }
    ]
  }
}

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value || !scoredAsc.value.length) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption(buildChartOption(), true)
}

const loadUsers = async () => {
  if (!userStore.isAdmin) return
  usersLoading.value = true
  try {
    const users = await userStore.getUsers()
    const currentId = Number(userStore.userId)
    userOptions.value = (users || [])
      .filter((item) => item.role === 'user' || item.id === currentId)
      .map((item) => ({ label: item.username, value: item.id }))
  } catch (error) {
    message.error(error.message)
  } finally {
    usersLoading.value = false
  }
}

const loadHistory = async () => {
  const requestSeq = ++historyLoadSeq
  loading.value = true
  // loading 期间图表容器会被卸载，先销毁实例避免复用到已脱离文档的节点
  chartInstance?.dispose()
  chartInstance = null
  try {
    const userId = userStore.isAdmin ? selectedUserId.value : userStore.userId
    const payload = await interviewHistoryApi.getHistory({ userId })
    if (requestSeq !== historyLoadSeq) return
    const normalized = (payload?.records || []).map((item) => ({
      ...item,
      title: decodeHtmlEntities(item?.title),
      position: decodeHtmlEntities(item?.position),
      round: decodeHtmlEntities(item?.round)
    }))
    historyPayload.value = { ...payload, records: normalized }
    selectedPosition.value = 'all'
  } catch (error) {
    if (requestSeq !== historyLoadSeq) return
    message.error(error.message)
  } finally {
    if (requestSeq === historyLoadSeq) {
      loading.value = false
      // 图表容器在 loading 结束后才挂载，需等 DOM 更新完再初始化
      await nextTick()
      await renderChart()
    }
  }
}

const openRecord = (record) => {
  if (record.has_result) {
    router.push({
      name: 'InterviewResultPage',
      query: { threadId: record.thread_id, position: record.position, round: record.round }
    })
    return
  }
  const isVoice = record.interview_mode === 'voice'
  router.push({
    name: isVoice ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      threadId: record.thread_id,
      mode: isVoice ? 'voice' : 'text',
      position: record.position,
      round: record.round
    }
  })
}
const startNewInterview = () => router.push({ name: 'InterviewWorkbench' })
const goPractice = () => router.push({ name: 'PracticeHomePage' })
const handleResize = () => chartInstance?.resize()

watch(selectedUserId, async (value, previous) => {
  if (!userSelectionReady.value || value === previous) return
  await loadHistory()
})
watch(scoredAsc, async (list) => {
  if (!list.length) {
    chartInstance?.dispose()
    chartInstance = null
    return
  }
  await renderChart()
})

onMounted(async () => {
  selectedUserId.value = userStore.userId
  if (userStore.isAdmin) await loadUsers()
  userSelectionReady.value = true
  await loadHistory()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped lang="less">
// 设计稿 [UI v3][2c0] 面试记录 · 一级
.records-home {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

// ===================== 顶栏 =====================
.page-topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0;
  color: var(--gray-1000);
}

.page-subtitle {
  font-size: 13px;
  color: var(--gray-500);
  margin: 6px 0 0;
}

.topbar-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.user-pick {
  min-width: 150px;
}

.topbar-actions,
.state-panel {
  :deep(.btn-secondary.ant-btn) {
    display: inline-flex;
    align-items: center;
    height: 34px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid var(--gray-200);
    background: var(--gray-0);
    color: var(--gray-700);
    border-radius: 0;
    box-shadow: none;

    &:hover,
    &:focus {
      border-color: var(--gray-500) !important;
      color: var(--gray-1000) !important;
    }
  }

  :deep(.btn-primary.ant-btn) {
    display: inline-flex;
    align-items: center;
    height: 34px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 0;
    background: var(--main-color);
    border-color: var(--main-color);
    color: #fff;
    box-shadow: none;

    &:hover,
    &:focus {
      background: var(--main-700) !important;
      border-color: var(--main-700) !important;
      color: #fff !important;
    }
  }

  :deep(.ant-btn[disabled]) {
    background: var(--gray-100);
    border-color: var(--gray-200);
    color: var(--gray-500);
  }
}

// ===================== 主体 =====================
.page-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 0 32px 32px;
}

.lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
  white-space: nowrap;
}

.state-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 96px 24px;
  text-align: center;

  p {
    margin: 0;
    font-size: 13px;
    color: var(--gray-500);
  }

  .state-panel__title {
    font-size: 16px;
    font-weight: 700;
    color: var(--gray-1000);
  }

  .state-panel__hint {
    max-width: 420px;
    line-height: 1.7;
  }
}

// ===================== 当前水平 + 成长轨迹 =====================
.level-row {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  border-bottom: 1px solid var(--gray-200);
}

.level-row__now {
  padding: 16px 24px 16px 0;
  border-right: 1px solid var(--gray-100);
}

.level-row__score {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-top: 4px;
}

.level-row__num {
  font-size: 44px;
  line-height: 0.95;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--gray-1000);
}

.level-row__delta {
  font-size: 15px;
  font-weight: 700;
  color: var(--main-800);

  &.down {
    color: var(--gray-500);
  }
}

.level-row__desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-600);
  margin: 8px 0 0;
}

.level-row__trend {
  padding: 16px 0 14px 30px;
}

.level-row__trend-hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.level-row__trend-title {
  font-size: 17px;
  font-weight: 800;
  color: var(--gray-1000);
}

.legend {
  display: flex;
  gap: 18px;
  font-size: 12px;
  color: var(--gray-600);
}

.legend__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend__line {
  width: 14px;
  height: 2px;
  background: var(--main-color);

  &--dash {
    height: 0;
    background: transparent;
    border-top: 1px dashed var(--gray-500);
  }
}

.trend-chart {
  width: 100%;
  height: 140px;
  margin-top: 6px;
}

.trend-empty {
  font-size: 13px;
  color: var(--gray-500);
  margin: 24px 0;
}

// ===================== 四维度 =====================
.dim-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-bottom: 1px solid var(--gray-200);
}

.dim-cell {
  padding: 16px 20px;
  border-right: 1px solid var(--gray-100);

  &:first-child {
    padding-left: 0;
  }

  &:last-child {
    padding-right: 0;
    border-right: none;
  }

  &--weak {
    background: var(--gray-25);

    .dim-cell__num {
      color: var(--main-color);
    }
  }
}

.dim-cell__hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.dim-cell__label {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-1000);
}

.dim-cell__delta {
  font-size: 12px;
  font-weight: 700;
  color: var(--main-800);

  &.down {
    color: var(--gray-500);
  }
}

.dim-cell__body {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-top: 8px;
}

.dim-cell__num {
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  color: var(--gray-1000);
}

.dim-cell__spark {
  flex: 1;
  min-width: 0;
  height: 34px;
}

.dim-cell__hint {
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 6px;
}

// ===================== 成长里程碑 =====================
.milestone {
  border-bottom: 1px solid var(--gray-200);
  padding: 16px 0 18px;
}

.milestone__hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.milestone__hint {
  font-size: 12px;
  color: var(--gray-500);
}

.milestone__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid var(--gray-100);
  margin-top: 12px;
}

.milestone__cell {
  padding: 12px 20px;
  border-right: 1px solid var(--gray-100);

  &:first-child {
    padding-left: 0;
  }

  &:last-child {
    padding-right: 0;
    border-right: none;
  }
}

.milestone__cell-hd {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.milestone__date {
  font-size: 12px;
  color: var(--gray-500);
}

.milestone__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-1000);
}

.milestone__score {
  font-size: 13px;
  font-weight: 800;
  color: var(--gray-1000);

  &.highlight {
    color: var(--main-800);
  }
}

.milestone__desc {
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-600);
  margin: 6px 0 0;
}

// ===================== 历史表 =====================
.history {
  padding: 14px 0 0;
}

.history__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.history__toolbar-spacer {
  flex: 1;
}

.opt {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 14px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  font-size: 13px;
  color: var(--gray-700);
  cursor: pointer;

  &.on {
    background: var(--gray-100);
    font-weight: 700;
    color: var(--gray-1000);
  }
}

.flat-select {
  min-width: 128px;

  :deep(.ant-select-selector) {
    padding-right: 0 !important;
  }

  :deep(.ant-select-selection-item) {
    font-size: 13px;
    color: var(--gray-600);
  }
}

.tools-divider {
  color: var(--gray-400);
  font-size: 13px;
}

.tools-text {
  font-size: 13px;
  color: var(--gray-600);
}

.history__table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 10px;

  th {
    text-align: left;
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--gray-500);
    font-weight: 700;
    padding: 9px 14px;
    border-bottom: 1px solid var(--gray-200);
  }

  td {
    font-size: 13px;
    padding: 11px 14px;
    border-bottom: 1px solid var(--gray-100);
    color: var(--gray-700);
  }

  th.col-time,
  td.col-time {
    padding-left: 0;
  }

  th.col-score,
  td.col-score {
    text-align: right;
    padding-right: 0;
  }

  .col-round,
  .col-mode {
    width: 90px;
  }

  .col-weak {
    width: 240px;
  }

  .col-delta {
    width: 120px;
  }

  .col-score {
    width: 80px;
  }
}

.history__row {
  cursor: pointer;

  &:hover td {
    background: var(--gray-25);
  }
}

.history__time {
  font-weight: 700;
  color: var(--gray-1000);
}

.history__note {
  font-size: 12px;
  color: var(--gray-500);
  margin-left: 10px;
}

.history__score {
  font-weight: 800;
  font-size: 16px;
  color: var(--gray-1000);
}

.history__empty {
  text-align: center;
  color: var(--gray-500);
  padding: 32px 0;
}

.history__ft {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0 0;
  font-size: 13px;
  color: var(--gray-500);
}

td.muted,
.history__table td.muted {
  color: var(--gray-500);
}

td.up {
  font-weight: 700;
  color: var(--main-800);
}

td.down {
  font-weight: 700;
  color: var(--gray-500);
}

@media (max-width: 1200px) {
  .level-row {
    grid-template-columns: 1fr;
  }

  .level-row__now {
    padding: 16px 0;
    border-right: none;
    border-bottom: 1px solid var(--gray-100);
  }

  .level-row__trend {
    padding: 16px 0;
  }

  .dim-row,
  .milestone__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dim-cell:nth-child(2n),
  .milestone__cell:nth-child(2n) {
    padding-right: 0;
    border-right: none;
  }

  .dim-cell:nth-child(2n + 1),
  .milestone__cell:nth-child(2n + 1) {
    padding-left: 0;
  }
}
</style>
