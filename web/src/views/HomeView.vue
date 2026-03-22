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
      <!-- Top Navigation Bar -->
      <nav class="top-nav">
        <div class="nav-container">
          <div class="brand">
            <img
              v-if="infoStore.organization?.logo"
              :src="infoStore.organization.logo"
              :alt="displayBrandName"
              class="brand-logo"
            />
            <div class="brand-name">{{ displayBrandName }}</div>
          </div>
          <div class="nav-actions">
            <!-- Using the existing UserInfoComponent for Auth -->
            <UserInfoComponent :show-button="true" />
          </div>
        </div>
        <div class="nav-divider"></div>
      </nav>

      <main class="page-main hero-gradient">
        <!-- Hero & Capabilities Section -->
        <section class="hero-section">
          <!-- Left: Hero Text -->
          <div class="hero-left">
            <div class="badge">
              <Sparkles :size="14" stroke-width="2.5" />
              <span class="badge-text">下一代求职伙伴</span>
            </div>
            
            <h1 class="hero-title">
              与 AI 一起<br/>
              <span class="text-gradient">掌握你的下一次面试</span>
            </h1>
            
            <p class="hero-desc">
              由先进大语言模型驱动的个性化实时模拟面试系统。上传简历、选择岗位与轮次，完善你的叙述，克服焦虑，斩获理想职位。
            </p>
            
            <div class="hero-actions">
              <button class="btn-primary" type="button" @click="goToInterview">
                开始模拟面试
                <ArrowRight :size="18" />
              </button>
              <button class="btn-secondary" type="button" @click="goToResumeCenter">
                <FileText :size="18" />
                我的简历
              </button>
            </div>
            
            <div class="social-proof">
              <div class="avatars">
                <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuBmegEzfJAvDYFJZCttYLAEMDPeyFAUfPh36XfCMMuzOzDqAhjDaaoesH01AGP4R3rpSCurhXgpfimI_JiPlhfpcY3Mj_vt-2cxGcyoyt_tjqvVraSs-D1wosNlE5Yxl8PwEMU_LsnoNUnuwGforo6BQuD-BVIM8V1B8wSdDFkkB03drDIXFklGzI9mO32S37_mhYoVXjrB1j3IfwfVPpuNxOS8S9DFP-uaRmR_PjxYWWcVDh0ykj1YMFnntz62jsjO1vgz7MB6fqM" alt="User" />
                <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuCoM8Ambi7HTYmr5ncTfZ-9DkpQomiZtP11woLy1N0sa_glw2opWstO28BQiH5nZdWzSUqzebMYUwJ-bXMT5WRkA3IDKl3acvizo_sipC62YKex_SVQ0CgA_YPKWMS414OJDaAnhQyEX34SutV_S_rgvMxPMBkTjT_Pr4LahzvNgDIeQ_xl2SsybllLQhpYoOsetmRGk7zuKXDhvQsEs-pXqWy3E2e8B5-XinSXsWXuqzdgw3jMDd1e_caE-Pyiga5am-3rDeQ3A5E" alt="User" />
                <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuAEZXmMWwJNtRjH7SXSgKIXe2EeGbEY-3SetM3FJYJDF6kGTpJ8NjdzqxSd1hv4QEXYBAANyk94gxyrmBfOi8hkfOppv2XEUbf4K9vBDlK-upu8MXGLr2qQgx6ol2-x6-jZchdnDAUWOqYf1Y0dJrKUigpQLsBF7Nr89iqBg5xny64ME9K3aekyneSYA07fPEFKOa0wdZl_nq_FVvCSo7vNStyr7knQgYjoRPr4yvi1kPBqUV0NUFWoL-0YuJ13KT61S2AVuWscAzI" alt="User" />
              </div>
              <p class="proof-text">
                <span class="highlight">2,400+</span> 职场人士本周已在此准备
              </p>
            </div>
          </div>

          <!-- Right: System Capabilities -->
          <div class="hero-right">
            <div class="decor-blob top-right"></div>
            <div class="decor-blob bottom-left"></div>
            
            <div class="bento-grid">
              <div class="glass-card">
                <div class="card-icon blue">
                  <BriefcaseBusiness :size="20" stroke-width="2.5" />
                </div>
                <h3 class="card-title">7+ 岗位方向</h3>
                <p class="card-desc">技术、产品、运营等主流求职方向全覆盖。</p>
              </div>
              
              <div class="glass-card mt-offset">
                <div class="card-icon teal">
                  <Repeat :size="20" stroke-width="2.5" />
                </div>
                <h3 class="card-title">3大面试轮次</h3>
                <p class="card-desc">支持初试、复试与 HR 面，全方位模拟真实场景。</p>
              </div>

              <div class="glass-card">
                <div class="card-icon gray">
                  <LineChart :size="20" stroke-width="2.5" />
                </div>
                <h3 class="card-title">详尽反馈体系</h3>
                <p class="card-desc">面试后的多维度分析，涵盖亮点、风险与改进建议。</p>
              </div>
              
              <div class="glass-card mt-offset">
                <div class="card-icon indigo">
                  <History :size="20" stroke-width="2.5" />
                </div>
                <h3 class="card-title">追问与记录</h3>
                <p class="card-desc">基于简历连续追问，侧边栏保存完整面试历史。</p>
              </div>
            </div>
          </div>
        </section>

        <!-- Dynamic Insights Section -->
        <section class="insights-section">
          <div class="insights-container">
            <div class="bg-watermark">
              <BrainCircuit :size="160" stroke-width="1" />
            </div>
            
            <div class="insights-content">
              <div class="insights-text">
                <h2 class="section-title">体验全新的面试准备方式</h2>
                <div class="feature-list">
                  <div class="feature-item">
                    <div class="check-icon">
                      <Check :size="14" stroke-width="3" />
                    </div>
                    <div class="feature-info">
                      <h4 class="feature-title">智能简历解析</h4>
                      <p class="feature-desc">系统自动读取你的简历，面试将围绕你的真实经历展开。</p>
                    </div>
                  </div>
                  <div class="feature-item">
                    <div class="check-icon">
                      <Check :size="14" stroke-width="3" />
                    </div>
                    <div class="feature-info">
                      <h4 class="feature-title">全真模拟对话</h4>
                      <p class="feature-desc">面试官智能发起提问与深度追问，高度还原真实面试压迫感。</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <div class="insights-preview">
                <div class="preview-header">
                  <div class="avatar"><Bot :size="20" stroke-width="2" /></div>
                  <div class="header-text">
                    <div class="user-label">AI 面试官</div>
                    <div class="user-msg">“你能描述一次工作中遇到的具有挑战性的冲突吗？”</div>
                  </div>
                </div>
                <div class="preview-body">
                  <div class="feedback-box">
                    <p class="feedback-label">实时反馈提示</p>
                    <div class="feedback-msg">
                      <Zap :size="16" />
                      <p>尝试使用 STAR 法则来让回答更有结构。</p>
                    </div>
                  </div>
                  <div class="progress-bar">
                    <div class="progress-fill"></div>
                  </div>
                  <p class="progress-text">当前表现得分：84%</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer class="page-footer">
        <div class="footer-layout">
          <div class="footer-brand">
            <div class="brand-name">{{ displayBrandName }}</div>
            <p class="brand-desc">构建职业成长与求职成功的基石。</p>
          </div>
          <div class="footer-links">
            <a href="#">隐私政策</a>
            <a href="#">服务条款</a>
            <a href="#">Cookie 设置</a>
            <a href="#">联系支持</a>
          </div>
          <div class="copyright">
            {{ displayCopyright }}
          </div>
        </div>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles,
  ArrowRight,
  FileText,
  BriefcaseBusiness,
  Repeat,
  LineChart,
  History,
  BrainCircuit,
  Check,
  Bot,
  Zap
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

