<template>
  <div class="interview-session-view">
    <AgentChatComponent
      ref="chatComponentRef"
      :agent-id="interviewAgentId"
      :single-mode="true"
      :preferred-thread-id="threadId"
      :context-overrides="contextOverrides"
      sidebar-placement="left"
      sidebar-title="面试记录"
      sidebar-create-text="开始新面试"
      sidebar-empty-text="暂无面试记录"
      @agent-state-change="handleAgentStateChange"
      @thread-change="handleThreadChange"
    >
      <template #header-right>
        <div class="agent-nav-btn" @click="backToSetup">
          <Settings :size="18" class="nav-btn-icon" />
          <span class="text">调整配置</span>
        </div>
        <div class="agent-nav-btn" @click="openResumeCenter">
          <FileText :size="18" class="nav-btn-icon" />
          <span class="text">我的简历</span>
        </div>
        <div v-if="threadId" class="agent-nav-btn" @click="openInterviewResult">
          <BarChart3 :size="18" class="nav-btn-icon" />
          <span class="text">面试结果</span>
        </div>
        <div class="agent-nav-btn" @click="handleShareChat">
          <Share2 :size="18" class="nav-btn-icon" />
          <span class="text">导出记录</span>
        </div>
      </template>
    </AgentChatComponent>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { BarChart3, FileText, Settings, Share2 } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import AgentChatComponent from '@/components/AgentChatComponent.vue'
import { useAgentStore } from '@/stores/agent'
import { ChatExporter } from '@/utils/chatExporter'
import { handleChatError } from '@/utils/errorHandler'

const DEFAULT_POSITION = '后端工程师'
const DEFAULT_ROUND = '初试'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const chatComponentRef = ref(null)

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')
const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const sessionKey = computed(() => String(route.query.session || '').trim())
const threadId = computed(() => String(route.query.threadId || '').trim())

const contextOverrides = computed(() => ({
  target_position: selectedPosition.value,
  interview_round: selectedRound.value
}))

const threadTitle = computed(() => `${selectedPosition.value} · ${selectedRound.value}`)

const interviewOpeningPrompt = computed(() => {
  return [
    `现在开始一轮${selectedPosition.value}${selectedRound.value}模拟面试。`,
    '你必须始终以面试官身份发言，不要代替候选人作答。',
    '请维护固定 7 个阶段 todo：1.读取简历并确认岗位背景；2.发起开场并请候选人自我介绍；3.追问项目经历与技术细节；4.相关技术知识提问；5.代码考核；6.评估岗位匹配度与风险点；7.输出总结与评分卡。',
    '如果当前会话里有附件，先读取附件简历；如果没有附件，只允许调用一次 query_kb 查询“我的简历”知识。',
    '第 4 阶段每次发技术题前都调用 pick_random_technical_question，并传入 excluded_questions 避免重复。',
    '当第 4 阶段完成时，调用 start_code_assessment 启动代码考核，并明确引导用户进入代码工作台。',
    '代码考核阶段除非用户明确请求提示，否则不要主动点评代码。'
  ].join('')
})

const getStartedStorageKey = (key) => `interview-session-started:${key}`
const getSkipCodingRedirectKey = (key) => `interview-skip-coding-redirect:${key}`

const parseThreadTitle = (title) => {
  const normalizedTitle = String(title || '').trim()
  if (!normalizedTitle || !normalizedTitle.includes('·')) {
    return {
      position: selectedPosition.value,
      round: selectedRound.value
    }
  }

  const [position, round] = normalizedTitle.split('·', 2)
  return {
    position: String(position || '').trim() || selectedPosition.value,
    round: String(round || '').trim() || selectedRound.value
  }
}

const restoreInterviewThread = async () => {
  if (!threadId.value || !chatComponentRef.value) return
  await nextTick()
  await chatComponentRef.value.openThread?.(threadId.value)
}

const backToSetup = () => {
  router.push({
    name: 'AgentComp',
    query: {
      position: selectedPosition.value,
      round: selectedRound.value
    }
  })
}

