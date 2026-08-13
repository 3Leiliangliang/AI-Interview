<template>
  <div class="database-page">
    <!-- 顶栏 -->
    <div class="page-topbar">
      <div class="topbar-left">
        <h1 class="page-title">知识库</h1>
        <p class="page-subtitle" v-if="!dbState.listLoading && databases.length > 0">
          {{ databases.length }} 个库 · {{ totalFileCount }} 个文件 · {{ indexStatusText }}
        </p>
      </div>
      <div class="topbar-actions">
        <div v-if="importTask" class="import-progress">
          <a-spin size="small" />
          <span class="import-progress-text">{{ importProgressText }}</span>
        </div>
        <a-button class="btn-secondary" :loading="importingUpstream" @click="handleImportUpstream">
          导入上游资料
        </a-button>
        <a-button type="primary" class="btn-primary" @click="state.openNewDatabaseModel = true">
          新建知识库
        </a-button>
      </div>
    </div>

    <!-- 新建知识库弹窗 -->
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

      <h3>共享设置</h3>
      <ShareConfigForm v-model="shareConfig" />
      <template #footer>
        <a-button key="back" @click="cancelCreateDatabase">取消</a-button>
        <a-button key="submit" type="primary" :loading="dbState.creating" @click="handleCreateDatabase">
          创建
        </a-button>
      </template>
    </a-modal>

    <!-- 加载状态 -->
    <div v-if="dbState.listLoading" class="loading-container">
      <a-spin size="large" />
      <p>正在加载知识库...</p>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!databases || databases.length === 0" class="empty-state">
      <h3 class="empty-title">暂无知识库</h3>
      <p class="empty-description">创建您的第一个知识库，开始管理文档和知识</p>
      <a-button type="primary" size="large" @click="state.openNewDatabaseModel = true">
        <template #icon><PlusOutlined /></template>
        创建知识库
      </a-button>
    </div>

    <!-- 表格区域 -->
    <template v-else>
      <!-- 岗位筛选 Tab + 搜索 -->
      <div class="filter-bar">
        <div class="position-tabs">
          <div
            v-for="tab in positionTabs"
            :key="tab.key"
            class="position-tab"
            :class="{ active: activePositionTab === tab.key }"
            @click="activePositionTab = tab.key"
          >
            {{ tab.label }} {{ tab.count }}
          </div>
        </div>
        <div class="filter-search">
          <SearchOutlined class="search-icon" />
          <input
            v-model="searchQuery"
            placeholder="搜索知识库…"
            class="search-input"
          />
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-wrapper">
        <table class="kb-table">
          <thead>
            <tr>
              <th class="col-name">名称</th>
              <th class="col-position">岗位</th>
              <th class="col-files sortable" @click="toggleSort('files')">
                文件
                <span class="sort-arrow" v-if="sortField === 'files'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
              </th>
              <th class="col-chunks">分块</th>
              <th class="col-embedding">Embedding</th>
              <th class="col-last-index sortable" @click="toggleSort('last_index')">
                最近索引
                <span class="sort-arrow" v-if="sortField === 'last_index'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
              </th>
              <th class="col-status">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="db in filteredDatabases"
              :key="db.db_id"
              class="kb-row"
              @click="navigateToDatabase(db.db_id)"
            >
              <td class="col-name">
                <div class="db-name">{{ db.name }}</div>
                <div class="db-desc">{{ db.description || '暂无描述' }}</div>
              </td>
              <td class="col-position">{{ getDatabasePositionLabel(db) }}</td>
              <td class="col-files">{{ getFileCount(db) }}</td>
              <td class="col-chunks">{{ chunkPresetLabelMap[getChunkPresetId(db)] || 'General' }}</td>
              <td class="col-embedding">{{ db.embed_info?.name || '—' }}</td>
              <td class="col-last-index">{{ formatLastIndexed(db) }}</td>
              <td class="col-status">
                <span class="status-badge" :class="getStatusClass(db)">{{ getStatusLabel(db) }}</span>
              </td>
            </tr>
            <!-- 上游资料未导入提示行 -->
            <tr v-if="showUpstreamBanner" class="upstream-row">
              <td :colspan="7">
                <div class="upstream-banner">
                  <div class="upstream-info">
                    <div class="upstream-title">还有 {{ unimportedCount }} 个上游面试资料源未导入</div>
                    <div class="upstream-examples">{{ unimportedExamples }}</div>
                  </div>
                  <a-button class="btn-secondary" :loading="importingUpstream" @click.stop="handleImportUpstream">
                    一键导入
                  </a-button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, reactive, watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useConfigStore } from '@/stores/config'
