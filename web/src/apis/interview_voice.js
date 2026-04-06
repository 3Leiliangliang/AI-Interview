import { apiPost } from './base'

export const interviewVoiceApi = {
  startVoiceSession: (payload) => apiPost('/api/interview/voice/session/start', payload),
  buildVoiceWsUrl: ({ voiceSessionId, token }) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const params = new URLSearchParams({
      voice_session_id: voiceSessionId,
      token
    })
    return `${protocol}//${host}/api/interview/voice/ws?${params.toString()}`
  }
}
