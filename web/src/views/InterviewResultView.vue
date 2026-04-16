<template>
  <div class="interview-result-view">
    <div class="result-toolbar">
      <div>
        <div class="toolbar-title">面试结果</div>
        <div class="toolbar-subtitle">本页展示这轮模拟面试的最终评分与结论</div>
      </div>
      <div class="toolbar-actions">
        <a-button @click="goBackToCoding">返回代码考核</a-button>
        <a-button @click="goBackToInterview">返回面试记录</a-button>
        <a-button type="primary" :loading="finalizing" @click="finalizeResult(true)">重新生成结果</a-button>
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin />
    </div>

    <div v-else-if="failedMessage" class="state-panel">
      <a-result status="warning" title="面试结果生成失败" :sub-title="failedMessage">
        <template #extra>
          <a-button type="primary" :loading="finalizing" @click="finalizeResult(true)">重新生成</a-button>
        </template>
      </a-result>
    </div>

    <div v-else-if="isGenerating" class="state-panel">
      <a-spin size="large" />
      <div class="state-title">正在生成面试结果</div>
      <div class="state-desc">系统正在根据整轮表现和代码考核结果生成最终评分卡，请稍候。</div>
    </div>

    <div v-else-if="!hasCompletedResult" class="state-panel">
      <a-empty description="当前还没有可展示的面试结果">
        <a-button type="primary" :loading="finalizing" @click="finalizeResult()">生成面试结果</a-button>
      </a-empty>
    </div>

    <div v-else class="result-layout">
      <section class="main-column">
        <div class="panel-card">
          <div class="panel-header">
            <div>
              <div class="panel-title">{{ threadTitle }}</div>
              <div class="panel-meta">
                <span v-if="scorecard?.role">{{ scorecard.role }}</span>
                <span v-if="scorecard?.round">{{ scorecard.round }}</span>
                <span v-if="generatedAtText">生成于 {{ generatedAtText }}</span>
              </div>
            </div>
            <a-tag color="green">已完成</a-tag>
          </div>

          <InterviewScorePanel v-if="scorecard" :scorecard="scorecard" />
        </div>

        <div v-if="expressionMetrics.length" class="panel-card">
          <div class="panel-header">
            <div>
              <div class="panel-title">表达分析</div>
              <div v-if="expressionAnalysis?.summary" class="panel-meta expression-meta">
                <span>{{ expressionAnalysis.summary }}</span>
              </div>
            </div>
            <a-tag color="blue">语音作答</a-tag>
          </div>

          <div class="expression-grid">
            <div v-for="item in expressionMetrics" :key="item.key" class="expression-card">
              <div class="expression-card__top">
                <span class="expression-card__label">{{ item.label }}</span>
                <a-tag color="default">{{ item.metric.level || '已分析' }}</a-tag>
              </div>
              <div class="expression-card__score">
                <span class="expression-card__number">{{ item.metric.score ?? '-' }}</span>
                <span class="expression-card__unit">/100</span>
              </div>
              <div v-if="item.metric.value" class="expression-card__value">{{ item.metric.value }}</div>
              <div v-if="item.metric.detail" class="expression-card__detail">{{ item.metric.detail }}</div>
            </div>
          </div>
        </div>

        <div v-if="improvementPlan" class="panel-card">
          <div class="panel-header">
            <div>
              <div class="panel-title">个性化提升路径</div>
              <div class="panel-meta">
                <span>围绕本轮表现生成短板诊断、练习任务与下次评估重点</span>
              </div>
            </div>
            <a-tag color="processing">练习-评估-提升</a-tag>
          </div>

          <div class="improvement-layout">
            <section v-if="improvementPlan.weaknesses?.length" class="improvement-section">
              <div class="improvement-section__title">短板诊断</div>
              <div class="improvement-grid">
                <div
                  v-for="item in improvementPlan.weaknesses"
                  :key="`${item.dimension_key}-${item.title}`"
                  class="improvement-card"
                >
                  <div class="improvement-card__top">
                    <span class="improvement-card__title">{{ item.title }}</span>
                    <a-tag color="default">{{ getDimensionLabel(item.dimension_key) }}</a-tag>
                  </div>
                  <div class="improvement-card__desc">{{ item.reason }}</div>
                </div>
              </div>
            </section>

            <section v-if="improvementPlan.recommended_resources?.length" class="improvement-section">
              <div class="improvement-section__title">推荐资源</div>
              <div class="resource-list">
                <div
                  v-for="item in improvementPlan.recommended_resources"
                  :key="`${item.resource_type}-${item.title}-${item.source_ref}`"
                  class="resource-item"
                >
                  <div class="resource-item__top">
                    <div class="resource-item__title-group">
                      <span class="resource-item__title">{{ item.title }}</span>
                      <div class="resource-item__actions">
                        <a-tag :color="getResourceTagColor(item.resource_type)">
                          {{ getResourceTypeLabel(item.resource_type) }}
                        </a-tag>
                        <a-button
                          v-if="canLearnResource(item)"
                          size="small"
                          type="link"
                          class="resource-item__learn-btn"
                          @click="openLearningResource(item)"
                        >
                          一键学习
                        </a-button>
                      </div>
                    </div>
                  </div>
                  <div class="resource-item__summary">{{ item.summary }}</div>
                </div>
              </div>
            </section>

            <section v-if="improvementPlan.practice_tasks?.length" class="improvement-section">
              <div class="improvement-section__title">本周练习任务</div>
              <div class="task-list">
                <div
                  v-for="item in improvementPlan.practice_tasks"
                  :key="`${item.action_type}-${item.title}`"
                  class="task-item"
                >
                  <div>
                    <div class="task-item__title">{{ item.title }}</div>
                    <div class="task-item__objective">{{ item.objective }}</div>
                  </div>
                  <div class="task-item__meta">{{ item.estimated_minutes }} 分钟</div>
                </div>
              </div>
            </section>

            <section v-if="improvementPlan.next_assessment_focus?.length" class="improvement-section">
              <div class="improvement-section__title">下次评估重点</div>
              <div class="focus-list">
                <div
                  v-for="item in improvementPlan.next_assessment_focus"
                  :key="`${item.dimension_key}-${item.title}`"
                  class="focus-item"
                >
                  <div class="focus-item__title">
                    {{ item.title }}
                    <span class="focus-item__tag">{{ getDimensionLabel(item.dimension_key) }}</span>
                  </div>
                  <div class="focus-item__desc">{{ item.focus }}</div>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div class="panel-card" v-if="summaryMarkdown">
          <div class="panel-header">
            <div class="panel-title">综合结论</div>
          </div>
          <MdPreview
            editor-id="interview-result-summary"
            :theme="theme"
            preview-theme="github"
            :show-code-row-number="false"
            :model-value="summaryMarkdown"
            class="summary-preview"
          />
        </div>
      </section>

      <aside class="side-column">
        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">代码考核摘要</div>
          </div>

          <div v-if="codingSession" class="coding-summary">
            <div class="summary-row">
              <span class="summary-label">题目</span>
              <span class="summary-value">{{ codingSession.problem_title || '-' }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">难度</span>
              <span class="summary-value">{{ codingSession.difficulty_level || '-' }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">判题结果</span>
              <a-tag :color="judgeStatusColor">{{ judgeStatusLabel }}</a-tag>
            </div>
            <div class="summary-row" v-if="codingSession.submission_id">
              <span class="summary-label">提交 ID</span>
              <span class="summary-value">{{ codingSession.submission_id }}</span>
            </div>
            <div class="summary-row" v-if="codingSession.submitted_at">
              <span class="summary-label">提交时间</span>
              <span class="summary-value">{{ codingSession.submitted_at }}</span>
            </div>
            <div class="summary-row" v-if="codingSession.judge_result?.score !== undefined">
              <span class="summary-label">判题得分</span>
              <span class="summary-value">{{ codingSession.judge_result.score }}</span>
            </div>
          </div>

          <div v-else class="empty-text">当前线程还没有代码考核记录</div>
        </div>

        <div class="panel-card">
          <div class="panel-header">
            <div class="panel-title">后续操作</div>
          </div>
          <div class="action-list">
            <a-button block @click="goBackToInterview">继续查看面试记录</a-button>
            <a-button block @click="goBackToCoding">回到代码工作台</a-button>
            <a-button block type="primary" :loading="finalizing" @click="finalizeResult(true)">
              重新生成结果
            </a-button>
          </div>
        </div>
      </aside>
    </div>

    <InterviewKnowledgeLearnModal v-model:open="learningModalVisible" :resource="activeLearningResource" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import InterviewScorePanel from '@/components/InterviewScorePanel.vue'
import InterviewKnowledgeLearnModal from '@/components/interview/InterviewKnowledgeLearnModal.vue'
import { interviewCodeApi } from '@/apis/interview_code'
import { useThemeStore } from '@/stores/theme'
import { formatDateTime } from '@/utils/time'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const loading = ref(false)
const finalizing = ref(false)
const payload = ref(null)
const improvementPlanPayload = ref(null)
const learningModalVisible = ref(false)
const activeLearningResource = ref(null)

const threadId = computed(() => String(route.query.threadId || '').trim())
const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || '初试')
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))

