import { computed, onBeforeUnmount, ref } from 'vue'

import { MessageProcessor } from '@/utils/messageProcessor'
import { interviewVoiceApi } from '@/apis/interview_voice'

const PCM_SAMPLE_RATE = 24000
const WS_CONNECT_TIMEOUT_MS = 10000

function pcmS16leToAudioBuffer(audioContext, arrayBuffer) {
  const int16 = new Int16Array(arrayBuffer)
  const float32 = new Float32Array(int16.length)
  for (let i = 0; i < int16.length; i += 1) {
    float32[i] = Math.max(-1, Math.min(1, int16[i] / 32768))
  }

  const audioBuffer = audioContext.createBuffer(1, float32.length, PCM_SAMPLE_RATE)
  audioBuffer.copyToChannel(float32, 0)
  return audioBuffer
}

function mapHistoryMessage(item) {
  if (!item || !['human', 'ai'].includes(item.type)) return null
  if (MessageProcessor.isHiddenInterviewPromptMessage(item)) return null

  return {
    id: `${item.type}-${item.id || item.created_at || Math.random()}`,
    role: item.type === 'human' ? 'user' : 'assistant',
    content: item.content || '',
    streaming: false,
    createdAt: item.created_at || ''
  }
}

export function useVoiceInterviewSession({ onCodingRedirect } = {}) {
  const connectionState = ref('idle')
  const playbackState = ref('idle')
  const error = ref('')
  const messages = ref([])
  const agentState = ref({})
  const threadId = ref('')
  const sessionReady = ref(false)

  let ws = null
  let audioContext = null
  let nextPlaybackTime = 0
  let activeSources = new Set()

  const isConnected = computed(() => connectionState.value === 'connected')

  async function ensureAudioContext() {
    if (!audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (!AudioContextClass) {
        throw new Error('当前浏览器不支持音频播放')
      }
      audioContext = new AudioContextClass()
    }
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }
  }

  function resetStreamingAssistant() {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant' && lastMessage.streaming) {
      lastMessage.streaming = false
    }
  }

  function applyAssistantDelta(content) {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant' && lastMessage.streaming) {
      lastMessage.content += content
      return
    }

    messages.value.push({
      id: `assistant-stream-${Date.now()}`,
      role: 'assistant',
      content,
      streaming: true,
      createdAt: new Date().toISOString()
    })
  }

  function applyAssistantFinal(content) {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage?.role === 'assistant' && lastMessage.streaming) {
      lastMessage.content = content
      lastMessage.streaming = false
      return
    }

    messages.value.push({
      id: `assistant-final-${Date.now()}`,
      role: 'assistant',
      content,
      streaming: false,
      createdAt: new Date().toISOString()
    })
  }

  function applyHistory(history) {
    messages.value = (history || []).map(mapHistoryMessage).filter(Boolean)
  }

  function stopPlayback() {
    activeSources.forEach((source) => {
      try {
        source.stop()
      } catch {
        // ignore
      }
    })
    activeSources = new Set()
    if (audioContext) {
      nextPlaybackTime = audioContext.currentTime
    } else {
      nextPlaybackTime = 0
    }
    playbackState.value = 'idle'
  }

  async function enqueueAudio(arrayBuffer) {
    if (!audioContext) return
    const audioBuffer = pcmS16leToAudioBuffer(audioContext, arrayBuffer)
    const source = audioContext.createBufferSource()
    source.buffer = audioBuffer
    source.connect(audioContext.destination)

    const startTime = Math.max(audioContext.currentTime, nextPlaybackTime)
    nextPlaybackTime = startTime + audioBuffer.duration
    activeSources.add(source)
    playbackState.value = 'playing'

    source.onended = () => {
      activeSources.delete(source)
      if (activeSources.size === 0 && audioContext.currentTime >= nextPlaybackTime - 0.05) {
        playbackState.value = 'idle'
      }
    }

    source.start(startTime)
  }

  function send(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify(payload))
  }

  async function connect({ voiceSessionId, token, nextThreadId }) {
    if (ws && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.readyState)) {
      return
    }

    error.value = ''
    connectionState.value = 'connecting'
    threadId.value = nextThreadId || threadId.value
    await new Promise((resolve, reject) => {
      let settled = false
      const finalize = (handler) => {
        if (settled) return
        settled = true
        handler()
      }

      const connectTimer = window.setTimeout(() => {
        finalize(() => {
          if (ws && ws.readyState === WebSocket.CONNECTING) {
            ws.close()
          }
          error.value = '语音连接超时'
          reject(new Error('语音连接超时'))
        })
      }, WS_CONNECT_TIMEOUT_MS)

      ws = new WebSocket(interviewVoiceApi.buildVoiceWsUrl({ voiceSessionId, token }))
      ws.binaryType = 'arraybuffer'

      ws.onopen = () => {
        window.clearTimeout(connectTimer)
        finalize(() => {
          connectionState.value = 'connected'
          resolve()
        })
      }

      ws.onmessage = async (event) => {
        if (typeof event.data !== 'string') {
          await enqueueAudio(event.data)
          return
        }

        const payload = JSON.parse(event.data)
        const eventType = payload.type

        if (eventType === 'session_ready') {
          sessionReady.value = true
          threadId.value = payload.thread_id || threadId.value
          return
        }

        if (eventType === 'history_loaded') {
          applyHistory(payload.history)
          return
        }

        if (eventType === 'user_message') {
          resetStreamingAssistant()
          messages.value.push({
            id: `user-${Date.now()}`,
            role: 'user',
            content: payload.content || '',
            streaming: false,
            createdAt: new Date().toISOString()
          })
          return
        }

        if (eventType === 'assistant_delta') {
          applyAssistantDelta(payload.content || '')
          return
        }

        if (eventType === 'assistant_final') {
          applyAssistantFinal(payload.content || '')
          return
        }

        if (eventType === 'agent_state') {
          agentState.value = payload.agent_state || {}
          return
        }

        if (eventType === 'coding_redirect') {
          onCodingRedirect?.(payload)
          return
        }

        if (eventType === 'interrupted') {
          stopPlayback()
          resetStreamingAssistant()
          return
        }

        if (eventType === 'error') {
          error.value = payload.message || '语音会话出错'
        }
      }

      ws.onerror = () => {
        window.clearTimeout(connectTimer)
        finalize(() => {
          error.value = '语音连接失败'
          reject(new Error('语音连接失败'))
        })
      }

      ws.onclose = () => {
        window.clearTimeout(connectTimer)
        connectionState.value = 'closed'
        sessionReady.value = false
        if (!settled) {
          settled = true
          reject(new Error(error.value || '语音连接已关闭'))
        }
        ws = null
      }
    })
  }

  function startInterview() {
    send({ type: 'start_interview' })
  }

  function sendUserText(content) {
    send({ type: 'user_text', content })
  }

  function interrupt() {
    stopPlayback()
    send({ type: 'interrupt' })
  }

  function close({ sendFinish = true } = {}) {
    if (sendFinish) {
      send({ type: 'finish' })
    }
    stopPlayback()
    if (ws) {
      ws.close()
      ws = null
    }
  }

  onBeforeUnmount(() => {
    close()
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close()
    }
  })

  return {
    agentState,
    connect,
    connectionState,
    ensureAudioContext,
    error,
    interrupt,
    isConnected,
    messages,
    playbackState,
    sendUserText,
    sessionReady,
    startInterview,
    threadId
  }
}
