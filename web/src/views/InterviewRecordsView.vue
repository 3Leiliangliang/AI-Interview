<template>
  <div class="interview-records-view">
    <div class="page-toolbar panel-card">
      <div>
        <div class="toolbar-title">面试记录</div>
        <div class="toolbar-subtitle">统一查看面试历史、配置标签与能力成长趋势</div>
      </div>

      <div class="toolbar-actions">
        <a-select
          v-if="userStore.isAdmin"
          v-model:value="selectedUserId"
          class="user-select"
          :options="userOptions"
          :loading="usersLoading"
          placeholder="选择学生"
          show-search
          :filter-option="filterUserOption"
        />
        <a-button :loading="loading" @click="loadHistory">
          <template #icon><SyncOutlined /></template>
          刷新数据
        </a-button>
      </div>
    </div>

    <div class="dashboard-grid">
      <div class="panel-card chart-card">
        <div class="section-header">
          <div>
            <div class="section-title">能力成长曲线</div>
            <div class="section-subtitle">
              {{ targetUserLabel }} · 基于已生成评分卡的历史面试结果
            </div>
          </div>
        </div>

        <div v-if="loading" class="state-panel compact">
          <a-spin />
        </div>
        <div v-else-if="!chartCategories.length" class="state-panel compact">
          <a-empty description="暂无可视化数据，完成几轮面试后会在这里展示成长曲线" />
        </div>
        <div v-else ref="chartRef" class="growth-chart"></div>
      </div>

      <div class="panel-card profile-card">
        <div class="section-header">
          <div>
            <div class="section-title">长期短板提醒</div>
            <div class="section-subtitle">最近 5 次已完成面试中的反复薄弱点</div>
          </div>
          <a-tag v-if="profile.pending_practice_count" color="purple">{{ profile.pending_practice_count }} 个待练习项</a-tag>
        </div>

        <div v-if="loading" class="state-panel compact">
          <a-spin />
        </div>
        <div v-else-if="!profile.top_weakness_dimensions?.length && !profile.latest_focus?.length" class="state-panel compact">
          <a-empty description="完成更多面试后分析短板" />
        </div>
        <div v-else class="profile-content">
          <div v-if="profile.top_weakness_dimensions?.length" class="profile-section">
            <div class="profile-section__title">反复偏弱维度</div>
            <div class="profile-chip-list">
              <div
                v-for="item in profile.top_weakness_dimensions"
                :key="item.dimension_key"
                class="profile-chip"
              >
                <div class="profile-chip__header">
                  <span class="profile-chip__title">{{ item.label }}</span>
                  <span class="profile-chip__score">{{ item.average_score }} 分</span>
                </div>
                <div class="profile-chip__meta">
                  低分出现 {{ item.low_score_count }} 次
                </div>
              </div>
            </div>
          </div>

          <div v-if="profile.latest_focus?.length" class="profile-section focus-section">
            <div class="profile-section__title">最近建议</div>
            <div class="profile-focus-list">
              <div v-for="item in profile.latest_focus" :key="`${item.dimension_key}-${item.title}`" class="profile-focus-item">
                <div class="profile-focus-item__title">{{ item.title }}</div>
                <div class="profile-focus-item__desc">{{ item.focus }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-card records-card">
      <div class="section-header">
        <div class="records-header-info">
          <div class="section-title">历史记录</div>
          <div class="section-subtitle">展示全部面试线程，成长曲线仅统计已完成结果</div>
        </div>
        <div class="records-stats">
          <div class="stat-item">
            <span class="stat-label">总面试</span>
            <span class="stat-value">{{ records.length }}</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-label">已完成</span>
            <span class="stat-value">{{ records.filter(r => r.status === 'completed').length }}</span>
          </div>
        </div>
      </div>

      <div v-if="loading" class="state-panel list-loading">
        <a-spin tip="加载记录中..." />
      </div>
      <div v-else-if="records.length === 0" class="state-panel empty-list">
        <a-empty description="暂无面试记录" />
      </div>
      <div v-else class="records-list">
        <div v-for="record in records" :key="record.thread_id" class="record-item">
          <div class="record-status-indicator" :class="record.status"></div>
          <div class="record-content">
            <div class="record-main-info">
              <div class="record-header-row">
                <div class="record-title-group">
                  <h3 class="record-title">{{ record.title || '未命名面试' }}</h3>
                  <div class="record-time-info">
                    <span class="time-item">更新：{{ formatDateTime(record.updated_at) }}</span>
                    <span class="time-separator">·</span>
                    <span class="time-item">创建：{{ formatDateTime(record.created_at) }}</span>
                  </div>
                </div>

                <div class="record-badge-group">
                  <a-tag class="tag-flat">{{ getInterviewModeLabel(record.interview_mode) }}</a-tag>
                  <a-tag class="tag-flat">{{ record.position }}</a-tag>
                  <a-tag class="tag-flat">{{ record.round }}</a-tag>
                  <a-tag :color="getStatusColor(record.status)" class="tag-status">
                    {{ getStatusLabel(record.status) }}
                  </a-tag>
                </div>
              </div>

              <div v-if="record.dimensions?.length" class="record-stats-section">
                <div class="record-overall-score">
                  <span class="score-num">{{ formatOverallScore(record.overall_score) }}</span>
                  <span class="score-unit">综合得分</span>
                </div>
                <div class="dimension-grid">
                  <div
                    v-for="dimension in record.dimensions"
                    :key="dimension.key"
                    class="dimension-stat"
                  >
                    <div class="dimension-line">
                      <span class="dim-label">{{ dimension.label }}</span>
                      <span class="dim-val">{{ formatDimensionScore(dimension.score) }}</span>
                    </div>
                    <div class="dim-progress-bg">
                      <div class="dim-progress-fill" :style="{ width: `${dimension.score}%` }"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="record-footer">
              <div class="footer-actions">
                <a-button @click="continueInterview(record)">
                  <template #icon><PlayCircleOutlined /></template>
                  继续面试
                </a-button>
                <a-button v-if="record.has_result" type="primary" @click="openInterviewResult(record)">
                  <template #icon><FileSearchOutlined /></template>
                  查看报告
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  SyncOutlined,
  PlayCircleOutlined,
  FileSearchOutlined
} from '@ant-design/icons-vue'