const parseThreadTitle = (title) => {
  const normalizedTitle = String(title || '').trim()
  if (!normalizedTitle || !normalizedTitle.includes('·')) {
    return {
      position: selectedPosition.value,
      round: selectedRound.value
    }
  }

  const [position, round] = normalizedTitle.split('·', 2)
  return {
    position: String(position || '').trim() || selectedPosition.value,
    round: String(round || '').trim() || selectedRound.value
  }
}

const result = computed(() => payload.value?.result || null)
const codingSession = computed(() => payload.value?.coding_session || null)
const scorecard = computed(() => result.value?.scorecard || null)
const improvementPlan = computed(
  () => improvementPlanPayload.value?.improvement_plan || result.value?.improvement_plan || null
)
const expressionAnalysis = computed(() => result.value?.expression_analysis || null)
const summaryMarkdown = computed(() =>
  String(result.value?.summary_markdown || '')
    .replace(/\n*\s*完整结果已生成，可在面试结果页查看。?\s*$/u, '')
    .trim()
)
const hasCompletedResult = computed(() => result.value?.status === 'completed' && !!scorecard.value)
const isGenerating = computed(() => result.value?.status === 'generating')
const failedMessage = computed(() => (result.value?.status === 'failed' ? result.value?.error_message || '请稍后重试' : ''))
const threadTitle = computed(() => payload.value?.title || `${selectedPosition.value} · ${selectedRound.value}`)
const threadContext = computed(() => parseThreadTitle(payload.value?.title || ''))
const displayPosition = computed(
  () => scorecard.value?.role || codingSession.value?.target_position || threadContext.value.position || selectedPosition.value
)
const displayRound = computed(
  () => scorecard.value?.round || threadContext.value.round || selectedRound.value
)
const resultRoute = computed(() => ({
  name: 'InterviewResultPage',
  query: {
    threadId: threadId.value,
    position: displayPosition.value,
    round: displayRound.value
  }
}))
const generatedAtText = computed(() => (result.value?.generated_at ? formatDateTime(result.value.generated_at) : ''))
const expressionMetrics = computed(() => {
  const analysis = expressionAnalysis.value
  if (!analysis) return []

  return [
    { key: 'speech_rate', label: '语速', metric: analysis.speech_rate },
    { key: 'pause_control', label: '停顿控制', metric: analysis.pause_control },
    { key: 'clarity', label: '清晰度', metric: analysis.clarity },
    { key: 'confidence', label: '自信度', metric: analysis.confidence }
  ].filter((item) => item.metric)
})