const displayBrandName = computed(() => {
  const name = String(infoStore.organization?.name || '').trim()
  if (!name || /^ai[\s-]*interview$/i.test(name)) {
    return '伯乐 Bole'
  }
  return name
})

const displayCopyright = computed(() => {
  const copyright = String(infoStore.footer?.copyright || '').trim()
  if (!copyright || /AI[\s-]*interview/i.test(copyright)) {
    return '© 2026 伯乐 Bole Professional Partner. All rights reserved.'
  }
  return copyright
})

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
    console.error('加载提示失败:', e)
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
  background-color: var(--gray-0);
  color: var(--gray-900);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  display: flex;
  flex-direction: column;
}

.loading-container,
.error-container {
  flex: 1;
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

/* Navbar */
.top-nav {
  position: fixed;
  top: 0;
  width: 100%;
  z-index: 50;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(16px);
}

.nav-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  object-fit: cover;
}

.brand-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-900);
  letter-spacing: -0.5px;
}

.nav-links {
  display: none;
}

@media (min-width: 768px) {
  .nav-links {
    display: flex;
    align-items: center;
    gap: 40px;
  }
}

.nav-link {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-600);
  text-decoration: none;
  transition: color 0.3s;
}

.nav-link:hover {
  color: var(--main-color);
}

