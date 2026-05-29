<template>
  <div class="rv-root">
    <!-- States: loading / failed / generating / empty -->
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
      <!-- ====== HERO: Verdict first ====== -->
      <!-- V3-001 fix: warn the user when the scorecard is structurally
           incomplete (LLM produced no `overall`). Keeps the report visible
           so the candidate can still read whatever did make it through, but
           offers a single-click recovery. -->
      <div v-if="isIncompleteScorecard" class="rv-incomplete-banner" role="alert">
        <div class="rv-incomplete-banner__body">
          <strong>本次评估数据不完整</strong>
          <p>系统识别到模型本轮未生成有效的综合得分，下方仍展示了已经成功提炼的内容；建议重新生成报告以获得完整评分。</p>
        </div>
        <button class="rv-btn" :disabled="finalizing" @click="finalizeResult(true)">
          {{ finalizing ? '重新生成中…' : '重新生成评分' }}
        </button>
      </div>

      <header ref="heroEl" class="rv-hero">
        <div class="rv-hero__text">
          <div class="rv-hero__kicker">
            <span>{{ displayPosition }}</span><span class="rv-dot">·</span>
            <span>{{ displayRound }}</span>
            <span v-if="generatedAtText" class="rv-dot">·</span>
            <span v-if="generatedAtText">{{ generatedAtText }}</span>
          </div>
          <!-- TL;DR verdict — the single most important sentence on the page -->
          <h1 class="rv-hero__title">{{ heroVerdict }}</h1>
          <!-- Supporting context — one line only -->
          <p class="rv-hero__lead">{{ heroContext }}</p>
          <!-- Score source badge (P1: 任务 D) -->
          <div class="rv-hero__source-chip">{{ scoreSourceBadge }}</div>
          <div class="rv-hero__actions">
            <button class="rv-btn" @click="scrollToSection('section-report')">看完整报告</button>
            <button class="rv-btn rv-btn--secondary" @click="scrollToSection('section-evidence')">看评分依据</button>
            <button class="rv-btn rv-btn--secondary rv-btn--print" @click="exportToPDF" :disabled="loading">
              <PrinterOutlined /> 导出 PDF
            </button>
          </div>
        </div>
        <div class="rv-hero__score" :class="{ 'rv-hero__score--incomplete': isIncompleteScorecard }">
          <div class="rv-hero__score-ring">
            <svg viewBox="0 0 160 160" class="rv-hero__score-svg">
              <circle cx="80" cy="80" r="72" fill="none" stroke="var(--gray-200)" stroke-width="3" />
              <circle v-if="!isIncompleteScorecard" cx="80" cy="80" r="72" fill="none" stroke="var(--main-500)" stroke-width="3"
                stroke-linecap="round" :stroke-dasharray="452" :stroke-dashoffset="452 - (452 * (overallScore ?? 0) / 100)"
                class="rv-hero__score-arc" />
            </svg>
            <div class="rv-hero__score-inner">
              <span v-if="isIncompleteScorecard" class="rv-hero__score-num rv-hero__score-num--muted">—</span>
              <template v-else>
                <span class="rv-hero__score-num">{{ animatedScore }}</span>
                <span class="rv-hero__score-total">/ 100</span>
              </template>
            </div>
          </div>
          <div class="rv-hero__score-label">{{ scoreVerdictLabel }}</div>
        </div>
      </header>

      <!-- Sticky nav -->
      <nav ref="navEl" class="rv-nav" aria-label="报告导航">
        <button v-for="item in sectionLinks" :key="item.id" class="rv-nav__link" @click="scrollToSection(item.id)">{{ item.label }}</button>
      </nav>

      <!-- ====== SECTION 1: In a nutshell ====== -->
      <section ref="takeawaysEl" class="rv-takeaways">
        <article v-for="(card, i) in nutshellCards" :key="card.tone" class="rv-takeaway" :style="{ transitionDelay: `${i * 80}ms` }">
          <span class="rv-takeaway__num">{{ String(i + 1).padStart(2, '0') }}</span>
          <div>
            <span class="rv-takeaway__kicker">{{ card.kicker }}</span>
            <h3>{{ card.title }}</h3>
            <p :class="{ 'rv-takeaway__empty': card.empty }">{{ card.body }}</p>
          </div>
        </article>
      </section>

      <!-- ====== SECTION 2: What to keep & what to fix ====== -->
      <section id="section-insights" ref="insightsEl" class="rv-block">
        <h2 class="rv-block__title">哪些该保持，哪些该补上</h2>
        <p class="rv-block__sub">以下判断基于你本轮的具体回答与各维度得分。每条都标注了评分依据，点击标签可以跳到证据区。</p>
        <div v-if="normalizedReportHighlights.length" class="rv-insights">
          <article v-for="item in normalizedReportHighlights" :key="`${item.priority}-${item.title}`" class="rv-insight" :style="{ transitionDelay: `${(item.priority - 1) * 60}ms` }">
            <span class="rv-insight__num">0{{ item.priority }}</span>
            <div class="rv-insight__body">
              <div class="rv-insight__hd"><h3>{{ item.title }}</h3><a-tag :color="highlightToneColorMap[item.tone]">{{ highlightToneLabelMap[item.tone] }}</a-tag></div>
              <p>{{ item.summary }}</p>
              <div v-if="item.evidence_refs.length" class="rv-insight__refs"><span>判断依据</span><a-tag v-for="ref in item.evidence_refs" :key="`${item.title}-${ref.key}`" class="rv-insight__ref" @click="scrollToSection('section-evidence')">{{ ref.label }}</a-tag></div>
            </div>
          </article>
        </div>
        <div v-else class="rv-data-empty">分析数据不足，无法生成本部分关键判断。</div>
      </section>

      <!-- ====== SECTION 3: The evidence ====== -->
      <section id="section-evidence" ref="evidenceEl" class="rv-block">
        <h2 class="rv-block__title">分数是怎么来的</h2>
        <p class="rv-block__sub">每个维度的评分、每道题的评估、表达分析和代码结果——你的每一项得分都有迹可循。</p>

        <!-- Dimension overview -->
        <div v-if="dimensionScoreCards.length" class="rv-dims">
          <div v-for="item in dimensionScoreCards" :key="item.key" class="rv-dim">
            <div class="rv-dim__label">{{ item.label }}</div>
            <div class="rv-dim__score">{{ item.score }}<span>/100</span></div>
            <div class="rv-dim__interpretation">{{ getDimensionInterpretation(item) }}</div>
            <div class="rv-dim__track"><div class="rv-dim__fill" :style="{ width: `${item.score}%` }" /></div>
          </div>
        </div>
        <div v-else class="rv-data-empty">分析数据不足，无法展示各维度评分。</div>

        <div v-if="sepThetaTrajectory.length > 1" class="rv-block__sub-section">
          <h3>答题过程中你的能力估计变化</h3>
          <p class="rv-sub-hint">θ 越高代表你越接近高难度题。曲线上升表示你的回答正在推动系统给出更难的题目。</p>
          <AdaptiveTrajectory :trajectory="sepThetaTrajectory" :questions="sepQuestions" />
        </div>
        <div v-if="sepEvidenceChain.length" class="rv-block__sub-section">
          <h3>每题评分的推理过程</h3>
          <p class="rv-sub-hint">展示模型对每道题给出分数的具体推理链——从问题意图到你的回答，再到分数判定。</p>
          <EvidenceChain :items="sepEvidenceChain" />
        </div>
        <div v-if="expressionMetrics.length" class="rv-block__sub-section">
          <h3>表达与沟通</h3>
          <p class="rv-sub-hint">除了技术内容，面试官也在听你的表达。这几个维度反映了你传达信息的方式。</p>
          <div class="rv-expr">
            <div v-for="item in expressionMetrics" :key="item.key" class="rv-expr__card">
              <div class="rv-expr__hd"><span>{{ item.label }}</span><a-tag>{{ item.metric.level || '已分析' }}</a-tag></div>
              <div class="rv-expr__score">{{ item.metric.score ?? '--' }}</div>
              <div v-if="item.metric.value" class="rv-expr__val">{{ item.metric.value }}</div>
              <div v-if="item.metric.detail" class="rv-expr__detail">{{ item.metric.detail }}</div>
            </div>
          </div>
        </div>
        <!-- Technical question reviews -->
        <div class="rv-block__sub-section">
          <h3>逐题回看：你的回答与反馈</h3>
          <p class="rv-sub-hint">每道题都标注了面试官在考察什么、你的回答覆盖了哪些要点、还有哪些可以补充。</p>
          <div v-if="displayedQuestionReviews.length" class="rv-questions">
            <article v-for="(item, i) in displayedQuestionReviews" :key="`${item.question_index}-${item.question}`" class="rv-q" :style="{ transitionDelay: `${i * 50}ms` }">
              <div class="rv-q__hd">
                <div>
                  <span class="rv-q__idx">第 {{ item.question_index }} 题</span>
                  <h4>{{ item.question }}</h4>
                </div>
                <div class="rv-q__badges"><a-tag :color="getQuestionScoreColor(item.score)">{{ item.level || '待评估' }}</a-tag><a-tag>{{ item.score ?? '--' }}/100</a-tag><a-button v-if="canOpenQuestionSource(item)" size="small" type="link" @click="openQuestionSource(item)">查看知识点</a-button></div>
              </div>
              <div v-if="item.kb_name || item.file_name || item.asked_at" class="rv-q__meta">
                <span v-if="item.kb_name">题库：{{ item.kb_name }}</span>
                <span v-if="item.file_name">来源：{{ item.file_name }}</span>
                <span v-if="item.asked_at">提问时间：{{ item.asked_at }}</span>
              </div>
              <div class="rv-q__answer">
                <span class="rv-q__answer-label">你的回答摘要</span>
                <p v-if="item.answer_excerpt">{{ item.answer_excerpt }}</p>
                <p v-else class="rv-q__na">未记录到有效回答内容（可能是回答过短或音频质量原因）。</p>
              </div>
              <div v-if="item.matched_keywords?.length || item.suggested_keywords?.length" class="rv-q__kw">
                <a-tag v-for="kw in item.matched_keywords" :key="`${item.question_index}-hit-${kw}`" color="green">已覆盖：{{ kw }}</a-tag>
                <a-tag v-for="kw in item.suggested_keywords" :key="`${item.question_index}-miss-${kw}`" color="gold">建议补充：{{ kw }}</a-tag>
              </div>
              <div class="rv-q__cols">
                <div>
                  <span class="rv-q__col-label">做得好的地方</span>
                  <ul v-if="item.strengths?.length"><li v-for="s in item.strengths" :key="s">{{ s }}</li></ul>
                  <p v-else class="rv-q__na">分析数据不足。</p>
                </div>
                <div>
                  <span class="rv-q__col-label">可以更好的地方</span>
                  <ul v-if="item.gaps?.length"><li v-for="g in item.gaps" :key="g">{{ g }}</li></ul>
                  <p v-else class="rv-q__na">分析数据不足。</p>
                </div>
              </div>
            </article>
          </div>
          <p v-else class="rv-empty">本轮面试没有记录到技术题的详细评估数据。</p>
          <div v-if="technicalQuestionReviews.length > initialQuestionReviewCount" class="rv-block__more">
            <a-button type="link" @click="showAllQuestionReviews = !showAllQuestionReviews">
              {{ showAllQuestionReviews ? '收起' : `查看全部 ${technicalQuestionReviews.length} 道题` }}
            </a-button>
          </div>
        </div>
        <!-- Coding summary -->
        <div class="rv-block__sub-section">
          <h3>编程能力</h3>
          <p class="rv-sub-hint">现场写代码是最接近真实工作场景的考察方式。以下是你的代码考核结果。</p>
          <div v-if="codingSession" class="rv-coding">
            <div class="rv-coding__row"><span>题目</span><span>{{ codingSession.problem_title || '未记录' }}</span></div>
            <div class="rv-coding__row"><span>难度</span><span>{{ codingSession.difficulty_level || '未记录' }}</span></div>
            <div class="rv-coding__row"><span>判题结果</span><a-tag :color="judgeStatusColor">{{ judgeStatusLabel }}</a-tag></div>
            <div v-if="codingSession.submitted_at" class="rv-coding__row"><span>提交时间</span><span>{{ codingSession.submitted_at }}</span></div>
            <div v-if="codingSession.judge_result?.score !== undefined" class="rv-coding__row"><span>判题得分</span><span>{{ codingSession.judge_result.score }}</span></div>
          </div>
          <p v-else class="rv-empty">本轮面试没有编程考核环节。</p>
        </div>
      </section>

      <!-- ====== SECTION 4: Full report ====== -->
      <section id="section-report" ref="reportEl" class="rv-block">
        <h2 class="rv-block__title">完整评估详情</h2>
        <p class="rv-block__sub">包含综合结论、各维度详细评分、代表题目复盘和面试官视角的改进建议。</p>
        <div class="rv-report-stats">
          <div class="rv-report-stat rv-report-stat--score"><span class="rv-report-stat__label">综合评分</span><span class="rv-report-stat__num">{{ overallScore ?? '--' }}</span><span class="rv-report-stat__note">{{ scoreVerdictLabel }}</span></div>
          <div class="rv-report-stat"><span class="rv-report-stat__label">面试轮次</span><span class="rv-report-stat__num rv-report-stat__num--sm">{{ displayRound }}</span><span class="rv-report-stat__note">{{ generatedAtText || '已生成完整报告' }}</span></div>
          <div class="rv-report-stat"><span class="rv-report-stat__label">技术题数量</span><span class="rv-report-stat__num rv-report-stat__num--sm">{{ technicalQuestionReviews.length }} 道</span><span class="rv-report-stat__note">{{ questionScoreSummary.lowest ? `最低 ${questionScoreSummary.lowest.score ?? '--'} 分 · 最高 ${questionScoreSummary.highest?.score ?? '--'} 分` : '暂无评分数据' }}</span></div>
          <div v-if="codingSession" class="rv-report-stat"><span class="rv-report-stat__label">编程考核</span><span class="rv-report-stat__num rv-report-stat__num--sm">{{ judgeStatusLabel }}</span><span class="rv-report-stat__note">{{ codingSession.problem_title || '已完成' }}</span></div>
        </div>
        <div class="rv-report-body">
          <div class="rv-report-main">
            <div v-if="summaryMarkdown" class="rv-report-panel">
              <h3>面试官综合评语</h3>
              <MdPreview editor-id="interview-result-summary" :theme="theme" preview-theme="github" :show-code-row-number="false" :model-value="summaryMarkdown" />
            </div>
            <div v-if="scorecard" class="rv-report-panel"><h3>评分卡详情</h3><InterviewScorePanel :scorecard="scorecard" /></div>
            <div v-if="technicalQuestionReviews.length" class="rv-report-panel">
              <h3>最具代表性的两道题</h3>
              <p class="rv-sub-hint">一题最低分、一题最高分，帮助你快速定位自己的上下限。</p>
              <div class="rv-report-qs">
                <article v-for="item in reportQuestionSamples" :key="`report-${item.question_index}-${item.question}`" class="rv-report-q">
                  <div class="rv-report-q__hd"><div><span class="rv-report-q__idx">第 {{ item.question_index }} 题</span><h4>{{ item.question }}</h4></div><a-tag :color="getQuestionScoreColor(item.score)">{{ item.score ?? '--' }}/100</a-tag></div>
                  <p v-if="item.answer_excerpt">{{ item.answer_excerpt }}</p>
                  <p v-else class="rv-q__na">未记录到有效回答。</p>
                  <p v-if="item.gaps?.length" class="rv-report-q__focus">最值得改进的一点：{{ item.gaps[0] }}</p>
                </article>
              </div>
            </div>
          </div>
          <aside class="rv-report-side">
            <div v-if="dimensionScoreCards.length" class="rv-report-panel rv-report-panel--side">
              <h3>各维度一览</h3>
              <div v-for="item in dimensionScoreCards" :key="`rd-${item.key}`" class="rv-report-dim">
                <div class="rv-report-dim__hd"><span>{{ item.label }}</span><span class="rv-report-dim__val">{{ item.score }}</span></div>
                <div class="rv-report-dim__bar"><div class="rv-dim__fill" :style="{ width: `${item.score}%` }" /></div>
                <div class="rv-report-dim__desc">{{ getDimensionInterpretation(item) }}</div>
              </div>
            </div>
            <div v-if="scorecard?.strengths?.length" class="rv-report-panel rv-report-panel--side">
              <h3>你的优势</h3>
              <ul class="rv-report-list"><li v-for="s in scorecard.strengths" :key="`s-${s}`">{{ s }}</li></ul>
            </div>
            <div v-if="scorecard?.risks?.length" class="rv-report-panel rv-report-panel--side">
              <h3>需要警惕的方面</h3>
              <ul class="rv-report-list"><li v-for="r in scorecard.risks" :key="`r-${r}`">{{ r }}</li></ul>
            </div>
            <div v-if="scorecard?.suggestions?.length" class="rv-report-panel rv-report-panel--side">
              <h3>下一步建议</h3>
              <ul class="rv-report-list"><li v-for="sg in scorecard.suggestions" :key="`sg-${sg}`">{{ sg }}</li></ul>
            </div>
            <div v-if="codingSession" class="rv-report-panel rv-report-panel--side">
              <h3>编程考核摘要</h3>
              <div class="rv-coding"><div class="rv-coding__row"><span>题目</span><span>{{ codingSession.problem_title || '-' }}</span></div><div class="rv-coding__row"><span>判题结果</span><a-tag :color="judgeStatusColor">{{ judgeStatusLabel }}</a-tag></div><div v-if="codingSession.judge_result?.score !== undefined" class="rv-coding__row"><span>判题得分</span><span>{{ codingSession.judge_result.score }}</span></div></div>
            </div>
          </aside>
        </div>
      </section>

      <!-- ====== SECTION 5: Learning loop — turn weak points into actions ====== -->
      <section id="section-next-steps" ref="nextStepsEl" class="rv-block">
        <h2 class="rv-block__title">下一步：把薄弱点变成下一次面试的强项</h2>
        <p class="rv-block__sub">基于你本轮的低分题和薄弱维度，自动整理了下面的学习与练习入口。点击直接跳到对应模块——不需要再自己搜关键词。</p>
        <div v-if="learningPathRecommendations.length" class="rv-nextsteps">
          <article v-for="rec in learningPathRecommendations" :key="`${rec.type}-${rec.keyword}`" class="rv-nextstep">
            <div class="rv-nextstep__hd">
              <h3>{{ rec.title }}</h3>
              <a-tag v-if="rec.type === 'review'" color="gold">来自低分题</a-tag>
              <a-tag v-else color="processing">薄弱维度</a-tag>
            </div>
            <p class="rv-nextstep__reason">{{ rec.reason }}</p>
            <div class="rv-nextstep__actions">
              <button class="rv-btn rv-btn--secondary rv-btn--sm" @click="openLearnFor(rec)">
                {{ rec.locator?.file_id ? '查看原始知识点' : '去知识库学习' }}
              </button>
              <button class="rv-btn rv-btn--sm" @click="openPracticeFor(rec)">去做相关练习题</button>
            </div>
          </article>
        </div>
        <p v-else class="rv-empty">本轮没有识别出明显薄弱点，可以选个新方向去 <router-link to="/learn">知识库</router-link> 或 <router-link to="/practice">代码练习</router-link> 继续挑战自己。</p>
      </section>

      <InterviewKnowledgeLearnModal v-model:open="learningModalVisible" :resource="activeLearningResource" />
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const initialQuestionReviewCount = 2
const sectionLinks = [
  { id: 'section-insights', label: '关键判断' },
  { id: 'section-evidence', label: '评分依据' },
  { id: 'section-report', label: '完整报告' },
  { id: 'section-next-steps', label: '下一步学习' }
]
const highlightToneColorMap = { risk: 'gold', strength: 'green', action: 'processing' }
const highlightToneLabelMap = { risk: '需要优先改进', strength: '建议继续保持', action: '值得关注' }
const dimensionLabelMap = {
  technical_competence: '技术能力', technical_knowledge: '技术能力', practical_experience: '技术能力',
  problem_solving: '问题解决', problem_solving_innovation: '问题解决',
  communication: '沟通表达', communication_clarity: '沟通表达',
  soft_skills: '综合素质', soft_skills_team_fit: '综合素质'
}
const scoreVerdictLabels = [
  { max: 40, text: '基础还需打磨' },
  { max: 55, text: '有潜力，需要系统补强' },
  { max: 70, text: '基本功过关，重点突破短板' },
  { max: 85, text: '表现不错，冲刺更高水平' },
  { max: 100, text: '面试表现优秀' }
]
const judgeStatusLabelMap = {
  PENDING: '等待判题', JUDGING: '判题中', ACCEPTED: '通过', WRONG_ANSWER: '答案错误',
  COMPILE_ERROR: '编译错误', RUNTIME_ERROR: '运行错误', SYSTEM_ERROR: '系统错误',
  MEMORY_LIMIT_EXCEEDED: '内存超限', CPU_TIME_LIMIT_EXCEEDED: 'CPU 超时',
  REAL_TIME_LIMIT_EXCEEDED: '运行超时', PARTIALLY_ACCEPTED: '部分通过'
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

const heroEl = ref(null)
const navEl = ref(null)
const takeawaysEl = ref(null)
const insightsEl = ref(null)
const evidenceEl = ref(null)
const reportEl = ref(null)
const nextStepsEl = ref(null)
const animatedScore = ref(0)
let observer = null
let scoreAnimFrame = null

const threadId = computed(() => String(route.query.threadId || '').trim())
const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || '初试')
const theme = computed(() => (themeStore.isDark ? 'dark' : 'light'))

