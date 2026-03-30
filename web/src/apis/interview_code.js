import { apiGet, apiPost, apiPut } from './base'

export const interviewCodeApi = {
  getCodingSession: (threadId) => apiGet(`/api/interview/${threadId}/coding-session`),
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
