// 练习进度持久化（localStorage 边界）。
// 在旧 `practice-home-progress-v1` schema 上向后兼容扩展：
//   旧: { attempted_map, favorite_refs, last_problem_ref }
//   新: + { result_map: { [problemRef]: { everAccepted, latestStatus, updatedAt } } }
// 写入失败不破坏页面——localStorage 是外部边界（配额/隐私模式等），捕获异常保留内存状态。

const STORAGE_KEY = 'practice-home-progress-v1'

// 五态：未开始 / 练习中 / 未通过 / 已通过 / 判题异常
export const PROBLEM_STATUS = {
  NEW: 'new',
  ATTEMPTING: 'attempting',
  PASSED: 'passed',
  FAILED: 'failed',
  ERROR: 'error',
}

export const PROBLEM_STATUS_LABEL = {
  new: '未开始',
  attempting: '练习中',
  passed: '已通过',
  failed: '未通过',
  error: '判题异常',
}

const PENDING_STATUSES = new Set(['PENDING', 'JUDGING'])
const FAILED_STATUSES = new Set([
  'WRONG_ANSWER',
  'COMPILE_ERROR',
  'RUNTIME_ERROR',
  'MEMORY_LIMIT_EXCEEDED',
  'CPU_TIME_LIMIT_EXCEEDED',
  'REAL_TIME_LIMIT_EXCEEDED',
  'PARTIALLY_ACCEPTED',
])
const ERROR_STATUSES = new Set(['SYSTEM_ERROR'])
const ACCEPTED_STATUSES = new Set(['ACCEPTED'])

export const emptyProgress = () => ({
  attempted_map: {},
  favorite_refs: [],
  last_problem_ref: '',
  result_map: {},
})

const safeParse = (raw) => {
  try {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return emptyProgress()
    return {
      attempted_map: parsed.attempted_map && typeof parsed.attempted_map === 'object' ? parsed.attempted_map : {},
      favorite_refs: Array.isArray(parsed.favorite_refs) ? parsed.favorite_refs : [],
      last_problem_ref: String(parsed.last_problem_ref || ''),
      result_map: parsed.result_map && typeof parsed.result_map === 'object' ? parsed.result_map : {},
    }
  } catch {
    return emptyProgress()
  }
}

export const loadProgress = () => {
  if (typeof window === 'undefined') return emptyProgress()
  try {
    if (typeof window.localStorage === 'undefined') return emptyProgress()
    return safeParse(window.localStorage.getItem(STORAGE_KEY))
  } catch {
    return emptyProgress()
  }
}

export const saveProgress = (progress) => {
  if (typeof window === 'undefined') return
  try {
    if (typeof window.localStorage === 'undefined') return
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(progress))
  } catch {
    // 外部边界失败：保留内存状态即可，不回抛。
  }
}

// 记录"打开过"：PracticeProblem 直接深链也要写入，不依赖先经过首页。
export const markOpened = (progress, problemRef) => {
  const ref = String(problemRef)
  return {
    ...progress,
    attempted_map: { ...(progress.attempted_map || {}), [ref]: new Date().toISOString() },
    last_problem_ref: ref,
  }
}

// 记录判题终态。everAccepted 一旦为真保持为真：通过后再次提交失败不降级。
export const recordResult = (progress, problemRef, judgeStatus) => {
  const ref = String(problemRef)
  const status = String(judgeStatus || '').trim().toUpperCase()
  if (!status) return progress
  const prev = progress.result_map?.[ref]
  return {
    ...progress,
    result_map: {
      ...(progress.result_map || {}),
      [ref]: {
        everAccepted: Boolean(prev?.everAccepted) || ACCEPTED_STATUSES.has(status),
        latestStatus: status,
        updatedAt: new Date().toISOString(),
      },
    },
  }
}

// 五态归一化。仅打开未判题 = 练习中（绝不映射成未通过）；PENDING/JUDGING 保持练习中。
export const getProblemStatus = (progress, problemRef) => {
  const ref = String(problemRef)
  const attempted = Boolean(progress.attempted_map?.[ref])
  const result = progress.result_map?.[ref]
  if (!attempted && !result) return PROBLEM_STATUS.NEW
  if (!result) return PROBLEM_STATUS.ATTEMPTING
  if (result.everAccepted) return PROBLEM_STATUS.PASSED
  const status = result.latestStatus
  if (PENDING_STATUSES.has(status)) return PROBLEM_STATUS.ATTEMPTING
  if (FAILED_STATUSES.has(status)) return PROBLEM_STATUS.FAILED
  if (ERROR_STATUSES.has(status)) return PROBLEM_STATUS.ERROR
  return PROBLEM_STATUS.ATTEMPTING
}

// 个人通过率统计用：仅通过/未通过计入分母，排除练习中与判题异常。
export const hasRealResult = (progress, problemRef) => {
  const status = getProblemStatus(progress, problemRef)
  return status === PROBLEM_STATUS.PASSED || status === PROBLEM_STATUS.FAILED
}
