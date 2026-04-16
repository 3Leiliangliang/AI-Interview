<template>
  <div class="database-container layout-container">
    <HeaderComponent title="文档知识库" :loading="dbState.listLoading">
      <template #actions>
        <a-button type="primary" @click="state.openNewDatabaseModel = true"> 新建知识库 </a-button>
      </template>
    </HeaderComponent>

    <a-modal
      :open="state.openNewDatabaseModel"
      title="新建知识库"
      :confirm-loading="dbState.creating"
      @ok="handleCreateDatabase"
      @cancel="cancelCreateDatabase"
      class="new-database-modal"
      width="800px"
      destroyOnClose
    >
      <h3>知识库名称<span style="color: var(--color-error-500)">*</span></h3>
      <a-input v-model:value="newDatabase.name" placeholder="新建知识库名称" size="large" />

      <h3>岗位<span style="color: var(--color-error-500)">*</span></h3>
      <a-select
        v-model:value="newDatabase.position"
        :options="positionOptions"
        style="width: 100%"
        size="large"
        placeholder="请选择岗位"
      />

      <template v-if="true">
        <h3>嵌入模型</h3>
        <EmbeddingModelSelector
          v-model:value="newDatabase.embed_model_name"
          style="width: 100%"
          size="large"
          placeholder="请选择嵌入模型"
        />
      </template>

      <template v-if="newDatabase.kb_type === 'openviking'">
        <h3>VLM 模型<span style="color: var(--color-error-500)">*</span></h3>
        <ModelSelectorComponent
          :model_spec="vlmModelSpec"
          style="width: 100%"
          size="large"
          placeholder="请选择 VLM 模型"
          @select-model="handleLLMSelect"
        />
      </template>

      <div class="chunk-preset-title-row">
        <h3 style="margin: 0">分块策略</h3>
        <a-tooltip :title="selectedPresetDescription">
          <QuestionCircleOutlined class="chunk-preset-help-icon" />
        </a-tooltip>
      </div>
      <a-select
        v-model:value="newDatabase.chunk_preset_id"
        :options="chunkPresetOptions"
        style="width: 100%"
        size="large"
      />


      <h3 style="margin-top: 20px">知识库描述</h3>
      <p style="color: var(--gray-700); font-size: 14px">
        在智能体流程中，这里的描述会作为工具的描述。智能体会根据知识库的标题和描述来选择合适的工具。所以这里描述的越详细，智能体越容易选择到合适的工具。
      </p>
      <AiTextarea
        v-model="newDatabase.description"
        :name="newDatabase.name"
        placeholder="新建知识库描述"
        :auto-size="{ minRows: 3, maxRows: 10 }"
      />

      <!-- 隐私设置（暂时隐藏）
      <h3 style="margin-top: 20px">隐私设置</h3>
      <div class="privacy-config">
        <a-switch
          v-model:checked="newDatabase.is_private"
          checked-children="私有"
          un-checked-children="公开"
          size="default"
        />
        <span style="margin-left: 12px">设置为私有知识库</span>
        <a-tooltip
          title="当前未使用此属性。在部分智能体的设计中，可以根据隐私标志来决定启用什么模型和策略。例如，对于私有知识库，可以选择更严格的数据处理和访问控制策略，以保护敏感信息的安全性和隐私性。"
        >
          <InfoCircleOutlined style="margin-left: 8px; color: var(--gray-500); cursor: help" />
        </a-tooltip>
      </div>
      -->

      <!-- 共享配置 -->
      <h3>共享设置</h3>
      <ShareConfigForm v-model="shareConfig" />
      <template #footer>
        <a-button key="back" @click="cancelCreateDatabase">取消</a-button>
        <a-button
          key="submit"
          type="primary"
          :loading="dbState.creating"
          @click="handleCreateDatabase"
          >创建</a-button
        >
      </template>
    </a-modal>

    <!-- 加载状态 -->
    <div v-if="dbState.listLoading" class="loading-container">
      <a-spin size="large" />
      <p>正在加载知识库...</p>
    </div>

    <!-- 空状态显示 -->
    <div v-else-if="!databases || databases.length === 0" class="empty-state">
      <h3 class="empty-title">暂无知识库</h3>
      <p class="empty-description">创建您的第一个知识库，开始管理文档和知识</p>
      <a-button type="primary" size="large" @click="state.openNewDatabaseModel = true">
        <template #icon>
          <PlusOutlined />
        </template>
        创建知识库
      </a-button>
    </div>

    <!-- 数据库列表 -->
    <div v-else class="databases">
      <div
        v-for="database in sortedDatabases"
        :key="database.db_id"
        class="database dbcard"
        @click="navigateToDatabase(database.db_id)"
      >
        <LockOutlined
          v-if="database.metadata?.is_private"
          class="private-lock-icon"
          title="私有知识库"
        />
        <div class="top">
          <div class="icon">
            <component :is="getKbTypeIcon(database.kb_type || 'openviking')" />
          </div>
          <div class="info">
            <h3>{{ database.name }}</h3>
            <p>
              <span>{{ database.files ? Object.keys(database.files).length : 0 }} 文件</span>
              <span class="created-time-inline" v-if="database.created_at">
                {{ formatCreatedTime(database.created_at) }}
              </span>
            </p>
          </div>
        </div>
        <p class="description">{{ database.description || '暂无描述' }}</p>
        <div class="tags">
          <a-tag color="blue" v-if="database.embed_info?.name">{{
            database.embed_info.name
          }}</a-tag>
          <a-tag color="geekblue">岗位：{{ getDatabasePositionLabel(database) }}</a-tag>
          <a-tag color="purple" v-if="getDatabaseVlmModel(database)">
            VLM：{{ getDatabaseVlmModel(database) }}
          </a-tag>
          <a-tag color="cyan" class="chunk-tag">
            分块：{{ chunkPresetLabelMap[database.additional_params?.chunk_preset_id || 'general'] || 'General' }}
          </a-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useConfigStore } from '@/stores/config'
