<template>
  <div class="rv-root">
    <!-- 状态分支 -->
    <div v-if="loading" class="rv-state"><a-spin /><span>正在调取你的面试数据…</span></div>
    <div v-else-if="failedMessage" class="rv-state">
      <div class="rv-state__mark">!</div>
      <h2>报告生成遇到了点问题</h2>
      <p>{{ failedMessage }}</p>
      <button class="rv-btn" :disabled="finalizing" @click="finalizeResult(true)">重新生成</button>
    </div>
    <div v-else-if="isGenerating" class="rv-state">
      <a-spin size="large" />
      <h2>正在为你整理面试复盘</h2>
      <p>我们正在逐题分析你的回答、对比岗位要求、汇总各维度表现。这通常需要几十秒。</p>
    </div>
    <div v-else-if="!hasCompletedResult" class="rv-state">
      <div class="rv-state__mark rv-state__mark--muted">?</div>
      <h2>这轮面试还没有生成报告</h2>
      <p>完成一轮模拟面试后，系统会自动分析你的表现并生成详细复盘。准备好了就点下方按钮。</p>
      <button class="rv-btn" :disabled="finalizing" @click="finalizeResult()">生成面试结果</button>
    </div>

    <template v-else>
      <!-- 数据不完整提示 -->
      <div v-if="isIncompleteScorecard" class="rv-incomplete-banner" role="alert">
        <div class="rv-incomplete-banner__body">
          <strong>本次评估数据不完整</strong>
          <p>系统识别到模型本轮未生成有效的综合得分，下方仍展示了已经成功提炼的内容；建议重新生成报告以获得完整评分。</p>
        </div>
        <button class="rv-btn" :disabled="finalizing" @click="finalizeResult(true)">
          {{ finalizing ? '重新生成中…' : '重新生成评分' }}
        </button>
      </div>

      <!-- 顶栏 -->
      <header class="rv-top">
        <div class="rv-top__title">
          <h1>{{ displayPosition }} · {{ displayRound }}</h1>
          <p class="rv-top__sub">{{ headerMeta }}</p>
        </div>
        <div class="rv-top__actions">
          <button class="rv-btn" @click="exportToPDF" :disabled="loading">
            <PrinterOutlined /> 导出 PDF
          </button>
          <button class="rv-btn rv-btn--primary" @click="startWeaknessPractice" :disabled="!weaknessRecs.length">
            按弱项开始练习
          </button>
        </div>
      </header>

      <!-- 评分来源 -->
      <div class="rv-source-chip">{{ scoreSourceBadge }}</div>

      <!-- 结论区 -->
      <section class="rv-conclusion">
        <div class="rv-conclusion__score">
          <span class="rv-lab">综合评分</span>
          <span class="rv-score-num">{{ isIncompleteScorecard ? '—' : animatedScore }}</span>
          <span class="rv-score-line" :class="{ 'rv-score-line--warn': !isIncompleteScorecard && (overallScore ?? 0) < 70 }">{{ scoreLine }}</span>
        </div>
        <div class="rv-conclusion__text">
          <span class="rv-lab">面试官结论</span>
          <p class="rv-conclusion__p">{{ conclusionText }}</p>
          <div v-if="abilityBadges.length" class="rv-badges">
            <span v-for="badge in abilityBadges" :key="`${badge.tone}-${badge.keyword}`" class="rv-badge" :class="`rv-badge--${badge.tone}`">
              {{ badge.keyword }} {{ badge.label }}
            </span>
          </div>
        </div>
      </section>

      <!-- 四维评分 + 下一步练习 -->
      <section class="rv-mid">
        <div class="rv-mid__col">
          <span class="rv-lab">四维评分</span>
          <div v-if="dimensionScoreCards.length" class="rv-dim-list">
            <div v-for="item in dimensionScoreCards" :key="item.key" class="rv-dim">
              <div class="rv-dim__hd">
                <span>{{ item.label }}</span>
                <span :class="{ 'rv-dim__num--weak': item.score < WEAK_THRESHOLD }">{{ item.score }}</span>
              </div>
              <div class="rv-dim__track">
                <div
                  class="rv-dim__fill"
                  :class="{ 'rv-dim__fill--weak': item.score < WEAK_THRESHOLD }"
                  :style="{ width: `${item.score}%` }"
                />
              </div>
            </div>
          </div>
          <div v-else class="rv-data-empty">分析数据不足，无法展示各维度评分。</div>
        </div>
        <div class="rv-mid__col">
          <span class="rv-lab">下一步练习</span>
          <div v-if="weaknessRecs.length" class="rv-next-list">
            <div v-for="rec in weaknessRecs" :key="`${rec.type}-${rec.query}`" class="rv-next-row">
              <div class="rv-next-row__txt">
                <div class="rv-next-row__name">{{ rec.label }}</div>
                <div class="rv-next-row__meta">{{ nextMeta(rec) }}</div>
              </div>
              <div class="rv-next-row__acts">
                <button class="rv-btn rv-btn--sm rv-btn--secondary" @click="openLearnFor(rec)">
                  {{ rec.locator?.file_id ? '查看资料' : '去学习' }}
                </button>
                <button class="rv-btn rv-btn--sm" @click="openPracticeFor(rec)">去练习</button>
              </div>
            </div>
          </div>
          <p v-else class="rv-empty">本轮没有识别出明显薄弱点，可以换个方向继续挑战。</p>
        </div>
      </section>

      <!-- 逐题回看 -->
      <section class="rv-questions">
        <span class="rv-lab">逐题回看</span>
        <div class="rv-table-wrap">
          <table class="rv-table">
            <thead>
              <tr>
                <th>#</th>
                <th>题目</th>
                <th>考察点覆盖</th>
                <th>评价</th>
                <th class="rv-th--right">得分</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in displayedQuestionReviews" :key="item.question_index">
                <tr class="rv-row" :class="{ 'rv-row--open': questionOpen(item) }">
                  <td class="rv-cell--ref">{{ item.question_index }}</td>
                  <td>
                    <button type="button" class="rv-title-btn" @click="toggleQuestion(item)">{{ item.question }}</button>
                  </td>
                  <td :class="{ 'rv-cell--weak': isLowScore(item) }">{{ coverageLabel(item) }}</td>
                  <td class="rv-muted">{{ item.gaps?.[0] || item.level || '—' }}</td>
                  <td class="rv-th--right" :class="{ 'rv-cell--weak': isLowScore(item) }">{{ item.score ?? '--' }}</td>
                </tr>
                <tr v-if="questionOpen(item)" class="rv-detail-row">
                  <td></td>
                  <td colspan="4">
                    <div v-if="item.kb_name || item.file_name || item.asked_at" class="rv-q-meta">
                      <span v-if="item.kb_name">题库：{{ item.kb_name }}</span>
                      <span v-if="item.file_name">来源：{{ item.file_name }}</span>
                      <span v-if="item.asked_at">提问时间：{{ item.asked_at }}</span>
                      <button v-if="canOpenQuestionSource(item)" type="button" class="rv-link-btn" @click="openQuestionSource(item)">查看知识点原文</button>
                    </div>
                    <p class="rv-q-answer">
                      <span class="rv-q-answer-label">你的回答摘要</span>
                      {{ item.answer_excerpt || '未记录到有效回答内容（可能是回答过短或音频质量原因）。' }}
                    </p>
                    <div class="rv-q-cols">
                      <div>
                        <span class="rv-q-col-label">做得好的地方</span>
                        <ul v-if="item.strengths?.length" class="rv-q-list">
                          <li v-for="strength in item.strengths" :key="strength">{{ strength }}</li>
                        </ul>
                        <p v-else class="rv-na">分析数据不足。</p>
                      </div>
                      <div>
                        <span class="rv-q-col-label">可以更好的地方</span>
                        <ul v-if="item.gaps?.length" class="rv-q-list">
                          <li v-for="gap in item.gaps" :key="gap">{{ gap }}</li>
                        </ul>
                        <p v-else class="rv-na">分析数据不足。</p>
                      </div>
                    </div>
                    <div v-if="item.matched_keywords?.length || item.suggested_keywords?.length" class="rv-q-kw">
                      <span v-for="kw in item.matched_keywords" :key="`hit-${kw}`" class="rv-kw rv-kw--hit">已覆盖：{{ kw }}</span>
                      <span v-for="kw in item.suggested_keywords" :key="`miss-${kw}`" class="rv-kw rv-kw--miss">建议补充：{{ kw }}</span>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div v-if="technicalQuestionReviews.length > initialQuestionReviewCount" class="rv-more">
          <button type="button" class="rv-link-btn" @click="showAllQuestionReviews = !showAllQuestionReviews">
            {{ showAllQuestionReviews ? '收起' : `查看全部 ${technicalQuestionReviews.length} 道题` }}
          </button>
        </div>
      </section>

      <!-- 详细分析折叠区 -->
      <details id="section-evidence" class="rv-collapse" :open="detailsState.evidence" @toggle="onDetailsToggle('evidence', $event)">
        <summary class="rv-collapse__hd">
          <span class="rv-lab">详细分析</span>
          <span class="rv-collapse__chev">{{ detailsState.evidence ? '收起' : '展开' }}</span>
        </summary>
        <div class="rv-collapse__body">
          <div v-if="normalizedReportHighlights.length" class="rv-subblock">
            <h3>哪些该保持，哪些该补上</h3>
            <div class="rv-insights">
              <article v-for="item in normalizedReportHighlights" :key="`${item.priority}-${item.title}`" class="rv-insight">
                <div class="rv-insight__hd">
                  <h4>{{ item.title }}</h4>
                  <span class="rv-tag" :class="`rv-tag--${item.tone}`">{{ highlightToneLabelMap[item.tone] }}</span>
                </div>
                <p>{{ item.summary }}</p>
                <div v-if="item.evidence_refs.length" class="rv-insight__refs">
                  <span>判断依据</span>
                  <button v-for="ref in item.evidence_refs" :key="ref.key" type="button" class="rv-link-btn" @click="scrollToSection('section-report')">{{ ref.label }}</button>
                </div>
              </article>
            </div>
          </div>
          <div v-if="scorecard" class="rv-subblock">
            <h3>评分卡详情</h3>
            <InterviewScorePanel :scorecard="scorecard" />
          </div>
          <div v-if="sepThetaTrajectory.length > 1" class="rv-subblock">
            <h3>答题过程中你的能力估计变化</h3>
            <AdaptiveTrajectory :key="theme" :trajectory="sepThetaTrajectory" :questions="sepQuestions" />
          </div>
          <div v-if="sepEvidenceChain.length" class="rv-subblock">
            <h3>每题评分的推理过程</h3>
            <EvidenceChain :items="sepEvidenceChain" />
          </div>
          <div v-if="expressionMetrics.length" class="rv-subblock">
            <h3>表达与沟通</h3>
            <div class="rv-expr">
              <div v-for="item in expressionMetrics" :key="item.key" class="rv-expr__card">
                <div class="rv-expr__hd">
                  <span>{{ item.label }}</span>
                  <span class="rv-tag">{{ item.metric.level || '已分析' }}</span>
                </div>
                <div class="rv-expr__score">{{ item.metric.score ?? '--' }}</div>
                <div v-if="item.metric.value" class="rv-expr__val">{{ item.metric.value }}</div>
                <div v-if="item.metric.detail" class="rv-expr__detail">{{ item.metric.detail }}</div>
              </div>
            </div>
          </div>
          <div class="rv-subblock">
            <h3>编程能力</h3>
            <div v-if="codingSession" class="rv-coding">
              <div class="rv-coding__row"><span>题目</span><span>{{ codingSession.problem_title || '未记录' }}</span></div>
              <div class="rv-coding__row"><span>难度</span><span>{{ codingSession.difficulty_level || '未记录' }}</span></div>
              <div class="rv-coding__row"><span>判题结果</span><span class="rv-tag" :class="`rv-tag--${judgeTone}`">{{ judgeStatusLabel }}</span></div>
              <div v-if="codingSession.submitted_at" class="rv-coding__row"><span>提交时间</span><span>{{ codingSession.submitted_at }}</span></div>
              <div v-if="codingSession.judge_result?.score !== undefined" class="rv-coding__row"><span>判题得分</span><span>{{ codingSession.judge_result.score }}</span></div>
            </div>
            <p v-else class="rv-empty">本轮面试没有编程考核环节。</p>
          </div>
        </div>
      </details>

      <!-- 完整报告折叠区 -->
      <details id="section-report" class="rv-collapse" :open="detailsState.report" @toggle="onDetailsToggle('report', $event)">
        <summary class="rv-collapse__hd">
          <span class="rv-lab">完整报告</span>
          <span class="rv-collapse__chev">{{ detailsState.report ? '收起' : '展开' }}</span>
        </summary>
        <div class="rv-collapse__body">
          <div class="rv-report-stats">
            <div class="rv-report-stat"><span class="rv-report-stat__label">综合评分</span><span class="rv-report-stat__num">{{ overallScore ?? '--' }}</span><span class="rv-report-stat__note">{{ scoreVerdictLabel }}</span></div>
            <div class="rv-report-stat"><span class="rv-report-stat__label">面试轮次</span><span class="rv-report-stat__num rv-report-stat__num--sm">{{ displayRound }}</span><span class="rv-report-stat__note">{{ generatedAtText || '已生成完整报告' }}</span></div>
            <div class="rv-report-stat"><span class="rv-report-stat__label">技术题数量</span><span class="rv-report-stat__num rv-report-stat__num--sm">{{ technicalQuestionReviews.length }} 道</span><span class="rv-report-stat__note">{{ questionScoreSummary.lowest ? `最低 ${questionScoreSummary.lowest.score ?? '--'} 分 · 最高 ${questionScoreSummary.highest?.score ?? '--'} 分` : '暂无评分数据' }}</span></div>
            <div v-if="codingSession" class="rv-report-stat"><span class="rv-report-stat__label">编程考核</span><span class="rv-report-stat__num rv-report-stat__num--sm">{{ judgeStatusLabel }}</span><span class="rv-report-stat__note">{{ codingSession.problem_title || '已完成' }}</span></div>
          </div>
          <div v-if="summaryMarkdown" class="rv-subblock">
            <h3>面试官综合评语</h3>
            <MdPreview editor-id="interview-result-summary" :theme="theme" preview-theme="github" :show-code-row-number="false" :model-value="summaryMarkdown" />
          </div>
          <div v-if="technicalQuestionReviews.length" class="rv-subblock">
            <h3>最具代表性的两道题</h3>
            <div class="rv-report-qs">
              <article v-for="item in reportQuestionSamples" :key="`report-${item.question_index}-${item.question}`" class="rv-report-q">
                <div class="rv-report-q__hd">
                  <div><span class="rv-report-q__idx">第 {{ item.question_index }} 题</span><h4>{{ item.question }}</h4></div>
                  <span class="rv-tag" :class="{ 'rv-tag--weak': isLowScore(item) }">{{ item.score ?? '--' }}/100</span>
                </div>
                <p v-if="item.answer_excerpt">{{ item.answer_excerpt }}</p>
                <p v-else class="rv-na">未记录到有效回答。</p>
                <p v-if="item.gaps?.length" class="rv-report-q__focus">最值得改进的一点：{{ item.gaps[0] }}</p>
              </article>
            </div>
          </div>
          <div v-if="scorecard?.strengths?.length" class="rv-subblock"><h3>你的优势</h3><ul class="rv-list"><li v-for="strength in scorecard.strengths" :key="`s-${strength}`">{{ strength }}</li></ul></div>
          <div v-if="scorecard?.risks?.length" class="rv-subblock"><h3>需要警惕的方面</h3><ul class="rv-list"><li v-for="risk in scorecard.risks" :key="`r-${risk}`">{{ risk }}</li></ul></div>
          <div v-if="scorecard?.suggestions?.length" class="rv-subblock"><h3>下一步建议</h3><ul class="rv-list"><li v-for="suggestion in scorecard.suggestions" :key="`sg-${suggestion}`">{{ suggestion }}</li></ul></div>
        </div>
      </details>

      <InterviewKnowledgeLearnModal v-model:open="learningModalVisible" :resource="activeLearningResource" />
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { MdPreview, config as mdEditorConfig } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css'

