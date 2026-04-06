<template>
  <div class="interview-setup-view">
    <div class="setup-shell">
      <div class="setup-card">
        <div class="setup-badge">
          <Sparkles :size="14" />
          <span>模拟面试配置</span>
        </div>

        <h1 class="setup-title">开始一轮新的模拟面试</h1>
        <p class="setup-subtitle">
          先选择岗位和轮次，再进入面试界面。进入后面试官会自动发起第一问。
        </p>

        <div class="setup-section">
          <div class="section-title">面试形式</div>
          <div class="option-grid mode-grid">
            <button
              v-for="item in interviewModeOptions"
              :key="item.value"
              type="button"
              class="option-card"
              :class="{ active: selectedInterviewMode === item.value }"
              @click="selectedInterviewMode = item.value"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="setup-section">
          <div class="section-title">选择岗位</div>
          <div class="option-grid">
            <button
              v-for="item in positionOptions"
              :key="item.value"
              type="button"
              class="option-card"
              :class="{ active: selectedPosition === item.value }"
              @click="selectedPosition = item.value"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="setup-section">
          <div class="section-title">面试轮次</div>
          <div class="option-grid round-grid">
            <button
              v-for="item in roundOptions"
              :key="item.value"
              type="button"
              class="option-card"
              :class="{ active: selectedRound === item.value }"
              @click="selectedRound = item.value"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <div class="setup-summary">
          <span class="summary-label">当前配置</span>
          <div class="summary-tags">
            <span class="summary-tag">{{ selectedInterviewModeLabel }}</span>
            <span class="summary-tag">{{ selectedPosition }}</span>
            <span class="summary-tag">{{ selectedRound }}</span>
          </div>
        </div>

        <div class="setup-actions">
          <button class="primary-btn" type="button" @click="startInterview">开始面试</button>
          <button class="secondary-btn" type="button" @click="openResumeCenter">我的简历</button>
        </div>
      </div>

      <div class="history-card">
        <div class="section-title history-title">
          <Clock :size="16" />
          <span>最近面试记录</span>
        </div>
        <div class="history-list" v-if="historyThreads.length > 0">
          <div
            v-for="thread in historyThreads"
            :key="thread.id"
            class="history-item"
            @click="continueInterview(thread)"
          >
            <div class="history-item-content">
              <div class="history-item-title">{{ thread.title || '未命名面试' }}</div>
              <div class="history-item-time">{{ formatTime(thread.created_at) }}</div>
            </div>
            <ChevronRight :size="16" class="history-item-arrow" />
          </div>
        </div>
        <div class="empty-state" v-else>
          <div v-if="loadingHistory" class="loading-text">
            <LoaderCircle class="loading-icon" :size="18" />
            <span>加载中...</span>
          </div>
          <div v-else class="empty-text">暂无面试记录</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Sparkles, Clock, ChevronRight, LoaderCircle } from 'lucide-vue-next'
import { useAgentStore } from '@/stores/agent'
import { threadApi } from '@/apis/agent_api'
import { parseToShanghai } from '@/utils/time'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()

const positionOptions = [
  { label: '前端', value: '前端工程师' },
  { label: '后端', value: '后端工程师' }
]

const interviewModeOptions = [
  { label: '文本面试', value: 'text' },
  { label: '语音对话面试', value: 'voice' }
]

const roundOptions = [
  { label: '初试', value: '初试' },
  { label: '复试', value: '复试' },
  { label: 'HR', value: 'HR' }
]

const selectedInterviewMode = ref(String(route.query.mode || 'text'))
const selectedPosition = ref(String(route.query.position || '后端工程师'))
const selectedRound = ref(String(route.query.round || '初试'))

const selectedInterviewModeLabel = computed(() => {
  return interviewModeOptions.find((item) => item.value === selectedInterviewMode.value)?.label || '文本面试'
})

const startInterview = () => {
  const targetRouteName = selectedInterviewMode.value === 'voice' ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp'
  router.push({
    name: targetRouteName,
    query: {
      mode: selectedInterviewMode.value,
      position: selectedPosition.value,
      round: selectedRound.value,
      session: `${Date.now()}`
    }
  })
}

const openResumeCenter = () => {
  router.push('/resume')
}

const historyThreads = ref([])
const loadingHistory = ref(false)

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const parsed = parseToShanghai(timeStr)
  return parsed ? parsed.format('M/D HH:mm') : ''
}

