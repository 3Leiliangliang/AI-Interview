<template>
  <div class="voice-interview-view">
    <div class="voice-toolbar">
      <div>
        <div class="toolbar-title">语音模拟面试</div>
        <div class="toolbar-subtitle">豆包负责语音播报，候选人语音由阿里云实时转文字后接回原面试 Agent 链路</div>
      </div>

      <div class="toolbar-actions">
        <span class="status-badge">{{ connectionStatusLabel }}</span>
        <span class="status-badge">{{ playbackStatusLabel }}</span>
        <span class="status-badge">{{ captureStatusLabel }}</span>
        <a-button
          :type="isAgentPanelOpen ? 'primary' : 'default'"
          :disabled="!hasAgentStateContent"
          @click="toggleAgentPanel"
        >
          {{ isAgentPanelOpen ? '收起状态工作台' : '展开状态工作台' }}
        </a-button>
        <a-button @click="backToSetup">调整配置</a-button>
        <a-button @click="openResumeCenter">我的简历</a-button>
        <a-button :disabled="!currentThreadId" @click="openInterviewResult">面试结果</a-button>
      </div>
    </div>

    <div class="voice-stage">
      <section class="role-card interviewer-card" :class="`state-${interviewerVisualState}`">
        <div class="role-header">
          <div class="role-label">面试官</div>
          <div class="role-actions">
            <a-button type="primary" :loading="startingVoice" @click="handleStartVoiceInterview">
              {{ startButtonLabel }}
            </a-button>
            <a-button :disabled="playbackState !== 'playing'" @click="interrupt">停止播放</a-button>
          </div>
        </div>
        <div class="interviewer-stage-content">
          <div class="interviewer-visual" :class="`is-${interviewerVisualState}`">
            <div class="interviewer-ring"></div>
            <div class="interviewer-core">
              <div v-if="interviewerVisualState === 'speaking'" class="wave-bars" aria-hidden="true">
                <span v-for="bar in 5" :key="`wave-${bar}`" class="wave-bar"></span>
              </div>
              <div v-else-if="interviewerVisualState === 'waiting'" class="waiting-dots" aria-hidden="true">
                <span v-for="dot in 3" :key="`waiting-${dot}`" class="waiting-dot"></span>
              </div>
              <div v-else class="interviewer-idle-icon" aria-hidden="true"></div>
            </div>
          </div>
          <div class="interviewer-stage-title">{{ interviewerStageTitle }}</div>
          <div class="interviewer-stage-text">{{ interviewerStageDescription }}</div>
        </div>
      </section>

      <section class="role-card candidate-card">
        <div class="role-header">
          <div class="role-label">面试者</div>
          <div class="role-actions">
            <a-button
              type="primary"
              :disabled="!canStartCapture"
              :loading="startingCapture"
              @click="handleStartCapture"
            >
              开始回答
            </a-button>
            <a-button :disabled="!isCapturing" @click="handleStopCapture">停止回答</a-button>
          </div>
        </div>
        <div class="role-placeholder">浏览器麦克风实时转写</div>
      </section>
    </div>

    <div class="voice-content-container">
      <div class="voice-shell">
        <div class="panel-header">
          <div>
            <div class="panel-title">文本记录</div>
            <div class="panel-subtitle">用于跟进当前线程的上下文、语音播报内容与候选人最终提交文本</div>
          </div>
        </div>

        <div class="messages-panel" ref="messagesPanelRef">
          <div v-if="error" class="error-banner">{{ error }}</div>

          <div v-if="visibleMessages.length === 0" class="empty-state">
            <div class="empty-title">语音会话尚未开始</div>
            <div class="empty-text">点击“开启语音面试”后，面试官会直接以语音形式发起第一问。</div>
          </div>

          <div
            v-for="item in visibleMessages"
            :key="item.id"
            class="message-row"
            :class="item.role === 'assistant' ? 'assistant' : 'user'"
          >
            <div class="message-role">{{ item.role === 'assistant' ? '面试官' : '你' }}</div>
            <div class="message-bubble">
              {{ item.content }}
              <span v-if="item.streaming" class="streaming-dot"></span>
            </div>
          </div>
        </div>

        <div class="input-panel">
          <div class="capture-panel">
            <div class="capture-status">
              <div class="capture-title">候选人语音输入</div>
              <div class="capture-subtitle">{{ captureHintLabel }}</div>
            </div>
          </div>

          <div class="transcript-shell">
            <div class="transcript-card">
              <div class="transcript-label">实时转写</div>
              <div class="transcript-content" :class="{ placeholder: !partialTranscript }">
                {{ partialTranscript || '开始回答后，这里会实时显示当前识别中的文本。' }}
              </div>
            </div>
            <div class="transcript-card">
              <div class="transcript-label">最终修正文本</div>
              <div class="transcript-content" :class="{ placeholder: !finalTranscript }">
                {{ finalTranscript || '句子结束后，这里会显示提交给面试 Agent 的最终文本。' }}
              </div>
            </div>
          </div>

          <div class="input-actions">
            <span class="input-hint">
              当前线程：{{ currentThreadId || '未创建' }} · 麦克风权限：{{ micPermissionLabel }}
            </span>
          </div>
        </div>
      </div>

      <div
        class="agent-panel-wrapper"
        ref="panelWrapperRef"
        :class="{
          'is-visible': isAgentPanelOpen && hasAgentStateContent,
          'no-transition': isResizing
        }"
        :style="{
          flexBasis: isAgentPanelOpen && hasAgentStateContent ? `${panelRatio * 100}%` : '0px'
        }"
      >
        <AgentPanel
          v-if="isAgentPanelOpen && hasAgentStateContent"
          :agent-state="agentState"
          :thread-id="currentThreadId"
          :panel-ratio="panelRatio"
          @refresh="handleAgentStateRefresh"
          @close="toggleAgentPanel"
          @resize="handlePanelResize"
          @resizing="handleResizingChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'

