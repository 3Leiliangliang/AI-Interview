<template>
  <div class="coding-view">
    <div class="coding-toolbar">
      <div>
        <div class="toolbar-title">OJ 工作台</div>
        <div class="toolbar-subtitle">左侧题面，右侧编码，可随时返回面试继续交流</div>
      </div>
      <div class="toolbar-actions">
        <a-button :loading="starting" @click="handleStartIfNeeded">刷新题目</a-button>
        <a-button @click="goBackToInterview">返回面试</a-button>
        <a-button v-if="canOpenResult" @click="goToInterviewResult(true)">查看面试结果</a-button>
        <a-button :loading="runningSample" @click="handleRunSample">运行样例</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">提交判题</a-button>
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
      <section class="problem-panel">
        <div class="panel-card problem-card">
          <div class="card-header">
            <div>
              <div class="card-title">{{ session.problem_title }}</div>
              <div class="card-meta">来源：{{ session.source || 'interview-seed' }}</div>
            </div>
            <a-tag :color="getStatusColor(session.judge_status || session.status)">
              {{ getStatusLabel(session.judge_status || session.status, '就绪') }}
            </a-tag>
          </div>

          <div class="problem-summary">{{ session.problem?.summary }}</div>

          <div class="problem-section">
            <h4>题目描述</h4>
            <p>{{ session.problem?.description }}</p>
          </div>

          <div class="problem-section" v-if="session.problem?.input_description">
            <h4>输入说明</h4>
            <p>{{ session.problem?.input_description }}</p>
          </div>

          <div class="problem-section" v-if="session.problem?.output_description">
            <h4>输出说明</h4>
            <p>{{ session.problem?.output_description }}</p>
          </div>

        </div>
      </section>

      <section class="editor-panel">
        <div class="panel-card editor-card">
          <div class="card-header editor-header">
            <div class="card-title">代码编辑器</div>
            <div class="editor-actions">
              <a-select v-model:value="language" class="language-select" :options="languageOptions" />
              <span class="save-state">{{ saveStateText }}</span>
            </div>
          </div>
          <textarea v-model="draftCode" class="code-editor" spellcheck="false"></textarea>
        </div>

        <div class="panel-card result-card result-tabs-card">
          <div class="card-header">
            <div>
              <div class="card-title">测试区</div>
              <div class="card-meta">通过上方标签切换测试用例、运行结果和提交结果</div>
            </div>
          </div>
          <a-tabs v-model:activeKey="bottomTab" class="result-tabs">
            <a-tab-pane key="cases" tab="测试用例">
              <div v-if="problemExamples.length" class="examples-list">
                <div v-for="(example, index) in problemExamples" :key="index" class="example-card">
                  <div class="example-title">样例 {{ index + 1 }}</div>
                  <div class="test-block">
                    <div class="console-title">输入</div>
                    <pre class="console-block">{{ example.input }}</pre>
                  </div>
                  <div class="test-block">
                    <div class="console-title">输出</div>
                    <pre class="console-block">{{ example.output }}</pre>
                  </div>
                </div>
              </div>
              <div v-else class="empty-text">当前题目未提供测试用例</div>
            </a-tab-pane>

            <a-tab-pane key="run" tab="运行结果">
              <div class="result-overview">
                <a-tag :color="getStatusColor(sampleRunResult.status)">
                  {{ getStatusLabel(sampleRunResult.status, '未运行') }}
                </a-tag>
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
              <ul v-if="sampleRunResult.tests?.length" class="judge-tests detailed-tests">
                <li v-for="test in sampleRunResult.tests" :key="test.name">
                  <div class="test-header">
                    <span :class="['dot', test.passed ? 'passed' : 'failed']"></span>
                    <span class="test-name">{{ test.name }}</span>
                    <span class="test-message">{{ test.message }}</span>
                  </div>
                  <div v-if="test.input" class="test-block">
                    <div class="console-title">输入</div>
                    <pre class="console-block">{{ test.input }}</pre>
                  </div>
                  <div v-if="test.expected_output" class="test-block">
                    <div class="console-title">期望输出</div>
                    <pre class="console-block">{{ test.expected_output }}</pre>
                  </div>
                  <div v-if="test.actual_output" class="test-block">
                    <div class="console-title">实际输出</div>
                    <pre class="console-block">{{ test.actual_output }}</pre>
                  </div>
                  <div v-if="test.stderr" class="test-block">
                    <div class="console-title">stderr</div>
                    <pre class="console-block error">{{ test.stderr }}</pre>
                  </div>
                </li>
              </ul>
              <div
                v-else-if="!sampleRunResult.compile_error && !sampleRunResult.stdout && !sampleRunResult.stderr"
                class="empty-text"
              >
                暂未运行样例
              </div>
            </a-tab-pane>

            <a-tab-pane key="submission" tab="提交结果">
              <div class="result-overview">
                <a-tag :color="getStatusColor(submissionResult.status || session.judge_status)">
                  {{ getStatusLabel(submissionResult.status || session.judge_status, '未提交') }}
                </a-tag>
                <span v-if="session.submission_id" class="card-meta">提交 ID：{{ session.submission_id }}</span>
                <span v-if="submissionResult.score !== undefined" class="card-meta">得分：{{ submissionResult.score }}</span>
                <span v-if="submissionResult.time_cost" class="card-meta">用时：{{ submissionResult.time_cost }}</span>
                <span v-if="submissionResult.memory_cost" class="card-meta">内存：{{ submissionResult.memory_cost }}</span>
              </div>
              <div v-if="submissionResult.message" class="judge-message">{{ submissionResult.message }}</div>
              <div v-if="submissionResult.compile_error" class="console-section">
                <div class="console-title">编译错误</div>
                <pre class="console-block error">{{ submissionResult.compile_error }}</pre>
              </div>
              <div v-if="submissionResult.stdout" class="console-section">
                <div class="console-title">stdout</div>
                <pre class="console-block">{{ submissionResult.stdout }}</pre>
              </div>
              <div v-if="submissionResult.stderr" class="console-section">
                <div class="console-title">stderr</div>
                <pre class="console-block error">{{ submissionResult.stderr }}</pre>
              </div>
              <ul v-if="submissionResult.tests?.length" class="judge-tests">
                <li v-for="test in submissionResult.tests" :key="test.name">
                  <span :class="['dot', test.passed ? 'passed' : 'failed']"></span>
                  <span class="test-name">{{ test.name }}</span>
                  <span class="test-message">{{ test.message }}</span>
                </li>
              </ul>
              <div v-else class="empty-text">暂未提交代码，提交后可在这里查看判题结果</div>
            </a-tab-pane>
          </a-tabs>
        </div>

        <div class="panel-card hint-card">
          <div class="card-header">
            <div class="card-title">请求提示</div>
          </div>
          <a-textarea
            v-model:value="hintQuestion"
            :rows="3"
            placeholder="例如：请提示我这题的思路，或帮我检查当前代码的边界条件。"
          />
          <div class="hint-actions">
            <a-button type="primary" :loading="hintLoading" @click="handleRequestHint">请求提示</a-button>
          </div>
          <div v-if="hintHistory.length" class="hint-history">
            <div v-for="item in hintHistory" :key="item.created_at" class="hint-item">
              <div class="hint-question">{{ item.question }}</div>
              <div class="hint-answer">{{ item.hint }}</div>
            </div>
          </div>
          <div v-else class="empty-text">只有在你主动请求时，Agent 才会给出提示。</div>
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
const canOpenResult = computed(
  () => Boolean(session.value?.submission_id) && !!currentJudgeStatus.value && !pendingJudgeStatuses.has(currentJudgeStatus.value)
)
const effectivePosition = computed(() => String(session.value?.target_position || selectedPosition.value || DEFAULT_POSITION).trim())
const effectiveRound = computed(() => String(route.query.round || selectedRound.value || '初试').trim() || '初试')

