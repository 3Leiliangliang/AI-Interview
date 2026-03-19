<template>
  <div class="home-page">
    <div v-if="isLoading" class="loading-container">
      <a-spin size="large" />
      <p class="loading-text">正在连接服务...</p>
    </div>

    <div v-else-if="error" class="error-container">
      <a-result status="error" :title="error.title" :sub-title="error.message">
        <template #extra>
          <a-button type="primary" @click="retryLoad">重试</a-button>
        </template>
      </a-result>
    </div>

    <template v-else>
      <header class="page-header">
        <div class="brand">
          <img
            v-if="infoStore.organization.logo"
            :src="infoStore.organization.logo"
            :alt="infoStore.organization.name"
            class="brand-logo"
          />
          <div class="brand-meta">
            <div class="brand-name">{{ infoStore.organization.name || 'AI Interview' }}</div>
            <div class="brand-desc">AI 模拟面试系统</div>
          </div>
        </div>
        <UserInfoComponent :show-button="true" />
      </header>

      <main class="page-main">
        <section class="hero-section">
          <div class="hero-content">
            <div class="hero-badge">
              <Sparkles :size="14" />
              <span>面向真实求职场景的 AI 面试体验</span>
            </div>

            <h1 class="hero-title">
              上传简历、选择岗位与轮次，
              <br />
              立即开始一轮模拟面试
            </h1>

            <p class="hero-subtitle">
              系统会先读取你的简历，再由面试官 Agent 自动发起提问。支持岗位配置、轮次切换、逐轮追问、结束评分与面试记录查看。
            </p>

            <div class="hero-actions">
              <button class="primary-btn" type="button" @click="goToInterview">
                <PlayCircle :size="18" />
                <span>开始模拟面试</span>
              </button>
              <button class="secondary-btn" type="button" @click="goToResumeCenter">
                <FileText :size="18" />
                <span>我的简历</span>
              </button>
            </div>

            <div class="hero-points">
              <div v-for="item in heroPoints" :key="item" class="hero-point">
                <CheckCircle2 :size="16" />
                <span>{{ item }}</span>
              </div>
            </div>
          </div>

          <div class="hero-panel">
            <div class="panel-card primary-card">
              <div class="panel-label">当前系统能力</div>
              <div class="panel-title">AI 面试官 + 简历知识库</div>
              <p class="panel-text">
                当前会话可直接读取上传简历；如果当前线程没有附件，面试官会继续从“我的简历”中读取最近上传的简历内容。
              </p>
            </div>

            <div class="panel-grid">
              <div v-for="item in stats" :key="item.label" class="panel-card stat-card">
                <div class="stat-icon">
                  <component :is="item.icon" :size="18" />
                </div>
                <div class="stat-meta">
                  <div class="stat-value">{{ item.value }}</div>
                  <div class="stat-label">{{ item.label }}</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="section-block">
          <div class="section-heading">
            <div class="section-title">你现在可以怎么用</div>
            <div class="section-desc">首页、配置页和面试页已经围绕模拟面试重构。</div>
          </div>

          <div class="feature-grid">
            <div v-for="item in featureCards" :key="item.title" class="feature-card">
              <div class="feature-icon">
                <component :is="item.icon" :size="20" />
              </div>
              <div class="feature-title">{{ item.title }}</div>
              <div class="feature-desc">{{ item.description }}</div>
            </div>
          </div>
        </section>

        <section class="section-block">
          <div class="section-heading">
            <div class="section-title">使用流程</div>
            <div class="section-desc">按照当前系统设计，完整面试链路分为四步。</div>
          </div>

          <div class="flow-list">
            <div v-for="(item, index) in flowSteps" :key="item.title" class="flow-card">
              <div class="flow-index">0{{ index + 1 }}</div>
              <div class="flow-body">
                <div class="flow-title">{{ item.title }}</div>
                <div class="flow-desc">{{ item.description }}</div>
              </div>
            </div>
          </div>
        </section>

        <section class="section-block">
          <div class="section-heading">
            <div class="section-title">支持的面试配置</div>
            <div class="section-desc">可先选择岗位、轮次，再进入面试界面。</div>
          </div>

          <div class="config-layout">
            <div class="config-card">
              <div class="config-title">岗位方向</div>
              <div class="tag-list">
                <span v-for="item in positions" :key="item" class="config-tag">{{ item }}</span>
              </div>
            </div>

            <div class="config-card">
              <div class="config-title">面试轮次</div>
              <div class="tag-list">
                <span v-for="item in rounds" :key="item" class="config-tag">{{ item }}</span>
              </div>
            </div>

            <div class="config-card">
              <div class="config-title">结果反馈</div>
              <div class="feedback-list">
                <div v-for="item in feedbackItems" :key="item" class="feedback-item">
                  <CheckCircle2 :size="15" />
                  <span>{{ item }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer class="page-footer">
        <p>{{ infoStore.footer?.copyright || '© 2026 AI Interview' }}</p>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  PlayCircle,
  FileText,
  Sparkles,
  CheckCircle2,
  BriefcaseBusiness,
  ClipboardList,
  MessageSquareQuote,
  Database,
  FolderClock,
  Gauge
} from 'lucide-vue-next'