import { useDatabaseStore } from '@/stores/database'
import { PlusOutlined, QuestionCircleOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import ModelSelectorComponent from '@/components/ModelSelectorComponent.vue'
import EmbeddingModelSelector from '@/components/EmbeddingModelSelector.vue'
import ShareConfigForm from '@/components/ShareConfigForm.vue'
import { usePositionTypes } from '@/composables/usePositionTypes'
import dayjs, { parseToShanghai } from '@/utils/time'
import AiTextarea from '@/components/AiTextarea.vue'
import { databaseApi } from '@/apis/knowledge_api'
import {
  getDefaultPositionType,
  getSelectablePositionTypes,
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

const { databases, state: dbState } = storeToRefs(databaseStore)

const state = reactive({
  openNewDatabaseModel: false
})

const shareConfig = ref({
  enabled_for_agents: true
})

const chunkPresetOptions = CHUNK_PRESET_OPTIONS.map(({ label, value }) => ({ label, value }))
const chunkPresetLabelMap = CHUNK_PRESET_LABEL_MAP

// 搜索 & 筛选
const searchQuery = ref('')
const activePositionTab = ref('all')

// 排序
const sortField = ref('last_index')
const sortDir = ref('desc')

// 上游资料导入
const upstreamState = ref({ unimported: [], unimported_count: 0, all_imported: true })
const importingUpstream = ref(false)
const importTask = ref(null)
let importPollTimer = null

const importProgressText = computed(() => {
  if (!importTask.value) return ''
  const pct = Math.round(importTask.value.progress || 0)
  const msg = importTask.value.message || '正在导入上游资料'
  return `${pct}% · ${msg}`
})

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

const positionTabs = computed(() => {
  const tabs = [{ key: 'all', label: '全部', count: (databases.value || []).length }]
  const selectable = getSelectablePositionTypes(positionTypes.value)
  const counts = {}
  for (const db of databases.value || []) {
    const pos = getDatabasePositionLabel(db)
    counts[pos] = (counts[pos] || 0) + 1
  }
  for (const item of selectable) {
    tabs.push({ key: item.key, label: item.label, count: counts[item.label] || 0 })
  }
  return tabs
})

// 计算属性
const totalFileCount = computed(() => {
  let count = 0
  for (const db of databases.value || []) {
    count += getFileCount(db)
  }
  return count
})

const indexStatusText = computed(() => {
  const dbs = databases.value || []
  if (!dbs.length) return '暂无数据'
  let indexed = 0
  let processing = 0
  let failed = 0
  let empty = 0
  for (const db of dbs) {
    const status = getDbOverallStatus(db)
    if (status === 'indexed') indexed++
    else if (status === 'processing') processing++
    else if (status === 'failed' || status === 'partial') failed++
    else if (status === 'empty') empty++
  }
  if (indexed === dbs.length) return '全部索引完成'
  const parts = []
  if (indexed) parts.push(`${indexed} 个索引完成`)
  if (processing) parts.push(`${processing} 个进行中`)
  if (failed) parts.push(`${failed} 个索引失败`)
  if (empty) parts.push(`${empty} 个无文件`)
  return parts.join(' · ')
})

const filteredDatabases = computed(() => {
  let list = [...(databases.value || [])]

  // 岗位筛选
  if (activePositionTab.value !== 'all') {
    const tab = positionTabs.value.find((t) => t.key === activePositionTab.value)
    if (tab) {
      list = list.filter((db) => getDatabasePositionLabel(db) === tab.label)
    }
  }

  // 搜索
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(
      (db) =>
        (db.name || '').toLowerCase().includes(q) ||
        (db.description || '').toLowerCase().includes(q)
    )
  }

  // 排序
  list.sort((a, b) => {
    let cmp = 0
    if (sortField.value === 'files') {
      cmp = getFileCount(a) - getFileCount(b)
    } else if (sortField.value === 'last_index') {
      const timeA = getLastIndexedTimestamp(a)
      const timeB = getLastIndexedTimestamp(b)
      cmp = timeA - timeB
    }
    return sortDir.value === 'desc' ? -cmp : cmp
  })

  return list
})

const showUpstreamBanner = computed(() => !upstreamState.value.all_imported)

const unimportedCount = computed(() => upstreamState.value.unimported_count)

const unimportedExamples = computed(() => {
  const names = upstreamState.value.unimported || []
  return names.slice(0, 3).join('、') + (names.length > 3 ? ' 等' : '')
})

// Helper functions
const getFileCount = (db) => {
  if (!db || !db.files) return 0
  return Object.values(db.files).filter((f) => f && !f.is_folder).length
}

const getChunkPresetId = (db) => {
  return db?.additional_params?.chunk_preset_id || 'general'
}

const getLastIndexedTimestamp = (db) => {
  if (!db || !db.files) return 0
  let maxTs = 0
  for (const f of Object.values(db.files)) {
    if (!f) continue
    const time = parseToShanghai(f.indexed_at || f.updated_at || f.created_at)
    if (time) maxTs = Math.max(maxTs, time.valueOf())
  }
  return maxTs
}

const formatLastIndexed = (db) => {
  const ts = getLastIndexedTimestamp(db)
  if (!ts) return '—'
  return dayjs(ts).format('MM/DD HH:mm')
}

const getDbOverallStatus = (db) => {
  if (!db || !db.files) return 'empty'
  const files = Object.values(db.files).filter((f) => f && !f.is_folder)
  if (!files.length) return 'empty'

  const processing = ['processing', 'waiting', 'parsing', 'indexing']
  let hasProcessing = false
  let hasFailed = false
  let allIndexed = true

  for (const f of files) {
    if (processing.includes(f.status)) hasProcessing = true
    if (f.status === 'error_indexing' || f.status === 'failed') hasFailed = true
    if (f.status !== 'indexed' && f.status !== 'done') allIndexed = false
  }

  if (hasProcessing) return 'processing'
  if (allIndexed) return 'indexed'
  if (hasFailed) return 'failed'
  return 'partial'
}

const getStatusLabel = (db) => {
  const status = getDbOverallStatus(db)
  const map = {
    indexed: '已索引',
    processing: '索引中',
    failed: '失败',
    partial: '部分索引',
    empty: '无文件'
  }
  return map[status] || status
}

const getStatusClass = (db) => {
  const status = getDbOverallStatus(db)
  return `status-${status}`
}

const parseModelSpec = (spec = '') => {
  if (typeof spec !== 'string' || !spec) return { provider: '', model_name: '' }
  const index = spec.indexOf('/')
  if (index === -1) return { provider: '', model_name: '' }
  return { provider: spec.slice(0, index), model_name: spec.slice(index + 1) }
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
  if (provider && modelName) return `${provider}/${modelName}`
  return ''
})