import { interviewVoiceApi } from '@/apis/interview_voice'
import AgentPanel from '@/components/AgentPanel.vue'
import { useVoiceInterviewSession } from '@/composables/useVoiceInterviewSession'
import { useAgentStore } from '@/stores/agent'
import { useUserStore } from '@/stores/user'

const DEFAULT_POSITION = '后端工程师'
const DEFAULT_ROUND = '初试'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const userStore = useUserStore()

const messagesPanelRef = ref(null)
const startingVoice = ref(false)
const startingCapture = ref(false)
const preloadingVoice = ref(false)
const preloadedSession = ref(null)
const hasStartedOpeningTurn = ref(false)
const isAgentPanelOpen = ref(false)
const isResizing = ref(false)
const panelRatio = ref(0.36)
const panelWrapperRef = ref(null)

let preloadPromise = null
let panelContainerWidth = 0

const minPanelRatio = 0.28
const maxPanelRatio = 0.5

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const routeThreadId = computed(() => String(route.query.threadId || '').trim())
const sessionKey = computed(() => String(route.query.session || '').trim())
const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')

const {
  agentState,
  candidateCaptureState,
  connect,
  connectionState,
  ensureAudioContext,
  ensureMicrophoneReady,
  error,
  finalTranscript,
  interrupt,
  isCapturing,
  messages,
  micPermissionState,
  partialTranscript,
  playbackState,
  sessionReady,
  startCandidateCapture,
  startInterview,
  stopCandidateCapture,
  threadId
} = useVoiceInterviewSession({
  onCodingRedirect: ({ thread_id: nextThreadId, position, round }) => {
    router.push({
      name: 'InterviewCodingWorkbench',
      query: {
        threadId: nextThreadId || currentThreadId.value,
        position: position || selectedPosition.value,
        round: round || selectedRound.value
      }
    })
  }
})