// Suppress Mermaid rendering errors from polluting the console
mdEditorConfig.mermaidConfig = { ...mdEditorConfig.mermaidConfig, suppressErrors: true }
import InterviewScorePanel from '@/components/InterviewScorePanel.vue'
import InterviewKnowledgeLearnModal from '@/components/interview/InterviewKnowledgeLearnModal.vue'
import { interviewCodeApi } from '@/apis/interview_code'
import { useThemeStore } from '@/stores/theme'
import { formatDateTime } from '@/utils/time'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'
import EvidenceChain from '@/components/sep/EvidenceChain.vue'
import AdaptiveTrajectory from '@/components/sep/AdaptiveTrajectory.vue'
import { PrinterOutlined } from '@ant-design/icons-vue'
import { extractReportWeaknesses, REPORT_SCORE_THRESHOLD } from '@/utils/weaknessPractice'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const initialQuestionReviewCount = 5
const highlightToneLabelMap = { risk: '需要优先改进', strength: '建议继续保持', action: '值得关注' }
const dimensionLabelMap = {
  technical_competence: '技术能力', technical_knowledge: '技术能力', practical_experience: '技术能力',
  problem_solving: '问题解决', problem_solving_innovation: '问题解决',
  communication: '沟通表达', communication_clarity: '沟通表达',
  soft_skills: '综合素质', soft_skills_team_fit: '综合素质',
}
const scoreVerdictLabels = [
  { max: 40, text: '基础还需打磨' },
  { max: 55, text: '有潜力，需要系统补强' },
  { max: 70, text: '基本功过关，重点突破短板' },
  { max: 85, text: '表现不错，冲刺更高水平' },
  { max: 100, text: '面试表现优秀' },
]
const judgeStatusLabelMap = {
  PENDING: '等待判题', JUDGING: '判题中', ACCEPTED: '通过', WRONG_ANSWER: '答案错误',
  COMPILE_ERROR: '编译错误', RUNTIME_ERROR: '运行错误', SYSTEM_ERROR: '系统错误',
  MEMORY_LIMIT_EXCEEDED: '内存超限', CPU_TIME_LIMIT_EXCEEDED: 'CPU 超时',
  REAL_TIME_LIMIT_EXCEEDED: '运行超时', PARTIALLY_ACCEPTED: '部分通过',
}

