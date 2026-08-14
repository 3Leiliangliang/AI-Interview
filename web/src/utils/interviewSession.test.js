import assert from 'node:assert/strict'
import test from 'node:test'

import { normalizeInterviewProgress } from './interviewSession.js'

test('空 todo 使用固定六阶段并定位第一步', () => {
  const progress = normalizeInterviewProgress([])

  assert.equal(progress.steps.length, 6)
  assert.equal(progress.currentIndex, 0)
  assert.equal(progress.completedCount, 0)
  assert.equal(progress.steps[0].status, 'in_progress')
})

test('优先定位进行中的阶段并保留真实文案', () => {
  const progress = normalizeInterviewProgress([
    { content: '开场', status: 'completed' },
    { content: '项目追问', status: 'in_progress' },
    { content: '技术提问', status: 'pending' }
  ])

  assert.equal(progress.currentIndex, 1)
  assert.equal(progress.completedCount, 1)
  assert.equal(progress.steps[1].label, '项目追问')
})

test('全部完成时定位最后一步', () => {
  const progress = normalizeInterviewProgress(
    Array.from({ length: 6 }, (_, index) => ({
      content: `阶段 ${index + 1}`,
      status: 'completed'
    }))
  )

  assert.equal(progress.currentIndex, 5)
  assert.equal(progress.completedCount, 6)
})

test('未知状态按待进行处理', () => {
  const progress = normalizeInterviewProgress([{ content: '开场', status: 'unknown' }])

  assert.equal(progress.steps[0].status, 'in_progress')
  assert.equal(progress.completedCount, 0)
})
