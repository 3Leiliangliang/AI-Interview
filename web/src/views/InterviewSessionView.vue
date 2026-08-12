<template>
  <div class="interview-session-view">
    <Transition name="coding-banner">
      <div v-if="codingReady" class="coding-ready-banner">
        <span class="coding-ready-banner__text">编程题已就绪，准备好后点击进入考核</span>
        <button class="coding-ready-banner__btn" @click="goToCodingWorkbench">进入编程考核</button>
        <button
          class="coding-ready-banner__close"
          type="button"
          aria-label="关闭编程考核提示"
          @click="dismissCodingBanner"
        >
          &times;
        </button>
      </div>
    </Transition>
    <header class="session-header">
      <div class="session-heading">
        <h1>{{ sessionTitle }}</h1>
        <p>{{ sessionSubtitle }}</p>
      </div>
      <div class="session-actions">
        <button
          class="session-button"
          :class="{ 'is-active': isVideoMode }"
          :disabled="isInitializing"
          @click="toggleVideoMode"
        >
          <LoaderCircle v-if="isInitializing" :size="16" class="loading-icon" />
          {{ isVideoMode ? '关闭分析' : '视频分析' }}
        </button>
        <button class="session-button" @click="handleShareChat">导出记录</button>
        <button class="session-button session-button--primary" @click="finishInterview">
          结束并生成报告
        </button>
      </div>
    </header>

    <div class="session-content">
      <main class="conversation-pane">
        <AgentChatComponent
          ref="chatComponentRef"
          :agent-id="interviewAgentId"
          :single-mode="true"
          :show-sidebar="false"
          :show-header="false"
          :show-agent-panel="false"
          conversation-variant="interview"
          :preferred-thread-id="threadId"
          :context-overrides="contextOverrides"
          @agent-state-change="handleAgentStateChange"
          @thread-change="handleThreadChange"
        >
          <template #input-actions-left>
            <button class="input-text-action" type="button" @click="switchToVoice">切到语音</button>
            <label class="input-text-action input-file-action">
              上传代码
              <input type="file" accept=".txt,.md" @change="handleCodeUpload" />
            </label>
          </template>
        </AgentChatComponent>
      </main>

      <aside class="context-rail">
        <section class="rail-section">
          <div class="rail-section__heading">
            <h2>本场进度</h2>
            <span>{{ progress.currentIndex + 1 }} / {{ progress.steps.length }} 阶段</span>
          </div>
          <div class="progress-track" aria-hidden="true">
            <span class="progress-track__done" :style="{ width: `${progressPercent}%` }"></span>
            <span class="progress-track__remaining"></span>
          </div>
          <ol class="progress-list">
            <li
              v-for="(step, index) in progress.steps"
              :key="`${index}-${step.label}`"
              :class="[`is-${step.status}`]"
            >
              <span class="progress-index">{{ index + 1 }}</span>
              <span class="progress-label">{{ step.label }}</span>
              <span v-if="step.status === 'pending'" class="progress-status">待提问</span>
            </li>
          </ol>
        </section>

        <section class="rail-section">
          <h2>本题考察点</h2>
          <div v-if="assessmentPoints.length" class="assessment-list">
            <div v-for="point in assessmentPoints" :key="point.label" class="assessment-row">
              <span>{{ point.label }}</span>
              <strong :class="{ 'is-covered': point.covered }">
                {{ point.covered ? '已覆盖' : '未提及' }}
              </strong>
            </div>
          </div>
          <p v-else class="rail-empty">当前 SSE 未提供 SEP 考察点，回答完成后将在报告中评估。</p>
        </section>

        <section class="rail-section">
          <h2>题目来源</h2>
          <div v-if="questionSource" class="source-block">
            <strong>{{ questionSource.name }}</strong>
            <span>{{ questionSource.path }}</span>
            <a
              v-if="questionSourceUrl"
              :href="questionSourceUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              查看知识点原文
            </a>
          </div>
          <p v-else class="rail-empty">当前会话未提供题库来源定位。</p>
        </section>

        <section class="rail-section">
          <h2>简历关联</h2>
          <blockquote v-if="resumeReference" class="resume-reference">
            {{ resumeReference.quote }}
            <footer>{{ resumeReference.source }}</footer>
          </blockquote>
          <p v-else class="rail-empty">当前会话未提供简历原文定位。</p>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { LoaderCircle } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import AgentChatComponent from '@/components/AgentChatComponent.vue'
