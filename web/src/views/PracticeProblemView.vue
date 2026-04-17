<template>
  <div class="practice-problem">
    <div class="page-toolbar">
      <div class="toolbar-main">
        <a-button @click="goBack">返回题单</a-button>
        <div>
          <div class="toolbar-title">{{ problem?.title || session?.problem_title || '代码练习' }}</div>
          <div class="toolbar-meta">
            <span>{{ problem?.primary_topic_tag || '专题练习' }}</span>
            <span>{{ difficultyLabelMap[problem?.difficulty_tag] || '中等' }}</span>
          </div>
        </div>
      </div>
      <div class="toolbar-actions">
        <a-button :loading="runningSample" @click="handleRunSample">运行样例</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">提交判题</a-button>
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
            <div>
              <div class="question-caption">题号 #{{ problem.problem_index }}</div>
              <h1>{{ problem.title }}</h1>
              <p v-if="problem.summary">{{ problem.summary }}</p>
            </div>
            <div class="question-tags">
              <a-tag :color="difficultyColorMap[problem.difficulty_tag] || 'default'">
                {{ difficultyLabelMap[problem.difficulty_tag] || '中等' }}
              </a-tag>
              <a-tag v-for="tag in problem.topic_tags || []" :key="tag">{{ tag }}</a-tag>
            </div>
          </div>

          <div class="question-section">
            <h3>题目描述</h3>
            <pre class="content-text">{{ problem.description || '暂无描述' }}</pre>
          </div>

          <div v-if="problem.input_description" class="question-section">
            <h3>输入说明</h3>
            <pre class="content-text">{{ problem.input_description }}</pre>
          </div>

          <div v-if="problem.output_description" class="question-section">
            <h3>输出说明</h3>
            <pre class="content-text">{{ problem.output_description }}</pre>
          </div>

          <div v-if="problem.examples?.length" class="question-section">
            <h3>示例</h3>
            <div class="example-grid">
              <div v-for="(example, index) in problem.examples" :key="index" class="example-card">
                <div class="example-title">样例 {{ index + 1 }}</div>
                <div class="example-block">
                  <span>输入</span>
                  <pre>{{ example.input || '(空)' }}</pre>
                </div>
                <div class="example-block">
                  <span>输出</span>
                  <pre>{{ example.output || '(空)' }}</pre>
                </div>
              </div>
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
            <a-select v-model:value="language" class="language-select" :options="languageOptions" />
          </div>
          <textarea v-model="draftCode" class="code-editor" spellcheck="false"></textarea>
        </div>

        <div class="panel-card result-card">
          <a-tabs v-model:activeKey="bottomTab">
            <a-tab-pane key="cases" tab="测试用例">
              <div v-if="problem.examples?.length" class="example-grid example-grid--compact">
                <div v-for="(example, index) in problem.examples" :key="index" class="example-card">
                  <div class="example-title">样例 {{ index + 1 }}</div>
                  <div class="example-block">
                    <span>输入</span>
                    <pre>{{ example.input || '(空)' }}</pre>
                  </div>
                  <div class="example-block">
                    <span>输出</span>
                    <pre>{{ example.output || '(空)' }}</pre>
                  </div>
                </div>
              </div>
              <div v-else class="empty-text">当前题目未提供测试用例</div>
            </a-tab-pane>

            <a-tab-pane key="run" tab="运行结果">
              <div class="result-overview">
                <a-tag :color="statusColor(sampleRunResult.status)">{{ statusLabel(sampleRunResult.status, '未运行') }}</a-tag>
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
          </a-tabs>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

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
const bottomTab = ref('cases')
const saveStateText = ref('未保存')

const pendingJudgeStatuses = new Set(['PENDING', 'JUDGING'])

let saveTimer = null
let pollTimer = null

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

const languageOptions = computed(() => {
  const allowed = session.value?.problem?.allowed_languages || problem.value?.allowed_languages || ['javascript']
  return allowed.map((value) => ({ label: languageLabelMap[value] || value, value }))
})

const sampleRunResult = computed(() => session.value?.sample_run || {})
const submissionResult = computed(() => session.value?.judge_result || {})
const sessionId = computed(() => String(session.value?.session_id || '').trim())
const problemRef = computed(() => String(route.params.problem_ref || '').trim())

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
  PARTIALLY_ACCEPTED: '部分通过'
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