.nav-link.active {
  color: var(--main-color);
}

.nav-actions {
  display: flex;
  align-items: center;
}

.nav-divider {
  height: 1px;
  width: 100%;
  background-color: var(--main-10);
  position: absolute;
  bottom: 0;
}

/* Main Content */
.page-main {
  flex: 1;
  padding-top: 80px;
  overflow-x: hidden;
}

.hero-gradient {
  background: radial-gradient(circle at 80% 20%, var(--main-20) 0%, var(--gray-0) 60%);
}

.hero-section {
  max-width: 1280px;
  margin: 0 auto;
  padding: 48px 24px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 48px;
  align-items: center;
}

@media (min-width: 1024px) {
  .hero-section {
    grid-template-columns: repeat(12, 1fr);
    padding: 96px 24px;
  }
  .hero-left {
    grid-column: span 6;
  }
  .hero-right {
    grid-column: span 6;
  }
}

/* Hero Left */
.hero-left {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 999px;
  background: rgba(195, 227, 255, 0.3); /* main-100 slightly transparent */
  border: 1px solid var(--main-200);
  align-self: flex-start;
}

.badge-text {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary-900);
  letter-spacing: 0.5px;
}

.badge :deep(svg) {
  color: var(--color-primary-700);
}

.hero-title {
  font-size: 42px;
  font-weight: 800;
  line-height: 1.15;
  color: var(--gray-900);
  letter-spacing: -1px;
}

@media (min-width: 768px) {
  .hero-title {
    font-size: 64px;
  }
}

.text-gradient {
  background: linear-gradient(to right, var(--main-700), var(--main-400));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-desc {
  font-size: 18px;
  color: var(--gray-700);
  max-width: 500px;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (min-width: 640px) {
  .hero-actions {
    flex-direction: row;
    align-items: center;
  }
}

.btn-primary, .btn-secondary {
  height: 54px;
  padding: 0 32px;
  border-radius: 999px;
  font-size: 16px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  border: none;
}

.btn-primary {
  background: linear-gradient(to right, var(--main-700), var(--main-500));
  color: white;
  margin-right:0px;
}

/* Rule says no hover displacement, so keeping hover simple */
.btn-primary:active, .btn-secondary:active {
  opacity: 0.9;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(8px);
  color: var(--gray-900);
  border: 1px solid var(--gray-200);
}

.btn-secondary:hover {
  background: var(--gray-50);
}

.social-proof {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
}

.avatars {
  display: flex;
}

.avatars img {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid white;
  object-fit: cover;
  margin-left: -12px;
}

.avatars img:first-child {
  margin-left: 0;
}

.proof-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--gray-600);
}

.highlight {
  color: var(--main-700);
  font-weight: 700;
}

/* Hero Right (Bento) */
.hero-right {
  position: relative;
}

.decor-blob {
  position: absolute;
  width: 256px;
  height: 256px;
  border-radius: 50%;
  filter: blur(60px);
  z-index: 0;
}

