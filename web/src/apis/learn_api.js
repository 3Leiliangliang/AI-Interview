import { apiGet } from './base'

export const learnApi = {
  getDatabases: async () => apiGet('/api/interview/knowledge/databases'),
  getDatabaseDetail: async (dbId) => apiGet(`/api/interview/knowledge/databases/${dbId}`)
}
