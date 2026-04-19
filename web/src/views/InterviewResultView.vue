<template>
  <div class="interview-result-view">
    <div class="result-toolbar">
      <div>
        <div class="toolbar-title">面试结果</div>
        <div class="toolbar-subtitle">把这轮最关键的结论、证据和复盘重点放在一页里</div>
      </div>
      <div class="toolbar-actions">
        <a-button @click="goBackToInterview">返回面试记录</a-button>
        <a-button @click="goBackToCoding">返回代码考核</a-button>
        <a-button type="primary" :loading="finalizing" @click="finalizeResult(true)"
          >重新生成结果</a-button
        >
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin />
    </div>

    <div v-else-if="failedMessage" class="state-panel">
      <a-result status="warning" title="面试结果生成失败" :sub-title="failedMessage">
        <template #extra>
          <a-button type="primary" :loading="finalizing" @click="finalizeResult(true)"
            >重新生成</a-button
          >
        </template>
      </a-result>
    </div>

    <div v-else-if="isGenerating" class="state-panel">
      <a-spin size="large" />
      <div class="state-title">正在生成面试结果</div>
      <div class="state-desc">
        系统正在整合本轮表现、技术题作答、表达分析和代码考核结果，请稍候。
      </div>
    </div>

    <div v-else-if="!hasCompletedResult" class="state-panel">
      <a-empty description="当前还没有可展示的面试结果">
        <a-button type="primary" :loading="finalizing" @click="finalizeResult()"
          >生成面试结果</a-button
        >
      </a-empty>
    </div>

    <template v-else>
      <section id="section-conclusion" class="hero-card">
        <div class="hero-main">
          <div class="hero-eyebrow">
            <span>成长型反馈报告</span>
            <span v-if="generatedAtText">生成于 {{ generatedAtText }}</span>
          </div>
          <h1 class="hero-title">{{ heroTitle }}</h1>
          <p class="hero-summary">{{ heroSummary }}</p>

          <div class="hero-meta">
            <a-tag color="processing">{{ displayPosition }}</a-tag>
            <a-tag color="default">{{ displayRound }}</a-tag>
            <a-tag color="green">已完成</a-tag>
            <a-tag v-if="overallScore !== null" color="gold">综合 {{ overallScore }}/100</a-tag>
          </div>

          <div class="hero-actions">
            <a-button type="primary" size="large" @click="scrollToSection('section-report')">
              查看完整报告
              <template #icon><RightOutlined /></template>
            </a-button>
            <a-button size="large" @click="scrollToSection('section-evidence')">
              查看证据依据
              <template #icon><FileSearchOutlined /></template>
            </a-button>
          </div>
        </div>

        <div class="hero-score-panel">
          <div class="hero-score-label">当前阶段</div>
          <div class="hero-score-value">{{ heroStageLabel }}</div>
          <div class="hero-score-note">
            {{
              primaryActionHighlight?.summary ||
              primaryRiskHighlight?.summary ||
              '先抓住最影响通过率的问题，再进入完整报告做定向复盘。'
            }}
          </div>
        </div>
      </section>

      <nav class="section-nav">
        <button
          v-for="item in sectionLinks"
          :key="item.id"
          type="button"
          class="section-nav__item"
          @click="scrollToSection(item.id)"
        >
          {{ item.label }}
        </button>
      </nav>

      <section class="summary-grid">
        <article v-for="item in heroCards" :key="item.tone" :class="['summary-card', item.tone]">
          <div class="summary-card__icon">
            <component :is="item.icon" />
          </div>
          <div class="summary-card__content">
            <div class="summary-card__eyebrow">{{ item.eyebrow }}</div>
            <div class="summary-card__title">{{ item.title }}</div>
            <div class="summary-card__desc">{{ item.summary }}</div>
          </div>
        </article>
      </section>

      <section id="section-insights" class="section-card">
        <div class="section-header">
          <div>
            <div class="section-title">高价值洞察</div>
            <div class="section-subtitle">只保留最值得认真看的 3 条结论，并明确展示判断依据</div>
          </div>
        </div>

        <div class="insight-list">
          <article
            v-for="item in normalizedReportHighlights"
            :key="`${item.priority}-${item.title}`"
            :class="['insight-card', item.tone]"
          >
            <div class="insight-card__top">
              <div class="insight-card__title-wrap">
                <div class="insight-card__priority">0{{ item.priority }}</div>
                <div class="insight-card__title">{{ item.title }}</div>
              </div>
              <a-tag :color="highlightToneColorMap[item.tone]">{{
                highlightToneLabelMap[item.tone]
              }}</a-tag>
            </div>
            <div class="insight-card__summary">{{ item.summary }}</div>
            <div class="insight-card__evidence">
              <span class="insight-card__evidence-label">依据：</span>
              <a-tag
                v-for="refItem in item.evidence_refs"
                :key="`${item.title}-${refItem.key}`"
                class="evidence-tag"
                @click="scrollToSection('section-evidence')"
              >
                {{ refItem.label }}
              </a-tag>
            </div>
          </article>
        </div>
      </section>

      <section id="section-evidence" class="section-card">
        <div class="section-header">
          <div>
            <div class="section-title">证据深挖</div>
            <div class="section-subtitle">
              结论不是凭感觉给的，而是来自题目级记录、维度分数、表达分析和代码结果
            </div>
          </div>
        </div>

        <div class="evidence-overview">
          <article v-for="item in dimensionScoreCards" :key="item.key" class="dimension-card">
            <div class="dimension-card__label">{{ item.label }}</div>
            <div class="dimension-card__value">{{ item.score }}</div>
            <div class="dimension-card__track">
              <div class="dimension-card__fill" :style="{ width: `${item.score}%` }"></div>
            </div>
          </article>
        </div>

        <div v-if="expressionMetrics.length" class="evidence-subsection">
          <div class="subsection-title">表达分析</div>
          <div class="expression-grid">
            <article v-for="item in expressionMetrics" :key="item.key" class="expression-card">
              <div class="expression-card__top">
                <span class="expression-card__label">{{ item.label }}</span>
                <a-tag color="default">{{ item.metric.level || '已分析' }}</a-tag>
              </div>
              <div class="expression-card__score">{{ item.metric.score ?? '--' }}/100</div>
              <div v-if="item.metric.value" class="expression-card__value">
                {{ item.metric.value }}
              </div>
              <div v-if="item.metric.detail" class="expression-card__detail">
                {{ item.metric.detail }}
              </div>
            </article>
          </div>
        </div>

        <div class="evidence-subsection">
          <div class="subsection-title">技术题作答效果</div>
          <div v-if="displayedQuestionReviews.length" class="question-review-list">
            <article
              v-for="item in displayedQuestionReviews"
              :key="`${item.question_index}-${item.question}`"
              class="question-review-card"
            >
              <div class="question-review-card__top">
                <div class="question-review-card__title-group">
                  <span class="question-review-card__index">技术题 {{ item.question_index }}</span>
                  <div class="question-review-card__title">{{ item.question }}</div>
                </div>
                <div class="question-review-card__actions">
                  <a-tag :color="getQuestionScoreColor(item.score)">{{
                    item.level || '待评估'
                  }}</a-tag>
                  <a-tag color="default">{{ item.score ?? '--' }}/100</a-tag>
                  <a-button
                    v-if="canOpenQuestionSource(item)"
                    size="small"
                    type="link"
                    @click="openQuestionSource(item)"
                  >
                    查看题源
                  </a-button>
                </div>
              </div>

              <div class="question-review-card__meta">
                <span v-if="item.kb_name">{{ item.kb_name }}</span>
                <span v-if="item.file_name">{{ item.file_name }}</span>
                <span v-if="item.asked_at">提问于 {{ item.asked_at }}</span>
              </div>

              <div class="question-review-card__section">
                <div class="question-review-card__label">用户回答</div>
                <div class="question-review-card__content">
                  {{ item.answer_excerpt || '未记录到有效回答' }}
                </div>
              </div>

              <div
                v-if="item.matched_keywords?.length || item.suggested_keywords?.length"
                class="question-review-card__tags"
              >
                <a-tag
                  v-for="keyword in item.matched_keywords"
                  :key="`${item.question_index}-hit-${keyword}`"
                  color="green"
                >
                  已覆盖：{{ keyword }}
                </a-tag>
                <a-tag
                  v-for="keyword in item.suggested_keywords"
                  :key="`${item.question_index}-miss-${keyword}`"
                  color="gold"
                >
                  待补充：{{ keyword }}
                </a-tag>
              </div>

              <div class="question-review-card__grid">
                <div class="question-review-card__col">
                  <div class="question-review-card__label">表现亮点</div>
                  <div v-if="item.strengths?.length" class="question-review-card__list">
                    <div
                      v-for="point in item.strengths"
                      :key="`${item.question_index}-strength-${point}`"
                      class="question-review-card__list-item success"
                    >
                      {{ point }}
                    </div>
                  </div>
                  <div v-else class="question-review-card__empty">暂无明显亮点</div>
                </div>

                <div class="question-review-card__col">
                  <div class="question-review-card__label">改进建议</div>
                  <div v-if="item.gaps?.length" class="question-review-card__list">
                    <div
                      v-for="point in item.gaps"
                      :key="`${item.question_index}-gap-${point}`"
                      class="question-review-card__list-item warning"
                    >
                      {{ point }}
                    </div>
                  </div>
                  <div v-else class="question-review-card__empty">当前没有明显短板</div>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="empty-text">本轮还没有可展示的技术题证据</div>

          <div
            v-if="technicalQuestionReviews.length > initialQuestionReviewCount"
            class="subsection-actions"
          >
            <a-button type="link" @click="showAllQuestionReviews = !showAllQuestionReviews">
              {{
                showAllQuestionReviews
                  ? '收起更多题目'
                  : `展开全部 ${technicalQuestionReviews.length} 道题`
              }}
            </a-button>
          </div>
        </div>

        <div class="evidence-subsection">
          <div class="subsection-title">代码考核摘要</div>
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
      </section>

      <section id="section-report" class="section-card report-section">
        <div class="section-header report-section__header">
          <div>
            <div class="section-title">完整报告</div>
            <div class="section-subtitle">从综合判断、维度表现到题目样本，完整复盘这轮面试表现</div>
          </div>
          <div class="report-section__meta">
            <a-tag color="processing">{{ displayPosition }}</a-tag>
            <a-tag color="default">{{ displayRound }}</a-tag>
            <a-tag v-if="overallScore !== null" color="gold">综合 {{ overallScore }}/100</a-tag>
          </div>
        </div>

        <div class="report-overview">
          <article class="report-stat-card report-stat-card--score">
            <div class="report-stat-card__label">综合评分</div>
            <div class="report-stat-card__value">{{ overallScore ?? '--' }}</div>
            <div class="report-stat-card__desc">{{ heroStageLabel }}</div>
          </article>

          <article class="report-stat-card">
            <div class="report-stat-card__label">面试信息</div>
            <div class="report-stat-card__value report-stat-card__value--small">
              {{ displayRound }}
            </div>
            <div class="report-stat-card__desc">{{ generatedAtText || '已生成结果报告' }}</div>
          </article>

          <article class="report-stat-card">
            <div class="report-stat-card__label">技术题表现</div>
            <div class="report-stat-card__value report-stat-card__value--small">
              {{ technicalQuestionReviews.length }} 道
            </div>
            <div class="report-stat-card__desc">
              {{
                questionScoreSummary.lowest
                  ? `最低 ${questionScoreSummary.lowest.score ?? '--'} / 最高 ${questionScoreSummary.highest?.score ?? '--'}`
                  : '暂无题目评分数据'
              }}
            </div>
          </article>

          <article class="report-stat-card" v-if="codingSession">
            <div class="report-stat-card__label">代码考核</div>
            <div class="report-stat-card__value report-stat-card__value--small">
              {{ judgeStatusLabel }}
            </div>
            <div class="report-stat-card__desc">
              {{ codingSession.problem_title || '已记录本轮代码考核结果' }}
            </div>
          </article>
        </div>

        <div class="report-body">
          <div class="report-main">
            <div v-if="summaryMarkdown" class="report-panel report-panel--summary">
              <div class="subsection-title">综合结论</div>
              <MdPreview
                editor-id="interview-result-summary"
                :theme="theme"
                preview-theme="github"
                :show-code-row-number="false"
                :model-value="summaryMarkdown"
                class="summary-preview"
              />
            </div>

            <div v-if="scorecard" class="report-panel">
              <div class="subsection-title">评分总览</div>
              <InterviewScorePanel :scorecard="scorecard" />
            </div>

            <div v-if="technicalQuestionReviews.length" class="report-panel">
              <div class="subsection-title">代表题目复盘</div>
              <div class="report-question-list">
                <article
                  v-for="item in reportQuestionSamples"
                  :key="`report-${item.question_index}-${item.question}`"
                  class="report-question-card"
                >
                  <div class="report-question-card__top">
                    <div>
                      <div class="report-question-card__eyebrow">
                        技术题 {{ item.question_index }}
                      </div>
                      <div class="report-question-card__title">{{ item.question }}</div>
                    </div>
                    <a-tag :color="getQuestionScoreColor(item.score)"
                      >{{ item.score ?? '--' }}/100</a-tag
                    >
                  </div>
                  <div class="report-question-card__summary">
                    {{ item.answer_excerpt || '未记录到有效回答。' }}
                  </div>
                  <div v-if="item.gaps?.length" class="report-question-card__insight">
                    复盘重点：{{ item.gaps[0] }}
                  </div>
                </article>
              </div>
            </div>
          </div>

          <aside class="report-side">
            <div v-if="dimensionScoreCards.length" class="report-panel report-side-card">
              <div class="subsection-title">维度概览</div>
              <div class="report-dimension-list">
                <div
                  v-for="item in dimensionScoreCards"
                  :key="`report-dimension-${item.key}`"
                  class="report-dimension-item"
                >
                  <div class="report-dimension-item__top">
                    <span>{{ item.label }}</span>
                    <span>{{ item.score }}</span>
                  </div>
                  <div class="dimension-card__track">
                    <div class="dimension-card__fill" :style="{ width: `${item.score}%` }"></div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="scorecard?.strengths?.length" class="report-panel report-side-card">
              <div class="subsection-title">亮点</div>
              <ul class="report-list">
                <li v-for="item in scorecard.strengths" :key="`strength-${item}`">{{ item }}</li>
              </ul>
            </div>

            <div v-if="scorecard?.risks?.length" class="report-panel report-side-card">
              <div class="subsection-title">风险点</div>
              <ul class="report-list">
                <li v-for="item in scorecard.risks" :key="`risk-${item}`">{{ item }}</li>
              </ul>
            </div>

            <div v-if="scorecard?.suggestions?.length" class="report-panel report-side-card">
              <div class="subsection-title">原始改进建议</div>
              <ul class="report-list">
                <li v-for="item in scorecard.suggestions" :key="`suggestion-${item}`">
                  {{ item }}
                </li>
              </ul>
            </div>

            <div v-if="codingSession" class="report-panel report-side-card">
              <div class="subsection-title">代码考核摘要</div>
              <div class="coding-summary">
                <div class="summary-row">
                  <span class="summary-label">题目</span>
                  <span class="summary-value">{{ codingSession.problem_title || '-' }}</span>
                </div>
                <div class="summary-row">
                  <span class="summary-label">判题结果</span>
                  <a-tag :color="judgeStatusColor">{{ judgeStatusLabel }}</a-tag>
                </div>
                <div class="summary-row" v-if="codingSession.judge_result?.score !== undefined">
                  <span class="summary-label">判题得分</span>
                  <span class="summary-value">{{ codingSession.judge_result.score }}</span>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <InterviewKnowledgeLearnModal
        v-model:open="learningModalVisible"
        :resource="activeLearningResource"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  FileSearchOutlined,
  FireOutlined,
  RightOutlined,
  RocketOutlined
} from '@ant-design/icons-vue'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

