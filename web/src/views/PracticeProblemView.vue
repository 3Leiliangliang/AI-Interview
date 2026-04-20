<template>
  <div class="practice-problem">
    <div class="page-toolbar">
      <div class="toolbar-left">
        <a-button @click="goBack">返回题单</a-button>
        <a-button :disabled="!hasPrevProblem" @click="navigateProblem(-1)">
          <LeftOutlined />
          上一题
        </a-button>
        <a-button :disabled="!hasNextProblem" @click="navigateProblem(1)">
          下一题
          <RightOutlined />
        </a-button>
      </div>

      <div class="toolbar-main">
        <div class="toolbar-title">{{ problem?.title || session?.problem_title || '代码练习' }}</div>
        <div class="toolbar-meta">
          <span>#{{ problem?.problem_index || '-' }}</span>
          <span>{{ problem?.primary_topic_tag || '专题练习' }}</span>
          <a-tag :color="difficultyColorMap[problem?.difficulty_tag] || 'default'">
            {{ difficultyLabelMap[problem?.difficulty_tag] || '中等' }}
          </a-tag>
        </div>
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
    </div>

    <div v-else-if="!problem || !session" class="state-panel">
      <a-empty description="题目加载失败" />
    </div>

    <div v-else class="content-layout">
      <section class="question-panel">
        <div class="panel-card question-card">
          <div class="question-hero">
            <div class="question-caption">题号 #{{ problem.problem_index }}</div>
            <h1>{{ problem.title }}</h1>
            <p v-if="problem.summary">{{ problem.summary }}</p>
            <div class="question-tags">
              <a-tag :color="difficultyColorMap[problem.difficulty_tag] || 'default'">
                {{ difficultyLabelMap[problem.difficulty_tag] || '中等' }}
              </a-tag>
              <a-tag v-for="tag in problem.topic_tags || []" :key="tag">{{ tag }}</a-tag>
            </div>

            <div class="limit-row">
              <span class="limit-chip"><FieldTimeOutlined /> 时间限制：{{ timeLimitText }}</span>
              <span class="limit-chip"><DatabaseOutlined /> 内存限制：{{ memoryLimitText }}</span>
              <span class="limit-chip"><CheckCircleOutlined /> 样例数：{{ problem.examples?.length || 0 }}</span>
            </div>
          </div>

          <div class="question-section">
            <h3>题目描述</h3>
            <div class="paragraph-list">
              <p v-for="(item, index) in descriptionParagraphs" :key="`desc-${index}`">{{ item }}</p>
            </div>
          </div>

          <div v-if="constraintLines.length" class="question-section">
            <h3>约束条件</h3>
            <div class="constraint-card">
              <ul>
                <li v-for="(line, index) in constraintLines" :key="`constraint-${index}`">{{ line }}</li>
              </ul>
            </div>
          </div>

          <div v-if="inputParagraphs.length" class="question-section">
            <h3>输入说明</h3>
            <div class="paragraph-list">
              <p v-for="(item, index) in inputParagraphs" :key="`input-${index}`">{{ item }}</p>
            </div>
          </div>

          <div v-if="outputParagraphs.length" class="question-section">
            <h3>输出说明</h3>
            <div class="paragraph-list">
              <p v-for="(item, index) in outputParagraphs" :key="`output-${index}`">{{ item }}</p>
            </div>
          </div>

          <div class="question-section">
            <h3>示例</h3>
            <div v-if="problem.examples?.length" class="example-grid">
              <div v-for="(example, index) in problem.examples" :key="index" class="example-card">
                <div class="example-head">
                  <div class="example-title">样例 {{ index + 1 }}</div>
                  <a-button size="small" :loading="runningSample" @click="runExample(index)">运行此样例</a-button>
                </div>
                <div class="example-block">
                  <span>输入</span>
                  <pre>{{ example.input || '（空）' }}</pre>
                </div>
                <div class="example-block">
                  <span>输出</span>
                  <pre>{{ example.output || '（空）' }}</pre>
                </div>
                <div class="example-tip">{{ buildExampleTip(example) }}</div>
              </div>
            </div>
            <div v-else class="empty-text">当前题目未提供测试样例</div>
          </div>
        </div>

        <div class="panel-card learning-card">
          <div class="learning-header">
            <div class="panel-title">面试学习面板</div>
            <a-switch v-model:checked="mockModeEnabled" />
          </div>

          <div class="learning-section">
            <div class="section-title">知识点标签</div>
            <div class="tag-row">
              <a-tag v-for="tag in problem.topic_tags || []" :key="`learning-${tag}`">{{ tag }}</a-tag>
              <span v-if="!(problem.topic_tags || []).length" class="empty-text">暂无标签</span>
            </div>
          </div>

          <div class="learning-section">
            <div class="section-title">我的笔记</div>
            <a-textarea
              v-model:value="noteText"
              :rows="4"
              placeholder="记录你的解题思路、易错点和复杂度分析"
            />
            <div class="note-meta">{{ noteSavedText }}</div>
          </div>

          <div v-if="mockModeEnabled" class="learning-section mock-section">
            <div class="section-title">模拟面试</div>
            <div class="mock-timer">剩余时间：{{ mockCountdownText }}</div>
            <div class="mock-actions">
              <a-button :disabled="mockRunning" @click="startMockMode">开始</a-button>
              <a-button :disabled="!mockRunning" @click="finishMockMode">结束</a-button>
            </div>
            <div v-if="mockReport" class="mock-report">
              <div>编码耗时：{{ mockReport.durationText }}</div>
              <div>提交状态：{{ mockReport.submissionStatus }}</div>
              <div>样例状态：{{ mockReport.sampleStatus }}</div>
            </div>
          </div>
        </div>
      </section>

      <section class="editor-panel">
        <div class="panel-card editor-card">
          <div class="editor-header">
            <div>
              <div class="panel-title">代码编辑器</div>
              <div class="panel-subtitle">{{ saveStateText }}</div>
            </div>
          </div>

          <div class="language-quick-tabs">
            <button
              v-for="item in languageOptions"
              :key="item.value"
              type="button"
              class="lang-chip"
              :class="{ active: language === item.value }"
              @click="language = item.value"
            >
              {{ item.label }}
            </button>
          </div>

          <textarea
            v-model="draftCode"
            class="code-editor"
            spellcheck="false"
            :placeholder="editorPlaceholder"
          ></textarea>

          <div class="editor-tools">
            <a-button size="small" @click="resetCode">
              <ReloadOutlined />
              重置代码
            </a-button>
            <a-button size="small" @click="handleSaveDraft">
              <SaveOutlined />
              保存草稿
            </a-button>
            <a-button size="small" @click="copyCurrentCode">
              <CopyOutlined />
              复制代码
            </a-button>
          </div>

          <div class="editor-actions">
            <a-button :loading="runningSample" @click="handleRunSample">
              <PlayCircleOutlined />
              运行样例
            </a-button>
            <a-button type="primary" :loading="submitting" @click="handleSubmit">
              <RocketOutlined />
              提交判题
            </a-button>
          </div>
        </div>

        <div class="panel-card result-card">
          <a-tabs v-model:activeKey="bottomTab">
            <a-tab-pane key="run" tab="运行结果">
              <div class="result-overview">
                <a-tag :color="statusColor(sampleRunResult.status)">{{ statusLabel(sampleRunResult.status, '未运行') }}</a-tag>
                <span class="panel-subtitle" v-if="activeExampleIndex >= 0">来自样例 {{ activeExampleIndex + 1 }}</span>
              </div>
              <div v-if="sampleRunResult.message" class="judge-message">{{ sampleRunResult.message }}</div>
              <div v-if="sampleRunResult.compile_error" class="console-section">
                <div class="console-title">编译错误</div>
                <pre class="console-block error">{{ sampleRunResult.compile_error }}</pre>
              </div>
              <div v-if="sampleRunResult.stdout" class="console-section">
                <div class="console-title">stdout</div>
                <pre class="console-block">{{ sampleRunResult.stdout }}</pre>
              </div>
              <div v-if="sampleRunResult.stderr" class="console-section">
                <div class="console-title">stderr</div>
                <pre class="console-block error">{{ sampleRunResult.stderr }}</pre>
              </div>
              <ul v-if="sampleRunResult.tests?.length" class="judge-tests">
                <li v-for="test in sampleRunResult.tests" :key="test.name">
                  <span :class="['dot', test.passed ? 'passed' : 'failed']"></span>
                  <span class="test-name">{{ test.name }}</span>
                  <span class="test-message">{{ test.message }}</span>
                </li>
              </ul>
            </a-tab-pane>

            <a-tab-pane key="submission" tab="提交结果">
              <div class="result-overview">
                <a-tag :color="statusColor(submissionResult.status || session.judge_status)">
                  {{ statusLabel(submissionResult.status || session.judge_status, '未提交') }}
                </a-tag>
                <span v-if="session.submission_id" class="panel-subtitle">提交 ID：{{ session.submission_id }}</span>
                <span v-if="submissionResult.score !== undefined" class="panel-subtitle">得分：{{ submissionResult.score }}</span>
              </div>
              <div v-if="submissionResult.message" class="judge-message">{{ submissionResult.message }}</div>
              <div v-if="submissionResult.compile_error" class="console-section">
                <div class="console-title">编译错误</div>
                <pre class="console-block error">{{ submissionResult.compile_error }}</pre>
              </div>
              <ul v-if="submissionResult.tests?.length" class="judge-tests">
                <li v-for="test in submissionResult.tests" :key="test.name">
                  <span :class="['dot', test.passed ? 'passed' : 'failed']"></span>
                  <span class="test-name">{{ test.name }}</span>
                  <span class="test-message">{{ test.message }}</span>
                </li>
              </ul>
              <div v-else class="empty-text">提交后可在这里查看判题结果</div>
            </a-tab-pane>

            <a-tab-pane key="metrics" tab="性能分析">
              <div class="metrics-grid">
                <div v-for="item in performanceMetrics" :key="item.label" class="metric-item">
                  <div class="metric-label">{{ item.label }}</div>
                  <div class="metric-value">{{ item.value }}</div>
                </div>
              </div>
            </a-tab-pane>

            <a-tab-pane key="cases" tab="测试用例">
              <div v-if="problem.examples?.length" class="example-grid example-grid--compact">
                <div v-for="(example, index) in problem.examples" :key="index" class="example-card">
                  <div class="example-title">样例 {{ index + 1 }}</div>
                  <div class="example-block">
                    <span>输入</span>
                    <pre>{{ example.input || '（空）' }}</pre>
                  </div>
                  <div class="example-block">
                    <span>输出</span>
                    <pre>{{ example.output || '（空）' }}</pre>
                  </div>
                </div>
              </div>
              <div v-else class="empty-text">当前题目未提供测试用例</div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  CopyOutlined,
  DatabaseOutlined,
  FieldTimeOutlined,
  LeftOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RightOutlined,
  RocketOutlined,
  SaveOutlined
} from '@ant-design/icons-vue'

