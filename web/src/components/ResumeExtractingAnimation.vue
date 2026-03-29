<template>
  <div class="resume-extracting">
    <div class="resume-extracting__card">
      <!-- Title -->
      <div class="resume-extracting__header">
        <Brain :size="20" class="resume-extracting__icon" />
        <span class="resume-extracting__title">AI 简历分析助手</span>
      </div>

      <!-- Document scanning animation -->
      <div class="resume-extracting__animation">
        <div class="doc-stack">
          <div class="doc doc--back">
            <FileText :size="20" />
          </div>
          <div class="doc doc--mid">
            <FileText :size="20" />
          </div>
          <div class="doc doc--front">
            <FileText :size="20" />
            <div class="scan-line"></div>
          </div>
        </div>
      </div>

      <!-- Progress bar -->
      <div class="resume-extracting__progress">
        <div class="resume-extracting__progress-bar" :style="{ width: progressPercent + '%' }"></div>
      </div>

      <!-- Stage icon + message -->
      <div class="resume-extracting__stage">
        <Loader2 v-if="isActive" :size="16" class="resume-extracting__spinner" />
        <CheckCircle v-else-if="stage === 'completed'" :size="16" class="resume-extracting__check" />
        <XCircle v-else-if="stage === 'failed'" :size="16" class="resume-extracting__error" />
        <span class="resume-extracting__message">{{ stageMessage }}</span>
      </div>

      <!-- Live statistics -->
      <div v-if="hasStats && isActive" class="resume-extracting__stats">
        <span class="resume-extracting__stat">已提取 {{ stats.skills }} 项技能</span>
        <span class="resume-extracting__stat-divider">|</span>
        <span class="resume-extracting__stat">已提取 {{ stats.projects }} 个项目</span>
        <span class="resume-extracting__stat-divider">|</span>
        <span class="resume-extracting__stat">已提取 {{ stats.experience }} 段经历</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FileText, Brain, CheckCircle, XCircle, Loader2 } from 'lucide-vue-next'

const props = defineProps({
  stage: {
    type: String,
    default: 'idle',
    validator: (v) => ['idle', 'parsing', 'extracting', 'completed', 'failed'].includes(v),
  },
  stats: {
    type: Object,
    default: () => ({ skills: 0, projects: 0, experience: 0 }),
  },
})

const stageMessages = {
  idle: '',
  parsing: '正在解析简历文档结构...',
  extracting: 'AI 正在分析简历内容...',
  completed: '简历分析完成！',
  failed: '简历分析失败，请重试',
}

const stageMessage = computed(() => stageMessages[props.stage] || '')
const isActive = computed(() => props.stage === 'parsing' || props.stage === 'extracting')
const hasStats = computed(
  () => props.stats.skills > 0 || props.stats.projects > 0 || props.stats.experience > 0,
)

// Pseudo-progress based on time elapsed
const progressPercent = ref(0)
let timer = null
const startTime = ref(null)

const startProgress = () => {
  stopProgress()
  progressPercent.value = 0
  startTime.value = Date.now()
  timer = setInterval(() => {
    if (!startTime.value) return
    const elapsed = (Date.now() - startTime.value) / 1000
    // Ease-out curve: reaches ~90% at 30s, asymptotically approaches 95%
    const target = 95 * (1 - Math.exp(-elapsed / 12))
    progressPercent.value = Math.min(target, 95)
  }, 200)
}

const stopProgress = () => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(
  () => props.stage,
  (newStage) => {
    if (newStage === 'parsing' || newStage === 'extracting') {
      if (!timer) startProgress()
    } else if (newStage === 'completed') {
      stopProgress()
      progressPercent.value = 100
    } else if (newStage === 'failed') {
      stopProgress()
    } else {
      stopProgress()
      progressPercent.value = 0
    }
  },
  { immediate: true },
)

onMounted(() => {
  if (isActive.value) startProgress()
})

onBeforeUnmount(() => {
  stopProgress()
})
</script>

<style lang="less" scoped>
.resume-extracting {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px 16px;
  background: linear-gradient(135deg, var(--main-50) 0%, var(--gray-25) 50%, var(--main-30) 100%);
  background-size: 200% 200%;
  animation: bgShift 8s ease-in-out infinite;
  border-radius: 12px;
}

@keyframes bgShift {
  0%,
  100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

.resume-extracting__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 36px 40px;
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  min-width: 360px;
}

/* Header */
.resume-extracting__header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.resume-extracting__icon {
  color: var(--main-color);
}

.resume-extracting__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-900);
}

/* Document scanning animation */
.resume-extracting__animation {
  position: relative;
  width: 80px;
  height: 80px;
}

.doc-stack {
  position: relative;
  width: 100%;
  height: 100%;
}

.doc {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 52px;
  border-radius: 6px;
  color: var(--main-color);
}

.doc--back {
  top: 0;
  left: 0;
  background: var(--main-50);
  border: 1px solid var(--main-200);
  opacity: 0.5;
  transform: rotate(-6deg);
}

.doc--mid {
  top: 4px;
  left: 18px;
  background: var(--main-100);
  border: 1px solid var(--main-200);
  opacity: 0.7;
  transform: rotate(3deg);
}

.doc--front {
  top: 16px;
  left: 28px;
  background: var(--main-50);
  border: 1.5px solid var(--main-300);
  z-index: 1;
  overflow: hidden;
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--main-color), transparent);
  animation: scanMove 2s ease-in-out infinite;
  box-shadow: 0 0 8px rgba(55, 129, 207, 0.4);
}

@keyframes scanMove {
  0% {
    top: 0;
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    top: calc(100% - 2px);
    opacity: 0;
  }
}

/* Progress bar */
.resume-extracting__progress {
  width: 100%;
  height: 4px;
  background: var(--gray-100);
  border-radius: 2px;
  overflow: hidden;
}

.resume-extracting__progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--main-color), var(--main-bright));
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* Stage message */
.resume-extracting__stage {
  display: flex;
  align-items: center;
  gap: 6px;
}

.resume-extracting__spinner {
  color: var(--main-color);
  animation: spin 1s linear infinite;
}

.resume-extracting__check {
  color: var(--color-success-500);
}

.resume-extracting__error {
  color: var(--color-error-500);
}

.resume-extracting__message {
  font-size: 14px;
  color: var(--gray-700);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Stats */
.resume-extracting__stats {
  display: flex;
  align-items: center;
  gap: 8px;
}

.resume-extracting__stat {
  font-size: 12px;
  color: var(--gray-500);
}

.resume-extracting__stat-divider {
  font-size: 10px;
  color: var(--gray-300);
}
</style>
