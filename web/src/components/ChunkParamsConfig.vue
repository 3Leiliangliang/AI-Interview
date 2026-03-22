<template>
  <div class="chunk-params-config">
    <div class="params-info">
      <p>调整分块参数可以控制文本的切分方式，影响检索质量和文档加载效率。</p>
    </div>
    <div class="preset-overview" :class="{ qa: effectivePresetId === 'qa' }">
      <div class="overview-header">
        <span class="overview-label">当前生效分块</span>
        <span class="preset-badge">{{ effectivePresetLabel }}</span>
      </div>
      <p class="overview-description">{{ presetDescription }}</p>
      <p v-if="tempChunkParams.chunk_preset_id" class="overview-meta">
        本次将按当前选择的策略处理文件
      </p>
      <p v-else-if="allowPresetFollowDefault" class="overview-meta">
        当前未单独覆盖，沿用知识库默认策略：{{ databasePresetLabel }}
      </p>
      <p v-if="effectivePresetId === 'qa'" class="overview-tip">
        QA 分块会优先按问答结构切分，当前知识库内容会更明显按问答方式入库。
      </p>
    </div>
    <a-form :model="tempChunkParams" name="chunkConfig" autocomplete="off" layout="vertical">
      <a-form-item v-if="showPreset" name="chunk_preset_id">
        <template #label>
          <span class="chunk-preset-label">
            分块策略
            <a-tooltip :title="presetDescription">
              <QuestionCircleOutlined class="chunk-preset-help-icon" />
            </a-tooltip>
          </span>
        </template>
        <a-select
          v-model:value="tempChunkParams.chunk_preset_id"
          :options="presetOptions"
          style="width: 100%"
        />
        <p class="param-description">
          预设策略对齐 RAGFlow：General、QA、Book、Laws。
          <span v-if="allowPresetFollowDefault">留空时沿用知识库默认策略。</span>
        </p>
      </a-form-item>

      <div class="chunk-row" v-if="showChunkSizeOverlap">
        <a-form-item label="Chunk Size" name="chunk_size">
          <a-input-number
            v-model:value="tempChunkParams.chunk_size"
            :min="100"
            :max="10000"
            style="width: 100%"
          />
          <p class="param-description">每个文本片段的最大字符数</p>
        </a-form-item>
        <a-form-item label="Chunk Overlap" name="chunk_overlap">
          <a-input-number
            v-model:value="tempChunkParams.chunk_overlap"
            :min="0"
            :max="1000"
            style="width: 100%"
          />
          <p class="param-description">相邻文本片段间的重叠字符数</p>
        </a-form-item>
      </div>
      <a-form-item
        v-if="showQaSplit"
        class="qa-separator-item"
        label="分隔符 (Separator)"
        name="qa_separator"
      >
        <a-input
          v-model:value="tempChunkParams.qa_separator"
          placeholder="输入分隔符，例如 \n\n\n 或 ---"
          style="width: 100%"
        />
        <p class="param-description">支持 \n、\t 等转义字符。留空则不启用预分割</p>
      </a-form-item>
    </a-form>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import {
  CHUNK_PRESET_OPTIONS,
  CHUNK_PRESET_LABEL_MAP,
  getChunkPresetDescription
} from '@/utils/chunk_presets'

const props = defineProps({
  tempChunkParams: {
    type: Object,
    required: true
  },
  showQaSplit: {
    type: Boolean,
    default: true
  },
  showChunkSizeOverlap: {
    type: Boolean,
    default: true
  },
  showPreset: {
    type: Boolean,
    default: true
  },
  allowPresetFollowDefault: {
    type: Boolean,
    default: false
  },
  databasePresetId: {
    type: String,
    default: 'general'
  }
})

const presetOptions = computed(() => {
  const options = []
  const defaultPresetLabel = CHUNK_PRESET_LABEL_MAP[props.databasePresetId] || 'General'

  if (props.allowPresetFollowDefault) {
    options.push({
      value: '',
      label: `沿用知识库默认（${defaultPresetLabel}）`
    })
  }

  options.push(...CHUNK_PRESET_OPTIONS.map(({ value, label }) => ({ value, label })))

  return options
})

const effectivePresetId = computed(
  () => props.tempChunkParams.chunk_preset_id || props.databasePresetId || 'general'
)
const effectivePresetLabel = computed(
  () => CHUNK_PRESET_LABEL_MAP[effectivePresetId.value] || 'General'
)
const databasePresetLabel = computed(
  () => CHUNK_PRESET_LABEL_MAP[props.databasePresetId] || 'General'
)
const presetDescription = computed(() => getChunkPresetDescription(effectivePresetId.value))
</script>

<style scoped>
.chunk-params-config {
  width: 100%;
}

.params-info {
  margin-bottom: 16px;
}

.params-info p {
  margin: 0;
  color: var(--gray-500);
  font-size: 14px;
  line-height: 1.5;
}

.preset-overview {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--gray-200);
  background: var(--gray-0);
}

.preset-overview.qa {
  border-color: rgba(8, 145, 178, 0.35);
  background: linear-gradient(135deg, rgba(236, 254, 255, 0.95) 0%, rgba(248, 250, 252, 1) 100%);
}

.overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.overview-label {
  font-size: 13px;
  color: var(--gray-500);
}

.preset-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(8, 145, 178, 0.12);
  color: rgb(14, 116, 144);
  font-size: 13px;
  font-weight: 600;
}

.overview-description {
  margin: 0;
  color: var(--gray-700);
  font-size: 13px;
  line-height: 1.6;
}

.overview-meta,
.overview-tip {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
}

.overview-meta {
  color: var(--gray-500);
}

.overview-tip {
  color: rgb(14, 116, 144);
  font-weight: 500;
}

.chunk-row {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.chunk-row > .ant-form-item {
  flex: 1;
  margin-bottom: 0;
}

.qa-separator-item {
  margin-top: 8px;
  margin-bottom: 0;
}

.param-description {
  font-size: 12px;
  color: var(--gray-400);
  margin: 4px 0 0 0;
  line-height: 1.4;
}

.chunk-preset-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chunk-preset-help-icon {
  color: var(--gray-500);
  cursor: help;
  font-size: 14px;
}
</style>
