import { computed, onBeforeUnmount, ref } from 'vue'

import { MessageProcessor } from '@/utils/messageProcessor'
import { interviewVoiceApi } from '@/apis/interview_voice'

const PLAYBACK_SAMPLE_RATE = 24000
const ASR_SAMPLE_RATE = 16000
const PCM_FRAME_BYTES = 3200
const WS_CONNECT_TIMEOUT_MS = 10000

function pcmS16leToAudioBuffer(audioContext, arrayBuffer) {
  const int16 = new Int16Array(arrayBuffer)
  const float32 = new Float32Array(int16.length)
  for (let i = 0; i < int16.length; i += 1) {
    float32[i] = Math.max(-1, Math.min(1, int16[i] / 32768))
  }

  const audioBuffer = audioContext.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE)
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

function concatUint8Arrays(left, right) {
  if (!left?.length) return right
  if (!right?.length) return left
  const result = new Uint8Array(left.length + right.length)
  result.set(left, 0)
  result.set(right, left.length)
  return result
}

function float32ToPcm16Bytes(input, inputSampleRate, outputSampleRate = ASR_SAMPLE_RATE) {
  if (!input?.length) return new Uint8Array(0)

  const sampleRateRatio = inputSampleRate / outputSampleRate
  const outputLength = Math.max(1, Math.round(input.length / sampleRateRatio))
  const pcm16 = new Int16Array(outputLength)
  let offsetInput = 0

  for (let i = 0; i < outputLength; i += 1) {
    const nextOffsetInput = Math.min(input.length, Math.round((i + 1) * sampleRateRatio))
    let accumulator = 0
    let count = 0
    for (let j = offsetInput; j < nextOffsetInput; j += 1) {
      accumulator += input[j]
      count += 1
    }
    const sample = count > 0 ? accumulator / count : input[Math.min(offsetInput, input.length - 1)]
    const normalized = Math.max(-1, Math.min(1, sample))
    pcm16[i] = normalized < 0 ? normalized * 32768 : normalized * 32767
    offsetInput = nextOffsetInput
  }

  return new Uint8Array(pcm16.buffer)
}

