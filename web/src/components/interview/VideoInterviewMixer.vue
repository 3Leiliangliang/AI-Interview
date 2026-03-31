<template>
  <div class="video-interview-mixer">
    <div class="video-wrapper">
      <VideoCapturePanel
        :video-ref="videoRef"
        :is-streaming="isStreaming"
        :fps="fps"
        :capture-error="captureError"
        :status="status"
        @video-ready="onVideoReady"
      />
      <VideoAnalysisCard
        :current-emotion="currentEmotion"
        :emotion-scores="emotionScores"
        :posture="posture"
        :posture-score="postureScore"
        :gaze-direction="gazeDirection"
        :attention-score="attentionScore"
        :alerts="alerts"
      />
    </div>
  </div>
</template>

<script setup>
import VideoCapturePanel from './VideoCapturePanel.vue'
import VideoAnalysisCard from './VideoAnalysisCard.vue'

const props = defineProps({
  // capture
  videoRef: { type: Object, default: null },
  isStreaming: { type: Boolean, default: false },
  fps: { type: Number, default: 0 },
  captureError: { type: String, default: null },
  // store
  status: { type: String, default: 'inactive' },
  currentEmotion: { type: String, default: 'neutral' },
  emotionScores: { type: Object, default: () => ({}) },
  posture: { type: String, default: 'upright' },
  postureScore: { type: Number, default: 100 },
  gazeDirection: { type: String, default: 'center' },
  attentionScore: { type: Number, default: 100 },
  alerts: { type: Array, default: () => [] },
})

const emit = defineEmits(['video-ready'])

function onVideoReady(el) {
  emit('video-ready', el)
}
</script>

<style lang="less" scoped>
.video-interview-mixer {
  flex-shrink: 0;
  width: 320px;
}

.video-wrapper {
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  overflow: hidden;
  background: var(--gray-900);
}
</style>