import { threadApi } from '@/apis'
import { useAgentStore } from '@/stores/agent'
import { useVideoEventStream } from '@/composables/useVideoEventStream'
import { ChatExporter } from '@/utils/chatExporter'
import { handleChatError } from '@/utils/errorHandler'
import { formatInterviewElapsed, normalizeInterviewProgress } from '@/utils/interviewSession'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const DEFAULT_ROUND = '初试'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const chatComponentRef = ref(null)
const eventStream = useVideoEventStream()
const codingReady = ref(false)
const currentAgentState = ref(null)
const elapsedSeconds = ref(0)
let elapsedTimer = null

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const { isVideoMode, isInitializing } = eventStream

const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')
const selectedPosition = computed(
  () => String(route.query.position || '').trim() || DEFAULT_POSITION
)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const selectedResumeId = computed(() => {
  const raw = String(route.query.resumeId || '').trim()
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
})
const sessionKey = computed(() => String(route.query.session || '').trim())
const threadId = computed(() => String(route.query.threadId || '').trim())
const elapsedStorageKey = computed(
  () => `interview-session-started-at:${sessionKey.value || threadId.value}`
)

const progress = computed(() => normalizeInterviewProgress(currentAgentState.value?.todos))
const progressPercent = computed(() => {
  const completeShare = progress.value.completedCount / progress.value.steps.length
  const activeShare = progress.value.completedCount < progress.value.steps.length ? 0.5 : 0
  return Math.min(
    100,
    Math.round((completeShare + activeShare / progress.value.steps.length) * 100)
  )
})
const currentStage = computed(() => progress.value.steps[progress.value.currentIndex])
const sessionTitle = computed(
  () => `第 ${progress.value.currentIndex + 1} 阶段 · ${currentStage.value?.label || '面试进行中'}`
)
const sessionSubtitle = computed(
  () =>
    `${selectedPosition.value} · ${selectedRound.value} · 文本面试 · 用时 ${formatInterviewElapsed(elapsedSeconds.value)}`
)
const assessmentPoints = computed(
  () => currentAgentState.value?.question_context?.assessment_points || []
)
const questionSource = computed(() => currentAgentState.value?.question_context?.source || null)
const questionSourceUrl = computed(() => {
  const url = String(questionSource.value?.url || '').trim()
  return /^https?:\/\//i.test(url) || (url.startsWith('/') && !url.startsWith('//')) ? url : ''
})
const resumeReference = computed(
  () => currentAgentState.value?.question_context?.resume_reference || null
)

const contextOverrides = computed(() => ({
  target_position: selectedPosition.value,
  interview_round: selectedRound.value,
  selected_resume_id: selectedResumeId.value
}))

const threadTitle = computed(() => `${selectedPosition.value} · ${selectedRound.value}`)

const interviewOpeningPrompt = computed(() => {
  return [
    `现在开始一轮${selectedPosition.value}${selectedRound.value}模拟面试。`,
    '请基于当前岗位设定与系统已注入的简历上下文，直接开始本轮面试。',
    '先完成开场引导并请候选人做简短自我介绍。'
  ].join('')
})

const getStartedStorageKey = (key) => `interview-session-started:${key}`
const getSkipCodingRedirectKey = (key) => `interview-skip-coding-redirect:${key}`

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

const restoreInterviewThread = async () => {
  if (!threadId.value || !chatComponentRef.value) return
  await nextTick()
  await chatComponentRef.value.openThread?.(threadId.value)
}

async function toggleVideoMode() {
  if (isVideoMode.value) {
    eventStream.disableVideoMode()
    return
  }
  const activeThreadId = chatComponentRef.value?.currentChatId
  if (!activeThreadId) {
    message.warning('面试会话未就绪，无法开启视频模式')
    return
  }
  await eventStream.enableVideoMode(activeThreadId)
  if (!isVideoMode.value && eventStream.error.value) {
    message.error(eventStream.error.value)
  }
}

