<template>
  <div class="voice-interview-view">
    <div class="voice-toolbar">
      <div class="toolbar-copy">
        <div class="toolbar-eyebrow">
          <span class="eyebrow-pill">Voice Interview Studio</span>
          <span class="eyebrow-meta">{{ selectedPosition }}</span>
          <span class="eyebrow-meta">{{ selectedRound }}</span>
        </div>
        <div class="toolbar-title">语音模拟面试</div>
        <div class="toolbar-subtitle">
          豆包负责语音播报，候选人语音由阿里云实时转文字后回到原面试 Agent 链路，整页同步展示连接、播报、收音与镜头状态。
        </div>
      </div>

      <div class="toolbar-actions">
        <span class="status-badge toolbar-action-item" :class="`tone-${connectionTone}`">
          <ApiOutlined />
          {{ connectionStatusLabel }}
        </span>
        <span class="status-badge toolbar-action-item" :class="`tone-${playbackTone}`">
          <AudioOutlined />
          {{ playbackStatusLabel }}
        </span>
        <span class="status-badge toolbar-action-item" :class="`tone-${captureTone}`">
          <UserOutlined />
          {{ captureStatusLabel }}
        </span>
        <a-button class="toolbar-action-item toolbar-action-button" @click="backToSetup">调整配置</a-button>
        <a-button class="toolbar-action-item toolbar-action-button" @click="openResumeCenter">我的简历</a-button>
        <a-button
          class="toolbar-action-item toolbar-action-button"
          :disabled="!currentThreadId"
          @click="openInterviewResult"
        >
          面试结果
        </a-button>
      </div>
    </div>

    <div class="voice-stage">
      <section class="role-card status-card" :class="`state-${interviewerVisualState}`">
        <div class="role-header">
          <div class="role-heading">
            <div class="role-label">状态驾驶舱</div>
            <div class="role-caption">左侧统一查看当前链路状态、面试进度与线程信息</div>
          </div>
          <div class="status-header-actions">
            <a-button type="primary" :loading="startingVoice" @click="handleStartVoiceInterview">
              {{ startButtonLabel }}
            </a-button>
            <a-button :disabled="playbackState !== 'playing'" @click="interrupt">停止播放</a-button>
            <span class="role-pill" :class="`tone-${liveStatusTone}`">{{ liveStatusShortLabel }}</span>
          </div>
        </div>

        <div class="status-hero">
          <div class="interviewer-visual" :class="`is-${visualPulseState}`">
            <div class="interviewer-ring"></div>
            <div class="interviewer-core">
              <div v-if="visualPulseState === 'speaking'" class="wave-bars" aria-hidden="true">
                <span v-for="bar in 6" :key="`wave-${bar}`" class="wave-bar"></span>
              </div>
              <div v-else-if="visualPulseState === 'waiting'" class="waiting-dots" aria-hidden="true">
                <span v-for="dot in 3" :key="`waiting-${dot}`" class="waiting-dot"></span>
              </div>
              <div v-else class="interviewer-idle-icon" aria-hidden="true"></div>
            </div>
          </div>

          <div class="hero-copy">
            <div class="hero-kicker">当前现场</div>
            <div class="hero-title">{{ liveStatusTitle }}</div>
            <div class="hero-text">{{ liveStatusDescription }}</div>

            <div class="hero-meter" :class="{ active: visualPulseState === 'speaking' }" aria-hidden="true">
              <span v-for="bar in 12" :key="`hero-meter-${bar}`" class="hero-meter-bar"></span>
            </div>
          </div>
        </div>

        <div class="status-grid">
          <article
            v-for="card in dashboardCards"
            :key="card.key"
            class="status-info-card"
            :class="`tone-${card.tone}`"
          >
            <div class="status-info-icon">
              <component :is="card.icon" />
            </div>
            <div class="status-info-body">
              <div class="status-info-label">{{ card.label }}</div>
              <div class="status-info-value">{{ card.value }}</div>
              <div class="status-info-note">{{ card.note }}</div>
            </div>
          </article>
        </div>

        <div class="workflow-strip">
          <div
            v-for="step in workflowSteps"
            :key="step.key"
            class="workflow-step"
            :class="`state-${step.state}`"
          >
            <span class="workflow-dot"></span>
            <div class="workflow-content">
              <div class="workflow-title">{{ step.label }}</div>
              <div class="workflow-text">{{ step.detail }}</div>
            </div>
          </div>
        </div>

        <AgentPanel
          class="status-workbench-panel"
          :agent-state="agentState"
          :thread-id="currentThreadId"
          embedded
          @refresh="handleAgentStateRefresh"
        />
      </section>

      <section class="role-card camera-card" :class="{ 'is-streaming': isCameraStreaming }">
        <div class="role-header">
          <div class="role-heading">
            <div class="role-label">面试者镜头</div>
            <div class="role-caption">右上区域会把摄像头观察事件同步到后端，并在下一轮提问前注给面试智能体</div>
          </div>
          <div class="role-actions camera-role-actions">
            <a-button
              class="camera-action-button"
              type="primary"
              :disabled="!canStartCapture"
              :loading="startingCapture"
              @click="handleStartCapture"
            >
              开始回答
            </a-button>
            <a-button class="camera-action-button" :disabled="!isCapturing" @click="handleStopCapture">
              停止回答
            </a-button>
            <a-button
              class="camera-action-button camera-action-button-wide"
              :loading="startingCamera"
              @click="handleStartCameraPreview"
            >
              <template #icon>
                <ReloadOutlined />
              </template>
              {{ cameraActionLabel }}
            </a-button>
          </div>
        </div>

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
            <div class="camera-empty-icon">
              <CameraOutlined />
            </div>
            <div class="camera-empty-title">
              {{ isCameraSupported ? '等待连接摄像头' : '当前环境不支持摄像头' }}
            </div>
            <div class="camera-empty-text">{{ cameraStatusLabel }}</div>
            <a-button v-if="isCameraSupported" type="primary" @click="handleStartCameraPreview">
              开启摄像头
            </a-button>
          </div>

          <div v-if="isCameraStreaming" class="camera-overlay camera-overlay-left">
            <span class="camera-live-pill">LIVE</span>
            <span class="camera-overlay-pill" :class="`tone-${cameraStatusTone}`">
              {{ cameraStatusLabel }}
            </span>
          </div>

          <div v-if="isCameraStreaming" class="camera-overlay camera-overlay-right">
            <span class="camera-metric-pill">{{ cameraResolutionLabel }}</span>
            <span class="camera-metric-pill">{{ cameraFps || 0 }} FPS</span>
            <span v-if="isVideoMode" class="camera-metric-pill">{{ analysisFps || 0 }} AI FPS</span>
          </div>

          <div class="camera-footer">
            <div class="camera-footer-meter" :class="{ active: candidateVisualState === 'speaking' }">
              <span v-for="bar in 8" :key="`candidate-meter-${bar}`" class="camera-footer-bar"></span>
            </div>
            <div class="camera-footer-copy">
              <div class="camera-footer-title">{{ candidateStatusTitle }}</div>
              <div class="camera-footer-text">{{ candidateStatusDescription }}</div>
            </div>
          </div>
        </div>

        <div class="camera-analysis-board">
          <div class="camera-analysis-header">
            <div class="camera-analysis-copy">
              <div class="camera-analysis-title">候选人观察摘要</div>
              <div class="camera-analysis-subtitle">{{ videoSyncNote }}</div>
            </div>
            <span class="mini-status-badge" :class="`tone-${videoBackendTone}`">
              {{ videoBackendStatusLabel }}
            </span>
          </div>

          <div class="camera-analysis-grid">
            <article
              v-for="metric in videoAnalysisMetrics"
              :key="metric.key"
              class="camera-analysis-card"
              :class="`tone-${metric.tone}`"
            >
              <div class="camera-analysis-label">{{ metric.label }}</div>
              <div class="camera-analysis-value">{{ metric.value }}</div>
              <div class="camera-analysis-note">{{ metric.note }}</div>
            </article>
          </div>

          <div class="camera-alerts">
            <div class="camera-alerts-title">最近提醒</div>
            <div class="camera-alert-list">
              <span
                v-for="(alert, index) in videoRecentAlerts"
                :key="`${alert.type || 'alert'}-${index}`"
                class="camera-alert-pill"
              >
                {{ alert.message }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div class="voice-content-container">
      <div class="voice-shell">
        <div class="panel-header">
          <div>
            <div class="panel-title">文本记录</div>
            <div class="panel-subtitle">
              用于跟进当前线程上下文、语音播报内容、候选人转写结果以及最新的提交状态。
            </div>
          </div>

          <div class="panel-meta">
            <span v-for="tag in sessionMetaTags" :key="tag" class="panel-tag">{{ tag }}</span>
          </div>
        </div>

        <div class="record-summary-grid">
          <article
            v-for="stat in recordStats"
            :key="stat.key"
            class="record-summary-card"
            :class="`tone-${stat.tone}`"
          >
            <div class="record-summary-icon">
              <component :is="stat.icon" />
            </div>
            <div class="record-summary-label">{{ stat.label }}</div>
            <div class="record-summary-value">{{ stat.value }}</div>
            <div class="record-summary-note">{{ stat.note }}</div>
          </article>
        </div>

        <div class="messages-panel" ref="messagesPanelRef">
          <div v-if="error" class="error-banner">{{ error }}</div>

          <div v-if="visibleMessages.length === 0" class="empty-state">
            <div class="empty-visual">
              <AudioOutlined />
            </div>
            <div class="empty-title">语音会话尚未开始</div>
            <div class="empty-text">
              点击“开始语音面试”后，面试官会直接以语音形式发起第一问，随后候选人可在右上区域开始回答。
            </div>
            <a-button type="primary" :loading="startingVoice" @click="handleStartVoiceInterview">
              {{ startButtonLabel }}
            </a-button>
          </div>

          <div
            v-for="item in visibleMessages"
            :key="item.id"
            class="message-row"
            :class="item.role === 'assistant' ? 'assistant' : 'user'"
          >
            <div class="message-role">
              <span class="message-role-pill">{{ item.role === 'assistant' ? '面试官' : '你' }}</span>
            </div>
            <div class="message-bubble">
              {{ item.content }}
              <span v-if="item.streaming" class="streaming-dot"></span>
            </div>
          </div>
        </div>

        <div class="input-panel">
          <div class="capture-panel">
            <div class="capture-status">
              <div class="capture-title-row">
                <div class="capture-title">候选人语音输入</div>
                <span class="mini-status-badge" :class="`tone-${captureTone}`">
                  {{ captureStatusLabel }}
                </span>
              </div>
              <div class="capture-subtitle">{{ captureHintLabel }}</div>
            </div>

            <div class="input-actions">
              <span class="input-hint">
                当前线程：{{ currentThreadId || '未创建' }} · 麦克风权限：{{ micPermissionLabel }}
              </span>
            </div>
          </div>

          <div class="transcript-shell">
            <div class="transcript-card">
              <div class="transcript-card-header">
                <div class="transcript-label">实时转写</div>
                <div class="transcript-meter" :class="{ active: isCapturing }" aria-hidden="true">
                  <span v-for="bar in 6" :key="`partial-meter-${bar}`" class="transcript-meter-bar"></span>
                </div>
              </div>
              <div class="transcript-content" :class="{ placeholder: !partialTranscript }">
                {{ partialTranscript || '开始回答后，这里会实时显示当前识别中的文本。' }}
              </div>
            </div>

            <div class="transcript-card">
              <div class="transcript-card-header">
                <div class="transcript-label">最终修正文案</div>
                <span class="mini-status-badge" :class="`tone-${submitTone}`">
                  {{ submitStatusLabel }}
                </span>
              </div>
              <div class="transcript-content" :class="{ placeholder: !finalTranscript }">
                {{ finalTranscript || '句子结束后，这里会显示提交给面试 Agent 的最终文本。' }}
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  AudioOutlined,
  CameraOutlined,
  MessageOutlined,
  PartitionOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  UserOutlined
} from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'