const normalizeDimensionKey = (value) => {
  const key = String(value || '').trim().toLowerCase()
  if (!key) return ''
  const map = { technical_competence: 'technical_competence', technical_knowledge: 'technical_competence', practical_experience: 'technical_competence', '技术能力': 'technical_competence', problem_solving: 'problem_solving', problem_solving_innovation: 'problem_solving', '问题解决': 'problem_solving', communication: 'communication', communication_clarity: 'communication', '沟通表达': 'communication', soft_skills: 'soft_skills', soft_skills_team_fit: 'soft_skills', '综合素质': 'soft_skills' }
  return map[key] || key
}
const getDimensionLabel = (key) => dimensionLabelMap[normalizeDimensionKey(key)] || key || '待分析'

// Replaces the old hardcoded `dimensionInterpretations` four-tier cliché text.
// Derives a short evidence-anchored sentence from the actual score + evidence count.
// If no evidence exists, returns explicit "data insufficient" label.
const getDimensionInterpretation = (item) => {
  if (!item || typeof item.score !== 'number') return '分析数据不足'
  const score = item.score
  const evidenceCount = item.evidence_count ?? 0
  const label = item.label || ''
  if (evidenceCount === 0) {
    return `当前 ${score} 分，但本轮没有采集到足够的${label}评分证据，结果仅供参考。`
  }
  if (score >= 80) return `${score} 分，基于 ${evidenceCount} 条评分证据，${label}表现稳定。`
  if (score >= 60) return `${score} 分，基于 ${evidenceCount} 条评分证据，${label}基本达标但有提升空间。`
  if (score >= 40) return `${score} 分，基于 ${evidenceCount} 条评分证据，${label}存在明显短板。`
  return `${score} 分，基于 ${evidenceCount} 条评分证据，${label}需要系统性补强。`
}

