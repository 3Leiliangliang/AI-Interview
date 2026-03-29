<template>
  <div class="match-result-panel">
    <!-- Overall Score Ring -->
    <div class="score-ring-section">
      <div class="score-ring">
        <svg viewBox="0 0 120 120" class="ring-svg">
          <circle cx="60" cy="60" r="52" fill="none" stroke="var(--bg-secondary, #f0f0f0)" stroke-width="8" />
          <circle
            cx="60" cy="60" r="52" fill="none"
            :stroke="scoreColor"
            stroke-width="8"
            stroke-linecap="round"
            :stroke-dasharray="circumference"
            :stroke-dashoffset="animatedDashOffset"
            transform="rotate(-90 60 60)"
            class="ring-progress"
          />
        </svg>
        <div class="score-text">
          <span class="score-value">{{ animatedScore }}</span>
          <span class="score-label">综合匹配</span>
        </div>
      </div>
      <div class="score-summary" v-if="matchResult.summary">{{ matchResult.summary }}</div>
    </div>

    <!-- Radar Chart -->
    <div class="section-card radar-section">
      <div class="section-title">
        <Target :size="16" />
        多维匹配分析
      </div>
      <div ref="radarChartRef" class="radar-chart"></div>
    </div>

    <!-- Skill Match -->
    <div class="section-card" v-if="matchResult.skill_match">
      <div class="section-title">
        <Target :size="16" />
        技能匹配 ({{ matchResult.skill_match.matched_count }}/{{ matchResult.skill_match.total_count }})
      </div>
      <div class="skill-tags" v-if="matchResult.skill_match.matched?.length">
        <div class="tag-group">
          <span class="tag-group-label">已匹配</span>
          <a-tag v-for="skill in matchResult.skill_match.matched" :key="skill" color="green">{{ skill }}</a-tag>
        </div>
      </div>
      <div class="skill-tags" v-if="matchResult.skill_match.missing?.length">
        <div class="tag-group">
          <span class="tag-group-label">缺失技能</span>
          <a-tag v-for="skill in matchResult.skill_match.missing" :key="skill" color="red">{{ skill }}</a-tag>
        </div>
      </div>
    </div>

    <!-- Experience Match -->
    <div class="section-card" v-if="matchResult.experience_match">
      <div class="section-title">
        <Briefcase :size="16" />
        经验匹配
        <a-tag :color="matchResult.experience_match.years_match ? 'green' : 'orange'" class="match-tag">
          {{ matchResult.experience_match.years_match ? '年限达标' : '年限不足' }}
        </a-tag>
      </div>
      <div class="exp-score-bar">
        <div class="bar-track">
          <div class="bar-fill exp-fill" :style="{ width: matchResult.experience_match.score + '%' }"></div>
        </div>
        <span class="bar-value">{{ matchResult.experience_match.score?.toFixed(1) }}分</span>
      </div>
      <div v-if="matchResult.experience_match.details?.length" class="detail-list">
        <div v-for="(detail, i) in matchResult.experience_match.details" :key="i" class="detail-item">{{ detail }}</div>
      </div>
    </div>

    <!-- Education Match -->
    <div class="section-card" v-if="matchResult.education_match">
      <div class="section-title">
        <GraduationCap :size="16" />
        教育匹配
        <a-tag :color="matchResult.education_match.meets_requirement ? 'green' : 'orange'" class="match-tag">
          {{ matchResult.education_match.meets_requirement ? '满足要求' : '未达标' }}
        </a-tag>
      </div>
      <div class="exp-score-bar">
        <div class="bar-track">
          <div class="bar-fill edu-fill" :style="{ width: matchResult.education_match.score + '%' }"></div>
        </div>
        <span class="bar-value">{{ matchResult.education_match.score?.toFixed(1) }}分</span>
      </div>
    </div>

    <!-- Strengths -->
    <div class="section-card" v-if="strengths.length">
      <div class="section-title strengths-title">
        <TrendingUp :size="16" />
        优势分析
      </div>
      <div class="strength-list">
        <div v-for="(s, i) in strengths" :key="i" class="strength-item">
          <span class="strength-bullet"></span>
          {{ s }}
        </div>
      </div>
    </div>

    <!-- Risk Points -->
    <div class="section-card" v-if="matchResult.risk_points?.length">
      <div class="section-title risk-title">
        <AlertTriangle :size="16" />
        风险提示
      </div>
      <div class="risk-list">
        <div v-for="(risk, i) in matchResult.risk_points" :key="i" class="risk-item">{{ risk }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Target, Briefcase, GraduationCap, TrendingUp, AlertTriangle } from 'lucide-vue-next'

const props = defineProps({
  matchResult: { type: Object, required: true }
})

const radarChartRef = ref(null)
let chartInstance = null
let animFrameId = null

// Animated score
const animatedScore = ref(0)
const circumference = 2 * Math.PI * 52 // ~326.7

const scoreColor = computed(() => {
  const s = props.matchResult.overall_score || 0
  if (s >= 80) return '#52c41a'
  if (s >= 60) return '#1890ff'
  if (s >= 40) return '#faad14'
  return '#ff4d4f'
})

const animatedDashOffset = computed(() => {
  const progress = animatedScore.value / 100
  return circumference * (1 - progress)
})

