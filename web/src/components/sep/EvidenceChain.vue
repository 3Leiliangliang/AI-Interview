<template>
  <div class="evidence-chain">
    <div v-if="!items.length" class="evidence-empty">暂无证据条目</div>

    <div
      v-for="(item, idx) in items"
      :key="`${item.concept}-${idx}`"
      class="evidence-item"
      :class="[deltaTone(item.score_delta), { 'is-misconception': item.evidence_type === 'misconception' }]"
    >
      <div class="evidence-header">
        <div class="evidence-header-left">
          <span class="evidence-concept">{{ item.concept }}</span>
          <a-tag color="default" size="small">{{ dimensionLabel(item.dimension) }}</a-tag>
          <a-tag v-if="item.evidence_type === 'misconception'" color="red" size="small">误区</a-tag>
        </div>
        <span
          :class="['evidence-delta', deltaTone(item.score_delta)]"
        >
          {{ item.score_delta >= 0 ? '+' : '' }}{{ item.score_delta }}
        </span>
      </div>

      <div class="evidence-text">{{ item.evidence_text }}</div>

      <div class="evidence-question">
        <span class="evidence-question-label">题目：</span>{{ item.question }}
      </div>
    </div>
  </div>
</template>

<script setup>
const DIMENSION_LABELS = {
  technical_competence: '技术能力',
  problem_solving: '问题解决',
  communication: '沟通表达',
  soft_skills: '综合素质',
}

defineProps({
  items: { type: Array, default: () => [] },
})

function dimensionLabel(key) {
  return DIMENSION_LABELS[key] ?? key
}

function deltaTone(delta) {
  const v = Number(delta || 0)
  if (v > 0) return 'positive'
  if (v < 0) return 'negative'
  return 'neutral'
}
</script>

<style scoped>
.evidence-chain {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-empty {
  color: var(--gray-500);
  font-size: 13px;
  padding: 12px 0;
}

.evidence-item {
  position: relative;
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  padding: 12px 14px 12px 17px;
  background: var(--main-0);
  transition: border-color 0.2s, background 0.2s;
}

.evidence-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--gray-400);
  border-top-left-radius: 4px;
  border-bottom-left-radius: 4px;
}

.evidence-item.positive::before {
  background: var(--color-success-500);
}

.evidence-item.negative::before {
  background: var(--color-error-500);
}

.evidence-item.neutral::before {
  background: var(--gray-400);
}

.evidence-item.is-misconception {
  background: var(--color-error-50);
  border-color: var(--color-error-100);
}

.evidence-item:hover {
  border-color: var(--main-500);
}

.evidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.evidence-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.evidence-concept {
  font-weight: 600;
  font-size: 13px;
  color: var(--gray-1000);
}

.evidence-delta {
  font-weight: 700;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.evidence-delta.positive {
  color: var(--color-success-500);
}

.evidence-delta.negative {
  color: var(--color-error-500);
}

.evidence-delta.neutral {
  color: var(--gray-600);
}

.evidence-text {
  font-size: 13px;
  color: var(--gray-700);
  margin-bottom: 6px;
  line-height: 1.5;
}

.evidence-question {
  font-size: 12px;
  color: var(--gray-500);
}

.evidence-question-label {
  font-weight: 500;
  color: var(--gray-600);
}
</style>
