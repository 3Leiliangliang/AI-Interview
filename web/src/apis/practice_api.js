import { apiGet, apiPost, apiPut } from './base'

export const practiceApi = {
  getDefaultPlan: () => apiGet('/api/interview/practice/plans/default'),
  getProblemDetail: (problemRef) => apiGet(`/api/interview/practice/problems/${encodeURIComponent(problemRef)}`),
  startSession: (problemRef) => apiPost(`/api/interview/practice/problems/${encodeURIComponent(problemRef)}/session`),
  getSession: (sessionId) => apiGet(`/api/interview/practice/sessions/${encodeURIComponent(sessionId)}`),
  saveDraft: (sessionId, payload) =>
    apiPut(`/api/interview/practice/sessions/${encodeURIComponent(sessionId)}/draft`, payload),
  runSample: (sessionId, payload) =>
    apiPost(`/api/interview/practice/sessions/${encodeURIComponent(sessionId)}/run-sample`, payload),
  submit: (sessionId, payload) =>
    apiPost(`/api/interview/practice/sessions/${encodeURIComponent(sessionId)}/submit`, payload),
  getSubmissionResult: (sessionId, submissionId) =>
    apiGet(
      `/api/interview/practice/sessions/${encodeURIComponent(sessionId)}/submissions/${encodeURIComponent(submissionId)}`
    )
}