const getScoreVerdict = (score) => {
  for (const tier of scoreVerdictLabels) { if (score <= tier.max) return tier.text }
  return scoreVerdictLabels[scoreVerdictLabels.length - 1].text
}

const normalizeScore = (value) => { const numeric = Number(value); return Number.isFinite(numeric) ? Math.max(0, Math.min(100, Math.round(numeric))) : null }

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
  return { db_id: dbId, file_id: fileId, chunk_id: String(locator.chunk_id || source?.chunk_id || '').trim() || undefined, chunk_index: locator.chunk_index !== undefined && locator.chunk_index !== null ? Number(locator.chunk_index) : source?.chunk_index !== undefined && source?.chunk_index !== null ? Number(source.chunk_index) : undefined, keyword: String(locator.keyword || '').trim() || undefined, query_text: String(locator.query_text || '').trim() || undefined }
}

const normalizeCodingSession = (value) => {
  if (!value || typeof value !== 'object') return null
  return { ...value, submitted_at: value.submitted_at ? formatDateTime(value.submitted_at) : '' }
}

const result = computed(() => payload.value?.result || null)
const codingSession = computed(() => normalizeCodingSession(payload.value?.coding_session || null))
const scorecard = computed(() => result.value?.scorecard || null)
const expressionAnalysis = computed(() => result.value?.expression_analysis || null)
const reportHighlights = computed(() => Array.isArray(result.value?.report_highlights) ? result.value.report_highlights : [])
const summaryMarkdown = computed(() => String(result.value?.summary_markdown || '').replace(/\n*\s*完整结果已生成，可在面试结果页查看。?\s*$/u, '').trim())
const hasCompletedResult = computed(() => result.value?.status === 'completed' && Boolean(scorecard.value || summaryMarkdown.value || reportHighlights.value.length || technicalQuestionReviews.value.length))
const isGenerating = computed(() => result.value?.status === 'generating')
const failedMessage = computed(() => result.value?.status === 'failed' ? result.value?.error_message || '请稍后重试' : '')
const threadTitle = computed(() => payload.value?.title || `${selectedPosition.value} · ${selectedRound.value}`)
const threadContext = computed(() => parseThreadTitle(threadTitle.value))
const displayPosition = computed(() => scorecard.value?.role || codingSession.value?.target_position || threadContext.value.position || selectedPosition.value)
const displayRound = computed(() => scorecard.value?.round || threadContext.value.round || selectedRound.value)
const generatedAtText = computed(() => result.value?.generated_at ? formatDateTime(result.value.generated_at) : '')
const overallScore = computed(() => normalizeScore(scorecard.value?.overall ?? scorecard.value?.overall_score ?? scorecard.value?.total_score))

