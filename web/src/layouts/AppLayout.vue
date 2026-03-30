<script setup>
import { ref, reactive, onMounted, computed, provide } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import {
  Bot,
  LibraryBig,
  BarChart3,
  CircleCheck,
  Blocks,
  FileText,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-vue-next'

import { useConfigStore } from '@/stores/config'
import { useDatabaseStore } from '@/stores/database'
import { useInfoStore } from '@/stores/info'
import { useTaskerStore } from '@/stores/tasker'
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'
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
const APP_LAYOUT_SIDEBAR_COLLAPSED_KEY = 'app_layout_sidebar_collapsed'

const layoutSettings = reactive({
  showDebug: false,
  useTopBar: false // 是否使用顶栏
})

// Add state for GitHub stars
const githubStars = ref(0)
const isLoadingStars = ref(false)

// Add state for debug modal
const showDebugModal = ref(false)

// Add state for settings modal
const showSettingsModal = ref(false)
const isSidebarCollapsed = ref(localStorage.getItem(APP_LAYOUT_SIDEBAR_COLLAPSED_KEY) === 'true')

// Provide settings modal methods to child components
const openSettingsModal = () => {
  showSettingsModal.value = true
}

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
  localStorage.setItem(APP_LAYOUT_SIDEBAR_COLLAPSED_KEY, String(isSidebarCollapsed.value))
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

// Fetch GitHub stars count
const fetchGithubStars = async () => {
  try {
    isLoadingStars.value = true
    // 公共API，可以直接使用fetch
    const response = await fetch('https://api.github.com/repos/xerrors/Bole')
    const data = await response.json()
    githubStars.value = data.stargazers_count
  } catch (error) {
    console.error('获取GitHub stars失败:', error)
  } finally {
    isLoadingStars.value = false
  }
}

onMounted(async () => {
  // 加载信息配置
  await infoStore.loadInfoConfig()
  // 加载其他配置
  getRemoteConfig()
  getRemoteDatabase()
  fetchGithubStars() // Fetch GitHub stars on mount
  // 预加载任务数据，确保任务中心打开时有内容
  taskerStore.loadTasks()
})

// 打印当前页面的路由信息，使用 vue3 的 setup composition API
const route = useRoute()
console.log(route)

const activeTaskCount = computed(() => activeCountRef.value || 0)
const sidebarToggleIcon = computed(() =>
  isSidebarCollapsed.value ? PanelLeftOpen : PanelLeftClose
)
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
    return {
      eyebrow: '',
      leading: '伯乐',
      trailing: 'Bole'
    }
  }
  return {
    eyebrow: '',
    leading: name,
    trailing: ''
  }
})

const showSidebarCollapseBtn = computed(() => {
  if (layoutSettings.useTopBar) {
    return false
  }
  return !route.path.startsWith('/dashboard')
})

// 下面是导航菜单部分，添加智能体项
const mainList = computed(() => {
  const items = [
    {
      name: '模拟面试',
      path: '/agent',
      icon: Bot,
      activeIcon: Bot
    },
    {
      name: '我的简历',
      path: '/resume',
      icon: FileText,
      activeIcon: FileText
    },
    {
      name: '知识库',
      path: '/database',
      icon: LibraryBig,
      activeIcon: LibraryBig
    }
  ]

  items.push({
    name: 'Dashboard',
    path: '/dashboard',
    icon: BarChart3,
    activeIcon: BarChart3
  })

  return items
})

// Provide settings modal methods to child components
provide('settingsModal', {
  openSettingsModal
})
</script>

