/**
 * API模块索引文件
 * 导出所有 API 模块，便于统一引入
 */

export * from './system_api'
export * from './knowledge_api'
export * from './agent_api'
export * from './tasker'
export * from './mindmap_api'
export * from './department_api'
export * from './mcp_api'
export * from './resume_api'
export * from './skill_api'
export * from './tool_api'
export * from './problemset_api'
export * from './interview_voice'

export {
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  apiAdminGet,
  apiAdminPost,
  apiAdminPut,
  apiAdminDelete,
  apiSuperAdminGet,
  apiSuperAdminPost,
  apiSuperAdminPut,
  apiSuperAdminDelete
} from './base'