import InterviewScorePanel from '@/components/InterviewScorePanel.vue'
import InterviewKnowledgeLearnModal from '@/components/interview/InterviewKnowledgeLearnModal.vue'
import { interviewCodeApi } from '@/apis/interview_code'
import { useThemeStore } from '@/stores/theme'
import { formatDateTime } from '@/utils/time'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const initialQuestionReviewCount = 2
const sectionLinks = [
  { id: 'section-conclusion', label: '结论' },
  { id: 'section-evidence', label: '证据' },
  { id: 'section-report', label: '完整报告' }
]
const highlightToneColorMap = {
  risk: 'gold',
  strength: 'green',
  action: 'processing'
}
const highlightToneLabelMap = {
  risk: '优先修复',
  strength: '继续保持',
  action: '建议关注'
}
const dimensionLabelMap = {
  technical_competence: '技术能力',
  technical_knowledge: '技术能力',
  practical_experience: '技术能力',
  problem_solving: '问题解决',
  problem_solving_innovation: '问题解决',
  communication: '沟通表达',
  communication_clarity: '沟通表达',
  soft_skills: '综合素质',
  soft_skills_team_fit: '综合素质'
}
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

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const loading = ref(false)
const finalizing = ref(false)
const payload = ref(null)
const learningModalVisible = ref(false)
const activeLearningResource = ref(null)
const showAllQuestionReviews = ref(false)