import { interviewVoiceApi } from '@/apis/interview_voice'
import { videoApi } from '@/apis/video_api'
import AgentPanel from '@/components/AgentPanel.vue'
import { useVideoEventStream } from '@/composables/useVideoEventStream'
import { useVoiceInterviewSession } from '@/composables/useVoiceInterviewSession'
import { useAgentStore } from '@/stores/agent'
import { useUserStore } from '@/stores/user'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const DEFAULT_ROUND = '初试'
const VIDEO_STATUS_POLL_INTERVAL = 1200

const EMOTION_LABELS = {
  happy: '愉悦',
  confident: '自信',
  neutral: '平稳',
  fear: '紧张',
  sad: '低落',
  angry: '烦躁',
  surprised: '惊讶',
  disgust: '抗拒'
}

const POSTURE_LABELS = {
  upright: '坐姿端正',
  leaning_forward: '身体前倾',
  leaning_back: '身体后仰',
  head_tilt: '头部偏斜',
  slouching: '含胸驼背'
}

const GAZE_LABELS = {
  center: '视线居中',
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
const backendVideoStatus = ref({
  session_id: '',
  events_in_buffer: 0,
  status: 'inactive'
})
const backendVideoAggregate = ref({
  has_data: false,
  event_count: 0,
  recent_alerts: []
})

let preloadPromise = null
let videoStatusTimer = null

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const selectedResumeId = computed(() => {
  const raw = String(route.query.resumeId || '').trim()
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
})
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
  posture,
  postureScore,
  resolution: cameraResolution,
  videoRef: cameraVideoRef
} = videoEventStream