// V3-001 fix: `status === "completed"` does NOT guarantee `overall` exists.
// In practice ~50% of historical threads have `overall=null` because the
// LLM occasionally returns a malformed scorecard. We surface that explicitly
// instead of pretending the score is 0/100 with verdict "等待评估".
const isIncompleteScorecard = computed(
  () => hasCompletedResult.value && overallScore.value === null
)

const scoreVerdictLabel = computed(() => {
  if (overallScore.value !== null) return getScoreVerdict(overallScore.value)
  if (isIncompleteScorecard.value) return '评分数据不完整'
  return '等待评估'
})

// Score source chip (P1: 任务 D)
const scoreSourceBadge = computed(() => {
  const src = String(scorecard.value?.score_source || '').trim()
  const coverage = Number(scorecard.value?.sep_coverage)
  if (src === 'sep') return '基于规则引擎评分 · 100% 题库覆盖'
  if (src === 'sep_partial' && Number.isFinite(coverage)) {
    return `基于规则引擎评分 · ${Math.round(coverage * 100)}% 题库覆盖（其余维度由 LLM 评估）`
  }
  return '基于 LLM 综合评估'
})

const heroVerdict = computed(() => {
  const risk = primaryRiskHighlight.value
  const strength = primaryStrengthHighlight.value
  if (risk && (overallScore.value ?? 0) < 60) return `你的${displayPosition.value}面试还需要系统性准备`
  if (risk) return `${risk.title}`
  if (strength && (overallScore.value ?? 0) >= 80) return `这轮${displayPosition.value}面试，你展现出了扎实的功底`
  return `${displayRound}${displayPosition.value}面试已完成`
})

const heroContext = computed(() => {
  const risk = primaryRiskHighlight.value
  const action = primaryActionHighlight.value
  if (risk && action) return `${risk.summary?.slice(0, 80)}… 建议优先关注：${action.title}。`
  if (risk) return risk.summary || '查看下方完整报告了解详细分析和改进建议。'
  return '查看下方完整报告了解详细分析和改进建议。'
})

const dimensionScoreCards = computed(() => {
  const dimensions = Array.isArray(scorecard.value?.dimensions) ? scorecard.value.dimensions : []
  return dimensions.map((item) => {
    const key = normalizeDimensionKey(item?.key || item?.name)
    const score = normalizeScore(item?.score)
    if (!key || score === null) return null
    const evidenceCount = Number.isFinite(Number(item?.evidence_count)) ? Number(item.evidence_count)
      : Array.isArray(item?.evidence) ? item.evidence.length : 0
    return { key, label: getDimensionLabel(key), score, evidence_count: evidenceCount }
  }).filter(Boolean).sort((a, b) => a.score - b.score)
})

const sepEvidenceChain = computed(() => Array.isArray(scorecard.value?.sep_evidence_chain) ? scorecard.value.sep_evidence_chain : [])
const sepThetaTrajectory = computed(() => Array.isArray(scorecard.value?.sep_theta_trajectory) ? scorecard.value.sep_theta_trajectory : [])
const sepQuestions = computed(() => { const seen = new Set(); return sepEvidenceChain.value.filter(item => { if (seen.has(item.question)) return false; seen.add(item.question); return true }).slice(0, sepThetaTrajectory.value.length - 1).map(item => ({ concept: item.concept, difficulty: item.difficulty ?? null })) })

const expressionMetrics = computed(() => {
  const analysis = expressionAnalysis.value
  if (!analysis) return []
  return [{ key: 'speech_rate', label: '语速', metric: analysis.speech_rate }, { key: 'pause_control', label: '停顿控制', metric: analysis.pause_control }, { key: 'clarity', label: '清晰度', metric: analysis.clarity }, { key: 'confidence', label: '自信度', metric: analysis.confidence }].filter((item) => item.metric)
})

const technicalQuestionReviews = computed(() => {
  const items = Array.isArray(result.value?.technical_question_reviews) ? result.value.technical_question_reviews : []
  return items.map((item, index) => ({ ...item, question_index: Number(item?.question_index || index + 1), score: normalizeScore(item?.score), asked_at: item?.asked_at ? formatDateTime(item.asked_at) : '', locator: resolveLearningLocator(item) })).sort((a, b) => (a.question_index || 0) - (b.question_index || 0))
})