<template>
  <div class="app-layout" :class="{ 'use-top-bar': layoutSettings.useTopBar }">
    <div
      class="header"
      :class="{ 'top-bar': layoutSettings.useTopBar, collapsed: isSidebarCollapsed }"
    >
      <div class="header-top">
        <div class="logo circle">
          <router-link to="/">
            <img :src="infoStore.organization.avatar" />
            <span v-if="!isSidebarCollapsed" class="logo-title">
              <span v-if="sidebarBrand.eyebrow" class="logo-eyebrow">{{ sidebarBrand.eyebrow }}</span>
              <span class="logo-title-main">
                <span class="logo-title-leading">{{ sidebarBrand.leading }}</span>
                <span v-if="sidebarBrand.trailing" class="logo-title-trailing">
                  {{ sidebarBrand.trailing }}
                </span>
              </span>
            </span>
          </router-link>
        </div>
        <button
          v-if="showSidebarCollapseBtn"
          type="button"
          class="collapse-btn"
          @click="toggleSidebar"
        >
          <component :is="sidebarToggleIcon" :size="18" />
        </button>
      </div>
      <div class="nav">
        <!-- 使用mainList渲染导航项 -->
        <RouterLink
          v-for="(item, index) in mainList"
          :key="index"
          :to="item.path"
          v-show="!item.hidden"
          class="nav-item"
          active-class="active"
        >
          <a-tooltip placement="right" :title="isSidebarCollapsed ? item.name : null">
            <span class="nav-item-inner">
              <component
                class="icon"
                :is="route.path.startsWith(item.path) ? item.activeIcon : item.icon"
                size="22"
              />
              <span v-if="!isSidebarCollapsed" class="text">{{ item.name }}</span>
            </span>
          </a-tooltip>
        </RouterLink>
        <div
          class="nav-item task-center"
          :class="{ active: isDrawerOpen }"
          @click="taskerStore.openDrawer()"
        >
          <a-tooltip placement="right" :title="isSidebarCollapsed ? '任务中心' : null">
            <span class="nav-item-inner">
              <a-badge
                :count="activeTaskCount"
                :overflow-count="99"
                class="task-center-badge"
                size="small"
              >
                <CircleCheck class="icon" size="22" />
              </a-badge>
              <span v-if="!isSidebarCollapsed" class="text">任务中心</span>
            </span>
          </a-tooltip>
        </div>
      </div>
      <div class="fill"></div>
      <!-- 用户信息组件 -->
      <div class="nav-item user-info">
        <UserInfoComponent :show-role="!isSidebarCollapsed" />
      </div>
    </div>
    <router-view v-slot="{ Component, route }" id="app-router-view">
      <keep-alive v-if="route.meta.keepAlive !== false">
        <component :is="Component" />
      </keep-alive>
      <component :is="Component" v-else />
    </router-view>

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
// Less 变量定义
@header-width: 220px;
@header-width-collapsed: 64px;

.app-layout {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100vh;
  min-width: var(--min-width);
}

div.header,
#app-router-view {
  height: 100%;
  max-width: 100%;
  user-select: none;
}

#app-router-view {
  flex: 1 1 auto;
  overflow-y: auto;
}

