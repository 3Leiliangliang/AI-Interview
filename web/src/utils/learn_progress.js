/**
 * 知识学习进度的本地存储读写。
 *
 * 三级页面（专题列表 / 专题详情 / 文档阅读）共用同一套 key，
 * 保证「已读篇数」「稍后读」「掌握状态」在各级页面里显示一致。
 */

const dbKey = (dbId, name) => `learn-db-${dbId}-${name}`
const docKey = (dbId, name) => `learn-doc-${dbId}-${name}`

const GLOBAL_LAST_DOC_KEY = 'learn-last-doc'

const readJson = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

const persistJson = (key, value) => {
  localStorage.setItem(key, JSON.stringify(value))
}

const readIdSet = (key) => {
  const value = readJson(key, [])
  return new Set(Array.isArray(value) ? value.map(String) : [])
}

/** 掌握状态：{ [fileId]: 'mastered' | 'review' | 'todo' } */
export const readMasteryMap = (dbId) => {
  const value = readJson(docKey(dbId, 'mastery'), {})
  return value && typeof value === 'object' ? value : {}
}

export const persistMasteryMap = (dbId, value) => persistJson(docKey(dbId, 'mastery'), value)

/** 笔记：{ [fileId]: string } */
export const readNotesMap = (dbId) => {
  const value = readJson(docKey(dbId, 'notes'), {})
  return value && typeof value === 'object' ? value : {}
}

export const persistNotesMap = (dbId, value) => persistJson(docKey(dbId, 'notes'), value)

/** 累计阅读秒数：{ [fileId]: number } */
export const readSecondsMap = (dbId) => {
  const value = readJson(docKey(dbId, 'read-seconds'), {})
  return value && typeof value === 'object' ? value : {}
}

export const persistSecondsMap = (dbId, value) => persistJson(docKey(dbId, 'read-seconds'), value)

/** 打开次数：{ [fileId]: number }，用于估算单篇阅读进度 */
export const readVisitCounts = (dbId) => {
  const value = readJson(dbKey(dbId, 'visits'), {})
  return value && typeof value === 'object' ? value : {}
}

export const persistVisitCounts = (dbId, value) => persistJson(dbKey(dbId, 'visits'), value)

export const readFavoriteIds = (dbId) => readIdSet(dbKey(dbId, 'favorites'))

export const persistFavoriteIds = (dbId, idSet) => persistJson(dbKey(dbId, 'favorites'), [...idSet])

export const readReadLaterIds = (dbId) => readIdSet(dbKey(dbId, 'read-later'))

export const persistReadLaterIds = (dbId, idSet) =>
  persistJson(dbKey(dbId, 'read-later'), [...idSet])

/** 某个专题内上次学习的文档 */
export const readLastDoc = (dbId) => {
  const value = readJson(dbKey(dbId, 'last-doc'), null)
  return value && typeof value === 'object' ? value : null
}

export const persistLastDoc = (dbId, value) => persistJson(dbKey(dbId, 'last-doc'), value)

/** 跨专题的「继续上次学习」入口 */
export const readGlobalLastDoc = () => {
  const value = readJson(GLOBAL_LAST_DOC_KEY, null)
  return value && typeof value === 'object' ? value : null
}

export const persistGlobalLastDoc = (value) => persistJson(GLOBAL_LAST_DOC_KEY, value)

/** 已标记掌握的篇数 */
export const countMastered = (dbId) =>
  Object.values(readMasteryMap(dbId)).filter((status) => status === 'mastered').length

/** 专题学习进度百分比 */
export const computeDbProgress = (dbId, fileCount) => {
  const total = Number(fileCount || 0)
  if (total <= 0) return 0
  return Math.min(100, Math.round((countMastered(dbId) / total) * 100))
}

/** 累计阅读时长（分钟） */
export const countReadMinutes = (dbId) => {
  const totalSeconds = Object.values(readSecondsMap(dbId)).reduce(
    (sum, value) => sum + Number(value || 0),
    0
  )
  return Math.round(totalSeconds / 60)
}

export const countReadLater = (dbId) => readReadLaterIds(dbId).size
