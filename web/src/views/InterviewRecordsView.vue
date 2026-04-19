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
        <div class="section-header section-header--compact">
          <div>
            <div class="section-eyebrow">概览</div>
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
        <div class="section-header section-header--compact profile-header">
          <div>
            <div class="section-eyebrow">行动建议</div>
            <div class="section-title">个性化提升路径</div>
            <div class="section-subtitle">基于最近几次已完成模拟面试，生成长期练习-评估-提升闭环</div>
          </div>
          <div class="profile-header__meta">
            <a-tag v-if="personalizedPath.source_round_count" color="purple">
              最近 {{ personalizedPath.source_round_count }} 次
            </a-tag>
            <a-tag v-if="personalizedPath.summary?.top_priority_label" color="processing">
              优先补强：{{ personalizedPath.summary.top_priority_label }}
            </a-tag>
          </div>
        </div>

        <div v-if="loading" class="state-panel compact">
          <a-spin />
        </div>
        <div
          v-else-if="!hasPersonalizedPathContent"
          class="state-panel compact"
        >
          <a-empty description="完成更多面试后分析短板并生成长期提升路径" />
        </div>
        <div v-else class="profile-content personalized-content">
          <a-alert
            v-if="shouldHighlightPersonalizedPath"
            type="success"
            show-icon
            class="personalized-path-alert"
            message="你的长期个性化提升路径已更新"
            :description="`已基于最近 ${personalizedPath.source_round_count} 次面试结果生成，建议现在查看并按路径执行。`"
          />
          <div class="path-summary-card">
            <div class="path-summary-card__header">
              <div>
                <div class="profile-section__title">当前阶段</div>
                <div class="path-summary-card__stage">{{ personalizedPath.summary?.stage_label || '待生成' }}</div>
              </div>
            </div>
            <div class="path-summary-card__desc">{{ personalizedPath.summary?.message || '完成更多面试后会生成长期提升路径。' }}</div>
            <div class="path-summary-stats">
              <div v-for="item in personalizedStats" :key="item.label" class="path-summary-stats__item">
                <span class="path-summary-stats__label">{{ item.label }}</span>
                <span class="path-summary-stats__value">{{ item.value }}</span>
              </div>
            </div>
          </div>

          <div v-if="personalizedPath.action_plan?.steps?.length" class="profile-section profile-section--emphasis">
            <div class="profile-section__title">提升闭环</div>
            <div class="profile-section__desc">左侧看清每一步要做什么，右侧快速理解这轮长期提升的完整闭环。</div>
            <div class="path-loop-layout">
              <div class="path-step-list path-step-list--rich">
                <article
                  v-for="(step, index) in personalizedPath.action_plan.steps"
                  :key="`${step.step_type}-${step.title}`"
                  class="path-step-item"
                >
                  <div class="path-step-item__index">0{{ index + 1 }}</div>
                  <div class="path-step-item__body">
                    <div class="path-step-item__header">
                      <div class="path-step-item__type">{{ getActionStepLabel(step.step_type) }}</div>
                      <div class="path-step-item__time">{{ step.estimated_minutes }} 分钟</div>
                    </div>
                    <div class="path-step-item__title">{{ step.title }}</div>
                    <div class="path-step-item__objective">{{ step.objective }}</div>
                    <div class="path-step-item__signal">完成标准：{{ step.success_signal }}</div>
                  </div>
                </article>
              </div>

              <div class="path-loop-visual-card">
                <div class="path-loop-visual-card__header">
                  <div>
                    <div class="path-loop-visual-card__eyebrow">行动地图</div>
                    <div class="path-loop-visual-card__title">学 → 练 → 回测</div>
                    <div class="path-loop-visual-card__hint">先补关键短板，再做定向练习，最后带着目标回测验证。</div>
                  </div>
                  <a-tag color="processing">闭环执行</a-tag>
                </div>
                <svg class="path-loop-visual" viewBox="0 0 320 220" aria-hidden="true">
                  <defs>
                    <linearGradient id="loopStrokeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#1677ff" />
                      <stop offset="100%" stop-color="#7c3aed" />
                    </linearGradient>
                    <marker id="loopArrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                      <path d="M0,0 L8,4 L0,8 z" fill="#7c3aed" />
                    </marker>
                  </defs>
                  <path d="M96 66 C150 20, 242 28, 250 78" stroke="url(#loopStrokeGradient)" stroke-width="6" stroke-linecap="round" fill="none" marker-end="url(#loopArrow)" opacity="0.9" />
                  <path d="M256 90 C274 146, 206 198, 154 176" stroke="url(#loopStrokeGradient)" stroke-width="6" stroke-linecap="round" fill="none" marker-end="url(#loopArrow)" opacity="0.82" />
                  <path d="M144 170 C90 192, 52 130, 80 84" stroke="url(#loopStrokeGradient)" stroke-width="6" stroke-linecap="round" fill="none" marker-end="url(#loopArrow)" opacity="0.72" />
                  <g v-for="node in actionLoopNodes" :key="node.key">
                    <circle :cx="node.x" :cy="node.y" r="26" :fill="node.fill" />
                    <circle :cx="node.x" :cy="node.y" r="31" :stroke="node.stroke" stroke-width="2" fill="transparent" opacity="0.4" />
                    <text :x="node.x" :y="node.y + 4" text-anchor="middle" class="path-loop-visual__token">{{ node.token }}</text>
                  </g>
                </svg>
                <div class="path-loop-node-list">
                  <div v-for="node in actionLoopNodes" :key="`${node.key}-meta`" class="path-loop-node-card">
                    <div class="path-loop-node-card__top">
                      <span class="path-loop-node-card__badge" :style="{ background: node.fill, color: node.badgeColor }">{{ node.token }}</span>
                      <span class="path-loop-node-card__label">{{ node.label }}</span>
                    </div>
                    <div class="path-loop-node-card__meta">{{ node.minutes }} 分钟 · {{ node.title }}</div>
                  </div>
                </div>
              </div>

              <div v-if="personalizedStrengths.length" class="path-strength-strip path-strength-strip--full">
                <div class="path-strength-strip__title">这几项表现可以继续保持</div>
                <div class="path-strength-strip__list">
                  <span v-for="item in personalizedStrengths" :key="item" class="path-strength-strip__item">{{ item }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="personalizedPath.weaknesses?.length" class="profile-section">
            <div class="profile-section__title">反复偏弱维度</div>
            <div class="profile-section__desc">左侧突出最近几轮里反复拖后腿的维度，右侧只展示与弱项不重复的稳定优势项。</div>
            <div class="weakness-contrast-layout">
              <div class="contrast-column contrast-column--weakness">
                <div class="contrast-column__header">
                  <div class="contrast-column__title">反复偏弱</div>
                  <div class="contrast-column__subtitle">最近几轮里最容易拖后腿的维度</div>
                </div>
                <div class="contrast-card-list">
                  <article v-for="item in topWeaknessDimensions" :key="item.dimension_key" class="contrast-score-card contrast-score-card--weakness">
                    <div class="contrast-score-card__top">
                      <span class="contrast-score-card__label">{{ item.label }}</span>
                      <span class="contrast-score-card__score">{{ item.average_score }} 分</span>
                    </div>
                    <div class="contrast-score-card__track">
                      <div class="contrast-score-card__fill contrast-score-card__fill--weakness" :style="{ width: `${item.average_score}%` }"></div>
                    </div>
                    <div class="contrast-score-card__meta">低分出现 {{ item.low_score_count }} 次</div>
                  </article>
                </div>
              </div>

              <div class="contrast-center-card">
                <div class="contrast-center-card__eyebrow">当前能力落差</div>
                <div class="contrast-center-card__title">{{ weaknessGapSummary.title }}</div>
                <div class="contrast-center-card__score">{{ weaknessGapSummary.gapText }}</div>
                <div class="contrast-center-card__desc">{{ weaknessGapSummary.description }}</div>
              </div>

              <div class="contrast-column contrast-column--strength">
                <div class="contrast-column__header">
                  <div class="contrast-column__title">相对优势</div>
                  <div class="contrast-column__subtitle">优先保留这些稳定发挥，且不与左侧短板重复的部分</div>
                </div>
                <div v-if="topStrengthDimensions.length" class="contrast-card-list">
                  <article v-for="item in topStrengthDimensions" :key="item.dimension_key" class="contrast-score-card contrast-score-card--strength">
                    <div class="contrast-score-card__top">
                      <span class="contrast-score-card__label">{{ item.label }}</span>
                      <span class="contrast-score-card__score">{{ item.average_score }} 分</span>
                    </div>
                    <div class="contrast-score-card__track">
                      <div class="contrast-score-card__fill contrast-score-card__fill--strength" :style="{ width: `${item.average_score}%` }"></div>
                    </div>
                    <div class="contrast-score-card__meta">最近几轮表现相对稳定</div>
                  </article>
                </div>
                <div v-else class="contrast-empty-card">
                  当前还没有形成与短板明显区分开的稳定优势，建议先继续完成 2-3 轮回测。
                </div>
              </div>
            </div>
            <div class="weakness-detail-layout">
              <div class="path-weakness-list">
                <div
                  v-for="item in personalizedPath.weaknesses"
                  :key="`${item.dimension_key}-${item.title}`"
                  class="path-weakness-item"
                >
                  <div class="path-weakness-item__title">{{ item.title }}</div>
                  <div class="path-weakness-item__reason">{{ item.reason }}</div>
                </div>
              </div>
              <div v-if="personalizedStrengths.length" class="strength-insight-card">
                <div class="strength-insight-card__title">优先保留的答题优势</div>
                <div class="strength-insight-card__desc">短板要补，但这几项稳定发挥不要丢，后续答题可以继续复用。</div>
                <div class="strength-insight-card__list">
                  <div v-for="item in personalizedStrengths" :key="`${item}-keep`" class="strength-insight-card__item">{{ item }}</div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="prioritizedResources.length" class="profile-section">
            <div class="profile-section__title">推荐资源</div>
            <div class="profile-section__desc">默认把可直接开始学习或练习的资源放前面，并补充至少 2 个外部链接，避免只有建议没有动作。</div>
            <div class="resource-priority-bar">
              <span class="resource-priority-bar__label">优先立即行动</span>
              <div class="resource-priority-bar__meta">
                <a-tag color="success">可直接打开 {{ primaryResources.length }}</a-tag>
                <a-tag color="processing">外部链接 {{ externalResourceCount }}</a-tag>
              </div>
            </div>
            <div class="path-resource-grid">
              <article
                v-for="resource in primaryResources"
                :key="`${resource.source_ref || resource.title}-${resource.resource_type}`"
                class="path-resource-card path-resource-card--primary"
              >
                <div class="path-resource-card__header">
                  <div class="path-resource-card__title-wrap">
                    <span class="path-resource-card__title">{{ resource.title }}</span>
                    <div class="path-resource-card__badges">
                      <a-tag color="success">立即可学</a-tag>
                      <a-tag :color="getResourceTagColor(resource.resource_type)">
                        {{ getResourceTypeLabel(resource.resource_type) }}
                      </a-tag>
                    </div>
                  </div>
                </div>
                <div class="path-resource-card__summary">{{ resource.summary }}</div>
                <div v-if="resource.reason" class="path-resource-card__reason">推荐理由：{{ resource.reason }}</div>
                <div class="path-resource-card__footer">
                  <div class="path-resource-card__source-group">
                    <span v-if="resource.is_external && resource.provider" class="path-resource-card__source">来源：{{ resource.provider }}</span>
                    <span v-if="resource.estimated_minutes" class="path-resource-card__source">约 {{ resource.estimated_minutes }} 分钟</span>
                  </div>
                  <a-button type="primary" size="small" @click="triggerResourceAction(resource)">
                    {{ getResourceActionLabel(resource) }}
                  </a-button>
                </div>
              </article>
            </div>
            <div v-if="supportingResources.length" class="resource-support-section">
              <div class="resource-support-section__title">补充拓展</div>
              <div class="path-resource-list">
                <article
                  v-for="resource in supportingResources"
                  :key="`${resource.source_ref || resource.title}-${resource.resource_type}`"
                  class="path-resource-card"
                >
                  <div class="path-resource-card__header">
                    <div class="path-resource-card__title-wrap">
                      <span class="path-resource-card__title">{{ resource.title }}</span>
                      <div class="path-resource-card__badges">
                        <a-tag v-if="resource.is_external" color="processing">外部链接</a-tag>
                        <a-tag :color="getResourceTagColor(resource.resource_type)">
                          {{ getResourceTypeLabel(resource.resource_type) }}
                        </a-tag>
                      </div>
                    </div>
                  </div>
                  <div class="path-resource-card__summary">{{ resource.summary }}</div>
                  <div v-if="resource.reason" class="path-resource-card__reason">推荐理由：{{ resource.reason }}</div>
                  <div class="path-resource-card__footer">
                    <div class="path-resource-card__source-group">
                      <span v-if="resource.is_external && resource.provider" class="path-resource-card__source">来源：{{ resource.provider }}</span>
                    </div>
                    <a-button size="small" @click="triggerResourceAction(resource)">
                      {{ getResourceActionLabel(resource) }}
                    </a-button>
                  </div>
                </article>
              </div>
            </div>
          </div>

          <div v-if="personalizedPath.next_assessment_focus?.length" class="profile-section focus-section">
            <div class="profile-section__title">下次回测重点</div>
            <div class="profile-section__desc">下次模拟面试时优先观察这些点是否真的改善，而不只是记住答案。</div>
            <div class="profile-focus-list">
              <div
                v-for="item in personalizedPath.next_assessment_focus"
                :key="`${item.dimension_key}-${item.title}`"
                class="profile-focus-item"
              >
                <div class="profile-focus-item__title">{{ item.title }}</div>
                <div class="profile-focus-item__desc">{{ item.focus }}</div>
              </div>
            </div>
          </div>

          <div v-if="personalizedPath.related_records?.length" class="profile-section profile-section--muted">
            <div class="profile-section__title">关联面试记录</div>
            <div class="profile-section__desc">这些记录是当前长期提升路径的主要证据来源，可直接回看报告。</div>
            <div class="path-related-list">
              <button
                v-for="item in personalizedPath.related_records"
                :key="item.thread_id"
                type="button"
                class="path-related-item"
                @click="openInterviewResult(item)"
              >
                <div class="path-related-item__title">{{ item.title }}</div>
                <div class="path-related-item__meta">{{ item.position }} · {{ item.round }} · {{ formatDateTime(item.updated_at) }}</div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel-card records-card">
      <div class="section-header section-header--compact records-header">
        <div class="records-header-info">
          <div class="section-eyebrow">全部记录</div>
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
            <span class="stat-value">{{ historyCompletedCount }}</span>
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
    <InterviewKnowledgeLearnModal v-model:open="learningModalVisible" :resource="activeLearningResource" />
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

import InterviewKnowledgeLearnModal from '@/components/interview/InterviewKnowledgeLearnModal.vue'
import { interviewHistoryApi } from '@/apis/interview_history'
import { useUserStore } from '@/stores/user'
import { formatDateTime, parseToShanghai } from '@/utils/time'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const usersLoading = ref(false)
const historyPayload = ref(null)
const personalizedPathPayload = ref(null)
const userOptions = ref([])
const selectedUserId = ref(null)
const chartRef = ref(null)
const userSelectionReady = ref(false)
const learningModalVisible = ref(false)
const activeLearningResource = ref(null)

let chartInstance = null

const records = computed(() => historyPayload.value?.records || [])
const profile = computed(
  () =>
    historyPayload.value?.profile || {
      top_weakness_dimensions: [],
      top_strength_dimensions: [],
      latest_focus: [],
      pending_practice_count: 0
    }
)
const personalizedPath = computed(
  () =>
    personalizedPathPayload.value?.personalized_path || {
      summary: {
        stage_label: '待生成',
        top_priority_dimension: '',
        top_priority_label: '',
        message: '完成更多模拟面试后，会在这里生成长期提升路径。'
      },
      weaknesses: [],
      recommended_resources: [],
      practice_tasks: [],
      next_assessment_focus: [],
      action_plan: null,
      strengths: [],
      source_round_count: 0,
      latest_updated_at: '',
      related_records: []
    }
)
const targetUser = computed(() => historyPayload.value?.target_user || personalizedPathPayload.value?.target_user || null)
const chartCategories = computed(() => historyPayload.value?.chart?.categories || [])
const chartSeries = computed(() => historyPayload.value?.chart?.series || [])
const historyCompletedCount = computed(() => records.value.filter((record) => record.status === 'completed').length)
const hasPersonalizedPathContent = computed(
  () =>
    Boolean(
      personalizedPath.value.weaknesses?.length ||
        personalizedPath.value.action_plan?.steps?.length ||
        personalizedPath.value.recommended_resources?.length ||
        personalizedPath.value.next_assessment_focus?.length
    )
)
const shouldHighlightPersonalizedPath = computed(
  () => hasPersonalizedPathContent.value && Number(personalizedPath.value.source_round_count || 0) >= 2
)
const personalizedStats = computed(() => [
  {
    label: '分析轮次',
    value: personalizedPath.value.source_round_count || '--'
  },
  {
    label: '待练习项',
    value: profile.value.pending_practice_count || '--'
  },
  {
    label: '最近更新',
    value: personalizedPath.value.latest_updated_at ? formatDateTime(personalizedPath.value.latest_updated_at) : '--'
  }
])
const targetUserLabel = computed(() => {
  const username = String(targetUser.value?.username || userStore.username || '').trim()
  if (!username) return '当前用户'
  return username
})
const topWeaknessDimensions = computed(() => profile.value.top_weakness_dimensions || [])
const topStrengthDimensions = computed(() => {
  const weaknessKeys = new Set((profile.value.top_weakness_dimensions || []).map((item) => item?.dimension_key).filter(Boolean))
  return (profile.value.top_strength_dimensions || []).filter((item) => !weaknessKeys.has(item?.dimension_key))
})
const personalizedStrengths = computed(() => (personalizedPath.value.strengths || []).filter(Boolean).slice(0, 3))
const prioritizedResources = computed(() => {
  const resources = personalizedPath.value.recommended_resources || []
  return [...resources].sort((left, right) => {
    const leftPriority = getResourcePriorityScore(left)
    const rightPriority = getResourcePriorityScore(right)
    if (leftPriority !== rightPriority) return rightPriority - leftPriority
    return 0
  })
})
const primaryResources = computed(() => prioritizedResources.value.slice(0, 4))
const supportingResources = computed(() => prioritizedResources.value.slice(4))
const externalResourceCount = computed(
  () => prioritizedResources.value.filter((item) => Boolean(item?.is_external && String(item?.url || '').trim())).length
)
const weaknessGapSummary = computed(() => {
  const weakest = topWeaknessDimensions.value[0]
  const strongest = topStrengthDimensions.value[0]
  if (!weakest && !strongest) {
    return {
      title: '等待更多轮面试数据',
      gapText: '--',
      description: '完成更多面试后，这里会显示最需要补强的能力落差。'
    }
  }
  if (!weakest || !strongest) {
    return {
      title: `${weakest?.label || strongest?.label || '核心能力'}需要持续观察`,
      gapText: `${weakest?.average_score || strongest?.average_score || '--'} 分`,
      description: '当前样本还不够完整，先继续累积几轮结果，再看长期稳定趋势。'
    }
  }
  const gap = Math.max(0, Number(strongest.average_score || 0) - Number(weakest.average_score || 0))
  return {
    title: `${weakest.label} 与 ${strongest.label} 存在明显差距`,
    gapText: `${gap} 分落差`,
    description: `${weakest.label} 是当前最容易拖后腿的维度，而 ${strongest.label} 已经相对稳定，建议优先把短板补到接近自身优势水平。`
  }
})
const actionLoopNodes = computed(() => {
  const fallbackColors = {
    learn: { fill: '#e8f3ff', stroke: '#1677ff', badgeColor: '#0958d9' },
    practice: { fill: '#fff7e6', stroke: '#fa8c16', badgeColor: '#ad4e00' },
    recheck: { fill: '#f3e8ff', stroke: '#7c3aed', badgeColor: '#531dab' }
  }
  const positions = {
    learn: { x: 82, y: 76 },
    practice: { x: 248, y: 84 },
    recheck: { x: 160, y: 168 }
  }
  return (personalizedPath.value.action_plan?.steps || []).map((step, index) => {
    const stepType = String(step?.step_type || '').trim()
    const token = String(index + 1).padStart(2, '0')
    const colors = fallbackColors[stepType] || fallbackColors.learn
    const position = positions[stepType] || { x: 70 + index * 80, y: 90 + index * 12 }
    return {
      key: `${stepType}-${step.title}`,
      token,
      label: getActionStepShortLabel(stepType),
      title: step.title,
      minutes: step.estimated_minutes || '--',
      fill: colors.fill,
      stroke: colors.stroke,
      badgeColor: colors.badgeColor,
      x: position.x,
      y: position.y
    }
  })
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

const actionStepLabelMap = {
  learn: '第 1 步 · 补知识',
  practice: '第 2 步 · 做练习',
  recheck: '第 3 步 · 回测验证'
}

const resolveLearningLocator = (source) => {
  const locator = source?.locator || {}
  const dbId = String(locator.db_id || source?.db_id || '').trim()
  const fileId = String(locator.file_id || source?.file_id || '').trim()
  if (!dbId || !fileId) return null
  return {
    db_id: dbId,
    file_id: fileId,
    chunk_id: String(locator.chunk_id || source?.chunk_id || '').trim() || undefined,
    chunk_index:
      locator.chunk_index !== undefined && locator.chunk_index !== null
        ? Number(locator.chunk_index)
        : source?.chunk_index !== undefined && source?.chunk_index !== null
          ? Number(source.chunk_index)
          : undefined,
    keyword: String(locator.keyword || '').trim() || undefined,
    query_text: String(locator.query_text || '').trim() || undefined
  }
}

const getActionStepLabel = (stepType) => actionStepLabelMap[String(stepType || '').trim()] || stepType || '行动步骤'
const getActionStepShortLabel = (stepType) => {
  const labelMap = {
    learn: '补知识',
    practice: '做练习',
    recheck: '回测验证'
  }
  return labelMap[String(stepType || '').trim()] || '行动步骤'
}

const getResourceTypeLabel = (type) => {
  const labelMap = {
    knowledge: '知识学习',
    interview_question: '定向练习',
    communication: '表达提升',
    article: '博客文章',
    video: '教学视频',
    case: '案例拆解'
  }
  return labelMap[type] || type || '资源'
}

const getResourceTagColor = (type) => {
  const colorMap = {
    knowledge: 'blue',
    interview_question: 'gold',
    communication: 'green',
    article: 'cyan',
    video: 'orange',
    case: 'volcano'
  }
  return colorMap[type] || 'default'
}

const canOpenLearningLocator = (resource) => Boolean(resolveLearningLocator(resource))
const canLearnResource = (resource) =>
  ['knowledge', 'communication'].includes(String(resource?.resource_type || '').trim()) && canOpenLearningLocator(resource)
const canPracticeResource = (resource) =>
  String(resource?.resource_type || '').trim() === 'interview_question' && String(resource?.problem_ref || '').trim()
const canOpenExternalResource = (resource) =>
  Boolean(resource?.is_external && /^https?:\/\//.test(String(resource?.url || '').trim()))
const getResourcePriorityScore = (resource) => {
  if (canOpenExternalResource(resource)) return 3
  if (canPracticeResource(resource)) return 2
  if (canLearnResource(resource)) return 1
  return 0
}
const getResourceActionLabel = (resource) => {
  if (canOpenExternalResource(resource)) return '立即学习'
  if (canPracticeResource(resource)) return '去练习'
  if (canLearnResource(resource)) return '开始学习'
  return '查看建议'
}

const openLearningLocator = (resource) => {
  const locator = resolveLearningLocator(resource)
  if (!locator) return
  activeLearningResource.value = {
    ...resource,
    locator
  }
  learningModalVisible.value = true
}

const openLearningResource = (resource) => openLearningLocator(resource)

const openPracticeResource = (resource) => {
  const problemRef = String(resource?.problem_ref || '').trim()
  if (!problemRef) return
  router.push({
    name: 'PracticeProblemPage',
    params: {
      problem_ref: problemRef
    }
  })
}

const openExternalResource = (resource) => {
  const url = String(resource?.url || '').trim()
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

const triggerResourceAction = (resource) => {
  if (canLearnResource(resource)) {
    openLearningResource(resource)
    return
  }
  if (canPracticeResource(resource)) {
    openPracticeResource(resource)
    return
  }
  if (canOpenExternalResource(resource)) {
    openExternalResource(resource)
  }
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
    const userId = userStore.isAdmin ? selectedUserId.value : userStore.userId
    const [historyResult, personalizedPathResult] = await Promise.all([
      interviewHistoryApi.getHistory({ userId }),
      interviewHistoryApi.getPersonalizedPath({ userId })
    ])
    const normalizedResources = (personalizedPathResult?.personalized_path?.recommended_resources || []).map((item) => ({
      ...item,
      title: decodeHtmlEntities(item?.title),
      summary: decodeHtmlEntities(item?.summary),
      reason: decodeHtmlEntities(item?.reason),
      provider: decodeHtmlEntities(item?.provider)
    }))
    historyPayload.value = historyResult
    personalizedPathPayload.value = {
      ...(personalizedPathResult || {}),
      personalized_path: {
        ...(personalizedPathResult?.personalized_path || {}),
        recommended_resources: normalizedResources
      }
    }
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

const decodeHtmlEntities = (value) => {
  const text = String(value || '')
  if (typeof window === 'undefined' || !text.includes('&')) return text
  const textarea = document.createElement('textarea')
  textarea.innerHTML = text
  return textarea.value
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
  box-shadow: 0 1px 4px var(--shadow-1);
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

.section-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--main-500);
  margin-bottom: 6px;
}

.section-header--compact {
  padding-bottom: 16px;
}

.profile-header {
  align-items: flex-start;
}

.profile-header__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr;
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

.personalized-content {
  gap: 16px;
}

.personalized-path-alert {
  margin-bottom: 4px;
}

.path-summary-card {
  padding: 18px;
  border-radius: 14px;
  background: var(--main-40);
  border: 1px solid var(--main-100);
}

.path-summary-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.path-summary-card__stage {
  font-size: 18px;
  font-weight: 700;
  color: var(--main-700);
  margin-top: 4px;
}

.path-summary-card__desc {
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.7;
}

.path-summary-stats {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.path-summary-stats__item {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid var(--main-100);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.path-summary-stats__label {
  font-size: 11px;
  color: var(--gray-500);
}

.path-summary-stats__value {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.path-step-list,
.path-weakness-list,
.path-resource-list,
.path-related-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.path-loop-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.path-step-list--rich {
  gap: 14px;
}

.path-step-item,
.path-weakness-item,
.path-resource-card,
.path-related-item,
.path-loop-visual-card,
.strength-insight-card,
.contrast-center-card,
.contrast-score-card {
  border: 1px solid var(--gray-150);
  border-radius: 14px;
  background: var(--gray-25);
}

.profile-section--emphasis .path-step-item {
  background: var(--gray-0);
  border-color: var(--main-100);
}

.profile-section--muted .path-related-item {
  background: var(--gray-0);
}

.path-step-item {
  display: flex;
  gap: 12px;
  padding: 14px;
}

.path-strength-strip {
  padding: 14px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(82, 196, 26, 0.08), rgba(24, 144, 255, 0.06));
  border: 1px solid rgba(82, 196, 26, 0.18);
}

.path-strength-strip--full {
  grid-column: 1 / -1;
}

.path-strength-strip__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.path-strength-strip__list {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.path-strength-strip__item {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  color: var(--gray-700);
  font-size: 12px;
}

.path-loop-visual-card {
  padding: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #fcf9ff 100%);
  border-color: rgba(124, 58, 237, 0.14);
  display: flex;
  flex-direction: column;
  align-self: start;
  gap: 12px;
}

.path-loop-visual-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.path-loop-visual-card__eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--main-500);
}

.path-loop-visual-card__title {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-900);
}

.path-loop-visual-card__hint {
  margin-top: 8px;
  max-width: 320px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-500);
}

.path-loop-visual {
  width: 100%;
  height: 188px;
  margin-top: 0;
}

.path-loop-visual__token {
  font-size: 14px;
  font-weight: 700;
  fill: var(--gray-900);
}

.path-loop-node-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.path-loop-node-card {
  padding: 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(124, 58, 237, 0.1);
}

.path-loop-node-card__top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.path-loop-node-card__badge {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.path-loop-node-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.path-loop-node-card__meta {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-600);
}

.path-step-item__index {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: var(--main-80);
  color: var(--main-700);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.path-step-item__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.path-step-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.path-step-item__type,
.path-step-item__time {
  font-size: 12px;
  color: var(--gray-500);
}

.path-step-item__signal {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed var(--gray-200);
}

.path-step-item__title,
.path-weakness-item__title,
.path-related-item__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.path-step-item__objective,
.path-step-item__signal,
.path-weakness-item__reason,
.path-related-item__meta,
.path-resource-card__summary,
.path-resource-card__reason,
.path-resource-card__source {
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.6;
}

.path-weakness-item,
.path-related-item {
  padding: 12px 14px;
}

.path-resource-card,
.path-related-item {
  text-align: left;
}

.path-resource-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.path-resource-card {
  padding: 16px;
}

.path-resource-card--primary {
  background: linear-gradient(180deg, rgba(240, 249, 255, 0.9), rgba(255, 255, 255, 0.96));
  border-color: rgba(22, 119, 255, 0.2);
}

.path-resource-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.path-resource-card__title-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.path-resource-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.path-resource-card__title {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-800);
}

.path-resource-card__source {
  font-size: 12px;
  color: var(--gray-500);
}

.path-resource-card__footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.path-resource-card__source-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.resource-priority-bar {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(82, 196, 26, 0.08), rgba(24, 144, 255, 0.06));
  border: 1px solid rgba(82, 196, 26, 0.18);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.resource-priority-bar__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.resource-priority-bar__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.resource-support-section {
  margin-top: 16px;
}

.resource-support-section__title {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-700);
}

.profile-section__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-700);
  margin-bottom: 12px;
}

.profile-section__desc {
  font-size: 12px;
  color: var(--gray-500);
  line-height: 1.6;
  margin-bottom: 12px;
}

.weakness-contrast-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px minmax(0, 1fr);
  gap: 14px;
  align-items: stretch;
}