const strengths = computed(() => {
  const matched = props.matchResult.skill_match?.matched || []
  if (matched.length === 0) return []
  const items = []
  if (matched.length >= 5) items.push(`技能覆盖广泛，匹配 ${matched.length} 项核心技能`)
  if (props.matchResult.experience_match?.years_match) items.push('工作经验年限满足岗位要求')
  if (props.matchResult.education_match?.meets_requirement) items.push('学历背景符合岗位要求')
  if (props.matchResult.experience_match?.project_relevance >= 70) items.push('项目经历与岗位高度相关')
  if (matched.length > 0 && matched.length < 5) items.push(`具备 ${matched.slice(0, 3).join('、')} 等关键技能`)
  return items
})

function animateScore() {
  if (animFrameId) cancelAnimationFrame(animFrameId)
  const target = Math.round(props.matchResult.overall_score || 0)
  const start = animatedScore.value
  const diff = target - start
  const duration = 800
  const startTime = performance.now()
  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1)
    // easeOutCubic
    const eased = 1 - Math.pow(1 - progress, 3)
    animatedScore.value = Math.round(start + diff * eased)
    if (progress < 1) {
      animFrameId = requestAnimationFrame(step)
    } else {
      animFrameId = null
    }
  }
  animFrameId = requestAnimationFrame(step)
}

function initRadarChart() {
  if (!radarChartRef.value) return
  chartInstance = echarts.init(radarChartRef.value)

  const sm = props.matchResult.skill_match?.score || 0
  const em = props.matchResult.experience_match?.score || 0
  const pr = props.matchResult.experience_match?.project_relevance || 0
  const edu = props.matchResult.education_match?.score || 0
  const overall = props.matchResult.overall_score || 0

  const option = {
    grid: {
      left: 0, right: 0, top: 0, bottom: 0,
      containLabel: true
    },
    radar: {
      indicator: [
        { name: '技能匹配', max: 100 },
        { name: '经验匹配', max: 100 },
        { name: '项目相关度', max: 100 },
        { name: '教育匹配', max: 100 },
        { name: '综合评分', max: 100 }
      ],
      center: ['50%', '50%'],
      radius: '70%',
      shape: 'circle',
      splitNumber: 4,
      nameGap: 8,
      axisName: {
        color: '#555',
        fontSize: 13,
        fontWeight: 600
      },
      splitLine: { lineStyle: { color: '#e8e8e8' } },
      splitArea: {
        show: true,
        areaStyle: { color: ['rgba(24,144,255,0.02)', 'rgba(24,144,255,0.04)'] }
      },
      axisLine: { lineStyle: { color: '#e8e8e8' } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: [sm, em, pr, edu, overall],
        areaStyle: { color: 'rgba(24, 144, 255, 0.15)' },
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
        symbol: 'circle',
        symbolSize: 6
      }],
      animationDuration: 1000,
      animationEasing: 'elasticOut'
    }]
  }
  chartInstance.setOption(option)
}

watch(() => props.matchResult, () => {
  nextTick(() => {
    animateScore()
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
    setTimeout(() => {
      initRadarChart()
    }, 300)
  })
}, { deep: true })

onMounted(() => {
  nextTick(() => {
    animateScore()
    // 延迟初始化雷达图，确保 Drawer 动画完成且容器尺寸正确
    setTimeout(() => {
      initRadarChart()
    }, 300)
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (animFrameId) cancelAnimationFrame(animFrameId)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

const handleResize = () => {
  chartInstance?.resize()
}
</script>

<style lang="less" scoped>
.match-result-panel {
  padding: 16px 0;
  max-height: calc(100vh - 56px);
  overflow-y: auto;
}

.score-ring-section {
  text-align: center;
  margin-bottom: 20px;
}

.score-ring {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 0 auto 8px;
}

.ring-svg {
  width: 100%;
  height: 100%;
}

.ring-progress {
  transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.score-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.score-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.score-label {
  display: block;
  font-size: 12px;
  color: #999;
}

.score-summary {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}

.radar-chart {
  width: 100%;
  height: 400px;
  min-height: 400px;
}

.radar-section {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 12px 0;
}

.section-card {
  background: var(--bg-secondary, #fafafa);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.match-tag {
  margin-left: auto;
  font-size: 11px;
}

.skill-tags {
  margin-bottom: 6px;
}

.tag-group {
  margin-bottom: 6px;
}

.tag-group-label {
  font-size: 12px;
  color: #999;
  margin-right: 6px;
}

:deep(.ant-tag) {
  margin-bottom: 4px;
  font-size: 12px;
}

.exp-score-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.bar-track {
  flex: 1;
  height: 6px;
  background: #e8e8e8;
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}

.exp-fill {
  background: linear-gradient(90deg, #1890ff, #40a9ff);
}

.edu-fill {
  background: linear-gradient(90deg, #722ed1, #9254de);
}

.bar-value {
  font-size: 13px;
  font-weight: 600;
  min-width: 48px;
  text-align: right;
}

.detail-list {
  margin-top: 4px;
}

.detail-item {
  font-size: 12px;
  color: #666;
  padding: 2px 0;
}

.strengths-title {
  color: #389e0d;
}

.risk-title {
  color: #d4380d;
}

.strength-list, .risk-list {
  padding-left: 4px;
}

.strength-item {
  font-size: 13px;
  color: #555;
  padding: 3px 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.strength-bullet {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  flex-shrink: 0;
}

.risk-item {
  font-size: 13px;
  color: #666;
  padding: 3px 0;
  padding-left: 14px;
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 10px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ff4d4f;
  }
}
</style>
