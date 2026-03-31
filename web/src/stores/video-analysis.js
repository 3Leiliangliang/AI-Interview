import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { videoApi } from '@/apis/video_api'

/**
 * 视频面试分析状态管理
 */
export const useVideoAnalysisStore = defineStore('video-analysis', () => {
  // ==================== 状态 ====================
  const isActive = ref(false)
  const sessionId = ref(null)
  const currentEmotion = ref('neutral')
  const emotionScores = ref({})
  const posture = ref('upright')
  const postureScore = ref(100)
  const gazeDirection = ref('center')
  const attentionScore = ref(100)
  const alerts = ref([])
  const overallScore = ref(100)
  const isLoading = ref(false)
  const error = ref(null)
  const fps = ref(0)
  const batchSequence = ref(0)
  const pendingEvents = ref([])

  // ==================== 计算属性 ====================
  const status = computed(() => {
    if (!isActive.value) return 'inactive'
    if (fps.value < 5) return 'degraded'
    return 'active'
  })

  const hasAlerts = computed(() => alerts.value.length > 0)

  const summary = computed(() => {
    const parts = []
    parts.push(`情绪：${currentEmotion.value}`)
    if (attentionScore.value < 70) {
      parts.push(`注意力偏低(${attentionScore.value}分)`)
    } else {
      parts.push(`注意力良好(${attentionScore.value}分)`)
    }
    if (postureScore.value < 80) {
      parts.push(`坐姿待改善(${postureScore.value}分)`)
    }
    if (hasAlerts.value) {
      parts.push(`${alerts.value.length}条提醒`)
    }
    return parts.join('；')
  })

  // ==================== 方法 ====================
  function startAnalysis(sid) {
    sessionId.value = sid
    isActive.value = true
    error.value = null
    batchSequence.value = 0
    _eventCounter = 0
    pendingEvents.value = []
    alerts.value = []
  }

  function stopAnalysis() {
    isActive.value = false
    sessionId.value = null
    currentEmotion.value = 'neutral'
    emotionScores.value = {}
    posture.value = 'upright'
    postureScore.value = 100
    gazeDirection.value = 'center'
    attentionScore.value = 100
    alerts.value = []
    overallScore.value = 100
    fps.value = 0
    pendingEvents.value = []
  }

  function updateAnalysis(data) {
    if (data.emotion) currentEmotion.value = data.emotion
    if (data.emotion_scores) emotionScores.value = data.emotion_scores
    if (data.posture) posture.value = data.posture
    if (data.posture_score !== undefined) postureScore.value = data.posture_score
    if (data.gaze_direction) gazeDirection.value = data.gaze_direction
    if (data.attention_score !== undefined) attentionScore.value = data.attention_score
    if (data.overall_score !== undefined) overallScore.value = data.overall_score
    if (data.fps !== undefined) fps.value = data.fps
  }

  function addAlert(alert) {
    alerts.value = [...alerts.value.slice(-9), alert]
  }

  /** 全局事件序号计数器 */
  let _eventCounter = 0

  function addEvent(event) {
    event.sequence = _eventCounter++
    pendingEvents.value.push(event)
  }

  async function flushEvents() {
    if (pendingEvents.value.length === 0 || !sessionId.value) return

    const events = [...pendingEvents.value]
    pendingEvents.value = []
    batchSequence.value += 1

    const batch = {
      session_id: sessionId.value,
      batch_id: crypto.randomUUID(),
      events,
      batch_timestamp: Date.now(),
      batch_sequence: batchSequence.value
    }

    try {
      await videoApi.sendEventBatch(batch)
    } catch (e) {
      // 发送失败，将事件放回队列（重新分配 sequence 避免重复）
      const recovered = events.map((e, i) => ({ ...e, sequence: _eventCounter + i }))
      _eventCounter += events.length
      pendingEvents.value = [...recovered, ...pendingEvents.value]
      error.value = '事件发送失败'
    }
  }

  function reset() {
    stopAnalysis()
  }

  return {
    // 状态
    isActive,
    sessionId,
    currentEmotion,
    emotionScores,
    posture,
    postureScore,
    gazeDirection,
    attentionScore,
    alerts,
    overallScore,
    isLoading,
    error,
    fps,
    batchSequence,
    pendingEvents,
    // 计算属性
    status,
    hasAlerts,
    summary,
    // 方法
    startAnalysis,
    stopAnalysis,
    updateAnalysis,
    addAlert,
    addEvent,
    flushEvents,
    reset
  }
})