.contrast-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.contrast-column__header {
  padding: 4px 2px;
}

.contrast-column__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-800);
}

.contrast-column__subtitle {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-500);
}

.contrast-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.contrast-score-card {
  padding: 14px;
}

.contrast-score-card--weakness {
  background: linear-gradient(180deg, rgba(255, 247, 230, 0.9), rgba(255, 255, 255, 0.96));
  border-color: rgba(250, 173, 20, 0.22);
}

.contrast-score-card--strength {
  background: linear-gradient(180deg, rgba(230, 247, 255, 0.9), rgba(255, 255, 255, 0.96));
  border-color: rgba(24, 144, 255, 0.2);
}

.contrast-score-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.contrast-score-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.contrast-score-card__score {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-900);
}

.contrast-score-card__track {
  margin-top: 10px;
  height: 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.contrast-score-card__fill {
  height: 100%;
  border-radius: inherit;
}

.contrast-score-card__fill--weakness {
  background: linear-gradient(90deg, #fa8c16 0%, #faad14 100%);
}

.contrast-score-card__fill--strength {
  background: linear-gradient(90deg, #1677ff 0%, #13c2c2 100%);
}

.contrast-score-card__meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--gray-600);
}

.contrast-empty-card {
  padding: 14px;
  border: 1px dashed rgba(24, 144, 255, 0.24);
  border-radius: 14px;
  background: rgba(230, 247, 255, 0.52);
  font-size: 12px;
  line-height: 1.7;
  color: var(--gray-600);
}

.contrast-center-card {
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  background: linear-gradient(180deg, rgba(250, 250, 255, 0.96), rgba(243, 248, 255, 0.96));
}

.contrast-center-card__eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--main-500);
}

