import { apiPost, apiGet } from './base'

/**
 * 视频面试分析 API 模块
 */
export const videoApi = {
  /**
   * 发送视频分析事件批次
   * @param {Object} batch - 事件批次
   * @returns {Promise<{status: string, events_count: number}>}
   */
  sendEventBatch: (batch) => apiPost('/api/video/event', batch),

  /**
   * 获取视频分析状态
   * @param {string} sessionId - 会话ID
   * @returns {Promise<{session_id: string, events_in_buffer: number, status: string}>}
   */
  getStatus: (sessionId) => apiGet(`/api/video/status/${sessionId}`),

  /**
   * 获取视频分析聚合摘要
   * @param {string} sessionId - 会话ID
   * @returns {Promise<Object>}
   */
  getAggregate: (sessionId) => apiGet(`/api/video/aggregate/${sessionId}`),

  /**
   * 生成面试视频分析报告
   * @param {string} sessionId - 会话ID
   * @returns {Promise<Object>} 报告数据，包含 scores, recommendations, strengths 等
   */
  generateReport: (sessionId) => apiPost(`/api/video/report/${sessionId}`),
}