const currentThreadId = computed(() => threadId.value || routeThreadId.value)
const visibleMessages = computed(() => messages.value)
const lastVisibleMessage = computed(() => visibleMessages.value[visibleMessages.value.length - 1] || null)
const lastVisibleMessageRole = computed(() => lastVisibleMessage.value?.role || '')
const canStartOpeningTurn = computed(() => {
  return connectionState.value === 'connected' && visibleMessages.value.length === 0 && !hasStartedOpeningTurn.value
})
const canStartCapture = computed(() => {
  return sessionReady.value && candidateCaptureState.value === 'idle' && !isCapturing.value
})

const getLabel = (value, mapping, fallback = '待检测') => {
  const normalizedValue = String(value || '').trim()
  if (!normalizedValue) return fallback
  return mapping[normalizedValue] || normalizedValue
}

const getScoreTone = (score, high = 80, medium = 60) => {
  if (typeof score !== 'number') return 'idle'
  if (score >= high) return 'active'
  if (score >= medium) return 'warning'
  return 'error'
}

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
const captureStatusLabel = computed(() => {
  if (isCapturing.value) return '正在收音'
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

const connectionTone = computed(() => {
  if (connectionState.value === 'connected') return 'active'
  if (connectionState.value === 'connecting') return 'warning'
  if (connectionState.value === 'closed') return 'error'
  return 'idle'
})
const playbackTone = computed(() => {
  if (playbackState.value === 'playing') return 'active'
  return 'idle'
})
const captureTone = computed(() => {
  if (isCapturing.value) return 'active'
  if (candidateCaptureState.value === 'listening') return 'active'
  if (candidateCaptureState.value === 'processing') return 'warning'
  if (candidateCaptureState.value === 'disabled') return 'idle'
  return 'active-soft'
})
const submitTone = computed(() => {
  if (candidateCaptureState.value === 'processing') return 'warning'
  if (finalTranscript.value) return 'active'
  return 'idle'
})
const cameraStatusTone = computed(() => {
  if (isCameraStreaming.value) return 'active'
  if (cameraError.value || videoStreamError.value) return 'error'
  if (startingCamera.value) return 'warning'
  return 'idle'
})
const liveStatusTone = computed(() => {
  if (isInterviewerSpeaking.value || isCapturing.value) return 'active'
  if (candidateCaptureState.value === 'processing' || connectionState.value === 'connecting') return 'warning'
  if (sessionReady.value) return 'active-soft'
  return 'idle'
})

const visualPulseState = computed(() => {
  if (isInterviewerSpeaking.value || isCapturing.value) return 'speaking'
  if (candidateCaptureState.value === 'processing' || isInterviewerWaiting.value) return 'waiting'
  return 'idle'
})
const liveStatusShortLabel = computed(() => {
  if (isInterviewerSpeaking.value) return '面试官播报中'
  if (isCapturing.value) return '候选人回答中'
  if (candidateCaptureState.value === 'processing') return '整理回答中'
  if (sessionReady.value) return '会话已就绪'
  return '等待开始'
})
const liveStatusTitle = computed(() => {
  if (isInterviewerSpeaking.value) return '面试官正在发问'
  if (isCapturing.value) return '你正在回答'
  if (candidateCaptureState.value === 'processing') return '系统正在整理你的回答'
  if (canStartOpeningTurn.value) return '语音面试待开始'
  if (sessionReady.value) return '等待下一轮对话'
  return '准备建立语音链路'
})
const liveStatusDescription = computed(() => {
  if (isInterviewerSpeaking.value) return '此时会持续语音播报问题，左侧状态条与下方记录会同步更新。'
  if (isCapturing.value) return '麦克风已打开，实时转写会马上出现在下方文本记录区域。'
  if (candidateCaptureState.value === 'processing') return '系统正在等待最终修正文本回传，并准备交给面试 Agent 继续追问。'
  if (canStartOpeningTurn.value) return '点击下方按钮后，系统会发起第一问并自动进入完整流程。'
  if (sessionReady.value) return '链路已经就绪，等待面试官发问或候选人开始回答。'
  return '页面已进入语音面试台，正在准备连接会话与基础设备。'
})

const backendEventCount = computed(() => {
  const aggregatedCount = Number(backendVideoAggregate.value?.event_count || 0)
  const bufferedCount = Number(backendVideoStatus.value?.events_in_buffer || 0)
  return aggregatedCount || bufferedCount || 0
})
const videoEmotionLabel = computed(() => {
  const realtimeEmotion = currentEmotion.value
  const backendEmotion = backendVideoAggregate.value?.dominant_emotion
  const preferredEmotion =
    realtimeEmotion && realtimeEmotion !== 'neutral' ? realtimeEmotion : backendEmotion || realtimeEmotion
  return getLabel(preferredEmotion, EMOTION_LABELS)
})
const videoEmotionConfidence = computed(() => {
  const realtimeEmotion = currentEmotion.value
  const backendEmotion = backendVideoAggregate.value?.dominant_emotion
  const score = emotionScores.value?.[realtimeEmotion]
  const trendLabel = backendEmotion ? getLabel(backendEmotion, EMOTION_LABELS) : ''

  if (typeof score !== 'number') {
    return trendLabel ? `趋势 ${trendLabel}` : '等待首帧表情数据'
  }

  const confidenceText = `置信度 ${Math.round(score * 100)}%`
  if (trendLabel && backendEmotion !== realtimeEmotion) {
    return `${confidenceText} · 趋势 ${trendLabel}`
  }
  return confidenceText
})
const videoAttentionValue = computed(() => {
  const backendAttention = backendVideoAggregate.value?.avg_attention_score
  if (typeof backendAttention === 'number') return Math.round(backendAttention)
  if (typeof attentionScore.value === 'number') return Math.round(attentionScore.value)
  return null
})
const videoAttentionLabel = computed(() => {
  if (typeof videoAttentionValue.value !== 'number') return '待检测'
  return `${videoAttentionValue.value} 分`
})
const videoAttentionNote = computed(() => {
  if (typeof videoAttentionValue.value !== 'number') return '开启摄像头后会持续评估专注度'
  if (videoAttentionValue.value >= 80) return '专注度稳定，适合继续深入提问'
  if (videoAttentionValue.value >= 60) return '专注度中等，可适度调整提问节奏'
  return '注意力偏低，建议下一轮问题先缓和再追问'
})
const videoPostureLabel = computed(() => {
  const backendPosture =
    backendVideoAggregate.value?.current_posture || backendVideoAggregate.value?.dominant_posture
  return getLabel(backendPosture || posture.value, POSTURE_LABELS)
})
const videoPostureScoreValue = computed(() => {
  const backendPostureScore = backendVideoAggregate.value?.avg_posture_score
  if (typeof backendPostureScore === 'number') return Math.round(backendPostureScore)
  if (typeof postureScore.value === 'number') return Math.round(postureScore.value)
  return null
})
const videoGazeLabel = computed(() => {
  return getLabel(backendVideoAggregate.value?.gaze_direction || gazeDirection.value, GAZE_LABELS, '视线待检测')
})
const videoBackendStatusLabel = computed(() => {
  if (!currentThreadId.value) return '等待线程'
  if (!isVideoMode.value) return '未接入'
  if (backendEventCount.value > 0) return '已同步'
  return '同步中'
})
const videoBackendTone = computed(() => {
  if (!currentThreadId.value || !isVideoMode.value) return 'idle'
  if (backendEventCount.value > 0) return 'active'
  return 'warning'
})
const videoSyncNote = computed(() => {
  if (!currentThreadId.value) return '线程建立后，观察事件才会汇总进后端并注给面试智能体'
  if (!isVideoMode.value) return '开启摄像头后，会把表情、注意力与坐姿事件同步到后端'
  if (backendEventCount.value > 0) {
    return `后端已累积 ${backendEventCount.value} 条观察，面试官下次发言前会自动参考这些状态`
  }
  return '正在等待首批表情与姿态事件同步到后端'
})
const videoRecentAlerts = computed(() => {
  const backendAlerts = Array.isArray(backendVideoAggregate.value?.recent_alerts)
    ? backendVideoAggregate.value.recent_alerts
    : []
  if (backendAlerts.length > 0) return backendAlerts.slice(-3)

  const liveAlerts = Array.isArray(videoAlerts.value) ? videoAlerts.value.slice(-3) : []
  if (liveAlerts.length > 0) return liveAlerts

  return [
    {
      type: 'placeholder',
      message: currentThreadId.value ? '等待生成最近提醒' : '开始语音面试后，这里会持续显示最近提醒'
    }
  ]
})
const videoAnalysisMetrics = computed(() => [
  {
    key: 'attention',
    label: '注意力',
    value: videoAttentionLabel.value,
    note: videoAttentionNote.value,
    tone: getScoreTone(videoAttentionValue.value)
  },
  {
    key: 'emotion',
    label: '情绪状态',
    value: videoEmotionLabel.value,
    note: videoEmotionConfidence.value,
    tone: currentEmotion.value && currentEmotion.value !== 'neutral' ? 'warning' : 'active-soft'
  },
  {
    key: 'posture',
    label: '坐姿 / 肢体',
    value: videoPostureLabel.value,
    note:
      typeof videoPostureScoreValue.value === 'number'
        ? `${videoGazeLabel.value} · 姿态分 ${videoPostureScoreValue.value}`
        : videoGazeLabel.value,
    tone: getScoreTone(videoPostureScoreValue.value)
  },
  {
    key: 'backend',
    label: '后端汇总',
    value: videoBackendStatusLabel.value,
    note: backendEventCount.value > 0 ? `已汇总 ${backendEventCount.value} 条观察事件` : '等待首批观察事件',
    tone: videoBackendTone.value
  }
])

const cameraStatusLabel = computed(() => {
  if (startingCamera.value) return '摄像头分析连接中'
  if (isVideoMode.value) return '摄像头分析中'
  if (isCameraStreaming.value) return '摄像头已连接'
  if (!isCameraSupported.value) return '浏览器当前不支持摄像头能力'
  if (videoStreamError.value) return videoStreamError.value
  if (cameraError.value) return cameraError.value
  return '点击后可开启摄像头并同步面试观察'
})
const cameraResolutionLabel = computed(() => {
  if (!cameraResolution.value.width || !cameraResolution.value.height) return '待检测'
  return `${cameraResolution.value.width} x ${cameraResolution.value.height}`
})
const cameraActionLabel = computed(() => {
  if (startingCamera.value) return '连接中'
  if (isVideoMode.value) return '重启摄像头分析'
  return '开启摄像头分析'
})
const candidateVisualState = computed(() => {
  if (isCapturing.value) return 'speaking'
  if (candidateCaptureState.value === 'processing') return 'processing'
  if (candidateCaptureState.value === 'disabled') return 'locked'
  if (isCameraStreaming.value) return 'ready'
  return 'idle'
})
const candidateStatusTitle = computed(() => {
  if (isCapturing.value) return '麦克风收音中'
  if (candidateCaptureState.value === 'processing') return '识别处理中'
  if (candidateCaptureState.value === 'disabled') return '等待面试官结束播报'
  if (isVideoMode.value) return '表情与姿态分析中'
  if (isCameraStreaming.value) return '镜头预览已就绪'
  return '摄像头待连接'
})
const candidateStatusDescription = computed(() => {
  if (videoStreamError.value && !isCameraStreaming.value) return videoStreamError.value
  if (cameraError.value && !isCameraStreaming.value) return cameraError.value
  if (isVideoMode.value) return videoSyncNote.value
  return captureHintLabel.value
})
const submitStatusLabel = computed(() => {
  if (candidateCaptureState.value === 'processing') return '提交中'
  if (finalTranscript.value) return '已更新'
  return '待生成'
})
const threadDisplayLabel = computed(() => {
  if (!currentThreadId.value) return '未创建'
  if (currentThreadId.value.length <= 12) return currentThreadId.value
  return `${currentThreadId.value.slice(0, 6)}...${currentThreadId.value.slice(-4)}`
})

const dashboardCards = computed(() => [
  {
    key: 'position',
    icon: PartitionOutlined,
    label: '面试岗位',
    value: selectedPosition.value,
    note: `轮次：${selectedRound.value}`,
    tone: 'active-soft'
  },
  {
    key: 'connection',
    icon: ApiOutlined,
    label: '语音链路',
    value: connectionStatusLabel.value,
    note: currentThreadId.value ? `线程：${threadDisplayLabel.value}` : '开始后会自动创建线程',
    tone: connectionTone.value
  },
  {
    key: 'mic',
    icon: SafetyCertificateOutlined,
    label: '麦克风权限',
    value: micPermissionLabel.value,
    note: captureHintLabel.value,
    tone: micPermissionState.value === 'denied' ? 'error' : micPermissionState.value === 'granted' ? 'active' : 'warning'
  },
  {
    key: 'camera',
    icon: CameraOutlined,
    label: '镜头状态',
    value: isVideoMode.value ? '分析中' : isCameraStreaming.value ? '已预览' : '未预览',
    note: videoSyncNote.value,
    tone: cameraStatusTone.value
  }
])

const workflowSteps = computed(() => [
  {
    key: 'connect',
    label: '语音连接',
    detail: connectionStatusLabel.value,
    state:
      connectionState.value === 'connected'
        ? 'done'
        : connectionState.value === 'connecting'
          ? 'current'
          : 'pending'
  },
  {
    key: 'question',
    label: '面试官提问',
    detail: isInterviewerSpeaking.value ? '正在语音播报问题' : '等待问题播报',
    state: isInterviewerSpeaking.value ? 'current' : hasStartedOpeningTurn.value ? 'done' : 'pending'
  },
  {
    key: 'answer',
    label: '候选人回答',
    detail: captureStatusLabel.value,
    state: isCapturing.value ? 'current' : finalTranscript.value ? 'done' : 'pending'
  },
  {
    key: 'submit',
    label: '文本入链',
    detail: candidateCaptureState.value === 'processing' ? '正在提交给 Agent' : submitStatusLabel.value,
    state: candidateCaptureState.value === 'processing' ? 'current' : finalTranscript.value ? 'done' : 'pending'
  }
])

const sessionMetaTags = computed(() => [
  selectedPosition.value,
  selectedRound.value,
  currentThreadId.value ? `线程 ${threadDisplayLabel.value}` : '等待创建线程'
])

const recordStats = computed(() => [
  {
    key: 'messages',
    icon: MessageOutlined,
    label: '对话消息',
    value: `${visibleMessages.value.length}`,
    note: visibleMessages.value.length > 0 ? '包含面试官与候选人最新上下文' : '会话开始后自动累积',
    tone: visibleMessages.value.length > 0 ? 'active-soft' : 'idle'
  },
  {
    key: 'thread',
    icon: ApiOutlined,
    label: '当前线程',
    value: threadDisplayLabel.value,
    note: currentThreadId.value ? '本轮面试的主线程标识' : '启动后自动生成',
    tone: currentThreadId.value ? 'active-soft' : 'idle'
  },
  {
    key: 'capture',
    icon: AudioOutlined,
    label: '候选人收音',
    value: captureStatusLabel.value,
    note: captureHintLabel.value,
    tone: captureTone.value
  }
])

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
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

const handleAgentStateRefresh = async () => {}

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

const stopVideoStatusPolling = () => {
  if (videoStatusTimer) {
    window.clearInterval(videoStatusTimer)
    videoStatusTimer = null
  }
}

const resetVideoBackendState = () => {
  backendVideoStatus.value = {
    session_id: '',
    events_in_buffer: 0,
    status: 'inactive'
  }
  backendVideoAggregate.value = {
    has_data: false,
    event_count: 0,
    recent_alerts: []
  }
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
  videoStatusTimer = window.setInterval(() => {
    void refreshVideoBackendState()
  }, VIDEO_STATUS_POLL_INTERVAL)
}

const handleStartCameraPreview = async ({ silent = false } = {}) => {
  if (startingCamera.value) return

  startingCamera.value = true
  try {
    stopVideoStatusPolling()

    if (isVideoMode.value) {
      disableVideoMode()
    }

    if (currentThreadId.value) {
      await enableVideoMode(currentThreadId.value)
    } else {
      await startCamera()
    }

    if (isVideoMode.value) {
      await startVideoStatusPolling()
    } else {
      resetVideoBackendState()
    }

    const activeError = videoStreamError.value || cameraError.value
    if (!isCameraStreaming.value && activeError && !silent) {
      message.error(activeError)
    }
  } catch (err) {
    if (!silent) {
      message.error(err?.message || '开启摄像头失败')
    }
  } finally {
    startingCamera.value = false
  }
}

const maybeAutoStartCapture = async () => {
  if (!sessionReady.value) return
  if (playbackState.value !== 'idle') return
  if (candidateCaptureState.value !== 'idle') return
  if (isCapturing.value) return
  if (lastVisibleMessageRole.value !== 'assistant') return
  if (lastVisibleMessage.value?.streaming) return

  try {
    await ensureMicrophoneReady()
    await startCandidateCapture()
  } catch (err) {
    console.warn('auto start candidate capture failed:', err)
  }
}

onBeforeUnmount(() => {
  stopVideoStatusPolling()
})

onMounted(async () => {
  if (!sessionKey.value && !routeThreadId.value) {
    router.replace({
      name: 'AgentComp',
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
    await handleStartCameraPreview({ silent: true })
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
  () => currentThreadId.value,
  async (nextThreadId, previousThreadId) => {
    if (!nextThreadId || nextThreadId === previousThreadId) return
    if (!isCameraStreaming.value || isVideoMode.value || startingCamera.value) return
    await handleStartCameraPreview({ silent: true })
  }
)

watch(
  () => candidateCaptureState.value,
  async (nextState, previousState) => {
    if (nextState !== 'idle' || previousState !== 'disabled') return
    await maybeAutoStartCapture()
  }
)
</script>

<style lang="less" scoped>
.voice-interview-view {
  min-height: 100%;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background:
    radial-gradient(circle at top right, rgba(var(--main-color-rgb), 0.08), transparent 28%),
    linear-gradient(180deg, var(--main-10) 0%, var(--gray-25) 100%);
}

.voice-toolbar,
.voice-shell,
.role-card {
  border: 1px solid var(--gray-100);
  border-radius: 24px;
  background: var(--gray-0);
  box-shadow: 0 10px 28px rgba(9, 26, 48, 0.04);
}

.voice-toolbar {
  padding: 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.toolbar-copy {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 760px;
}

.toolbar-eyebrow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.eyebrow-pill,
.eyebrow-meta {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
}

.eyebrow-pill {
  background: var(--main-50);
  color: var(--main-800);
  border: 1px solid var(--main-100);
  font-weight: 600;
}

.eyebrow-meta {
  background: var(--gray-25);
  color: var(--gray-600);
  border: 1px solid var(--gray-100);
}

.toolbar-title {
  margin-top: 14px;
  font-size: 30px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--gray-900);
}

.toolbar-subtitle {
  margin-top: 10px;
  max-width: 760px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-600);
}

.toolbar-actions {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 148px));
  justify-content: end;
  gap: 10px 12px;
}

.toolbar-action-item {
  width: 148px;
  box-sizing: border-box;
  justify-content: center;
  white-space: nowrap;
}

.toolbar-action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 16px;
  font-size: 13px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid var(--gray-100);
  font-size: 13px;
  color: var(--gray-700);
  background: var(--gray-25);
}

.voice-stage {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 20px;
}

.role-card {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.role-header,
.panel-header,
.capture-panel,
.input-actions,
.transcript-shell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.role-heading {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.role-label {
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-900);
}

.role-caption {
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-500);
}

.role-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.camera-role-actions {
  flex: 0 1 248px;
  display: grid;
  width: min(100%, 248px);
  max-width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  justify-content: end;
  gap: 8px;
}

.camera-action-button {
  width: 100%;
  min-width: 0;
  height: 42px;
  padding: 0 12px;
  box-sizing: border-box;
}

.camera-action-button-wide {
  grid-column: 1 / -1;
}

.status-header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.role-pill,
.mini-status-badge,
.panel-tag,
.camera-overlay-pill,
.camera-live-pill,
.camera-metric-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid var(--gray-100);
  font-size: 12px;
}

.role-pill {
  height: 32px;
  padding: 0 14px;
  font-weight: 600;
}

.status-card {
  background:
    radial-gradient(circle at top left, rgba(var(--main-color-rgb), 0.08), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, var(--main-5) 100%);
}

.status-card.state-speaking {
  border-color: var(--main-100);
}

.status-hero {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 20px;
  align-items: center;
  padding: 22px;
  border-radius: 20px;
  border: 1px solid rgba(var(--main-color-rgb), 0.08);
  background:
    linear-gradient(135deg, rgba(var(--main-color-rgb), 0.08) 0%, rgba(var(--main-color-rgb), 0.02) 100%),
    var(--gray-0);
}

.interviewer-visual {
  position: relative;
  width: 140px;
  height: 140px;
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
  background: rgba(255, 255, 255, 0.92);
}

.interviewer-core {
  inset: 34px;
  border: 1px solid rgba(var(--main-color-rgb), 0.12);
  background: rgba(255, 255, 255, 0.96);
  display: flex;
  align-items: center;
  justify-content: center;
}

.interviewer-visual.is-speaking .interviewer-ring {
  border-color: rgba(var(--main-color-rgb), 0.28);
  background: rgba(var(--main-color-rgb), 0.12);
  animation: interviewer-ring-pulse 1.8s ease-in-out infinite;
}

.interviewer-visual.is-waiting .interviewer-ring {
  border-color: rgba(var(--main-color-rgb), 0.16);
  animation: interviewer-ring-breathe 1.8s ease-in-out infinite;
}

.wave-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 38px;
}

