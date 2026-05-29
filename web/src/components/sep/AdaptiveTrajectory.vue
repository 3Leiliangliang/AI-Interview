<template>
  <div class="adaptive-trajectory">
    <div class="trajectory-header">
      <span class="trajectory-title">能力估计 θ 走势</span>
      <span class="trajectory-hint">纵轴为当前能力估计 θ，点的大小为题目难度</span>
    </div>
    <div ref="chartEl" class="trajectory-chart" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  trajectory: { type: Array, default: () => [] },
  questions: { type: Array, default: () => [] },
})

const chartEl = ref(null)
let chart = null
// Resolve real CSS variable values once at setup. ECharts canvas
// cannot consume `var(--...)` strings, so we must read them here.
const palette = {
  primary: '#4f9fec',
  axis: '#bdbfbf',
  text: '#697070',
  split: '#e4e6e6',
}

function readCssVars() {
  if (typeof window === 'undefined') return
  const styles = getComputedStyle(document.documentElement)
  const read = (name, fallback) => {
    const v = styles.getPropertyValue(name).trim()
    return v || fallback
  }
  palette.primary = read('--main-500', palette.primary)
  palette.axis = read('--gray-400', palette.axis)
  palette.text = read('--gray-600', palette.text)
  palette.split = read('--gray-200', palette.split)
}

function onResize() {
  chart?.resize()
}

function buildOption() {
  const labels = ['起始', ...props.questions.map((q, i) => `Q${i + 1}: ${q.concept ?? ''}`)]
  const values = props.trajectory.map((v, i) => ({
    value: v,
    symbolSize: i === 0 ? 8 : Math.round((props.questions[i - 1]?.difficulty ?? 0.5) * 24) + 4,
  }))

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        const qIdx = p.dataIndex - 1
        const q = props.questions[qIdx]
        const diffText = q && q.difficulty !== undefined && q.difficulty !== null ? `难度 ${q.difficulty}` : '初始值'
        return `${p.name}<br/>θ = ${p.value}<br/>${diffText}`
      },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 40 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { fontSize: 11, color: palette.text, rotate: props.questions.length > 5 ? 20 : 0 },
      axisLine: { lineStyle: { color: palette.axis } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      name: 'θ',
      nameTextStyle: { fontSize: 11, color: palette.text },
      axisLabel: { color: palette.text },
      splitLine: { lineStyle: { type: 'dashed', color: palette.split } },
    },
    series: [
      {
        type: 'line',
        data: values,
        smooth: 0.4,
        lineStyle: { width: 2, color: palette.primary },
        itemStyle: { color: palette.primary },
        markLine: {
          silent: true,
          data: [{ yAxis: 0.5, lineStyle: { type: 'dashed', color: palette.axis } }],
          label: { formatter: '平均水平', color: palette.text },
        },
      },
    ],
  }
}

watch(
  () => [props.trajectory, props.questions],
  () => {
    chart?.setOption(buildOption(), { notMerge: true })
  },
  { deep: true },
)

onMounted(() => {
  if (!chartEl.value) return
  readCssVars()
  chart = echarts.init(chartEl.value)
  chart.setOption(buildOption(), { notMerge: true })
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.adaptive-trajectory {
  width: 100%;
}

.trajectory-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}

.trajectory-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--gray-1000);
}

.trajectory-hint {
  font-size: 11px;
  color: var(--gray-500);
}

.trajectory-chart {
  height: 200px;
  width: 100%;
}
</style>