import { practiceApi } from '@/apis/practice_api'

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

const activeExampleIndex = ref(-1)

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

const difficultyColorMap = {
  easy: 'green',
  medium: 'gold',
  hard: 'red'
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

const splitParagraphs = (value) => {
  const text = normalizeLineBreaks(value)
  return text
    .split(/\n\s*\n/g)
    .map((item) => item.trim())
    .filter(Boolean)
}

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

const sampleRunResult = computed(() => session.value?.sample_run || {})
const submissionResult = computed(() => session.value?.judge_result || {})

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

const statusColor = (status) => {
  if (status === 'ACCEPTED') return 'green'
  if (status === 'PENDING' || status === 'JUDGING') return 'blue'
  if (
    ['WRONG_ANSWER', 'COMPILE_ERROR', 'RUNTIME_ERROR', 'SYSTEM_ERROR', 'MEMORY_LIMIT_EXCEEDED', 'CPU_TIME_LIMIT_EXCEEDED', 'REAL_TIME_LIMIT_EXCEEDED'].includes(
      status
    )
  ) {
    return 'red'
  }
  return 'default'
}

const statusLabel = (status, fallback = '未知状态') => statusMap[status] || status || fallback

const descriptionParagraphs = computed(() => {
  const base = splitParagraphs(problem.value?.description)
  if (base.length) {
    return base
  }
  return ['暂无题目描述']
})

const inputParagraphs = computed(() => splitParagraphs(problem.value?.input_description))
const outputParagraphs = computed(() => splitParagraphs(problem.value?.output_description))

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

const constraintLines = computed(() => {
  const lines = normalizeLineBreaks(combinedProblemText.value)
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)

  const patterns = [
    /\b\d+\s*(?:<=|<|≤)\s*[a-zA-Z_][\w\[\]]*\s*(?:<=|<|≤)\s*\d+/,
    /[a-zA-Z_][\w\[\]]*\s*(?:<=|<|≤)\s*\d+/,
    /\b(?:constraints?|约束|限制)\b/i,
    /10\^\d+/
  ]

  const picked = []
  for (const line of lines) {
    if (patterns.some((pattern) => pattern.test(line))) {
      picked.push(line)
    }
  }

  return [...new Set(picked)].slice(0, 8)
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
    value: statusLabel(sampleRunResult.value.status, '未运行')
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
    value: statusLabel(submissionResult.value.status || session.value?.judge_status, '未提交')
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
    noteSavedText.value = '笔记已保存'
  } catch {
    noteSavedText.value = '笔记保存失败'
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
  saveStateText.value = '保存中...'
  const data = await practiceApi.saveDraft(sessionId.value, {
    language: language.value,
    draft_code: draftCode.value
  })
  session.value = data?.practice_session || session.value
  saveStateText.value = '已保存'
}

const scheduleDraftSave = () => {
  if (!session.value || suppressDraftSave.value) return
  saveStateText.value = '编辑中...'
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

const runExample = async (index) => {
  activeExampleIndex.value = index
  await handleRunSample()
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
    bottomTab.value = 'submission'
    startSubmissionPolling()
    message.success('代码已提交')
  } catch (error) {
    message.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

const handleSaveDraft = async () => {
  try {
    await persistDraft()
    message.success('草稿已保存')
  } catch (error) {
    message.error(error.message || '保存失败')
  }
}

const resetCode = () => {
  suppressDraftSave.value = true
  draftCode.value = resolvedStarterCode.value
  suppressDraftSave.value = false
  scheduleDraftSave()
}

const copyCurrentCode = async () => {
  try {
    await navigator.clipboard.writeText(draftCode.value)
    message.success('代码已复制')
  } catch {
    message.error('复制失败')
  }
}

const buildExampleTip = (example) => {
  if (example.input && example.output) {
    return '建议先手动推演一轮输入，再对照输出验证思路。'
  }
  return '该样例信息较少，建议先补充边界场景自行验证。'
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
    submissionStatus: statusLabel(submissionResult.value.status || session.value?.judge_status, '未提交'),
    sampleStatus: statusLabel(sampleRunResult.value.status, '未运行')
  }
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
  activeExampleIndex.value = -1
  bottomTab.value = 'run'
  mockRunning.value = false
  mockReport.value = null
  mockRemainingSeconds.value = 15 * 60

  try {
    await loadProblem()
    await loadNavigationContext()

    if (!problem.value?.supports_online_judge) {
      message.warning('当前题目暂未绑定在线判题，暂时无法开始练习')
      goBack()
      return
    }

    await ensureSession()
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
  noteSavedText.value = '保存中...'
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
  min-height: 100%;
  padding: 20px;
  background: var(--gray-50);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-toolbar,
.panel-card,
.state-panel {
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 18px;
}

.page-toolbar {
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.toolbar-left,
.toolbar-meta,
.question-tags,
.limit-row,
.result-overview,
.editor-tools,
.editor-actions,
.mock-actions,
.tag-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
}

.toolbar-title,
.panel-title,
.question-hero h1 {
  color: var(--gray-1000);
}

.toolbar-title,
.panel-title {
  font-size: 16px;
  font-weight: 600;
}

.toolbar-meta,
.panel-subtitle,
.question-caption,
.empty-text,
.test-message,
.note-meta,
.metric-label,
.limit-chip {
  font-size: 13px;
  color: var(--gray-600);
}

.state-panel {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.content-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(320px, 40%) minmax(460px, 60%);
  gap: 16px;
}

.question-panel,
.editor-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.question-card,
.editor-card,
.result-card {
  flex: 1;
}

.panel-card {
  padding: 16px;
  overflow: auto;
}

.question-hero {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--gray-150);
}

.question-hero h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.35;
}

.question-hero p {
  margin: 0;
  color: var(--gray-700);
  line-height: 1.75;
}

.limit-chip {
  padding: 6px 10px;
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--gray-25);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.question-section + .question-section {
  margin-top: 18px;
}

.question-section h3,
.section-title {
  margin: 0 0 10px;
  font-size: 15px;
  color: var(--gray-1000);
}

.paragraph-list p {
  margin: 0;
  color: var(--gray-800);
  line-height: 1.8;
  white-space: pre-wrap;
}

.paragraph-list p + p {
  margin-top: 10px;
}

.constraint-card {
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--gray-25);
  padding: 10px 12px;
}

.constraint-card ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--gray-800);
}

