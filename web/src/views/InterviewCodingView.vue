<template>
  <div class="coding-view">
    <div class="top">
      <div class="top-head">
        <h1 class="h1">编程考核</h1>
        <p class="sub">{{ effectivePosition }} · {{ effectiveRound }}</p>
      </div>
      <div class="top-actions">
        <button class="b" type="button" @click="goBackToInterview">返回面试</button>
        <button
          class="b"
          type="button"
          :disabled="runningSample"
          @click="handleRunSample"
        >
          {{ runningSample ? '运行中…' : '运行样例' }}
        </button>
        <button
          class="b p"
          type="button"
          :disabled="submitting"
          @click="handleSubmit"
        >
          {{ submitting ? '提交中…' : '提交判题' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin />
    </div>

    <div v-else-if="!session" class="state-panel">
      <a-empty description="当前线程还没有代码考核会话">
        <a-button type="primary" :loading="starting" @click="handleStartIfNeeded">开始代码考核</a-button>
      </a-empty>
    </div>

    <div v-else class="coding-layout">
      <!-- 左栏：题面 -->
      <section class="problem-panel">
        <div class="problem-head">
          <span class="problem-title">{{ session.problem_title }}</span>
          <span class="badge">{{ difficultyLabel }}</span>
        </div>
        <div class="problem-meta">{{ metaText }}</div>
        <p class="problem-desc">{{ session.problem?.description }}</p>

        <div class="lab problem-lab">输入说明</div>
        <p class="problem-text">{{ session.problem?.input_description }}</p>

        <div class="lab problem-lab">输出说明</div>
        <p class="problem-text">{{ session.problem?.output_description }}</p>

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

      <!-- 中栏：编辑器 + 判题结果 -->
      <section class="editor-panel">
        <div class="editor-bar">
          <div class="language-switch">
            <span
              v-for="opt in languageOptions"
              :key="opt.value"
              class="opt"
              :class="{ on: opt.value === language }"
              @click="switchLanguage(opt.value)"
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
          ></textarea>
        </div>

        <div class="judge-panel">
          <div class="judge-tabs">
            <div class="judge-tab" :class="{ on: bottomTab === 'run' }" @click="bottomTab = 'run'">运行结果</div>
            <div class="judge-tab" :class="{ on: bottomTab === 'cases' }" @click="bottomTab = 'cases'">测试用例</div>
            <div class="judge-tab" :class="{ on: bottomTab === 'submission' }" @click="bottomTab = 'submission'">提交结果</div>
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

            <template v-else>
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
              <div v-if="submissionResult.stdout || submissionResult.stderr" class="console-section">
                <div v-if="submissionResult.stdout" class="console-title">stdout</div>
                <pre v-if="submissionResult.stdout" class="console-block">{{ submissionResult.stdout }}</pre>
                <div v-if="submissionResult.stderr" class="console-title">stderr</div>
                <pre v-if="submissionResult.stderr" class="console-block error">{{ submissionResult.stderr }}</pre>
              </div>
              <div v-if="!currentJudgeStatus && !judgeTests.length" class="empty-text">
                暂未提交代码，提交后可在这里查看判题结果
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- 右栏：考察点 + 提示 -->
      <section class="aside-panel">
        <div>
          <div class="lab">本题在考什么</div>
          <div class="points-list">
            <div v-for="point in examinationPoints" :key="point.name" class="point-row">
              <span class="point-name">{{ point.name }}</span>
              <span :class="['point-status', point.done ? 'done' : 'pending']">{{ point.status }}</span>
            </div>
            <div v-if="!examinationPoints.length" class="empty-text">提交判题后可查看考察点实现情况</div>
          </div>
        </div>

        <div class="hint-block">
          <div class="hint-head">
            <span class="lab">提示</span>
            <span class="hint-count">已用 {{ hintCount }} 次</span>
          </div>
          <p class="hint-desc">只有你主动请求时，面试官才会给提示。请求次数会写进报告。</p>
          <textarea
            v-model="hintQuestion"
            class="hint-input"
            rows="3"
            placeholder="描述你想获得的提示…"
          ></textarea>
          <button class="b hint-btn" type="button" :disabled="hintLoading" @click="handleRequestHint">
            {{ hintLoading ? '请求中…' : '请求提示' }}
          </button>
          <div v-if="hintHistory.length" class="hint-history">
            <div v-for="item in hintHistory" :key="item.created_at" class="hint-item">
              <div class="hint-question">{{ item.question }}</div>
              <div class="hint-answer">{{ item.hint }}</div>
              <div class="hint-time">{{ formatTime(item.created_at) }}</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

import { threadApi } from '@/apis'
import { interviewCodeApi } from '@/apis/interview_code'
import { useAgentStore } from '@/stores/agent'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()

const threadId = computed(() => String(route.query.threadId || '').trim())
const activeThreadId = ref('')
const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || '初试')

const loading = ref(false)
const starting = ref(false)
const runningSample = ref(false)
const submitting = ref(false)
const hintLoading = ref(false)
const session = ref(null)
const draftCode = ref('')
const language = ref('javascript')
const hintQuestion = ref('')
const bottomTab = ref('cases')
const saveStateText = ref('未保存')
const lastSavedAt = ref('')
const latestSubmittedId = ref('')
const languageLabelMap = {
  javascript: 'JavaScript',
  c: 'C',
  cpp: 'C++',
  java: 'Java',
  python: 'Python'
}
const pendingJudgeStatuses = new Set(['PENDING', 'JUDGING'])
const getSkipCodingRedirectKey = (value) => `interview-skip-coding-redirect:${value}`

let saveTimer = null
let pollTimer = null

const languageOptions = computed(() => {
  const allowed = session.value?.problem?.allowed_languages || ['javascript']
  return allowed.map((value) => ({
    label: languageLabelMap[value] || value,
    value
  }))
})

const hintHistory = computed(() => session.value?.requested_hints || [])
const sampleRunResult = computed(() => session.value?.sample_run || {})
const submissionResult = computed(() => session.value?.judge_result || {})
const problemExamples = computed(() => session.value?.problem?.examples || [])
const currentJudgeStatus = computed(
  () => String(session.value?.judge_status || submissionResult.value?.status || '').trim() || ''
)
const effectivePosition = computed(() => String(session.value?.target_position || selectedPosition.value || DEFAULT_POSITION).trim())
const effectiveRound = computed(() => String(route.query.round || selectedRound.value || '初试').trim() || '初试')

const lineCount = computed(() => draftCode.value.split('\n').length)
const editorHeight = computed(() => Math.max(lineCount.value * 24 + 28, 240))

const difficultyLabelMap = { easy: '简单', medium: '中等', hard: '困难' }
const difficultyLabel = computed(
  () => difficultyLabelMap[session.value?.problem?.difficulty_tag || ''] || session.value?.problem?.difficulty_tag || ''
)
const metaText = computed(() => {
  const parts = []
  const source = session.value?.source || ''
  if (source) parts.push(`来源 ${source}`)
  const tags = session.value?.problem?.topic_tags || []
  if (tags.length) parts.push(tags.join(' · '))
  return parts.join(' · ')
})

const examinationPoints = computed(() => {
  const tags = (session.value?.problem?.topic_tags || []).map((item) => String(item).trim()).filter(Boolean)
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

const hintCount = computed(() => Number(session.value?.hint_count ?? session.value?.requested_hints?.length ?? 0))
const sampleBadgeText = computed(() => {
  const tests = sampleRunResult.value?.tests || []
  if (!tests.length) return ''
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

const statusLabelMap = {
  ready: '就绪',
  coding: '编码中',
  submitted: '已提交',
  reviewed: '已评审',
  idle: '未运行',
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
  PARTIALLY_ACCEPTED: '部分通过'
}

const getStatusLabel = (status, fallback = '就绪') => statusLabelMap[status] || status || fallback

const returnRoute = computed(() => {
  return {
    name: 'AgentInterviewComp',
    query: {
      threadId: activeThreadId.value || threadId.value,
      position: effectivePosition.value,
      round: effectiveRound.value
    }
  }
})

const formatClock = (date) => {
  const pad = (value) => String(value).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}
const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return formatClock(date)
}
const formatMemory = (value) => {
  const kb = Number(value)
  if (!Number.isFinite(kb)) return ''
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${Math.round(kb)} KB`
}
const testDataText = (test) => {
  const normalize = (value) =>
    value != null ? String(value).replace(/\s+/g, ' ').trim() : ''
  const expected = normalize(test.expected_output)
  const actual = normalize(test.actual_output)
  if (!expected && !actual) return ''
  if (test.passed) return expected
  return expected && actual ? `期望 ${expected} · 实际 ${actual}` : expected || actual
}

const switchLanguage = (value) => {
  if (value === language.value) return
  language.value = value
}

const syncDraftFromSession = () => {
  language.value = session.value?.language || languageOptions.value[0]?.value || 'javascript'
  draftCode.value =
    session.value?.drafts?.[language.value] ||
    session.value?.draft_code ||
    session.value?.problem?.starter_code?.[language.value] ||
    ''
}

const resolveInterviewAgentId = async () => {
  if (!agentStore.isInitialized) {
    await agentStore.initialize()
  }
  return (
    agentStore.agents.find((item) => item.id === 'InterviewAgent')?.id ||
    agentStore.defaultAgentId ||
    agentStore.defaultAgent?.id ||
    agentStore.agents[0]?.id ||
    ''
  )
}

const ensureThreadId = async () => {
  if (activeThreadId.value) return activeThreadId.value
  if (threadId.value) {
    activeThreadId.value = threadId.value
    return threadId.value
  }

  const agentId = await resolveInterviewAgentId()
  if (!agentId) {
    throw new Error('未找到可用的面试智能体，无法创建 OJ 会话')
  }

  const thread = await threadApi.createThread(agentId, 'OJ 工作台', {
    source: 'oj_workbench',
    target_position: selectedPosition.value,
    interview_round: selectedRound.value
  })

  const nextThreadId = String(thread?.id || '').trim()
  if (!nextThreadId) {
    throw new Error('创建 OJ 会话线程失败')
  }
  activeThreadId.value = nextThreadId

  await router.replace({
    name: 'OJWorkbenchComp',
    query: {
      ...route.query,
      threadId: nextThreadId,
      position: effectivePosition.value,
      round: effectiveRound.value
    }
  })
  return nextThreadId
}

const loadSession = async (currentThreadId = activeThreadId.value || threadId.value) => {
  if (!currentThreadId) return
  loading.value = true
  try {
    const data = await interviewCodeApi.getCodingSession(currentThreadId)
    session.value = data?.coding_session || null
    if (session.value) syncDraftFromSession()
  } catch (error) {
    session.value = null
    if (!String(error?.message || '').includes('Coding session not found')) {
      message.error(error.message || '加载代码考核失败')
    }
  } finally {
    loading.value = false
  }
}

const handleStartIfNeeded = async () => {
  starting.value = true
  try {
    const currentThreadId = await ensureThreadId()
    const data = await interviewCodeApi.startCodingSession(currentThreadId, {
      target_position: effectivePosition.value
    })
    session.value = data?.coding_session || null
    syncDraftFromSession()
    message.success('代码考核已就绪')
  } catch (error) {
    message.error(error.message || '启动代码考核失败')
  } finally {
    starting.value = false
  }
}

const persistDraft = async () => {
  const currentThreadId = activeThreadId.value || threadId.value
  if (!currentThreadId || !session.value) return
  saveStateText.value = '保存中…'
  try {
    const data = await interviewCodeApi.saveDraft(currentThreadId, {
      language: language.value,
      draft_code: draftCode.value
    })
    session.value = data?.coding_session || session.value
    saveStateText.value = '已自动保存'
    lastSavedAt.value = formatClock(new Date())
  } catch (error) {
    saveStateText.value = '保存失败'
    console.error('保存草稿失败:', error)
  }
}

const scheduleDraftSave = () => {
  if (!session.value) return
  saveStateText.value = '编辑中…'
  session.value = {
    ...session.value,
    drafts: {
      ...(session.value.drafts || {}),
      [language.value]: draftCode.value
    }
  }
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    persistDraft()
  }, 800)
}

const startSubmissionPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  if (!session.value?.submission_id) return
  pollTimer = setInterval(async () => {
    try {
      const data = await interviewCodeApi.getSubmissionResult(
        activeThreadId.value || threadId.value,
        session.value.submission_id
      )
      session.value = {
        ...session.value,
        judge_status: data.judge_status,
        judge_result: data.judge_result,
        submitted_at: data.submitted_at
      }
      if (data.judge_status && !pendingJudgeStatuses.has(data.judge_status)) {
        clearInterval(pollTimer)
        pollTimer = null
        if (latestSubmittedId.value && latestSubmittedId.value === session.value?.submission_id) {
          latestSubmittedId.value = ''
          message.success('代码考核已完成，正在返回面试继续后续环节')
          goBackToInterview()
        }
      }
    } catch (error) {
      clearInterval(pollTimer)
      pollTimer = null
      console.error('轮询判题结果失败:', error)
    }
  }, 1500)
}

const handleRunSample = async () => {
  const currentThreadId = activeThreadId.value || threadId.value
  if (!currentThreadId || !session.value) return
  runningSample.value = true
  try {
    await persistDraft()
    const data = await interviewCodeApi.runSample(currentThreadId, {
      language: language.value,
      code: draftCode.value
    })
    session.value = data?.coding_session || session.value
    bottomTab.value = 'run'
    message.success('样例运行完成')
  } catch (error) {
    message.error(error.message || '运行样例失败')
  } finally {
    runningSample.value = false
  }
}

const handleSubmit = async () => {
  const currentThreadId = activeThreadId.value || threadId.value
  if (!currentThreadId || !session.value) return
  submitting.value = true
  try {
    await persistDraft()
    const data = await interviewCodeApi.submitCodingSession(currentThreadId, {
      language: language.value,
      code: draftCode.value
    })
    session.value = data?.coding_session || session.value
    latestSubmittedId.value = String(session.value?.submission_id || '').trim()
    bottomTab.value = 'submission'
    message.success('代码已提交')
    startSubmissionPolling()
  } catch (error) {
    message.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

watch(
  threadId,
  (value) => {
    if (value) activeThreadId.value = value
  },
  { immediate: true }
)

watch(
  language,
  (value, previousValue) => {
    if (!session.value || value === previousValue) return
    if (previousValue) {
      session.value = {
        ...session.value,
        drafts: {
          ...(session.value.drafts || {}),
          [previousValue]: draftCode.value
        }
      }
    }
    draftCode.value =
      session.value?.drafts?.[value] || session.value?.problem?.starter_code?.[value] || ''
  }
)

const handleRequestHint = async () => {
  const currentThreadId = activeThreadId.value || threadId.value
  if (!currentThreadId || !session.value) return
  if (!hintQuestion.value.trim()) {
    message.warning('请先输入你希望获得的提示')
    return
  }
  hintLoading.value = true
  try {
    const data = await interviewCodeApi.requestHint(currentThreadId, {
      question: hintQuestion.value,
      draft_code: draftCode.value
    })
    session.value = {
      ...session.value,
      requested_hints: data?.history || [],
      hint_count: data?.hint_count ?? session.value?.hint_count ?? 0
    }
    hintQuestion.value = ''
  } catch (error) {
    message.error(error.message || '请求提示失败')
  } finally {
    hintLoading.value = false
  }
}

const goBackToInterview = () => {
  const currentThreadId = activeThreadId.value || threadId.value
  if (currentThreadId) {
    const startedAt = String(session.value?.started_at || '').trim()
    sessionStorage.setItem(getSkipCodingRedirectKey(currentThreadId), startedAt || 'active')
  }
  router.push(returnRoute.value)
}

watch([draftCode, language], () => {
  scheduleDraftSave()
})

onMounted(async () => {
  try {
    const hadThreadId = Boolean(threadId.value)
    const currentThreadId = await ensureThreadId()
    await loadSession(currentThreadId)
    if (!hadThreadId && !session.value) {
      await handleStartIfNeeded()
    }
    if (session.value?.status === 'submitted' && session.value?.submission_id) {
      startSubmissionPolling()
    }
  } catch (error) {
    message.error(error.message || '初始化 OJ 工作台失败')
  }
})

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style lang="less" scoped>
.coding-view {
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
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--gray-100);
}

.h1 {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0;
  color: var(--gray-1000);
}

.sub {
  font-size: 13px;
  color: var(--gray-500);
  margin: 6px 0 0;
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
.coding-layout {
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

.problem-desc {
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

/* ---------- 右栏：考察点 + 提示 ---------- */
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

.hint-block {
  display: flex;
  flex-direction: column;
}

.hint-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.hint-count {
  font-size: 12px;
  color: var(--gray-500);
}

.hint-desc {
  font-size: 13px;
  line-height: 1.65;
  color: var(--gray-600);
  margin: 10px 0 12px;
}

.hint-input {
  width: 100%;
  min-height: 64px;
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

.hint-input:focus {
  border-color: var(--main-600);
}

.hint-btn {
  width: 100%;
  justify-content: flex-start;
  margin-top: 12px;
}

.hint-history {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hint-item {
  border-left: 2px solid var(--gray-200);
  padding-left: 14px;
}

.hint-question {
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-800);
}

.hint-answer {
  font-size: 13px;
  line-height: 1.65;
  color: var(--gray-600);
  margin-top: 6px;
  white-space: pre-wrap;
}

.hint-time {
  font-size: 12px;
  color: var(--gray-500);
  margin-top: 8px;
}

/* ---------- 窄屏适配 ---------- */
@media (max-width: 1360px) {
  .coding-layout {
    grid-template-columns: 360px minmax(0, 1fr) 260px;
  }

  .top {
    padding: 18px 24px 14px;
  }

  .problem-panel,
  .aside-panel {
    padding: 20px 20px;
  }
}
</style>