const syncDraftFromSession = () => {
  language.value = session.value?.language || languageOptions.value[0]?.value || 'javascript'
  draftCode.value =
    session.value?.drafts?.[language.value] ||
    session.value?.draft_code ||
    session.value?.problem?.starter_code?.[language.value] ||
    ''
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

const persistDraft = async () => {
  if (!sessionId.value || !session.value) return
  saveStateText.value = '保存中...'
  try {
    const data = await practiceApi.saveDraft(sessionId.value, {
      language: language.value,
      draft_code: draftCode.value
    })
    session.value = data?.practice_session || session.value
    saveStateText.value = '已保存'
  } catch (error) {
    saveStateText.value = '保存失败'
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
        clearInterval(pollTimer)
        pollTimer = null
      }
    } catch (error) {
      clearInterval(pollTimer)
      pollTimer = null
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
    bottomTab.value = 'submission'
    startSubmissionPolling()
    message.success('代码已提交')
  } catch (error) {
    message.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

const goBack = () => {
  const topic = String(route.query.topic || '').trim()
  if (topic) {
    router.push({ name: 'PracticeTopicPage', params: { topic_key: topic } })
    return
  }
  router.push({ name: 'PracticeHomePage' })
}

watch([draftCode, language], () => {
  scheduleDraftSave()
})

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
    draftCode.value = session.value?.drafts?.[value] || session.value?.problem?.starter_code?.[value] || ''
  }
)

onMounted(async () => {
  loading.value = true
  try {
    await loadProblem()
    if (!problem.value?.supports_online_judge) {
      message.warning('当前题目暂未绑定在线判题，暂时无法开始练习')
      goBack()
      return
    }
    await ensureSession()
    if (session.value?.status === 'submitted' && session.value?.submission_id) {
      startSubmissionPolling()
    }
  } catch (error) {
    message.error(error.message || '加载练习题目失败')
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
  if (pollTimer) clearInterval(pollTimer)
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
  padding: 16px 18px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.toolbar-main,
.toolbar-actions,
.toolbar-meta,
.question-tags,
.result-overview {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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
.test-message {
  font-size: 13px;
  color: var(--gray-600);
}

.state-panel {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.content-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(320px, 46%) minmax(420px, 54%);
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
.editor-card {
  flex: 1;
}

.panel-card {
  padding: 18px;
  overflow: auto;
}

.question-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--gray-150);
}

.question-hero h1 {
  margin: 6px 0 0;
  font-size: 28px;
  line-height: 1.3;
}

.question-hero p {
  margin: 10px 0 0;
  color: var(--gray-700);
  line-height: 1.8;
}

.question-section + .question-section {
  margin-top: 20px;
}

.question-section h3 {
  margin: 0 0 10px;
  font-size: 16px;
  color: var(--gray-1000);
}

.content-text,
.console-block,
.example-block pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'SFMono-Regular', Consolas, monospace;
  line-height: 1.7;
}

.content-text {
  font-size: 13px;
  color: var(--gray-800);
  font-family: inherit;
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
  padding: 14px;
  border-radius: 14px;
  background: var(--gray-25);
  border: 1px solid var(--gray-200);
}

.example-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-900);
}

.example-block + .example-block {
  margin-top: 10px;
}

.example-block span,
.console-title {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--gray-700);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.language-select {
  width: 140px;
}

.code-editor {
  width: 100%;
  min-height: 520px;
  border: 1px solid var(--gray-200);
  border-radius: 14px;
  padding: 16px;
  resize: vertical;
  outline: none;
  background: var(--gray-10000);
  color: var(--main-5);
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.judge-message {
  margin: 0 0 12px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
  color: var(--gray-800);
}

.console-section + .console-section {
  margin-top: 12px;
}

.console-block {
  padding: 12px;
  border-radius: 12px;
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
  margin: 12px 0 0;
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

@media (max-width: 1080px) {
  .content-layout {
    grid-template-columns: 1fr;
  }

  .page-toolbar {
    flex-direction: column;
    align-items: stretch;
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

  .question-hero {
    flex-direction: column;
  }
}
</style>