import { useDatabaseStore } from '@/stores/database'
import { LockOutlined, PlusOutlined, QuestionCircleOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import HeaderComponent from '@/components/HeaderComponent.vue'
import ModelSelectorComponent from '@/components/ModelSelectorComponent.vue'
import EmbeddingModelSelector from '@/components/EmbeddingModelSelector.vue'
import ShareConfigForm from '@/components/ShareConfigForm.vue'
import { usePositionTypes } from '@/composables/usePositionTypes'
import dayjs, { parseToShanghai } from '@/utils/time'
import AiTextarea from '@/components/AiTextarea.vue'
import { getKbTypeIcon } from '@/utils/kb_utils'
import {
  getDefaultPositionType,
  getSelectablePositionTypes,
  getUnclassifiedPositionType,
  inferPositionType,
  normalizePositionType
} from '@/utils/position_utils'
import {
  CHUNK_PRESET_OPTIONS,
  CHUNK_PRESET_LABEL_MAP,
  getChunkPresetDescription
} from '@/utils/chunk_presets'

const route = useRoute()
const router = useRouter()
const configStore = useConfigStore()
const databaseStore = useDatabaseStore()
const { positionTypes, loadPositionTypes } = usePositionTypes()

// 使用 store 的状态
const { databases, state: dbState } = storeToRefs(databaseStore)

const state = reactive({
  openNewDatabaseModel: false
})

// 共享配置状态（用于提交数据）
const shareConfig = ref({
  enabled_for_agents: true
})


const chunkPresetOptions = CHUNK_PRESET_OPTIONS.map(({ label, value }) => ({ label, value }))
const chunkPresetLabelMap = CHUNK_PRESET_LABEL_MAP

const LEGACY_POSITION_MAP = {
  'React Interview Questions': '前端工程师',
  'Waking-Up': '后端工程师',
  JavaGuide: '后端工程师',
  'SQL 面试题库': '后端工程师',
  'DSA 面试手册': '算法工程师',
  '系统设计面试题库': '系统架构师',
  'AI 应用开发面试': 'AI 应用开发'
}

const positionOptions = computed(() =>
  getSelectablePositionTypes(positionTypes.value).map((item) => ({
    label: item.label,
    value: item.label
  }))
)

const parseModelSpec = (spec = '') => {
  if (typeof spec !== 'string' || !spec) {
    return {
      provider: '',
      model_name: ''
    }
  }

  const index = spec.indexOf('/')
  if (index === -1) {
    return {
      provider: '',
      model_name: ''
    }
  }

  return {
    provider: spec.slice(0, index),
    model_name: spec.slice(index + 1)
  }
}

const createEmptyDatabaseForm = () => ({
  name: '',
  description: '',
  position: getDefaultPositionType(positionTypes.value).label,
  embed_model_name: configStore.config?.embed_model,
  kb_type: 'openviking',
  llm_info: parseModelSpec(configStore.config?.default_model || ''),
  is_private: false,
  storage: '',
  chunk_preset_id: 'general'
})

const newDatabase = reactive(createEmptyDatabaseForm())

const selectedPresetDescription = computed(() =>
  getChunkPresetDescription(newDatabase.chunk_preset_id)
)

const vlmModelSpec = computed(() => {
  const provider = newDatabase.llm_info?.provider || ''
  const modelName = newDatabase.llm_info?.model_name || ''
  if (provider && modelName) {
    return `${provider}/${modelName}`
  }
  return ''
})

const inferDatabasePosition = (database) => {
  const explicitPosition =
    database?.additional_params?.position || database?.metadata?.position || ''
  if (explicitPosition) {
    return normalizePositionType(explicitPosition, positionTypes.value).label
  }

  const name = String(database?.name || '').trim()
  if (LEGACY_POSITION_MAP[name]) {
    return LEGACY_POSITION_MAP[name]
  }

  return inferPositionType(name, database?.description || '', positionTypes.value, {
    fallbackToDefault: false
  }).label
}

const getDatabasePositionLabel = (database) => inferDatabasePosition(database)

const getDatabaseVlmModel = (database) => {
  const provider = database?.llm_info?.provider || ''
  const modelName = database?.llm_info?.model_name || ''
  if (provider && modelName) {
    return `${provider}/${modelName}`
  }
  return ''
}

const positionOrder = computed(
  () =>
    new Map(
      [
        ...getSelectablePositionTypes(positionTypes.value).map((item) => item.label),
        getUnclassifiedPositionType(positionTypes.value).label
      ].map((label, index) => [label, index])
    )
)

const sortedDatabases = computed(() =>
  [...(databases.value || [])].sort((left, right) => {
    const leftOrder = positionOrder.value.get(inferDatabasePosition(left)) ?? Number.MAX_SAFE_INTEGER
    const rightOrder = positionOrder.value.get(inferDatabasePosition(right)) ?? Number.MAX_SAFE_INTEGER
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder
    }

    const leftTime = dayjs(parseToShanghai(left?.created_at) || 0).valueOf()
    const rightTime = dayjs(parseToShanghai(right?.created_at) || 0).valueOf()
    if (leftTime !== rightTime) {
      return rightTime - leftTime
    }

    return String(left?.name || '').localeCompare(String(right?.name || ''), 'zh-CN')
  })
)

