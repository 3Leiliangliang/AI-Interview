<template>
  <div class="rr-root">
    <header class="rr-hd">
      <div>
        <h1 class="rr-hd__title">你的面试成长轨迹</h1>
        <p class="rr-hd__sub">每一次模拟面试都在积累数据。这里记录了你从第一场到最近一场的全部表现，以及系统为你生成的长期提升建议。</p>
      </div>
      <div class="rr-hd__actions">
        <a-select v-if="userStore.isAdmin" v-model:value="selectedUserId" class="rr-user-pick" :options="userOptions" :loading="usersLoading" placeholder="选择学生" show-search :filter-option="filterUserOption" />
        <button class="rr-btn rr-btn--secondary" :disabled="loading" @click="loadHistory"><SyncOutlined /> 刷新</button>
      </div>
    </header>

    <!-- Stats — with meaning -->
    <div ref="statsEl" class="rr-stats reveal">
      <div class="rr-stat">
        <span class="rr-stat__num">{{ records.length }}</span>
        <span class="rr-stat__label">累计面试次数</span>
        <span class="rr-stat__hint">{{ records.length >= 5 ? '已有足够样本观察趋势' : records.length >= 2 ? '再多几轮，趋势会更清晰' : '完成第一次面试后在这里看数据' }}</span>
      </div>
      <div class="rr-stat">
        <span class="rr-stat__num">{{ historyCompletedCount }}</span>
        <span class="rr-stat__label">已完成并生成报告</span>
        <span class="rr-stat__hint">{{ historyCompletedCount ? '点击「查看报告」回看任意一轮的详细评估' : '需要生成报告才能计入成长曲线' }}</span>
      </div>
      <div class="rr-stat">
        <span class="rr-stat__num rr-stat__num--sm">{{ targetUserLabel }}</span>
        <span class="rr-stat__label">当前查看的候选人</span>
        <span class="rr-stat__hint">{{ records.length < 3 ? '数据不足以判断重点维度（至少需要 3 次面试）' : (topWeaknessDimensions.length ? `最需要关注的维度：${topWeaknessDimensions[0].label}` : '积累更多面试数据后会显示趋势分析') }}</span>
      </div>
    </div>

    <!-- Growth Chart -->
    <section ref="chartCardEl" class="rr-card reveal">
      <div class="rr-card__hd">
        <div>
          <span class="rr-card__kicker">趋势</span>
          <h2 class="rr-card__title">各维度能力变化</h2>
          <p class="rr-card__sub">每条线代表一个评估维度。线往上走，说明你在进步。{{ chartCategories.length >= 3 ? '看起来你已经积累了不少数据，趋势开始有意义了。' : '再多积累几轮面试，这里的曲线会越来越有参考价值。' }}</p>
        </div>
      </div>
      <div v-if="loading" class="rr-card__state"><a-spin /></div>
      <div v-else-if="!chartCategories.length" class="rr-card__state">
        <div class="rr-card__empty"><span class="rr-card__empty-icon">—</span><p>还没有足够的数据来绘制成长曲线。</p><p class="rr-card__empty-hint">完成至少两轮面试并获得评分后，这里会自动显示你的能力变化趋势。通常 3-5 轮后趋势会变得清晰。</p></div>
      </div>
      <div v-else ref="chartRef" class="rr-chart"></div>
    </section>

    <!-- Personalized Path -->
    <section ref="pathCardEl" class="rr-card reveal">
      <div class="rr-card__hd">
        <div>
          <span class="rr-card__kicker">长期提升</span>
          <h2 class="rr-card__title">你的专属提升路线图</h2>
          <p class="rr-card__sub">不是泛泛的"多练习"，而是基于你最近几次面试的实际表现，生成的具体、可执行的提升计划。</p>
        </div>
        <div class="rr-card__tags">
          <a-tag v-if="personalizedPath.source_round_count" color="purple">基于最近 {{ personalizedPath.source_round_count }} 轮</a-tag>
          <a-tag v-if="personalizedPath.summary?.top_priority_label" color="processing">当前重点：{{ personalizedPath.summary.top_priority_label }}</a-tag>
        </div>
      </div>
      <div v-if="loading" class="rr-card__state"><a-spin /></div>
      <div v-else-if="!hasPersonalizedPathContent" class="rr-card__state">
        <div class="rr-card__empty"><span class="rr-card__empty-icon">—</span><p>还没有足够的数据来生成个性化路线图。</p><p class="rr-card__empty-hint">一般来说，完成 2-3 轮面试并生成报告后，系统就能分析出你的薄弱环节并给出针对性建议。继续加油，每一次练习都在积累数据。</p></div>
      </div>
      <div v-else class="rr-card__body">
        <a-alert v-if="shouldHighlightPersonalizedPath" type="success" show-icon class="rr-alert" message="你的路线图刚刚更新了" :description="`基于最近 ${personalizedPath.source_round_count} 轮面试的最新数据，你的提升建议已经刷新。下滑查看具体要怎么执行。`" />

        <div class="rr-stage">
          <div><span class="rr-stage__label">你目前所处的阶段</span><div class="rr-stage__name">{{ personalizedPath.summary?.stage_label || '数据积累中' }}</div></div>
          <p class="rr-stage__msg">{{ personalizedPath.summary?.message || '完成更多模拟面试后，系统会自动为你生成长期的、循序渐进的提升路线。' }}</p>
          <div class="rr-stage__stats">
            <div v-for="item in personalizedStats" :key="item.label" class="rr-stage__stat"><span class="rr-stage__stat-num">{{ item.value }}</span><span class="rr-stage__stat-label">{{ item.label }}</span></div>
          </div>
        </div>

        <div v-if="personalizedPath.action_plan?.steps?.length" class="rr-section">
          <h3 class="rr-section__title">三步走：从补知识到回测验证</h3>
          <p class="rr-section__desc">这是一个完整的闭环——不是一次性学完就结束，而是学→练→测→再学的循环。每一步都有明确的完成标准，让你知道什么时候可以进入下一步。</p>
          <div class="rr-loop">
            <div class="rr-loop__steps">
              <article v-for="(step, index) in personalizedPath.action_plan.steps" :key="`${step.step_type}-${step.title}`" class="rr-loop__step">
                <span class="rr-loop__num">{{ String(index + 1).padStart(2, '0') }}</span>
                <div>
                  <div class="rr-loop__step-hd"><span>{{ getActionStepLabel(step.step_type) }}</span><span class="rr-loop__step-time">预计 {{ step.estimated_minutes }} 分钟</span></div>
                  <div class="rr-loop__step-title">{{ step.title }}</div>
                  <div class="rr-loop__step-obj">{{ step.objective }}</div>
                  <div class="rr-loop__step-sig">✅ 完成标准：{{ step.success_signal }}</div>
                </div>
              </article>
            </div>
            <div class="rr-loop__vis">
              <div class="rr-loop__vis-hd"><div><span class="rr-loop__vis-kicker">行动关系</span><div class="rr-loop__vis-title">学 → 练 → 回测</div><p class="rr-loop__vis-hint">先补齐关键知识点，再通过定向练习巩固，最后回到模拟面试验证是否真的有进步。</p></div><a-tag color="processing">闭环执行</a-tag></div>
              <svg class="rr-loop__svg" viewBox="0 0 320 220" aria-hidden="true"><defs><marker id="rrLoopArr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#4f9fec" fill-opacity="0.8"/></marker></defs><path d="M96 66 C150 20, 242 28, 250 78" stroke="#4f9fec" stroke-opacity="0.6" stroke-width="3" stroke-linecap="round" fill="none" marker-end="url(#rrLoopArr)"/><path d="M256 90 C274 146, 206 198, 154 176" stroke="#4f9fec" stroke-opacity="0.6" stroke-width="3" stroke-linecap="round" fill="none" marker-end="url(#rrLoopArr)"/><path d="M144 170 C90 192, 52 130, 80 84" stroke="#4f9fec" stroke-opacity="0.6" stroke-width="3" stroke-linecap="round" fill="none" marker-end="url(#rrLoopArr)"/><g v-for="node in actionLoopNodes" :key="node.key"><circle :cx="node.x" :cy="node.y" r="24" :fill="node.fill" /><circle :cx="node.x" :cy="node.y" r="29" :stroke="node.stroke" stroke-width="1.5" fill="transparent" opacity="0.3" /><text :x="node.x" :y="node.y + 4" text-anchor="middle" class="rr-loop__svg-tok">{{ node.token }}</text></g></svg>
              <div class="rr-loop__nodes"><div v-for="node in actionLoopNodes" :key="`${node.key}-meta`" class="rr-loop__node"><div class="rr-loop__node-top"><span class="rr-loop__node-badge" :style="{ background: node.fill, color: node.badgeColor }">{{ node.token }}</span><span>{{ node.label }}</span></div><div class="rr-loop__node-meta">{{ node.minutes }} 分钟 · {{ node.title }}</div></div></div>
            </div>
            <div v-if="personalizedStrengths.length" class="rr-strength-strip"><span class="rr-strength-strip__title">🎯 这几项继续保持就好</span><div class="rr-strength-strip__list"><span v-for="s in personalizedStrengths" :key="s" class="rr-strength-strip__item">{{ s }}</span></div></div>
          </div>
        </div>

        <div v-if="personalizedPath.weaknesses?.length" class="rr-section">
          <h3 class="rr-section__title">你最需要优先提升的方面</h3>
          <p class="rr-section__desc">不是所有维度都要同时补。下面这些是在你最近几轮面试里反复被扣分的点——先把它们提上来，整体分数会有明显变化。右边也列出了你相对稳定的优势，继续保留。</p>
          <div class="rr-contrast">
            <div class="rr-contrast__col"><div class="rr-contrast__col-label">近期反复低分</div><div v-for="item in topWeaknessDimensions" :key="item.dimension_key" class="rr-contrast__item"><div class="rr-contrast__item-hd"><span>{{ item.label }}</span><span>{{ item.average_score }} 分</span></div><div class="rr-contrast__bar"><div class="rr-contrast__fill rr-contrast__fill--warn" :style="{ width: `${item.average_score}%` }" /></div><div class="rr-contrast__item-meta">在最近几轮中 {{ item.low_score_count }} 次低于预期</div></div></div>
            <div class="rr-contrast__center"><span class="rr-contrast__center-kicker">能力落差</span><div class="rr-contrast__center-title">{{ weaknessGapSummary.title }}</div><div class="rr-contrast__center-val">{{ weaknessGapSummary.gapText }}</div><p class="rr-contrast__center-desc">{{ weaknessGapSummary.description }}</p></div>
            <div class="rr-contrast__col"><div class="rr-contrast__col-label">你可以依赖的优势</div><div v-if="topStrengthDimensions.length"><div v-for="item in topStrengthDimensions" :key="item.dimension_key" class="rr-contrast__item"><div class="rr-contrast__item-hd"><span>{{ item.label }}</span><span>{{ item.average_score }} 分</span></div><div class="rr-contrast__bar"><div class="rr-contrast__fill rr-contrast__fill--good" :style="{ width: `${item.average_score}%` }" /></div><div class="rr-contrast__item-meta">最近几轮表现稳定</div></div></div><div v-else class="rr-contrast__empty">目前还没有足够的数据来区分稳定优势。多完成 2-3 轮面试后，系统会自动帮你识别。</div></div>
          </div>
          <div class="rr-detail"><div class="rr-detail__list"><div v-for="item in personalizedPath.weaknesses" :key="`${item.dimension_key}-${item.title}`" class="rr-detail__item"><div class="rr-detail__item-title">{{ item.title }}</div><div class="rr-detail__item-reason">{{ item.reason }}</div></div></div><div v-if="personalizedStrengths.length" class="rr-detail__str"><div class="rr-detail__str-title">继续发挥的优势</div><p class="rr-detail__str-desc">短板要补，但这些稳定的强项是你的底牌，后续面试中继续保持。</p><div class="rr-detail__str-list"><div v-for="s in personalizedStrengths" :key="`${s}-keep`" class="rr-detail__str-item">{{ s }}</div></div></div></div>
        </div>

        <div v-if="prioritizedResources.length" class="rr-section">
          <h3 class="rr-section__title">我们帮你挑了这些学习资源</h3>
          <p class="rr-section__desc">不是随便推荐的——每条资源都对应了你的薄弱环节。优先选标了「立即可学」的，它们是你现在最需要的。</p>
          <div class="rr-res-bar"><span class="rr-res-bar__label">建议从这里开始</span><div class="rr-res-bar__tags"><a-tag color="success">在本平台内即可学习 {{ primaryResources.length }} 个</a-tag><a-tag color="processing">来自外部 {{ externalResourceCount }} 个</a-tag></div></div>
          <div class="rr-res-grid"><article v-for="resource in primaryResources" :key="`${resource.source_ref || resource.title}-${resource.resource_type}`" class="rr-res-card"><div class="rr-res-card__hd"><div class="rr-res-card__title-wrap"><span class="rr-res-card__title">{{ resource.title }}</span><div class="rr-res-card__badges"><a-tag color="success">优先推荐</a-tag><a-tag :color="getResourceTagColor(resource.resource_type)">{{ getResourceTypeLabel(resource.resource_type) }}</a-tag></div></div></div><p class="rr-res-card__summary">{{ resource.summary }}</p><p v-if="resource.reason" class="rr-res-card__reason">为什么推荐：{{ resource.reason }}</p><div class="rr-res-card__ft"><div class="rr-res-card__srcs"><span v-if="resource.is_external && resource.provider">来自：{{ resource.provider }}</span><span v-if="resource.estimated_minutes">大约需要 {{ resource.estimated_minutes }} 分钟</span></div><button class="rr-btn rr-btn--sm" @click="triggerResourceAction(resource)">{{ getResourceActionLabel(resource) }}</button></div></article></div>
          <div v-if="supportingResources.length" class="rr-res-extra"><span class="rr-res-extra__title">有空可以看看这些</span><div class="rr-res-list"><article v-for="resource in supportingResources" :key="`${resource.source_ref || resource.title}-${resource.resource_type}`" class="rr-res-card"><div class="rr-res-card__hd"><div class="rr-res-card__title-wrap"><span class="rr-res-card__title">{{ resource.title }}</span><div class="rr-res-card__badges"><a-tag v-if="resource.is_external" color="processing">外部资源</a-tag><a-tag :color="getResourceTagColor(resource.resource_type)">{{ getResourceTypeLabel(resource.resource_type) }}</a-tag></div></div></div><p class="rr-res-card__summary">{{ resource.summary }}</p><p v-if="resource.reason" class="rr-res-card__reason">为什么推荐：{{ resource.reason }}</p><div class="rr-res-card__ft"><div class="rr-res-card__srcs"><span v-if="resource.is_external && resource.provider">来自：{{ resource.provider }}</span></div><button class="rr-btn rr-btn--sm rr-btn--secondary" @click="triggerResourceAction(resource)">{{ getResourceActionLabel(resource) }}</button></div></article></div></div>
        </div>

        <div v-if="personalizedPath.next_assessment_focus?.length" class="rr-section">
          <h3 class="rr-section__title">下次面试时特别注意这些</h3>
          <p class="rr-section__desc">不是每次面试都要面面俱到。带着这几个具体的关注点进入下一轮，比无目的地再练一次效果好得多。</p>
          <div class="rr-focus"><div v-for="item in personalizedPath.next_assessment_focus" :key="`${item.dimension_key}-${item.title}`" class="rr-focus__item"><div class="rr-focus__item-title">{{ item.title }}</div><div class="rr-focus__item-desc">重点关注：{{ item.focus }}</div></div></div>
        </div>

        <div v-if="personalizedPath.related_records?.length" class="rr-section">
          <h3 class="rr-section__title">这些面试是路线图的数据来源</h3>
          <p class="rr-section__desc">每次完成面试后，路线图会随着你的新数据自动更新。点击任意一条可回看当时的完整报告。</p>
          <div class="rr-related"><button v-for="item in personalizedPath.related_records" :key="item.thread_id" class="rr-related__item" @click="openInterviewResult(item)"><div class="rr-related__item-title">{{ item.title }}</div><div class="rr-related__item-meta">{{ item.position }} · {{ item.round }} · 最后更新 {{ formatDateTime(item.updated_at) }}</div></button></div>
        </div>
      </div>
    </section>

    <!-- Records list -->
    <section ref="recordsCardEl" class="rr-card reveal">
      <div class="rr-card__hd"><div><span class="rr-card__kicker">全部记录</span><h2 class="rr-card__title">每一次面试的档案</h2><p class="rr-card__sub">不论是否完成评分，你参加的每一场模拟面试都在这里。点击「查看报告」回看详细评估，或者「继续面试」接着上次的对话往下走。</p></div></div>
      <div v-if="loading" class="rr-card__state"><a-spin /></div>
      <div v-else-if="records.length === 0" class="rr-card__state">
        <div class="rr-card__empty"><span class="rr-card__empty-icon">—</span><p>你还没有参加过模拟面试。</p><p class="rr-card__empty-hint">去首页选择一个岗位和轮次，上传简历，然后开始你的第一场模拟面试。完成之后，记录和报告会出现在这里。</p></div>
      </div>
      <div v-else class="rr-card__body rr-records">
        <div v-for="record in records" :key="record.thread_id" class="rr-record" :class="{ 'is-completed': record.status === 'completed', 'is-active': record.status === 'in_progress', 'is-failed': record.status === 'failed' }">
          <div class="rr-record__main">
            <div class="rr-record__hd"><div><h3 class="rr-record__title">{{ record.title || '未命名面试' }}</h3><div class="rr-record__times"><span>最近更新：{{ formatDateTime(record.updated_at) }}</span><span>·</span><span>创建于 {{ formatDateTime(record.created_at) }}</span></div></div><div class="rr-record__badges"><a-tag class="rr-record__tag">{{ getInterviewModeLabel(record.interview_mode) }}</a-tag><a-tag class="rr-record__tag">{{ record.position }}</a-tag><a-tag class="rr-record__tag">{{ record.round }}</a-tag><span class="rr-record__status" :data-status="record.status">{{ getStatusLabel(record.status) }}</span></div></div>
            <div v-if="record.dimensions?.length" class="rr-record__dims"><div class="rr-record__score"><span class="rr-record__score-num">{{ formatOverallScore(record.overall_score) }}</span><span class="rr-record__score-label">综合评分</span></div><div class="rr-record__dim-grid"><div v-for="dim in record.dimensions" :key="dim.key" class="rr-record__dim"><div class="rr-record__dim-hd"><span>{{ dim.label }}</span><span>{{ formatDimensionScore(dim.score) }}</span></div><div class="rr-record__dim-bar"><div class="rr-record__dim-fill" :style="{ width: `${dim.score}%` }" /></div></div></div></div>
            <div class="rr-record__ft"><button class="rr-btn rr-btn--sm rr-btn--secondary" @click="continueInterview(record)"><PlayCircleOutlined /> 继续面试</button><button v-if="record.has_result" class="rr-btn rr-btn--sm" @click="openInterviewResult(record)"><FileSearchOutlined /> 查看报告</button></div>
          </div>
        </div>
      </div>
    </section>

    <InterviewKnowledgeLearnModal v-model:open="learningModalVisible" :resource="activeLearningResource" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { SyncOutlined, PlayCircleOutlined, FileSearchOutlined } from '@ant-design/icons-vue'
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
let observer = null

