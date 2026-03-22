<template>
  <div class="interview-session-view">
    <AgentChatComponent
      ref="chatComponentRef"
      :agent-id="interviewAgentId"
      :single-mode="true"
      :context-overrides="contextOverrides"
      sidebar-placement="left"
      sidebar-title="面试记录"
      sidebar-create-text="开始新面试"
      sidebar-empty-text="暂无面试记录"
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
import { FileText, Settings, Share2 } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'

import AgentChatComponent from '@/components/AgentChatComponent.vue'
import { useAgentStore } from '@/stores/agent'
import { ChatExporter } from '@/utils/chatExporter'
import { handleChatError } from '@/utils/errorHandler'

const DEFAULT_POSITION = '通用岗位'
const DEFAULT_ROUND = '初试'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()
const chatComponentRef = ref(null)

const { selectedAgentId, defaultAgentId } = storeToRefs(agentStore)

const interviewAgentId = computed(() => selectedAgentId.value || defaultAgentId.value || '')

const selectedPosition = computed(() => {
  const value = String(route.query.position || '').trim()
  return value || DEFAULT_POSITION
})

const selectedRound = computed(() => {
  const value = String(route.query.round || '').trim()
  return value || DEFAULT_ROUND
})

const sessionKey = computed(() => String(route.query.session || '').trim())
const threadId = computed(() => String(route.query.threadId || '').trim())

const contextOverrides = computed(() => ({
  target_position: selectedPosition.value,
  interview_round: selectedRound.value
}))

const interviewOpeningPrompt = computed(
  () =>
    [
      `现在开始一轮${selectedPosition.value}${selectedRound.value}模拟面试。`,
      '你必须始终以面试官身份发言，不能代替候选人作答，也不要输出“我叫……/我毕业于……”这类候选人口吻内容。',
      '请先维护固定 5 步面试任务：1.读取简历并确认岗位背景；2.发起开场并请候选人自我介绍；3.追问项目经历与技术细节；4.评估岗位匹配度与风险点；5.输出总结与评分卡。',
      '首轮真正发问前先初始化任务，第 1 项 in_progress，其余 pending。',
      '如果当前会话里有附件，先读取附件简历；如果没有附件，只允许对“我的简历”知识库执行一次 query_kb 来读取最近上传的简历，本轮拿到内容后不要再次 query_kb，也不要对知识库返回内容调用 read_file。',
      '拿到简历后立刻进入第一问：先简短欢迎，再请候选人做简短自我介绍，最多补一句基于简历的提示性追问方向，并且结尾必须是问句。',
      '之后每次候选人回答后，请先用一句话做简短评价，再继续问下一个问题。'
    ].join('')
)

const threadTitle = computed(() => `${selectedPosition.value} · ${selectedRound.value}`)

const getStartedStorageKey = (key) => `interview-session-started:${key}`

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
    message.success(`面试记录已导出为 HTML 文件：${result.filename}`)
  } catch (error) {
    if (error?.message?.includes('没有可导出的对话内容')) {
      message.warning('请先开始一轮模拟面试，再导出记录')
      return
    }
    handleChatError(error, 'export')
  }
}

const maybeRestoreInterview = async () => {
  if (!threadId.value || !interviewAgentId.value || !chatComponentRef.value) return

  await nextTick()
  await chatComponentRef.value.openThread?.(threadId.value)
}

const maybeStartInterview = async () => {
  if (threadId.value) {
    await maybeRestoreInterview()
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
  }
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
      console.error('\u521d\u59cb\u5316\u9762\u8bd5\u667a\u80fd\u4f53\u5931\u8d25:', error)
    }
  }

  await maybeStartInterview()
})

watch(
  () => [sessionKey.value, threadId.value, interviewAgentId.value],
  async () => {
    await maybeStartInterview()
  }
)
</script>

<style lang="less" scoped>
.interview-session-view {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.session-header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.session-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--main-20);
  color: var(--main-color);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-900);
}

.session-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.session-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  min-height: 24px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-700);
  font-size: 12px;
}

@media (max-width: 768px) {
  .session-title {
    display: none;
  }
}
</style>