const displayedQuestionReviews = computed(() => showAllQuestionReviews.value ? technicalQuestionReviews.value : technicalQuestionReviews.value.slice(0, initialQuestionReviewCount))
const questionScoreSummary = computed(() => { const scored = technicalQuestionReviews.value.filter((item) => item.score !== null); if (!scored.length) return { lowest: null, highest: null }; const sortedByScore = [...scored].sort((a, b) => (a.score ?? 0) - (b.score ?? 0)); return { lowest: sortedByScore[0], highest: sortedByScore[sortedByScore.length - 1] } })
const reportQuestionSamples = computed(() => { const samples = []; if (questionScoreSummary.value.lowest) samples.push(questionScoreSummary.value.lowest); if (questionScoreSummary.value.highest && questionScoreSummary.value.highest.question_index !== questionScoreSummary.value.lowest?.question_index) samples.push(questionScoreSummary.value.highest); if (samples.length >= 2) return samples; return technicalQuestionReviews.value.slice(0, 2) })

// Learning-loop recommendations (task 14): turn weak dimensions and low-score
// question concepts into actionable links into the existing /learn and /practice
// modules. Only emits cards anchored in real data — no filler "go practice more".
const learningPathRecommendations = computed(() => {
  const recs = []
  const seenKeywords = new Set()
  const pickKeyword = (raw) => {
    const k = String(raw || '').trim()
    if (!k || seenKeywords.has(k)) return null
    seenKeywords.add(k)
    return k
  }
  // 1) Low-score question concepts — most concrete actionable signal.
  const sortedReviews = [...technicalQuestionReviews.value]
    .filter((q) => q.score !== null && q.score < 70)
    .sort((a, b) => (a.score ?? 100) - (b.score ?? 100))
    .slice(0, 3)
  for (const review of sortedReviews) {
    const keyword = pickKeyword(
      review.suggested_keywords?.[0]
        || review.matched_keywords?.[0]
        || review.kb_name
        || review.question
    )
    if (!keyword) continue
    recs.push({
      type: 'review',
      keyword,
      title: `补强：${keyword}`,
      reason: `第 ${review.question_index} 题得分 ${review.score} 分，${review.gaps?.[0] || '建议系统复习此知识点'}`,
      learn_query: keyword,
      practice_query: keyword,
      locator: review.locator || null,
      file_name: review.file_name || ''
    })
  }
  // 2) Weak dimensions — high-level direction.
  for (const dim of dimensionScoreCards.value.slice(0, 2)) {
    if (dim.score >= 75) break
    const keyword = pickKeyword(dim.label)
    if (!keyword) continue
    recs.push({
      type: 'dimension',
      keyword,
      title: `${keyword}维度专项提升`,
      reason: `本轮 ${dim.score} 分，是相对薄弱的维度，建议集中训练。`,
      learn_query: keyword,
      practice_query: keyword,
      locator: null,
      file_name: ''
    })
  }
  return recs.slice(0, 4)
})

const openLearnFor = (rec) => {
  if (rec.locator?.db_id && rec.locator?.file_id) {
    router.push({
      name: 'LearnDocumentPage',
      params: { db_id: rec.locator.db_id, file_id: rec.locator.file_id },
      query: rec.locator.chunk_id ? { chunk: rec.locator.chunk_id } : undefined
    })
    return
  }
  router.push({ name: 'LearnHomePage', query: { q: rec.learn_query } })
}
const openPracticeFor = (rec) => {
  router.push({ name: 'PracticeHomePage', query: { q: rec.practice_query } })
}

const judgeStatus = computed(() => String(codingSession.value?.judge_status || codingSession.value?.judge_result?.status || '').trim() || 'UNKNOWN')
const judgeStatusColor = computed(() => { if (judgeStatus.value === 'ACCEPTED') return 'green'; if (['PENDING', 'JUDGING'].includes(judgeStatus.value)) return 'blue'; if (['WRONG_ANSWER', 'COMPILE_ERROR', 'RUNTIME_ERROR', 'SYSTEM_ERROR', 'MEMORY_LIMIT_EXCEEDED', 'CPU_TIME_LIMIT_EXCEEDED', 'REAL_TIME_LIMIT_EXCEEDED'].includes(judgeStatus.value)) return 'red'; return 'gold' })
const judgeStatusLabel = computed(() => judgeStatusLabelMap[judgeStatus.value] || judgeStatus.value)

// Replaces the old `fallbackHighlights` motivational filler text.
// Only emits highlights anchored in real data; otherwise the consumer (nutshellCards / normalizedReportHighlights)
// renders an explicit "data insufficient" placeholder instead of inspirational copy.
const dataDrivenFallbackHighlights = computed(() => {
  const items = []
  const sortedReviews = [...technicalQuestionReviews.value].sort((a, b) => (a.score ?? 999) - (b.score ?? 999))
  const lowReview = sortedReviews[0]
  const highReview = [...technicalQuestionReviews.value].sort((a, b) => (b.score ?? -1) - (a.score ?? -1))[0]
  const weakDimension = dimensionScoreCards.value[0]
  const strongDimension = [...dimensionScoreCards.value].sort((a, b) => b.score - a.score)[0]

  // Risk: require a real low-scoring question with a concrete gap, or a sub-60 weak dimension.
  if (lowReview && lowReview.gaps?.length) {
    items.push({
      title: `第 ${lowReview.question_index} 题：${lowReview.question || '低分题'}`,
      summary: lowReview.gaps[0],
      tone: 'risk',
      dimension_key: 'technical_competence',
      priority: 1,
      evidence_refs: [{ kind: 'question_review', key: `question_review:${lowReview.question_index}`, label: `第 ${lowReview.question_index} 题 · ${lowReview.score ?? '--'} 分` }]
    })
  } else if (weakDimension && weakDimension.score < 60) {
    items.push({
      title: `${weakDimension.label}得分 ${weakDimension.score}`,
      summary: `本轮${weakDimension.label}维度得分低于及格线，建议作为下一步重点。`,
      tone: 'risk',
      dimension_key: weakDimension.key,
      priority: 1,
      evidence_refs: [{ kind: 'dimension', key: weakDimension.key, label: `${weakDimension.label} · ${weakDimension.score} 分` }]
    })
  }

  // Strength: require a ≥80 question with a concrete strength, or backend-provided strengths list.
  if (highReview && (highReview.score ?? 0) >= 80 && highReview.strengths?.length) {
    items.push({
      title: `第 ${highReview.question_index} 题：${highReview.question || '高分题'}`,
      summary: highReview.strengths[0],
      tone: 'strength',
      dimension_key: 'technical_competence',
      priority: 2,
      evidence_refs: [{ kind: 'question_review', key: `question_review:${highReview.question_index}`, label: `第 ${highReview.question_index} 题 · ${highReview.score ?? '--'} 分` }]
    })
  } else if (scorecard.value?.strengths?.length) {
    items.push({
      title: '面试官认可的强项',
      summary: scorecard.value.strengths[0],
      tone: 'strength',
      dimension_key: strongDimension?.key || '',
      priority: 2,
      evidence_refs: strongDimension ? [{ kind: 'dimension', key: strongDimension.key, label: `${strongDimension.label} · ${strongDimension.score} 分` }] : []
    })
  }

  // Action: require a concrete weak dimension (<80) or a low-review with a gap.
  if (weakDimension && weakDimension.score < 80) {
    items.push({
      title: `下一步：补强${weakDimension.label}`,
      summary: `${weakDimension.label}当前 ${weakDimension.score} 分，是性价比最高的提升方向。`,
      tone: 'action',
      dimension_key: weakDimension.key,
      priority: 3,
      evidence_refs: [{ kind: 'dimension', key: weakDimension.key, label: `${weakDimension.label} · ${weakDimension.score} 分` }]
    })
  } else if (lowReview && lowReview.gaps?.length) {
    items.push({
      title: `下一步：复盘第 ${lowReview.question_index} 题`,
      summary: `针对该题已识别的缺口（${lowReview.gaps[0]}）做定向补强。`,
      tone: 'action',
      dimension_key: 'technical_competence',
      priority: 3,
      evidence_refs: [{ kind: 'question_review', key: `question_review:${lowReview.question_index}`, label: `第 ${lowReview.question_index} 题 · ${lowReview.score ?? '--'} 分` }]
    })
  }

  return items.slice(0, 3)
})

