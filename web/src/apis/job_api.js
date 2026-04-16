import { apiGet, apiPost } from './base'

export const jobApi = {
  /**
   * 获取内置岗位列表
   * @returns {Promise<{jobs: Array, total: number}>}
   */
  getJobs: async (params = {}) => {
    const { skip = 0, limit = 20 } = params
    const queryParams = new URLSearchParams()
    queryParams.append('skip', String(skip))
    queryParams.append('limit', String(limit))

    return apiGet(`/api/job?${queryParams.toString()}`)
  },

  /**
   * 获取岗位类型配置
   * @returns {Promise<{position_types: Array, default_position_key: string}>}
   */
  getPositionTypes: async () => {
    return apiGet('/api/job/position-types')
  },

  /**
   * 获取单个岗位详情
   * @param {number} jobId - 岗位ID
   * @returns {Promise<{job: Object}>}
   */
  getJobDetail: async (jobId) => {
    return apiGet(`/api/job/${jobId}`)
  },

  /**
   * 简历与JD匹配
   * @param {number} jobId - 岗位ID
   * @param {Object} resumeSummary - 简历结构化摘要
   * @returns {Promise<{match_result: Object}>}
   */
  matchResume: async (jobId, resumeSummary) => {
    return apiPost('/api/job/match', {
      job_id: jobId,
      resume_summary: resumeSummary,
    })
  },
}
