<script setup>
import { ref, onMounted, computed, provide, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  Plus,
  History,
  FileText,
  BookOpen,
  Code2,
  LibraryBig,
  Blocks,
  BarChart3,
  CircleCheck,
  Folder
} from 'lucide-vue-next'

import { useConfigStore } from '@/stores/config'
import { useDatabaseStore } from '@/stores/database'
import { useInfoStore } from '@/stores/info'
import { useTaskerStore } from '@/stores/tasker'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
import { interviewHistoryApi } from '@/apis/interview_history'
import UserInfoComponent from '@/components/UserInfoComponent.vue'
import DebugComponent from '@/components/DebugComponent.vue'
import TaskCenterDrawer from '@/components/TaskCenterDrawer.vue'
import SettingsModal from '@/components/SettingsModal.vue'

const configStore = useConfigStore()
const databaseStore = useDatabaseStore()
const infoStore = useInfoStore()
const taskerStore = useTaskerStore()
const userStore = useUserStore()
const { activeCount: activeCountRef, isDrawerOpen } = storeToRefs(taskerStore)

const route = useRoute()
const router = useRouter()

// Add state for debug modal
const showDebugModal = ref(false)

// Add state for settings modal
const showSettingsModal = ref(false)

// Provide settings modal methods to child components
const openSettingsModal = () => {
  showSettingsModal.value = true
}

// Handle debug modal close
const handleDebugModalClose = () => {
  showDebugModal.value = false
}

const getRemoteConfig = () => {
  configStore.refreshConfig()
}

const getRemoteDatabase = () => {
  databaseStore.loadDatabases()
}

onMounted(async () => {
  // 加载信息配置
  await infoStore.loadInfoConfig()
  // 加载其他配置
  getRemoteConfig()
  if (userStore.isAdmin) {
    getRemoteDatabase()
  }
  // 预加载任务数据，确保任务中心打开时有内容
  if (userStore.isAdmin) {
    taskerStore.loadTasks()
  }
  loadRecords()
})

const activeTaskCount = computed(() => activeCountRef.value || 0)
const organizationName = computed(() => {
  const name = String(infoStore.organization?.name || '').trim()
  if (!name || /^ai[\s-]*interview$/i.test(name)) {
    return '伯乐 Bole'
  }
  return name
})
const sidebarBrand = computed(() => {
  const name = organizationName.value.trim()
  if (name === '伯乐 Bole' || name === '伯乐' || name.toLowerCase() === 'bole') {
    return { leading: '伯乐', trailing: 'Bole' }
  }
  return { leading: name, trailing: '' }
})

// 主导航项
const mainList = computed(() => [
  {
    name: '开始面试',
    path: '/agent',
    matchNames: [
      'AgentComp',
      'AgentInterviewComp',
      'AgentVoiceInterviewComp',
      'InterviewCodingWorkbench',
      'InterviewResultPage'
    ],
    icon: Plus
  },
  {
    name: '面试记录',
    path: '/agent/records',
    matchNames: ['InterviewRecordsPage'],
    icon: History
  },
  {
    name: '我的简历',
    path: '/resume',
    matchNames: ['ResumeListComp', 'ResumeDetailComp'],
    icon: FileText
  },
  {
    name: '知识学习',
    path: '/learn',
    matchNames: ['LearnHomePage', 'LearnDatabasePage', 'LearnDocumentPage'],
    icon: BookOpen
  },
  {
    name: '代码练习',
    path: '/practice',
    matchNames: ['PracticeHomePage', 'PracticeTopicPage', 'PracticeProblemPage'],
    icon: Code2
  }
])

// 运营（仅管理员可见）
const opsList = computed(() => {
  if (!userStore.isAdmin) return []
  return [
    {
      name: '知识库',
      path: '/database',
      matchNames: ['DatabaseComp', 'DatabaseInfoComp'],
      icon: LibraryBig
    },
    {
      name: '题库管理',
      path: '/problemsets',
      matchNames: ['ProblemSetManageComp'],
      icon: Blocks
    },
    {
      name: '数据看板',
      path: '/dashboard',
      matchNames: ['DashboardComp'],
      icon: BarChart3
    }
  ]
})

const isNavItemActive = (item) => {
  return Array.isArray(item.matchNames) ? item.matchNames.includes(route.name) : route.path === item.path
}

// ------- 侧栏面试记录树 -------
const RECORD_PREVIEW_COUNT = 4

const records = ref([])
const expandedGroups = ref({})

const decodeHtmlEntities = (value) => {
  const text = String(value || '')
  if (typeof window === 'undefined' || !text.includes('&')) return text
  const doc = new DOMParser().parseFromString(text, 'text/html')
  return doc.body.textContent || ''
}

