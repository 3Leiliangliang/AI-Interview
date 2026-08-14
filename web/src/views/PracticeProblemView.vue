<template>
  <div class="practice-problem">
    <!-- 顶栏 -->
    <div class="top">
      <div class="top-nav">
        <button class="b" type="button" @click="goBack">返回题单</button>
        <button class="b" type="button" :disabled="!hasPrevProblem" @click="navigateProblem(-1)">
          <LeftOutlined />
          上一题
        </button>
        <button class="b" type="button" :disabled="!hasNextProblem" @click="navigateProblem(1)">
          下一题
          <RightOutlined />
        </button>
      </div>
      <div v-if="problem" class="top-title">
        <span class="top-title-text">{{ problem.title }}</span>
        <span class="top-title-meta">#{{ problem.problem_index }} · {{ problem.primary_topic_tag || '专题练习' }}</span>
      </div>
      <div class="top-actions">
        <button class="b" type="button" :disabled="runningSample" @click="handleRunSample">
          {{ runningSample ? '运行中…' : '运行样例' }}
        </button>
        <button class="b p" type="button" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? '提交中…' : '提交判题' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="state-panel"><a-spin /></div>

    <div v-else-if="!problem || !session" class="state-panel"><a-empty description="题目加载失败" /></div>

    <div v-else class="problem-layout">
      <!-- 左栏：题面 -->
      <section class="problem-panel">
        <div class="problem-head">
          <span class="problem-title">{{ problem.title }}</span>
          <span class="badge">{{ difficultyLabel }}</span>
        </div>
        <div class="problem-meta">{{ metaText }}</div>
        <p v-if="problem.summary" class="problem-summary">{{ problem.summary }}</p>

        <div class="lab problem-lab">题目描述</div>
        <p class="problem-text">{{ problem.description }}</p>

        <div class="lab problem-lab">输入说明</div>
        <p class="problem-text">{{ problem.input_description || '（无）' }}</p>

        <div class="lab problem-lab">输出说明</div>
        <p class="problem-text">{{ problem.output_description || '（无）' }}</p>

        <div class="lab problem-lab">样例</div>
        <div v-if="problemExamples.length" class="examples-list">
          <div v-for="(example, index) in problemExamples" :key="index" class="example-box">
            <div class="example-item">
              <div class="example-label">样例 {{ index + 1 }}</div>
              <div class="example-col">
                <div class="console-title">输入</div>
                <pre class="console-block">{{ example.input }}</pre>
              </div>
              <div class="example-col">
                <div class="console-title">输出</div>
                <pre class="console-block">{{ example.output }}</pre>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-text">当前题目未提供样例</div>
      </section>

      <!-- 中栏：编辑器 + 判题 -->
      <section class="editor-panel">
        <div class="editor-bar">
          <div class="language-switch">
            <span
              v-for="opt in languageOptions"
              :key="opt.value"
              class="opt"
              :class="{ on: opt.value === language }"
              @click="language = opt.value"
            >{{ opt.label }}</span>
          </div>
          <span class="save-state">{{ saveStateText }}{{ lastSavedAt ? ' · ' + lastSavedAt : '' }}</span>
        </div>

        <div class="editor-body">
          <div class="line-numbers">
            <div v-for="n in lineCount" :key="n">{{ n }}</div>
          </div>
          <textarea
            v-model="draftCode"
            class="code-area"
            spellcheck="false"
            :style="{ height: editorHeight + 'px' }"
            :placeholder="editorPlaceholder"
          ></textarea>
        </div>

        <div class="judge-panel">
          <div class="judge-tabs">
            <div class="judge-tab" :class="{ on: bottomTab === 'run' }" @click="bottomTab = 'run'">运行结果</div>
            <div class="judge-tab" :class="{ on: bottomTab === 'cases' }" @click="bottomTab = 'cases'">测试用例</div>
            <div class="judge-tab" :class="{ on: bottomTab === 'submission' }" @click="bottomTab = 'submission'">提交结果</div>
            <div class="judge-tab" :class="{ on: bottomTab === 'metrics' }" @click="bottomTab = 'metrics'">性能分析</div>
          </div>

          <div class="judge-content">
            <template v-if="bottomTab === 'run'">
              <div v-if="sampleRunResult.status" class="result-overview">
                <span class="badge strong">{{ sampleBadgeText }}</span>
                <span v-if="sampleStatsText" class="result-stats">{{ sampleStatsText }}</span>
              </div>
              <div v-if="sampleRunResult.message" class="judge-message">{{ sampleRunResult.message }}</div>
              <div v-if="sampleRunResult.compile_error" class="console-section">
                <div class="console-title">编译错误</div>
                <pre class="console-block error">{{ sampleRunResult.compile_error }}</pre>
              </div>
              <table v-if="sampleRunResult.tests?.length" class="judge-table">
                <thead>
                  <tr><th>用例</th><th>结果</th><th>数据</th><th>用时</th></tr>
                </thead>
                <tbody>
                  <tr v-for="test in sampleRunResult.tests" :key="test.name">
                    <td>{{ test.name }}</td>
                    <td :class="test.passed ? 'pass' : 'fail'">{{ test.passed ? '通过' : '未通过' }}</td>
                    <td class="mono ellipsis">{{ testDataText(test) }}</td>
                    <td class="time">{{ test.cpu_time != null ? `${test.cpu_time} ms` : '—' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="sampleRunResult.stdout || sampleRunResult.stderr" class="console-section">
                <div v-if="sampleRunResult.stdout" class="console-title">stdout</div>
                <pre v-if="sampleRunResult.stdout" class="console-block">{{ sampleRunResult.stdout }}</pre>
                <div v-if="sampleRunResult.stderr" class="console-title">stderr</div>
                <pre v-if="sampleRunResult.stderr" class="console-block error">{{ sampleRunResult.stderr }}</pre>
              </div>
              <div
                v-if="!sampleRunResult.status && !sampleRunResult.compile_error && !sampleRunResult.stdout && !sampleRunResult.stderr"
                class="empty-text"
              >
                暂未运行样例
              </div>
            </template>

            <template v-else-if="bottomTab === 'cases'">
              <div v-if="problemExamples.length" class="examples-list">
                <div v-for="(example, index) in problemExamples" :key="index" class="example-box">
                  <div class="example-item">
                    <div class="example-label">样例 {{ index + 1 }}</div>
                    <div class="example-col">
                      <div class="console-title">输入</div>
                      <pre class="console-block">{{ example.input }}</pre>
                    </div>
                    <div class="example-col">
                      <div class="console-title">输出</div>
                      <pre class="console-block">{{ example.output }}</pre>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="empty-text">当前题目未提供测试用例</div>
            </template>

            <template v-else-if="bottomTab === 'submission'">
              <div v-if="currentJudgeStatus" class="result-overview">
                <span class="badge strong" :class="{ fail: !submissionPassed }">
                  {{ getStatusLabel(currentJudgeStatus, '未提交') }}
                </span>
                <span v-if="submissionStatsText" class="result-stats">{{ submissionStatsText }}</span>
              </div>
              <div v-if="submissionResult.message" class="judge-message">{{ submissionResult.message }}</div>
              <div v-if="submissionResult.compile_error" class="console-section">
                <div class="console-title">编译错误</div>
                <pre class="console-block error">{{ submissionResult.compile_error }}</pre>
              </div>
              <table v-if="judgeTests.length" class="judge-table">
                <thead>
                  <tr><th>用例</th><th>结果</th><th>信息</th><th>用时</th></tr>
                </thead>
                <tbody>
                  <tr v-for="test in judgeTests" :key="test.name">
                    <td>{{ test.name }}</td>
                    <td :class="test.passed ? 'pass' : 'fail'">{{ test.passed ? '通过' : '未通过' }}</td>
                    <td class="ellipsis">{{ test.message || '—' }}</td>
                    <td class="time">{{ test.cpu_time != null ? `${test.cpu_time} ms` : '—' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!currentJudgeStatus && !judgeTests.length" class="empty-text">
                暂未提交代码，提交后可在这里查看判题结果
              </div>
            </template>

            <template v-else>
              <div class="metrics-grid">
                <div v-for="item in performanceMetrics" :key="item.label" class="metric-item">
                  <div class="metric-label">{{ item.label }}</div>
                  <div class="metric-value">{{ item.value }}</div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- 右栏：学习面板 -->
      <section class="aside-panel">
        <div>
          <div class="lab">本题在考什么</div>
          <div class="points-list">
            <div v-for="point in examinationPoints" :key="point.name" class="point-row">
              <span class="point-name">{{ point.name }}</span>
              <span :class="['point-status', point.done ? 'done' : 'pending']">{{ point.status }}</span>
            </div>
            <div v-if="!examinationPoints.length" class="empty-text">暂无知识点标签</div>
          </div>
        </div>

        <div>
          <div class="lab">我的笔记</div>
          <textarea
            v-model="noteText"
            class="note-input"
            rows="5"
            placeholder="记录你的解题思路、易错点和复杂度分析"
          ></textarea>
          <div class="note-meta">{{ noteSavedText }}</div>
        </div>

        <div>
          <div class="mock-head">
            <span class="lab">模拟面试</span>
            <button class="b" type="button" @click="toggleMockMode">
              {{ mockModeEnabled ? '关闭' : '开启' }}
            </button>
          </div>
          <template v-if="mockModeEnabled">
            <div class="mock-timer">剩余时间：{{ mockCountdownText }}</div>
            <div class="mock-actions">
              <button class="b" type="button" :disabled="mockRunning" @click="startMockMode">开始</button>
              <button class="b" type="button" :disabled="!mockRunning" @click="finishMockMode">结束</button>
            </div>
            <div v-if="mockReport" class="mock-report">
              <div>编码耗时：{{ mockReport.durationText }}</div>
              <div>提交状态：{{ mockReport.submissionStatus }}</div>
              <div>样例状态：{{ mockReport.sampleStatus }}</div>
            </div>
          </template>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { LeftOutlined, RightOutlined } from '@ant-design/icons-vue'

import { practiceApi } from '@/apis/practice_api'
import { loadProgress, markOpened, recordResult, saveProgress } from '@/utils/practiceProgress'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const runningSample = ref(false)
const submitting = ref(false)
const problem = ref(null)
const session = ref(null)
const draftCode = ref('')
const language = ref('javascript')
const bottomTab = ref('run')
const saveStateText = ref('未保存')
const lastSavedAt = ref('')

const noteText = ref('')
const noteSavedText = ref('')

const mockModeEnabled = ref(false)
const mockRunning = ref(false)
const mockRemainingSeconds = ref(15 * 60)
const mockReport = ref(null)
let mockStartedAt = 0

const navigationProblems = ref([])

const pendingJudgeStatuses = new Set(['PENDING', 'JUDGING'])
const suppressDraftSave = ref(false)

let saveTimer = null
let pollTimer = null
let noteTimer = null
let mockTimer = null

const fallbackTemplateByLanguage = {
  javascript: ['function solve() {', '  // TODO: implement', '}', '', 'solve()'].join('\n'),
  python: ['def solve():', '    # TODO: implement', '    pass', '', "if __name__ == '__main__':", '    solve()'].join('\n'),
  java: [
    'import java.util.*;',
    '',
    'public class Main {',
    '    public static void main(String[] args) {',
    '        // TODO: implement',
    '    }',
    '}'
  ].join('\n'),
  cpp: [
    '#include <bits/stdc++.h>',
    'using namespace std;',
    '',
    'int main() {',
    '    // TODO: implement',
    '    return 0;',
    '}'
  ].join('\n'),
  c: ['#include <stdio.h>', '', 'int main() {', '    // TODO: implement', '    return 0;', '}'].join('\n')
}

const languageLabelMap = {
  javascript: 'JavaScript',
  c: 'C',
  cpp: 'C++',
  java: 'Java',
  python: 'Python'
}

const difficultyLabelMap = {
  easy: '简单',
  medium: '中等',
  hard: '困难'
}

const htmlDecoder =
  typeof window !== 'undefined' && typeof document !== 'undefined' ? document.createElement('textarea') : null

const decodeHtml = (value) => {
  const text = String(value || '')
  if (!text) return ''
  if (!htmlDecoder) return text
  htmlDecoder.innerHTML = text
  return htmlDecoder.value
}

const normalizeLineBreaks = (value) =>
  String(value || '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')

const normalizeProblemDetail = (item) => {
  if (!item) return null
  return {
    ...item,
    title: decodeHtml(item.title),
    summary: decodeHtml(item.summary),
    description: decodeHtml(item.description),
    input_description: decodeHtml(item.input_description),
    output_description: decodeHtml(item.output_description),
    examples: (item.examples || []).map((example) => ({
      ...example,
      input: decodeHtml(example?.input || ''),
      output: decodeHtml(example?.output || '')
    })),
    starter_code: Object.fromEntries(
      Object.entries(item.starter_code || {}).map(([languageKey, code]) => [languageKey, decodeHtml(code)])
    )
  }
}

const problemRef = computed(() => String(route.params.problem_ref || '').trim())
const topicKey = computed(() => String(route.query.topic || problem.value?.primary_topic_key || '').trim())
const sessionId = computed(() => String(session.value?.session_id || '').trim())

const noteStorageKey = computed(() => `practice-note:${problemRef.value}`)

const languageOptions = computed(() => {
  const allowed = session.value?.problem?.allowed_languages || problem.value?.allowed_languages || ['javascript']
  return allowed.map((value) => ({ label: languageLabelMap[value] || value, value }))
})

const currentStarterCode = computed(
  () => session.value?.problem?.starter_code?.[language.value] || problem.value?.starter_code?.[language.value] || ''
)

const resolvedStarterCode = computed(() => currentStarterCode.value || fallbackTemplateByLanguage[language.value] || '')

const editorPlaceholder = computed(() => `请在此编写 ${languageLabelMap[language.value] || language.value} 解法`)

const lineCount = computed(() => draftCode.value.split('\n').length)
const editorHeight = computed(() => Math.max(lineCount.value * 24 + 28, 240))

const sampleRunResult = computed(() => session.value?.sample_run || {})
const submissionResult = computed(() => session.value?.judge_result || {})
const problemExamples = computed(() => problem.value?.examples || [])
const currentJudgeStatus = computed(
  () => String(session.value?.judge_status || submissionResult.value?.status || '').trim() || ''
)

const statusMap = {
  ready: '就绪',
  coding: '编码中',
  submitted: '已提交',
  PENDING: '等待判题',
  JUDGING: '判题中',
  ACCEPTED: '通过',
  WRONG_ANSWER: '答案错误',
  COMPILE_ERROR: '编译错误',
  RUNTIME_ERROR: '运行错误',
  SYSTEM_ERROR: '系统错误',
  MEMORY_LIMIT_EXCEEDED: '内存超限',
  CPU_TIME_LIMIT_EXCEEDED: 'CPU 超时',
  REAL_TIME_LIMIT_EXCEEDED: '运行超时',
  PARTIALLY_ACCEPTED: '部分通过',
  idle: '未运行'
}

const getStatusLabel = (status, fallback = '未知状态') => statusMap[status] || status || fallback

const difficultyLabel = computed(
  () => difficultyLabelMap[problem.value?.difficulty_tag || ''] || problem.value?.difficulty_tag || ''
)

const metaText = computed(() => {
  const parts = []
  if (problem.value?.primary_topic_tag) parts.push(problem.value.primary_topic_tag)
  const tags = problem.value?.topic_tags || []
  if (tags.length) parts.push(tags.join(' · '))
  if (timeLimitText.value && timeLimitText.value !== '-') parts.push(`时间 ${timeLimitText.value}`)
  if (memoryLimitText.value && memoryLimitText.value !== '-') parts.push(`内存 ${memoryLimitText.value}`)
  return parts.join(' · ')
})

const combinedProblemText = computed(() =>
  [problem.value?.description, problem.value?.input_description, problem.value?.output_description]
    .map((item) => normalizeLineBreaks(item))
    .join('\n')
)

const normalizeLimitValue = (value) =>
  String(value || '')
    .replace(/\s+/g, ' ')
    .trim()

const extractByPatterns = (text, patterns) => {
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match && match[1]) {
      const normalized = normalizeLimitValue(match[1])
      if (normalized && normalized.length <= 64) {
        return normalized
      }
    }
  }
  return ''
}

const timeLimitText = computed(() => {
  const text = combinedProblemText.value
  return (
    extractByPatterns(text, [
      /(?:time\s*limit|时间限制)\s*[:：]?\s*(?:per\s*test\s*)?(\d+(?:\.\d+)?\s*(?:ms|s|sec(?:ond)?s?|milliseconds?|seconds?|毫秒|秒))/i,
      /(?:time\s*limit|时间限制)\s*[:：]?\s*([^\n]*?)(?=\b(?:memory\s*limit|input|output|note|example|examples)\b|$)/i
    ]) || '-'
  )
})

const memoryLimitText = computed(() => {
  const text = combinedProblemText.value
  return (
    extractByPatterns(text, [
      /(?:memory\s*limit|内存限制)\s*[:：]?\s*(?:per\s*test\s*)?(\d+(?:\.\d+)?\s*(?:kb|mb|gb|kib|mib|gib|bytes?|byte|kilobytes?|megabytes?|gigabytes?|千字节|兆|吉字节))/i,
      /(?:memory\s*limit|内存限制)\s*[:：]?\s*([^\n]*?)(?=\b(?:input|output|note|example|examples)\b|$)/i
    ]) || '-'
  )
})

const navigationIndex = computed(() =>
  navigationProblems.value.findIndex((item) => String(item.problem_ref || '') === problemRef.value)
)

const hasPrevProblem = computed(() => navigationIndex.value > 0)
const hasNextProblem = computed(() => navigationIndex.value >= 0 && navigationIndex.value < navigationProblems.value.length - 1)

const formatMetric = (value, suffix = '') => {
  if (value === undefined || value === null || value === '') {
    return '-'
  }
  return `${value}${suffix}`
}

const sampleTimeCost = computed(() => {
  const values = (sampleRunResult.value.tests || []).map((item) => Number(item.cpu_time || 0)).filter((item) => item > 0)
  if (!values.length) return '-'
  return `${Math.max(...values)} ms`
})

const sampleMemoryCost = computed(() => {
  const values = (sampleRunResult.value.tests || []).map((item) => Number(item.memory || 0)).filter((item) => item > 0)
  if (!values.length) return '-'
  return `${Math.max(...values)} KB`
})

const performanceMetrics = computed(() => [
  {
    label: '样例状态',
    value: getStatusLabel(sampleRunResult.value.status, '未运行')
  },
  {
    label: '样例耗时',
    value: sampleTimeCost.value
  },
  {
    label: '样例内存',
    value: sampleMemoryCost.value
  },
  {
    label: '提交状态',
    value: getStatusLabel(submissionResult.value.status || session.value?.judge_status, '未提交')
  },
  {
    label: '提交得分',
    value: formatMetric(submissionResult.value.score)
  },
  {
    label: '提交耗时',
    value: formatMetric(submissionResult.value.time_cost, ' ms')
  },
  {
    label: '提交内存',
    value: formatMetric(submissionResult.value.memory_cost, ' KB')
  }
])

const formatClock = (date) => {
  const pad = (value) => String(value).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const formatMemory = (value) => {
  const kb = Number(value)
  if (!Number.isFinite(kb)) return ''
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${Math.round(kb)} KB`
}

const testDataText = (test) => {
  const normalize = (value) => (value != null ? String(value).replace(/\s+/g, ' ').trim() : '')
  const expected = normalize(test.expected_output)
  const actual = normalize(test.actual_output)
  if (!expected && !actual) return ''
  if (test.passed) return expected
  return expected && actual ? `期望 ${expected} · 实际 ${actual}` : expected || actual
}

const sampleBadgeText = computed(() => {
  const tests = sampleRunResult.value?.tests || []
  if (!tests.length) {
    return getStatusLabel(sampleRunResult.value?.status, '') || '未运行'
  }
  const passed = tests.filter((test) => test.passed).length
  return passed === tests.length ? '全部通过' : `通过 ${passed} / ${tests.length}`
})

const sampleStatsText = computed(() => {
  const tests = sampleRunResult.value?.tests || []
  if (!tests.length) return ''
  const passed = tests.filter((test) => test.passed).length
  const time = tests.reduce((sum, test) => sum + (Number(test.cpu_time) || 0), 0)
  const memory = tests.reduce((sum, test) => sum + (Number(test.memory) || 0), 0)
  return `${passed} / ${tests.length} 用例 · 用时 ${time} ms · 内存 ${formatMemory(memory)}`
})

const judgeTests = computed(() => submissionResult.value?.tests || [])
const submissionPassed = computed(() => currentJudgeStatus.value === 'ACCEPTED')
const submissionStatsText = computed(() => {
  const parts = []
  const tests = judgeTests.value
  if (tests.length) {
    const passed = tests.filter((test) => test.passed).length
    parts.push(`${passed} / ${tests.length} 用例`)
  }
  if (submissionResult.value?.score !== undefined) parts.push(`得分 ${submissionResult.value.score}`)
  if (submissionResult.value?.time_cost) parts.push(`用时 ${submissionResult.value.time_cost} ms`)
  if (submissionResult.value?.memory_cost) parts.push(`内存 ${formatMemory(submissionResult.value.memory_cost)}`)
  return parts.join(' · ')
})

const examinationPoints = computed(() => {
  const tags = (problem.value?.topic_tags || []).map((item) => String(item).trim()).filter(Boolean)
  const tests = judgeTests.value
  const accepted = currentJudgeStatus.value === 'ACCEPTED'
  if (tags.length) {
    return tags.map((name, index) => {
      const test = tests[index]
      const done = test ? test.passed === true : accepted
      return { name, status: done ? '已实现' : '待验证', done }
    })
  }
  if (tests.length) {
    return tests.map((test) => ({
      name: String(test.name || '用例'),
      status: test.passed ? '已实现' : '待验证',
      done: !!test.passed
    }))
  }
  return []
})

const mockCountdownText = computed(() => {
  const minutes = Math.floor(mockRemainingSeconds.value / 60)
  const seconds = mockRemainingSeconds.value % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

const clearPollTimer = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const clearMockTimer = () => {
  if (mockTimer) {
    clearInterval(mockTimer)
    mockTimer = null
  }
}

const loadNote = () => {
  try {
    noteText.value = localStorage.getItem(noteStorageKey.value) || ''
    noteSavedText.value = ''
  } catch {
    noteText.value = ''
  }
}

const saveNote = () => {
  try {
    localStorage.setItem(noteStorageKey.value, noteText.value)
    noteSavedText.value = '已自动保存'
  } catch {
    noteSavedText.value = '保存失败'
  }
}

const syncDraftFromSession = () => {
  suppressDraftSave.value = true
  language.value = session.value?.language || languageOptions.value[0]?.value || 'javascript'
  draftCode.value =
    session.value?.drafts?.[language.value] ||
    session.value?.draft_code ||
    session.value?.problem?.starter_code?.[language.value] ||
    resolvedStarterCode.value
  suppressDraftSave.value = false
}

const loadProblem = async () => {
  const data = await practiceApi.getProblemDetail(problemRef.value)
  problem.value = normalizeProblemDetail(data)
}

const ensureSession = async () => {
  if (!problem.value?.supports_online_judge) {
    session.value = null
    return
  }
  const data = await practiceApi.startSession(problemRef.value)
  session.value = data?.practice_session || null
  syncDraftFromSession()
}

// 练习进度写入（localStorage）。仅记录"打开过"与判题终态，失败不回抛。
const localProgress = ref(loadProgress())

const syncProblemOpened = () => {
  if (!problemRef.value) return
  localProgress.value = markOpened(localProgress.value, problemRef.value)
  saveProgress(localProgress.value)
}

const syncJudgeResult = () => {
  if (!problemRef.value || !session.value) return
  const status = String(
    session.value?.judge_status || session.value?.judge_result?.status || ''
  )
    .trim()
    .toUpperCase()
  if (!status || pendingJudgeStatuses.has(status)) return
  localProgress.value = recordResult(localProgress.value, problemRef.value, status)
  saveProgress(localProgress.value)
}

const loadNavigationContext = async () => {
  try {
    const data = await practiceApi.getDefaultPlan()
    const allProblems = (data?.topics || []).flatMap((topic) => topic.problems || [])
    const currentTopic = topicKey.value
    if (currentTopic) {
      const topic = (data?.topics || []).find((item) => String(item.topic_key || '') === currentTopic)
      if (topic?.problems?.length) {
        navigationProblems.value = topic.problems
        return
      }
    }
    navigationProblems.value = allProblems
  } catch {
    navigationProblems.value = []
  }
}

const persistDraft = async () => {
  if (!sessionId.value || !session.value) return
  saveStateText.value = '保存中…'
  const data = await practiceApi.saveDraft(sessionId.value, {
    language: language.value,
    draft_code: draftCode.value
  })
  session.value = data?.practice_session || session.value
  saveStateText.value = '已自动保存'
  lastSavedAt.value = formatClock(new Date())
}

const scheduleDraftSave = () => {
  if (!session.value || suppressDraftSave.value) return
  saveStateText.value = '编辑中…'
  session.value = {
    ...session.value,
    drafts: {
      ...(session.value.drafts || {}),
      [language.value]: draftCode.value
    }
  }

  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await persistDraft()
    } catch {
      saveStateText.value = '保存失败'
    }
  }, 800)
}

const startSubmissionPolling = () => {
  clearPollTimer()
  if (!session.value?.submission_id || !sessionId.value) return
  pollTimer = setInterval(async () => {
    try {
      const data = await practiceApi.getSubmissionResult(sessionId.value, session.value.submission_id)
      session.value = {
        ...session.value,
        judge_status: data.judge_status,
        judge_result: data.judge_result,
        submitted_at: data.submitted_at
      }
      if (data.judge_status && !pendingJudgeStatuses.has(data.judge_status)) {
        clearPollTimer()
      }
      syncJudgeResult()
    } catch {
      clearPollTimer()
    }
  }, 1500)
}

const handleRunSample = async () => {
  if (!sessionId.value || !session.value) return
  runningSample.value = true
  try {
    await persistDraft()
    const data = await practiceApi.runSample(sessionId.value, {
      language: language.value,
      code: draftCode.value
    })
    session.value = data?.practice_session || session.value
    bottomTab.value = 'run'
    message.success('样例运行完成')
  } catch (error) {
    message.error(error.message || '运行样例失败')
  } finally {
    runningSample.value = false
  }
}

const handleSubmit = async () => {
  if (!sessionId.value || !session.value) return
  submitting.value = true
  try {
    await persistDraft()
    const data = await practiceApi.submit(sessionId.value, {
      language: language.value,
      code: draftCode.value
    })
    session.value = data?.practice_session || session.value
    syncJudgeResult()
    bottomTab.value = 'submission'
    startSubmissionPolling()
    message.success('代码已提交')
  } catch (error) {
    message.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

const startMockMode = () => {
  mockRunning.value = true
  mockReport.value = null
  mockRemainingSeconds.value = 15 * 60
  mockStartedAt = Date.now()
  clearMockTimer()

  mockTimer = setInterval(() => {
    if (mockRemainingSeconds.value <= 0) {
      finishMockMode()
      return
    }
    mockRemainingSeconds.value -= 1
  }, 1000)
}

const finishMockMode = () => {
  if (!mockRunning.value) return
  mockRunning.value = false
  clearMockTimer()

  const elapsedSeconds = Math.max(Math.floor((Date.now() - mockStartedAt) / 1000), 0)
  const minutes = Math.floor(elapsedSeconds / 60)
  const seconds = elapsedSeconds % 60
  mockReport.value = {
    durationText: `${minutes}分${seconds}秒`,
    submissionStatus: getStatusLabel(submissionResult.value.status || session.value?.judge_status, '未提交'),
    sampleStatus: getStatusLabel(sampleRunResult.value.status, '未运行')
  }
}

const toggleMockMode = () => {
  mockModeEnabled.value = !mockModeEnabled.value
}

const navigateProblem = (offset) => {
  const currentIndex = navigationIndex.value
  if (currentIndex < 0) return
  const next = navigationProblems.value[currentIndex + offset]
  if (!next?.problem_ref) return

  router.push({
    name: 'PracticeProblemPage',
    params: { problem_ref: next.problem_ref },
    query: topicKey.value ? { topic: topicKey.value } : {}
  })
}

const goBack = () => {
  if (topicKey.value) {
    router.push({ name: 'PracticeTopicPage', params: { topic_key: topicKey.value } })
    return
  }
  router.push({ name: 'PracticeHomePage' })
}

const stopAllTimers = () => {
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  if (noteTimer) {
    clearTimeout(noteTimer)
    noteTimer = null
  }
  clearPollTimer()
  clearMockTimer()
}

const initializePage = async () => {
  stopAllTimers()
  loading.value = true
  bottomTab.value = 'run'
  mockRunning.value = false
  mockReport.value = null
  mockRemainingSeconds.value = 15 * 60

  try {
    await loadProblem()
    syncProblemOpened()
    await loadNavigationContext()

    if (!problem.value?.supports_online_judge) {
      message.warning('当前题目暂未绑定在线判题，暂时无法开始练习')
      goBack()
      return
    }

    await ensureSession()
    syncJudgeResult()
    loadNote()

    if (session.value?.status === 'submitted' && session.value?.submission_id) {
      startSubmissionPolling()
    }
  } catch (error) {
    message.error(error.message || '加载练习题目失败')
  } finally {
    loading.value = false
  }
}

watch(
  problemRef,
  () => {
    initializePage()
  },
  { immediate: true }
)

watch(draftCode, () => {
  scheduleDraftSave()
})

watch(language, (value, previousValue) => {
  if (!session.value || value === previousValue) return

  suppressDraftSave.value = true
  if (previousValue) {
    session.value = {
      ...session.value,
      drafts: {
        ...(session.value.drafts || {}),
        [previousValue]: draftCode.value
      }
    }
  }

  draftCode.value = session.value?.drafts?.[value] || session.value?.problem?.starter_code?.[value] || fallbackTemplateByLanguage[value] || ''
  suppressDraftSave.value = false
})

watch(noteText, () => {
  noteSavedText.value = '保存中…'
  if (noteTimer) clearTimeout(noteTimer)
  noteTimer = setTimeout(() => {
    saveNote()
  }, 500)
})

watch(mockModeEnabled, (value) => {
  if (!value) {
    if (mockRunning.value) {
      finishMockMode()
    }
    mockReport.value = null
  }
})

onBeforeUnmount(() => {
  stopAllTimers()
})
</script>

<style scoped lang="less">
.practice-problem {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--gray-0);
}

/* ---------- 顶栏 ---------- */
.top {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 32px;
  border-bottom: 1px solid var(--gray-100);
}

.top-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.top-title {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.top-title-text {
  max-width: 100%;
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-1000);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-title-meta {
  font-size: 12px;
  color: var(--gray-500);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ---------- 通用控件 ---------- */
.b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-700);
  cursor: pointer;
  box-sizing: border-box;
  white-space: nowrap;
  gap: 6px;
}

.b:hover:not(:disabled) {
  color: var(--gray-1000);
  border-color: var(--gray-300);
}

.b:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.b.p {
  background: var(--main-600);
  border-color: var(--main-600);
  color: #fff;
}

.b.p:hover:not(:disabled) {
  background: var(--main-700);
  border-color: var(--main-700);
}

.badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid var(--gray-200);
  color: var(--gray-600);
  box-sizing: border-box;
  white-space: nowrap;
}

.badge.strong {
  background: var(--gray-100);
  color: var(--gray-1000);
  border-color: transparent;
}

.badge.strong.fail {
  background: var(--color-error-50);
  color: var(--color-error-700);
}

.lab {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}

.opt {
  display: flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-700);
  cursor: pointer;
  box-sizing: border-box;
}

.opt + .opt {
  border-left: none;
}

.opt.on {
  background: var(--gray-100);
  font-weight: 700;
  color: var(--gray-1000);
}

.empty-text {
  font-size: 13px;
  color: var(--gray-500);
}

/* ---------- 状态面板 ---------- */
.state-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-0);
  border: 1px solid var(--gray-200);
  margin: 20px;
}

/* ---------- 三栏布局 ---------- */
.problem-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 440px minmax(0, 1fr) 300px;
}

/* ---------- 左栏：题面 ---------- */
.problem-panel {
  min-height: 0;
  overflow: auto;
  border-right: 1px solid var(--gray-100);
  padding: 22px 24px;
}

.problem-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.problem-title {
  font-size: 19px;
  font-weight: 800;
  color: var(--gray-1000);
}

.problem-meta {
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 6px;
}

.problem-summary {
  font-size: 14px;
  line-height: 1.75;
  color: var(--gray-700);
  margin: 18px 0 0;
  white-space: pre-wrap;
}

.problem-lab {
  margin-top: 22px;
}

.problem-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-700);
  margin: 8px 0 0;
  white-space: pre-wrap;
}

.examples-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.example-box {
  border: 1px solid var(--gray-200);
  margin-top: 10px;
}

.example-item {
  padding: 10px 14px;
}

.example-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
  margin-bottom: 8px;
}

.example-col + .example-col {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--gray-100);
}

.console-title {
  font-size: 11px;
  color: var(--gray-500);
  letter-spacing: 0.1em;
  font-weight: 700;
}

.console-block {
  margin: 6px 0 0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-700);
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---------- 中栏：编辑器 + 判题 ---------- */
.editor-panel {
  min-width: 0;
  min-height: 0;
  border-right: 1px solid var(--gray-100);
  display: flex;
  flex-direction: column;
}

.editor-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--gray-100);
}

.language-switch {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.save-state {
  font-size: 12px;
  color: var(--gray-500);
  white-space: nowrap;
}

.editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: auto;
  background: var(--gray-10);
}

.line-numbers {
  flex: 0 0 44px;
  padding: 14px 0;
  text-align: right;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 24px;
  color: var(--gray-400);
  border-right: 1px solid var(--gray-100);
  user-select: none;
  box-sizing: border-box;
}

.code-area {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--gray-1000);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 24px;
  padding: 14px 18px;
  white-space: pre;
  overflow: hidden;
  box-sizing: border-box;
  display: block;
}

.judge-panel {
  flex: 0 0 250px;
  border-top: 1px solid var(--gray-100);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.judge-tabs {
  flex: 0 0 auto;
  display: flex;
  border-bottom: 1px solid var(--gray-100);
  padding: 0 20px;
  overflow-x: auto;
}

.judge-tab {
  padding: 12px 0;
  margin-right: 22px;
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-600);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  white-space: nowrap;
}

.judge-tab.on {
  color: var(--gray-1000);
  border-bottom-color: var(--main-600);
}

.judge-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px 20px;
}

.result-overview {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.result-stats {
  font-size: 13px;
  color: var(--gray-600);
}

.judge-message {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--gray-700);
}

.console-section {
  margin-top: 12px;
}

.judge-table {
  width: 100%;
  border-collapse: collapse;
}

.judge-table th {
  text-align: left;
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--gray-500);
  font-weight: 700;
  padding: 6px 14px;
  border-bottom: 1px solid var(--gray-200);
}

.judge-table th:first-child,
.judge-table td:first-child {
  padding-left: 0;
}

.judge-table th:last-child,
.judge-table td:last-child {
  padding-right: 0;
}

.judge-table td {
  font-size: 13px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--gray-100);
  color: var(--gray-700);
}

.judge-table td.pass {
  color: var(--color-success-500);
}

.judge-table td.fail {
  color: var(--color-error-500);
}

.judge-table td.time {
  text-align: right;
  color: var(--gray-500);
  white-space: nowrap;
}

.judge-table td.mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}

.judge-table td.ellipsis {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---------- 右栏：学习面板 ---------- */
.aside-panel {
  min-height: 0;
  overflow: auto;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.points-list {
  margin-top: 12px;
  font-size: 13px;
  line-height: 1.7;
}

.point-row {
  border-top: 1px solid var(--gray-100);
  padding: 10px 0;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.point-name {
  color: var(--gray-800);
}

.point-status.done {
  color: var(--main-800);
  font-weight: 700;
}

.point-status.pending {
  color: var(--gray-500);
}

.note-input {
  width: 100%;
  margin-top: 12px;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.6;
  font-family: inherit;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
  color: var(--gray-1000);
  outline: none;
  resize: vertical;
  box-sizing: border-box;
}

.note-input:focus {
  border-color: var(--main-600);
}

.note-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--gray-500);
}

.mock-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mock-timer {
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-1000);
  margin: 12px 0 10px;
}

.mock-actions {
  display: flex;
  gap: 8px;
}

.mock-report {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--gray-700);
  font-size: 13px;
}

/* ---------- 性能分析 ---------- */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-item {
  border: 1px solid var(--gray-200);
  padding: 10px 12px;
  background: var(--gray-10);
}

.metric-label {
  font-size: 12px;
  color: var(--gray-500);
}

.metric-value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-1000);
}

/* ---------- 窄屏适配 ---------- */
@media (max-width: 1360px) {
  .problem-layout {
    grid-template-columns: 360px minmax(0, 1fr) 260px;
  }

  .top {
    padding: 14px 24px;
  }

  .problem-panel,
  .aside-panel {
    padding: 20px;
  }
}

@media (max-width: 1100px) {
  .top-title {
    display: none;
  }

  .problem-layout {
    grid-template-columns: 320px minmax(0, 1fr);
  }

  .aside-panel {
    display: none;
  }
}
</style>
