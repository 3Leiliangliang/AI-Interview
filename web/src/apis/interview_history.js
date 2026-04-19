import { apiGet } from './base'

export const interviewHistoryApi = {
  getHistory: ({ userId } = {}) => {
    const queryParams = new URLSearchParams()
    if (userId !== undefined && userId !== null && String(userId).trim() !== '') {
      queryParams.set('user_id', String(userId).trim())
    }
    const query = queryParams.toString()
    return apiGet(`/api/interview/history${query ? `?${query}` : ''}`)
  },
  getPersonalizedPath: ({ userId } = {}) => {
    const queryParams = new URLSearchParams()
    if (userId !== undefined && userId !== null && String(userId).trim() !== '') {
      queryParams.set('user_id', String(userId).trim())
    }
    const query = queryParams.toString()
    return apiGet(`/api/interview/personalized-path${query ? `?${query}` : ''}`)
  }
}
