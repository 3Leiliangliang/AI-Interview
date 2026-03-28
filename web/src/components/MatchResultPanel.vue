<template>
  <div class="match-result-panel">
    <!-- 整体评分 -->
    <div class="match-result-panel__header">
      <div class="match-result-panel__meta">
        <div class="match-result-panel__title">匹配分析结果</div>
        <div class="match-result-panel__tags">
          <span v-if="matchResult.summary" class="match-tag">{{ matchLevelText }}</span>
        </div>
      </div>
      <div v-if="matchResult.overall_score" class="match-result-panel__overall">
        <span class="match-result-panel__number">{{ matchResult.overall_score }}</span>
        <span class="match-result-panel__unit">/100</span>
      </div>
    </div>

    <!-- 雷达图和详细分数 -->
    <div class="match-result-panel__content">
      <!-- 雷达图 -->
      <div class="radar-section">
        <div ref="radarChartRef" class="radar-chart"></div>
      </div>

      <!-- 详细分数 -->
      <div class="detail-section">
        <!-- 技能匹配 -->
        <div class="score-card">
          <div class="score-card__header">
            <span class="score-card__title">技能匹配</span>
            <span class="score-card__score">{{ matchResult.skill_match?.score || 0 }}/100</span>
          </div>
          <div class="skill-tags">
            <span
              v-for="skill in matchResult.skill_match?.matched || []"
              :key="skill"
              class="skill-tag skill-tag--matched"
            >
              <Check :size="12" />
              {{ skill }}
            </span>
            <span
              v-for="skill in matchResult.skill_match?.missing || []"
              :key="skill"
              class="skill-tag skill-tag--missing"
            >
              <X :size="12" />
              {{ skill }}
            </span>
          </div>
          <div v-if="matchResult.skill_match" class="skill-count">
            已匹配 {{ matchResult.skill_match.matched_count || 0 }} / {{ matchResult.skill_match.total_count || 0 }} 项技能
          </div>
        </div>

        <!-- 经验匹配 -->
        <div class="score-card">
          <div class="score-card__header">
            <span class="score-card__title">经验匹配</span>
            <span class="score-card__score">{{ matchResult.experience_match?.score || 0 }}/100</span>
          </div>
          <ul v-if="matchResult.experience_match?.details?.length" class="experience-list">
            <li v-for="(detail, idx) in matchResult.experience_match.details" :key="idx">
              {{ detail }}
            </li>
          </ul>
          <div v-if="matchResult.experience_match?.years_match === false" class="risk-badge">
            工作年限不满足要求
          </div>
          <div v-else-if="matchResult.experience_match?.years_match === null" class="warning-badge">
            年限无法确定
          </div>
        </div>
      </div>
    </div>

    <!-- 风险点 -->
    <div v-if="matchResult.risk_points?.length" class="risk-section">
      <div class="section-title">
        <AlertTriangle :size="14" />
        风险点
      </div>
      <ul class="risk-list">
        <li v-for="(risk, idx) in matchResult.risk_points" :key="idx">{{ risk }}</li>
      </ul>
    </div>

    <!-- 摘要 -->
    <p v-if="matchResult.summary" class="match-result-panel__summary">{{ matchResult.summary }}</p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { Check, X, AlertTriangle } from 'lucide-vue-next'

const props = defineProps({
  matchResult: {
    type: Object,
    required: true,
    default: () => ({
      overall_score: 0,
      skill_match: {
        score: 0,
        matched: [],
        missing: [],
        matched_count: 0,
        total_count: 0,
      },
      experience_match: {
        score: 0,
        years_match: true,
        project_relevance: 0,
        details: [],
      },
      risk_points: [],
      summary: '',
    }),
  },
})

const radarChartRef = ref(null)
let chartInstance = null

const matchLevelText = computed(() => {
  const score = props.matchResult.overall_score || 0
  if (score >= 80) return '优秀'
  if (score >= 60) return '良好'
  if (score >= 40) return '一般'
  return '较差'
})

