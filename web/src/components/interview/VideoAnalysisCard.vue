<template>
  <div class="video-analysis-card">
    <!-- 表情指示器 -->
    <div class="analysis-section">
      <span class="section-label">表情</span>
      <div class="emotion-row">
        <span class="emotion-tag">{{ emotionLabel }}</span>
        <div class="score-bar-track">
          <div
            class="score-bar-fill emotion-fill"
            :style="{ width: emotionIntensity + '%' }"
          ></div>
        </div>
        <span class="score-value">{{ Math.round(emotionIntensity * 100) }}%</span>
      </div>
    </div>

    <!-- 姿态评分 -->
    <div class="analysis-section">
      <span class="section-label">姿态</span>
      <div class="metric-row">
        <Progress
          type="circle"
          :percent="postureScore"
          :size="36"
          :stroke-width="8"
          :stroke-color="postureColor"
          trail-color="rgba(255,255,255,0.1)"
        />
        <div class="metric-detail">
          <span class="detail-item">{{ postureLabel }}</span>
          <span class="detail-item">{{ gazeDirection }}</span>
        </div>
      </div>
    </div>

    <!-- 注意力评分 -->
    <div class="analysis-section">
      <span class="section-label">注意力</span>
      <div class="metric-row">
        <Progress
          :percent="attentionScore"
          :size="'100%'"
          :stroke-width="6"
          :stroke-color="attentionColor"
          trail-color="rgba(255,255,255,0.1)"
          :show-info="false"
        />
        <span class="score-value">{{ attentionScore }}分</span>
      </div>
    </div>

    <!-- 告警列表 -->
    <div class="alerts-section" v-if="alerts.length > 0">
      <TransitionGroup name="alert-fade">
        <div
          v-for="alert in recentAlerts"
          :key="alert.time"
          class="alert-item"
        >
          <AlertTriangle :size="12" class="alert-icon" />
          <span class="alert-text">{{ alert.message }}</span>
          <span class="alert-time">{{ formatTime(alert.time) }}</span>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Progress } from 'ant-design-vue'
import { AlertTriangle } from 'lucide-vue-next'

const props = defineProps({
  currentEmotion: { type: String, default: 'neutral' },
  emotionScores: { type: Object, default: () => ({}) },
  posture: { type: String, default: 'upright' },
  postureScore: { type: Number, default: 100 },
  gazeDirection: { type: String, default: 'center' },
  attentionScore: { type: Number, default: 100 },
  alerts: { type: Array, default: () => [] },
})

const EMOTION_LABELS = {
  happy: '开心',
  sad: '悲伤',
  angry: '愤怒',
  neutral: '平静',
  fear: '恐惧',
  disgust: '厌恶',
  surprise: '惊讶',
}

const GAZE_LABELS = {
  center: '居中',
  left: '偏左',
  right: '偏右',
  up: '偏上',
  down: '偏下',
}

const POSTURE_LABELS = {
  upright: '端正',
  leaning_forward: '前倾',
  leaning_back: '后仰',
  head_tilt: '歪头',
  slouching: '驼背',
}

const emotionLabel = computed(() => EMOTION_LABELS[props.currentEmotion] || props.currentEmotion)

const emotionIntensity = computed(() => {
  if (!props.emotionScores) return 0
  const dominant = props.emotionScores[props.currentEmotion]
  return typeof dominant === 'number' ? dominant : 0
})

const postureLabel = computed(() => POSTURE_LABELS[props.posture] || '端正')

const postureColor = computed(() => {
  if (props.postureScore >= 80) return '#52c41a'
  if (props.postureScore >= 60) return '#faad14'
  return '#ff4d4f'
})

const gazeDirection = computed(() => GAZE_LABELS[props.gazeDirection] || props.gazeDirection)

const attentionColor = computed(() => {
  if (props.attentionScore >= 70) return '#52c41a'
  if (props.attentionScore >= 50) return '#faad14'
  return '#ff4d4f'
})

const recentAlerts = computed(() => props.alerts.slice(-10))

function formatTime(timestamp) {
  const d = new Date(timestamp)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${h}:${m}:${s}`
}
</script>

<style lang="less" scoped>
.video-analysis-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 0 0 8px 8px;
  color: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  max-width: 320px;
}

.analysis-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-label {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.emotion-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.emotion-tag {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 11px;
}

.score-bar-track {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.emotion-fill {
  background: var(--main-500);
}

.score-value {
  flex-shrink: 0;
  width: 32px;
  text-align: right;
  font-size: 11px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.7);
}

.metric-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-detail {
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-size: 11px;
}

.detail-item {
  color: rgba(255, 255, 255, 0.65);
}

.alerts-section {
  display: flex;
  flex-direction: column;
  gap: 3px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 6px;
  max-height: 180px;
  overflow-y: auto;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-warning-100);
}

.alert-icon {
  flex-shrink: 0;
  color: var(--color-warning-500);
}

.alert-text {
  line-height: 1.3;
}

.alert-time {
  flex-shrink: 0;
  margin-left: auto;
  font-size: 10px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.35);
}

.alert-fade-enter-active,
.alert-fade-leave-active {
  transition: opacity 0.3s ease;
}

.alert-fade-enter-from,
.alert-fade-leave-to {
  opacity: 0;
}
</style>