const currentThreadId = computed(() => threadId.value || routeThreadId.value)
const visibleMessages = computed(() => messages.value)
const lastVisibleMessage = computed(() => visibleMessages.value[visibleMessages.value.length - 1] || null)
const hasAgentStateContent = computed(() => {
  const todos = Array.isArray(agentState.value?.todos) ? agentState.value.todos.length : 0
  const files = agentState.value?.files
  if (Array.isArray(files)) {
    return todos > 0 || files.length > 0
  }
  if (files && typeof files === 'object') {
    return todos > 0 || Object.keys(files).length > 0
  }
  return todos > 0
})
const lastVisibleMessageRole = computed(() => lastVisibleMessage.value?.role || '')
const canStartOpeningTurn = computed(() => {
  return connectionState.value === 'connected' && visibleMessages.value.length === 0 && !hasStartedOpeningTurn.value
})
const canStartCapture = computed(() => {
  return sessionReady.value && candidateCaptureState.value === 'idle' && !isCapturing.value
})
const connectionStatusLabel = computed(() => {
  if (connectionState.value === 'connected') return '连接已建立'
  if (connectionState.value === 'connecting') return '连接中'
  if (connectionState.value === 'closed') return '连接已关闭'
  return '未连接'
})
const playbackStatusLabel = computed(() => {
  if (playbackState.value === 'playing') return '正在播报'
  return '待机'
})
const isInterviewerSpeaking = computed(() => playbackState.value === 'playing')
const isInterviewerWaiting = computed(() => {
  if (isInterviewerSpeaking.value || !sessionReady.value) return false
  if (candidateCaptureState.value === 'processing') return true
  if (hasStartedOpeningTurn.value && visibleMessages.value.length === 0) return true
  if (lastVisibleMessage.value?.role === 'assistant' && lastVisibleMessage.value.streaming) return true
  return lastVisibleMessage.value?.role === 'user' && !isCapturing.value
})
const interviewerVisualState = computed(() => {
  if (isInterviewerSpeaking.value) return 'speaking'
  if (isInterviewerWaiting.value) return 'waiting'
  return 'idle'
})
const interviewerStageTitle = computed(() => {
  if (interviewerVisualState.value === 'speaking') return '在面试'
  if (interviewerVisualState.value === 'waiting') return '在思考'
  return '豆包实时语音播报'
})
const interviewerStageDescription = computed(() => {
  if (interviewerVisualState.value === 'speaking') return '输出语音时会实时展示波形反馈。'
  if (interviewerVisualState.value === 'waiting') return '收到你的回答后，面试官会短暂组织下一轮提问。'
  return '开始后面试官会主动提问，追问时也会在这里切换状态。'
})
const captureStatusLabel = computed(() => {
  if (candidateCaptureState.value === 'listening') return '正在收音'
  if (candidateCaptureState.value === 'processing') return '识别处理中'
  if (candidateCaptureState.value === 'disabled') return '等待面试官'
  return '可开始回答'
})
const micPermissionLabel = computed(() => {
  if (micPermissionState.value === 'granted') return '已授权'
  if (micPermissionState.value === 'denied') return '已拒绝'
  return '待授权'
})
const captureHintLabel = computed(() => {
  if (candidateCaptureState.value === 'disabled') return '面试官播报期间会自动暂停收音，避免回声串入识别。'
  if (candidateCaptureState.value === 'processing') return '正在等待阿里云返回当前句子的最终修正文案。'
  if (isCapturing.value) return '你正在回答，系统会实时转写，并在句子结束后自动提交给面试 Agent。'
  return '面试官播报结束后可开始回答，系统也会在合适时机自动进入收音。'
})
const startButtonLabel = computed(() => {
  if (preloadingVoice.value && connectionState.value !== 'connected') return '预加载中'
  if (canStartOpeningTurn.value) return '开始语音面试'
  if (connectionState.value === 'connected') return '语音已就绪'
  if (routeThreadId.value) return '连接语音会话'
  return '开启语音面试'
})

const scrollMessagesToBottom = async () => {
  await nextTick()
  const el = messagesPanelRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

const backToSetup = () => {
  router.push({
    name: 'AgentComp',
    query: {
      mode: 'voice',
      position: selectedPosition.value,
      round: selectedRound.value
    }
  })
}

const openResumeCenter = () => {
  router.push('/resume')
}

const openInterviewResult = () => {
  if (!currentThreadId.value) return
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: currentThreadId.value,
      position: selectedPosition.value,
      round: selectedRound.value
    }
  })
}

const toggleAgentPanel = () => {
  if (!hasAgentStateContent.value) return
  isAgentPanelOpen.value = !isAgentPanelOpen.value
}