const loadRecords = async () => {
  if (!userStore.isLoggedIn) return
  try {
    // 不传 user_id，后端默认返回当前登录用户的记录
    const payload = await interviewHistoryApi.getHistory()
    records.value = (payload?.records || []).map((r) => ({
      ...r,
      title: decodeHtmlEntities(r?.title),
      position: decodeHtmlEntities(r?.position),
      round: decodeHtmlEntities(r?.round)
    }))
  } catch (error) {
    console.error('加载侧栏面试记录失败:', error)
  }
}

// 面试结束、或进入记录页时刷新侧栏，避免展示过期数据
watch(
  () => route.name,
  (name) => {
    if (name === 'InterviewResultPage' || name === 'InterviewRecordsPage') {
      loadRecords()
    }
  }
)

const recordGroups = computed(() => {
  const groups = []
  const indexByPosition = new Map()
  records.value.forEach((record) => {
    const position = record.position || '未分类'
    if (!indexByPosition.has(position)) {
      indexByPosition.set(position, groups.length)
      groups.push({ position, items: [] })
    }
    groups[indexByPosition.get(position)].items.push(record)
  })
  return groups.map((group) => ({
    ...group,
    visibleItems: expandedGroups.value[group.position]
      ? group.items
      : group.items.slice(0, RECORD_PREVIEW_COUNT),
    hiddenCount: Math.max(0, group.items.length - RECORD_PREVIEW_COUNT)
  }))
})

const toggleGroup = (position) => {
  expandedGroups.value = {
    ...expandedGroups.value,
    [position]: !expandedGroups.value[position]
  }
}

const recordLabel = (record) => {
  const parts = [record.round, record.title].filter(Boolean)
  return parts.length ? parts.join(' · ') : '未命名面试'
}

const recordScore = (record) => {
  const score = record.overall_score
  return typeof score === 'number' && Number.isFinite(score) ? `${Math.round(score)}` : ''
}

const isRecordActive = (record) => String(route.query.threadId || '') === String(record.thread_id)

const openRecord = (record) => {
  if (record.status === 'completed') {
    router.push({
      name: 'InterviewResultPage',
      query: { threadId: record.thread_id, position: record.position, round: record.round }
    })
    return
  }
  const isVoice = record.interview_mode === 'voice'
  router.push({
    name: isVoice ? 'AgentVoiceInterviewComp' : 'AgentInterviewComp',
    query: {
      threadId: record.thread_id,
      mode: isVoice ? 'voice' : 'text',
      position: record.position,
      round: record.round
    }
  })
}

// Provide settings modal methods to child components
provide('settingsModal', {
  openSettingsModal
})
</script>

<template>
  <div class="app-layout">
    <nav class="rail">
      <div class="rail-brand">
        <router-link to="/" class="rail-brand-link">
          <img :src="infoStore.organization.avatar" alt="" />
          <span class="rail-brand-text">
            <span class="rail-brand-leading">{{ sidebarBrand.leading }}</span>
            <span v-if="sidebarBrand.trailing" class="rail-brand-trailing">
              {{ sidebarBrand.trailing }}
            </span>
          </span>
        </router-link>
      </div>

      <div class="rail-body">
        <RouterLink
          v-for="item in mainList"
          :key="item.path"
          :to="item.path"
          class="rail-item"
          :class="{ active: isNavItemActive(item) }"
        >
          <component class="rail-icon" :is="item.icon" :size="16" />
          <span class="rail-item-text">{{ item.name }}</span>
        </RouterLink>

        <div class="rail-group-label">面试记录</div>
        <div class="rail-records">
          <template v-for="group in recordGroups" :key="group.position">
            <div class="rail-folder">
              <Folder class="rail-icon rail-icon-muted" :size="16" />
              <span class="rail-item-text">{{ group.position }}</span>
            </div>
            <div
              v-for="record in group.visibleItems"
              :key="record.thread_id"
              class="rail-record"
              :class="{ active: isRecordActive(record) }"
              @click="openRecord(record)"
            >
              <span class="rail-record-title">{{ recordLabel(record) }}</span>
              <span v-if="recordScore(record)" class="rail-record-score">
                {{ recordScore(record) }}
              </span>
              <span v-else class="rail-record-dot"></span>
            </div>
            <div v-if="group.hiddenCount" class="rail-more" @click="toggleGroup(group.position)">
              {{ expandedGroups[group.position] ? '收起' : `展开显示（${group.hiddenCount}）` }}
            </div>
          </template>
          <div v-if="!recordGroups.length" class="rail-empty">暂无面试记录</div>
        </div>

        <template v-if="opsList.length">
          <div class="rail-group-label">运营</div>
          <RouterLink
            v-for="item in opsList"
            :key="item.path"
            :to="item.path"
            class="rail-item"
            :class="{ active: isNavItemActive(item) }"
          >
            <component class="rail-icon" :is="item.icon" :size="16" />
            <span class="rail-item-text">{{ item.name }}</span>
          </RouterLink>
          <div
            class="rail-item rail-task"
            :class="{ active: isDrawerOpen }"
            @click="taskerStore.openDrawer()"
          >
            <a-badge :count="activeTaskCount" :overflow-count="99" size="small">
              <CircleCheck class="rail-icon" :size="16" />
            </a-badge>
            <span class="rail-item-text">任务中心</span>
          </div>
        </template>
      </div>

      <div class="rail-user">
        <UserInfoComponent :show-role="true" />
      </div>
    </nav>

    <main id="app-router-view" class="app-router-view">
      <router-view v-slot="{ Component, route }">
        <keep-alive v-if="route.meta.keepAlive !== false">
          <component :is="Component" />
        </keep-alive>
        <component :is="Component" v-else />
      </router-view>
    </main>

    <!-- Debug Modal -->
    <a-modal
      v-model:open="showDebugModal"
      title="调试面板"
      width="90%"
      :footer="null"
      @cancel="handleDebugModalClose"
      :maskClosable="true"
      :destroyOnClose="true"
      class="debug-modal"
    >
      <DebugComponent />
    </a-modal>
    <TaskCenterDrawer />
    <SettingsModal v-model:visible="showSettingsModal" @close="() => (showSettingsModal = false)" />
  </div>