.wave-bar {
  width: 7px;
  height: 18px;
  border-radius: 999px;
  background: var(--main-color);
  transform-origin: center bottom;
  animation: wave-bar-bounce 1s ease-in-out infinite;
}

.wave-bar:nth-child(2) {
  animation-delay: 0.08s;
}

.wave-bar:nth-child(3) {
  animation-delay: 0.16s;
}

.wave-bar:nth-child(4) {
  animation-delay: 0.24s;
}

.wave-bar:nth-child(5) {
  animation-delay: 0.32s;
}

.wave-bar:nth-child(6) {
  animation-delay: 0.4s;
}

.waiting-dots {
  display: flex;
  gap: 8px;
  align-items: center;
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
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid var(--main-100);
  background: radial-gradient(circle, var(--main-100) 0 32%, transparent 34%);
}

.hero-copy {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hero-kicker {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--main-700);
}

.hero-title {
  font-size: 24px;
  line-height: 1.3;
  font-weight: 700;
  color: var(--gray-900);
}

.hero-text {
  max-width: 480px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-600);
}

.hero-meter {
  display: flex;
  align-items: flex-end;
  gap: 5px;
  height: 30px;
  margin-top: 4px;
}

.hero-meter-bar {
  width: 5px;
  height: 10px;
  border-radius: 999px;
  background: rgba(var(--main-color-rgb), 0.2);
  transition: height 0.2s ease, background 0.2s ease, opacity 0.2s ease;
  opacity: 0.55;
}

