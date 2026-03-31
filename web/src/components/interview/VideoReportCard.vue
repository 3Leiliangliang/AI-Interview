<template>
  <div class="video-report-card">
    <div class="report-header" @click="expanded = !expanded">
      <span class="header-title">视频分析报告</span>
      <div class="header-right">
        <Tag v-if="report.has_data" :color="overallColor">{{ overallLabel }}</Tag>
        <DownOutlined :class="['expand-icon', { 'expand-icon-expanded': expanded }]" />
      </div>
    </div>

    <div v-if="!report.has_data" class="no-data">
      <span>暂无视频分析数据</span>
    </div>

    <template v-else>
      <!-- 评分概览 - 始终可见 -->
      <div class="scores-section">
        <div class="score-item" v-for="item in scoreItems" :key="item.key">
          <span class="score-label">{{ item.label }}</span>
          <Progress
            :percent="item.value"
            :stroke-color="item.color"
            :size="'small'"
            :stroke-width="6"
            trail-color="rgba(0, 0, 0, 0.06)"
          />
          <span class="score-value">{{ item.value }}</span>
        </div>
      </div>

      <!-- 可展开的详情区域 -->
      <Transition name="expand">
        <div v-if="expanded" class="detail-section">
          <!-- 整体印象 -->
          <div class="detail-block" v-if="report.overall_impression">
            <div class="detail-title">整体印象</div>
            <p class="detail-text">{{ report.overall_impression }}</p>
          </div>

          <!-- 各维度详细分析 -->
          <div class="detail-block" v-if="hasDimensionAnalysis">
            <div class="detail-title">维度分析</div>
            <div class="dimension-item" v-for="(text, key) in report.dimension_analysis" :key="key">
              <span class="dimension-tag">{{ dimensionLabels[key] || key }}</span>
              <span class="dimension-text">{{ text }}</span>
            </div>
          </div>

          <!-- 改进建议 -->
          <div class="detail-block" v-if="report.recommendations?.length">
            <div class="detail-title">改进建议</div>
            <ul class="recommendation-list">
              <li v-for="(rec, idx) in report.recommendations" :key="idx">{{ rec }}</li>
            </ul>
          </div>

          <!-- 优势总结 -->
          <div class="detail-block" v-if="report.strengths?.length">
            <div class="detail-title">优势总结</div>
            <ul class="strength-list">
              <li v-for="(s, idx) in report.strengths" :key="idx">{{ s }}</li>
            </ul>
          </div>

          <!-- 警告信息 -->
          <div class="detail-block" v-if="report.alerts?.length">
            <div class="detail-title">面试中的提醒</div>
            <div class="alert-item" v-for="(alert, idx) in report.alerts" :key="idx">
              <ExclamationCircleOutlined class="alert-icon" />
              <span>{{ alert.message }}</span>
            </div>
          </div>
        </div>
      </Transition>

      <div class="expand-toggle" @click="expanded = !expanded">
        {{ expanded ? '收起详情' : '查看详情' }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Progress, Tag } from 'ant-design-vue'
import { DownOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue'

const props = defineProps({
  report: {
    type: Object,
    default: () => ({ has_data: false, scores: {}, recommendations: [], strengths: [] }),
  },
})

const expanded = ref(false)

const dimensionLabels = {
  emotion: '情绪',
  posture: '姿态',
  attention: '注意力',
}

function getScoreColor(score) {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#ff4d4f'
}

const overallScore = computed(() => props.report.scores?.overall ?? 0)

const overallColor = computed(() => getScoreColor(overallScore.value))

const overallLabel = computed(() => {
  const s = overallScore.value
  if (s >= 85) return '优秀'
  if (s >= 70) return '良好'
  if (s >= 55) return '一般'
  return '待改善'
})

const scoreItems = computed(() => {
  const scores = props.report.scores || {}
  return [
    { key: 'emotion_stability', label: '情绪稳定性', value: Math.round(scores.emotion_stability ?? 0), color: getScoreColor(scores.emotion_stability ?? 0) },
    { key: 'posture', label: '姿态评分', value: Math.round(scores.posture ?? 0), color: getScoreColor(scores.posture ?? 0) },
    { key: 'attention', label: '注意力评分', value: Math.round(scores.attention ?? 0), color: getScoreColor(scores.attention ?? 0) },
    { key: 'overall', label: '综合评分', value: Math.round(scores.overall ?? 0), color: getScoreColor(scores.overall ?? 0) },
  ]
})

const hasDimensionAnalysis = computed(() => {
  const da = props.report.dimension_analysis
  return da && Object.keys(da).length > 0
})
</script>

<style lang="less" scoped>
.video-report-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  overflow: hidden;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;

  &:hover {
    background: #fafafa;
  }
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.85);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-icon {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  transition: transform 0.2s ease;
}

.expand-icon-expanded {
  transform: rotate(180deg);
}

.no-data {
  padding: 24px 16px;
  text-align: center;
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
}

.scores-section {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-label {
  flex-shrink: 0;
  width: 80px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.score-item :deep(.ant-progress) {
  flex: 1;
}

.score-value {
  flex-shrink: 0;
  width: 32px;
  text-align: right;
  font-size: 13px;
  font-family: monospace;
  color: rgba(0, 0, 0, 0.65);
}

.detail-section {
  padding: 0 16px 8px;
  border-top: 1px solid #f0f0f0;
}

.detail-block {
  padding: 10px 0;
  border-bottom: 1px solid #f5f5f5;

  &:last-child {
    border-bottom: none;
  }
}

.detail-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.85);
  margin-bottom: 6px;
}

.detail-text {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.6;
  margin: 0;
}

.dimension-item {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.6;
}

.dimension-tag {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: 3px;
  background: #f0f0f0;
  font-size: 12px;
  line-height: 22px;
}

.recommendation-list,
.strength-list {
  margin: 0;
  padding-left: 16px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.8;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  margin-bottom: 4px;

  .alert-icon {
    flex-shrink: 0;
    color: #faad14;
    margin-top: 3px;
  }
}

.expand-toggle {
  padding: 8px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--main-500, #1890ff);
  cursor: pointer;
  border-top: 1px solid #f0f0f0;

  &:hover {
    background: #fafafa;
  }
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  max-height: 1000px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