const handleAgentStateRefresh = async () => {}

const handlePanelResize = (deltaX) => {
  if (!panelWrapperRef.value) return

  if (!panelContainerWidth) {
    const container = document.querySelector('.voice-content-container')
    panelContainerWidth = container ? container.clientWidth : window.innerWidth
  }

  const currentWidth = panelWrapperRef.value.offsetWidth
  const nextWidth = currentWidth - deltaX
  const nextRatio = nextWidth / panelContainerWidth

  if (nextRatio >= minPanelRatio && nextRatio <= maxPanelRatio) {
    panelWrapperRef.value.style.setProperty('flex', `0 0 ${nextWidth}px`, 'important')
  }
}

const handleResizingChange = (value) => {
  isResizing.value = value
  if (!value && panelWrapperRef.value && panelContainerWidth) {
    panelRatio.value = panelWrapperRef.value.offsetWidth / panelContainerWidth
    panelContainerWidth = 0
  }
}

const ensureAgentReady = async () => {
  if (!agentStore.isInitialized) {
    await agentStore.initialize()
  }
  if (!interviewAgentId.value) {
    throw new Error('未找到可用的面试智能体')
  }
}

const preloadVoiceSession = async () => {
  if (preloadPromise) {
    return preloadPromise
  }

  if (connectionState.value === 'connected' && preloadedSession.value) {
    return preloadedSession.value
  }

  preloadPromise = (async () => {
    preloadingVoice.value = true
    await ensureAgentReady()

    const payload =
      preloadedSession.value ||
      (await interviewVoiceApi.startVoiceSession({
        agent_id: interviewAgentId.value,
        position: selectedPosition.value,
        round: selectedRound.value,
        thread_id: routeThreadId.value || undefined,
        force_new_thread: false
      }))

    preloadedSession.value = payload

    await connect({
      voiceSessionId: payload.voice_session_id,
      token: userStore.token,
      nextThreadId: payload.thread_id
    })

    if (routeThreadId.value !== payload.thread_id) {
      router.replace({
        name: 'AgentVoiceInterviewComp',
        query: {
          mode: 'voice',
          position: selectedPosition.value,
          round: selectedRound.value,
          threadId: payload.thread_id,
          ...(sessionKey.value ? { session: sessionKey.value } : {})
        }
      })
    }

    return payload
  })()

  try {
    return await preloadPromise
  } finally {
    preloadingVoice.value = false
    preloadPromise = null
  }
}

const waitForSessionReady = async () => {
  let waitCount = 0
  while (!sessionReady.value && waitCount < 20) {
    await new Promise((resolve) => setTimeout(resolve, 50))
    waitCount += 1
  }
}

const handleStartVoiceInterview = async () => {
  startingVoice.value = true
  try {
    await preloadVoiceSession()
    await ensureAudioContext()
    await ensureMicrophoneReady()
    await waitForSessionReady()

    if (canStartOpeningTurn.value) {
      hasStartedOpeningTurn.value = true
      startInterview()
      return
    }

    message.success('语音会话已就绪')
  } catch (err) {
    message.error(err?.message || '开启语音面试失败')
  } finally {
    startingVoice.value = false
  }
}

const handleStartCapture = async () => {
  startingCapture.value = true
  try {
    await ensureMicrophoneReady()
    await startCandidateCapture()
  } catch (err) {
    message.error(err?.message || '开始收音失败')
  } finally {
    startingCapture.value = false
  }
}

const handleStopCapture = () => {
  stopCandidateCapture()
}

const maybeAutoStartCapture = async () => {
  if (!sessionReady.value) return
  if (playbackState.value !== 'idle') return
  if (candidateCaptureState.value !== 'idle') return
  if (isCapturing.value) return
  if (lastVisibleMessageRole.value !== 'assistant') return

  try {
    await ensureMicrophoneReady()
    await startCandidateCapture()
  } catch (err) {
    console.warn('auto start candidate capture failed:', err)
  }
}