const resetNewDatabase = () => {
  Object.assign(newDatabase, createEmptyDatabaseForm())
  // 重置共享配置
  shareConfig.value = {
    enabled_for_agents: true
  }
}

const cancelCreateDatabase = () => {
  state.openNewDatabaseModel = false
  resetNewDatabase()
}

// 格式化创建时间
const formatCreatedTime = (createdAt) => {
  if (!createdAt) return ''
  const parsed = parseToShanghai(createdAt)
  if (!parsed) return ''

  const today = dayjs().startOf('day')
  const createdDay = parsed.startOf('day')
  const diffInDays = today.diff(createdDay, 'day')

  if (diffInDays === 0) {
    return '今天创建'
  }
  if (diffInDays === 1) {
    return '昨天创建'
  }
  if (diffInDays < 7) {
    return `${diffInDays} 天前创建`
  }
  if (diffInDays < 30) {
    const weeks = Math.floor(diffInDays / 7)
    return `${weeks} 周前创建`
  }
  if (diffInDays < 365) {
    const months = Math.floor(diffInDays / 30)
    return `${months} 个月前创建`
  }
  const years = Math.floor(diffInDays / 365)
  return `${years} 年前创建`
}

// 处理LLM选择
const handleLLMSelect = (spec) => {
  console.log('LLM选择:', spec)
  if (typeof spec !== 'string' || !spec) return

  const index = spec.indexOf('/')
  const provider = index !== -1 ? spec.slice(0, index) : ''
  const modelName = index !== -1 ? spec.slice(index + 1) : ''

  newDatabase.llm_info.provider = provider
  newDatabase.llm_info.model_name = modelName
}

// 构建请求数据（只负责表单数据转换）
const buildRequestData = () => {
  const requestData = {
    database_name: newDatabase.name.trim(),
    description: newDatabase.description?.trim() || '',
    kb_type: newDatabase.kb_type,
    additional_params: {}
  }

  requestData.embed_model_name = newDatabase.embed_model_name || configStore.config.embed_model
  requestData.additional_params.is_private = newDatabase.is_private || false
  requestData.additional_params.chunk_preset_id = newDatabase.chunk_preset_id || 'general'
  requestData.additional_params.position = newDatabase.position

  requestData.share_config = {
    enabled_for_agents: shareConfig.value.enabled_for_agents !== false
  }

  if (newDatabase.kb_type === 'openviking') {
    if (newDatabase.storage) {
      requestData.additional_params.storage = newDatabase.storage
    }
    requestData.llm_info = {
      provider: newDatabase.llm_info?.provider || '',
      model_name: newDatabase.llm_info?.model_name || ''
    }
  }

  return requestData
}

const handleCreateDatabase = async () => {
  if (!newDatabase.position) {
    message.error('请选择岗位')
    return
  }

  if (
    newDatabase.kb_type === 'openviking' &&
    (!newDatabase.llm_info?.provider || !newDatabase.llm_info?.model_name)
  ) {
    message.error('OpenViking 知识库需要配置 VLM 模型')
    return
  }

  const requestData = buildRequestData()
  try {
    await databaseStore.createDatabase(requestData)
    resetNewDatabase()
    state.openNewDatabaseModel = false
  } catch {
    // 错误已在 store 中处理
  }
}