const switchToVoice = () => {
  router.push({
    name: 'AgentVoiceInterviewComp',
    query: {
      position: selectedPosition.value,
      round: selectedRound.value,
      ...(threadId.value ? { threadId: threadId.value } : {}),
      ...(sessionKey.value ? { session: sessionKey.value } : {}),
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const handleCodeUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  const activeThreadId = threadId.value || chatComponentRef.value?.currentChatId
  if (!file || !activeThreadId) {
    if (file) message.warning('面试会话未就绪，暂时无法上传代码')
    return
  }

  try {
    await threadApi.uploadThreadAttachment(activeThreadId, file)
    await chatComponentRef.value?.refreshAgentState?.()
    message.success('代码附件已上传')
  } catch (error) {
    handleChatError(error, 'upload')
  }
}

const goToCodingWorkbench = () => {
  if (!threadId.value) return
  codingReady.value = false
  router.push({
    name: 'InterviewCodingWorkbench',
    query: {
      threadId: threadId.value,
      position: selectedPosition.value,
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const dismissCodingBanner = () => {
  codingReady.value = false
}

const finishInterview = () => {
  if (!threadId.value) {
    message.warning('面试会话未就绪，暂时无法生成报告')
    return
  }
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: threadId.value,
      position: selectedPosition.value,
      round: selectedRound.value,
      autoGenerate: '1',
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const handleShareChat = async () => {
  try {
    const exportData = chatComponentRef.value?.getExportPayload?.()
    if (!exportData) {
      message.warning('当前没有可导出的面试记录')
      return
    }

    const hasMessages = Boolean(exportData.messages?.length)
    const hasOngoingMessages = Boolean(exportData.onGoingMessages?.length)
    if (!hasMessages && !hasOngoingMessages) {
      message.warning('请先开始一轮模拟面试，再导出记录')
      return
    }

    const result = await ChatExporter.exportToHTML(exportData)
    message.success(`面试记录已导出为 HTML：${result.filename}`)
  } catch (error) {
    if (error?.message?.includes('没有可导出的对话内容')) {
      message.warning('请先开始一轮模拟面试，再导出记录')
      return
    }
    handleChatError(error, 'export')
  }
}

const maybeStartInterview = async () => {
  if (threadId.value) {
    await restoreInterviewThread()
    return
  }
  if (!sessionKey.value || !interviewAgentId.value || !chatComponentRef.value) return
  if (sessionStorage.getItem(getStartedStorageKey(sessionKey.value)) === '1') return

  await nextTick()
  const startedThreadId = await chatComponentRef.value.startInterviewSession({
    openingPrompt: interviewOpeningPrompt.value,
    threadTitle: threadTitle.value,
    threadMetadata: {
      interview_mode: 'text',
      target_position: selectedPosition.value,
      interview_round: selectedRound.value,
      ...(selectedResumeId.value ? { resume_id: selectedResumeId.value } : {})
    },
    forceNewThread: true
  })

  if (startedThreadId) {
    sessionStorage.setItem(getStartedStorageKey(sessionKey.value), '1')
    router.replace({
      name: 'AgentInterviewComp',
      query: {
        threadId: startedThreadId,
        position: selectedPosition.value,
        round: selectedRound.value,
        session: sessionKey.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
      }
    })
  }
}

const interviewCompletedKey = (tid) => `interview-completed-redirected:${tid}`
// Threads observed actively in-progress this session. The completion redirect
// must only fire on a genuine live transition (in-progress → all done), never on
// a stale all-completed snapshot carried over when switching into a freshly
// started thread — otherwise a brand-new interview is bounced straight to the
// result page before the first question is even answered.
const threadsSeenInProgress = new Set()

const handleAgentStateChange = (agentState) => {
  currentAgentState.value = agentState || null
  if (!threadId.value) return

  // Detect interview completion: all todos finished → auto-redirect to result page
  const todos = agentState?.todos
  if (Array.isArray(todos) && todos.length > 0) {
    const allCompleted = todos.every((t) => t.status === 'completed')
    const lastTodo = todos[todos.length - 1]
    const lastDone = lastTodo?.status === 'completed'
    if (!allCompleted) {
      threadsSeenInProgress.add(threadId.value)
    } else if (lastDone && threadsSeenInProgress.has(threadId.value)) {
      const doneKey = interviewCompletedKey(threadId.value)
      if (!sessionStorage.getItem(doneKey)) {
        sessionStorage.setItem(doneKey, '1')
        router.replace({
          name: 'InterviewResultPage',
          query: {
            threadId: threadId.value,
            position: selectedPosition.value,
            round: selectedRound.value,
            autoGenerate: '1',
            ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
          }
        })
        return
      }
    }
  }

  const codingSession = agentState?.coding_session
  if (!threadId.value || !codingSession) return
  if (!['ready', 'coding'].includes(codingSession.status)) return
  const skipKey = getSkipCodingRedirectKey(threadId.value)
  const skipStartedAt = sessionStorage.getItem(skipKey)
  const currentStartedAt = String(codingSession.started_at || '').trim() || 'active'
  if (skipStartedAt && skipStartedAt === currentStartedAt) {
    return
  }
  if (skipStartedAt && skipStartedAt !== currentStartedAt) {
    sessionStorage.removeItem(skipKey)
  }

  codingReady.value = true
}

const handleThreadChange = (nextThread) => {
  const normalizedThreadId = String(nextThread?.id || nextThread || '').trim()
  if (!normalizedThreadId || normalizedThreadId === threadId.value) return

  const { position, round } = parseThreadTitle(nextThread?.title)

  router.replace({
    name: 'AgentInterviewComp',
    query: {
      threadId: normalizedThreadId,
      position,
      round,
      ...(sessionKey.value ? { session: sessionKey.value } : {}),
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

onMounted(async () => {
  const storedStartedAt = Number(sessionStorage.getItem(elapsedStorageKey.value))
  const startedAt =
    Number.isFinite(storedStartedAt) && storedStartedAt > 0 ? storedStartedAt : Date.now()
  if ((sessionKey.value || threadId.value) && !storedStartedAt) {
    sessionStorage.setItem(elapsedStorageKey.value, String(startedAt))
  }
  const updateElapsed = () => {
    elapsedSeconds.value = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  }
  updateElapsed()
  elapsedTimer = window.setInterval(updateElapsed, 1000)

  if (!sessionKey.value && !threadId.value) {
    router.replace({
      name: 'InterviewWorkbench',
      query: {
        position: selectedPosition.value,
        round: selectedRound.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
      }
    })
    return
  }

  if (!agentStore.isInitialized) {
    try {
      await agentStore.initialize()
    } catch (error) {
      console.error('初始化面试智能体失败:', error)
    }
  }

  await maybeStartInterview()
})

onBeforeUnmount(() => {
  if (elapsedTimer) window.clearInterval(elapsedTimer)
  eventStream.disableVideoMode()
})

watch(
  () => [sessionKey.value, threadId.value, interviewAgentId.value],
  async () => {
    await maybeStartInterview()
    if (threadId.value) {
      await restoreInterviewThread()
    }
  }
)
</script>

<style lang="less" scoped>
.interview-session-view {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--gray-0);
  color: var(--gray-1000);
}

.coding-ready-banner {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--main-50);
  border-bottom: 1px solid var(--main-200);
  font-size: 14px;
  color: var(--main-900);

  &__btn {
    height: 30px;
    padding: 0 14px;
    border: 1px solid var(--main-color);
    border-radius: 0;
    background: var(--main-color);
    color: var(--gray-0);
    cursor: pointer;
    font-size: 13px;
    white-space: nowrap;
  }

  &__close {
    border: none;
    background: none;
    font-size: 18px;
    color: var(--gray-600);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
}

.coding-banner-enter-active,
.coding-banner-leave-active {
  transition: all 0.3s ease;
}
.coding-banner-enter-from,
.coding-banner-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

.session-header {
  min-height: 88px;
  padding: 20px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--gray-200);
  flex-shrink: 0;
}

.session-heading {
  min-width: 0;

  h1 {
    margin: 0;
    font-size: 20px;
    line-height: 1.3;
    font-weight: 800;
    letter-spacing: -0.01em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  p {
    margin: 5px 0 0;
    font-size: 13px;
    color: var(--gray-600);
  }
}

.session-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.session-button {
  height: 36px;
  padding: 0 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid var(--gray-300);
  border-radius: 0;
  background: var(--gray-0);
  color: var(--gray-1000);
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;

  &:hover:not(:disabled),
  &:focus-visible,
  &.is-active {
    border-color: var(--main-color);
    color: var(--main-800);
    outline: none;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  &--primary {
    border-color: var(--main-color);
    background: var(--main-color);
    color: var(--gray-0);

    &:hover:not(:disabled),
    &:focus-visible {
      color: var(--gray-0);
      background: var(--main-700);
    }
  }
}

.session-content {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
}

.conversation-pane {
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--gray-100);
  overflow: hidden;
}

.context-rail {
  min-height: 0;
  padding: 24px;
  overflow-y: auto;
}

.rail-section {
  padding-bottom: 22px;
  margin-bottom: 22px;
  border-bottom: 2px solid var(--gray-1000);

  &:last-child {
    margin-bottom: 0;
    border-bottom: 0;
  }

  h2 {
    margin: 0;
    font-size: 11px;
    line-height: 1.4;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--gray-700);
  }
}

.rail-section__heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;

  span {
    font-size: 12px;
    color: var(--gray-600);
  }
}

.progress-track {
  height: 6px;
  margin: 10px 0 14px;
  display: flex;
  gap: 2px;

  &__done,
  &__remaining {
    height: 100%;
  }

  &__done {
    background: var(--main-color);
    transition: width 0.2s ease;
  }

  &__remaining {
    min-width: 0;
    flex: 1;
    background: var(--gray-100);
  }
}

.progress-list {
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
  list-style: none;

  li {
    display: grid;
    grid-template-columns: 18px minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    min-height: 22px;
    font-size: 13px;
    color: var(--gray-500);
  }

  li.is-completed {
    color: var(--gray-600);
  }

  li.is-in_progress {
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.progress-index {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--gray-200);
  color: var(--gray-500);
  font-size: 10px;
  font-weight: 750;
  box-sizing: border-box;

  .is-completed & {
    border-color: var(--main-color);
    background: var(--main-color);
    color: var(--gray-0);
  }

  .is-in_progress & {
    border: 2px solid var(--main-color);
    color: var(--main-800);
  }
}

.progress-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-status {
  font-size: 11px;
  color: var(--gray-500);
}

.assessment-list {
  margin-top: 12px;
}

.assessment-row {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--gray-100);
  font-size: 14px;

  &:last-child {
    border-bottom: 0;
  }

  strong {
    font-size: 12px;
    font-weight: 500;
    color: var(--gray-500);
  }

  strong.is-covered {
    color: var(--main-800);
    font-weight: 750;
  }
}

.rail-empty {
  margin: 12px 0 0;
  font-size: 13px;
  line-height: 1.65;
  color: var(--gray-500);
}

.source-block {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  line-height: 1.6;

  strong {
    color: var(--gray-1000);
  }

  span {
    color: var(--gray-600);
  }

  a {
    width: fit-content;
    color: var(--main-800);
    text-decoration: none;

    &:hover,
    &:focus-visible {
      color: var(--main-color);
      text-decoration: underline;
      outline: none;
    }
  }
}

.resume-reference {
  margin: 12px 0 0;
  padding-left: 14px;
  border-left: 1px solid var(--gray-200);
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-700);

  footer {
    margin-top: 8px;
    font-size: 12px;
    color: var(--gray-500);
  }
}

.input-text-action {
  height: 28px;
  padding: 0 7px;
  border: 0;
  background: transparent;
  color: var(--gray-600);
  font: inherit;
  font-size: 13px;
  cursor: pointer;

  &:hover,
  &:focus-visible {
    color: var(--main-800);
    outline: 1px solid var(--main-color);
    outline-offset: 1px;
  }
}

.input-file-action {
  display: inline-flex;
  align-items: center;

  input {
    display: none;
  }
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1100px) {
  .session-header {
    align-items: flex-start;
  }

  .session-content {
    grid-template-columns: minmax(0, 1fr) 300px;
  }
}

@media (max-width: 860px) {
  .session-header {
    padding: 16px 20px;
    flex-direction: column;
  }

  .session-actions {
    width: 100%;
    overflow-x: auto;
  }

  .session-content {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .conversation-pane {
    min-height: 620px;
    flex: 0 0 70vh;
    border-right: 0;
    border-bottom: 1px solid var(--gray-100);
  }

  .context-rail {
    overflow: visible;
  }
}
</style>