const getStatusColor = (status) => {
  if (status === 'ACCEPTED') return 'green'
  if (['WRONG_ANSWER', 'COMPILE_ERROR', 'RUNTIME_ERROR', 'SYSTEM_ERROR', 'MEMORY_LIMIT_EXCEEDED', 'CPU_TIME_LIMIT_EXCEEDED', 'REAL_TIME_LIMIT_EXCEEDED'].includes(status)) return 'red'
  if (status === 'PENDING' || status === 'JUDGING') return 'blue'
  return 'gold'
}

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

const resultRoute = computed(() => ({
  name: 'InterviewResultPage',
  query: {
    threadId: activeThreadId.value || threadId.value,
    position: effectivePosition.value,
    round: effectiveRound.value
  }
}))

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
  saveStateText.value = '保存中...'
  try {
    const data = await interviewCodeApi.saveDraft(currentThreadId, {
      language: language.value,
      draft_code: draftCode.value
    })
    session.value = data?.coding_session || session.value
    saveStateText.value = '已保存'
  } catch (error) {
    saveStateText.value = '保存失败'
    console.error('保存草稿失败:', error)
  }
}

const scheduleDraftSave = () => {
  if (!session.value) return
  saveStateText.value = '编辑中...'
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
      requested_hints: data?.history || []
    }
    hintQuestion.value = ''
  } catch (error) {
    message.error(error.message || '请求提示失败')
  } finally {
    hintLoading.value = false
  }
}

