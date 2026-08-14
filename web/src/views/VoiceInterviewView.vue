<template>
  <div class="voice-interview-view">
    <header class="voice-toolbar">
      <div>
        <h1 class="toolbar-title">语音面试 · {{ selectedPosition }} {{ selectedRound }}</h1>
        <p class="toolbar-subtitle">
          {{ questionProgressLabel }} · 已回答 {{ answeredQuestionCount }} /
          {{ totalQuestionCount }} 题 · 用时 {{ elapsedTimeLabel }} · 豆包 TTS + Fun-ASR
        </p>
      </div>

      <div class="toolbar-actions">
        <a-button @click="backToSetup">调整配置</a-button>
        <a-button @click="switchToTextInterview">切到文本</a-button>
        <a-button type="primary" :disabled="!currentThreadId" @click="openInterviewResult">
          结束并生成报告
        </a-button>
      </div>
    </header>

    <main class="interview-workspace">
      <section class="conversation-column">
        <div class="playback-bar">
          <div class="playback-wave" :class="{ active: isInterviewerSpeaking }" aria-hidden="true">
            <span v-for="bar in 8" :key="`playback-${bar}`"></span>
          </div>
          <div class="playback-copy">
            <strong>{{ playbackTitle }}</strong>
            <span>{{ playbackDetail }}</span>
          </div>
          <a-button
            v-if="isInterviewerSpeaking"
            :disabled="playbackState !== 'playing'"
            @click="interrupt"
          >
            停止播放
          </a-button>
          <a-button
            v-else-if="canStartOpeningTurn"
            type="primary"
            :loading="startingVoice"
            @click="handleStartVoiceInterview"
          >
            开始面试
          </a-button>
        </div>

        <div ref="messagesPanelRef" class="conversation-stream">
          <div v-if="error" class="error-banner">{{ error }}</div>

          <div v-if="visibleMessages.length === 0" class="empty-state">
            <div>
              <strong>{{ startButtonLabel }}</strong>
              <span>建立语音链路后，面试官会发起第一问。</span>
            </div>
            <a-button type="primary" :loading="startingVoice" @click="handleStartVoiceInterview">
              {{ startButtonLabel }}
            </a-button>
          </div>

          <article
            v-for="item in visibleMessages"
            :key="item.id"
            class="message-row"
            :class="item.role === 'assistant' ? 'assistant' : 'user'"
          >
            <div class="message-role">{{ item.role === 'assistant' ? '面试官' : '我' }}</div>
            <div class="message-content">
              {{ item.content }}
              <span v-if="item.streaming" class="streaming-mark">...</span>
            </div>
          </article>
        </div>

        <div class="transcript-dock">
          <section class="transcript-panel">
            <header class="transcript-header">
              <span>实时转写</span>
              <div class="transcript-wave" :class="{ active: isCapturing }" aria-hidden="true">
                <span v-for="bar in 4" :key="`partial-${bar}`"></span>
              </div>
            </header>
            <div class="transcript-content" :class="{ placeholder: !partialTranscript }">
              {{ partialTranscript || '开始回答后，实时识别内容会显示在这里。' }}
            </div>
          </section>

          <section class="transcript-panel">
            <header class="transcript-header">
              <span>最终修正文案</span>
              <span class="sync-badge">{{ finalTranscript ? '已提交' : '3 秒静音后提交' }}</span>
            </header>
            <div class="transcript-content" :class="{ placeholder: !finalTranscript }">
              {{ finalTranscript || '等待本句结束...' }}
            </div>
          </section>
        </div>
      </section>

      <aside class="observation-column">
        <div v-if="showCameraPreview" class="camera-block">
          <div class="camera-stage">
            <video
              v-show="isCameraStreaming"
              ref="cameraVideoRef"
              class="camera-video"
              autoplay
              muted
              playsinline
            ></video>

            <div v-if="!isCameraStreaming" class="camera-empty">
              <CameraOutlined />
              <span>{{ cameraStatusLabel }}</span>
            </div>

            <div class="camera-overlay">
              <div class="camera-overlay-group">
                <span class="live-badge"><i></i>LIVE</span>
                <span class="camera-status">{{ candidateCameraStatus }}</span>
              </div>
              <div v-if="isCameraStreaming" class="camera-overlay-group camera-metrics">
                <span>{{ cameraResolutionLabel }}</span>
                <span>{{ cameraFps || 0 }} FPS</span>
                <span>{{ analysisFps || 0 }} AI FPS</span>
              </div>
            </div>
          </div>

          <div class="camera-actions">
            <a-button :loading="startingCamera" @click="handleToggleCamera">
              {{ isCameraStreaming ? '关闭摄像头' : '开启摄像头' }}
            </a-button>
            <a-button :disabled="!isCapturing" @click="handleToggleCapture">
              {{ isCapturing ? '静音' : '开始收音' }}
            </a-button>
          </div>
        </div>

        <section class="observation-section">
          <header class="section-header">
            <span>候选人观察摘要</span>
            <span class="sync-badge">每 5 秒同步</span>
          </header>
          <div class="observation-grid">
            <article
              v-for="metric in videoAnalysisMetrics"
              :key="metric.key"
              class="observation-item"
            >
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
              <small>{{ metric.note }}</small>
            </article>
          </div>
        </section>

        <section class="observation-section alert-section">
          <header class="section-header"><span>最近提醒</span></header>
          <div class="alert-list">
            <div
              v-for="(alert, index) in videoRecentAlerts"
              :key="`${alert.type || 'alert'}-${index}`"
              class="alert-row"
            >
              <span>{{ alert.message }}</span>
              <time>{{ formatAlertTime(alert.time) }}</time>
            </div>
          </div>
        </section>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { CameraOutlined } from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'