.top-right {
  top: -48px;
  right: -48px;
  background: rgba(195, 227, 255, 0.4);
}

.bottom-left {
  bottom: -48px;
  left: -48px;
  background: rgba(135, 232, 222, 0.3);
}

.bento-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (min-width: 768px) {
  .bento-grid {
    gap: 24px;
  }
}

.mt-offset {
  margin-top: 0;
}

@media (min-width: 640px) {
  .mt-offset {
    margin-top: 32px;
  }
}

.glass-card {
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  padding: 24px;
  border-radius: 16px;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.card-icon.blue { background: rgba(55, 129, 207, 0.1); color: var(--main-color); }
.card-icon.teal { background: rgba(3, 100, 117, 0.1); color: #004a58; }
.card-icon.gray { background: rgba(87, 101, 122, 0.1); color: #515f74; }
.card-icon.indigo { background: rgba(0, 82, 204, 0.1); color: #0052cc; }

.card-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--gray-900);
}

.card-desc {
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.6;
}

/* Insights Section */
.insights-section {
  max-width: 1280px;
  margin: 0 auto;
  padding: 48px 24px 96px;
}

.insights-container {
  background-color: var(--main-10);
  border-radius: 24px;
  padding: 32px;
  position: relative;
  overflow: hidden;
}

@media (min-width: 768px) {
  .insights-container {
    padding: 48px;
  }
}

.bg-watermark {
  position: absolute;
  top: 0;
  right: 0;
  padding: 32px;
  opacity: 0.05;
  color: var(--gray-900);
}

.insights-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: 48px;
  align-items: center;
}

@media (min-width: 1024px) {
  .insights-content {
    grid-template-columns: 1fr 1fr;
  }
}

.section-title {
  font-size: 30px;
  font-weight: 800;
  color: var(--gray-900);
  margin-bottom: 24px;
}

@media (min-width: 768px) {
  .section-title {
    font-size: 36px;
  }
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.check-icon {
  margin-top: 4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: rgba(55, 129, 207, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--main-color);
  flex-shrink: 0;
}

.feature-title {
  font-weight: 700;
  color: var(--gray-900);
  margin-bottom: 4px;
  font-size: 16px;
}

.feature-desc {
  font-size: 14px;
  color: var(--gray-600);
}

/* Preview Card */
.insights-preview {
  background-color: white;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid var(--gray-100);
  box-shadow: 0 10px 25px rgba(0,0,0,0.03); /* Subtle shadow inline with the rules */
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--gray-100);
  margin-bottom: 24px;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--main-700);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--main-700);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.user-msg {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-900);
  margin-top: 2px;
}

.preview-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feedback-box {
  padding: 16px;
  background-color: var(--main-10);
  border-radius: 12px;
}

.feedback-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--gray-600);
  margin-bottom: 8px;
}

.feedback-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #004a58; /* tertiary color from template */
  font-size: 14px;
  font-weight: 500;
  font-style: italic;
}

.progress-bar {
  height: 8px;
  width: 100%;
  background-color: var(--main-50);
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  width: 84%;
  background-color: var(--main-color);
  border-radius: 999px;
}

.progress-text {
  font-size: 12px;
  color: var(--gray-600);
  text-align: center;
}

/* Footer */
.page-footer {
  background-color: var(--gray-0);
  border-top: 1px solid var(--gray-100);
  padding: 48px 0;
}

.footer-layout {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: center;
}

@media (min-width: 768px) {
  .footer-layout {
    flex-direction: row;
    justify-content: space-between;
  }
}

.footer-brand .brand-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-900);
}

.footer-brand .brand-desc {
  font-size: 12px;
  color: var(--gray-600);
  margin-top: 8px;
  max-width: 200px;
}

.footer-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 32px;
}

.footer-links a {
  font-size: 12px;
  color: var(--gray-600);
  text-decoration: none;
}

.footer-links a:hover {
  color: var(--main-color);
}

.copyright {
  font-size: 12px;
  color: var(--gray-400);
  text-align: center;
}

@media (min-width: 768px) {
  .copyright {
    text-align: right;
  }
}
</style>