const normalizedReportHighlights = computed(() => {
  // Prefer backend-provided highlights; otherwise fall back to data-anchored items only.
  // Filter out any entry lacking a real title or summary (no synthetic "洞察 N" / "系统已提炼" filler).
  const source = reportHighlights.value.length ? reportHighlights.value : dataDrivenFallbackHighlights.value
  return source.map((item, index) => ({
    title: String(item?.title || '').trim(),
    summary: String(item?.summary || '').trim(),
    tone: ['risk', 'strength', 'action'].includes(String(item?.tone || '').trim()) ? item.tone : 'action',
    dimension_key: normalizeDimensionKey(item?.dimension_key),
    priority: Number(item?.priority || index + 1),
    evidence_refs: Array.isArray(item?.evidence_refs) ? item.evidence_refs.map((refItem, refIndex) => ({
      kind: ['question_review', 'dimension', 'expression_metric', 'coding'].includes(String(refItem?.kind || '').trim()) ? refItem.kind : 'dimension',
      key: String(refItem?.key || `${index}-${refIndex}`).trim(),
      label: String(refItem?.label || '相关证据').trim()
    })).filter((refItem) => refItem.key) : []
  })).filter((item) => item.title && item.summary).sort((a, b) => a.priority - b.priority).slice(0, 3)
})

const primaryRiskHighlight = computed(() => normalizedReportHighlights.value.find((item) => item.tone === 'risk') || normalizedReportHighlights.value[0] || null)
const primaryStrengthHighlight = computed(() => normalizedReportHighlights.value.find((item) => item.tone === 'strength') || null)
const primaryActionHighlight = computed(() => normalizedReportHighlights.value.find((item) => item.tone === 'action') || null)

// nutshellCards now degrade explicitly when the corresponding highlight is missing,
// instead of rendering motivational filler.
const nutshellCards = computed(() => {
  const s = primaryStrengthHighlight.value
  const r = primaryRiskHighlight.value
  const a = primaryActionHighlight.value
  return [
    {
      tone: 'strength',
      kicker: '继续保持',
      title: s?.title || '暂未识别明确强项',
      body: s?.summary || '本轮回答中未提炼出可作为强项的具体证据。',
      empty: !s
    },
    {
      tone: 'risk',
      kicker: '如果只改一件事',
      title: r?.title || '暂未识别明确风险',
      body: r?.summary || '本轮回答中未提炼出可作为风险的具体证据。',
      empty: !r
    },
    {
      tone: 'action',
      kicker: '下次面试前',
      title: a?.title || '暂未生成下一步建议',
      body: a?.summary || '需要更多评分证据才能给出有针对性的下一步行动。',
      empty: !a
    }
  ]
})

const getQuestionScoreColor = (score) => { const normalized = normalizeScore(score); if (normalized === null) return 'default'; if (normalized >= 80) return 'green'; if (normalized >= 60) return 'gold'; return 'red' }
const canOpenQuestionSource = (item) => Boolean(resolveLearningLocator(item))
const openQuestionSource = (item) => { activeLearningResource.value = { title: item.file_name || item.question || '题源知识点', summary: item.question || '', locator: resolveLearningLocator(item) }; learningModalVisible.value = true }
const scrollToSection = (id) => { if (typeof document === 'undefined') return; const target = document.getElementById(id); if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' }) }

// PDF export via the browser's native print dialog.
// `@media print` rules below hide the app chrome and expand all collapsed
// sections so the printed copy is self-contained.
const exportToPDF = async () => {
  if (typeof document === 'undefined' || typeof window === 'undefined') return
  // Make sure all "see more" sections are expanded before printing.
  const wasCollapsed = !showAllQuestionReviews.value
  if (wasCollapsed) showAllQuestionReviews.value = true
  // Cache the original document title; restore it after the dialog closes
  // so saved PDFs use a meaningful filename.
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
  }
}

const animateScore = (target) => {
  if (scoreAnimFrame) cancelAnimationFrame(scoreAnimFrame)
  const start = animatedScore.value; const diff = target - start
  if (diff === 0) return
  const startTime = performance.now()
  const easeOutExpo = (t) => t === 1 ? 1 : 1 - Math.pow(2, -10 * t)
  const tick = (now) => { const elapsed = now - startTime; const progress = Math.min(elapsed / 1200, 1); animatedScore.value = Math.round(start + diff * easeOutExpo(progress)); if (progress < 1) scoreAnimFrame = requestAnimationFrame(tick) }
  scoreAnimFrame = requestAnimationFrame(tick)
}
watch(overallScore, (val) => { if (val !== null) animateScore(val) }, { immediate: true })

const setupObserver = () => {
  const revealEls = [takeawaysEl.value, insightsEl.value, evidenceEl.value, reportEl.value, nextStepsEl.value].filter(Boolean)
  if (!revealEls.length) return; if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => { entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target) } }) }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' })
  revealEls.forEach(el => observer.observe(el))
}

const loadResult = async () => { if (!threadId.value) return; loading.value = true; try { payload.value = await interviewCodeApi.getInterviewResult(threadId.value) } catch (error) { message.error(error.message || '加载面试结果失败') } finally { loading.value = false; await nextTick(); setupObserver() } }
const finalizeResult = async (force = false) => { if (!threadId.value) return; finalizing.value = true; try { payload.value = await interviewCodeApi.finalizeInterviewResult(threadId.value, { target_position: displayPosition.value, interview_round: displayRound.value, force }); if ((payload.value?.result || {}).status === 'completed') { router.replace({ name: 'InterviewResultPage', query: { threadId: threadId.value, position: displayPosition.value, round: displayRound.value } }); message.success(force ? '面试结果已重新生成' : '面试结果已生成') } } catch (error) { message.error(error.message || '生成面试结果失败'); await loadResult() } finally { finalizing.value = false; await nextTick(); setupObserver() } }

onMounted(async () => { if (!threadId.value) { router.replace({ name: 'AgentComp', query: { position: selectedPosition.value, round: selectedRound.value } }); return }; await loadResult(); if (!hasCompletedResult.value && !isGenerating.value && route.query.autoGenerate === '1') await finalizeResult() })
onBeforeUnmount(() => { if (observer) observer.disconnect(); if (scoreAnimFrame) cancelAnimationFrame(scoreAnimFrame) })
</script>

<style lang="less" scoped>
// Unified platform sans-serif stack. Serif display font removed (P0-3).
@font-body: system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;

.rv-root {
  min-height: 100vh;
  padding: 56px 48px 96px;
  background: var(--gray-25);
  max-width: 960px;
  margin: 0 auto;
  font-family: @font-body;
  color: var(--gray-1000);
  -webkit-font-smoothing: antialiased;
  position: relative;
}
.rv-dot { color: var(--gray-300); }
.rv-sub-hint { font-size: 13px; color: var(--gray-600); margin: 0 0 16px; line-height: 1.6; }
.rv-data-empty {
  font-size: 13px;
  color: var(--gray-500);
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  padding: 14px 18px;
  text-align: center;
}