import { interviewVoiceApi } from '@/apis/interview_voice'
import { videoApi } from '@/apis/video_api'
import { useVideoEventStream } from '@/composables/useVideoEventStream'
import { useVoiceInterviewSession } from '@/composables/useVoiceInterviewSession'
import { useAgentStore } from '@/stores/agent'
import { useUserStore } from '@/stores/user'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const DEFAULT_ROUND = '初试'
const VIDEO_STATUS_POLL_INTERVAL = 5000

const EMOTION_LABELS = {
  happy: '愉悦',
  confident: '自信',
  neutral: '稳定',
  fear: '紧张',
  sad: '低落',
  angry: '烦躁',
  surprised: '惊讶',
  disgust: '抗拒'
}

const GAZE_LABELS = {
  center: '看向镜头',
  left: '视线偏左',
  right: '视线偏右',
  up: '视线上移',
  down: '视线下移'
}

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const userStore = useUserStore()
const messagesPanelRef = ref(null)
const startingVoice = ref(false)
const startingCapture = ref(false)
const startingCamera = ref(false)
const preloadingVoice = ref(false)
const preloadedSession = ref(null)
const hasStartedOpeningTurn = ref(false)
const startedAt = ref(Date.now())
const backendVideoStatus = ref({ session_id: '', events_in_buffer: 0, status: 'inactive' })
const backendVideoAggregate = ref({ has_data: false, event_count: 0, recent_alerts: [] })

let preloadPromise = null
let videoStatusTimer = null
let elapsedTimeTimer = null

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)
const selectedPosition = computed(
  () => String(route.query.position || '').trim() || DEFAULT_POSITION
)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const selectedResumeId = computed(() => {
  const raw = String(route.query.resumeId || '').trim()
  const parsed = Number(raw)
  return raw && Number.isFinite(parsed) ? parsed : null
})
const routeThreadId = computed(() => String(route.query.threadId || '').trim())
const sessionKey = computed(() => String(route.query.session || '').trim())
const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')
const isVoiceOnlyMode = computed(() => String(route.query.video || '').toLowerCase() === 'false')

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
        round: round || selectedRound.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
      }
    })
  }
})