const openResumeCenter = () => {
  router.push('/resume')
}

const openInterviewResult = () => {
  if (!threadId.value) return
  router.push({
    name: 'InterviewResultPage',
    query: {
      threadId: threadId.value,
      position: selectedPosition.value,
      round: selectedRound.value
    }
  })
}

const handleShareChat = async () => {
  try {
    const exportData = chatComponentRef.value?.getExportPayload?.()
    if (!exportData) {
      message.warning('当前没有可导出的面试记录')
      return
    }

    const hasMessages = Boolean(exportData.messages?.length)
    const hasOngoingMessages = Boolean(exportData.onGoingMessages?.length)
    if (!hasMessages && !hasOngoingMessages) {
      message.warning('请先开始一轮模拟面试，再导出记录')
      return
    }

    const result = await ChatExporter.exportToHTML(exportData)
    message.success(`面试记录已导出为 HTML：${result.filename}`)
  } catch (error) {
    if (error?.message?.includes('没有可导出的对话内容')) {
      message.warning('请先开始一轮模拟面试，再导出记录')
      return
    }
    handleChatError(error, 'export')
  }
}

const maybeStartInterview = async () => {
  if (threadId.value) {
    await restoreInterviewThread()
    return
  }
  if (!sessionKey.value || !interviewAgentId.value || !chatComponentRef.value) return
  if (sessionStorage.getItem(getStartedStorageKey(sessionKey.value)) === '1') return

  await nextTick()
  const startedThreadId = await chatComponentRef.value.startInterviewSession({
    openingPrompt: interviewOpeningPrompt.value,
    threadTitle: threadTitle.value,
    forceNewThread: true
  })

  if (startedThreadId) {
    sessionStorage.setItem(getStartedStorageKey(sessionKey.value), '1')
    router.replace({
      name: 'AgentInterviewComp',
      query: {
        threadId: startedThreadId,
        position: selectedPosition.value,
        round: selectedRound.value,
        session: sessionKey.value
      }
    })
  }
}

const handleAgentStateChange = (agentState) => {
  const codingSession = agentState?.coding_session
  if (!threadId.value || !codingSession) return
  if (!['ready', 'coding'].includes(codingSession.status)) return
  const skipKey = getSkipCodingRedirectKey(threadId.value)
  const skipStartedAt = sessionStorage.getItem(skipKey)
  const currentStartedAt = String(codingSession.started_at || '').trim() || 'active'
  if (skipStartedAt && skipStartedAt === currentStartedAt) {
    return
  }
  if (skipStartedAt && skipStartedAt !== currentStartedAt) {
    sessionStorage.removeItem(skipKey)
  }

  router.push({
    name: 'InterviewCodingWorkbench',
    query: {
      threadId: threadId.value,
      position: selectedPosition.value,
      round: selectedRound.value
    }
  })
}

const handleThreadChange = (nextThread) => {
  const normalizedThreadId = String(nextThread?.id || nextThread || '').trim()
  if (!normalizedThreadId || normalizedThreadId === threadId.value) return

  const { position, round } = parseThreadTitle(nextThread?.title)

  router.replace({
    name: 'AgentInterviewComp',
    query: {
      threadId: normalizedThreadId,
      position,
      round,
      ...(sessionKey.value ? { session: sessionKey.value } : {})
    }
  })
}

onMounted(async () => {
  if (!sessionKey.value && !threadId.value) {
    router.replace({
      name: 'AgentComp',
      query: {
        position: selectedPosition.value,
        round: selectedRound.value
      }
    })
    return
  }

  if (!agentStore.isInitialized) {
    try {
      await agentStore.initialize()
    } catch (error) {
      console.error('初始化面试智能体失败:', error)
    }
  }

  await maybeStartInterview()
})

watch(
  () => [sessionKey.value, threadId.value, interviewAgentId.value],
  async () => {
    await maybeStartInterview()
    if (threadId.value) {
      await restoreInterviewThread()
    }
  }
)
</script>

<style lang="less" scoped>
.interview-session-view {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>