const navigateToDatabase = (databaseId) => {
  router.push({ path: `/database/${databaseId}` })
}

watch(
  () => route.path,
  (newPath) => {
    if (newPath === '/database') {
      databaseStore.loadDatabases()
    }
  }
)

onMounted(() => {
  loadPositionTypes().then(() => {
    newDatabase.position = normalizePositionType(newDatabase.position, positionTypes.value).label
  })
  databaseStore.loadDatabases()
})
</script>

<style lang="less" scoped>
.new-database-modal {
  .chunk-preset-title-row {
    margin-top: 20px;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .chunk-preset-help-icon {
    color: var(--gray-500);
    cursor: help;
    font-size: 14px;
  }

  .privacy-config {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
  }

  .chunk-config {
    margin-top: 16px;
    padding: 12px 16px;
    background-color: var(--gray-25);
    border-radius: 6px;
    border: 1px solid var(--gray-150);

    h3 {
      margin-top: 0;
      margin-bottom: 12px;
      color: var(--gray-800);
    }

    .chunk-params {
      display: flex;
      flex-direction: column;
      gap: 12px;

      .param-row {
        display: flex;
        align-items: center;
        gap: 12px;

        label {
          min-width: 80px;
          font-weight: 500;
          color: var(--gray-700);
        }

        .param-hint {
          font-size: 12px;
          color: var(--gray-500);
          margin-left: 8px;
        }
      }
    }
  }
}

.database-container {
  .databases {
    .database {
      .top {
        .info {
          h3 {
            display: block;
          }
        }
      }
    }
  }
}
.database-actions,
.document-actions {
  margin-bottom: 20px;
}
.databases {
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.database,
.graphbase {
  background: linear-gradient(145deg, var(--gray-0) 0%, var(--gray-10) 100%);
  box-shadow: 0px 1px 2px 0px var(--shadow-2);
  border: 1px solid var(--gray-100);
  transition: none;
  position: relative;
}

.dbcard,
.database {
  width: 100%;
  padding: 16px;
  border-radius: 16px;
  min-height: 156px;
  height: auto;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  position: relative; // 为绝对定位的锁定图标提供参考
  overflow: hidden;

  .private-lock-icon {
    position: absolute;
    top: 20px;
    right: 20px;
    color: var(--gray-600);
    background: linear-gradient(135deg, var(--gray-0) 0%, var(--gray-100) 100%);
    font-size: 12px;
    border-radius: 8px;
    padding: 6px;
    z-index: 2;
    box-shadow: 0px 2px 4px var(--shadow-2);
    border: 1px solid var(--gray-100);
  }

  .top {
    display: flex;
    align-items: center;
    height: 54px;
    margin-bottom: 14px;

    .icon {
      width: 54px;
      height: 54px;
      font-size: 26px;
      margin-right: 14px;
      display: flex;
      justify-content: center;
      align-items: center;
      background: var(--main-30);
      border-radius: 12px;
      border: 1px solid var(--gray-150);
      color: var(--main-color);
      position: relative;
    }

    .info {
      flex: 1;
      min-width: 0;

      h3,
      p {
        margin: 0;
        color: var(--gray-10000);
      }

      h3 {
        font-size: 17px;
        font-weight: 600;
        letter-spacing: -0.02em;
        line-height: 1.4;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      p {
        color: var(--gray-700);
        font-size: 13px;
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 4px;
        font-weight: 400;

        .created-time-inline {
          color: var(--gray-700);
          font-size: 11px;
          font-weight: 400;
          background: var(--gray-50);
          padding: 2px 6px;
          border-radius: 4px;
        }
      }
    }
  }

  .description {
    color: var(--gray-600);
    overflow: hidden;
    display: -webkit-box;
    line-clamp: 1;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    text-overflow: ellipsis;
    margin-bottom: 12px;
    font-size: 13px;
    font-weight: 400;
    flex: 1;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .chunk-tag {
    font-weight: 600;
  }
}

.database-empty {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  flex-direction: column;
  color: var(--gray-900);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 20px;
  text-align: center;

  .empty-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--gray-900);
    margin: 0 0 12px 0;
    letter-spacing: -0.02em;
  }

  .empty-description {
    font-size: 14px;
    color: var(--gray-600);
    margin: 0 0 32px 0;
    line-height: 1.5;
    max-width: 320px;
  }

  .ant-btn {
    height: 44px;
    padding: 0 24px;
    font-size: 15px;
    font-weight: 500;
  }
}

.database-container {
  padding: 0;
}

.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 300px;
  gap: 16px;
}

.new-database-modal {
  h3 {
    margin-top: 10px;
  }
}
</style>