const videoEventStream = useVideoEventStream()
const {
  alerts: videoAlerts,
  analysisFps,
  attentionScore,
  captureError: cameraError,
  captureStart: startCamera,
  currentEmotion,
  disableVideoMode,
  emotionScores,
  enableVideoMode,
  error: videoStreamError,
  fps: cameraFps,
  gazeDirection,
  isCameraSupported,
  isStreaming: isCameraStreaming,
  isVideoMode,
  postureScore,
  resolution: cameraResolution,
  videoRef: cameraVideoRef
} = videoEventStream

const currentThreadId = computed(() => threadId.value || routeThreadId.value)
const visibleMessages = computed(() => messages.value)
const lastVisibleMessage = computed(
  () => visibleMessages.value[visibleMessages.value.length - 1] || null
)
const canStartOpeningTurn = computed(() => {
  return (
    connectionState.value === 'connected' &&
    visibleMessages.value.length === 0 &&
    !hasStartedOpeningTurn.value
  )
})
const isInterviewerSpeaking = computed(() => playbackState.value === 'playing')
const showCameraPreview = computed(() => {
  return (
    !isVoiceOnlyMode.value && isCameraSupported.value && cameraError.value !== '摄像头权限被拒绝'
  )
})
const answeredQuestionCount = computed(
  () => visibleMessages.value.filter((item) => item.role === 'user').length
)
const totalQuestionCount = computed(() => 8)
const questionProgressLabel = computed(() => {
  const current = Math.min(answeredQuestionCount.value + 1, totalQuestionCount.value)
  return `第 ${current} 问`
})
const elapsedTimeLabel = ref('00:00')
const playbackTitle = computed(() => {
  if (isInterviewerSpeaking.value) return '面试官正在提问'
  if (isCapturing.value) return '正在收音'
  if (candidateCaptureState.value === 'processing') return '正在整理回答'
  return sessionReady.value ? '等待下一轮对话' : '语音链路准备中'
})
const playbackDetail = computed(() => {
  if (isInterviewerSpeaking.value) return '播放中 · 说完后自动开始收音'
  if (isCapturing.value) return '实时转写与最终修正文案会分别显示'
  if (candidateCaptureState.value === 'processing') return '等待本句最终修正文案回传'
  return '面试官提问后会自动开始收音'
})
const startButtonLabel = computed(() => {
  if (preloadingVoice.value && connectionState.value !== 'connected') return '预加载中'
  if (canStartOpeningTurn.value) return '开始语音面试'
  if (connectionState.value === 'connected') return '语音已就绪'
  return '连接语音会话'
})
const candidateCameraStatus = computed(() => {
  if (isCapturing.value) return '候选人正在讲话'
  if (candidateCaptureState.value === 'processing') return '正在整理回答'
  return '候选人等待回答'
})
const cameraStatusLabel = computed(() => {
  if (!isCameraSupported.value) return '当前环境不支持摄像头'
  if (startingCamera.value) return '摄像头分析连接中'
  if (videoStreamError.value || cameraError.value)
    return videoStreamError.value || cameraError.value
  return '摄像头未开启'
})
const cameraResolutionLabel = computed(() => {
  if (!cameraResolution.value.width || !cameraResolution.value.height) return '待检测'
  return `${cameraResolution.value.width} x ${cameraResolution.value.height}`
})