const goToInterviewResult = (autoGenerate = false) => {
  const target = {
    ...resultRoute.value,
    query: {
      ...resultRoute.value.query,
      ...(autoGenerate ? { autoGenerate: '1' } : {})
    }
  }
  if (autoGenerate) {
    router.replace(target)
    return
  }
  router.push(target)
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
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  background: var(--gray-50);
}

.coding-toolbar,
.panel-card {
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
}

.coding-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
}

.toolbar-title,
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-900);
}

.toolbar-subtitle,
.card-meta,
.empty-text,
.save-state,
.test-message {
  font-size: 13px;
  color: var(--gray-600);
}

.toolbar-actions,
.editor-actions,
.hint-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.state-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-container);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
}

.coding-layout {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: minmax(320px, 42%) minmax(420px, 58%);
  gap: 16px;
}

.problem-panel,
.editor-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  padding: 16px;
  overflow: auto;
}

.problem-card,
.editor-card {
  flex: 1;
}

.result-card {
  max-height: 320px;
}

.result-tabs-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.hint-card {
  max-height: 220px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.problem-summary {
  padding: 12px;
  border-radius: 12px;
  background: var(--main-20);
  color: var(--gray-800);
  line-height: 1.6;
}

.problem-section {
  margin-top: 16px;
  color: var(--gray-800);
  line-height: 1.7;
}

.problem-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--gray-900);
}

.problem-section p {
  margin: 0;
  white-space: pre-wrap;
}

.example-card {
  padding: 12px;
  border-radius: 12px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.example-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.editor-header {
  align-items: center;
}

.result-overview {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 12px;
}

.language-select {
  width: 140px;
}

.code-editor {
  width: 100%;
  min-height: 520px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  padding: 16px;
  resize: vertical;
  outline: none;
  background: var(--gray-10000);
  color: var(--main-5);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.result-tabs {
  flex: 1;
  min-height: 0;
}

.result-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 12px;
}

.result-tabs :deep(.ant-tabs-content-holder) {
  overflow: auto;
  min-height: 0;
}

.examples-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.judge-message {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--gray-50);
  color: var(--gray-800);
}

.console-section {
  margin-bottom: 12px;
}

.console-title {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-700);
}

.console-block {
  margin: 0;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-50);
  color: var(--gray-800);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, 'Courier New', monospace;
}

.console-block.error {
  background: #fff2f0;
  border-color: #ffccc7;
  color: #a8071a;
}

.judge-tests {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.judge-tests li {
  display: grid;
  grid-template-columns: 10px auto 1fr;
  gap: 8px;
  align-items: start;
}

.detailed-tests li {
  display: block;
  padding: 12px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--gray-50);
}

.test-header {
  display: grid;
  grid-template-columns: 10px auto 1fr;
  gap: 8px;
  align-items: start;
  margin-bottom: 10px;
}

.test-block + .test-block {
  margin-top: 10px;
}

.test-name {
  min-width: 96px;
  color: var(--gray-800);
}

.dot {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 50%;
}

.dot.passed {
  background: var(--color-success-500);
}

.dot.failed {
  background: var(--color-error-500);
}

.hint-history {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hint-item {
  padding: 12px;
  border-radius: 12px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
}

.hint-question {
  margin-bottom: 8px;
  font-weight: 600;
  color: var(--gray-800);
}

.hint-answer {
  white-space: pre-wrap;
  color: var(--gray-700);
  line-height: 1.6;
}

@media (max-width: 1080px) {
  .coding-layout {
    grid-template-columns: 1fr;
  }

  .coding-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }
}
</style>