const inferDatabasePosition = (database) => {
  const explicitPosition =
    database?.additional_params?.position || database?.metadata?.position || ''
  if (explicitPosition) {
    return normalizePositionType(explicitPosition, positionTypes.value).label
  }

  const name = String(database?.name || '').trim()
  if (LEGACY_POSITION_MAP[name]) return LEGACY_POSITION_MAP[name]

  return inferPositionType(name, database?.description || '', positionTypes.value, {
    fallbackToDefault: false
  }).label
}

const getDatabasePositionLabel = (database) => inferDatabasePosition(database)

const toggleSort = (field) => {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortField.value = field
    sortDir.value = 'desc'
  }
}

// 上游资料来源检查
const loadUpstreamSources = async () => {
  try {
    const data = await databaseApi.getUpstreamSources()
    upstreamState.value = {
      unimported: data.unimported || [],
      unimported_count: data.unimported_count || 0,
      all_imported: data.all_imported !== false
    }
  } catch {
    upstreamState.value = { unimported: [], unimported_count: 0, all_imported: true }
  }
}

const handleImportUpstream = async () => {
  importingUpstream.value = true
  try {
    const result = await databaseApi.importUpstreamSources()
    message.success(result.message || '导入任务已提交')
    importTask.value = {
      task_id: result.task_id,
      status: 'pending',
      progress: 0,
      message: '任务已提交，等待执行'
    }
    startImportPoll(result.task_id)
  } catch (e) {
    message.error(e.message || '导入失败')
  } finally {
    importingUpstream.value = false
  }
}

