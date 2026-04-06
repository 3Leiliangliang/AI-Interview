<template>
  <div class="voice-interview-view">
    <div class="voice-toolbar">
      <div>
        <div class="toolbar-title">语音模拟面试</div>
        <div class="toolbar-subtitle">豆包实时语音出话，原面试 Agent 负责后台编排</div>
      </div>

      <div class="toolbar-actions">
        <span class="status-badge">{{ connectionStatusLabel }}</span>
        <span class="status-badge">{{ playbackStatusLabel }}</span>
        <a-button @click="backToSetup">调整配置</a-button>
        <a-button @click="openResumeCenter">我的简历</a-button>
        <a-button :disabled="!currentThreadId" @click="openInterviewResult">面试结果</a-button>
      </div>
    </div>

    <div class="voice-stage">
      <section class="role-card interviewer-card">
        <div class="role-label">面试官</div>
        <div class="role-placeholder">占位</div>
      </section>

      <section class="role-card candidate-card">
        <div class="role-label">面试者</div>
        <div class="role-placeholder">占位</div>
      </section>
    </div>

    <div class="voice-shell">
      <div class="panel-header">
        <div>
          <div class="panel-title">文本记录</div>
          <div class="panel-subtitle">用于跟进当前线程的上下文与语音播报内容</div>
        </div>
        <div class="panel-actions">
          <a-button type="primary" :loading="startingVoice" @click="handleStartVoiceInterview">
            {{ startButtonLabel }}
          </a-button>
          <a-button :disabled="playbackState !== 'playing'" @click="interrupt">停止播放</a-button>
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
        <a-textarea
          v-model:value="userInput"
          :rows="3"
          :disabled="!sessionReady"
          placeholder="当前版本先使用文本输入，豆包会直接语音回复。"
        />
        <div class="input-actions">
          <span class="input-hint">当前线程：{{ currentThreadId || '未创建' }}</span>
          <a-button type="primary" :disabled="!sessionReady || !trimmedInput" @click="handleSend">
            发送
          </a-button>
        </div>
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
const userInput = ref('')
const startingVoice = ref(false)
const preloadingVoice = ref(false)
const preloadedSession = ref(null)
const needsOpeningTurn = ref(!Boolean(route.query.threadId))
const hasStartedOpeningTurn = ref(false)

let preloadPromise = null

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const routeThreadId = computed(() => String(route.query.threadId || '').trim())
const sessionKey = computed(() => String(route.query.session || '').trim())
const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')

const {
  agentState,
  connect,
  connectionState,
  ensureAudioContext,
  error,
  interrupt,
  messages,
  playbackState,
  sendUserText,
  sessionReady,
  startInterview,
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
const trimmedInput = computed(() => userInput.value.trim())
const canStartOpeningTurn = computed(() => {
  return connectionState.value === 'connected' && visibleMessages.value.length === 0 && !hasStartedOpeningTurn.value
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
    await waitForSessionReady()

    if (canStartOpeningTurn.value) {
      hasStartedOpeningTurn.value = true
      startInterview()
      needsOpeningTurn.value = false
      return
    }

    message.success('语音会话已就绪')
  } catch (err) {
    message.error(err?.message || '开启语音面试失败')
  } finally {
    startingVoice.value = false
  }
}

const handleSend = () => {
  if (!trimmedInput.value) return
  sendUserText(trimmedInput.value)
  userInput.value = ''
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

.role-label {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-800);
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

.voice-shell {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 520px;
}

.panel-header,
.input-actions {
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

.panel-actions {
  display: flex;
  gap: 10px;
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
}

@media (max-width: 960px) {
  .voice-toolbar,
  .panel-header,
  .input-actions {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-actions {
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