const judgeStatus = computed(
  () => String(codingSession.value?.judge_status || codingSession.value?.judge_result?.status || '').trim() || 'UNKNOWN'
)

const judgeStatusLabelMap = {
  PENDING: '等待判题',
  JUDGING: '判题中',
  ACCEPTED: '通过',
  WRONG_ANSWER: '答案错误',
  COMPILE_ERROR: '编译错误',
  RUNTIME_ERROR: '运行错误',
  SYSTEM_ERROR: '系统错误',
  MEMORY_LIMIT_EXCEEDED: '内存超限',
  CPU_TIME_LIMIT_EXCEEDED: 'CPU 超时',
  REAL_TIME_LIMIT_EXCEEDED: '运行超时',
  PARTIALLY_ACCEPTED: '部分通过'
}

const judgeStatusColor = computed(() => {
  if (judgeStatus.value === 'ACCEPTED') return 'green'
  if (['PENDING', 'JUDGING'].includes(judgeStatus.value)) return 'blue'
  if (
    ['WRONG_ANSWER', 'COMPILE_ERROR', 'RUNTIME_ERROR', 'SYSTEM_ERROR', 'MEMORY_LIMIT_EXCEEDED', 'CPU_TIME_LIMIT_EXCEEDED', 'REAL_TIME_LIMIT_EXCEEDED'].includes(
      judgeStatus.value
    )
  ) {
    return 'red'
  }
  return 'gold'
})

const judgeStatusLabel = computed(() => judgeStatusLabelMap[judgeStatus.value] || judgeStatus.value)

const dimensionLabelMap = {
  technical_competence: '技术能力',
  problem_solving: '问题解决',
  communication: '沟通表达',
  soft_skills: '综合素质'
}

const getDimensionLabel = (key) => dimensionLabelMap[key] || key || '待分析'

const getResourceTypeLabel = (type) => {
  const labelMap = {
    knowledge: '知识库 QA',
    interview_question: '编程题',
    communication: '沟通表达'
  }
  return labelMap[type] || type || '资源'
}

const getResourceTagColor = (type) => {
  const colorMap = {
    knowledge: 'blue',
    interview_question: 'gold',
    communication: 'green'
  }
  return colorMap[type] || 'default'
}

const canLearnResource = (resource) => {
  const locator = resource?.locator
  return (
    resource?.resource_type === 'knowledge' &&
    locator &&
    String(locator.db_id || '').trim() &&
    String(locator.file_id || '').trim()
  )
}