// 轮询后台任务状态，展示导入进度
const startImportPoll = (taskId) => {
  stopImportPoll()
  importPollTimer = setInterval(async () => {
    try {
      const data = await databaseApi.getTask(taskId)
      const task = data?.task
      if (!task) return
      importTask.value = {
        task_id: taskId,
        status: task.status,
        progress: task.progress || 0,
        message: task.message || ''
      }
      if (task.status === 'success') {
        stopImportPoll()
        importTask.value = null
        message.success('上游资料导入完成')
        databaseStore.loadDatabases()
        loadUpstreamSources()
      } else if (task.status === 'failed' || task.status === 'cancelled') {
        stopImportPoll()
        importTask.value = null
        message.error(
          `导入${task.status === 'cancelled' ? '已取消' : '失败'}：${task.error || task.message || '未知错误'}`
        )
      }
    } catch {
      stopImportPoll()
      importTask.value = null
      message.error('获取导入进度失败，请稍后刷新查看')
    }
  }, 3000)
}

const stopImportPoll = () => {
  if (importPollTimer) {
    clearInterval(importPollTimer)
    importPollTimer = null
  }
}

const resetNewDatabase = () => {
  Object.assign(newDatabase, createEmptyDatabaseForm())
  shareConfig.value = { enabled_for_agents: true }
}

const cancelCreateDatabase = () => {
  state.openNewDatabaseModel = false
  resetNewDatabase()
}

const handleLLMSelect = (spec) => {
  if (typeof spec !== 'string' || !spec) return
  const index = spec.indexOf('/')
  const provider = index !== -1 ? spec.slice(0, index) : ''
  const modelName = index !== -1 ? spec.slice(index + 1) : ''
  newDatabase.llm_info.provider = provider
  newDatabase.llm_info.model_name = modelName
}

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
    await loadUpstreamSources()
  } catch {
    // 错误已在 store 中处理
  }
}

const navigateToDatabase = (databaseId) => {
  router.push({ path: `/database/${databaseId}` })
}

// 自动刷新（索引进行中）
let refreshInterval = null
const startAutoRefresh = () => {
  if (refreshInterval) return
  refreshInterval = setInterval(() => {
    const hasProcessing = (databases.value || []).some(
      (db) => getDbOverallStatus(db) === 'processing'
    )
    if (hasProcessing) {
      databaseStore.loadDatabases()
    } else {
      stopAutoRefresh()
    }
  }, 3000)
}

const stopAutoRefresh = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

watch(
  () => databases.value,
  (dbs) => {
    const hasProcessing = (dbs || []).some((db) => getDbOverallStatus(db) === 'processing')
    if (hasProcessing) startAutoRefresh()
    else stopAutoRefresh()
  },
  { deep: true }
)

watch(
  () => route.path,
  (newPath) => {
    if (newPath === '/database') {
      databaseStore.loadDatabases()
      loadUpstreamSources()
    }
  }
)

onMounted(() => {
  loadPositionTypes().then(() => {
    newDatabase.position = normalizePositionType(newDatabase.position, positionTypes.value).label
  })
  databaseStore.loadDatabases()
  loadUpstreamSources()
})

onUnmounted(() => {
  stopAutoRefresh()
  stopImportPoll()
})
</script>

<style lang="less" scoped>
// ===================== 页面容器 =====================
.database-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

// ===================== 顶栏 =====================
.page-topbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 20px 32px 16px;
  border-bottom: 1px solid var(--gray-100);
  flex-shrink: 0;
}

.topbar-left {
  .page-title {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0;
    color: var(--gray-1000);
  }

  .page-subtitle {
    font-size: 13px;
    color: var(--gray-500);
    margin: 6px 0 0;
  }
}

.topbar-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.import-progress {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 12px;
  font-size: 13px;
  color: var(--gray-600);
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: var(--gray-0);
  white-space: nowrap;
}

.import-progress-text {
  max-width: 420px;
  overflow: hidden;
  text-overflow: ellipsis;
}

// ===================== 按钮（深度覆盖 Ant Design） =====================
.topbar-actions,
.upstream-banner {
  :deep(.btn-secondary.ant-btn) {
    display: inline-flex;
    align-items: center;
    height: 34px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid var(--gray-200);
    background: var(--gray-0);
    color: var(--gray-700);
    border-radius: 0;
    box-shadow: none;

    &:hover,
    &:focus {
      border-color: var(--gray-500) !important;
      color: var(--gray-1000) !important;
    }
  }

  :deep(.btn-primary.ant-btn) {
    display: inline-flex;
    align-items: center;
    height: 34px;
    padding: 0 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 0;
    background: var(--main-color);
    border-color: var(--main-color);
    color: #fff;
    box-shadow: none;

    &:hover,
    &:focus {
      background: var(--main-700) !important;
      border-color: var(--main-700) !important;
      color: #fff !important;
    }
  }
}