const videoGazeValue = computed(() => {
  const score = backendVideoAggregate.value?.avg_attention_score ?? attentionScore.value
  return typeof score === 'number' ? Math.round(score) : null
})
const videoGazeNote = computed(() => {
  const direction = backendVideoAggregate.value?.gaze_direction || gazeDirection.value
  return GAZE_LABELS[direction] || '等待检测'
})
const videoEmotionValue = computed(() => {
  const emotion = backendVideoAggregate.value?.dominant_emotion || currentEmotion.value
  return EMOTION_LABELS[emotion] || '待检测'
})
const videoEmotionNote = computed(() => {
  const emotion = backendVideoAggregate.value?.dominant_emotion || currentEmotion.value
  const score = emotionScores.value?.[emotion]
  return typeof score === 'number' ? `置信度 ${Math.round(score * 100)}%` : '无明显波动'
})
const videoAnalysisMetrics = computed(() => [
  {
    key: 'gaze',
    label: '视线停留',
    value: videoGazeValue.value === null ? '待检测' : `${videoGazeValue.value}%`,
    note: videoGazeNote.value
  },
  {
    key: 'pace',
    label: '语速',
    value: isCapturing.value ? '回答中' : '待检测',
    note: isCapturing.value ? '实时识别中' : '开始回答后统计'
  },
  {
    key: 'pause',
    label: '停顿次数',
    value: '待检测',
    note: isCapturing.value ? '本题统计中' : '开始回答后统计'
  },
  {
    key: 'emotion',
    label: '情绪',
    value: videoEmotionValue.value,
    note: videoEmotionNote.value
  }
])
const videoRecentAlerts = computed(() => {
  const backendAlerts = Array.isArray(backendVideoAggregate.value?.recent_alerts)
    ? backendVideoAggregate.value.recent_alerts
    : []
  const liveAlerts = Array.isArray(videoAlerts.value) ? videoAlerts.value : []
  const alerts = backendAlerts.length ? backendAlerts : liveAlerts
  if (alerts.length) return alerts.slice(-3).reverse()
  return [{ type: 'placeholder', message: '等待生成最近提醒' }]
})