</template>

<style lang="less" scoped>
@rail-width: 260px;
@rail-pad: 18px;

.app-layout {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100vh;
  min-width: var(--min-width);
}

.app-router-view {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  max-width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
}

.rail {
  display: flex;
  flex-direction: column;
  flex: 0 0 @rail-width;
  width: @rail-width;
  height: 100%;
  box-sizing: border-box;
  background-color: var(--bg-sider);
  border-right: 1px solid var(--gray-200);
  color: var(--gray-1000);
  overflow: hidden;
}

.rail-brand {
  padding: 14px @rail-pad 12px;

  .rail-brand-link {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    text-decoration: none;
    color: inherit;
  }

  img {
    width: 26px;
    height: 26px;
    flex-shrink: 0;
  }

  .rail-brand-text {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
    white-space: nowrap;
  }

  .rail-brand-leading {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--gray-1000);
  }

  .rail-brand-trailing {
    font-size: 13px;
    font-weight: 600;
    color: var(--gray-600);
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.rail-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.rail-item {
  display: flex;
  align-items: center;
  gap: 11px;
  height: 34px;
  flex: 0 0 34px;
  padding: 0 @rail-pad;
  box-sizing: border-box;
  font-size: 14px;
  color: var(--gray-700);
  text-decoration: none;
  cursor: pointer;

  &:hover {
    background-color: var(--gray-50);
  }

  &.active {
    background-color: var(--gray-100);
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.rail-item-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rail-icon {
  flex: 0 0 16px;
}

.rail-icon-muted {
  color: var(--gray-500);
}

.rail-group-label {
  padding: 22px @rail-pad 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--gray-500);
}

.rail-records {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.rail-folder {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px @rail-pad;
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-1000);
}

.rail-record {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px @rail-pad 5px 38px;
  font-size: 13px;
  color: var(--gray-600);
  white-space: nowrap;
  overflow: hidden;
  cursor: pointer;

  &:hover {
    background-color: var(--gray-50);
  }

  &.active {
    background-color: var(--gray-100);
    color: var(--gray-1000);
    font-weight: 700;
  }
}

.rail-record-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rail-record-score {
  font-size: 11px;
  color: var(--gray-500);
  flex-shrink: 0;
}

.rail-record-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  background-color: var(--main-600);
}

.rail-more {
  padding: 4px @rail-pad 4px 38px;
  font-size: 13px;
  color: var(--gray-500);
  cursor: pointer;

  &:hover {
    color: var(--gray-700);
  }
}

.rail-empty {
  padding: 4px @rail-pad 4px 38px;
  font-size: 13px;
  color: var(--gray-500);
}

.rail-task {
  :deep(.ant-badge) {
    display: flex;
    align-items: center;
  }
}

.rail-user {
  border-top: 1px solid var(--gray-200);
  padding: 12px @rail-pad;
}
</style>