const initChart = () => {
  if (!radarChartRef.value) return

  try {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }

    chartInstance = echarts.init(radarChartRef.value)
    const skillScore = props.matchResult.skill_match?.score || 0
    const expScore = props.matchResult.experience_match?.score || 0

    const option = {
      radar: {
        indicator: [
          { name: '技能匹配', max: 100 },
          { name: '经验匹配', max: 100 },
          { name: '项目相关度', max: 100 },
        ],
        radius: '60%',
        center: ['50%', '50%'],
        axisName: {
          color: '#666',
          fontSize: 12,
        },
        splitArea: {
          areaStyle: {
            color: ['rgba(0, 122, 255, 0.05)', 'rgba(0, 122, 255, 0.1)'],
          },
        },
        axisLine: {
          lineStyle: {
            color: '#ddd',
          },
        },
        splitLine: {
          lineStyle: {
            color: '#eee',
          },
        },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: [skillScore, expScore, props.matchResult.experience_match?.project_relevance || 0],
              name: '匹配度',
              symbol: 'circle',
              symbolSize: 6,
              lineStyle: {
                color: '#007AFF',
                width: 2,
              },
              areaStyle: {
                color: 'rgba(0, 122, 255, 0.2)',
              },
              itemStyle: {
                color: '#007AFF',
              },
            },
          ],
        },
      ],
    }

    chartInstance.setOption(option)
  } catch (error) {
    console.error('初始化雷达图失败:', error)
  }
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

watch(
  () => props.matchResult,
  () => {
    initChart()
  },
  { deep: true },
)
</script>

<style lang="less" scoped>
.match-result-panel {
  margin: 14px 0 8px;
  padding: 20px;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-25);
}

.match-result-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.match-result-panel__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--gray-900);
}

.match-result-panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.match-tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-700);
  font-size: 12px;
}

.match-result-panel__overall {
  display: flex;
  align-items: baseline;
  gap: 2px;
  white-space: nowrap;
  color: var(--main-color);
}

.match-result-panel__number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.match-result-panel__unit {
  font-size: 13px;
  color: var(--gray-500);
}

.match-result-panel__content {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
  margin-top: 18px;
}

.radar-section {
  display: flex;
  align-items: center;
  justify-content: center;
}

.radar-chart {
  width: 300px;
  height: 300px;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-card {
  padding: 14px;
  border-radius: 10px;
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
}

.score-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.score-card__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.score-card__score {
  font-size: 16px;
  font-weight: 600;
  color: var(--main-color);
}

.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.skill-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
}

.skill-tag--matched {
  background: rgba(52, 199, 89, 0.1);
  color: #34c759;
}

.skill-tag--missing {
  background: rgba(255, 59, 48, 0.1);
  color: #ff3b30;
}

.skill-count {
  margin-top: 8px;
  font-size: 12px;
  color: var(--gray-500);
}

.experience-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--gray-700);

  li + li {
    margin-top: 6px;
  }
}

.risk-badge {
  display: inline-flex;
  align-items: center;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(255, 59, 48, 0.1);
  color: #ff3b30;
  font-size: 12px;
}

.warning-badge {
  display: inline-flex;
  align-items: center;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(255, 149, 0, 0.1);
  color: #ff9500;
  font-size: 12px;
}

.risk-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--gray-150);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #ff3b30;
}

.risk-list {
  margin: 0;
  padding-left: 18px;
  color: var(--gray-700);
  font-size: 13px;

  li + li {
    margin-top: 6px;
  }
}

.match-result-panel__summary {
  margin: 14px 0 0;
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.7;
}

@media (max-width: 640px) {
  .match-result-panel__content {
    grid-template-columns: 1fr;
  }

  .radar-chart {
    width: 260px;
    height: 260px;
    margin: 0 auto;
  }
}
</style>