.rv-btn {
  border: none;
  border-radius: 6px;
  background: var(--main-500);
  color: var(--gray-0);
  padding: 10px 24px;
  font-family: @font-body;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover:not(:disabled) { background: var(--main-600); }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
}
.rv-btn--secondary {
  background: var(--gray-0);
  color: var(--gray-1000);
  border: 1px solid var(--gray-300);
  &:hover:not(:disabled) {
    background: var(--main-50);
    color: var(--main-700);
    border-color: var(--main-300);
  }
}

.rv-state {
  min-height: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  text-align: center;
}
.rv-state__mark {
  width: 56px; height: 56px;
  border: 1px solid var(--gray-200);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-family: @font-body;
  font-size: 24px;
  font-weight: 500;
  color: var(--main-600);
}
.rv-state__mark--muted { color: var(--gray-500); border-color: var(--gray-200); }
.rv-state h2 { font-family: @font-body; font-size: 22px; font-weight: 600; margin: 0; }
.rv-state p { font-size: 15px; color: var(--gray-700); max-width: 440px; line-height: 1.6; margin: 0; }

.rv-hero {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 56px;
  align-items: center;
  padding: 36px 0 44px;
  border-bottom: 1px solid var(--gray-200);
}
.rv-hero__text { display: flex; flex-direction: column; gap: 14px; }
.rv-hero__kicker {
  font-size: 12px; color: var(--gray-600);
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.rv-hero__title {
  font-family: @font-body;
  font-size: 30px;
  font-weight: 600;
  line-height: 1.25;
  margin: 0;
  color: var(--gray-1000);
}
.rv-hero__lead { font-size: 15px; line-height: 1.6; color: var(--gray-700); margin: 0; max-width: 65ch; }
.rv-hero__source-chip {
  align-self: flex-start;
  display: inline-block;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  background: var(--color-info-100);
  color: var(--color-info-700);
  border: 1px solid var(--color-info-100);
}
.rv-hero__actions { display: flex; gap: 12px; margin-top: 8px; }
.rv-hero__score { text-align: center; position: relative; }
.rv-hero__score-ring { position: relative; width: 180px; height: 180px; margin: 0 auto; }
.rv-hero__score-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.rv-hero__score-arc { transition: stroke-dashoffset 1.2s ease; }
.rv-hero__score-inner {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.rv-hero__score-num {
  font-family: @font-body;
  font-size: 48px;
  font-weight: 600;
  line-height: 1;
  color: var(--main-600);
}
.rv-hero__score-num--muted { color: var(--gray-400); }
.rv-hero__score--incomplete .rv-hero__score-num { color: var(--gray-400); }
.rv-hero__score-total { font-size: 14px; color: var(--gray-500); margin-top: 4px; }

/* V3-001 fix: incomplete-scorecard banner sits just above the hero block. */
.rv-incomplete-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  margin-bottom: 24px;
  background: var(--color-warning-50);
  border: 1px solid var(--color-warning-100);
  border-radius: 8px;
  color: var(--gray-1000);
}
.rv-incomplete-banner__body { flex: 1; min-width: 0; }
.rv-incomplete-banner__body strong { display: block; font-size: 15px; margin-bottom: 4px; color: var(--color-warning-700); }
.rv-incomplete-banner__body p { margin: 0; font-size: 13px; line-height: 1.6; color: var(--gray-700); }
.rv-hero__score-label {
  font-size: 13px; color: var(--gray-700); font-weight: 500; margin-top: 16px;
  padding: 6px 14px;
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  display: inline-block;
  background: var(--gray-0);
}

.rv-nav {
  display: flex; gap: 0;
  padding: 10px 0;
  position: sticky; top: 0; z-index: 10;
  background: var(--gray-25);
  border-bottom: 1px solid var(--gray-200);
}
.rv-nav__link {
  border: none; border-radius: 0;
  background: none; color: var(--gray-600);
  padding: 8px 18px;
  font-family: @font-body; font-size: 13px; font-weight: 500;
  cursor: pointer;
  transition: color 0.2s ease, background 0.2s ease;
}
.rv-nav__link:hover { color: var(--main-600); background: var(--gray-50); }

.rv-takeaways, .rv-block {
  opacity: 0;
  transition: opacity 0.5s ease;
  &.is-visible { opacity: 1; }
}
.rv-takeaways {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 32px;
}
.rv-takeaway {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 24px 20px;
  display: flex;
  gap: 14px;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover { background: var(--gray-50); border-color: var(--gray-300); }
}
.rv-takeaway__num {
  font-family: @font-body;
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-400);
  flex-shrink: 0;
  line-height: 1.2;
}
.rv-takeaway__kicker { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-takeaway h3 { font-family: @font-body; font-size: 15px; font-weight: 600; margin: 6px 0 0; line-height: 1.4; }
.rv-takeaway p { font-size: 13px; line-height: 1.6; color: var(--gray-700); margin: 8px 0 0; }
.rv-takeaway__empty { color: var(--gray-500); font-style: italic; }

.rv-block__title { font-family: @font-body; font-size: 22px; font-weight: 600; margin: 0; padding-top: 56px; }
.rv-block__sub { font-size: 14px; color: var(--gray-700); line-height: 1.6; margin: 8px 0 24px; max-width: 60ch; }
.rv-block__sub-section { margin-top: 40px; }
.rv-block__sub-section h3 { font-family: @font-body; font-size: 16px; font-weight: 600; margin: 0 0 4px; }
.rv-block__more { margin-top: 16px; }

.rv-insights { display: flex; flex-direction: column; gap: 12px; }
.rv-insight {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 24px;
  display: flex;
  gap: 20px;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover { background: var(--gray-50); border-color: var(--main-300); }
}
.rv-insight__num {
  font-family: @font-body;
  font-size: 28px;
  font-weight: 600;
  color: var(--gray-300);
  line-height: 1;
  flex-shrink: 0;
  width: 44px;
}
.rv-insight__body { min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.rv-insight__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.rv-insight__hd h3 { font-family: @font-body; font-size: 16px; font-weight: 600; margin: 0; line-height: 1.4; }
.rv-insight p { font-size: 14px; line-height: 1.6; color: var(--gray-700); margin: 0; }
.rv-insight__refs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: var(--gray-500); }
.rv-insight__ref { cursor: pointer; }

.rv-dims {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}
.rv-dim {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 20px;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover { background: var(--gray-50); border-color: var(--gray-300); }
}
.rv-dim__label { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-dim__score { font-family: @font-body; font-size: 30px; font-weight: 600; margin-top: 6px; color: var(--gray-1000); }
.rv-dim__score span { font-size: 13px; font-weight: 400; color: var(--gray-500); }
.rv-dim__interpretation { font-size: 12px; line-height: 1.5; color: var(--gray-700); margin-top: 8px; margin-bottom: 6px; }
.rv-dim__track { margin-top: 12px; height: 4px; background: var(--gray-200); border-radius: 2px; overflow: hidden; }
.rv-dim__fill { height: 100%; background: var(--main-500); transition: width 0.6s ease; border-radius: 2px; }

.rv-expr {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.rv-expr__card {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 20px;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover { background: var(--gray-50); border-color: var(--gray-300); }
}
.rv-expr__hd { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--gray-600); }
.rv-expr__score { font-family: @font-body; font-size: 28px; font-weight: 600; margin-top: 10px; color: var(--gray-1000); }
.rv-expr__val { font-size: 14px; color: var(--gray-700); margin-top: 8px; }
.rv-expr__detail { font-size: 13px; color: var(--gray-600); margin-top: 6px; line-height: 1.6; }

.rv-questions { display: flex; flex-direction: column; gap: 12px; }
.rv-q {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 24px;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover { background: var(--gray-50); border-color: var(--main-300); }
}
.rv-q__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.rv-q__idx { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-q__hd h4 { font-family: @font-body; font-size: 15px; font-weight: 600; margin: 4px 0 0; line-height: 1.4; }
.rv-q__badges { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }
.rv-q__meta { display: flex; gap: 12px; font-size: 12px; color: var(--gray-500); margin-top: 12px; }
.rv-q__answer { margin-top: 16px; }
.rv-q__answer-label { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-q__answer p { font-size: 14px; line-height: 1.6; color: var(--gray-700); margin: 6px 0 0; }
.rv-q__kw { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.rv-q__cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.rv-q__cols > div { background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: 6px; padding: 16px; }
.rv-q__col-label { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-q__cols ul { margin: 8px 0 0; padding-left: 16px; font-size: 13px; line-height: 1.6; color: var(--gray-700); }
.rv-q__cols li + li { margin-top: 4px; }
.rv-q__na { font-size: 13px; color: var(--gray-500); margin: 6px 0 0; }

.rv-coding {
  padding: 20px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--gray-0);
  display: flex; flex-direction: column; gap: 10px;
  transition: border-color 0.2s ease;
  &:hover { border-color: var(--gray-300); }
}
.rv-coding__row { display: flex; justify-content: space-between; align-items: center; font-size: 14px; color: var(--gray-700); }
.rv-coding__row span:first-child { color: var(--gray-500); font-size: 13px; }

.rv-report-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}
.rv-report-stat {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 20px;
  transition: background 0.2s ease, border-color 0.2s ease;
  &:hover { background: var(--gray-50); border-color: var(--gray-300); }
  &--score { background: var(--main-50); border-color: var(--main-200); }
}
.rv-report-stat__label { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-report-stat__num { font-family: @font-body; font-size: 36px; font-weight: 600; line-height: 1; display: block; margin-top: 8px; color: var(--gray-1000); }
.rv-report-stat__num--sm { font-size: 22px; }
.rv-report-stat__note { font-size: 13px; color: var(--gray-600); margin-top: 8px; display: block; }

.rv-report-body { display: grid; grid-template-columns: 1.5fr 1fr; gap: 20px; align-items: start; margin-top: 28px; }
.rv-report-main, .rv-report-side { display: flex; flex-direction: column; gap: 16px; }
.rv-report-panel {
  padding: 24px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--gray-0);
  transition: border-color 0.2s ease;
  &:hover { border-color: var(--gray-300); }
}
.rv-report-panel h3 { font-family: @font-body; font-size: 16px; font-weight: 600; margin: 0 0 14px; }
.rv-report-panel--side { background: var(--gray-50); border-color: var(--gray-200); }

.rv-report-qs { display: flex; flex-direction: column; gap: 12px; }
.rv-report-q {
  padding: 16px;
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  background: var(--gray-50);
  transition: border-color 0.2s ease;
  &:hover { border-color: var(--main-300); }
}
.rv-report-q__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.rv-report-q__idx { font-size: 11px; color: var(--gray-500); letter-spacing: 0.04em; }
.rv-report-q h4 { font-family: @font-body; font-size: 14px; font-weight: 600; margin: 4px 0 0; line-height: 1.4; }
.rv-report-q p { font-size: 14px; line-height: 1.6; color: var(--gray-700); margin-top: 12px; }
.rv-report-q__focus {
  font-size: 13px;
  color: var(--main-700);
  margin-top: 10px;
  padding: 10px 14px;
  background: var(--main-50);
  border: 1px solid var(--main-200);
  border-radius: 4px;
}

.rv-report-dim { margin-bottom: 14px; }
.rv-report-dim__hd { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 6px; color: var(--gray-1000); }
.rv-report-dim__val { font-weight: 600; }
.rv-report-dim__bar { height: 4px; background: var(--gray-200); border-radius: 2px; margin-bottom: 6px; overflow: hidden; }
.rv-report-dim__desc { font-size: 12px; line-height: 1.5; color: var(--gray-600); }
.rv-report-list { margin: 0; padding-left: 16px; font-size: 14px; line-height: 1.6; color: var(--gray-700); li + li { margin-top: 6px; } }
.rv-empty { font-size: 14px; color: var(--gray-500); text-align: center; padding: 40px 0; }

/* === Next-steps learning loop (task 14) === */
.rv-nextsteps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.rv-nextstep {
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rv-nextstep__hd {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  h3 { margin: 0; font-size: 16px; color: var(--gray-1000); line-height: 1.4; }
}
.rv-nextstep__reason {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-600);
  flex: 1;
}
.rv-nextstep__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.rv-btn--sm { padding: 6px 14px; font-size: 12px; }
.rv-btn--print { display: inline-flex; align-items: center; gap: 4px; }

@media (max-width: 768px) {
  .rv-root { padding: 32px 20px 64px; }
  .rv-hero { grid-template-columns: 1fr; gap: 32px; }
  .rv-hero__title { font-size: 24px; }
  .rv-hero__score-ring { width: 150px; height: 150px; }
  .rv-hero__score-num { font-size: 40px; }
  .rv-takeaways { grid-template-columns: 1fr; }
  .rv-dims { grid-template-columns: repeat(2, 1fr); }
  .rv-report-body { grid-template-columns: 1fr; }
  .rv-q__cols { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .rv-root { padding: 24px 16px 48px; }
  .rv-hero__title { font-size: 22px; }
  .rv-dims { grid-template-columns: 1fr; }
  .rv-report-stats { grid-template-columns: 1fr; }
  .rv-hero__actions { flex-direction: column; }
}

/* === PDF export === */
/* Hides the app shell, sticky nav, and interactive buttons so the printed
   copy is a self-contained report. Layouts collapse to single-column for
   reliable pagination, and dim-bars are forced to print via color-adjust. */
@media print {
  :global(body), :global(html) { background: #fff !important; }
  /* Hide the project's actual app shell: `.app-layout > .header` + `.nav` +
     legacy ant-design candidates kept as a safety net. */
  :global(.header), :global(.app-layout > .header),
  :global(.nav), :global(.app-layout > .nav),
  :global(.app-sider), :global(.ant-layout-sider),
  :global(.ant-back-top),
  :global(.ant-message), :global(.ant-modal-mask), :global(.ant-modal-wrap) {
    display: none !important;
  }
  :global(.app-router-view), :global(.app-layout), :global(main) {
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
    width: 100% !important;
  }
  .rv-root {
    max-width: 100% !important;
    padding: 24px 16px !important;
    background: #fff !important;
    color: #000 !important;
    page-break-inside: auto;
  }
  .rv-nav, .rv-hero__actions, .rv-block__more, .rv-insight__refs,
  .rv-btn, button, .rv-incomplete-banner { display: none !important; }
  .rv-hero { grid-template-columns: 2fr 1fr !important; gap: 24px !important; page-break-after: avoid; }
  .rv-hero__title { font-size: 22px !important; }
  .rv-hero__source-chip { background: #f5f5f5 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .rv-takeaways { grid-template-columns: repeat(3, 1fr) !important; page-break-inside: avoid; }
  .rv-block { page-break-inside: auto; page-break-before: auto; }
  .rv-block__title, .rv-q, .rv-insight, .rv-report-panel { page-break-inside: avoid; }
  .rv-q { break-inside: avoid; }
  .rv-report-body { grid-template-columns: 1fr !important; }
  .rv-dim__fill, .rv-report-dim__bar > div {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  .ant-tag { border: 1px solid #ccc !important; background: #f8f8f8 !important; color: #333 !important; }
  a { color: inherit !important; text-decoration: none !important; }
  /* Force visibility of any IntersectionObserver-gated reveals */
  .is-visible, [class*="reveal"], [class*="rv-"] {
    opacity: 1 !important;
    transform: none !important;
    transition: none !important;
  }
}
</style>