import UserInfoComponent from '@/components/UserInfoComponent.vue'
import { useUserStore } from '@/stores/user'
import { useInfoStore } from '@/stores/info'
import { healthApi } from '@/apis/system_api'

const router = useRouter()
const userStore = useUserStore()
const infoStore = useInfoStore()

const isLoading = ref(true)
const error = ref(null)

const heroPoints = [
  '支持上传 PDF 简历并统一管理',
  '岗位 / 轮次配置后自动开始面试',
  '面试结束后输出评分卡与反馈'
]

const stats = [
  { label: '岗位方向', value: '7+', icon: BriefcaseBusiness },
  { label: '面试轮次', value: '3', icon: ClipboardList },
  { label: '追问方式', value: '逐轮', icon: MessageSquareQuote },
  { label: '面试记录', value: '侧边栏', icon: FolderClock }
]

const featureCards = [
  {
    title: '面试配置页',
    description: '先选择目标岗位和面试轮次，再进入正式面试界面。',
    icon: BriefcaseBusiness
  },
  {
    title: '我的简历',
    description: '简历集中管理，面试官可优先读取当前会话附件，或从“我的简历”继续提问。',
    icon: Database
  },
  {
    title: 'AI 面试官',
    description: '自动发起第一问，候选人回答后先简短点评，再继续追问。',
    icon: MessageSquareQuote
  },
  {
    title: '评分反馈',
    description: '结束面试后输出亮点、风险点、改进建议与评分面板。',
    icon: Gauge
  }
]

const flowSteps = [
  {
    title: '上传或选择简历',
    description: '在“我的简历”中上传 PDF 简历，系统会解析并作为面试依据。'
  },
  {
    title: '选择岗位与轮次',
    description: '支持前端、后端、产品、测试、算法、运营、通用等岗位，以及初试 / 复试 / HR。'
  },
  {
    title: '进入面试会话',
    description: '面试官 Agent 自动发起第一问，并根据简历和你的回答持续追问。'
  },
  {
    title: '获取总结与评分',
    description: '结束面试后查看整体评价、维度评分和后续改进建议。'
  }
]

const positions = ['前端工程师', '后端工程师', '产品经理', '测试工程师', '算法工程师', '运营', '通用岗位']
const rounds = ['初试', '复试', 'HR']
const feedbackItems = ['亮点总结', '风险点提醒', '改进建议', '评分卡输出']

const checkHealth = async () => {
  try {
    const response = await healthApi.checkHealth()
    if (response.status !== 'ok') {
      throw new Error('服务不可用')
    }
  } catch (e) {
    error.value = {
      title: '服务连接失败',
      message: '后端服务暂时不可用，请检查服务是否正常运行。'
    }
    throw e
  }
}

const loadData = async () => {
  isLoading.value = true
  error.value = null

  try {
    await checkHealth()
    await infoStore.loadInfoConfig()
  } catch (e) {
    console.error('加载首页数据失败:', e)
  } finally {
    isLoading.value = false
  }
}

const retryLoad = () => {
  loadData()
}

const ensureLogin = () => {
  if (userStore.isLoggedIn) {
    return true
  }

  sessionStorage.setItem('redirect', '/')
  router.push('/login')
  return false
}