// 四维评分的弱项强调阈值（主色）
const WEAK_THRESHOLD = 70

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const loading = ref(false)
const finalizing = ref(false)
const payload = ref(null)
const learningModalVisible = ref(false)
const activeLearningResource = ref(null)
const showAllQuestionReviews = ref(false)
const animatedScore = ref(0)
const openQuestions = ref(new Set())
const detailsState = reactive({ evidence: false, report: false })
let scoreAnimFrame = null

const threadId = computed(() => String(route.query.threadId || '').trim())
const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || '初试')
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))

const normalizeDimensionKey = (value) => {
  const key = String(value || '').trim().toLowerCase()
  const map = {
    technical_competence: 'technical_competence', technical_knowledge: 'technical_competence',
    practical_experience: 'technical_competence', '技术能力': 'technical_competence',
    problem_solving: 'problem_solving', problem_solving_innovation: 'problem_solving', '问题解决': 'problem_solving',
    communication: 'communication', communication_clarity: 'communication', '沟通表达': 'communication',
    soft_skills: 'soft_skills', soft_skills_team_fit: 'soft_skills', '综合素质': 'soft_skills',
  }
  return map[key] || key
}
const getDimensionLabel = (key) => dimensionLabelMap[normalizeDimensionKey(key)] || key || '待分析'