const statsEl = ref(null)
const chartCardEl = ref(null)
const pathCardEl = ref(null)
const recordsCardEl = ref(null)

const records = computed(() => historyPayload.value?.records || [])
const profile = computed(() => historyPayload.value?.profile || { top_weakness_dimensions: [], top_strength_dimensions: [], latest_focus: [], pending_practice_count: 0 })
const personalizedPath = computed(() => personalizedPathPayload.value?.personalized_path || { summary: { stage_label: '数据积累中', top_priority_dimension: '', top_priority_label: '', message: '完成更多模拟面试后，系统会自动生成长期提升路线。' }, weaknesses: [], recommended_resources: [], practice_tasks: [], next_assessment_focus: [], action_plan: null, strengths: [], source_round_count: 0, latest_updated_at: '', related_records: [] })
const targetUser = computed(() => historyPayload.value?.target_user || personalizedPathPayload.value?.target_user || null)
const chartCategories = computed(() => historyPayload.value?.chart?.categories || [])
const chartSeries = computed(() => historyPayload.value?.chart?.series || [])
const historyCompletedCount = computed(() => records.value.filter((r) => r.status === 'completed').length)
const hasPersonalizedPathContent = computed(() => Boolean(personalizedPath.value.weaknesses?.length || personalizedPath.value.action_plan?.steps?.length || personalizedPath.value.recommended_resources?.length || personalizedPath.value.next_assessment_focus?.length))
const shouldHighlightPersonalizedPath = computed(() => hasPersonalizedPathContent.value && Number(personalizedPath.value.source_round_count || 0) >= 2)
const personalizedStats = computed(() => [{ label: '分析轮次', value: personalizedPath.value.source_round_count || '--' }, { label: '待练习项', value: profile.value.pending_practice_count || '--' }, { label: '最近更新', value: personalizedPath.value.latest_updated_at ? formatDateTime(personalizedPath.value.latest_updated_at) : '--' }])
const targetUserLabel = computed(() => { const u = String(targetUser.value?.username || userStore.username || '').trim(); return u || '当前用户' })
const topWeaknessDimensions = computed(() => profile.value.top_weakness_dimensions || [])
const topStrengthDimensions = computed(() => { const wk = new Set((profile.value.top_weakness_dimensions || []).map((i) => i?.dimension_key).filter(Boolean)); return (profile.value.top_strength_dimensions || []).filter((i) => !wk.has(i?.dimension_key)) })
const personalizedStrengths = computed(() => (personalizedPath.value.strengths || []).filter(Boolean).slice(0, 3))
const prioritizedResources = computed(() => { return [...(personalizedPath.value.recommended_resources || [])].sort((l, r) => getResourcePriorityScore(r) - getResourcePriorityScore(l)) })
const primaryResources = computed(() => prioritizedResources.value.slice(0, 4))
const supportingResources = computed(() => prioritizedResources.value.slice(4))
const externalResourceCount = computed(() => prioritizedResources.value.filter((i) => Boolean(i?.is_external && String(i?.url || '').trim())).length)
const weaknessGapSummary = computed(() => { const w = topWeaknessDimensions.value[0]; const s = topStrengthDimensions.value[0]; if (!w && !s) return { title: '等待更多轮面试数据', gapText: '--', description: '完成至少 2 轮以上面试并生成报告后，这里会自动分析你的强弱项差距。' }; if (!w || !s) return { title: `${w?.label || s?.label || '核心能力'}需要持续观察`, gapText: `${w?.average_score || s?.average_score || '--'} 分`, description: '当前样本还不够，先继续积累几轮数据。' }; const gap = Math.max(0, Number(s.average_score || 0) - Number(w.average_score || 0)); return { title: `${w.label} 与 ${s.label} 差了 ${gap} 分`, gapText: `${gap} 分差距`, description: `你的${s.label}已经比较稳定了。现在最值得投入时间的是把${w.label}提上来——补短板比拉长板见效更快。` } })
const actionLoopNodes = computed(() => { const fc = { learn: { fill: '#edf7ff', stroke: '#4f9fec', badgeColor: '#143254' }, practice: { fill: '#f5f7f7', stroke: '#697070', badgeColor: '#151616' }, recheck: { fill: '#def0ff', stroke: '#2765a3', badgeColor: '#091a30' } }; const pos = { learn: { x: 82, y: 76 }, practice: { x: 248, y: 84 }, recheck: { x: 160, y: 168 } }; return (personalizedPath.value.action_plan?.steps || []).map((step, index) => { const t = String(step?.step_type || '').trim(); const token = String(index + 1).padStart(2, '0'); const c = fc[t] || fc.learn; const p = pos[t] || { x: 70 + index * 80, y: 90 + index * 12 }; return { key: `${t}-${step.title}`, token, label: getActionStepShortLabel(t), title: step.title, minutes: step.estimated_minutes || '--', fill: c.fill, stroke: c.stroke, badgeColor: c.badgeColor, x: p.x, y: p.y } }) })