const threadId = computed(() => String(route.query.threadId || '').trim())
const selectedPosition = computed(
  () => String(route.query.position || '').trim() || DEFAULT_POSITION
)
const selectedRound = computed(() => String(route.query.round || '').trim() || '初试')
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))

const normalizeDimensionKey = (value) => {
  const key = String(value || '')
    .trim()
    .toLowerCase()
  if (!key) return ''
  const map = {
    technical_competence: 'technical_competence',
    technical_knowledge: 'technical_competence',
    practical_experience: 'technical_competence',
    技术能力: 'technical_competence',
    problem_solving: 'problem_solving',
    problem_solving_innovation: 'problem_solving',
    问题解决: 'problem_solving',
    communication: 'communication',
    communication_clarity: 'communication',
    沟通表达: 'communication',
    soft_skills: 'soft_skills',
    soft_skills_team_fit: 'soft_skills',
    综合素质: 'soft_skills'
  }
  return map[key] || key
}

const getDimensionLabel = (key) => dimensionLabelMap[normalizeDimensionKey(key)] || key || '待分析'

const normalizeScore = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return null
  return Math.max(0, Math.min(100, Math.round(numeric)))
}

const parseThreadTitle = (title) => {
  const normalizedTitle = String(title || '').trim()
  if (!normalizedTitle) {
    return {
      position: selectedPosition.value,
      round: selectedRound.value
    }
  }

  const separatorPatterns = [/\s*[·•｜|]\s*/, /\s+[?？]\s+/, /\s+[-—–]+\s+/]
  for (const pattern of separatorPatterns) {
    const matched = normalizedTitle.match(pattern)
    if (!matched || matched.index === undefined) continue
    const position = normalizedTitle.slice(0, matched.index).trim()
    const round = normalizedTitle.slice(matched.index + matched[0].length).trim()
    if (!position || !round) continue
    return {
      position,
      round
    }
  }

  return {
    position: normalizedTitle,
    round: selectedRound.value
  }
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

const normalizeCodingSession = (value) => {
  if (!value || typeof value !== 'object') return null
  return {
    ...value,
    submitted_at: value.submitted_at ? formatDateTime(value.submitted_at) : ''
  }
}

const result = computed(() => payload.value?.result || null)
const codingSession = computed(() => normalizeCodingSession(payload.value?.coding_session || null))
const scorecard = computed(() => result.value?.scorecard || null)
const expressionAnalysis = computed(() => result.value?.expression_analysis || null)
const reportHighlights = computed(() =>
  Array.isArray(result.value?.report_highlights) ? result.value.report_highlights : []
)
const summaryMarkdown = computed(() =>
  String(result.value?.summary_markdown || '')
    .replace(/\n*\s*完整结果已生成，可在面试结果页查看。?\s*$/u, '')
    .trim()
)
const hasCompletedResult = computed(
  () =>
    result.value?.status === 'completed' &&
    Boolean(
      scorecard.value ||
      summaryMarkdown.value ||
      reportHighlights.value.length ||
      technicalQuestionReviews.value.length
    )
)
const isGenerating = computed(() => result.value?.status === 'generating')
const failedMessage = computed(() =>
  result.value?.status === 'failed' ? result.value?.error_message || '请稍后重试' : ''
)
const threadTitle = computed(
  () => payload.value?.title || `${selectedPosition.value} · ${selectedRound.value}`
)
const threadContext = computed(() => parseThreadTitle(threadTitle.value))
const displayPosition = computed(
  () =>
    scorecard.value?.role ||
    codingSession.value?.target_position ||
    threadContext.value.position ||
    selectedPosition.value
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
const generatedAtText = computed(() =>
  result.value?.generated_at ? formatDateTime(result.value.generated_at) : ''
)
const overallScore = computed(() =>
  normalizeScore(
    scorecard.value?.overall ?? scorecard.value?.overall_score ?? scorecard.value?.total_score
  )
)

const dimensionScoreCards = computed(() => {
  const dimensions = Array.isArray(scorecard.value?.dimensions) ? scorecard.value.dimensions : []
  return dimensions
    .map((item) => {
      const key = normalizeDimensionKey(item?.key || item?.name)
      const score = normalizeScore(item?.score)
      if (!key || score === null) return null
      return {
        key,
        label: getDimensionLabel(key),
        score
      }
    })
    .filter(Boolean)
    .sort((a, b) => a.score - b.score)
})

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

const technicalQuestionReviews = computed(() => {
  const items = Array.isArray(result.value?.technical_question_reviews)
    ? result.value.technical_question_reviews
    : []
  return items
    .map((item, index) => ({
      ...item,
      question_index: Number(item?.question_index || index + 1),
      score: normalizeScore(item?.score),
      asked_at: item?.asked_at ? formatDateTime(item.asked_at) : '',
      locator: resolveLearningLocator(item)
    }))
    .sort((a, b) => (a.question_index || 0) - (b.question_index || 0))
})

const displayedQuestionReviews = computed(() =>
  showAllQuestionReviews.value
    ? technicalQuestionReviews.value
    : technicalQuestionReviews.value.slice(0, initialQuestionReviewCount)
)
const questionScoreSummary = computed(() => {
  const scored = technicalQuestionReviews.value.filter((item) => item.score !== null)
  if (!scored.length) {
    return {
      lowest: null,
      highest: null
    }
  }
  const sortedByScore = [...scored].sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
  return {
    lowest: sortedByScore[0],
    highest: sortedByScore[sortedByScore.length - 1]
  }
})
const reportQuestionSamples = computed(() => {
  const samples = []
  if (questionScoreSummary.value.lowest) samples.push(questionScoreSummary.value.lowest)
  if (
    questionScoreSummary.value.highest &&
    questionScoreSummary.value.highest.question_index !==
      questionScoreSummary.value.lowest?.question_index
  ) {
    samples.push(questionScoreSummary.value.highest)
  }
  if (samples.length >= 2) return samples
  return technicalQuestionReviews.value.slice(0, 2)
})

const judgeStatus = computed(
  () =>
    String(
      codingSession.value?.judge_status || codingSession.value?.judge_result?.status || ''
    ).trim() || 'UNKNOWN'
)
const judgeStatusColor = computed(() => {
  if (judgeStatus.value === 'ACCEPTED') return 'green'
  if (['PENDING', 'JUDGING'].includes(judgeStatus.value)) return 'blue'
  if (
    [
      'WRONG_ANSWER',
      'COMPILE_ERROR',
      'RUNTIME_ERROR',
      'SYSTEM_ERROR',
      'MEMORY_LIMIT_EXCEEDED',
      'CPU_TIME_LIMIT_EXCEEDED',
      'REAL_TIME_LIMIT_EXCEEDED'
    ].includes(judgeStatus.value)
  ) {
    return 'red'
  }
  return 'gold'
})
const judgeStatusLabel = computed(() => judgeStatusLabelMap[judgeStatus.value] || judgeStatus.value)

const fallbackHighlights = computed(() => {
  const items = []
  const sortedReviews = [...technicalQuestionReviews.value].sort(
    (a, b) => (a.score ?? 999) - (b.score ?? 999)
  )
  const lowReview = sortedReviews[0]
  const highReview = [...technicalQuestionReviews.value].sort(
    (a, b) => (b.score ?? -1) - (a.score ?? -1)
  )[0]
  const weakDimension = dimensionScoreCards.value[0]
  const strongDimension = [...dimensionScoreCards.value].sort((a, b) => b.score - a.score)[0]

  if (lowReview) {
    items.push({
      title: `${lowReview.question || '最低分技术题'}需要优先补强`,
      summary:
        lowReview.gaps?.[0] || '这道技术题的答题深度和关键词覆盖仍然不足，建议优先回看相关知识点。',
      tone: 'risk',
      dimension_key: 'technical_competence',
      priority: 1,
      evidence_refs: [
        {
          kind: 'question_review',
          key: `question_review:${lowReview.question_index}`,
          label: `技术题 ${lowReview.question_index} · ${lowReview.score ?? '--'} 分`
        }
      ]
    })
  } else if (weakDimension) {
    items.push({
      title: `${weakDimension.label}是当前最需要补的维度`,
      summary: `当前最低分维度为${weakDimension.label}，建议优先补这部分的知识结构和答题方式。`,
      tone: 'risk',
      dimension_key: weakDimension.key,
      priority: 1,
      evidence_refs: [
        {
          kind: 'dimension',
          key: weakDimension.key,
          label: `${weakDimension.label} · ${weakDimension.score} 分`
        }
      ]
    })
  }

  if (highReview && (highReview.score ?? 0) >= 80) {
    items.push({
      title: '有一项能力已经值得保留',
      summary:
        highReview.strengths?.[0] || '至少有一题回答已经比较完整，可以作为后续答题模板保留下来。',
      tone: 'strength',
      dimension_key: 'technical_competence',
      priority: 2,
      evidence_refs: [
        {
          kind: 'question_review',
          key: `question_review:${highReview.question_index}`,
          label: `技术题 ${highReview.question_index} · ${highReview.score ?? '--'} 分`
        }
      ]
    })
  } else if (scorecard.value?.strengths?.length) {
    items.push({
      title: '这轮已经有可继续保持的强项',
      summary: scorecard.value.strengths[0],
      tone: 'strength',
      dimension_key: strongDimension?.key || '',
      priority: 2,
      evidence_refs: strongDimension
        ? [
            {
              kind: 'dimension',
              key: strongDimension.key,
              label: `${strongDimension.label} · ${strongDimension.score} 分`
            }
          ]
        : []
    })
  }

  if (weakDimension) {
    items.push({
      title: `建议优先复盘 ${weakDimension.label}`,
      summary: `先围绕 ${weakDimension.label} 复盘本轮证据和失分点，再针对性准备下一轮。`,
      tone: 'action',
      dimension_key: weakDimension.key,
      priority: 3,
      evidence_refs: [
        {
          kind: 'dimension',
          key: weakDimension.key,
          label: `${weakDimension.label} · ${weakDimension.score} 分`
        }
      ]
    })
  } else if (lowReview) {
    items.push({
      title: `建议先复盘技术题 ${lowReview.question_index}`,
      summary: '先把这道题的回答结构、关键词覆盖和解释深度补齐，再进入下一轮准备。',
      tone: 'action',
      dimension_key: 'technical_competence',
      priority: 3,
      evidence_refs: [
        {
          kind: 'question_review',
          key: `question_review:${lowReview.question_index}`,
          label: `技术题 ${lowReview.question_index} · ${lowReview.score ?? '--'} 分`
        }
      ]
    })
  }

  return items.slice(0, 3)
})

const normalizedReportHighlights = computed(() => {
  const source = reportHighlights.value.length ? reportHighlights.value : fallbackHighlights.value
  return source
    .map((item, index) => ({
      title: String(item?.title || '').trim() || `洞察 ${index + 1}`,
      summary: String(item?.summary || '').trim() || '系统已提炼出一条关键判断。',
      tone: ['risk', 'strength', 'action'].includes(String(item?.tone || '').trim())
        ? item.tone
        : 'action',
      dimension_key: normalizeDimensionKey(item?.dimension_key),
      priority: Number(item?.priority || index + 1),
      evidence_refs: Array.isArray(item?.evidence_refs)
        ? item.evidence_refs
            .map((refItem, refIndex) => ({
              kind: ['question_review', 'dimension', 'expression_metric', 'coding'].includes(
                String(refItem?.kind || '').trim()
              )
                ? refItem.kind
                : 'dimension',
              key: String(refItem?.key || `${index}-${refIndex}`).trim(),
              label: String(refItem?.label || '相关证据').trim()
            }))
            .filter((refItem) => refItem.key)
        : []
    }))
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 3)
})

const primaryRiskHighlight = computed(
  () =>
    normalizedReportHighlights.value.find((item) => item.tone === 'risk') ||
    normalizedReportHighlights.value[0] ||
    null
)
const primaryStrengthHighlight = computed(
  () => normalizedReportHighlights.value.find((item) => item.tone === 'strength') || null
)
const primaryActionHighlight = computed(
  () => normalizedReportHighlights.value.find((item) => item.tone === 'action') || null
)

const heroStageLabel = computed(() => {
  if (primaryRiskHighlight.value?.dimension_key) {
    return `优先关注${getDimensionLabel(primaryRiskHighlight.value.dimension_key)}`
  }
  if ((overallScore.value ?? 0) >= 85) return '进入冲刺优化阶段'
  if ((overallScore.value ?? 0) >= 70) return '进入定向复盘阶段'
  return '进入基础补强阶段'
})

const heroTitle = computed(() => {
  if (primaryRiskHighlight.value?.title) return primaryRiskHighlight.value.title
  if (primaryActionHighlight.value?.title) return primaryActionHighlight.value.title
  return '先把最影响通过率的问题复盘清楚'
})

const heroSummary = computed(() => {
  const strength = primaryStrengthHighlight.value?.summary || '这轮已经出现了可保留的表现片段。'
  const risk = primaryRiskHighlight.value?.summary || '当前还存在会直接影响通过率的短板。'
  const action = primaryActionHighlight.value?.title || '先进入完整报告，定位最需要复盘的环节。'
  return `本轮 ${displayPosition.value}${displayRound.value} 的结果显示：${strength} 当前最需要优先处理的是，${risk} 建议先关注：${action}。`
})

const heroCards = computed(() => [
  {
    tone: 'strength',
    eyebrow: '最强项',
    title: primaryStrengthHighlight.value?.title || '已经有可保留的答题片段',
    summary:
      primaryStrengthHighlight.value?.summary || '先保留这部分稳定发挥，后续继续复用答题结构。',
    icon: RocketOutlined
  },
  {
    tone: 'risk',
    eyebrow: '最影响通过率的问题',
    title: primaryRiskHighlight.value?.title || '当前仍有关键短板',
    summary:
      primaryRiskHighlight.value?.summary || '这部分问题会最先拉低面试官判断，应该优先修复。',
    icon: FireOutlined
  },
  {
    tone: 'action',
    eyebrow: '建议优先复盘',
    title: primaryActionHighlight.value?.title || '先进入完整报告查看关键复盘点',
    summary:
      primaryActionHighlight.value?.summary || '把结论落实到复盘重点，再决定下一轮准备方向。',
    icon: RightOutlined
  }
])

const getQuestionScoreColor = (score) => {
  const normalized = normalizeScore(score)
  if (normalized === null) return 'default'
  if (normalized >= 80) return 'green'
  if (normalized >= 60) return 'gold'
  return 'red'
}

const canOpenQuestionSource = (item) => Boolean(resolveLearningLocator(item))

const openLearningLocator = (resource) => {
  const locator = resolveLearningLocator(resource)
  if (!locator) return
  activeLearningResource.value = {
    ...resource,
    locator
  }
  learningModalVisible.value = true
}

const openQuestionSource = (item) =>
  openLearningLocator({
    title: item.file_name || item.question || '题源知识点',
    summary: item.question || '',
    locator: resolveLearningLocator(item)
  })

const scrollToSection = (id) => {
  if (typeof document === 'undefined') return
  const target = document.getElementById(id)
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const loadResult = async () => {
  if (!threadId.value) return
  loading.value = true
  try {
    payload.value = await interviewCodeApi.getInterviewResult(threadId.value)
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
        position: selectedPosition.value,
        round: selectedRound.value
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
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: linear-gradient(180deg, #fff9ef 0%, var(--gray-10) 220px, var(--gray-25) 100%);
}

.result-toolbar,
.hero-card,
.section-card,
.section-nav {
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 24px;
  box-shadow: 0 10px 24px var(--shadow-0);
}

.result-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  padding: 18px 22px;
}

.toolbar-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-1000);
}

.toolbar-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--gray-600);
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.state-panel {
  min-height: 360px;
  padding: 32px 24px;
  border-radius: 24px;
  border: 1px solid var(--gray-150);
  background: var(--gray-0);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.state-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-1000);
}

