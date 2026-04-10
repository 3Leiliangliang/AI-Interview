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
        <a-button :loading="loading" @click="loadHistory">刷新</a-button>
      </div>
    </div>

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

    <div class="panel-card records-card">
      <div class="section-header">
        <div>
          <div class="section-title">历史记录</div>
          <div class="section-subtitle">展示全部面试线程，成长曲线仅统计已完成结果</div>
        </div>
        <a-tag color="blue">{{ records.length }} 条</a-tag>
      </div>

      <div v-if="loading" class="state-panel compact">
        <a-spin />
      </div>
      <div v-else-if="records.length === 0" class="state-panel compact">
        <a-empty description="暂无面试记录" />
      </div>
      <div v-else class="records-list">
        <div v-for="record in records" :key="record.thread_id" class="record-item">
          <div class="record-main">
            <div class="record-top">
              <div>
                <div class="record-title">{{ record.title || '未命名面试' }}</div>
                <div class="record-meta">
                  <span>{{ formatDateTime(record.updated_at) }}</span>
                  <span>创建于 {{ formatDateTime(record.created_at) }}</span>
                </div>
              </div>

              <div class="record-score">
                <span class="score-label">总分</span>
                <span class="score-value">{{ formatOverallScore(record.overall_score) }}</span>
              </div>
            </div>

            <div class="record-tags">
              <a-tag>{{ getInterviewModeLabel(record.interview_mode) }}</a-tag>
              <a-tag>{{ record.position }}</a-tag>
              <a-tag>{{ record.round }}</a-tag>
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusLabel(record.status) }}
              </a-tag>
            </div>

            <div v-if="record.dimensions?.length" class="dimension-list">
              <div
                v-for="dimension in record.dimensions"
                :key="dimension.key"
                class="dimension-item"
              >
                <span class="dimension-label">{{ dimension.label }}</span>
                <span class="dimension-value">{{ formatDimensionScore(dimension.score) }}</span>
              </div>
            </div>
          </div>

          <div class="record-actions">
            <a-button @click="continueInterview(record)">继续面试</a-button>
            <a-button v-if="record.has_result" type="primary" @click="openInterviewResult(record)">
              查看结果
            </a-button>
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
  const numeric = Number(score)
  return Number.isFinite(numeric) ? `${Math.round(numeric)}` : '--'
}

const formatDimensionScore = (score) => {
  const numeric = Number(score)
  return Number.isFinite(numeric) ? numeric : '--'
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
      right: 20,
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
  if (!chartRef.value || !chartCategories.value.length) return
  await nextTick()
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
  padding: 20px;
  background: var(--gray-50);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
}

.page-toolbar,
.section-header,
.record-top,
.record-item,
.record-actions {
  display: flex;
}

.page-toolbar,
.section-header {
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
}

.toolbar-title,
.section-title,
.record-title {
  color: var(--gray-900);
  font-weight: 600;
}

.toolbar-title {
  font-size: 18px;
}

.toolbar-subtitle,
.section-subtitle,
.record-meta,
.score-label,
.dimension-label {
  color: var(--gray-500);
  font-size: 13px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-select {
  width: 260px;
}

.chart-card,
.records-card {
  padding: 0;
}

.growth-chart {
  width: 100%;
  height: 360px;
  padding: 0 12px 16px;
}

.state-panel.compact {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.records-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 20px 20px;
}

.record-item {
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px;
  border: 1px solid var(--gray-150);
  border-radius: 14px;
  background: var(--gray-25);
}

.record-main {
  flex: 1;
  min-width: 0;
}

.record-top {
  justify-content: space-between;
  gap: 16px;
}

.record-title {
  font-size: 16px;
}

.record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 6px;
}

.record-score {
  min-width: 64px;
  text-align: right;
}

.score-value {
  display: block;
  margin-top: 4px;
  color: var(--main-color);
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}

.record-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.dimension-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.dimension-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--gray-150);
  border-radius: 10px;
  background: var(--gray-0);
}

.dimension-value {
  color: var(--gray-800);
  font-size: 14px;
  font-weight: 600;
}

.record-actions {
  flex-shrink: 0;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 960px) {
  .page-toolbar,
  .section-header,
  .record-top,
  .record-item {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .user-select {
    width: 100%;
  }

  .record-score {
    text-align: left;
  }

  .dimension-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .record-actions {
    width: 100%;
  }
}
</style>
