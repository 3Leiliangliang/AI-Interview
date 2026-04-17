import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'
import { useUserStore } from '@/stores/user'
import { useAgentStore } from '@/stores/agent'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'main',
      component: BlankLayout,
      children: [
        {
          path: '',
          name: 'Home',
          component: () => import('../views/HomeView.vue'),
          meta: { keepAlive: true, requiresAuth: false }
        }
      ]
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/agent',
      name: 'AgentMain',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'AgentComp',
          component: () => import('../views/AgentView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        },
        {
          path: 'interview',
          name: 'AgentInterviewComp',
          component: () => import('../views/InterviewSessionView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: 'interview/voice',
          name: 'AgentVoiceInterviewComp',
          component: () => import('../views/VoiceInterviewView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: 'interview/code',
          name: 'InterviewCodingWorkbench',
          component: () => import('../views/InterviewCodingView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: 'interview/result',
          name: 'InterviewResultPage',
          component: () => import('../views/InterviewResultView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: 'records',
          name: 'InterviewRecordsPage',
          component: () => import('../views/InterviewRecordsView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: ':agent_id',
          redirect: '/agent'
        }
      ]
    },
    {
      path: '/resume',
      name: 'resume',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ResumeListComp',
          component: () => import('../views/MyResumeView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: ':resume_id',
          name: 'ResumeDetailComp',
          component: () => import('../views/ResumeDetailView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
    {
      path: '/learn',
      name: 'learn',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'LearnHomePage',
          component: () => import('../views/LearnHomeView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: ':db_id',
          name: 'LearnDatabasePage',
          component: () => import('../views/LearnDatabaseView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: ':db_id/doc/:file_id',
          name: 'LearnDocumentPage',
          component: () => import('../views/LearnDocumentView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
    {
      path: '/practice',
      name: 'practice',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'PracticeHomePage',
          component: () => import('../views/PracticeHomeView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: 'problem/:problem_ref',
          name: 'PracticeProblemPage',
          component: () => import('../views/PracticeProblemView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        },
        {
          path: ':topic_key',
          name: 'PracticeTopicPage',
          component: () => import('../views/PracticeHomeView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
    {
      path: '/oj',
      name: 'oj',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'OJWorkbenchComp',
          component: () => import('../views/InterviewCodingView.vue'),
          meta: { keepAlive: false, requiresAuth: true }
        }
      ]
    },
    {
      path: '/database',
      name: 'database',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'DatabaseComp',
          component: () => import('../views/DataBaseView.vue'),
          meta: { keepAlive: true, requiresAuth: true, requiresAdmin: true }
        },
        {
          path: ':database_id',
          name: 'DatabaseInfoComp',
          component: () => import('../views/DataBaseInfoView.vue'),
          meta: { keepAlive: false, requiresAuth: true, requiresAdmin: true }
        }
      ]
    },
    {
      path: '/problemsets',
      name: 'problemsets',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ProblemSetManageComp',
          component: () => import('../views/ProblemSetManageView.vue'),
          meta: { keepAlive: false, requiresAuth: true, requiresAdmin: true }
        }
      ]
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'DashboardComp',
          component: () => import('../views/DashboardView.vue'),
          meta: { keepAlive: false, requiresAuth: true, requiresAdmin: true }
        }
      ]
    },
    {
      path: '/extensions',
      name: 'extensions',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ExtensionsComp',
          component: () => import('../views/ExtensionsView.vue'),
          meta: {
            keepAlive: false,
            requiresAuth: true,
            requiresAdmin: true,
            requiresSuperAdmin: true
          }
        }
      ]
    },
    {
      path: '/skills',
      name: 'skills',
      redirect: '/extensions'
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('../views/EmptyView.vue'),
      meta: { requiresAuth: false }
    }
  ]
})

// 全局前置守卫
router.beforeEach(async (to, from, next) => {
  // 检查路由是否需要认证
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth === true)
  const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)
  const requiresSuperAdmin = to.matched.some((record) => record.meta.requiresSuperAdmin)

  const userStore = useUserStore()

  // 如果有 token 但用户信息未加载，先获取用户信息
  if (userStore.token && !userStore.userId) {
    try {
      await userStore.getCurrentUser()
    } catch (error) {
      // 如果获取用户信息失败（如 token 过期），清除 token
      console.error('获取用户信息失败:', error)
      userStore.logout()
    }
  }

  const isLoggedIn = userStore.isLoggedIn
  const isAdmin = userStore.isAdmin
  const isSuperAdmin = userStore.isSuperAdmin

  // 如果路由需要认证但用户未登录
  if (requiresAuth && !isLoggedIn) {
    // 保存尝试访问的路径，登录后跳转
    sessionStorage.setItem('redirect', to.fullPath)
    next('/login')
    return
  }

  // 如果路由需要管理员权限但用户不是管理员
  if (requiresAdmin && !isAdmin) {
    // 如果是普通用户，跳转到默认智能体页面
    try {
      const agentStore = useAgentStore()
      // 等待 store 初始化完成
      if (!agentStore.isInitialized) {
        await agentStore.initialize()
      }

      const defaultAgent = agentStore.defaultAgent
      if (defaultAgent && defaultAgent.id) {
        next(`/agent/${defaultAgent.id}`)
      } else {
        // 如果没有默认智能体，可以考虑跳转到第一个可用的智能体，或者一个特定的页面
        const agentIds = Object.keys(agentStore.agents)
        if (agentIds.length > 0) {
          next(`/agent/${agentIds[0]}`)
        } else {
          // 没有可用的智能体，跳转到聊天页
          next('/agent')
        }
      }
    } catch (error) {
      console.error('获取智能体信息失败:', error)
      next('/agent')
    }
    return
  }

  // 如果路由需要超级管理员权限但用户不是超级管理员
  if (requiresSuperAdmin && !isSuperAdmin) {
    try {
      const agentStore = useAgentStore()
      if (!agentStore.isInitialized) {
        await agentStore.initialize()
      }
      const defaultAgent = agentStore.defaultAgent
      if (defaultAgent && defaultAgent.id) {
        next(`/agent/${defaultAgent.id}`)
      } else {
        next('/agent')
      }
    } catch (error) {
      console.error('获取智能体信息失败:', error)
      next('/agent')
    }
    return
  }

  // 如果用户已登录但访问登录页
  if (to.path === '/login' && isLoggedIn) {
    next('/')
    return
  }

  // 其他情况正常导航
  next()
})

export default router