.console-block,
.example-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, 'Courier New', monospace;
  line-height: 1.6;
}

.example-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.example-grid--compact {
  grid-template-columns: 1fr;
}

.example-card {
  padding: 12px;
  border-radius: 12px;
  background: var(--gray-25);
  border: 1px solid var(--gray-200);
}

.example-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.example-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-900);
}

.example-block + .example-block {
  margin-top: 8px;
}

.example-block span,
.console-title {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-700);
}

.example-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--gray-600);
}

.learning-card {
  flex: none;
}

.learning-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.learning-section + .learning-section {
  margin-top: 14px;
}

.note-meta {
  margin-top: 8px;
}

.mock-section {
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 10px;
  background: var(--gray-25);
}

.mock-timer {
  font-size: 18px;
  font-weight: 700;
  color: var(--gray-1000);
  margin-bottom: 8px;
}

.mock-report {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--gray-700);
  font-size: 13px;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}

.language-quick-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.lang-chip {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  padding: 6px 12px;
  background: var(--color-bg-container);
  color: var(--gray-700);
  cursor: pointer;
}

.lang-chip.active {
  border-color: var(--main-300);
  background: var(--main-20);
  color: var(--main-color);
}

.code-editor {
  width: 100%;
  min-height: 420px;
  border: 1px solid var(--gray-200);
  border-radius: 14px;
  padding: 14px;
  resize: vertical;
  outline: none;
  background: #111827;
  color: #f8fafc;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.editor-tools {
  margin-top: 10px;
}