.hero-meter.active .hero-meter-bar {
  background: rgba(var(--main-color-rgb), 0.9);
  opacity: 1;
  animation: hero-meter-wave 1.1s ease-in-out infinite;
}

.hero-meter.active .hero-meter-bar:nth-child(2) {
  animation-delay: 0.05s;
}

.hero-meter.active .hero-meter-bar:nth-child(3) {
  animation-delay: 0.1s;
}

.hero-meter.active .hero-meter-bar:nth-child(4) {
  animation-delay: 0.15s;
}

.hero-meter.active .hero-meter-bar:nth-child(5) {
  animation-delay: 0.2s;
}

.hero-meter.active .hero-meter-bar:nth-child(6) {
  animation-delay: 0.25s;
}

.hero-meter.active .hero-meter-bar:nth-child(7) {
  animation-delay: 0.3s;
}

.hero-meter.active .hero-meter-bar:nth-child(8) {
  animation-delay: 0.35s;
}

.hero-meter.active .hero-meter-bar:nth-child(9) {
  animation-delay: 0.4s;
}

.hero-meter.active .hero-meter-bar:nth-child(10) {
  animation-delay: 0.45s;
}

.hero-meter.active .hero-meter-bar:nth-child(11) {
  animation-delay: 0.5s;
}