const getScoreVerdict = (score) => {
  for (const tier of scoreVerdictLabels) {
    if (score <= tier.max) return tier.text
  }
  return scoreVerdictLabels[scoreVerdictLabels.length - 1].text
}

const normalizeScore = (value) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? Math.max(0, Math.min(100, Math.round(numeric))) : null
}

const parseThreadTitle = (title) => {
  const normalizedTitle = String(title || '').trim()
  if (!normalizedTitle) return { position: selectedPosition.value, round: selectedRound.value }
  for (const pattern of [/\s*[·•｜|]\s*/, /\s+[?？]\s+/, /\s+[-—–]+\s*/]) {
    const matched = normalizedTitle.match(pattern)
    if (!matched || matched.index === undefined) continue
    const position = normalizedTitle.slice(0, matched.index).trim()
    const round = normalizedTitle.slice(matched.index + matched[0].length).trim()
    if (!position || !round) continue
    return { position, round }
  }
  return { position: normalizedTitle, round: selectedRound.value }
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
    chunk_index: locator.chunk_index !== undefined && locator.chunk_index !== null ? Number(locator.chunk_index) : source?.chunk_index !== undefined && source?.chunk_index !== null ? Number(source.chunk_index) : undefined,
    keyword: String(locator.keyword || '').trim() || undefined,
    query_text: String(locator.query_text || '').trim() || undefined,
  }
}

const normalizeCodingSession = (value) => {
  if (!value || typeof value !== 'object') return null
  return { ...value, submitted_at: value.submitted_at ? formatDateTime(value.submitted_at) : '' }
}

const result = computed(() => payload.value?.result || null)
const codingSession = computed(() => normalizeCodingSession(payload.value?.coding_session || null))
const scorecard = computed(() => result.value?.scorecard || null)
const expressionAnalysis = computed(() => result.value?.expression_analysis || null)
const reportHighlights = computed(() => (Array.isArray(result.value?.report_highlights) ? result.value.report_highlights : []))
const summaryMarkdown = computed(() => String(result.value?.summary_markdown || '').replace(/\n*\s*完整结果已生成，可在面试结果页查看。?\s*$/u, '').trim())
const hasCompletedResult = computed(() => result.value?.status === 'completed' && Boolean(scorecard.value || summaryMarkdown.value || reportHighlights.value.length || technicalQuestionReviews.value.length))
const isGenerating = computed(() => result.value?.status === 'generating')
const failedMessage = computed(() => (result.value?.status === 'failed' ? result.value?.error_message || '请稍后重试' : ''))
const threadTitle = computed(() => payload.value?.title || `${selectedPosition.value} · ${selectedRound.value}`)
const threadContext = computed(() => parseThreadTitle(threadTitle.value))
const displayPosition = computed(() => scorecard.value?.role || codingSession.value?.target_position || threadContext.value.position || selectedPosition.value)
const displayRound = computed(() => scorecard.value?.round || threadContext.value.round || selectedRound.value)
const generatedAtText = computed(() => (result.value?.generated_at ? formatDateTime(result.value.generated_at) : ''))
const overallScore = computed(() => normalizeScore(scorecard.value?.overall ?? scorecard.value?.overall_score ?? scorecard.value?.total_score))

const isIncompleteScorecard = computed(() => hasCompletedResult.value && overallScore.value === null)

const scoreVerdictLabel = computed(() => {
  if (overallScore.value !== null) return getScoreVerdict(overallScore.value)
  if (isIncompleteScorecard.value) return '评分数据不完整'
  return '等待评估'
})

// 评分来源（sep / sep_partial / LLM）
const scoreSourceBadge = computed(() => {
  const src = String(scorecard.value?.score_source || '').trim()
  const coverage = Number(scorecard.value?.sep_coverage)
  if (src === 'sep') return '基于规则引擎评分 · 100% 题库覆盖'
  if (src === 'sep_partial' && Number.isFinite(coverage)) {
    return `基于规则引擎评分 · ${Math.round(coverage * 100)}% 题库覆盖（其余维度由 LLM 评估）`
  }
  return '基于 LLM 综合评估'
})

const dimensionScoreCards = computed(() => {
  const dimensions = Array.isArray(scorecard.value?.dimensions) ? scorecard.value.dimensions : []
  return dimensions
    .map((item) => {
      const key = normalizeDimensionKey(item?.key || item?.name)
      const score = normalizeScore(item?.score)
      if (!key || score === null) return null
      const evidenceCount = Number.isFinite(Number(item?.evidence_count)) ? Number(item.evidence_count)
        : Array.isArray(item?.evidence) ? item.evidence.length : 0
      return { key, label: getDimensionLabel(key), score, evidence_count: evidenceCount }
    })
    .filter(Boolean)
    .sort((a, b) => a.score - b.score)
})

const sepEvidenceChain = computed(() => (Array.isArray(scorecard.value?.sep_evidence_chain) ? scorecard.value.sep_evidence_chain : []))
const sepThetaTrajectory = computed(() => (Array.isArray(scorecard.value?.sep_theta_trajectory) ? scorecard.value.sep_theta_trajectory : []))
const sepQuestions = computed(() => {
  const seen = new Set()
  return sepEvidenceChain.value
    .filter((item) => {
      if (seen.has(item.question)) return false
      seen.add(item.question)
      return true
    })
    .slice(0, sepThetaTrajectory.value.length - 1)
    .map((item) => ({ concept: item.concept, difficulty: item.difficulty ?? null }))
})

const expressionMetrics = computed(() => {
  const analysis = expressionAnalysis.value
  if (!analysis) return []
  return [
    { key: 'speech_rate', label: '语速', metric: analysis.speech_rate },
    { key: 'pause_control', label: '停顿控制', metric: analysis.pause_control },
    { key: 'clarity', label: '清晰度', metric: analysis.clarity },
    { key: 'confidence', label: '自信度', metric: analysis.confidence },
  ].filter((item) => item.metric)
})

const technicalQuestionReviews = computed(() => {
  const items = Array.isArray(result.value?.technical_question_reviews) ? result.value.technical_question_reviews : []
  return items
    .map((item, index) => ({
      ...item,
      question_index: Number(item?.question_index || index + 1),
      score: normalizeScore(item?.score),
      asked_at: item?.asked_at ? formatDateTime(item.asked_at) : '',
      locator: resolveLearningLocator(item),
    }))
    .sort((a, b) => (a.question_index || 0) - (b.question_index || 0))
})