.state-desc {
  max-width: 520px;
  text-align: center;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-600);
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.8fr);
  gap: 20px;
  padding: 28px;
  background:
    radial-gradient(circle at top right, rgba(250, 173, 20, 0.12), transparent 28%),
    linear-gradient(135deg, #fffaf2 0%, var(--gray-0) 58%, #f8fbff 100%);
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-eyebrow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
  color: var(--gray-600);
}

.hero-title {
  margin: 0;
  font-size: 34px;
  line-height: 1.2;
  color: var(--gray-2000);
}

.hero-summary {
  margin: 0;
  max-width: 820px;
  font-size: 15px;
  line-height: 1.85;
  color: var(--gray-700);
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 6px;
}

.hero-score-panel {
  padding: 22px;
  border-radius: 20px;
  border: 1px solid rgba(250, 173, 20, 0.18);
  background: rgba(255, 250, 242, 0.92);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
}

.hero-score-label {
  font-size: 13px;
  color: var(--gray-600);
}

.hero-score-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--gray-1000);
}

.hero-score-note {
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-700);
}

.section-nav {
  padding: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  position: sticky;
  top: 12px;
  z-index: 2;
}

.section-nav__item {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--gray-10);
  color: var(--gray-700);
  padding: 10px 16px;
  font-size: 14px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;

  &:hover {
    border-color: var(--main-300);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.summary-card,
.insight-card,
.dimension-card,
.expression-card,
.question-review-card,
.report-stat-card,
.report-panel,
.report-question-card {
  border: 1px solid var(--gray-150);
  border-radius: 20px;
  background: var(--gray-0);
}

.summary-card {
  padding: 20px;
  display: flex;
  gap: 14px;

  &.strength {
    background: linear-gradient(180deg, rgba(82, 196, 26, 0.06) 0%, var(--gray-0) 100%);
  }

  &.risk {
    background: linear-gradient(180deg, rgba(250, 173, 20, 0.08) 0%, var(--gray-0) 100%);
  }

  &.action {
    background: linear-gradient(180deg, rgba(79, 159, 236, 0.08) 0%, var(--gray-0) 100%);
  }
}

.summary-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: var(--gray-10);
  color: var(--main-700);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.summary-card__content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-card__eyebrow {
  font-size: 12px;
  color: var(--gray-500);
}

.summary-card__title {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-1000);
  line-height: 1.4;
}