import { interviewHistoryApi } from '@/apis/interview_history'
import { useUserStore } from '@/stores/user'
import { formatDateTime, parseToShanghai } from '@/utils/time'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const usersLoading = ref(false)
const historyPayload = ref(null)
const userOptions = ref([])
const selectedUserId = ref(null)
const chartRef = ref(null)
const userSelectionReady = ref(false)

let chartInstance = null

const records = computed(() => historyPayload.value?.records || [])
const profile = computed(
  () =>
    historyPayload.value?.profile || {
      top_weakness_dimensions: [],
      latest_focus: [],
      pending_practice_count: 0
    }
)
const targetUser = computed(() => historyPayload.value?.target_user || null)
const chartCategories = computed(() => historyPayload.value?.chart?.categories || [])
const chartSeries = computed(() => historyPayload.value?.chart?.series || [])
const targetUserLabel = computed(() => {
  const username = String(targetUser.value?.username || userStore.username || '').trim()
  if (!username) return '当前用户'
  return username
})

const getStatusLabel = (status) => {
  const statusMap = {
    in_progress: '进行中',
    generating: '结果生成中',
    completed: '已完成',
    failed: '结果生成失败'
  }
  return statusMap[status] || status || '进行中'
}

const getStatusColor = (status) => {
  const colorMap = {
    in_progress: 'processing',
    generating: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colorMap[status] || 'default'
}

const getInterviewModeLabel = (mode) => {
  return String(mode || '').trim() === 'voice' ? '语音面试' : '文本面试'
}

const formatOverallScore = (score) => {
  if (typeof score !== 'number' || !Number.isFinite(score)) return '--'
  return `${Math.round(score)}`
}

const formatDimensionScore = (score) => {
  if (typeof score !== 'number' || !Number.isFinite(score)) return '--'
  return score
}

const filterUserOption = (input, option) => {
  const label = String(option?.label || '').toLowerCase()
  return label.includes(String(input || '').toLowerCase())
}

const loadUsers = async () => {
  if (!userStore.isAdmin) return
  usersLoading.value = true
  try {
    const users = await userStore.getUsers()
    const currentUserId = Number(userStore.userId)
    userOptions.value = (users || [])
      .filter((item) => item.role === 'user' || item.id === currentUserId)
      .map((item) => ({
        label: item.username,
        value: item.id
      }))
  } catch (error) {
    message.error(error.message || '加载用户列表失败')
  } finally {
    usersLoading.value = false
  }
}

const loadHistory = async () => {
  loading.value = true
  try {
    historyPayload.value = await interviewHistoryApi.getHistory({
      userId: userStore.isAdmin ? selectedUserId.value : userStore.userId
    })
  } catch (error) {
    message.error(error.message || '加载面试记录失败')
  } finally {
    loading.value = false
    if (!chartCategories.value.length) {
      chartInstance?.dispose()
      chartInstance = null
      return
    }
    await renderChart()
  }
}

const buildChartOption = () => {
  return {
    color: ['#1677ff', '#52c41a', '#faad14', '#722ed1', '#13c2c2'],
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      top: 0
    },
    grid: {
      left: 20,
      right: 40,
      top: 50,
      bottom: 20,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: chartCategories.value.map((item) => {
        const parsed = parseToShanghai(item)
        return parsed ? parsed.format('MM/DD HH:mm') : item
      })
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100
    },
    series: chartSeries.value.map((item) => ({
      name: item.label,
      type: 'line',
      smooth: true,
      showSymbol: true,
      connectNulls: false,
      data: item.data || []
    }))
  }
}

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value || !chartCategories.value.length) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  chartInstance.setOption(buildChartOption(), true)
}

const handleResize = () => {
  chartInstance?.resize()
}

const continueInterview = (record) => {
  router.push({
    name: record.interview_mode === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      threadId: record.thread_id,
      mode: record.interview_mode === 'voice' ? 'voice' : 'text',
      position: record.position,
      round: record.round
    }
  })
}

