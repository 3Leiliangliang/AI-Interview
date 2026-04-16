<template>
  <div class="interview-session-view">
    <AgentChatComponent
      ref="chatComponentRef"
      :agent-id="interviewAgentId"
      :single-mode="true"
      :show-sidebar="false"
      :preferred-thread-id="threadId"
      :context-overrides="contextOverrides"
      @agent-state-change="handleAgentStateChange"
      @thread-change="handleThreadChange"
    >
      <template #header-right>
        <div
          class="agent-nav-btn"
          :class="{ 'is-active': isVideoMode, 'is-disabled': isInitializing }"
          @click="toggleVideoMode"
        >
          <LoaderCircle v-if="isInitializing" :size="18" class="nav-btn-icon loading-icon" />
          <Video v-else :size="18" class="nav-btn-icon" />
          <span class="text">{{ isVideoMode ? '关闭分析' : '视频分析' }}</span>
          <span v-if="isVideoMode" class="analyzing-dot"></span>
        </div>
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
import { BarChart3, FileText, Settings, Share2, Video, LoaderCircle } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import AgentChatComponent from '@/components/AgentChatComponent.vue'
import { useAgentStore } from '@/stores/agent'
import { useVideoEventStream } from '@/composables/useVideoEventStream'
import { ChatExporter } from '@/utils/chatExporter'
import { handleChatError } from '@/utils/errorHandler'
import { getDefaultPositionType, getFallbackPositionTypes } from '@/utils/position_utils'

const DEFAULT_POSITION = getDefaultPositionType(getFallbackPositionTypes()).label
const DEFAULT_ROUND = '初试'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const chatComponentRef = ref(null)
const eventStream = useVideoEventStream()

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const { isVideoMode, isInitializing } = eventStream

const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')
const selectedPosition = computed(() => String(route.query.position || '').trim() || DEFAULT_POSITION)
const selectedRound = computed(() => String(route.query.round || '').trim() || DEFAULT_ROUND)
const selectedResumeId = computed(() => {
  const raw = String(route.query.resumeId || '').trim()
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
})
const sessionKey = computed(() => String(route.query.session || '').trim())
const threadId = computed(() => String(route.query.threadId || '').trim())

const contextOverrides = computed(() => ({
  target_position: selectedPosition.value,
  interview_round: selectedRound.value,
  selected_resume_id: selectedResumeId.value
}))

const threadTitle = computed(() => `${selectedPosition.value} · ${selectedRound.value}`)

const interviewOpeningPrompt = computed(() => {
  return [
    `现在开始一轮${selectedPosition.value}${selectedRound.value}模拟面试。`,
    '请基于当前岗位设定与系统已注入的简历上下文，直接开始本轮面试。',
    '先完成开场引导并请候选人做简短自我介绍。'
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

async function toggleVideoMode() {
  if (isVideoMode.value) {
    eventStream.disableVideoMode()
    return
  }
  const activeThreadId = chatComponentRef.value?.currentChatId
  if (!activeThreadId) {
    message.warning('面试会话未就绪，无法开启视频模式')
    return
  }
  await eventStream.enableVideoMode(activeThreadId)
  if (!isVideoMode.value && eventStream.error.value) {
    message.error(eventStream.error.value)
  }
}

const backToSetup = () => {
  router.push({
    name: 'AgentComp',
    query: {
      position: selectedPosition.value,
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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
    threadMetadata: {
      interview_mode: 'text',
      target_position: selectedPosition.value,
      interview_round: selectedRound.value,
      ...(selectedResumeId.value ? { resume_id: selectedResumeId.value } : {})
    },
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
        session: sessionKey.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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
      round: selectedRound.value,
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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
      ...(sessionKey.value ? { session: sessionKey.value } : {}),
      ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
    }
  })
}

onMounted(async () => {
  if (!sessionKey.value && !threadId.value) {
    router.replace({
      name: 'AgentComp',
      query: {
        position: selectedPosition.value,
        round: selectedRound.value,
        ...(selectedResumeId.value ? { resumeId: String(selectedResumeId.value) } : {})
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

.agent-nav-btn {
  &.is-disabled {
    opacity: 0.5;
    pointer-events: none;
  }

  &.is-active {
    color: var(--main-color);
    background: var(--main-20);
  }
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.analyzing-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  margin-left: 4px;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}
</style>