.summary-card__desc {
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-700);
}

.section-card {
  padding: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--gray-1000);
}

.section-subtitle {
  margin-top: 6px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-600);
}

.insight-list,
.question-review-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.insight-card {
  padding: 18px 20px;

  &.risk {
    border-color: rgba(250, 173, 20, 0.28);
  }

  &.strength {
    border-color: rgba(82, 196, 26, 0.24);
  }

  &.action {
    border-color: rgba(79, 159, 236, 0.24);
  }
}

.insight-card__top,
.question-review-card__top,
.expression-card__top,
.report-question-card__top,
.report-dimension-item__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.insight-card__title-wrap {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.insight-card__priority {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  background: #fff5e8;
  color: var(--color-warning-700);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.insight-card__title {
  font-size: 17px;
  font-weight: 700;
  color: var(--gray-1000);
  line-height: 1.5;
}

.insight-card__summary,
.question-review-card__content,
.question-review-card__empty,
.question-review-card__list-item,
.coding-summary,
.summary-preview,
.empty-text,
.report-question-card__summary,
.report-question-card__insight,
.report-stat-card__desc {
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-700);
}

.insight-card__summary {
  margin-top: 12px;
}

.insight-card__evidence {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.insight-card__evidence-label {
  color: var(--gray-500);
  font-size: 13px;
}

.evidence-tag {
  cursor: pointer;
}

.evidence-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.dimension-card {
  padding: 18px;
}

.dimension-card__label {
  font-size: 13px;
  color: var(--gray-500);
}

.dimension-card__value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  color: var(--gray-1000);
}

.dimension-card__track {
  margin-top: 16px;
  height: 8px;
  border-radius: 999px;
  background: var(--gray-100);
  overflow: hidden;
}

.dimension-card__fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--main-400) 0%, var(--main-600) 100%);
}