.hero-meter.active .hero-meter-bar:nth-child(12) {
  animation-delay: 0.55s;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.status-info-card,
.record-summary-card {
  border-radius: 18px;
  border: 1px solid var(--gray-100);
  background: rgba(255, 255, 255, 0.9);
}

.status-info-card {
  display: flex;
  gap: 14px;
  padding: 16px;
}

.status-info-icon,
.record-summary-icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.status-info-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-info-label,
.record-summary-label {
  font-size: 12px;
  color: var(--gray-500);
}

.status-info-value,
.record-summary-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-900);
  line-height: 1.4;
}

.status-info-note,
.record-summary-note {
  font-size: 12px;
  line-height: 1.7;
  color: var(--gray-600);
}

.workflow-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.workflow-step {
  min-width: 0;
  display: flex;
  gap: 10px;
  padding: 14px 12px;
  border-radius: 16px;
  border: 1px solid var(--gray-100);
  background: rgba(255, 255, 255, 0.86);
}

.workflow-dot {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 50%;
  background: var(--gray-300);
  flex-shrink: 0;
}

.workflow-content {
  min-width: 0;
}

.workflow-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-800);
}

.workflow-text {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-500);
}

.workflow-step.state-current {
  border-color: rgba(var(--main-color-rgb), 0.22);
  background: rgba(var(--main-color-rgb), 0.08);
}