const formatElapsedTime = () => {
  const totalSeconds = Math.floor((Date.now() - startedAt.value) / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  elapsedTimeLabel.value = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

const formatAlertTime = (value) => {
  if (!value) return '--:--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--'
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const scrollMessagesToBottom = async () => {
  await nextTick()
  if (messagesPanelRef.value) messagesPanelRef.value.scrollTop = messagesPanelRef.value.scrollHeight
}

const backToSetup = () => {
  router.push({
    name: 'InterviewWorkbench',
    query: {
      mode: 'voice',
      position: selectedPosition.value,
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const switchToTextInterview = () => {
  if (!currentThreadId.value) {
    backToSetup()
    return
  }
  router.push({
    name: 'AgentInterviewComp',
    query: {
      threadId: currentThreadId.value,
      mode: 'text',
      position: selectedPosition.value,
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const openInterviewResult = () => {
  if (!currentThreadId.value) return
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: currentThreadId.value,
      position: selectedPosition.value,
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const ensureAgentReady = async () => {
  if (!agentStore.isInitialized) await agentStore.initialize()
  if (!interviewAgentId.value) throw new Error('未找到可用的面试智能体')
}

const preloadVoiceSession = async () => {
  if (preloadPromise) return preloadPromise
  if (connectionState.value === 'connected' && preloadedSession.value) return preloadedSession.value

  preloadPromise = (async () => {
    preloadingVoice.value = true
    await ensureAgentReady()
    const payload =
      preloadedSession.value ||
      (await interviewVoiceApi.startVoiceSession({
        agent_id: interviewAgentId.value,
        position: selectedPosition.value,
        round: selectedRound.value,
        resume_id: selectedResumeId.value || undefined,
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
          ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {}),
          ...(sessionKey.value ? { session: sessionKey.value } : {}),
          ...(isVoiceOnlyMode.value ? { video: 'false' } : {})
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

const handleToggleCapture = async () => {
  if (isCapturing.value) {
    stopCandidateCapture()
    return
  }
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

const stopVideoStatusPolling = () => {
  if (videoStatusTimer) {
    window.clearInterval(videoStatusTimer)
    videoStatusTimer = null
  }
}

const resetVideoBackendState = () => {
  backendVideoStatus.value = { session_id: '', events_in_buffer: 0, status: 'inactive' }
  backendVideoAggregate.value = { has_data: false, event_count: 0, recent_alerts: [] }
}

const refreshVideoBackendState = async () => {
  const activeThreadId = currentThreadId.value
  if (!activeThreadId || !isVideoMode.value) {
    resetVideoBackendState()
    return
  }
  try {
    const [status, aggregate] = await Promise.all([
      videoApi.getStatus(activeThreadId),
      videoApi.getAggregate(activeThreadId)
    ])
    if (currentThreadId.value !== activeThreadId) return
    backendVideoStatus.value = status || backendVideoStatus.value
    backendVideoAggregate.value = aggregate || backendVideoAggregate.value
  } catch (err) {
    console.warn('refresh video backend state failed:', err)
  }
}

const startVideoStatusPolling = async () => {
  stopVideoStatusPolling()
  await refreshVideoBackendState()
  videoStatusTimer = window.setInterval(
    () => void refreshVideoBackendState(),
    VIDEO_STATUS_POLL_INTERVAL
  )
}

const handleToggleCamera = async () => {
  if (isCameraStreaming.value || isVideoMode.value) {
    disableVideoMode()
    stopVideoStatusPolling()
    resetVideoBackendState()
    return
  }

  startingCamera.value = true
  try {
    if (currentThreadId.value) {
      await enableVideoMode(currentThreadId.value)
    } else {
      await startCamera()
    }
    if (isVideoMode.value) await startVideoStatusPolling()
    const activeError = videoStreamError.value || cameraError.value
    if (!isCameraStreaming.value && activeError) message.error(activeError)
  } catch (err) {
    message.error(err?.message || '开启摄像头失败')
  } finally {
    startingCamera.value = false
  }
}

const maybeAutoStartCapture = async () => {
  if (!sessionReady.value || playbackState.value !== 'idle') return
  if (candidateCaptureState.value !== 'idle' || isCapturing.value) return
  if (lastVisibleMessage.value?.role !== 'assistant' || lastVisibleMessage.value.streaming) return
  try {
    await ensureMicrophoneReady()
    await startCandidateCapture()
  } catch (err) {
    console.warn('auto start candidate capture failed:', err)
  }
}

onBeforeUnmount(() => {
  stopVideoStatusPolling()
  if (elapsedTimeTimer) window.clearInterval(elapsedTimeTimer)
})

onMounted(async () => {
  formatElapsedTime()
  elapsedTimeTimer = window.setInterval(formatElapsedTime, 1000)
  if (!sessionKey.value && !routeThreadId.value) {
    router.replace({
      name: 'InterviewWorkbench',
      query: {
        mode: 'voice',
        position: selectedPosition.value,
        round: selectedRound.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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
  () =>
    visibleMessages.value
      .map((item) => `${item.id}:${item.content.length}:${item.streaming}`)
      .join('|'),
  scrollMessagesToBottom
)

watch(
  () => agentState.value?.coding_session?.status,
  (status) => {
    if (!['ready', 'coding'].includes(status)) return
    router.push({
      name: 'InterviewCodingWorkbench',
      query: {
        threadId: currentThreadId.value,
        position: selectedPosition.value,
        round: selectedRound.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
      }
    })
  }
)

watch(isVideoMode, async (active) => {
  if (active) {
    await startVideoStatusPolling()
    return
  }
  stopVideoStatusPolling()
  resetVideoBackendState()
})

watch(
  () => candidateCaptureState.value,
  async (nextState, previousState) => {
    if (nextState === 'idle' && previousState === 'disabled') await maybeAutoStartCapture()
  }
)
</script>

<style lang="less" scoped>
.voice-interview-view {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--gray-0);
  color: var(--gray-1000);
}

.voice-toolbar {
  min-height: 88px;
  padding: 20px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 2px solid var(--gray-1000);
}

.toolbar-title {
  margin: 0;
  font-family: Archivo, 'Noto Sans SC', sans-serif;
  font-size: 20px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--gray-1000);
}

.toolbar-subtitle {
  margin: 5px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--gray-600);
}

.toolbar-actions,
.camera-actions,
.camera-overlay-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-actions :deep(.ant-btn),
.camera-actions :deep(.ant-btn),
.playback-bar :deep(.ant-btn) {
  height: 34px;
  border-radius: 0;
  border-color: var(--gray-200);
  color: var(--gray-700);
  box-shadow: none;
  font-size: 13px;
}

.toolbar-actions :deep(.ant-btn-primary),
.playback-bar :deep(.ant-btn-primary) {
  border-color: var(--main-color);
  background: var(--main-color);
  color: var(--gray-0);
}

.interview-workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
}

.conversation-column {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--gray-200);
}

.playback-bar {
  padding: 18px 32px;
  display: flex;
  align-items: center;
  gap: 20px;
  border-bottom: 1px solid var(--gray-200);
}

.playback-wave,
.transcript-wave {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  flex: 0 0 auto;
}

.playback-wave {
  height: 34px;
}

.playback-wave span {
  width: 4px;
  height: 10px;
  background: var(--main-color);
  transform-origin: bottom;
}

.playback-wave span:nth-child(2),
.playback-wave span:nth-child(7) {
  height: 24px;
}

.playback-wave span:nth-child(3) {
  height: 34px;
}

.playback-wave span:nth-child(4),
.playback-wave span:nth-child(6) {
  height: 18px;
}

.playback-wave span:nth-child(5) {
  height: 29px;
}

.playback-wave span:nth-child(8) {
  height: 8px;
}

.playback-wave.active span {
  animation: playback-wave 900ms ease-in-out infinite alternate;
}

.playback-wave.active span:nth-child(2),
.transcript-wave.active span:nth-child(2) {
  animation-delay: 100ms;
}

.playback-wave.active span:nth-child(3),
.transcript-wave.active span:nth-child(3) {
  animation-delay: 200ms;
}

.playback-wave.active span:nth-child(4),
.transcript-wave.active span:nth-child(4) {
  animation-delay: 300ms;
}

.playback-copy {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.playback-copy strong {
  font-size: 15px;
  color: var(--gray-1000);
}

.playback-copy span {
  font-size: 13px;
  color: var(--gray-500);
}

.conversation-stream {
  flex: 1;
  min-height: 240px;
  overflow-y: auto;
  padding: 24px 32px;
}

.message-row {
  display: grid;
  grid-template-columns: 60px minmax(0, 620px);
  column-gap: 18px;
  margin-bottom: 22px;
}

.message-role,
.section-header,
.transcript-header {
  font-size: 11px;
  line-height: 1.4;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--gray-600);
}

.message-content {
  font-size: 15px;
  line-height: 1.75;
  color: var(--gray-700);
  white-space: pre-wrap;
  word-break: break-word;
}

.message-row.user .message-role {
  color: var(--main-800);
}

.message-row.user .message-content {
  padding-left: 18px;
  border-left: 2px solid var(--main-color);
}

.streaming-mark {
  color: var(--gray-500);
}

.empty-state {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  color: var(--gray-600);
}

.empty-state div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.empty-state strong {
  font-size: 15px;
  color: var(--gray-1000);
}

.empty-state span {
  font-size: 13px;
}

.error-banner {
  margin-bottom: 16px;
  padding: 10px 12px;
  border: 1px solid var(--color-error-500);
  color: var(--color-error-700);
  font-size: 13px;
}

.transcript-dock {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  padding: 18px 32px 22px;
  border-top: 1px solid var(--gray-200);
}

.transcript-header,
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.transcript-wave {
  height: 12px;
  gap: 2px;
}

.transcript-wave span {
  width: 3px;
  height: 6px;
  background: var(--gray-400);
  transform-origin: bottom;
}

.transcript-wave span:nth-child(2) {
  height: 11px;
}

.transcript-wave span:nth-child(3) {
  height: 8px;
}

.transcript-wave span:nth-child(4) {
  height: 4px;
}

.transcript-wave.active span {
  background: var(--main-color);
  animation: transcript-wave 800ms ease-in-out infinite alternate;
}

.transcript-content {
  min-height: 64px;
  margin-top: 10px;
  padding: 12px 14px;
  border: 1px solid var(--gray-200);
  background: var(--gray-50);
  font-size: 14px;
  line-height: 1.6;
  color: var(--gray-700);
  white-space: pre-wrap;
  word-break: break-word;
}

.transcript-content.placeholder {
  color: var(--gray-500);
}

.sync-badge {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 8px;
  border: 1px solid var(--gray-200);
  background: var(--gray-100);
  color: var(--gray-600);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0;
}

.observation-column {
  min-width: 0;
  overflow-y: auto;
  padding-bottom: 24px;
}

.camera-block {
  padding: 20px 24px 0;
}

.camera-stage {
  position: relative;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: var(--gray-1000);
}

.camera-video {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.camera-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--gray-400);
  font-size: 13px;
}

.camera-empty :deep(.anticon) {
  font-size: 24px;
}

.camera-overlay {
  position: absolute;
  right: 12px;
  bottom: 12px;
  left: 12px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  pointer-events: none;
}

.camera-overlay-group {
  gap: 6px;
  flex-wrap: wrap;
}

.live-badge,
.camera-status,
.camera-metrics span {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--gray-700);
  color: var(--gray-400);
  background: var(--gray-1000);
  font-size: 11px;
  white-space: nowrap;
}

.live-badge {
  gap: 6px;
  border-color: var(--gray-0);
  background: var(--gray-0);
  color: var(--gray-1000);
  font-weight: 700;
  letter-spacing: 0.08em;
}

.live-badge i {
  width: 6px;
  height: 6px;
  background: var(--main-color);
}

.camera-actions {
  margin-top: 12px;
}

.camera-actions :deep(.ant-btn) {
  flex: 1;
  justify-content: flex-start;
}

.observation-section {
  padding: 22px 24px 0;
}

.observation-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 12px;
  border-top: 1px solid var(--gray-200);
}

.observation-item {
  min-width: 0;
  padding: 12px 14px 12px 0;
  border-bottom: 1px solid var(--gray-100);
}

.observation-item:nth-child(odd) {
  border-right: 1px solid var(--gray-100);
  padding-right: 14px;
}

.observation-item:nth-child(even) {
  padding-right: 0;
  padding-left: 14px;
}

.observation-item span,
.observation-item small {
  display: block;
  color: var(--gray-500);
}

.observation-item span {
  font-size: 12px;
}

.observation-item strong {
  display: block;
  margin-top: 3px;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
  color: var(--gray-1000);
  overflow-wrap: anywhere;
}

.observation-item small {
  margin-top: 5px;
  font-size: 12px;
  line-height: 1.4;
}

.alert-list {
  margin-top: 12px;
}

.alert-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--gray-100);
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-700);
}

.alert-row time {
  flex: 0 0 auto;
  color: var(--gray-500);
  font-size: 12px;
}

@keyframes playback-wave {
  from {
    transform: scaleY(0.45);
    opacity: 0.55;
  }
  to {
    transform: scaleY(1.2);
    opacity: 1;
  }
}

@keyframes transcript-wave {
  from {
    transform: scaleY(0.55);
  }
  to {
    transform: scaleY(1.35);
  }
}

@media (max-width: 1100px) {
  .interview-workspace {
    grid-template-columns: minmax(0, 1fr) 360px;
  }
}

@media (max-width: 900px) {
  .voice-toolbar {
    align-items: flex-start;
    flex-direction: column;
    padding: 18px 20px;
  }

  .toolbar-actions {
    flex-wrap: wrap;
  }

  .interview-workspace {
    grid-template-columns: 1fr;
  }

  .conversation-column {
    border-right: 0;
    border-bottom: 2px solid var(--gray-1000);
  }

  .observation-column {
    min-height: auto;
  }
}

@media (max-width: 640px) {
  .playback-bar,
  .conversation-stream,
  .transcript-dock {
    padding-right: 20px;
    padding-left: 20px;
  }

  .playback-bar {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .playback-bar :deep(.ant-btn) {
    margin-left: 54px;
  }

  .message-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .transcript-dock {
    grid-template-columns: 1fr;
  }
}
</style>