.evidence-subsection,
.report-panel + .report-panel {
  margin-top: 22px;
}

.subsection-title {
  margin-bottom: 14px;
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-1000);
}

.expression-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 14px;
}

.expression-card {
  padding: 18px;
}

.expression-card__label,
.question-review-card__label,
.summary-label,
.report-question-card__eyebrow,
.report-stat-card__label {
  font-size: 13px;
  color: var(--gray-500);
}

.expression-card__score {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  color: var(--main-700);
}

.expression-card__value {
  margin-top: 8px;
  font-size: 14px;
  color: var(--gray-800);
}

.expression-card__detail {
  margin-top: 8px;
  font-size: 13px;
  color: var(--gray-600);
  line-height: 1.8;
}

.question-review-card {
  padding: 18px 20px;
}

.question-review-card__title-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.question-review-card__index {
  font-size: 12px;
  color: var(--gray-500);
}

.question-review-card__title,
.report-question-card__title {
  font-size: 17px;
  font-weight: 700;
  color: var(--gray-1000);
  line-height: 1.5;
}

.question-review-card__actions,
.question-review-card__tags,
.report-section__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.question-review-card__meta {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
  color: var(--gray-500);
}

.question-review-card__section,
.question-review-card__tags,
.question-review-card__grid {
  margin-top: 14px;
}

