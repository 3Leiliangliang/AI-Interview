import assert from 'node:assert/strict'

import {
  PROBLEM_STATUS,
  getProblemStatus,
  loadProgress,
  markOpened,
  recordResult,
  saveProgress,
} from '../src/utils/practiceProgress.js'
import { matchWeaknessCandidates, parseWeaknessTokens } from '../src/utils/weaknessPractice.js'

const topics = [
  {
    topic_key: 'distributed-transaction',
    topic_name: '分布式事务',
    topic_tags: ['事务'],
    problems: [{ problem_ref: 'Case-Sensitive-Ref', title: '幂等转账' }],
  },
]

assert.deepEqual(parseWeaknessTokens([' JVM ', '', 'jvm', 'x'.repeat(41)]), ['jvm'])
assert.deepEqual(
  parseWeaknessTokens(['a'.repeat(40), 'b', 'c', 'd', 'e']),
  ['a'.repeat(40), 'b', 'c', 'd'],
)

const directProblemRefMatch = matchWeaknessCandidates(
  [{ query: 'case-sensitive-ref', label: '题号', type: 'report' }],
  topics,
)
assert.deepEqual(directProblemRefMatch.matchedTopicKeys, ['distributed-transaction'])
assert.deepEqual(directProblemRefMatch.matchedProblemRefs, ['Case-Sensitive-Ref'])
assert.equal(directProblemRefMatch.unresolved.length, 0)

const unresolvedMatch = matchWeaknessCandidates(
  [{ query: '不存在的弱项', label: '未知', type: 'report' }],
  topics,
)
assert.deepEqual(unresolvedMatch.matchedTopicKeys, [])
assert.equal(unresolvedMatch.unresolved.length, 1)

let progress = { attempted_map: {}, favorite_refs: [], result_map: {} }
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.NEW)
progress = markOpened(progress, 'p1')
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.ATTEMPTING)
progress = recordResult(progress, 'p1', 'PENDING')
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.ATTEMPTING)
progress = recordResult(progress, 'p1', 'WRONG_ANSWER')
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.FAILED)
progress = recordResult(progress, 'p1', 'SYSTEM_ERROR')
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.ERROR)
progress = recordResult(progress, 'p1', 'ACCEPTED')
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.PASSED)
progress = recordResult(progress, 'p1', 'RUNTIME_ERROR')
assert.equal(getProblemStatus(progress, 'p1'), PROBLEM_STATUS.PASSED)

Object.defineProperty(globalThis, 'window', {
  configurable: true,
  value: Object.defineProperty({}, 'localStorage', {
    get() {
      throw new DOMException('Access denied', 'SecurityError')
    },
  }),
})
assert.deepEqual(loadProgress(), {
  attempted_map: {},
  favorite_refs: [],
  last_problem_ref: '',
  result_map: {},
})
assert.doesNotThrow(() => saveProgress({ attempted_map: {}, favorite_refs: [], result_map: {} }))

Object.defineProperty(globalThis, 'window', {
  configurable: true,
  value: {
    localStorage: {
      getItem() {
        throw new DOMException('Read denied', 'SecurityError')
      },
      setItem() {
        throw new DOMException('Write denied', 'SecurityError')
      },
    },
  },
})
assert.deepEqual(loadProgress(), {
  attempted_map: {},
  favorite_refs: [],
  last_problem_ref: '',
  result_map: {},
})
assert.doesNotThrow(() => saveProgress({ attempted_map: {}, favorite_refs: [], result_map: {} }))

console.log('UI v3 contract checks passed')