.header {
  display: flex;
  flex-direction: column;
  flex: 0 0 @header-width;
  justify-content: flex-start;
  align-items: stretch;
  position: relative;
  overflow: visible;
  background-color: var(--bg-sider);
  height: 100%;
  width: @header-width;
  padding: 12px 10px;
  border-right: 1px solid var(--main-40);
  transition:
    width 0.2s ease,
    flex-basis 0.2s ease,
    padding 0.2s ease;

  &.collapsed {
    flex-basis: @header-width-collapsed;
    width: @header-width-collapsed;
    padding: 12px 8px;

    .header-top {
      flex-direction: column;
      justify-content: center;
      align-items: center;
      gap: 8px;
      min-height: auto;
      margin-bottom: 14px;
    }

    .logo {
      width: 100%;

      > a {
        justify-content: center;
      }
    }

    .collapse-btn {
      position: static;
      margin-left: 0;
    }

    .nav-item {
      width: 100%;
      justify-content: center;
      padding: 10px 0;

      .nav-item-inner {
        justify-content: center;
      }
    }

    .user-info {
      justify-content: center;
    }
  }

  .header-top {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
    margin-bottom: 20px;
    min-height: 36px;
  }

  .nav {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    position: relative;
    gap: 8px;
  }

  .fill {
    flex-grow: 1;
  }

  .logo {
    min-width: 0;

    img {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      flex-shrink: 0;
    }

    & > a {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      font-size: 15px;
      font-weight: 600;
      color: var(--gray-900);
      min-width: 0;
    }

    .logo-title {
      display: flex;
      flex-direction: column;
      min-width: 0;
      overflow: hidden;
    }

    .logo-eyebrow {
      font-size: 10px;
      line-height: 1;
      letter-spacing: 0.16em;
      color: var(--main-color);
      font-weight: 700;
      margin-bottom: 4px;
      white-space: nowrap;
    }

    .logo-title-main {
      display: flex;
      align-items: baseline;
      gap: 6px;
      min-width: 0;
      white-space: nowrap;
    }

    .logo-title-leading {
      font-size: 18px;
      line-height: 1;
      font-weight: 800;
      letter-spacing: 0.04em;
      color: var(--gray-1000);
    }

    .logo-title-trailing {
      font-size: 15px;
      line-height: 1;
      font-weight: 600;
      letter-spacing: 0.01em;
      color: var(--gray-700);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .collapse-btn {
    position: relative;
    margin-left: auto;
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--main-100);
    border-radius: 10px;
    background: var(--main-0);
    color: var(--gray-700);
    cursor: pointer;
    transition:
      background-color 0.2s ease,
      color 0.2s ease,
      border-color 0.2s ease;

    &:hover {
      background-color: var(--main-20);
      border-color: var(--main-200);
      color: var(--main-color);
    }
  }

  .nav-item {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 10px;
    width: 100%;
    min-height: 42px;
    padding: 10px 12px;
    border: 1px solid transparent;
    border-radius: 12px;
    background-color: transparent;
    color: var(--gray-1000);
    font-size: 14px;
    transition:
      background-color 0.2s ease-in-out,
      color 0.2s ease-in-out,
      border-color 0.2s ease-in-out;
    margin: 0;
    text-decoration: none;
    cursor: pointer;
    outline: none;
    box-sizing: border-box;

    .text {
      font-weight: 500;
      white-space: nowrap;
    }

    .nav-item-inner {
      width: 100%;
      display: inline-flex;
      align-items: center;
      gap: 10px;
    }

    & > svg:focus {
      outline: none;
    }
    & > svg:focus-visible {
      outline: none;
    }

    &.active {
      background-color: var(--main-20);
      border-color: var(--main-100);
      font-weight: bold;
      color: var(--main-color);
    }

    &.warning {
      color: var(--color-error-500);
    }

    &:hover {
      background-color: var(--main-10);
      color: var(--main-color);
    }

    &.github {
      padding: 10px 12px;
      margin-bottom: 16px;
      &:hover {
        background-color: transparent;
        border: 1px solid transparent;
      }

      .github-link {
        display: flex;
        flex-direction: column;
        align-items: center;
        color: inherit;
      }

      .github-stars {
        display: flex;
        align-items: center;
        font-size: 12px;
        margin-top: 4px;

        .star-icon {
          color: var(--color-warning-500);
          font-size: 12px;
          margin-right: 2px;
        }

        .star-count {
          font-weight: 600;
        }
      }
    }

    &.api-docs {
      padding: 10px 12px;
    }
    &.docs {
      display: none;
    }
    &.task-center {
      .task-center-badge {
        display: flex;
        align-items: center;
        justify-content: center;
      }
    }

    &.theme-toggle-nav {
      .theme-toggle-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;
        cursor: pointer;
        color: var(--gray-1000);
        transition: color 0.2s ease-in-out;

        &:hover {
          color: var(--main-color);
        }
      }
    }
    &.user-info {
      margin-bottom: 8px;
      padding: 8px 10px;
    }
  }
}

.app-layout.use-top-bar {
  flex-direction: column;
}

.header.top-bar {
  flex-direction: row;
  flex: 0 0 50px;
  width: 100%;
  height: 50px;
  border-right: none;
  border-bottom: 1px solid var(--main-40);
  background-color: var(--main-20);
  padding: 0 20px;
  gap: 24px;

  .logo {
    width: fit-content;
    height: 28px;
    margin-right: 16px;
    display: flex;
    align-items: center;

    a {
      display: flex;
      align-items: center;
      text-decoration: none;
      color: inherit;
    }

    img {
      width: 28px;
      height: 28px;
      margin-right: 8px;
    }
  }

  .nav {
    flex-direction: row;
    height: auto;
    gap: 20px;
  }

  .nav-item {
    flex-direction: row;
    width: auto;
    padding: 4px 16px;
    margin: 0;

    .icon {
      margin-right: 8px;
      font-size: 15px; // 减小图标大小
      border: none;
      outline: none;

      &:focus,
      &:active {
        border: none;
        outline: none;
      }
    }

    .text {
      margin-top: 0;
      font-size: 15px;
    }

    &.github {
      padding: 8px 12px;

      .icon {
        margin-right: 0;
        font-size: 18px;
      }

      &.active {
        color: var(--main-color);
      }

      a {
        display: flex;
        align-items: center;
      }

      .github-stars {
        display: flex;
        align-items: center;
        margin-left: 6px;

        .star-icon {
          color: var(--color-warning-500);
          font-size: 14px;
          margin-right: 2px;
        }
      }
    }

    &.theme-toggle-nav {
      padding: 8px 12px;

      .theme-toggle-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--gray-1000);
        transition: color 0.2s ease-in-out;
        cursor: pointer;

        &:hover {
          color: var(--main-color);
        }
      }

      &.active {
        .theme-toggle-icon {
          color: var(--main-color);
        }
      }
    }
  }
}
</style>
