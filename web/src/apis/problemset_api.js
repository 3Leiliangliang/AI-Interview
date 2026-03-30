import { apiGet } from './base'

export const problemsetApi = {
  getImportedProblemsets: () => apiGet('/api/interview/problemsets'),
  getProblemsetDetail: (packagePath) =>
    apiGet(`/api/interview/problemset-detail?package_path=${encodeURIComponent(packagePath)}`)
}
