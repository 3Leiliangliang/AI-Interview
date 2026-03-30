import { apiDelete, apiGet, apiPost } from './base'

/**
 * 通过轮询监听简历提取进度（EventSource 无法传 Authorization header，改用轮询）
 * @param {number} resumeId - 简历 ID
 * @param {Object} callbacks - 回调函数集合
 * @param {Function} callbacks.onProgress - 进度更新回调 (data) => void
 * @param {Function} callbacks.onCompleted - 提取完成回调 (summary) => void
 * @param {Function} callbacks.onFailed - 提取失败回调 (error) => void
 * @returns {{ stop: () => void }} - 调用 .stop() 停止轮询
 */
function mapStatusToStage(status) {
  if (status === 'completed' || status === 'failed') return status
  if (status === 'processing' || status === 'pending' || status === 'extracting') return 'extracting'
  return 'extracting'
}

export function watchExtractProgress(resumeId, { onProgress, onCompleted, onFailed }) {
  let stopped = false
  const POLL_INTERVAL = 2000

  const poll = async () => {
    if (stopped) return
    try {
      const data = await apiGet(`/api/resume/${resumeId}`)
      const resume = data?.resume
      if (!resume) {
        onFailed?.('简历不存在')
        return
      }

      const status = resume.summary_status
      if (status === 'completed') {
        onCompleted?.(resume.summary_json)
        return
      } else if (status === 'failed') {
        onFailed?.(resume.summary_error || '提取失败')
        return
      } else {
        onProgress?.({ stage: mapStatusToStage(status) })
      }
    } catch {
      // 网络错误，继续轮询
    }

    if (!stopped) {
      setTimeout(poll, POLL_INTERVAL)
    }
  }

  poll()

  return {
    close: () => {
      stopped = true
    },
  }
}

export const resumeApi = {
  getMyResumes: async () => {
    return apiGet('/api/resume')
  },

  getResumeDetail: async (resumeId) => {
    return apiGet(`/api/resume/${resumeId}`)
  },

  uploadResume: async (file, jobId = null) => {
    const formData = new FormData()
    formData.append('file', file)
    if (jobId) {
      formData.append('job_id', String(jobId))
    }
    return apiPost('/api/resume', formData)
  },

  deleteResume: async (resumeId) => {
    return apiDelete(`/api/resume/${resumeId}`)
  },

  matchResume: async (resumeId, jobId) => {
    return apiPost(`/api/resume/${resumeId}/match`, {
      job_id: jobId,
    })
  },

  matchResumeAutoDetect: async (resumeId) => {
    return apiPost(`/api/resume/${resumeId}/match`, {
      auto_detect: true,
    })
  },

  detectPosition: async (resumeId) => {
    return apiPost(`/api/resume/${resumeId}/detect-position`, {})
  },

  retryExtract: async (resumeId) => {
    return apiPost(`/api/resume/${resumeId}/retry-extract`, {})
  },
}