onMounted(async () => {
  if (!sessionKey.value && !routeThreadId.value) {
    router.replace({
      name: 'AgentComp',
      query: {
        mode: 'voice',
        position: selectedPosition.value,
        round: selectedRound.value
      }
    })
    return
  }

  try {
    await ensureAgentReady()
    await preloadVoiceSession()
  } catch (err) {
    message.error(err?.message || '预加载语音会话失败')
  }
})

watch(
  () => visibleMessages.value.map((item) => `${item.id}:${item.content.length}:${item.streaming}`).join('|'),
  async () => {
    await scrollMessagesToBottom()
  }
)

watch(hasAgentStateContent, (value, oldValue) => {
  if (value && !oldValue) {
    isAgentPanelOpen.value = true
  }
})

watch(
  () => agentState.value?.coding_session?.status,
  (status) => {
    if (!['ready', 'coding'].includes(status)) return
    router.push({
      name: 'InterviewCodingWorkbench',
      query: {
        threadId: currentThreadId.value,
        position: selectedPosition.value,
        round: selectedRound.value
      }
    })
  }
)

watch(
  () =>
    [
      candidateCaptureState.value,
      playbackState.value,
      sessionReady.value,
      lastVisibleMessageRole.value,
      isCapturing.value
    ].join('|'),
  async () => {
    await maybeAutoStartCapture()
  }
)
</script>

<style lang="less" scoped>
.voice-interview-view {
  min-height: 100%;
  background: var(--gray-25);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.voice-toolbar,
.voice-shell {
  border: 1px solid var(--gray-100);
  border-radius: 20px;
  background: var(--gray-0);
}

.voice-toolbar {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.toolbar-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--gray-900);
}

.toolbar-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--gray-500);
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--gray-25);
  border: 1px solid var(--gray-100);
  color: var(--gray-700);
  font-size: 13px;
}

.voice-stage {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.role-card {
  min-height: 220px;
  border-radius: 20px;
  border: 1px solid var(--gray-100);
  background: var(--gray-0);
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.interviewer-card {
  overflow: hidden;
}

.interviewer-card.state-speaking {
  border-color: var(--main-100);
}

.role-label {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-800);
}

.role-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.role-actions {
  display: flex;
  gap: 8px;
}

.role-placeholder {
  flex: 1;
  margin-top: 18px;
  border-radius: 16px;
  border: 1px dashed var(--gray-200);
  background: var(--gray-25);
  color: var(--gray-400);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.interviewer-stage-content {
  flex: 1;
  margin-top: 18px;
  border-radius: 16px;
  border: 1px dashed var(--gray-200);
  background: var(--gray-25);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 24px;
  text-align: center;
}

.interviewer-card.state-speaking .interviewer-stage-content {
  border-color: var(--main-100);
  background: var(--main-20);
}

.interviewer-visual {
  position: relative;
  width: 128px;
  height: 128px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.interviewer-ring,
.interviewer-core {
  position: absolute;
  border-radius: 50%;
}

.interviewer-ring {
  inset: 10px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
}

.interviewer-core {
  inset: 30px;
  border: 1px solid var(--gray-100);
  background: var(--gray-0);
  display: flex;
  align-items: center;
  justify-content: center;
}

.interviewer-visual.is-speaking .interviewer-ring {
  border-color: var(--main-100);
  background: var(--main-20);
  animation: interviewer-ring-pulse 1.8s ease-in-out infinite;
}

.interviewer-visual.is-waiting .interviewer-ring {
  animation: interviewer-ring-breathe 1.8s ease-in-out infinite;
}

.wave-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 30px;
}

.wave-bar {
  width: 6px;
  height: 14px;
  border-radius: 999px;
  background: var(--main-color);
  transform-origin: center bottom;
  animation: wave-bar-bounce 1s ease-in-out infinite;
}

.wave-bar:nth-child(2) {
  animation-delay: 0.12s;
}

.wave-bar:nth-child(3) {
  animation-delay: 0.24s;
}

.wave-bar:nth-child(4) {
  animation-delay: 0.36s;
}

.wave-bar:nth-child(5) {
  animation-delay: 0.48s;
}

.waiting-dots {
  display: flex;
  align-items: center;
  gap: 8px;
}

.waiting-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--gray-400);
  animation: waiting-dot-fade 1.2s ease-in-out infinite;
}

