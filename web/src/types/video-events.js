/**
 * @fileoverview 视频面试分析事件类型定义
 */

/**
 * 视频事件类型枚举
 * @readonly
 * @enum {string}
 */
export const VideoEventType = {
  EMOTION_DETECTED: 'emotion_detected',
  POSTURE_DETECTED: 'posture_detected',
  ATTENTION_CHANGE: 'attention_change',
  ALERT_TRIGGERED: 'alert_triggered',
  SESSION_SUMMARY: 'session_summary',
}

/**
 * 警告类型枚举
 * @readonly
 * @enum {string}
 */
export const AlertType = {
  NO_FACE_DETECTED: 'no_face_detected',
  LOOKING_AWAY: 'looking_away',
  SLOUCHING: 'slouching',
  LOW_ATTENTION: 'low_attention',
}

/**
 * 表情类型枚举
 * @readonly
 * @enum {string}
 */
export const EmotionType = {
  HAPPY: 'happy',
  SAD: 'sad',
  ANGRY: 'angry',
  NEUTRAL: 'neutral',
  FEAR: 'fear',
  DISGUST: 'disgust',
  SURPRISE: 'surprise',
}

/**
 * 姿态类型枚举
 * @readonly
 * @enum {string}
 */
export const PostureType = {
  UPRIGHT: 'upright',
  LEANING_FORWARD: 'leaning_forward',
  LEANING_BACK: 'leaning_back',
  HEAD_TILT: 'head_tilt',
  SLOUCHING: 'slouching',
}

/**
 * 视线方向枚举
 * @readonly
 * @enum {string}
 */
export const GazeDirection = {
  CENTER: 'center',
  LEFT: 'left',
  RIGHT: 'right',
  UP: 'up',
  DOWN: 'down',
}

/**
 * 创建表情事件
 * @param {string} sessionId
 * @param {string} dominant - 主要表情
 * @param {Object<string, number>} scores - 各表情置信度
 * @param {number} intensity - 情绪强度 0-1
 * @param {boolean} faceDetected - 是否检测到人脸
 * @returns {Object} 视频事件
 */
export function createEmotionEvent(sessionId, dominant, scores, intensity, faceDetected) {
  return {
    event_id: crypto.randomUUID(),
    session_id: sessionId,
    timestamp: Date.now(),
    sequence: 0, // 由调用方设置
    type: VideoEventType.EMOTION_DETECTED,
    data: { dominant, scores, intensity, face_detected: faceDetected },
    severity: 'low',
  }
}

/**
 * 创建姿态事件
 * @param {string} sessionId
 * @param {string} posture - 姿态类型
 * @param {number} headTiltAngle - 头部倾斜角度
 * @param {string} gazeDirection - 视线方向
 * @param {number} shoulderBalance - 肩膀平衡度 0-100
 * @param {number} postureScore - 综合姿态评分 0-100
 * @returns {Object} 视频事件
 */
export function createPostureEvent(
  sessionId,
  posture,
  headTiltAngle,
  gazeDirection,
  shoulderBalance,
  postureScore,
) {
  return {
    event_id: crypto.randomUUID(),
    session_id: sessionId,
    timestamp: Date.now(),
    sequence: 0,
    type: VideoEventType.POSTURE_DETECTED,
    data: {
      posture,
      head_tilt_angle: headTiltAngle,
      gaze_direction: gazeDirection,
      shoulder_balance: shoulderBalance,
      posture_score: postureScore,
    },
    severity: postureScore < 50 ? 'high' : postureScore < 70 ? 'medium' : 'low',
  }
}

/**
 * 创建注意力事件
 * @param {string} sessionId
 * @param {number} attentionScore - 注意力分数 0-100
 * @param {number} blinkRate - 眨眼频率
 * @param {number} gazeStability - 视线稳定性 0-100
 * @returns {Object} 视频事件
 */
export function createAttentionEvent(sessionId, attentionScore, blinkRate, gazeStability) {
  return {
    event_id: crypto.randomUUID(),
    session_id: sessionId,
    timestamp: Date.now(),
    sequence: 0,
    type: VideoEventType.ATTENTION_CHANGE,
    data: { attention_score: attentionScore, blink_rate: blinkRate, gaze_stability: gazeStability },
    severity: attentionScore < 40 ? 'high' : attentionScore < 60 ? 'medium' : 'low',
  }
}

/**
 * 创建警告事件
 * @param {string} sessionId
 * @param {string} alertType - 警告类型
 * @param {string} message - 警告信息
 * @param {number} durationSeconds - 持续时长
 * @param {string} suggestion - 改进建议
 * @returns {Object} 视频事件
 */
export function createAlertEvent(sessionId, alertType, message, durationSeconds, suggestion) {
  return {
    event_id: crypto.randomUUID(),
    session_id: sessionId,
    timestamp: Date.now(),
    sequence: 0,
    type: VideoEventType.ALERT_TRIGGERED,
    data: { alert_type: alertType, message, duration_seconds: durationSeconds, suggestion },
    severity: 'high',
  }
}

/**
 * 创建事件批次
 * @param {string} sessionId
 * @param {Array<Object>} events - 事件列表
 * @param {number} batchSequence - 批次序号
 * @returns {Object} 事件批次
 */
export function createEventBatch(sessionId, events, batchSequence) {
  return {
    session_id: sessionId,
    batch_id: crypto.randomUUID(),
    events,
    batch_timestamp: Date.now(),
    batch_sequence: batchSequence,
  }
}
