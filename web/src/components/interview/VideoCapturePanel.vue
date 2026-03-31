<template>
  <div class="video-capture-panel">
    <!-- 状态指示灯 -->
    <div class="status-indicator">
      <span class="status-dot" :class="statusClass"></span>
      <span class="status-text">{{ statusText }}</span>
    </div>

    <!-- FPS -->
    <div class="fps-badge" v-if="fps > 0">{{ fps }} FPS</div>

    <!-- 视频流 -->
    <video
      ref="videoElement"
      class="video-element"
      autoplay
      playsinline
      muted
      v-show="isStreaming"
    ></video>

    <!-- 无摄像头提示 -->
    <div class="no-camera-hint" v-if="!isStreaming">
      <VideoIcon :size="32" />
      <span>{{ captureError || '请允许摄像头权限' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { Video as VideoIcon } from 'lucide-vue-next'

const props = defineProps({
  /** useVideoCapture 返回的 videoRef（外部绑定用） */
  videoRef: { type: Object, default: null },
  isStreaming: { type: Boolean, default: false },
  fps: { type: Number, default: 0 },
  captureError: { type: String, default: null },
  /** store.status: 'active' | 'degraded' | 'inactive' */
  status: { type: String, default: 'inactive' },
})

const emit = defineEmits(['video-ready'])

const videoElement = ref(null)

const statusClass = computed(() => {
  if (!props.isStreaming) return 'status-off'
  if (props.status === 'active') return 'status-active'
  if (props.status === 'degraded') return 'status-degraded'
  return 'status-off'
})

const statusText = computed(() => {
  if (!props.isStreaming) return '未连接'
  if (props.status === 'active') return '正常'
  if (props.status === 'degraded') return '降级'
  return '异常'
})

// 将内部 video 元素同步给外部 videoRef
watch(videoElement, (el) => {
  if (el && props.videoRef) {
    props.videoRef.value = el
    emit('video-ready', el)
  }
})

onUnmounted(() => {
  if (videoElement.value) {
    videoElement.value.srcObject = null
  }
})
</script>

<style lang="less" scoped>
.video-capture-panel {
  position: relative;
  width: 100%;
  max-width: 320px;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: var(--gray-900);
}

.video-element {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.status-indicator {
  position: absolute;
  top: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.55);
  z-index: 2;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-active {
  background: var(--color-success-500);
}

.status-degraded {
  background: var(--color-warning-500);
}

.status-off {
  background: var(--color-error-500);
}

.status-text {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1;
}

.fps-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: rgba(255, 255, 255, 0.75);
  font-size: 10px;
  font-family: monospace;
  z-index: 2;
}

.no-camera-hint {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--gray-400);
  font-size: 13px;
}
</style>
