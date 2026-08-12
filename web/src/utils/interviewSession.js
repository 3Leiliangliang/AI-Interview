export const INTERVIEW_STAGE_LABELS = [
  '发起开场并请候选人自我介绍',
  '追问项目经历与技术细节',
  '相关技术知识提问',
  '代码考核',
  '评估岗位匹配度与风险点',
  '输出总结与评分卡'
]

const normalizeStatus = (status) => {
  if (status === 'completed') return 'completed'
  if (status === 'in_progress') return 'in_progress'
  return 'pending'
}

export const normalizeInterviewProgress = (rawTodos) => {
  const todos = Array.isArray(rawTodos) ? rawTodos.slice(0, INTERVIEW_STAGE_LABELS.length) : []
  const steps = INTERVIEW_STAGE_LABELS.map((fallbackLabel, index) => ({
    label: String(todos[index]?.content || fallbackLabel).trim() || fallbackLabel,
    status: normalizeStatus(todos[index]?.status)
  }))

  let currentIndex = steps.findIndex((step) => step.status === 'in_progress')
  if (currentIndex < 0) {
    currentIndex = steps.findIndex((step) => step.status !== 'completed')
  }
  if (currentIndex < 0) currentIndex = steps.length - 1

  steps.forEach((step, index) => {
    if (index === currentIndex && step.status === 'pending') {
      step.status = 'in_progress'
    }
  })

  return {
    steps,
    currentIndex,
    completedCount: steps.filter((step) => step.status === 'completed').length
  }
}

export const formatInterviewElapsed = (elapsedSeconds) => {
  const total = Math.max(0, Math.floor(Number(elapsedSeconds) || 0))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const parts = hours > 0 ? [hours, minutes, seconds] : [minutes, seconds]
  return parts.map((part) => String(part).padStart(2, '0')).join(':')
}