const decodeHtmlEntities = (value) => { const text = String(value || ''); if (typeof window === 'undefined' || !text.includes('&')) return text; const doc = new DOMParser().parseFromString(text, 'text/html'); return doc.body.textContent || '' }
const getStatusLabel = (s) => ({ in_progress: '进行中', generating: '报告生成中', completed: '已完成', failed: '生成失败' })[s] || s || '进行中'
const getInterviewModeLabel = (m) => String(m || '').trim() === 'voice' ? '语音面试' : '文本面试'
const formatOverallScore = (s) => (typeof s === 'number' && Number.isFinite(s)) ? `${Math.round(s)}` : '--'
const formatDimensionScore = (s) => (typeof s === 'number' && Number.isFinite(s)) ? s : '--'
const filterUserOption = (input, option) => String(option?.label || '').toLowerCase().includes(String(input || '').toLowerCase())
const resolveLearningLocator = (source) => { const loc = source?.locator || {}; const dbId = String(loc.db_id || source?.db_id || '').trim(); const fileId = String(loc.file_id || source?.file_id || '').trim(); if (!dbId || !fileId) return null; return { db_id: dbId, file_id: fileId, chunk_id: String(loc.chunk_id || source?.chunk_id || '').trim() || undefined, chunk_index: loc.chunk_index !== undefined && loc.chunk_index !== null ? Number(loc.chunk_index) : source?.chunk_index !== undefined && source?.chunk_index !== null ? Number(source.chunk_index) : undefined, keyword: String(loc.keyword || '').trim() || undefined, query_text: String(loc.query_text || '').trim() || undefined } }
const actionStepLabelMap = { learn: '第一步 · 补知识', practice: '第二步 · 做练习', recheck: '第三步 · 回测验证' }
const getActionStepLabel = (t) => actionStepLabelMap[String(t || '').trim()] || t || '行动步骤'
const getActionStepShortLabel = (t) => ({ learn: '补知识', practice: '做练习', recheck: '回测验证' })[String(t || '').trim()] || '行动步骤'
const getResourceTypeLabel = (t) => ({ knowledge: '知识文章', interview_question: '面试真题', communication: '表达训练', article: '博客文章', video: '教学视频', case: '案例拆解' })[t] || t || '学习资源'
const getResourceTagColor = (t) => ({ knowledge: 'blue', interview_question: 'gold', communication: 'green', article: 'cyan', video: 'orange', case: 'volcano' })[t] || 'default'
const canOpenLearningLocator = (r) => Boolean(resolveLearningLocator(r))
const canLearnResource = (r) => ['knowledge', 'communication'].includes(String(r?.resource_type || '').trim()) && canOpenLearningLocator(r)
const canPracticeResource = (r) => String(r?.resource_type || '').trim() === 'interview_question' && String(r?.problem_ref || '').trim()
const canOpenExternalResource = (r) => Boolean(r?.is_external && /^https?:\/\//.test(String(r?.url || '').trim()))
const getResourcePriorityScore = (r) => { if (canOpenExternalResource(r)) return 3; if (canPracticeResource(r)) return 2; if (canLearnResource(r)) return 1; return 0 }
const getResourceActionLabel = (r) => { if (canOpenExternalResource(r)) return '打开链接'; if (canPracticeResource(r)) return '开始练习'; if (canLearnResource(r)) return '开始学习'; return '查看' }
const triggerResourceAction = (r) => { if (canLearnResource(r)) { activeLearningResource.value = { ...r, locator: resolveLearningLocator(r) }; learningModalVisible.value = true; return } if (canPracticeResource(r)) { const pr = String(r?.problem_ref || '').trim(); if (pr) router.push({ name: 'PracticeProblemPage', params: { problem_ref: pr } }); return } if (canOpenExternalResource(r)) { window.open(String(r?.url || '').trim(), '_blank', 'noopener,noreferrer') } }

const setupObserver = () => { const els = [statsEl.value, chartCardEl.value, pathCardEl.value, recordsCardEl.value].filter(Boolean); if (!els.length) return; if (observer) observer.disconnect(); observer = new IntersectionObserver((entries) => { entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-visible'); observer.unobserve(e.target) } }) }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' }); els.forEach(el => observer.observe(el)) }
const loadUsers = async () => { if (!userStore.isAdmin) return; usersLoading.value = true; try { const users = await userStore.getUsers(); const cur = Number(userStore.userId); userOptions.value = (users || []).filter((i) => i.role === 'user' || i.id === cur).map((i) => ({ label: i.username, value: i.id })) } catch (e) { message.error(e.message) } finally { usersLoading.value = false } }
const loadHistory = async () => { loading.value = true; try { const uid = userStore.isAdmin ? selectedUserId.value : userStore.userId; const [h, pp] = await Promise.all([interviewHistoryApi.getHistory({ userId: uid }), interviewHistoryApi.getPersonalizedPath({ userId: uid })]); const rawRecords = (h?.records || []).map((r) => ({ ...r, title: decodeHtmlEntities(r?.title), position: decodeHtmlEntities(r?.position), round: decodeHtmlEntities(r?.round) })); const nr = (pp?.personalized_path?.recommended_resources || []).map((i) => ({ ...i, title: decodeHtmlEntities(i?.title), summary: decodeHtmlEntities(i?.summary), reason: decodeHtmlEntities(i?.reason), provider: decodeHtmlEntities(i?.provider) })); historyPayload.value = { ...h, records: rawRecords }; personalizedPathPayload.value = { ...(pp || {}), personalized_path: { ...(pp?.personalized_path || {}), recommended_resources: nr } } } catch (e) { message.error(e.message) } finally { loading.value = false; await nextTick(); setupObserver(); if (chartCategories.value.length) await renderChart() } }
const buildChartOption = () => { const cs = typeof window !== 'undefined' ? getComputedStyle(document.documentElement) : null; const read = (name, fb) => { const v = cs ? cs.getPropertyValue(name).trim() : ''; return v || fb }; const cMain = read('--main-500', '#4f9fec'); const cInk = read('--gray-1000', '#151616'); const cText = read('--gray-700', '#4c4d4d'); const cMuted = read('--gray-500', '#979999'); const cBorder = read('--gray-200', '#e4e6e6'); const cSplit = read('--gray-150', '#eef0f0'); const cBg = read('--main-0', '#ffffff'); return { color: [cMain, read('--color-success-500', '#52c41a'), read('--color-warning-500', '#faad14'), read('--main-700', '#2765a3'), read('--color-accent-500', '#13c2c2')], tooltip: { trigger: 'axis', backgroundColor: cBg, borderColor: cBorder, textStyle: { color: cInk, fontSize: 13 }, extraCssText: 'border-radius: 4px;' }, legend: { top: 0, textStyle: { color: cText } }, grid: { left: 20, right: 40, top: 50, bottom: 20, containLabel: true }, xAxis: { type: 'category', boundaryGap: false, data: chartCategories.value.map((i) => { const p = parseToShanghai(i); return p ? p.format('MM/DD HH:mm') : i }), axisLine: { lineStyle: { color: cBorder } }, axisTick: { show: false }, axisLabel: { color: cMuted, fontSize: 11 } }, yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: cSplit } }, axisLabel: { color: cMuted, fontSize: 11 } }, series: chartSeries.value.map((i) => ({ name: i.label, type: 'line', smooth: true, showSymbol: true, connectNulls: false, symbolSize: 5, lineStyle: { width: 2 }, data: i.data || [] })) } }
const renderChart = async () => { await nextTick(); if (!chartRef.value || !chartCategories.value.length) return; if (!chartInstance) chartInstance = echarts.init(chartRef.value); chartInstance.setOption(buildChartOption(), true) }
const handleResize = () => chartInstance?.resize()
const continueInterview = (r) => router.push({ name: r.interview_mode === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp', query: { threadId: r.thread_id, mode: r.interview_mode === 'voice' ? 'voice' : 'text', position: r.position, round: r.round } })
const openInterviewResult = (r) => router.push({ name: 'InterviewResultPage', query: { threadId: r.thread_id, position: r.position, round: r.round } })
watch(() => selectedUserId.value, async (v, old) => { if (!userSelectionReady.value) return; if (v === old) return; await loadHistory() })
watch(() => historyPayload.value?.chart, async () => { if (!chartCategories.value.length) { chartInstance?.dispose(); chartInstance = null; return }; await renderChart() }, { deep: true })
onMounted(async () => { selectedUserId.value = userStore.userId; if (userStore.isAdmin) await loadUsers(); userSelectionReady.value = true; await loadHistory(); window.addEventListener('resize', handleResize) })
onBeforeUnmount(() => { window.removeEventListener('resize', handleResize); chartInstance?.dispose(); chartInstance = null; if (observer) observer.disconnect() })
</script>

<style lang="less" scoped>
@font-body: system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;

.rr-root { min-height: 100vh; padding: 48px 48px 96px; background: var(--gray-50); max-width: 960px; margin: 0 auto; font-family: @font-body; color: var(--gray-1000); -webkit-font-smoothing: antialiased; display: flex; flex-direction: column; gap: 32px; position: relative; }
.rr-btn { border: none; border-radius: 4px; background: var(--main-500); color: var(--main-0); padding: 8px 18px; font-family: @font-body; font-size: 13px; font-weight: 500; cursor: pointer; transition: background 0.2s ease; display: inline-flex; align-items: center; gap: 6px; &:hover:not(:disabled) { background: var(--main-600); } &:disabled { opacity: 0.4; cursor: not-allowed; } }
.rr-btn--secondary { background: var(--main-0); color: var(--gray-1000); border: 1px solid var(--gray-200); &:hover:not(:disabled) { background: var(--gray-50); color: var(--main-600); border-color: var(--main-500); } }
.rr-btn--sm { padding: 6px 14px; font-size: 12px; }
.reveal { opacity: 0; transition: opacity 0.4s ease; &.is-visible { opacity: 1; } }
.rr-hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap; }
.rr-hd__title { font-size: 24px; font-weight: 600; margin: 0; color: var(--gray-1000); }
.rr-hd__sub { font-size: 14px; color: var(--gray-700); max-width: 520px; line-height: 1.6; margin: 6px 0 0; }
.rr-hd__actions { display: flex; gap: 12px; align-items: center; flex-shrink: 0; }
.rr-user-pick { min-width: 160px; }
.rr-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.rr-stat { padding: 20px; background: var(--main-0); border: 1px solid var(--gray-200); border-radius: 4px; transition: border-color 0.2s, background 0.2s; &:hover { background: var(--gray-25); border-color: var(--gray-300); } }
.rr-stat__num { font-size: 28px; font-weight: 600; line-height: 1; color: var(--gray-1000); display: block; }
.rr-stat__num--sm { font-size: 18px; }
.rr-stat__label { font-size: 12px; color: var(--gray-600); display: block; margin-top: 8px; }
.rr-stat__hint { font-size: 11px; color: var(--gray-500); line-height: 1.5; display: block; margin-top: 6px; }

.rr-card { border: 1px solid var(--gray-200); border-radius: 4px; background: var(--main-0); box-shadow: 0 1px 3px var(--shadow-1); }
.rr-card__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 20px 24px 0; flex-wrap: wrap; }
.rr-card__kicker { font-size: 11px; color: var(--gray-500); }
.rr-card__title { font-size: 18px; font-weight: 600; margin: 4px 0 0; color: var(--gray-1000); }
.rr-card__sub { font-size: 13px; color: var(--gray-700); margin: 6px 0 0; line-height: 1.6; }
.rr-card__tags { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }
.rr-card__body { padding: 20px 24px 24px; display: flex; flex-direction: column; gap: 20px; }
.rr-card__state { min-height: 200px; display: flex; align-items: center; justify-content: center; padding: 32px 24px; }
.rr-card__empty { text-align: center; }
.rr-card__empty-icon { font-size: 28px; color: var(--gray-300); display: block; margin-bottom: 8px; }
.rr-card__empty p { font-size: 14px; color: var(--gray-700); margin: 0 0 6px; }
.rr-card__empty-hint { font-size: 12px; color: var(--gray-500); line-height: 1.6; max-width: 440px; margin: 0 auto; }
.rr-empty { font-size: 13px; color: var(--gray-500); text-align: center; }
.rr-alert { margin-bottom: 4px; }
.rr-chart { width: 100%; height: 320px; padding: 8px 16px 0; }

