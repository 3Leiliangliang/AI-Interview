import { apiDelete, apiGet, apiPost, apiPut } from './base'

export const jobApi = {
  /**
   * 获取职位描述列表
   * @param {Object} params - 查询参数
   * @param {string} [params.status] - 按状态筛选 (draft/active/closed)
   * @param {number} [params.skip=0] - 跳过的记录数
   * @param {number} [params.limit=20] - 返回的记录数
   * @returns {Promise<{jobs: Array, total: number, skip: number, limit: number}>}
   */
  getJobs: async (params = {}) => {
    const { status, skip = 0, limit = 20 } = params
    const queryParams = new URLSearchParams()
    if (status) queryParams.append('status', status)
    queryParams.append('skip', String(skip))
    queryParams.append('limit', String(limit))

    return apiGet(`/api/job?${queryParams.toString()}`)
  },

  /**
   * 获取单个职位描述详情
   * @param {number} jobId - 职位描述ID
   * @returns {Promise<{job: Object}>}
   */
  getJobDetail: async (jobId) => {
    return apiGet(`/api/job/${jobId}`)
  },

  /**
   * 创建职位描述
   * @param {Object} jobData - 职位描述数据
   * @returns {Promise<{job: Object}>}
   */
  createJob: async (jobData) => {
    return apiPost('/api/job', jobData)
  },

  /**
   * 更新职位描述
   * @param {number} jobId - 职位描述ID
   * @param {Object} jobData - 更新的数据
   * @returns {Promise<{job: Object}>}
   */
  updateJob: async (jobId, jobData) => {
    return apiPut(`/api/job/${jobId}`, jobData)
  },

  /**
   * 删除职位描述
   * @param {number} jobId - 职位描述ID
   * @returns {Promise<{message: string}>}
   */
  deleteJob: async (jobId) => {
    return apiDelete(`/api/job/${jobId}`)
  },

  /**
   * 简历与JD匹配
   * @param {number} jobId - 职位描述ID
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
