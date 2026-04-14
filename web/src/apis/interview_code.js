import { apiGet, apiPost, apiPut } from './base'

export const interviewCodeApi = {
  getCodingSession: (threadId) => apiGet(`/api/interview/${threadId}/coding-session`),
  getInterviewResult: (threadId) => apiGet(`/api/interview/${threadId}/result`),
  getImprovementPlan: (threadId) => apiGet(`/api/interview/${threadId}/improvement-plan`),
  getLearningDocument: (dbId, fileId, locator = {}) => {
    const params = new URLSearchParams()
    if (locator.chunk_id) params.set('target_chunk_id', String(locator.chunk_id).trim())
    if (locator.chunk_index !== undefined && locator.chunk_index !== null && locator.chunk_index !== '') {
      params.set('target_chunk_index', String(locator.chunk_index))
    }
    if (locator.keyword) params.set('keyword', String(locator.keyword).trim())
    const query = params.toString()
    return apiGet(`/api/interview/knowledge/${dbId}/documents/${fileId}${query ? `?${query}` : ''}`)
  },
  finalizeInterviewResult: (threadId, payload = {}) =>
    apiPost(`/api/interview/${threadId}/result/finalize`, payload),
  startCodingSession: (threadId, payload = {}) =>
    apiPost(`/api/interview/${threadId}/coding-session/start`, payload),
  saveDraft: (threadId, payload) => apiPut(`/api/interview/${threadId}/coding-session/draft`, payload),
  runSample: (threadId, payload) => apiPost(`/api/interview/${threadId}/coding-session/run-sample`, payload),
  submitCodingSession: (threadId, payload) =>
    apiPost(`/api/interview/${threadId}/coding-session/submit`, payload),
  getSubmissionResult: (threadId, submissionId) =>
    apiGet(`/api/interview/${threadId}/coding-session/submissions/${submissionId}`),
  requestHint: (threadId, payload) => apiPost(`/api/interview/${threadId}/coding-session/hint`, payload)
}