const openLearningResource = (resource) => {
  activeLearningResource.value = resource
  learningModalVisible.value = true
}

const loadImprovementPlan = async () => {
  if (!threadId.value) return
  try {
    improvementPlanPayload.value = await interviewCodeApi.getImprovementPlan(threadId.value)
  } catch (error) {
    improvementPlanPayload.value = null
  }
}

const loadResult = async () => {
  if (!threadId.value) return
  loading.value = true
  try {
    payload.value = await interviewCodeApi.getInterviewResult(threadId.value)
    await loadImprovementPlan()
  } catch (error) {
    message.error(error.message || '加载面试结果失败')
  } finally {
    loading.value = false
  }
}

const finalizeResult = async (force = false) => {
  if (!threadId.value) return
  finalizing.value = true
  try {
    payload.value = await interviewCodeApi.finalizeInterviewResult(threadId.value, {
      target_position: displayPosition.value,
      interview_round: displayRound.value,
      force
    })
    await loadImprovementPlan()
    if ((payload.value?.result || {}).status === 'completed') {
      router.replace(resultRoute.value)
      message.success(force ? '面试结果已重新生成' : '面试结果已生成')
    }
  } catch (error) {
    message.error(error.message || '生成面试结果失败')
    await loadResult()
  } finally {
    finalizing.value = false
  }
}

const goBackToInterview = () => {
  router.push({
    name: 'AgentInterviewComp',
    query: {
      threadId: threadId.value,
      position: displayPosition.value,
      round: displayRound.value
    }
  })
}

const goBackToCoding = () => {
  router.push({
    name: 'InterviewCodingWorkbench',
    query: {
      threadId: threadId.value,
      position: displayPosition.value,
      round: displayRound.value
    }
  })
}

onMounted(async () => {
  if (!threadId.value) {
    router.replace({
      name: 'AgentComp',
      query: {
        position: displayPosition.value,
        round: displayRound.value
      }
    })
    return
  }

  await loadResult()
  if (!hasCompletedResult.value && !isGenerating.value && route.query.autoGenerate === '1') {
    await finalizeResult()
  }
})
</script>

<style lang="less" scoped>
.interview-result-view {
  min-height: 100%;
  padding: 20px;
  background: var(--gray-50);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-toolbar,
.panel-card {
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
}

.result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
}

.toolbar-title,
.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-900);
}

.toolbar-subtitle,
.panel-meta,
.empty-text,
.state-desc,
.summary-label {
  font-size: 13px;
  color: var(--gray-500);
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.state-panel {
  min-height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  padding: 24px;
}

.state-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-900);
}

.result-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
  gap: 16px;
  align-items: start;
}

.main-column,
.side-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  padding: 18px 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.panel-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}

.expression-meta {
  margin-top: 6px;
}

.summary-preview {
  margin-top: 14px;
}

.improvement-layout {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-top: 14px;
}

.improvement-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.improvement-section__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.improvement-grid,
.resource-list,
.task-list,
.focus-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.improvement-card,
.resource-item,
.task-item,
.focus-item {
  padding: 14px;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-25);
}

.improvement-card__top,
.resource-item__top,
.task-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.improvement-card__title,
.resource-item__title,
.task-item__title,
.focus-item__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-900);
}

.resource-item__title-group,
.resource-item__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
}

.resource-item__actions {
  width: auto;
  flex-wrap: wrap;
}

.resource-item__learn-btn {
  padding-inline: 0;
}

.improvement-card__desc,
.resource-item__summary,
.task-item__objective,
.focus-item__desc {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-600);
}

.task-item__meta,
.focus-item__tag {
  color: var(--gray-500);
  font-size: 12px;
}

.focus-item__tag {
  margin-left: 8px;
}

.expression-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.expression-card {
  padding: 14px;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-25);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.expression-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.expression-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.expression-card__score {
  display: flex;
  align-items: baseline;
  gap: 3px;
  color: var(--main-color);
}

.expression-card__number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.expression-card__unit {
  font-size: 12px;
  color: var(--gray-500);
}

.expression-card__value {
  font-size: 13px;
  color: var(--gray-700);
  font-weight: 500;
}

.expression-card__detail {
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-600);
}

.coding-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary-value {
  flex: 1;
  text-align: right;
  color: var(--gray-800);
  font-size: 14px;
  word-break: break-word;
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 960px) {
  .result-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .result-layout {
    grid-template-columns: 1fr;
  }

  .summary-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-value {
    text-align: left;
  }

  .improvement-card__top,
  .resource-item__top,
  .resource-item__title-group,
  .task-item {
    flex-direction: column;
  }
}
</style>
