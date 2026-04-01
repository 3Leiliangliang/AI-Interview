import { ref, computed, watch, onUnmounted } from 'vue'

/**
 * 视频捕获 composable — 管理摄像头流的获取、释放与帧捕获
 * @returns {{
 *   isStreaming: import('vue').Ref<boolean>,
 *   videoRef: import('vue').Ref<HTMLVideoElement|null>,
 *   stream: import('vue').Ref<MediaStream|null>,
 *   error: import('vue').Ref<string|null>,
 *   fps: import('vue').Ref<number>,
 *   resolution: import('vue').Ref<{width:number,height:number}>,
 *   isSupported: import('vue').ComputedRef<boolean>,
 *   availableDevices: import('vue').ComputedRef<MediaDeviceInfo[]>,
 *   start: (options?: {deviceId?:string,facingMode?:string}) => Promise<void>,
 *   stop: () => void,
 *   captureFrame: (canvas?: HTMLCanvasElement) => {canvas:HTMLCanvasElement, ctx:CanvasRenderingContext2D}|null,
 *   getFrameBitmap: () => Promise<ImageBitmap|null>
 * }}
 */
export function useVideoCapture() {
  const isStreaming = ref(false)
  const videoRef = ref(null)
  const stream = ref(null)
  const error = ref(null)
  const fps = ref(0)
  const resolution = ref({ width: 0, height: 0 })

  let fpsFrameCount = 0
  let fpsTimerId = null
  let devicesCache = ref([])

  const isSupported = computed(
    () => typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia
  )

  const availableDevices = computed(() => devicesCache.value.filter((d) => d.kind === 'videoinput'))

  /**
   * 枚举可用的视频输入设备
   */
  async function enumerateDevices() {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      devicesCache.value = devices
    } catch {
      devicesCache.value = []
    }
  }

  /**
   * 请求摄像头流，支持分辨率降级
   * @param {{ deviceId?: string, facingMode?: string }} options
   */
  async function start(options = {}) {
    error.value = null

    if (!isSupported.value) {
      error.value = '浏览器不支持 getUserMedia'
      return
    }

    // 若已有流先停止
    if (isStreaming.value) {
      stop()
    }

    const { deviceId, facingMode = 'user' } = options

    /** @param {number} w @param {number} h @returns {MediaStreamConstraints} */
    const buildConstraints = (w, h) => ({
      video: deviceId
        ? { deviceId: { exact: deviceId }, width: { ideal: w }, height: { ideal: h } }
        : { facingMode, width: { ideal: w }, height: { ideal: h } }
    })

    let mediaStream = null

    // 先尝试 720p
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia(buildConstraints(1280, 720))
    } catch {
      // 降级到 480p
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia(buildConstraints(640, 480))
      } catch (err) {
        const name = err instanceof DOMException ? err.name : ''
        if (name === 'NotAllowedError') {
          error.value = '摄像头权限被拒绝'
        } else if (name === 'NotFoundError') {
          error.value = '未找到可用的摄像头设备'
        } else {
          error.value = `无法获取摄像头流: ${err instanceof Error ? err.message : String(err)}`
        }
        return
      }
    }

    stream.value = mediaStream

    // 绑定到 video 元素
    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream
      await videoRef.value.play()
      // 读取实际分辨率
      const vw = videoRef.value.videoWidth || 0
      const vh = videoRef.value.videoHeight || 0
      resolution.value = { width: vw, height: vh }
    }

    isStreaming.value = true
    startFpsMonitor()
    await enumerateDevices()
  }

  /**
   * 停止摄像头并释放资源
   */
  function stop() {
    stopFpsMonitor()

    if (stream.value) {
      for (const track of stream.value.getTracks()) {
        track.stop()
      }
      stream.value = null
    }

    if (videoRef.value) {
      videoRef.value.srcObject = null
    }

    isStreaming.value = false
    resolution.value = { width: 0, height: 0 }
    fps.value = 0
  }

  /**
   * 捕获当前视频帧到 Canvas
   * @param {HTMLCanvasElement} [canvas] 可选复用的 canvas
   * @returns {{ canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D } | null}
   */
  function captureFrame(canvas) {
    const video = videoRef.value
    if (!video || !isStreaming.value) return null

    const w = video.videoWidth
    const h = video.videoHeight
    if (!w || !h) return null

    const cvs = canvas || document.createElement('canvas')
    cvs.width = w
    cvs.height = h

    const ctx = cvs.getContext('2d')
    ctx.drawImage(video, 0, 0, w, h)

    return { canvas: cvs, ctx }
  }

  /**
   * 从当前视频帧创建 ImageBitmap（适用于 MediaPipe 等分析场景）
   * @returns {Promise<ImageBitmap|null>}
   */
  async function getFrameBitmap() {
    const video = videoRef.value
    if (!video || !isStreaming.value) return null

    const w = video.videoWidth
    const h = video.videoHeight
    if (!w || !h) return null

    try {
      return await createImageBitmap(video, 0, 0, w, h)
    } catch {
      // 回退：通过 canvas 中转
      const result = captureFrame()
      if (!result) return null
      try {
        return await createImageBitmap(result.canvas)
      } catch {
        return null
      }
    }
  }

  // 当 videoRef 延迟挂载时，自动绑定已有的摄像头流
  watch(videoRef, async (el) => {
    if (el && stream.value && !el.srcObject) {
      el.srcObject = stream.value
      try {
        await el.play()
        const vw = el.videoWidth || 0
        const vh = el.videoHeight || 0
        resolution.value = { width: vw, height: vh }
      } catch {
        // autoplay 可能被浏览器阻止
      }
    }
  })

  // ---- FPS 监控 ----

  function startFpsMonitor() {
    stopFpsMonitor()
    fpsFrameCount = 0

    const countFrame = () => {
      fpsFrameCount++
      if (isStreaming.value) {
        fpsTimerId = requestAnimationFrame(countFrame)
      }
    }
    fpsTimerId = requestAnimationFrame(countFrame)

    // 每秒统计一次帧数
    fps._interval = setInterval(() => {
      fps.value = fpsFrameCount
      fpsFrameCount = 0
    }, 1000)
  }

  function stopFpsMonitor() {
    if (fpsTimerId != null) {
      cancelAnimationFrame(fpsTimerId)
      fpsTimerId = null
    }
    if (fps._interval) {
      clearInterval(fps._interval)
      fps._interval = null
    }
  }

  // 组件卸载时自动清理
  onUnmounted(() => {
    stop()
  })

  return {
    isStreaming,
    videoRef,
    stream,
    error,
    fps,
    resolution,
    isSupported,
    availableDevices,
    start,
    stop,
    captureFrame,
    getFrameBitmap
  }
}