// 上游横幅按钮单独覆盖
.upstream-banner {
  :deep(.btn-secondary.ant-btn) {
    &:hover,
    &:focus {
      background: var(--gray-0) !important;
    }
  }
}

// ===================== 筛选栏 =====================
.filter-bar {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--gray-200);
  padding: 24px 32px 0;
  margin-bottom: 22px;
  flex-shrink: 0;
}

.position-tabs {
  display: flex;
  flex: 1;
}

.position-tab {
  padding: 10px 20px;
  font-size: 14px;
  color: var(--gray-600);
  cursor: pointer;
  user-select: none;

  &:first-child {
    padding-left: 0;
  }

  &.active {
    font-weight: 700;
    color: var(--gray-1000);
    border-bottom: 2px solid var(--main-color);
    margin-bottom: -1px;
  }

  &:hover:not(.active) {
    color: var(--gray-1000);
  }
}

.filter-search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0;

  .search-icon {
    color: var(--gray-500);
    font-size: 14px;
  }

  .search-input {
    border: none;
    outline: none;
    font-size: 14px;
    color: var(--gray-1000);
    background: transparent;
    width: 160px;

    &::placeholder {
      color: var(--gray-500);
    }
  }
}

// ===================== 表格 =====================
.table-wrapper {
  flex: 1;
  overflow: auto;
  padding: 0 32px 24px;
}

.kb-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;

  thead tr {
    th {
      text-align: left;
      font-size: 11px;
      letter-spacing: 0.1em;
      color: var(--gray-500);
      font-weight: 700;
      padding: 9px 14px;
      border-bottom: 1px solid var(--gray-200);
      white-space: nowrap;

      &:first-child {
        padding-left: 0;
      }

      &:last-child {
        padding-right: 0;
      }

      &.sortable {
        cursor: pointer;
        user-select: none;

        &:hover {
          color: var(--gray-700);
        }
      }

      .sort-arrow {
        font-size: 10px;
        margin-left: 2px;
      }
    }
  }

  tbody tr {
    &:not(.upstream-row) {
      cursor: pointer;

      &:hover {
        background: var(--gray-50);
      }
    }

    td {
      padding: 11px 14px;
      border-bottom: 1px solid var(--gray-100);
      font-size: 13px;
      color: var(--gray-1000);
      vertical-align: middle;

      &:first-child {
        padding-left: 0;
      }

      &:last-child {
        padding-right: 0;
      }
    }
  }
}

// 列宽（对齐设计稿 [UI v3][2e]）
.col-name { width: auto; }
.col-position { width: 150px; }
.col-files { width: 110px; }
.col-chunks { width: 110px; }
.col-embedding { width: 190px; }
.col-last-index { width: 130px; }
.col-status { width: 110px; text-align: right; }

// 名称单元格
.db-name {
  font-weight: 700;
  font-size: 15px;
  color: var(--gray-1000);
}

.db-desc {
  font-size: 13px;
  color: var(--gray-600);
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}

// Embedding 单元格
.col-embedding {
  font-size: 13px;
}

// 状态 Badge
.status-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid var(--gray-200);
  color: var(--gray-600);

  &.status-indexed {
    background: var(--gray-100);
    color: var(--gray-1000);
    border-color: var(--gray-200);
  }

  &.status-processing {
    border-color: var(--main-color);
    color: var(--main-color);
  }

  &.status-failed {
    border-color: var(--color-error-500);
    color: var(--color-error-500);
  }

  &.status-partial {
    background: var(--color-warning-50);
    color: var(--color-warning-700);
    border-color: var(--color-warning-100);
  }

  &.status-empty {
    color: var(--gray-500);
    border-color: var(--gray-200);
  }
}

// ===================== 上游资料导入提示行 =====================
.upstream-row {
  cursor: default !important;

  &:hover {
    background: transparent !important;
  }

  td {
    padding: 0 !important;
    border-bottom: none !important;
  }
}

.upstream-banner {
  border: 1px dashed var(--gray-300);
  padding: 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.upstream-info {
  .upstream-title {
    font-weight: 700;
    font-size: 15px;
    color: var(--gray-1000);
  }

  .upstream-examples {
    font-size: 13px;
    color: var(--gray-600);
    margin-top: 4px;
  }
}

// ===================== 弹窗 =====================
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

  h3 {
    margin-top: 10px;
  }
}

// ===================== 加载状态 =====================
.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 300px;
  gap: 16px;
}

// ===================== 空状态 =====================
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
    color: var(--gray-1000);
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
</style>