onMounted(async () => {
  loadingHistory.value = true
  try {
    if (!agentStore.isInitialized) {
      await agentStore.initialize()
    }
    const agentId = agentStore.defaultAgentId
    if (agentId) {
      const threads = await threadApi.getThreads(agentId, 15, 0)
      if (threads && Array.isArray(threads)) {
        historyThreads.value = threads
      }
    }
  } catch (error) {
    console.error('Failed to load interview history:', error)
  } finally {
    loadingHistory.value = false
  }
})

const continueInterview = (thread) => {
  const [pos, rnd] = (thread.title || '').split(' · ')
  const isVoiceThread = thread?.metadata?.interview_mode === 'voice'

  router.push({
    name: isVoiceThread ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      mode: isVoiceThread ? 'voice' : 'text',
      position: pos ? pos.trim() : '后端工程师',
      round: rnd ? rnd.trim() : '初试',
      threadId: thread.id
    }
  })
}
</script>

<style lang="less" scoped>
.interview-setup-view {
  width: 100%;
  min-height: 100%;
  background: var(--gray-25);
  display: flex;
  align-items: center;
  justify-content: center;
}

.setup-shell {
  display: flex;
  align-items: stretch;
  justify-content: center;
  width: 100%;
  max-width: 1080px;
  padding: 32px 20px;
  gap: 24px;
}

.setup-card {
  flex: 3;
  padding: 32px;
  border-radius: 20px;
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
}

.setup-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--main-20);
  color: var(--main-color);
  font-size: 12px;
  font-weight: 600;
}

.setup-title {
  margin: 18px 0 10px;
  font-size: 28px;
  line-height: 1.2;
  color: var(--gray-900);
}

.setup-subtitle {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
}

.setup-section {
  margin-top: 28px;
}

.section-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.round-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.mode-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.option-card {
  min-height: 48px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid var(--gray-150);
  background: var(--gray-0);
  color: var(--gray-700);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.option-card:hover {
  border-color: var(--main-200);
  color: var(--main-color);
}

.option-card.active {
  border-color: var(--main-color);
  background: var(--main-20);
  color: var(--main-color);
  font-weight: 600;
}

.setup-summary {
  margin-top: 28px;
  padding: 16px 18px;
  border-radius: 14px;
  background: var(--gray-25);
  border: 1px solid var(--gray-100);
}

.summary-label {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--gray-500);
}

.summary-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.summary-tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  color: var(--gray-700);
  font-size: 13px;
}

.setup-actions {
  display: flex;
  gap: 12px;
  margin-top: 28px;
}

.primary-btn,
.secondary-btn {
  min-width: 136px;
  height: 44px;
  padding: 0 18px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-btn {
  border: none;
  background: var(--main-color);
  color: var(--gray-0);
}

.secondary-btn {
  border: 1px solid var(--gray-150);
  background: var(--gray-0);
  color: var(--gray-700);
}

.history-card {
  flex: 2;
  min-width: 320px;
  padding: 24px;
  border-radius: 20px;
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
  display: flex;
  flex-direction: column;
}

.history-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 20px;
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-800);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  max-height: 500px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-radius: 12px;
  background: var(--gray-25);
  border: 1px solid var(--gray-100);
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    background: var(--main-20);
    
    .history-item-title {
      color: var(--main-color);
    }
    
    .history-item-arrow {
      color: var(--main-color);
      transform: translateX(4px);
    }
  }
}

.history-item-content {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.2s ease;
}

.history-item-time {
  font-size: 12px;
  color: var(--gray-500);
}

.history-item-arrow {
  color: var(--gray-400);
  transition: all 0.2s ease;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  border-radius: 12px;
  background: var(--gray-25);
  border: 1px dashed var(--gray-200);
}

.loading-text {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--main-color);
  font-size: 14px;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-text {
  color: var(--gray-500);
  font-size: 14px;
}

@media (max-width: 860px) {
  .setup-shell {
    flex-direction: column;
  }
  
  .history-card {
    width: 100%;
  }

  .setup-card {
    padding: 24px 18px;
  }

  .setup-title {
    font-size: 24px;
  }

  .option-grid,
  .round-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .setup-actions {
    flex-direction: column;
  }

  .primary-btn,
  .secondary-btn {
    width: 100%;
  }
}
</style>
