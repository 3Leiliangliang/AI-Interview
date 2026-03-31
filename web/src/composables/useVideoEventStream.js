import { ref, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useVideoAnalysisStore } from '@/stores/video-analysis'
import { useVideoCapture } from '@/composables/useVideoCapture'
import { useVideoAnalysis } from '@/composables/useVideoAnalysis'
import {
  createEmotionEvent,
  createPostureEvent,
  createAttentionEvent,
  createAlertEvent,
  VideoEventType,
  AlertType
} from '@/types/video-events'

/**
 * 视频事件流 composable
 *
 * 将 useVideoAnalysis 的分析结果转换为时序事件，按 500ms 间隔打包批次发送到后端。
 */
export function useVideoEventStream() {
  const store = useVideoAnalysisStore()
  const storeRefs = storeToRefs(store)
  const capture = useVideoCapture()
  const analysis = useVideoAnalysis()

  const isVideoMode = ref(false)
  const isInitializing = ref(false)

  /** @type {number|null} */
  let batchTimerId = null

  /** @type {HTMLVideoElement|null} */
  let _hiddenVideoEl = null

  /** 无脸检测持续时间计数器（单位：500ms tick） */
  let noFaceTicks = 0

  /** 视线偏离持续时间计数器（单位：500ms tick） */
  let _lookingAwayTicks = 0

  /** 告警冷却计时器，避免同类告警刷屏（key=alertType, value=剩余tick数） */
  const _alertCooldowns = { low_attention: 0, slouching: 0, looking_away: 0, no_face: 0 }
  const ALERT_COOLDOWN_TICKS = 6 // 6 x 500ms = 3s 冷却期

  // ==================== 内部方法 ====================

  /**
   * 将分析结果转换为事件并推送到 store
   * @param {{ emotion: Object, posture: Object, attention: Object, timestamp: number }|null} result
   */
  function processAnalysisResult(result) {
    if (!result || !store.sessionId) return

    const sid = store.sessionId

    // --- 表情事件 ---
    const emotionEvent = createEmotionEvent(
      sid,
      result.emotion.dominant,
      result.emotion.scores,
      result.emotion.intensity,
      result.emotion.face_detected
    )
    store.addEvent(emotionEvent)

    // --- 姿态事件 ---
    const postureEvent = createPostureEvent(
      sid,
      result.posture.posture,
      result.posture.head_tilt_angle,
      result.posture.gaze_direction,
      result.posture.shoulder_balance,
      result.posture.posture_score
    )
    store.addEvent(postureEvent)

    // --- 注意力事件 ---
    const attentionEvent = createAttentionEvent(
      sid,
      result.attention.attention_score,
      result.attention.blink_rate,
      result.attention.gaze_stability
    )
    store.addEvent(attentionEvent)

    // --- 告警检测 ---
    checkAlerts(result)

    // --- 更新 store 展示数据 ---
    store.updateAnalysis({
      emotion: result.emotion.dominant,
      emotion_scores: result.emotion.scores,
      posture: result.posture.posture,
      posture_score: result.posture.posture_score,
      gaze_direction: result.posture.gaze_direction,
      attention_score: result.attention.attention_score,
      fps: capture.fps.value
    })
  }

  /**
   * 检查是否需要生成告警
   * @param {{ emotion: Object, posture: Object, attention: Object }} result
   */
  function checkAlerts(result) {
    if (!store.sessionId) return

    const sid = store.sessionId

    // 递减所有冷却计时器
    for (const key of Object.keys(_alertCooldowns)) {
      if (_alertCooldowns[key] > 0) _alertCooldowns[key]--
    }

    // 无脸检测计时
    if (!result.emotion.face_detected) {
      noFaceTicks++
      if (noFaceTicks === 6 && _alertCooldowns.no_face <= 0) {
        // 6 x 500ms = 3s
        const alertEvent = createAlertEvent(
          sid,
          AlertType.NO_FACE_DETECTED,
          '未检测到人脸，请确保面部在画面中',
          3,
          '调整坐姿或摄像头角度'
        )
        store.addEvent(alertEvent)
        store.addAlert({
          type: AlertType.NO_FACE_DETECTED,
          message: '未检测到人脸',
          time: Date.now()
        })
        _alertCooldowns.no_face = ALERT_COOLDOWN_TICKS
      }
    } else {
      noFaceTicks = 0
    }

    // 注意力过低（添加 cooldown）
    if (result.attention.attention_score < 50 && _alertCooldowns.low_attention <= 0) {
      const alertEvent = createAlertEvent(
        sid,
        AlertType.LOW_ATTENTION,
        `注意力偏低(${result.attention.attention_score}分)`,
        0,
        '集中注意力看向屏幕'
      )
      store.addEvent(alertEvent)
      store.addAlert({
        type: AlertType.LOW_ATTENTION,
        message: `注意力偏低(${result.attention.attention_score}分)`,
        time: Date.now()
      })
      _alertCooldowns.low_attention = ALERT_COOLDOWN_TICKS
    }

    // 坐姿评分过低（添加 cooldown）
    if (result.posture.posture_score < 60 && _alertCooldowns.slouching <= 0) {
      const alertEvent = createAlertEvent(
        sid,
        AlertType.SLOUCHING,
        `坐姿评分偏低(${result.posture.posture_score}分)`,
        0,
        '调整坐姿，保持身体端正'
      )
      store.addEvent(alertEvent)
      store.addAlert({
        type: AlertType.SLOUCHING,
        message: `坐姿评分偏低(${result.posture.posture_score}分)`,
        time: Date.now()
      })
      _alertCooldowns.slouching = ALERT_COOLDOWN_TICKS
    }

    // 视线偏离（需要持续偏离才触发）
    if (result.posture.gaze_direction !== 'center') {
      _lookingAwayTicks++
      if (_lookingAwayTicks >= 2 && _alertCooldowns.looking_away <= 0) {
        // 持续 2 x 500ms = 1s 偏离才触发
        const alertEvent = createAlertEvent(
          sid,
          AlertType.LOOKING_AWAY,
          `视线偏离(${result.posture.gaze_direction})`,
          0,
          '保持视线朝向屏幕'
        )
        store.addEvent(alertEvent)
        store.addAlert({
          type: AlertType.LOOKING_AWAY,
          message: `视线偏离(${result.posture.gaze_direction})`,
          time: Date.now()
        })
        _alertCooldowns.looking_away = ALERT_COOLDOWN_TICKS
      }
    } else {
      _lookingAwayTicks = 0
    }
  }

  /** 批次定时器回调：处理最新分析结果 + 刷新事件队列 */
  function batchTick() {
    if (!store.isActive) return

    processAnalysisResult(analysis.lastResult.value)
    store.flushEvents()
  }

  function startBatchTimer() {
    stopBatchTimer()
    batchTimerId = setInterval(batchTick, 500)
  }

  function stopBatchTimer() {
    if (batchTimerId != null) {
      clearInterval(batchTimerId)
      batchTimerId = null
    }
  }

  // ==================== 公共方法 ====================

  /**
   * 开启视频模式
   * @param {string} sessionId - 面试会话 ID
   */
  async function enableVideoMode(sessionId) {
    if (isVideoMode.value) return

    isInitializing.value = true

    try {
      // 1. 初始化模型
      await analysis.initializeModels()
      if (!analysis.isModelReady.value) {
        throw new Error(analysis.modelLoadError.value || '模型加载失败')
      }

      // 2. 启动摄像头
      await capture.start()
      if (!capture.isStreaming.value) {
        throw new Error(capture.error.value || '摄像头启动失败')
      }

      // 3. 创建隐藏 video 元素用于 MediaPipe 分析
      const hiddenVideo = document.createElement('video')
      hiddenVideo.autoplay = true
      hiddenVideo.muted = true
      hiddenVideo.playsInline = true
      hiddenVideo.style.display = 'none'
      hiddenVideo.srcObject = capture.stream.value
      await hiddenVideo.play()

      // 4. 初始化 store
      store.startAnalysis(sessionId)

      // 5. 启动分析（使用隐藏 video 元素）
      analysis.startAnalysis(hiddenVideo)

      // 6. 启动事件批次定时器
      noFaceTicks = 0
      _lookingAwayTicks = 0
      for (const key of Object.keys(_alertCooldowns)) _alertCooldowns[key] = 0
      startBatchTimer()

      // 7. 激活视频模式（仅用于 UI 状态指示）
      isVideoMode.value = true

      // 保存隐藏 video 引用以便清理
      _hiddenVideoEl = hiddenVideo
    } catch (err) {
      disableVideoMode()
      store.error = err instanceof Error ? err.message : String(err)
    } finally {
      isInitializing.value = false
    }
  }

  /** 关闭视频模式 */
  function disableVideoMode() {
    stopBatchTimer()
    analysis.stopAnalysis()
    capture.stop()
    store.stopAnalysis()
    // 清理隐藏 video 元素
    if (_hiddenVideoEl) {
      _hiddenVideoEl.srcObject = null
      _hiddenVideoEl = null
    }
    isVideoMode.value = false
    isInitializing.value = false
    noFaceTicks = 0
  }

  // 组件卸载时清理
  onUnmounted(() => {
    if (isVideoMode.value) {
      disableVideoMode()
    }
  })

  return {
    // 状态
    isVideoMode,
    isInitializing,

    // 方法
    enableVideoMode,
    disableVideoMode,
    processAnalysisResult,

    // store（响应式 refs + 方法）
    ...storeRefs,
    startAnalysis: store.startAnalysis,
    stopAnalysis: store.stopAnalysis,
    updateAnalysis: store.updateAnalysis,
    addAlert: store.addAlert,
    addEvent: store.addEvent,
    flushEvents: store.flushEvents,
    reset: store.reset,

    // capture
    isStreaming: capture.isStreaming,
    videoRef: capture.videoRef,
    captureStream: capture.stream,
    captureError: capture.error,
    fps: capture.fps,
    resolution: capture.resolution,
    isCameraSupported: capture.isSupported,
    availableDevices: capture.availableDevices,
    captureStart: capture.start,
    captureStop: capture.stop,
    captureFrame: capture.captureFrame,
    getFrameBitmap: capture.getFrameBitmap,

    // analysis
    isAnalyzing: analysis.isAnalyzing,
    isModelReady: analysis.isModelReady,
    modelLoadError: analysis.modelLoadError,
    analysisFps: analysis.analysisFps,
    lastResult: analysis.lastResult,
    initializeModels: analysis.initializeModels,
    startAnalysis: analysis.startAnalysis,
    stopAnalysis: analysis.stopAnalysis,
    analyzeFrame: analysis.analyzeFrame
  }
}