.question-review-card__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.question-review-card__col {
  padding: 14px;
  border-radius: 16px;
  background: var(--gray-25);
  border: 1px solid var(--gray-150);
}

.question-review-card__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.question-review-card__list-item {
  padding: 10px 12px;
  border-radius: 12px;

  &.success {
    background: rgba(82, 196, 26, 0.08);
  }

  &.warning {
    background: rgba(250, 173, 20, 0.12);
  }
}

.subsection-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-start;
}

.coding-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--gray-150);
  background: var(--gray-25);
}

.summary-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.summary-value {
  color: var(--gray-800);
  text-align: right;
  word-break: break-word;
}

.summary-preview {
  margin-top: 10px;
}

.report-section {
  background: linear-gradient(180deg, var(--gray-0) 0%, #fbfcff 100%);
}

.report-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.report-stat-card {
  padding: 18px;
  background: linear-gradient(180deg, var(--gray-0) 0%, var(--gray-25) 100%);
}

.report-stat-card--score {
  background: linear-gradient(180deg, rgba(79, 159, 236, 0.1) 0%, var(--gray-0) 100%);
}

.report-stat-card__value {
  margin-top: 10px;
  font-size: 34px;
  font-weight: 700;
  line-height: 1;
  color: var(--gray-1000);
}

.report-stat-card__value--small {
  font-size: 22px;
}

.report-stat-card__desc {
  margin-top: 10px;
}

.report-body {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.95fr);
  gap: 18px;
}