const displayedQuestionReviews = computed(() =>
  showAllQuestionReviews.value ? technicalQuestionReviews.value : technicalQuestionReviews.value.slice(0, initialQuestionReviewCount),
)
const questionScoreSummary = computed(() => {
  const scored = technicalQuestionReviews.value.filter((item) => item.score !== null)
  if (!scored.length) return { lowest: null, highest: null }
  const sortedByScore = [...scored].sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
  return { lowest: sortedByScore[0], highest: sortedByScore[sortedByScore.length - 1] }
})
const reportQuestionSamples = computed(() => {
  const samples = []
  if (questionScoreSummary.value.lowest) samples.push(questionScoreSummary.value.lowest)
  if (questionScoreSummary.value.highest && questionScoreSummary.value.highest.question_index !== questionScoreSummary.value.lowest?.question_index) samples.push(questionScoreSummary.value.highest)
  if (samples.length >= 2) return samples
  return technicalQuestionReviews.value.slice(0, 2)
})

// 弱项候选（与练习页共用同一套提取算法）
const weaknessRecs = computed(() =>
  extractReportWeaknesses({
    technicalReviews: technicalQuestionReviews.value,
    dimensions: dimensionScoreCards.value,
  }),
)

// 逐题覆盖度：matched / (matched + 未覆盖建议关键词)，近似值非 SEP 精确覆盖率
const isLowScore = (item) => item.score !== null && Number(item.score) < REPORT_SCORE_THRESHOLD
const questionOpen = (item) => openQuestions.value.has(item.question_index)
const toggleQuestion = (item) => {
  const next = new Set(openQuestions.value)
  if (next.has(item.question_index)) next.delete(item.question_index)
  else next.add(item.question_index)
  openQuestions.value = next
}
const coverageLabel = (item) => {
  const matched = new Set((item.matched_keywords || []).map((keyword) => String(keyword).trim().toLowerCase()).filter(Boolean))
  const suggested = (item.suggested_keywords || []).map((keyword) => String(keyword).trim().toLowerCase()).filter(Boolean)
  const missing = suggested.filter((keyword) => !matched.has(keyword))
  const knownTotal = matched.size + missing.length
  if (!knownTotal) return '—'
  return `${Math.round((matched.size / knownTotal) * 4)} / 4`
}

// 面试官结论：scorecard.summary 优先，其次风险 highlight，最后空态
const conclusionText = computed(() => {
  const summary = String(scorecard.value?.summary || '').trim()
  if (summary) return summary
  const risk = primaryRiskHighlight.value
  if (risk?.summary) return risk.summary
  return '本轮暂无足够评分证据生成面试官结论。'
})

const scoreLine = computed(() => {
  if (isIncompleteScorecard.value) return '评分数据不完整'
  return (overallScore.value ?? 0) < 70 ? '未达初试通过线（70）' : '达到初试通过线（70）'
})

// 三个能力 badge：从 highlights 各 tone 取一个，不足用维度分数补齐
const abilityBadges = computed(() => {
  const badges = []
  const toneLabel = { strength: '强', risk: '弱', action: '需关注' }
  const pushBadge = (tone, keyword) => {
    const normalized = String(keyword || '').trim().replace(/^第 \d+ 题[：:]?\s*/, '').slice(0, 8)
    if (!normalized || badges.some((badge) => badge.keyword === normalized)) return
    badges.push({ tone, keyword: normalized, label: toneLabel[tone] })
  }
  for (const tone of ['strength', 'risk', 'action']) {
    const item = normalizedReportHighlights.value.find((highlight) => highlight.tone === tone)
    if (item) pushBadge(tone, item.title)
  }
  for (const dim of dimensionScoreCards.value) {
    if (badges.length >= 3) break
    const tone = dim.score >= 80 ? 'strength' : dim.score < 70 ? 'risk' : 'action'
    pushBadge(tone, dim.label)
  }
  return badges.slice(0, 3)
})