.contrast-center-card__title {
  margin-top: 10px;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--gray-900);
}

.contrast-center-card__score {
  margin-top: 12px;
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  color: var(--main-700);
}

.contrast-center-card__desc {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--gray-600);
}

.weakness-detail-layout {
  margin-top: 14px;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
  gap: 14px;
}

.strength-insight-card {
  padding: 16px;
  background: linear-gradient(180deg, rgba(82, 196, 26, 0.06), rgba(24, 144, 255, 0.04));
  border-color: rgba(82, 196, 26, 0.18);
}

.strength-insight-card__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-800);
}

.strength-insight-card__desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-600);
}

.strength-insight-card__list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.strength-insight-card__item {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--gray-700);
  font-size: 12px;
  line-height: 1.6;
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
  gap: 14px;
}

.record-item {
  display: flex;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 14px;
  overflow: hidden;
  transition: border-color 0.2s ease, background-color 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    background: var(--gray-25);
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
  font-size: 17px;
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

  .path-summary-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dimension-grid,
  .path-resource-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .path-loop-layout,
  .weakness-detail-layout,
  .weakness-contrast-layout {
    grid-template-columns: 1fr;
  }

  .path-loop-node-list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
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

  .profile-header__meta,
  .path-summary-stats {
    width: 100%;
  }

  .path-summary-card__header,
  .path-step-item__header,
  .path-resource-card__header,
  .path-resource-card__footer,
  .resource-priority-bar,
  .path-loop-visual-card__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .path-summary-stats,
  .path-loop-node-list,
  .path-resource-grid {
    grid-template-columns: 1fr;
  }

  .path-loop-visual {
    height: 200px;
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