.workflow-step.state-current .workflow-dot {
  background: var(--main-color);
  box-shadow: 0 0 0 4px rgba(var(--main-color-rgb), 0.12);
}

.workflow-step.state-done .workflow-dot {
  background: var(--color-success-500);
}

.camera-card {
  background:
    linear-gradient(180deg, rgba(9, 26, 48, 0.04) 0%, rgba(9, 26, 48, 0.02) 100%),
    var(--gray-0);
}

.camera-stage {
  position: relative;
  min-height: 420px;
  border-radius: 22px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(9, 26, 48, 0.24) 0%, rgba(9, 26, 48, 0.7) 100%),
    #091a30;
}

.camera-video {
  width: 100%;
  height: 100%;
  min-height: 420px;
  object-fit: cover;
  display: block;
  background: #091a30;
}

.camera-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  text-align: center;
  color: rgba(255, 255, 255, 0.86);
}

.camera-empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.camera-empty-title {
  font-size: 20px;
  font-weight: 700;
}

.camera-empty-text {
  max-width: 320px;
  font-size: 13px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.72);
}

.camera-overlay {
  position: absolute;
  top: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 2;
}

.camera-overlay-left {
  left: 18px;
}

.camera-overlay-right {
  right: 18px;
}

.camera-live-pill {
  height: 30px;
  padding: 0 10px;
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 77, 79, 0.18);
  color: #fff2f0;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.camera-overlay-pill,
.camera-metric-pill {
  height: 30px;
  padding: 0 12px;
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.88);
}

.camera-footer {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 18px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(9, 26, 48, 0.68);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(8px);
}

.camera-footer-meter {
  width: 82px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 5px;
}

.camera-footer-bar {
  flex: 1;
  height: 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.26);
  transition: height 0.2s ease, background 0.2s ease;
}

.camera-footer-meter.active .camera-footer-bar {
  background: rgba(255, 255, 255, 0.92);
  animation: candidate-meter-wave 1s ease-in-out infinite;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(2) {
  animation-delay: 0.08s;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(3) {
  animation-delay: 0.16s;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(4) {
  animation-delay: 0.24s;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(5) {
  animation-delay: 0.32s;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(6) {
  animation-delay: 0.4s;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(7) {
  animation-delay: 0.48s;
}

.camera-footer-meter.active .camera-footer-bar:nth-child(8) {
  animation-delay: 0.56s;
}

.camera-footer-copy {
  min-width: 0;
}

.camera-footer-title {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
}

.camera-footer-text {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.76);
}

.camera-analysis-board {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.camera-analysis-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.camera-analysis-copy {
  min-width: 0;
}

.camera-analysis-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-900);
}

.camera-analysis-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-500);
}

.camera-analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.camera-analysis-card {
  border-radius: 18px;
  border: 1px solid var(--gray-100);
  background: rgba(255, 255, 255, 0.92);
  padding: 16px;
}

.camera-analysis-label {
  font-size: 12px;
  color: var(--gray-500);
}

.camera-analysis-value {
  margin-top: 6px;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--gray-900);
}

.camera-analysis-note {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--gray-600);
}

.camera-alerts {
  border-radius: 18px;
  border: 1px solid var(--gray-100);
  background: rgba(255, 255, 255, 0.88);
  padding: 14px 16px;
}

.camera-alerts-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-800);
}

.camera-alert-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.camera-alert-pill {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(250, 173, 20, 0.24);
  background: rgba(250, 173, 20, 0.08);
  color: var(--color-warning-700);
  font-size: 12px;
  line-height: 1.6;
}

.status-workbench-panel {
  width: 100%;
  min-width: 0;
}

.status-workbench-panel :deep(.agent-panel.embedded) {
  height: auto;
}

.voice-shell {
  flex: 1;
  min-width: 0;
  min-height: 520px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.voice-content-container {
  min-height: 520px;
}

.panel-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-900);
}

.panel-subtitle,
.input-hint {
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-500);
}

.panel-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.panel-tag {
  height: 30px;
  padding: 0 12px;
  background: var(--gray-25);
  color: var(--gray-600);
}

