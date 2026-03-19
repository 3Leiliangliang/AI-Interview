<template>
  <BaseToolCall :tool-call="toolCall" :hide-params="true">
    <template #header>
      <div class="sep-header">
        <span class="note">{{ operationLabel }}</span>
        <span class="separator" v-if="kbName">|</span>
        <span class="description" v-if="kbName">知识库: {{ kbName }}</span>
        <span class="separator" v-if="queryText">|</span>
        <span class="description" v-if="queryText">{{ queryText }}</span>
      </div>
    </template>

    <template #result="{ resultContent }">
      <div class="query-kb-result">
        <div v-if="isPlainTextResult(resultContent)" class="plain-result">
          <pre>{{ normalizePlainText(resultContent) }}</pre>
        </div>
        <KbResultGroupedList v-else :chunks="parseStructuredData(resultContent)" />
      </div>
    </template>
  </BaseToolCall>
</template>

<script setup>
import { computed } from 'vue'

import BaseToolCall from '../BaseToolCall.vue'
import KbResultGroupedList from '@/components/sources/KbResultGroupedList.vue'

const props = defineProps({
  toolCall: {
    type: Object,
    required: true
  }
})

const args = computed(() => {
  const value = props.toolCall.args || props.toolCall.function?.arguments
  if (!value) return {}
  if (typeof value === 'object') return value
  try {
    return JSON.parse(value)
  } catch {
    return {}
  }
})

const toolName = computed(() => props.toolCall.name || props.toolCall.function?.name || '知识库')
const operationLabel = computed(() => `${toolName.value} 搜索`)
const kbName = computed(() => args.value.kb_name || '')
const queryText = computed(() => args.value.query_text || '')

const tryParseJson = (content) => {
  if (typeof content !== 'string') {
    return content
  }

  try {
    return JSON.parse(content)
  } catch {
    return null
  }
}

const isPlainTextResult = (content) => {
  if (typeof content !== 'string') {
    return false
  }

  return tryParseJson(content) === null
}

const normalizePlainText = (content) => {
  if (typeof content !== 'string') {
    return ''
  }
  return content.trim() || '知识库未返回内容'
}

const parseStructuredData = (content) => {
  if (!content) {
    return []
  }

  const parsed = tryParseJson(content)
  if (Array.isArray(parsed)) {
    return parsed
  }

  return []
}
</script>

<style scoped lang="less">
.query-kb-result {
  background: var(--gray-0);
  border-radius: 8px;
  padding: 4px;
}

.plain-result {
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--gray-25);
  border: 1px solid var(--gray-100);

  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 13px;
    line-height: 1.7;
    color: var(--gray-700);
  }
}
</style>