export function useVoiceInterviewSession({ onCodingRedirect } = {}) {
  const connectionState = ref('idle')
  const playbackState = ref('idle')
  const candidateCaptureState = ref('idle')
  const micPermissionState = ref('unknown')
  const isCapturing = ref(false)
  const error = ref('')
  const messages = ref([])
  const agentState = ref({})
  const threadId = ref('')
  const sessionReady = ref(false)
  const partialTranscript = ref('')
  const finalTranscript = ref('')

  let ws = null
  let audioContext = null
  let nextPlaybackTime = 0
  let activeSources = new Set()
  let microphoneStream = null
  let microphoneSource = null
  let microphoneProcessor = null
  let microphoneSilentGain = null
  let pendingPcmBytes = new Uint8Array(0)

  const isConnected = computed(() => connectionState.value === 'connected')

  async function ensureAudioContext() {
    if (!audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (!AudioContextClass) {
        throw new Error('当前浏览器不支持音频能力')
      }
      audioContext = new AudioContextClass()
    }
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }
  }

  async function ensureMicrophoneReady() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前浏览器不支持麦克风采集')
    }

    await ensureAudioContext()
    if (microphoneStream) {
      micPermissionState.value = 'granted'
      if (!microphoneSource) {
        microphoneSource = audioContext.createMediaStreamSource(microphoneStream)
      }
      return
    }

    try {
      microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })
      micPermissionState.value = 'granted'
      microphoneSource = audioContext.createMediaStreamSource(microphoneStream)
    } catch (err) {
      const name = err instanceof DOMException ? err.name : ''
      micPermissionState.value = 'denied'
      if (name === 'NotAllowedError') {
        throw new Error('麦克风权限被拒绝')
      }
      if (name === 'NotFoundError') {
        throw new Error('未检测到可用麦克风')
      }
      throw new Error(err?.message || '麦克风初始化失败')
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

  function sendBinary(buffer) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(buffer)
  }

  function teardownCaptureGraph() {
    if (microphoneProcessor) {
      microphoneProcessor.onaudioprocess = null
      try {
        microphoneProcessor.disconnect()
      } catch {
        // ignore
      }
      microphoneProcessor = null
    }
    if (microphoneSilentGain) {
      try {
        microphoneSilentGain.disconnect()
      } catch {
        // ignore
      }
      microphoneSilentGain = null
    }
  }

  function flushPendingPcmBytes() {
    if (!pendingPcmBytes.length) return
    sendBinary(pendingPcmBytes.buffer.slice(0))
    pendingPcmBytes = new Uint8Array(0)
  }

  function pumpPcmBytes(chunkBytes) {
    pendingPcmBytes = concatUint8Arrays(pendingPcmBytes, chunkBytes)
    while (pendingPcmBytes.length >= PCM_FRAME_BYTES) {
      const frame = pendingPcmBytes.slice(0, PCM_FRAME_BYTES)
      pendingPcmBytes = pendingPcmBytes.slice(PCM_FRAME_BYTES)
      sendBinary(frame.buffer)
    }
  }

  async function startCandidateCapture() {
    if (isCapturing.value) return
    if (!sessionReady.value) {
      throw new Error('语音会话尚未就绪')
    }

    await ensureMicrophoneReady()
    partialTranscript.value = ''
    finalTranscript.value = ''
    pendingPcmBytes = new Uint8Array(0)

    send({ type: 'candidate_audio_start' })

    microphoneProcessor = audioContext.createScriptProcessor(4096, 1, 1)
    microphoneSilentGain = audioContext.createGain()
    microphoneSilentGain.gain.value = 0
    microphoneProcessor.onaudioprocess = (event) => {
      if (!isCapturing.value) return
      const channelData = event.inputBuffer.getChannelData(0)
      const chunkBytes = float32ToPcm16Bytes(channelData, audioContext.sampleRate, ASR_SAMPLE_RATE)
      pumpPcmBytes(chunkBytes)
    }

    microphoneSource.connect(microphoneProcessor)
    microphoneProcessor.connect(microphoneSilentGain)
    microphoneSilentGain.connect(audioContext.destination)
    isCapturing.value = true
  }

  function stopCandidateCapture({ sendStop = true } = {}) {
    if (!isCapturing.value && !microphoneProcessor) {
      if (sendStop) {
        send({ type: 'candidate_audio_stop' })
      }
      return
    }

    flushPendingPcmBytes()
    teardownCaptureGraph()
    isCapturing.value = false
    if (sendStop) {
      send({ type: 'candidate_audio_stop' })
    }
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

        if (eventType === 'candidate_capture_state') {
          candidateCaptureState.value = payload.state || 'idle'
          if (candidateCaptureState.value !== 'listening') {
            stopCandidateCapture({ sendStop: false })
          }
          return
        }

        if (eventType === 'candidate_transcript_partial') {
          partialTranscript.value = payload.content || ''
          return
        }

        if (eventType === 'candidate_transcript_final') {
          finalTranscript.value = payload.content || ''
          partialTranscript.value = payload.content || ''
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
          stopCandidateCapture({ sendStop: false })
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
        stopCandidateCapture({ sendStop: false })
        connectionState.value = 'closed'
        sessionReady.value = false
        candidateCaptureState.value = 'idle'
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
    stopCandidateCapture({ sendStop: false })
    send({ type: 'interrupt' })
  }

  function close({ sendFinish = true } = {}) {
    stopCandidateCapture({ sendStop: false })
    if (sendFinish) {
      send({ type: 'finish' })
    }
    stopPlayback()
    if (ws) {
      ws.close()
      ws = null
    }
    if (microphoneStream) {
      microphoneStream.getTracks().forEach((track) => track.stop())
      microphoneStream = null
      microphoneSource = null
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
    candidateCaptureState,
    connect,
    connectionState,
    ensureAudioContext,
    ensureMicrophoneReady,
    error,
    finalTranscript,
    interrupt,
    isCapturing,
    isConnected,
    messages,
    micPermissionState,
    partialTranscript,
    playbackState,
    sendUserText,
    sessionReady,
    startCandidateCapture,
    startInterview,
    stopCandidateCapture,
    threadId
  }
}