.record-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.record-summary-card {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.messages-panel {
  flex: 1;
  min-height: 280px;
  max-height: 480px;
  overflow-y: auto;
  border-radius: 20px;
  border: 1px solid var(--gray-100);
  background:
    linear-gradient(180deg, rgba(var(--main-color-rgb), 0.03) 0%, rgba(255, 255, 255, 0.9) 100%),
    var(--gray-25);
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

.message-role-pill {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
}

.message-bubble {
  max-width: 82%;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(var(--main-color-rgb), 0.08);
  color: var(--gray-800);
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-row.user .message-bubble {
  background: var(--main-20);
  border-color: rgba(var(--main-color-rgb), 0.16);
}

.streaming-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 8px;
  border-radius: 50%;
  background: var(--main-color);
  animation: dot-blink 1s ease-in-out infinite;
}

.empty-state {
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  text-align: center;
}

.empty-visual {
  width: 68px;
  height: 68px;
  border-radius: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: var(--main-700);
  background: var(--main-50);
  border: 1px solid var(--main-100);
}

.empty-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-800);
}

.empty-text {
  max-width: 480px;
  font-size: 13px;
  line-height: 1.8;
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
  border-radius: 20px;
  border: 1px solid var(--gray-100);
  background: linear-gradient(180deg, var(--gray-0) 0%, var(--main-5) 100%);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.capture-status,
.transcript-card {
  flex: 1;
}

.capture-title-row,
.transcript-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.capture-title,
.transcript-label {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-800);
}

.capture-subtitle {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-500);
}

.mini-status-badge {
  height: 28px;
  padding: 0 12px;
  font-weight: 600;
}

.transcript-card {
  border-radius: 18px;
  border: 1px solid var(--gray-100);
  background: rgba(255, 255, 255, 0.88);
  padding: 16px;
}

.transcript-meter {
  width: 56px;
  height: 20px;
  display: flex;
  align-items: flex-end;
  gap: 4px;
}

.transcript-meter-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgba(var(--main-color-rgb), 0.2);
}

.transcript-meter.active .transcript-meter-bar {
  background: rgba(var(--main-color-rgb), 0.92);
  animation: transcript-meter-wave 1s ease-in-out infinite;
}

.transcript-meter.active .transcript-meter-bar:nth-child(2) {
  animation-delay: 0.08s;
}

.transcript-meter.active .transcript-meter-bar:nth-child(3) {
  animation-delay: 0.16s;
}

.transcript-meter.active .transcript-meter-bar:nth-child(4) {
  animation-delay: 0.24s;
}

.transcript-meter.active .transcript-meter-bar:nth-child(5) {
  animation-delay: 0.32s;
}

.transcript-meter.active .transcript-meter-bar:nth-child(6) {
  animation-delay: 0.4s;
}

.transcript-content {
  margin-top: 10px;
  min-height: 86px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--gray-800);
  white-space: pre-wrap;
  word-break: break-word;
}

.transcript-content.placeholder {
  color: var(--gray-400);
}

.tone-active {
  border-color: rgba(var(--main-color-rgb), 0.16);
  background: rgba(var(--main-color-rgb), 0.08);
  color: var(--main-800);
}

.tone-active-soft {
  border-color: rgba(var(--main-color-rgb), 0.12);
  background: var(--main-5);
  color: var(--main-700);
}

.tone-warning {
  border-color: rgba(250, 173, 20, 0.26);
  background: rgba(250, 173, 20, 0.08);
  color: var(--color-warning-700);
}

.tone-error {
  border-color: rgba(255, 77, 79, 0.22);
  background: rgba(255, 77, 79, 0.08);
  color: var(--color-error-700);
}

.tone-idle {
  border-color: var(--gray-100);
  background: var(--gray-25);
  color: var(--gray-600);
}

.tone-active-soft .status-info-icon,
.tone-active .status-info-icon,
.tone-active-soft .record-summary-icon,
.tone-active .record-summary-icon {
  background: rgba(var(--main-color-rgb), 0.1);
  color: var(--main-700);
}

.tone-warning .status-info-icon,
.tone-warning .record-summary-icon {
  background: rgba(250, 173, 20, 0.12);
  color: var(--color-warning-700);
}

.tone-error .status-info-icon,
.tone-error .record-summary-icon {
  background: rgba(255, 77, 79, 0.12);
  color: var(--color-error-700);
}

.tone-idle .status-info-icon,
.tone-idle .record-summary-icon {
  background: var(--gray-50);
  color: var(--gray-500);
}

@keyframes wave-bar-bounce {
  0%,
  100% {
    transform: scaleY(0.45);
    opacity: 0.5;
  }
  50% {
    transform: scaleY(1.3);
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
    transform: scale(1.03);
    opacity: 0.82;
  }
}

@keyframes hero-meter-wave {
  0%,
  100% {
    height: 10px;
  }
  40% {
    height: 28px;
  }
  70% {
    height: 16px;
  }
}

@keyframes candidate-meter-wave {
  0%,
  100% {
    height: 12px;
  }
  50% {
    height: 38px;
  }
}

@keyframes transcript-meter-wave {
  0%,
  100% {
    height: 6px;
  }
  50% {
    height: 18px;
  }
}

@keyframes dot-blink {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@media (max-width: 1280px) {
  .voice-stage {
    grid-template-columns: 1fr;
  }

  .status-hero {
    grid-template-columns: 140px minmax(0, 1fr);
  }
}

@media (max-width: 1200px) {
  .record-summary-grid,
  .workflow-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .voice-interview-view {
    padding: 16px;
  }

  .voice-toolbar,
  .role-header,
  .status-header-actions,
  .panel-header,
  .capture-panel,
  .input-actions,
  .transcript-shell {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-actions,
  .role-actions,
  .panel-meta {
    justify-content: flex-start;
  }

  .camera-role-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }

  .camera-action-button,
  .camera-action-button-wide {
    width: 100%;
  }

  .toolbar-actions {
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .toolbar-action-item {
    width: 100%;
  }

  .status-hero {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }

  .status-grid,
  .record-summary-grid,
  .workflow-strip {
    grid-template-columns: 1fr;
  }

  .camera-stage,
  .camera-video {
    min-height: 360px;
  }

  .camera-analysis-header,
  .camera-analysis-grid {
    width: 100%;
  }

  .camera-analysis-grid {
    grid-template-columns: 1fr;
  }

  .camera-overlay {
    position: static;
    padding: 16px 16px 0;
    flex-wrap: wrap;
  }

  .camera-footer {
    position: static;
    margin: 16px;
  }

  .message-bubble {
    max-width: 100%;
  }
}
</style>