const goToInterview = () => {
  if (!ensureLogin()) return
  router.push('/agent')
}

const goToResumeCenter = () => {
  if (!ensureLogin()) return
  router.push('/resume')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="less">
.home-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at top right, var(--main-20), transparent 30%),
    radial-gradient(circle at left top, var(--main-10), transparent 28%),
    var(--gray-25);
  color: var(--gray-900);
}

.loading-container,
.error-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
}

.loading-text {
  color: var(--gray-600);
  font-size: 14px;
}

.page-header {
  height: 76px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--gray-100);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(18px);
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.brand-logo {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  object-fit: cover;
}

.brand-meta {
  min-width: 0;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-900);
}

.brand-desc {
  margin-top: 2px;
  font-size: 12px;
  color: var(--gray-500);
}

.page-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 36px 24px 56px;
}

.hero-section {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 24px;
  align-items: stretch;
}

.hero-content,
.hero-panel,
.feature-card,
.flow-card,
.config-card {
  border-radius: 20px;
  border: 1px solid var(--gray-100);
  background: var(--gray-0);
}

.hero-content {
  padding: 32px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--main-20);
  color: var(--main-color);
  font-size: 12px;
  font-weight: 600;
}

.hero-title {
  margin: 18px 0 0;
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.15;
  font-weight: 800;
  color: var(--gray-900);
}

.hero-subtitle {
  margin: 18px 0 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--gray-600);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.primary-btn,
.secondary-btn {
  height: 46px;
  padding: 0 18px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-btn {
  border: none;
  background: var(--main-color);
  color: var(--gray-0);
}

.secondary-btn {
  border: 1px solid var(--gray-150);
  background: var(--gray-0);
  color: var(--gray-700);
}

.hero-points {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hero-point,
.feedback-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--gray-700);
  font-size: 14px;
}

.hero-point :deep(svg),
.feedback-item :deep(svg) {
  color: var(--main-color);
  flex-shrink: 0;
}

.hero-panel {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-card {
  border-radius: 16px;
  background: var(--gray-25);
  border: 1px solid var(--gray-100);
  padding: 18px;
}

.primary-card {
  background: linear-gradient(180deg, var(--main-10), var(--gray-0));
}

.panel-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--main-color);
}

.panel-title {
  margin-top: 10px;
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-900);
}

.panel-text {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--gray-0);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--main-color);
  flex-shrink: 0;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-900);
}

.stat-label {
  margin-top: 4px;
  font-size: 13px;
  color: var(--gray-500);
}

.section-block {
  margin-top: 24px;
}

.section-heading {
  margin-bottom: 14px;
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--gray-900);
}

.section-desc {
  margin-top: 6px;
  font-size: 14px;
  color: var(--gray-600);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.feature-card {
  padding: 22px;
}

.feature-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--main-20);
  color: var(--main-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.feature-title {
  margin-top: 16px;
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-900);
}

.feature-desc {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
}

.flow-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.flow-card {
  padding: 22px;
}

.flow-index {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  background: var(--main-20);
  color: var(--main-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
}

.flow-title {
  margin-top: 16px;
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-900);
}

.flow-desc {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--gray-600);
}

.config-layout {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.config-card {
  padding: 22px;
}

.config-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-900);
}

.tag-list {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.config-tag {
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--gray-150);
  background: var(--gray-25);
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  color: var(--gray-700);
}

.feedback-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.page-footer {
  padding: 20px 24px 34px;
  text-align: center;
  color: var(--gray-500);
  font-size: 13px;
}

@media (max-width: 1080px) {
  .hero-section,
  .feature-grid,
  .flow-list,
  .config-layout {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .page-header {
    height: auto;
    padding: 14px 16px;
    gap: 12px;
    align-items: flex-start;
    flex-direction: column;
  }

  .page-main {
    padding: 20px 16px 40px;
  }

  .hero-section,
  .feature-grid,
  .flow-list,
  .config-layout,
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .hero-content,
  .hero-panel,
  .feature-card,
  .flow-card,
  .config-card {
    padding: 18px;
  }

  .hero-actions {
    flex-direction: column;
  }

  .primary-btn,
  .secondary-btn {
    width: 100%;
  }
}
</style>
