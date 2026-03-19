import { apiDelete, apiGet, apiPost } from './base'

export const resumeApi = {
  getMyResumes: async () => {
    return apiGet('/api/resume')
  },

  getResumeDetail: async (resumeId) => {
    return apiGet(`/api/resume/${resumeId}`)
  },

  uploadResume: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiPost('/api/resume', formData)
  },

  deleteResume: async (resumeId) => {
    return apiDelete(`/api/resume/${resumeId}`)
  }
}