.rr-stage { padding: 20px; border: 1px solid var(--gray-200); border-radius: 4px; background: var(--main-30); }
.rr-stage__label { font-size: 11px; color: var(--gray-500); }
.rr-stage__name { font-size: 18px; font-weight: 600; color: var(--main-600); margin-top: 4px; }
.rr-stage__msg { font-size: 13px; color: var(--gray-700); margin: 10px 0 0; line-height: 1.6; }
.rr-stage__stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 16px; }
.rr-stage__stat { background: var(--main-0); padding: 12px 14px; border: 1px solid var(--gray-200); border-radius: 4px; transition: background 0.2s; &:hover { background: var(--gray-25); } }
.rr-stage__stat-num { font-size: 18px; font-weight: 600; display: block; color: var(--gray-1000); }
.rr-stage__stat-label { font-size: 11px; color: var(--gray-500); display: block; margin-top: 4px; }

.rr-section { margin-top: 4px; }
.rr-section__title { font-size: 16px; font-weight: 600; margin: 0 0 6px; color: var(--gray-1000); }
.rr-section__desc { font-size: 13px; color: var(--gray-700); line-height: 1.6; margin: 0 0 16px; }
.rr-loop { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; align-items: start; }
.rr-loop__steps { display: flex; flex-direction: column; gap: 8px; }
.rr-loop__step { background: var(--main-0); padding: 14px 16px; border: 1px solid var(--gray-200); border-radius: 4px; display: flex; gap: 12px; transition: background 0.2s, border-color 0.2s; &:hover { background: var(--gray-25); border-color: var(--gray-300); } }
.rr-loop__num { font-size: 16px; font-weight: 600; color: var(--gray-400); flex-shrink: 0; width: 28px; line-height: 1.2; }
.rr-loop__step-hd { display: flex; justify-content: space-between; font-size: 11px; color: var(--gray-500); }
.rr-loop__step-time { font-size: 11px; }
.rr-loop__step-title { font-size: 14px; font-weight: 500; margin-top: 4px; color: var(--gray-1000); }
.rr-loop__step-obj { font-size: 12px; color: var(--gray-700); line-height: 1.6; margin-top: 4px; }
.rr-loop__step-sig { font-size: 11px; color: var(--gray-600); padding-top: 8px; margin-top: 8px; border-top: 1px solid var(--gray-200); }
.rr-loop__vis { padding: 16px; border: 1px solid var(--gray-200); border-radius: 4px; display: flex; flex-direction: column; gap: 12px; background: var(--main-30); }
.rr-loop__vis-hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.rr-loop__vis-kicker { font-size: 11px; color: var(--gray-500); }
.rr-loop__vis-title { font-size: 16px; font-weight: 600; margin-top: 4px; color: var(--gray-1000); }
.rr-loop__vis-hint { font-size: 12px; color: var(--gray-700); margin: 6px 0 0; line-height: 1.6; max-width: 280px; }
.rr-loop__svg { width: 100%; height: 180px; }
.rr-loop__svg-tok { font-family: @font-body; font-size: 12px; font-weight: 600; fill: var(--gray-1000); }
.rr-loop__nodes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.rr-loop__node { padding: 10px; border: 1px solid var(--gray-200); border-radius: 4px; transition: border-color 0.2s; &:hover { border-color: var(--main-400); } }
.rr-loop__node-top { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 500; color: var(--gray-1000); }
.rr-loop__node-badge { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; border-radius: 4px; }
.rr-loop__node-meta { font-size: 11px; color: var(--gray-500); margin-top: 4px; }
.rr-strength-strip { grid-column: 1 / -1; padding: 12px 16px; border: 1px solid var(--gray-200); border-radius: 4px; }
.rr-strength-strip__title { font-size: 12px; font-weight: 500; color: var(--gray-1000); }
.rr-strength-strip__list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.rr-strength-strip__item { padding: 4px 10px; border: 1px solid var(--gray-200); border-radius: 4px; font-size: 12px; color: var(--gray-700); background: var(--gray-25); }

