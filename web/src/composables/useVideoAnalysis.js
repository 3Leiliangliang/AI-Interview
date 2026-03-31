import { ref, onUnmounted } from 'vue'

/**
 * MediaPipe 视频分析 composable — 使用 FaceLandmarker 和 PoseLandmarker 实时分析面部表情与身体姿态
 *
 * @returns {{
 *   isAnalyzing: import('vue').Ref<boolean>,
 *   isModelReady: import('vue').Ref<boolean>,
 *   modelLoadError: import('vue').Ref<string|null>,
 *   analysisFps: import('vue').Ref<number>,
 *   lastResult: import('vue').Ref<Object|null>,
 *   initializeModels: () => Promise<void>,
 *   startAnalysis: (videoElement: HTMLVideoElement) => void,
 *   stopAnalysis: () => void,
 *   analyzeFrame: (videoElement: HTMLVideoElement) => Object|null
 * }}
 */
export function useVideoAnalysis() {
  // ==================== 响应式状态 ====================
  const isAnalyzing = ref(false)
  const isModelReady = ref(false)
  const modelLoadError = ref(null)
  const analysisFps = ref(0)
  const lastResult = ref(null)

  // ==================== 内部变量 ====================

  /** @type {import('@mediapipe/tasks-vision').FaceLandmarker|null} */
  let faceLandmarker = null
  /** @type {import('@mediapipe/tasks-vision').PoseLandmarker|null} */
  let poseLandmarker = null

  let animationFrameId = null
  let lastAnalysisTime = 0
  let fpsFrameCount = 0
  let fpsIntervalId = null

  /** 当前分析使用的 video 元素引用 */
  let currentVideoElement = null

  // --- 注意力追踪 ---
  let prevBlinkValue = 0
  let blinkTimestamps = []
  let prevGazeDirection = 'center'
  let gazeChangeTimestamps = []

  // ==================== 常量 ====================

  const TARGET_INTERVAL = 100 // 10fps
  const BLINK_RISING_THRESHOLD = 0.4 // 眨眼上升沿阈值
  const BLINK_FALLING_THRESHOLD = 0.2 // 眨眼下降沿阈值
  const ATTENTION_WINDOW_MS = 60_000 // 眨眼/视线统计窗口 1 分钟
  const GAZE_CHANGE_THRESHOLD = 5 // 视线方向变化计数阈值（每分钟）

  const VISION_WASM_PATH = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.34/wasm'
  const FACE_MODEL_PATH = '/models/face_landmarker.task'
  const POSE_MODEL_PATH = '/models/pose_landmarker_heavy.task'

  /**
   * 面部 blendshape 名称 → 简短别名 的映射表（Apple ARKit 52 个中的关键项）
   * 用于从 blendshapes 数组中按名称取值
   */
  const BS = {
    BROW_INNER_UP: 'browInnerUp',
    BROW_DOWN_LEFT: 'browDownLeft',
    BROW_DOWN_RIGHT: 'browDownRight',
    EYE_BLINK_LEFT: 'eyeBlinkLeft',
    EYE_BLINK_RIGHT: 'eyeBlinkRight',
    EYE_WIDE_LEFT: 'eyeWideLeft',
    EYE_WIDE_RIGHT: 'eyeWideRight',
    MOUTH_SMILE_LEFT: 'mouthSmileLeft',
    MOUTH_SMILE_RIGHT: 'mouthSmileRight',
    MOUTH_FROWN_LEFT: 'mouthFrownLeft',
    MOUTH_FROWN_RIGHT: 'mouthFrownRight',
    MOUTH_OPEN: 'jawOpen',
    MOUTH_STRETCH_LEFT: 'mouthStretchLeft',
    MOUTH_STRETCH_RIGHT: 'mouthStretchRight',
    MOUTH_PRESS_LEFT: 'mouthPressLeft',
    MOUTH_PRESS_RIGHT: 'mouthPressRight',
    NOSE_WRINKLE_LEFT: 'noseSneerLeft',
    NOSE_WRINKLE_RIGHT: 'noseSneerRight'
  }

  // ==================== 模型初始化 ====================

  /**
   * 初始化 FaceLandmarker 和 PoseLandmarker 模型
   */
  async function initializeModels() {
    if (isModelReady.value) return

    modelLoadError.value = null

    try {
      // 动态导入 @mediapipe/tasks-vision，避免在 SSR 或未安装时报错
      const { FaceLandmarker, PoseLandmarker, FilesetResolver } =
        await import('@mediapipe/tasks-vision')

      const vision = await FilesetResolver.forVisionTasks(VISION_WASM_PATH)

      // 并行加载两个模型
      const [faceResult, poseResult] = await Promise.all([
        FaceLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: FACE_MODEL_PATH, delegate: 'GPU' },
          runningMode: 'VIDEO',
          outputFaceBlendshapes: true,
          numFaces: 1
        }),
        PoseLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: POSE_MODEL_PATH, delegate: 'GPU' },
          runningMode: 'VIDEO',
          numPoses: 1
        })
      ])

      faceLandmarker = faceResult
      poseLandmarker = poseResult
      isModelReady.value = true
    } catch (err) {
      let msg = '未知错误'
      if (err instanceof Error) {
        msg = err.message
      } else if (err && typeof err === 'object') {
        // MediaPipe 可能抛出 Event 对象
        msg = err.message || err.type || err.name || JSON.stringify(err)
      } else {
        msg = String(err)
      }
      console.error('[useVideoAnalysis] 模型加载失败:', err)
      modelLoadError.value = `模型加载失败: ${msg}`
      isModelReady.value = false
    }
  }

  // ==================== Blendshape 辅助 ====================

  /**
   * 从 blendshapes 数组中取指定名称的分数
   * @param {Array<{categoryName: string, score: number}>|null} blendshapes
   * @param {string} name
   * @returns {number}
   */
  function getBlendshape(blendshapes, name) {
    if (!blendshapes) return 0
    const item = blendshapes.find((b) => b.categoryName === name)
    return item ? item.score : 0
  }

  /**
   * 取左右两侧 blendshape 的平均值
   * @param {Array<{categoryName: string, score: number}>|null} blendshapes
   * @param {string} leftName
   * @param {string} rightName
   * @returns {number}
   */
  function getBlendshapeAvg(blendshapes, leftName, rightName) {
    return (getBlendshape(blendshapes, leftName) + getBlendshape(blendshapes, rightName)) / 2
  }

  // ==================== 表情推断 ====================

  /**
   * 基于 blendshapes 推断表情
   * @param {Array<{categoryName: string, score: number}>|null} blendshapes
   * @returns {{ dominant: string, scores: Object<string,number>, intensity: number, face_detected: boolean }}
   */
  function inferEmotion(blendshapes) {
    if (!blendshapes) {
      return { dominant: 'neutral', scores: {}, intensity: 0, face_detected: false }
    }

    const mouthSmile = getBlendshapeAvg(blendshapes, BS.MOUTH_SMILE_LEFT, BS.MOUTH_SMILE_RIGHT)
    const mouthFrown = getBlendshapeAvg(blendshapes, BS.MOUTH_FROWN_LEFT, BS.MOUTH_FROWN_RIGHT)
    const browInnerUpVal = getBlendshape(blendshapes, BS.BROW_INNER_UP)
    const eyeWide = getBlendshapeAvg(blendshapes, BS.EYE_WIDE_LEFT, BS.EYE_WIDE_RIGHT)
    const mouthOpen = getBlendshape(blendshapes, BS.MOUTH_OPEN)
    const mouthStretch = getBlendshapeAvg(
      blendshapes,
      BS.MOUTH_STRETCH_LEFT,
      BS.MOUTH_STRETCH_RIGHT
    )
    const noseWrinkle = getBlendshapeAvg(blendshapes, BS.NOSE_WRINKLE_LEFT, BS.NOSE_WRINKLE_RIGHT)
    const mouthPress = getBlendshapeAvg(blendshapes, BS.MOUTH_PRESS_LEFT, BS.MOUTH_PRESS_RIGHT)

    const scores = {
      happy: mouthSmile,
      sad: mouthFrown * (1 - browInnerUpVal),
      angry: browInnerUpVal * mouthFrown,
      surprised: eyeWide * mouthOpen,
      fear: browInnerUpVal * eyeWide * (1 - mouthStretch),
      disgust: Math.max(noseWrinkle, mouthPress),
      neutral: 0
    }

    // 按规则推断 dominant
    let dominant = 'neutral'

    if (mouthSmile > 0.3) {
      dominant = 'happy'
    } else if (mouthFrown > 0.2 && browInnerUpVal < 0.1) {
      dominant = 'sad'
    } else if (browInnerUpVal > 0.3 && mouthFrown > 0.15) {
      dominant = 'angry'
    } else if (eyeWide > 0.2 && mouthOpen > 0.3) {
      dominant = 'surprised'
    } else if (browInnerUpVal > 0.25 && eyeWide > 0.2 && mouthStretch < 0.1) {
      dominant = 'fear'
    } else if (noseWrinkle > 0.2 || mouthPress > 0.3) {
      dominant = 'disgust'
    }

    // neutral 得分：所有其他情绪都不高时设为余量
    const maxOtherScore = Math.max(...Object.values(scores).filter((v) => v !== undefined))
    scores.neutral = Math.max(0, 1 - maxOtherScore)

    const intensity = dominant === 'neutral' ? scores.neutral : scores[dominant] || 0

    return { dominant, scores, intensity, face_detected: true }
  }

  // ==================== 姿态评分 ====================

  /**
   * 基于 PoseLandmarker 的关键点计算姿态评分
   * @param {Array<Array<{x:number,y:number,z:number,visibility:number}>>|null} poseLandmarks
   * @returns {{ posture: string, head_tilt_angle: number, gaze_direction: string, shoulder_balance: number, posture_score: number }}
   */
  function computePosture(poseLandmarks) {
    const defaultResult = {
      posture: 'upright',
      head_tilt_angle: 0,
      gaze_direction: 'center',
      shoulder_balance: 100,
      posture_score: 100
    }

    if (!poseLandmarks || poseLandmarks.length === 0) return defaultResult

    const lm = poseLandmarks[0]

    // PoseLandmarker 关键点索引（33 点中的关键项）
    const NOSE = 0
    const LEFT_SHOULDER = 11
    const RIGHT_SHOULDER = 12
    const LEFT_EAR = 7
    const RIGHT_EAR = 8

    const nose = lm[NOSE]
    const leftShoulder = lm[LEFT_SHOULDER]
    const rightShoulder = lm[RIGHT_SHOULDER]
    const leftEar = lm[LEFT_EAR]
    const rightEar = lm[RIGHT_EAR]

    if (!nose || !leftShoulder || !rightShoulder) return defaultResult

    // --- 肩膀水平度 ---
    const shoulderDy = Math.abs(leftShoulder.y - rightShoulder.y)
    const shoulderWidth = Math.abs(leftShoulder.x - rightShoulder.x) || 0.01
    const shoulderImbalance = shoulderDy / shoulderWidth
    const shoulderBalance = Math.max(0, Math.min(100, 100 - shoulderImbalance * 500))

    // --- 头部倾斜 ---
    const midShoulderX = (leftShoulder.x + rightShoulder.x) / 2
    const headOffsetX = Math.abs(nose.x - midShoulderX)
    const headTiltAngle = headOffsetX * 180 // 近似角度映射

    // --- 视线方向 ---
    let gazeDirection = 'center'
    const earMidX = (leftEar.x + rightEar.x) / 2
    const noseEarOffset = nose.x - earMidX

    if (noseEarOffset > 0.05) {
      gazeDirection = 'right'
    } else if (noseEarOffset < -0.05) {
      gazeDirection = 'left'
    }

    // 纵向：鼻子相对肩膀中点的 y 偏移判断仰视/俯视
    // 注意：摄像头通常在眼睛上方或平齐，正常坐姿 noseShoulderDy 自然偏负
    // 阈值需要较宽松，避免正常坐姿误判
    const midShoulderY = (leftShoulder.y + rightShoulder.y) / 2
    const noseShoulderDy = nose.y - midShoulderY
    if (noseShoulderDy < -0.35) {
      gazeDirection = 'up'
    } else if (noseShoulderDy > 0.2) {
      gazeDirection = 'down'
    }

    // --- 综合姿态评分 ---
    const headAlignment = Math.max(0, Math.min(100, 100 - headTiltAngle * 2))
    const gazeCenter = gazeDirection === 'center' ? 100 : 50
    const postureScore = Math.round(0.5 * shoulderBalance + 0.3 * headAlignment + 0.2 * gazeCenter)

    // --- 姿态分类 ---
    let posture = 'upright'
    if (shoulderBalance < 50 || headTiltAngle > 20) {
      posture = 'slouching'
    } else if (headTiltAngle > 10) {
      posture = 'head_tilt'
    } else if (noseShoulderDy < -0.1) {
      posture = 'leaning_back'
    } else if (noseShoulderDy > 0.02 && noseShoulderDy < 0.15) {
      posture = 'leaning_forward'
    }

    return {
      posture,
      head_tilt_angle: Math.round(headTiltAngle * 10) / 10,
      gaze_direction: gazeDirection,
      shoulder_balance: Math.round(shoulderBalance),
      posture_score: postureScore
    }
  }

  // ==================== 注意力评分 ====================

  /**
   * 计算注意力评分（基于眨眼频率和视线稳定性）
   * @param {Array<{categoryName: string, score: number}>|null} blendshapes
   * @param {string} gazeDirection
   * @param {number} now
   * @returns {{ attention_score: number, blink_rate: number, gaze_stability: number }}
   */
  function computeAttention(blendshapes, gazeDirection, now) {
    // 眨眼检测：追踪 eyeBlink 的上升沿
    const blinkValue = getBlendshapeAvg(blendshapes, BS.EYE_BLINK_LEFT, BS.EYE_BLINK_RIGHT)

    if (prevBlinkValue < BLINK_FALLING_THRESHOLD && blinkValue >= BLINK_RISING_THRESHOLD) {
      blinkTimestamps.push(now)
    }
    prevBlinkValue = blinkValue

    // 清理超出窗口的眨眼记录
    blinkTimestamps = blinkTimestamps.filter((t) => now - t < ATTENTION_WINDOW_MS)
    const blinkRate = blinkTimestamps.length // 次/分钟

    // 视线方向变化追踪
    if (gazeDirection !== prevGazeDirection) {
      gazeChangeTimestamps.push(now)
      prevGazeDirection = gazeDirection
    }
    gazeChangeTimestamps = gazeChangeTimestamps.filter((t) => now - t < ATTENTION_WINDOW_MS)

    // 视线稳定性：变化越少越稳定
    const gazeChanges = gazeChangeTimestamps.length
    const gazeStability = Math.max(
      0,
      Math.min(100, 100 - (gazeChanges - GAZE_CHANGE_THRESHOLD) * 10)
    )

    // 眨眼频率评分：正常范围 15-20 次/分钟，偏离越远越低
    const blinkDeviation = Math.abs(blinkRate - 17.5)
    const blinkScore = Math.max(0, Math.min(100, 100 - blinkDeviation * 5))

    const attentionScore = Math.round(0.5 * blinkScore + 0.5 * gazeStability)

    return {
      attention_score: attentionScore,
      blink_rate: blinkRate,
      gaze_stability: Math.round(gazeStability)
    }
  }

  // ==================== 单帧分析 ====================

  /**
   * 分析单帧视频
   * @param {HTMLVideoElement} videoElement
   * @returns {{
   *   emotion: { dominant: string, scores: Object<string,number>, intensity: number, face_detected: boolean },
   *   posture: { posture: string, head_tilt_angle: number, gaze_direction: string, shoulder_balance: number, posture_score: number },
   *   attention: { attention_score: number, blink_rate: number, gaze_stability: number },
   *   timestamp: number
   * }|null}
   */
  function analyzeFrame(videoElement) {
    if (!isModelReady.value || !faceLandmarker || !poseLandmarker) return null
    if (!videoElement || videoElement.readyState < 2) return null

    const now = Date.now()
    const currentTimeMs = videoElement.currentTime * 1000

    // FaceLandmarker 分析
    let faceResult
    try {
      faceResult = faceLandmarker.detectForVideo(videoElement, currentTimeMs)
    } catch {
      return null
    }

    const blendshapes =
      faceResult && faceResult.faceBlendshapes && faceResult.faceBlendshapes.length > 0
        ? faceResult.faceBlendshapes[0].categories
        : null

    const emotion = inferEmotion(blendshapes)

    // PoseLandmarker 分析
    let poseResult
    try {
      poseResult = poseLandmarker.detectForVideo(videoElement, currentTimeMs)
    } catch {
      return null
    }

    const poseLandmarks =
      poseResult && poseResult.landmarks && poseResult.landmarks.length > 0
        ? poseResult.landmarks
        : null

    const posture = computePosture(poseLandmarks)

    const attention = computeAttention(blendshapes, posture.gaze_direction, now)

    const result = { emotion, posture, attention, timestamp: now }
    lastResult.value = result
    return result
  }

  // ==================== 分析循环 ====================

  function startFpsCounter() {
    stopFpsCounter()
    fpsFrameCount = 0
    fpsIntervalId = setInterval(() => {
      analysisFps.value = fpsFrameCount
      fpsFrameCount = 0
    }, 1000)
  }

  function stopFpsCounter() {
    if (fpsIntervalId != null) {
      clearInterval(fpsIntervalId)
      fpsIntervalId = null
    }
  }

  /**
   * 分析循环核心 — 以 ~10fps 节流调用 analyzeFrame
   * @param {DOMHighResTimeStamp} timestamp
   */
  function analysisLoop(timestamp) {
    if (!isAnalyzing.value) return

    if (timestamp - lastAnalysisTime >= TARGET_INTERVAL) {
      if (currentVideoElement) {
        analyzeFrame(currentVideoElement)
        fpsFrameCount++
      }
      lastAnalysisTime = timestamp
    }

    animationFrameId = requestAnimationFrame(analysisLoop)
  }

  /**
   * 启动实时分析循环
   * @param {HTMLVideoElement} videoElement
   */
  function startAnalysis(videoElement) {
    if (isAnalyzing.value) return
    if (!isModelReady.value) return

    currentVideoElement = videoElement
    isAnalyzing.value = true
    lastAnalysisTime = 0

    // 重置注意力追踪状态
    prevBlinkValue = 0
    blinkTimestamps = []
    prevGazeDirection = 'center'
    gazeChangeTimestamps = []

    startFpsCounter()
    animationFrameId = requestAnimationFrame(analysisLoop)
  }

  /**
   * 停止分析循环
   */
  function stopAnalysis() {
    isAnalyzing.value = false
    currentVideoElement = null

    if (animationFrameId != null) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }

    stopFpsCounter()
    analysisFps.value = 0
  }

  // ==================== 生命周期 ====================

  onUnmounted(() => {
    stopAnalysis()

    // 释放 MediaPipe 模型资源
    if (faceLandmarker) {
      faceLandmarker.close()
      faceLandmarker = null
    }
    if (poseLandmarker) {
      poseLandmarker.close()
      poseLandmarker = null
    }

    isModelReady.value = false
  })

  return {
    isAnalyzing,
    isModelReady,
    modelLoadError,
    analysisFps,
    lastResult,
    initializeModels,
    startAnalysis,
    stopAnalysis,
    analyzeFrame
  }
}