.waiting-dot:nth-child(2) {
  animation-delay: 0.18s;
}

.waiting-dot:nth-child(3) {
  animation-delay: 0.36s;
}

.interviewer-idle-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--main-100) 0 34%, transparent 38%);
  border: 1px solid var(--gray-200);
}

.interviewer-stage-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-800);
}

.interviewer-stage-text {
  max-width: 320px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-500);
}

@keyframes wave-bar-bounce {
  0%,
  100% {
    transform: scaleY(0.45);
    opacity: 0.52;
  }
  50% {
    transform: scaleY(1.25);
    opacity: 1;
  }
}

@keyframes waiting-dot-fade {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.35;
  }
  50% {
    transform: translateY(-4px);
    opacity: 1;
  }
}

@keyframes interviewer-ring-pulse {
  0%,
  100% {
    transform: scale(0.96);
    opacity: 0.72;
  }
  50% {
    transform: scale(1.02);
    opacity: 1;
  }
}

@keyframes interviewer-ring-breathe {
  0%,
  100% {
    transform: scale(0.98);
    opacity: 0.45;
  }
  50% {
    transform: scale(1.04);
    opacity: 0.82;
  }
}

.voice-shell {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 520px;
  min-width: 0;
  flex: 1;
}

.voice-content-container {
  display: flex;
  gap: 20px;
  align-items: stretch;
  min-height: 520px;
}

.panel-header,
.input-actions,
.capture-panel,
.transcript-shell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-900);
}

.panel-subtitle,
.input-hint {
  font-size: 13px;
  color: var(--gray-500);
}



.messages-panel {
  flex: 1;
  min-height: 280px;
  max-height: 480px;
  overflow-y: auto;
  border-radius: 16px;
  border: 1px solid var(--gray-100);
  background: var(--gray-25);
  padding: 18px;
}

.message-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}

.message-row.assistant {
  align-items: flex-start;
}

.message-row.user {
  align-items: flex-end;
}

.message-role {
  font-size: 12px;
  color: var(--gray-500);
}

.message-bubble {
  max-width: 80%;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
  color: var(--gray-800);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-row.user .message-bubble {
  background: var(--main-20);
  border-color: var(--main-100);
}

.streaming-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--main-color);
  margin-left: 8px;
}

.empty-state {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-800);
}

.empty-text {
  margin-top: 8px;
  font-size: 13px;
  color: var(--gray-500);
}

.error-banner {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #fff1f0;
  border: 1px solid #ffccc7;
  color: #cf1322;
  font-size: 13px;
}

.input-panel {
  border-radius: 16px;
  border: 1px solid var(--gray-100);
  background: var(--gray-0);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.capture-status,
.transcript-card {
  flex: 1;
}

.agent-panel-wrapper {
  flex: 0 0 0;
  width: 0;
  min-width: 0;
  overflow: hidden;
  transition: flex-basis 0.24s ease, width 0.24s ease;
}

.agent-panel-wrapper.is-visible {
  min-width: 320px;
}

.agent-panel-wrapper.no-transition {
  transition: none;
}

.agent-panel-wrapper :deep(.agent-panel) {
  height: 100%;
}

@media (max-width: 1200px) {
  .voice-content-container {
    flex-direction: column;
  }

  .agent-panel-wrapper,
  .agent-panel-wrapper.is-visible {
    width: 100%;
    min-width: 100%;
  }
}

.capture-title,
.transcript-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-800);
}

.capture-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-500);
}

.transcript-card {
  border-radius: 14px;
  border: 1px solid var(--gray-100);
  background: var(--gray-25);
  padding: 14px;
}

.transcript-content {
  margin-top: 8px;
  min-height: 72px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-800);
  white-space: pre-wrap;
  word-break: break-word;
}

.transcript-content.placeholder {
  color: var(--gray-400);
}

@media (max-width: 960px) {
  .voice-toolbar,
  .panel-header,
  .input-actions,
  .capture-panel,
  .transcript-shell,
  .role-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-actions {
    justify-content: flex-start;
  }

  .role-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .voice-stage {
    grid-template-columns: 1fr;
  }

  .message-bubble {
    max-width: 100%;
  }
}
</style>