// 顶栏元数据：技术题时间区间 · 题数 · 报告时间（尽力贴近设计稿，缺失省略）
const questionTimeRange = computed(() => {
  const raw = Array.isArray(result.value?.technical_question_reviews) ? result.value.technical_question_reviews : []
  const times = raw
    .map((review) => {
      const time = new Date(review.asked_at).getTime()
      return Number.isNaN(time) ? null : time
    })
    .filter(Boolean)
  if (!times.length) return ''
  const fmt = (date) => `${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  const min = new Date(Math.min(...times))
  const max = new Date(Math.max(...times))
  return min.getTime() === max.getTime() ? fmt(min) : `${fmt(min)} – ${fmt(max)}`
})
const headerMeta = computed(() => {
  const parts = []
  if (questionTimeRange.value) parts.push(questionTimeRange.value)
  if (technicalQuestionReviews.value.length) parts.push(`${technicalQuestionReviews.value.length} 道技术题`)
  if (generatedAtText.value) parts.push(generatedAtText.value)
  return parts.join(' · ')
})

const nextMeta = (rec) => {
  if (rec.file_name) return `${rec.file_name} · 相关知识点与练习`
  if (rec.kb_name) return `${rec.kb_name} · 相关知识点与练习`
  if (rec.type === 'dimension') return '本轮薄弱维度 · 专项提升'
  return '知识库资料 · 相关练习'
}

const openLearnFor = (rec) => {
  if (rec.locator?.db_id && rec.locator?.file_id) {
    router.push({
      name: 'LearnDocumentPage',
      params: { db_id: rec.locator.db_id, file_id: rec.locator.file_id },
      query: rec.locator.chunk_id ? { chunk: rec.locator.chunk_id } : undefined,
    })
    return
  }
  router.push({ name: 'LearnHomePage', query: { q: rec.query } })
}

const openPracticeFor = (rec) => {
  router.push({ name: 'PracticeHomePage', query: { topic: rec.query, source: 'report' } })
}

const startWeaknessPractice = () => {
  const recs = weaknessRecs.value
  if (!recs.length) {
    message.warning('暂未识别出可练习的弱项')
    return
  }
  const query = { topic: recs.map((rec) => rec.query), source: 'report' }
  if (result.value?.generated_at) query.reportAt = result.value.generated_at
  router.push({ name: 'PracticeHomePage', query })
}

const judgeStatus = computed(() => String(codingSession.value?.judge_status || codingSession.value?.judge_result?.status || '').trim() || 'UNKNOWN')
const judgeStatusLabel = computed(() => judgeStatusLabelMap[judgeStatus.value] || judgeStatus.value)
const judgeTone = computed(() => {
  if (judgeStatus.value === 'ACCEPTED') return 'passed'
  if (['WRONG_ANSWER', 'COMPILE_ERROR', 'RUNTIME_ERROR', 'SYSTEM_ERROR', 'MEMORY_LIMIT_EXCEEDED', 'CPU_TIME_LIMIT_EXCEEDED', 'REAL_TIME_LIMIT_EXCEEDED'].includes(judgeStatus.value)) return 'failed'
  return 'pending'
})

// 数据驱动 highlight（risk/strength/action）
const dataDrivenFallbackHighlights = computed(() => {
  const items = []
  const sortedReviews = [...technicalQuestionReviews.value].sort((a, b) => (a.score ?? 999) - (b.score ?? 999))
  const lowReview = sortedReviews[0]
  const highReview = [...technicalQuestionReviews.value].sort((a, b) => (b.score ?? -1) - (a.score ?? -1))[0]
  const weakDimension = dimensionScoreCards.value[0]
  const strongDimension = [...dimensionScoreCards.value].sort((a, b) => b.score - a.score)[0]

  if (lowReview && lowReview.gaps?.length) {
    items.push({ title: `第 ${lowReview.question_index} 题：${lowReview.question || '低分题'}`, summary: lowReview.gaps[0], tone: 'risk', dimension_key: 'technical_competence', priority: 1, evidence_refs: [{ kind: 'question_review', key: `question_review:${lowReview.question_index}`, label: `第 ${lowReview.question_index} 题 · ${lowReview.score ?? '--'} 分` }] })
  } else if (weakDimension && weakDimension.score < 60) {
    items.push({ title: `${weakDimension.label}得分 ${weakDimension.score}`, summary: `本轮${weakDimension.label}维度得分低于及格线，建议作为下一步重点。`, tone: 'risk', dimension_key: weakDimension.key, priority: 1, evidence_refs: [{ kind: 'dimension', key: weakDimension.key, label: `${weakDimension.label} · ${weakDimension.score} 分` }] })
  }

  if (highReview && (highReview.score ?? 0) >= 80 && highReview.strengths?.length) {
    items.push({ title: `第 ${highReview.question_index} 题：${highReview.question || '高分题'}`, summary: highReview.strengths[0], tone: 'strength', dimension_key: 'technical_competence', priority: 2, evidence_refs: [{ kind: 'question_review', key: `question_review:${highReview.question_index}`, label: `第 ${highReview.question_index} 题 · ${highReview.score ?? '--'} 分` }] })
  } else if (scorecard.value?.strengths?.length) {
    items.push({ title: '面试官认可的强项', summary: scorecard.value.strengths[0], tone: 'strength', dimension_key: strongDimension?.key || '', priority: 2, evidence_refs: strongDimension ? [{ kind: 'dimension', key: strongDimension.key, label: `${strongDimension.label} · ${strongDimension.score} 分` }] : [] })
  }

  if (weakDimension && weakDimension.score < 80) {
    items.push({ title: `下一步：补强${weakDimension.label}`, summary: `${weakDimension.label}当前 ${weakDimension.score} 分，是性价比最高的提升方向。`, tone: 'action', dimension_key: weakDimension.key, priority: 3, evidence_refs: [{ kind: 'dimension', key: weakDimension.key, label: `${weakDimension.label} · ${weakDimension.score} 分` }] })
  } else if (lowReview && lowReview.gaps?.length) {
    items.push({ title: `下一步：复盘第 ${lowReview.question_index} 题`, summary: `针对该题已识别的缺口（${lowReview.gaps[0]}）做定向补强。`, tone: 'action', dimension_key: 'technical_competence', priority: 3, evidence_refs: [{ kind: 'question_review', key: `question_review:${lowReview.question_index}`, label: `第 ${lowReview.question_index} 题 · ${lowReview.score ?? '--'} 分` }] })
  }

  return items.slice(0, 3)
})

const normalizedReportHighlights = computed(() => {
  const source = reportHighlights.value.length ? reportHighlights.value : dataDrivenFallbackHighlights.value
  return source
    .map((item, index) => ({
      title: String(item?.title || '').trim(),
      summary: String(item?.summary || '').trim(),
      tone: ['risk', 'strength', 'action'].includes(String(item?.tone || '').trim()) ? item.tone : 'action',
      dimension_key: normalizeDimensionKey(item?.dimension_key),
      priority: Number(item?.priority || index + 1),
      evidence_refs: Array.isArray(item?.evidence_refs)
        ? item.evidence_refs
            .map((refItem, refIndex) => ({
              kind: ['question_review', 'dimension', 'expression_metric', 'coding'].includes(String(refItem?.kind || '').trim()) ? refItem.kind : 'dimension',
              key: String(refItem?.key || `${index}-${refIndex}`).trim(),
              label: String(refItem?.label || '相关证据').trim(),
            }))
            .filter((refItem) => refItem.key)
        : [],
    }))
    .filter((item) => item.title && item.summary)
    .sort((a, b) => a.priority - b.priority)
    .slice(0, 3)
})

const primaryRiskHighlight = computed(() => normalizedReportHighlights.value.find((item) => item.tone === 'risk') || normalizedReportHighlights.value[0] || null)

const canOpenQuestionSource = (item) => Boolean(resolveLearningLocator(item))
const openQuestionSource = (item) => {
  activeLearningResource.value = { title: item.file_name || item.question || '题源知识点', summary: item.question || '', locator: resolveLearningLocator(item) }
  learningModalVisible.value = true
}

const onDetailsToggle = (key, event) => {
  detailsState[key] = event.target.open
}

const scrollToSection = (id) => {
  if (id === 'section-evidence') detailsState.evidence = true
  if (id === 'section-report') detailsState.report = true
  nextTick(() => {
    if (typeof document === 'undefined') return
    const target = document.getElementById(id)
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

// PDF 导出：先展开全部折叠区与逐题，打印后恢复
const exportToPDF = async () => {
  if (typeof document === 'undefined' || typeof window === 'undefined') return
  if (scoreAnimFrame) {
    cancelAnimationFrame(scoreAnimFrame)
    scoreAnimFrame = null
  }
  if (overallScore.value !== null) animatedScore.value = overallScore.value
  const wasCollapsed = !showAllQuestionReviews.value
  const wasEvidenceClosed = !detailsState.evidence
  const wasReportClosed = !detailsState.report
  if (wasCollapsed) showAllQuestionReviews.value = true
  detailsState.evidence = true
  detailsState.report = true

  const previousTitle = document.title
  const safePosition = (displayPosition.value || '面试').replace(/[\\/:*?"<>|]/g, '')
  const safeRound = (displayRound.value || '').replace(/[\\/:*?"<>|]/g, '')
  const date = generatedAtText.value || formatDateTime(new Date())
  document.title = `伯乐面试报告 - ${safePosition} ${safeRound} ${date}`.trim()
  await nextTick()
  try {
    window.print()
  } finally {
    document.title = previousTitle
    if (wasCollapsed) showAllQuestionReviews.value = false
    if (wasEvidenceClosed) detailsState.evidence = false
    if (wasReportClosed) detailsState.report = false
  }
}

const animateScore = (target) => {
  if (scoreAnimFrame) cancelAnimationFrame(scoreAnimFrame)
  const start = animatedScore.value
  const diff = target - start
  if (diff === 0) return
  const startTime = performance.now()
  const easeOutExpo = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t))
  const tick = (now) => {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / 1200, 1)
    animatedScore.value = Math.round(start + diff * easeOutExpo(progress))
    if (progress < 1) scoreAnimFrame = requestAnimationFrame(tick)
  }
  scoreAnimFrame = requestAnimationFrame(tick)
}
watch(overallScore, (value) => {
  if (value !== null) animateScore(value)
}, { immediate: true })

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
    payload.value = await interviewCodeApi.finalizeInterviewResult(threadId.value, { target_position: displayPosition.value, interview_round: displayRound.value, force })
    if ((payload.value?.result || {}).status === 'completed') {
      router.replace({ name: 'InterviewResultPage', query: { threadId: threadId.value, position: displayPosition.value, round: displayRound.value } })
      message.success(force ? '面试结果已重新生成' : '面试结果已生成')
    }
  } catch (error) {
    message.error(error.message || '生成面试结果失败')
    await loadResult()
  } finally {
    finalizing.value = false
  }
}

onMounted(async () => {
  if (!threadId.value) {
    router.replace({ name: 'InterviewWorkbench', query: { position: selectedPosition.value, round: selectedRound.value } })
    return
  }
  await loadResult()
  if (!hasCompletedResult.value && !isGenerating.value && route.query.autoGenerate === '1') await finalizeResult()
})
onBeforeUnmount(() => {
  if (scoreAnimFrame) cancelAnimationFrame(scoreAnimFrame)
})
</script>

<style lang="less" scoped>
.rv-root {
  height: 100%;
  overflow-y: auto;
  padding: 0 32px 48px;
  font-size: 15px;
  color: var(--gray-1000);
}

/* 状态区 */
.rv-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 72px 0;
  color: var(--gray-600);
}
.rv-state h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-1000);
}
.rv-state p {
  margin: 0;
  max-width: 480px;
  text-align: center;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
}
.rv-state__mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  font-size: 22px;
  font-weight: 800;
  color: var(--color-error-500);
  border: 1px solid var(--color-error-500);
}
.rv-state__mark--muted {
  color: var(--gray-500);
  border-color: var(--gray-300);
}

/* 通用按钮 */
.rv-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-700);
  background: transparent;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  cursor: pointer;
  white-space: nowrap;
}
.rv-btn:hover {
  background: var(--gray-100);
}
.rv-btn:focus-visible {
  outline: 2px solid var(--main-600);
  outline-offset: 1px;
}
.rv-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.rv-btn--primary {
  background: var(--main-600);
  border-color: var(--main-600);
  color: var(--main-0);
}
.rv-btn--primary:hover {
  background: var(--main-700);
}
.rv-btn--secondary {
  color: var(--gray-600);
}
.rv-btn--sm {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
}
.rv-link-btn {
  padding: 0;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--main-600);
  background: none;
  border: 0;
  cursor: pointer;
}
.rv-link-btn:hover {
  color: var(--main-800);
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* 顶栏 */
.rv-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 26px 0 18px;
  border-bottom: 1px solid var(--gray-100);
}
.rv-top h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--gray-1000);
}
.rv-top__sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--gray-600);
}
.rv-top__actions {
  display: flex;
  gap: 10px;
}

/* 评分来源 */
.rv-source-chip {
  display: inline-block;
  margin-top: 14px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--gray-600);
  background: var(--gray-100);
}

/* 小标签 */
.rv-lab {
  display: block;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--gray-600);
}

/* 结论区 */
.rv-conclusion {
  display: grid;
  grid-template-columns: 290px 1fr;
  border-bottom: 1px solid var(--gray-200);
}
.rv-conclusion__score {
  padding: 22px 30px 22px 0;
  border-right: 1px solid var(--gray-100);
}
.rv-score-num {
  display: block;
  margin: 8px 0 6px;
  font-size: 74px;
  font-weight: 800;
  line-height: 0.92;
  letter-spacing: -0.04em;
  color: var(--gray-1000);
}
.rv-score-line {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-600);
}
.rv-score-line--warn {
  color: var(--main-800);
}
.rv-conclusion__text {
  padding: 22px 0 22px 30px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rv-conclusion__p {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
  max-width: 840px;
  color: var(--gray-1000);
}
.rv-badges {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.rv-badge {
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid transparent;
}
.rv-badge--strength {
  color: var(--gray-700);
  background: var(--gray-100);
}
.rv-badge--risk {
  color: var(--gray-700);
  background: var(--gray-100);
}
.rv-badge--action {
  color: var(--main-800);
  background: var(--main-50);
  border-color: var(--main-200);
}

/* 四维 + 下一步 */
.rv-mid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid var(--gray-200);
}
.rv-mid__col {
  padding: 22px 30px 22px 0;
}
.rv-mid__col + .rv-mid__col {
  border-left: 1px solid var(--gray-100);
  padding-left: 30px;
}
.rv-dim-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 14px;
}
.rv-dim__hd {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--gray-1000);
}
.rv-dim__num--weak {
  color: var(--main-600);
}
.rv-dim__track {
  height: 8px;
  background: var(--gray-100);
}
.rv-dim__fill {
  height: 8px;
  background: var(--gray-1000);
}
.rv-dim__fill--weak {
  background: var(--main-600);
}
.rv-next-list {
  display: flex;
  flex-direction: column;
  margin-top: 14px;
}
.rv-next-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--gray-200);
}
.rv-next-row:first-child {
  border-top: 0;
}
.rv-next-row__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-1000);
}
.rv-next-row__meta {
  margin-top: 3px;
  font-size: 13px;
  color: var(--gray-600);
}
.rv-next-row__acts {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.rv-empty {
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--gray-500);
}
.rv-data-empty {
  margin-top: 14px;
  font-size: 13px;
  color: var(--gray-500);
}

/* 逐题回看 */
.rv-questions {
  padding: 22px 0;
  border-bottom: 1px solid var(--gray-200);
}
.rv-table-wrap {
  margin-top: 12px;
  overflow-x: auto;
}
.rv-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  font-size: 14px;
}
.rv-table th {
  padding: 8px 12px 8px 0;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--gray-600);
  border-bottom: 1px solid var(--gray-200);
  white-space: nowrap;
}
.rv-table td {
  padding: 12px 12px 12px 0;
  border-bottom: 1px solid var(--gray-100);
  vertical-align: top;
}
.rv-th--right {
  text-align: right;
}
.rv-cell--ref {
  font-size: 13px;
  color: var(--gray-500);
  white-space: nowrap;
}
.rv-cell--weak {
  color: var(--main-600);
  font-weight: 700;
}
.rv-title-btn {
  padding: 0;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
  background: none;
  border: 0;
  cursor: pointer;
  text-align: left;
}
.rv-title-btn:hover {
  color: var(--main-600);
}
.rv-muted {
  font-size: 13px;
  color: var(--gray-600);
}
.rv-detail-row td {
  background: var(--gray-25);
}
.rv-q-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--gray-600);
}
.rv-q-answer {
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-700);
}
.rv-q-answer-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-600);
}
.rv-q-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 10px;
}
.rv-q-col-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-600);
}
.rv-q-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-700);
}
.rv-na {
  margin: 0;
  font-size: 13px;
  color: var(--gray-500);
}
.rv-q-kw {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.rv-kw {
  padding: 2px 8px;
  font-size: 12px;
}
.rv-kw--hit {
  color: var(--color-success-500);
  background: var(--color-success-50);
}
.rv-kw--miss {
  color: var(--color-warning-500);
  background: var(--color-warning-50);
}
.rv-more {
  margin-top: 12px;
}

/* 折叠区 */
.rv-collapse {
  border-bottom: 1px solid var(--gray-200);
}
.rv-collapse__hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0;
  cursor: pointer;
  list-style: none;
}
.rv-collapse__hd::-webkit-details-marker {
  display: none;
}
.rv-collapse__chev {
  font-size: 13px;
  color: var(--gray-500);
}
.rv-collapse__body {
  padding: 0 0 22px;
}
.rv-subblock {
  margin-top: 22px;
}
.rv-subblock h3 {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-1000);
}
.rv-tag {
  display: inline-block;
  padding: 3px 8px;
  font-size: 12px;
  color: var(--gray-700);
  background: var(--gray-100);
}
.rv-tag--risk {
  color: var(--color-warning-500);
  background: var(--color-warning-50);
}
.rv-tag--strength {
  color: var(--color-success-500);
  background: var(--color-success-50);
}
.rv-tag--action {
  color: var(--main-800);
  background: var(--main-50);
}
.rv-tag--failed {
  color: var(--color-error-500);
  background: var(--color-error-50);
}
.rv-tag--passed {
  color: var(--color-success-500);
  background: var(--color-success-50);
}
.rv-tag--pending {
  color: var(--gray-600);
  background: var(--gray-100);
}
.rv-tag--weak {
  color: var(--main-600);
  background: var(--main-50);
}

/* 详细分析内 insights / expr / coding / report */
.rv-insights {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.rv-insight {
  padding: 14px 16px;
  border: 1px solid var(--gray-100);
  background: var(--gray-10);
}
.rv-insight__hd {
  display: flex;
  align-items: center;
  gap: 10px;
}
.rv-insight__hd h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-1000);
}
.rv-insight p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-700);
}
.rv-insight__refs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--gray-500);
}
.rv-expr {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.rv-expr__card {
  padding: 14px 16px;
  border: 1px solid var(--gray-100);
  background: var(--gray-10);
}
.rv-expr__hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-700);
}
.rv-expr__score {
  margin-top: 10px;
  font-size: 26px;
  font-weight: 800;
  color: var(--gray-1000);
}
.rv-expr__val,
.rv-expr__detail {
  margin-top: 6px;
  font-size: 13px;
  color: var(--gray-600);
}
.rv-coding {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rv-coding__row {
  display: flex;
  gap: 12px;
  font-size: 14px;
}
.rv-coding__row > span:first-child {
  width: 90px;
  flex-shrink: 0;
  color: var(--gray-500);
}
.rv-report-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  padding: 16px;
  border: 1px solid var(--gray-100);
  background: var(--gray-10);
}
.rv-report-stat__label {
  display: block;
  font-size: 12px;
  color: var(--gray-600);
}
.rv-report-stat__num {
  display: block;
  margin-top: 6px;
  font-size: 26px;
  font-weight: 800;
  color: var(--gray-1000);
}
.rv-report-stat__num--sm {
  font-size: 18px;
}
.rv-report-stat__note {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: var(--gray-500);
}
.rv-report-qs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.rv-report-q {
  padding: 14px 16px;
  border: 1px solid var(--gray-100);
  background: var(--gray-10);
}
.rv-report-q__hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.rv-report-q__idx {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--gray-500);
}
.rv-report-q__hd h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-1000);
}
.rv-report-q p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-700);
}
.rv-report-q__focus {
  color: var(--main-800);
  font-weight: 600;
}
.rv-list {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-700);
}

@media (max-width: 1024px) {
  .rv-conclusion {
    grid-template-columns: 1fr;
  }
  .rv-conclusion__score {
    border-right: 0;
    border-bottom: 1px solid var(--gray-100);
    padding-right: 0;
  }
  .rv-conclusion__text {
    padding-left: 0;
    padding-top: 22px;
  }
  .rv-mid {
    grid-template-columns: 1fr;
  }
  .rv-mid__col + .rv-mid__col {
    border-left: 0;
    border-top: 1px solid var(--gray-100);
    padding-left: 0;
  }
  .rv-expr,
  .rv-report-qs,
  .rv-report-stats {
    grid-template-columns: 1fr;
  }
}

@media print {
  .rv-root {
    overflow: visible;
    height: auto;
    padding: 0;
  }
  .rv-top__actions {
    display: none;
  }
  .rv-root :deep(button),
  .rv-collapse__chev {
    display: none !important;
  }
  .rv-state,
  .rv-incomplete-banner,
  .rv-source-chip {
    display: none;
  }
  .rv-conclusion,
  .rv-mid,
  .rv-questions {
    break-inside: avoid;
  }
  .rv-collapse {
    border-bottom: 0;
  }
  .rv-collapse__body {
    display: block !important;
    padding-bottom: 0;
  }
  .rv-subblock {
    margin-top: 10px;
  }
  .rv-top h1 {
    font-size: 22px;
  }
  .rv-score-num {
    font-size: 56px;
  }
  :global(.app-layout > .rail) {
    display: none !important;
  }
  :global(.app-layout) {
    display: block !important;
    width: auto;
    height: auto !important;
    min-width: 0 !important;
    overflow: visible !important;
  }
  :global(.app-router-view) {
    width: 100%;
    height: auto !important;
    max-width: none !important;
    overflow: visible !important;
  }
}
</style>