.editor-actions {
  margin-top: 12px;
  justify-content: flex-end;
}

.judge-message {
  margin: 0 0 10px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  color: var(--gray-800);
}

.console-section + .console-section {
  margin-top: 10px;
}

.console-block {
  padding: 10px;
  border-radius: 10px;
  background: var(--gray-25);
  border: 1px solid var(--gray-200);
  color: var(--gray-800);
  font-size: 12px;
}

.console-block.error {
  background: #fff2f0;
  border-color: #ffccc7;
  color: #a8071a;
}

.judge-tests {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.judge-tests li {
  display: grid;
  grid-template-columns: 10px auto 1fr;
  gap: 8px;
  align-items: center;
}

.test-name {
  color: var(--gray-800);
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.passed {
  background: var(--color-success-500);
}

.dot.failed {
  background: var(--color-error-500);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-item {
  border: 1px solid var(--gray-200);
  border-radius: 10px;
  padding: 10px;
  background: var(--gray-25);
}

.metric-value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-1000);
}

@media (max-width: 1200px) {
  .content-layout {
    grid-template-columns: 1fr;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .practice-problem {
    padding: 12px;
  }

  .panel-card,
  .page-toolbar {
    padding: 14px;
  }

  .page-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-main {
    align-items: flex-start;
  }

  .question-hero h1 {
    font-size: 22px;
  }

  .code-editor {
    min-height: 320px;
  }

  .editor-actions {
    justify-content: flex-start;
  }
}
</style>