const openInterviewResult = (record) => {
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: record.thread_id,
      position: record.position,
      round: record.round
    }
  })
}

watch(
  () => selectedUserId.value,
  async (value, oldValue) => {
    if (!userSelectionReady.value) return
    if (value === oldValue) return
    await loadHistory()
  }
)

watch(
  () => historyPayload.value?.chart,
  async () => {
    if (!chartCategories.value.length) {
      chartInstance?.dispose()
      chartInstance = null
      return
    }
    await renderChart()
  },
  { deep: true }
)

onMounted(async () => {
  selectedUserId.value = userStore.userId
  if (userStore.isAdmin) {
    await loadUsers()
  }
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

<style lang="less" scoped>
.interview-records-view {
  min-height: 100%;
  width: 100%;
  padding: 24px;
  background: var(--gray-50);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.panel-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px var(--shadow-1);

  &:hover {
    box-shadow: 0 4px 12px var(--shadow-2);
  }
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.page-toolbar > :first-child {
  flex: 1 1 320px;
  min-width: 0;
}

.toolbar-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-900);
  line-height: 1.3;
}

.toolbar-subtitle {
  font-size: 13px;
  color: var(--gray-500);
  margin-top: 6px;
  line-height: 1.5;
  word-break: break-word;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 0 1 auto;
  flex-wrap: wrap;
  gap: 12px;
  margin-left: auto;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1.6fr 1.1fr;
  gap: 20px;
}

.section-header {
  padding: 20px 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-800);
}

.section-subtitle {
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 6px;
  line-height: 1.5;
}

.growth-chart {
  width: 100%;
  height: 320px;
  padding: 0 16px 20px;
}

.profile-content {
  padding: 0 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.profile-section__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-700);
  margin-bottom: 12px;
}

.profile-chip-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.profile-chip {
  padding: 12px;
  background: var(--main-40);
  border-radius: 12px;
  border: 1px solid var(--main-100);
}

.profile-chip__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.profile-chip__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--main-800);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.profile-chip__score {
  font-size: 13px;
  font-weight: 700;
  color: var(--main-600);
}

.profile-chip__meta {
  font-size: 11px;
  color: var(--main-500);
}

.profile-focus-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.profile-focus-item {
  padding: 12px;
  background: var(--gray-25);
  border-radius: 12px;
  border: 1px solid var(--gray-150);
}

.profile-focus-item__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
  margin-bottom: 4px;
}

.profile-focus-item__desc {
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.5;
}

/* Records List */
.records-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--gray-50);
  padding: 6px 16px;
  border-radius: 10px;
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 11px;
  color: var(--gray-500);
}

.stat-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-800);
}

.stat-divider {
  width: 1px;
  height: 20px;
  background: var(--gray-200);
}

.records-list {
  padding: 0 24px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.record-item {
  display: flex;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 14px;
  overflow: hidden;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px var(--shadow-1);
  }
}

.record-status-indicator {
  width: 4px;
  flex-shrink: 0;
  background: var(--gray-300);

  &.completed { background: var(--color-success-500); }
  &.in_progress { background: var(--main-400); }
  &.generating { background: var(--color-info-500); }
  &.failed { background: var(--color-error-500); }
}

.record-content {
  flex: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.record-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.record-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-900);
  margin: 0;
}

.record-time-info {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-item {
  font-size: 12px;
  color: var(--gray-500);
}

.time-separator {
  color: var(--gray-300);
}

.record-badge-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag-flat {
  margin: 0;
  border: none;
  background: var(--gray-100);
  color: var(--gray-600);
  border-radius: 4px;
  padding: 2px 10px;
}

.record-stats-section {
  display: flex;
  align-items: center;
  gap: 32px;
  background: var(--gray-25);
  padding: 16px;
  border-radius: 12px;
}

.record-overall-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  text-align: center;
}

.score-num {
  font-size: 32px;
  font-weight: 800;
  color: var(--main-color);
  line-height: 1;
}

.score-unit {
  font-size: 11px;
  color: var(--gray-500);
  margin-top: 4px;
  white-space: nowrap;
}

.dimension-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.dimension-stat {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dimension-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dim-label {
  font-size: 12px;
  color: var(--gray-600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dim-val {
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-800);
}

.dim-progress-bg {
  height: 4px;
  background: var(--gray-200);
  border-radius: 2px;
  overflow: hidden;
}

.dim-progress-fill {
  height: 100%;
  background: var(--main-400);
  border-radius: 2px;
}

.record-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--gray-50);
  padding-top: 12px;
}

.footer-actions {
  display: flex;
  gap: 12px;
}

.state-panel.compact {
  min-height: 200px;
}

@media (max-width: 1200px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .dimension-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .interview-records-view {
    padding: 16px;
  }

  .page-toolbar,
  .section-header {
    padding: 16px;
  }

  .record-header-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .record-stats-section {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .record-overall-score {
    flex-direction: row;
    gap: 12px;
    justify-content: flex-start;
  }

  .dimension-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .records-stats {
    width: 100%;
    justify-content: center;
  }
}
</style>
