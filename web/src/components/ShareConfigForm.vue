<template>
  <div class="share-config-form">
    <div class="share-config-content">
      <div class="share-mode-row">
        <a-switch
          v-model:checked="config.enabled_for_agents"
          checked-children="已启用"
          un-checked-children="已禁用"
        />
        <span class="share-label">允许普通用户在智能体中使用该知识库</span>
      </div>
      <p class="share-hint">
        {{ config.enabled_for_agents ? '普通用户可通过智能体使用该知识库' : '仅管理员可在后台使用该知识库' }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
    default: () => ({
      enabled_for_agents: true
    })
  }
})

const emit = defineEmits(['update:modelValue'])

const config = reactive({
  enabled_for_agents: props.modelValue.enabled_for_agents ?? props.modelValue.is_shared ?? true
})

watch(
  () => props.modelValue,
  (value) => {
    config.enabled_for_agents = value?.enabled_for_agents ?? value?.is_shared ?? true
  },
  { deep: true }
)

watch(
  () => config.enabled_for_agents,
  (value) => {
    emit('update:modelValue', { enabled_for_agents: value })
  }
)

const validate = () => ({ valid: true, message: '' })

defineExpose({
  config,
  validate
})
</script>

<style lang="less" scoped>
.share-config-form {
  .share-config-content {
    background: var(--gray-25);
    border-radius: 8px;
    padding: 16px;
    border: 1px solid var(--gray-150);
  }

  .share-mode-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .share-label {
    color: var(--gray-800);
  }

  .share-hint {
    font-size: 13px;
    color: var(--gray-600);
    margin: 8px 0 0;
  }
}
</style>