.rr-contrast { display: grid; grid-template-columns: 1fr 200px 1fr; gap: 16px; align-items: start; }
.rr-contrast__col-label { font-size: 11px; color: var(--gray-500); margin-bottom: 10px; }
.rr-contrast__col { display: flex; flex-direction: column; gap: 8px; }
.rr-contrast__item { padding: 12px; border: 1px solid var(--gray-200); border-radius: 4px; transition: border-color 0.2s, background 0.2s; &:hover { border-color: var(--main-400); background: var(--gray-25); } }
.rr-contrast__item-hd { display: flex; justify-content: space-between; font-size: 13px; font-weight: 500; color: var(--gray-1000); }
.rr-contrast__bar { margin-top: 10px; height: 4px; background: var(--gray-200); border-radius: 2px; overflow: hidden; }
.rr-contrast__fill { height: 100%; transition: width 1s cubic-bezier(0.16,1,0.3,1); }
.rr-contrast__fill--warn { background: var(--color-warning-500); }
.rr-contrast__fill--good { background: var(--color-success-500); }
.rr-contrast__item-meta { font-size: 11px; color: var(--gray-500); margin-top: 6px; }
.rr-contrast__center { padding: 20px 16px; text-align: center; border: 1px solid var(--gray-200); border-radius: 4px; background: var(--main-30); display: flex; flex-direction: column; justify-content: center; }
.rr-contrast__center-kicker { font-size: 11px; color: var(--gray-500); }
.rr-contrast__center-title { font-size: 15px; font-weight: 500; margin-top: 8px; line-height: 1.4; color: var(--gray-1000); }
.rr-contrast__center-val { font-size: 24px; font-weight: 600; color: var(--main-600); margin-top: 8px; }
.rr-contrast__center-desc { font-size: 12px; color: var(--gray-700); margin-top: 8px; line-height: 1.6; }
.rr-contrast__empty { padding: 12px; border: 1px solid var(--gray-200); border-radius: 4px; font-size: 12px; color: var(--gray-700); line-height: 1.6; }
.rr-detail { display: grid; grid-template-columns: 1.3fr 1fr; gap: 16px; margin-top: 16px; }
.rr-detail__list { display: flex; flex-direction: column; gap: 8px; }
.rr-detail__item { background: var(--main-0); border: 1px solid var(--gray-200); border-radius: 4px; padding: 12px 14px; transition: background 0.2s; &:hover { background: var(--gray-25); } }
.rr-detail__item-title { font-size: 14px; font-weight: 500; color: var(--gray-1000); }
.rr-detail__item-reason { font-size: 12px; color: var(--gray-700); margin-top: 4px; line-height: 1.6; }
.rr-detail__str { padding: 16px; border: 1px solid var(--gray-200); border-radius: 4px; background: var(--main-30); }
.rr-detail__str-title { font-size: 14px; font-weight: 500; color: var(--gray-1000); }
.rr-detail__str-desc { font-size: 12px; color: var(--gray-700); margin: 6px 0 0; line-height: 1.6; }
.rr-detail__str-list { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.rr-detail__str-item { padding: 8px 12px; border: 1px solid var(--gray-200); border-radius: 4px; font-size: 12px; color: var(--gray-700); line-height: 1.5; background: var(--main-0); }
.rr-res-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; border: 1px solid var(--gray-200); border-radius: 4px; margin-bottom: 12px; }
.rr-res-bar__label { font-size: 12px; font-weight: 500; color: var(--gray-1000); }
.rr-res-bar__tags { display: flex; gap: 8px; }
.rr-res-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.rr-res-card { background: var(--main-0); padding: 16px; border: 1px solid var(--gray-200); border-radius: 4px; transition: background 0.2s, border-color 0.2s; &:hover { background: var(--gray-25); border-color: var(--gray-300); } }
.rr-res-card__hd { margin-bottom: 8px; }
.rr-res-card__title-wrap { min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.rr-res-card__badges { display: flex; gap: 8px; flex-wrap: wrap; }
.rr-res-card__title { font-size: 15px; font-weight: 600; color: var(--gray-1000); }
.rr-res-card__summary { font-size: 13px; line-height: 1.6; color: var(--gray-700); margin: 0; }
.rr-res-card__reason { font-size: 12px; color: var(--gray-500); margin: 8px 0 0; }
.rr-res-card__ft { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; gap: 12px; }
.rr-res-card__srcs { display: flex; gap: 10px; font-size: 12px; color: var(--gray-500); }
.rr-res-extra { margin-top: 16px; }
.rr-res-extra__title { font-size: 13px; font-weight: 500; display: block; margin-bottom: 10px; color: var(--gray-1000); }
.rr-res-list { display: flex; flex-direction: column; gap: 8px; }
.rr-focus { display: flex; flex-direction: column; gap: 8px; }
.rr-focus__item { background: var(--main-0); padding: 12px 14px; border: 1px solid var(--gray-200); border-radius: 4px; transition: background 0.2s; &:hover { background: var(--gray-25); } }
.rr-focus__item-title { font-size: 13px; font-weight: 500; color: var(--gray-1000); }
.rr-focus__item-desc { font-size: 12px; color: var(--gray-700); margin-top: 4px; line-height: 1.6; }
.rr-related { display: flex; flex-direction: column; gap: 6px; }
.rr-related__item { display: block; width: 100%; text-align: left; padding: 12px 14px; border: 1px solid var(--gray-200); border-radius: 4px; background: var(--main-0); cursor: pointer; font-family: @font-body; transition: background 0.2s, border-color 0.2s; &:hover { background: var(--gray-25); border-color: var(--main-400); } }
.rr-related__item-title { font-size: 13px; font-weight: 500; color: var(--gray-1000); }
.rr-related__item-meta { font-size: 12px; color: var(--gray-500); margin-top: 4px; }
.rr-records { display: flex; flex-direction: column; gap: 10px; }
.rr-record { background: var(--main-0); border: 1px solid var(--gray-200); border-radius: 4px; transition: background 0.2s, border-color 0.2s; &:hover { background: var(--gray-25); border-color: var(--gray-300); } }
.rr-record__main { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
.rr-record__hd { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.rr-record__title { font-size: 16px; font-weight: 600; margin: 0; color: var(--gray-1000); }
.rr-record__times { display: flex; gap: 8px; font-size: 12px; color: var(--gray-500); margin-top: 4px; }
.rr-record__badges { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; align-items: center; }
.rr-record__tag { border: 1px solid var(--gray-200); background: var(--gray-25); color: var(--gray-700); border-radius: 4px; margin: 0; }
.rr-record__status { font-size: 11px; font-weight: 500; padding: 3px 8px; border: 1px solid var(--gray-200); border-radius: 4px; color: var(--gray-700); background: var(--gray-25); }
.rr-record__status[data-status="completed"] { color: var(--color-success-700); border-color: var(--color-success-500); background: var(--color-success-50); }
.rr-record__status[data-status="in_progress"] { color: var(--main-700); border-color: var(--main-500); background: var(--main-50); }
.rr-record__status[data-status="failed"] { color: var(--color-error-700); border-color: var(--color-error-500); background: var(--color-error-50); }
.rr-record__dims { display: flex; align-items: center; gap: 24px; padding: 16px; border: 1px solid var(--gray-200); border-radius: 4px; background: var(--gray-25); }
.rr-record__score { display: flex; flex-direction: column; align-items: center; min-width: 80px; text-align: center; }
.rr-record__score-num { font-size: 32px; font-weight: 600; color: var(--main-600); line-height: 1; }
.rr-record__score-label { font-size: 11px; color: var(--gray-500); margin-top: 4px; }
.rr-record__dim-grid { flex: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.rr-record__dim-hd { display: flex; justify-content: space-between; font-size: 12px; color: var(--gray-700); }
.rr-record__dim-bar { height: 4px; background: var(--gray-200); border-radius: 2px; margin-top: 6px; overflow: hidden; }
.rr-record__dim-fill { height: 100%; background: var(--main-500); transition: width 1s cubic-bezier(0.16,1,0.3,1); }
.rr-record__ft { display: flex; justify-content: flex-end; gap: 10px; }

@media (max-width: 1024px) { .rr-loop { grid-template-columns: 1fr; } .rr-contrast { grid-template-columns: 1fr; } .rr-detail { grid-template-columns: 1fr; } .rr-res-grid { grid-template-columns: 1fr; } .rr-stats { grid-template-columns: 1fr; } }
@media (max-width: 768px) { .rr-root { padding: 24px 20px 64px; } .rr-hd__title { font-size: 22px; } .rr-record__hd { flex-direction: column; } .rr-record__dims { flex-direction: column; } .rr-record__dim-grid { grid-template-columns: repeat(2, 1fr); } .rr-stage__stats { grid-template-columns: 1fr; } .rr-loop__nodes { grid-template-columns: 1fr; } }
</style>