.report-main,
.report-side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.report-panel {
  padding: 18px;
}

.report-panel--summary {
  background: linear-gradient(180deg, rgba(79, 159, 236, 0.04) 0%, var(--gray-0) 100%);
}

.report-side-card {
  background: var(--gray-10);
}

.report-question-list,
.report-dimension-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-question-card {
  padding: 16px;
  background: var(--gray-25);
}

.report-question-card__summary,
.report-question-card__insight {
  margin-top: 10px;
}

.report-question-card__insight {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(250, 173, 20, 0.08);
}

.report-dimension-item {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--gray-150);
  background: var(--gray-0);
}

.report-dimension-item__top {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.report-list {
  margin: 0;
  padding-left: 18px;
  color: var(--gray-700);

  li + li {
    margin-top: 8px;
  }
}

@media (max-width: 1280px) {
  .summary-grid,
  .report-body {
    grid-template-columns: 1fr;
  }

  .evidence-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .interview-result-view {
    padding: 18px;
  }

  .result-toolbar,
  .hero-card,
  .section-header,
  .question-review-card__top,
  .summary-row,
  .report-question-card__top {
    flex-direction: column;
  }

  .result-toolbar,
  .hero-card {
    display: flex;
  }

  .section-nav {
    position: static;
  }

  .summary-grid,
  .evidence-overview,
  .question-review-card__grid {
    grid-template-columns: 1fr;
  }

  .summary-value {
    text-align: left;
  }
}

@media (max-width: 640px) {
  .interview-result-view {
    padding: 14px;
  }

  .hero-card,
  .section-card,
  .result-toolbar {
    padding: 18px;
    border-radius: 20px;
  }

  .hero-title {
    font-size: 28px;
  }

  .toolbar-actions,
  .hero-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .question-review-card,
  .summary-card,
  .report-panel,
  .report-stat-card,
  .report-question-card {
    padding: 16px;
  }
}
</style>
