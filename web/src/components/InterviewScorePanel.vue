<template>
  <div class="score-panel">
    <div class="score-panel__header">
      <div class="score-panel__meta">
        <div class="score-panel__title">面试评分</div>
        <div class="score-panel__tags">
          <span v-if="scorecard.role" class="score-tag">{{ scorecard.role }}</span>
          <span v-if="scorecard.round" class="score-tag">{{ scorecard.round }}</span>
        </div>
      </div>

      <div v-if="scorecard.overall !== null" class="score-panel__overall">
        <span class="score-panel__number">{{ scorecard.overall }}</span>
        <span class="score-panel__unit">/100</span>
      </div>
    </div>

    <div v-if="dimensions.length" class="score-grid">
      <div v-for="item in dimensions" :key="item.name" class="score-grid__item">
        <span class="score-grid__label">{{ getDimensionLabel(item.name) }}</span>
        <span class="score-grid__value">{{ item.score }}</span>
      </div>
    </div>

    <p v-if="scorecard.summary" class="score-panel__summary">{{ scorecard.summary }}</p>

    <div v-if="scorecard.strengths.length" class="score-section">
      <div class="score-section__title">亮点</div>
      <ul class="score-section__list">
        <li v-for="item in scorecard.strengths" :key="item">{{ item }}</li>
      </ul>
    </div>

    <div v-if="scorecard.risks.length" class="score-section">
      <div class="score-section__title">风险点</div>
      <ul class="score-section__list">
        <li v-for="item in scorecard.risks" :key="item">{{ item }}</li>
      </ul>
    </div>

    <div v-if="scorecard.suggestions.length" class="score-section">
      <div class="score-section__title">改进建议</div>
      <ul class="score-section__list">
        <li v-for="item in scorecard.suggestions" :key="item">{{ item }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  scorecard: {
    type: Object,
    required: true
  }
})

const dimensions = computed(() => props.scorecard.dimensions || [])

const dimensionLabels = {
  technical_competence: '技术能力',
  problem_solving: '问题解决',
  problem_solving_innovation: '问题解决',
  communication: '沟通表达',
  communication_clarity: '沟通表达',
  soft_skills: '综合素质',
  soft_skills_team_fit: '综合素质'
}

const getDimensionLabel = (name) => dimensionLabels[name] || name
</script>

<style lang="less" scoped>
.score-panel {
  margin: 14px 0 8px;
  padding: 16px;
  border: 1px solid var(--gray-150);
  border-radius: 12px;
  background: var(--gray-25);
}

.score-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.score-panel__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--gray-900);
}

.score-panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.score-tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-700);
  font-size: 12px;
}

.score-panel__overall {
  display: flex;
  align-items: baseline;
  gap: 2px;
  white-space: nowrap;
  color: var(--main-color);
}

.score-panel__number {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.score-panel__unit {
  font-size: 13px;
  color: var(--gray-500);
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.score-grid__item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--gray-0);
  border: 1px solid var(--gray-100);
}

.score-grid__label {
  font-size: 12px;
  color: var(--gray-500);
}

.score-grid__value {
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-900);
}

.score-panel__summary {
  margin: 14px 0 0;
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.7;
}

.score-section {
  margin-top: 14px;
}

.score-section__title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-800);
}

.score-section__list {
  margin: 0;
  padding-left: 18px;
  color: var(--gray-700);

  li + li {
    margin-top: 6px;
  }
}

@media (max-width: 640px) {
  .score-panel__header {
    flex-direction: column;
  }
}
</style>
