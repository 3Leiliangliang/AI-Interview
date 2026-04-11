<template>
  <div class="login-view" :class="{ 'has-alert': serverStatus === 'error', 'is-leaving': isLeaving }">
    <div v-if="serverStatus === 'error'" class="server-status-alert">
      <div class="alert-content">
        <exclamation-circle-outlined class="alert-icon" />
        <div class="alert-text">
          <div class="alert-title">服务端连接失败</div>
          <div class="alert-message">{{ serverError }}</div>
        </div>
        <a-button type="link" size="small" @click="checkServerHealth" :loading="healthChecking">
          重试
        </a-button>
      </div>
    </div>

    <main class="login-main">
      <div class="auth-container">
        <div class="auth-shell">
          <section class="auth-visual">
            <div class="auth-visual-top">
              <h2 class="visual-brand">{{ brandName }}</h2>
            </div>

            <div class="auth-visual-center">
              <AnimatedCharacters
                :is-typing="isTyping"
                :show-password="showPassword"
                :password-length="activePasswordLength"
              />
            </div>

            <div class="auth-visual-bottom">
              <a href="https://github.com/xerrors/Bole/blob/main/LICENSE" target="_blank">隐私政策</a>
              <a href="https://github.com/xerrors/Bole" target="_blank">使用帮助</a>
            </div>

            <div class="blob one" />
            <div class="blob two" />
          </section>

          <section class="auth-panel">
            <div class="auth-card">
              <div class="auth-card-head">
                <a-button type="text" size="small" class="back-home-btn" @click="goHome">
                  返回首页
                </a-button>
              </div>

              <div class="mobile-brand">
                <h2 class="visual-brand">{{ brandName }}</h2>
              </div>

              <header class="form-header">
                <p class="welcome-text">欢迎登录</p>
                <h2 v-if="isFirstRun" class="init-title">系统初始化，请创建超级管理员</h2>
              </header>

              <div class="login-content" :class="{ 'is-initializing': isFirstRun }">
                <div v-if="isFirstRun" class="login-form login-form--init">
                  <a-form :model="adminForm" @finish="handleInitialize" layout="vertical">
                  <a-form-item
                    label="用户ID"
                    name="user_id"
                    :rules="[
                      { required: true, message: '请输入用户ID' },
                      {
                        pattern: /^[a-zA-Z0-9_]+$/,
                        message: '用户ID只能包含字母、数字和下划线'
                      },
                      {
                        min: 3,
                        max: 20,
                        message: '用户ID长度必须在3-20个字符之间'
                      }
                    ]"
                  >
                    <a-input
                      v-model:value="adminForm.user_id"
                      placeholder="请输入用户ID（3-20个字符）"
                      :maxlength="20"
                      @focus="handleInputFocus"
                      @blur="handleInputBlur"
                    />
                  </a-form-item>

                  <a-form-item
                    label="手机号（可选）"
                    name="phone_number"
                    :rules="[
                      {
                        validator: async (rule, value) => {
                          if (!value || value.trim() === '') {
                            return
                          }
                          const phoneRegex = /^1[3-9]\d{9}$/
                          if (!phoneRegex.test(value)) {
                            throw new Error('请输入正确的手机号格式')
                          }
                        }
                      }
                    ]"
                  >
                    <a-input
                      v-model:value="adminForm.phone_number"
                      placeholder="可用于登录，可不填写"
                      :max-length="11"
                      @focus="handleInputFocus"
                      @blur="handleInputBlur"
                    />
                  </a-form-item>

                  <a-form-item
                    label="密码"
                    name="password"
                    :rules="[{ required: true, message: '请输入密码' }]"
                  >
                    <a-input-password
                      v-model:value="adminForm.password"
                      prefix-icon="lock"
                      @focus="handleInputFocus"
                      @blur="handleInputBlur"
                      @visibleChange="handlePasswordVisibleChange"
                    />
                  </a-form-item>

                  <a-form-item
                    label="确认密码"
                    name="confirmPassword"
                    :rules="[
                      { required: true, message: '请确认密码' },
                      { validator: validateConfirmPassword }
                    ]"
                  >
                    <a-input-password
                      v-model:value="adminForm.confirmPassword"
                      prefix-icon="lock"
                      @focus="handleInputFocus"
                      @blur="handleInputBlur"
                      @visibleChange="handlePasswordVisibleChange"
                    />
                  </a-form-item>

                  <a-form-item>
                    <a-button type="primary" html-type="submit" :loading="loading" block size="large">
                      创建管理员账户
                    </a-button>
                  </a-form-item>
                  </a-form>
                </div>

                <div v-else class="login-form">
                  <a-form :model="loginForm" @finish="handleLogin" layout="vertical">
                  <a-form-item
                    label="登录账号"
                    name="loginId"
                    :rules="[{ required: true, message: '请输入用户ID或手机号' }]"
                  >
                    <a-input
                      v-model:value="loginForm.loginId"
                      placeholder="用户ID或手机号"
                      @focus="handleInputFocus"
                      @blur="handleInputBlur"
                    >
                      <template #prefix>
                        <user-outlined />
                      </template>
                    </a-input>
                  </a-form-item>

                  <a-form-item
                    label="密码"
                    name="password"
                    :rules="[{ required: true, message: '请输入密码' }]"
                  >
                    <a-input-password
                      v-model:value="loginForm.password"
                      @focus="handleInputFocus"
                      @blur="handleInputBlur"
                      @visibleChange="handlePasswordVisibleChange"
                    >
                      <template #prefix>
                        <lock-outlined />
                      </template>
                    </a-input-password>
                  </a-form-item>

                  <a-form-item>
                    <div class="login-options">
                      <a-checkbox v-model:checked="rememberMe" @click="showDevMessage">记住我</a-checkbox>
                      <a class="forgot-password" @click="showDevMessage">忘记密码?</a>
                    </div>
                  </a-form-item>

                  <a-form-item>
                    <a-button
                      type="primary"
                      html-type="submit"
                      :loading="loading"
                      :disabled="isLocked"
                      block
                      size="large"
                    >
                      <span v-if="isLocked">账户已锁定 {{ formatTime(lockRemainingTime) }}</span>
                      <span v-else>登录</span>
                    </a-button>
                  </a-form-item>

                  <div class="third-party-login">
                    <div class="divider">
                      <span>其他登录方式</span>
                    </div>
                    <div class="login-icons">
                      <a-tooltip title="微信登录">
                        <a-button shape="circle" class="login-icon" @click="showDevMessage">
                          <template #icon><wechat-outlined /></template>
                        </a-button>
                      </a-tooltip>
                      <a-tooltip title="企业微信登录">
                        <a-button shape="circle" class="login-icon" @click="showDevMessage">
                          <template #icon><qrcode-outlined /></template>
                        </a-button>
                      </a-tooltip>
                      <a-tooltip title="飞书登录">
                        <a-button shape="circle" class="login-icon" @click="showDevMessage">
                          <template #icon><thunderbolt-outlined /></template>
                        </a-button>
                      </a-tooltip>
                    </div>
                  </div>
                  </a-form>
                </div>

                <div v-if="errorMessage" class="error-message">
                  {{ errorMessage }}
                </div>
              </div>

              <footer class="page-footer">
                <div class="footer-links">
                  <a href="https://github.com/xerrors" target="_blank">联系我们</a>
                  <span class="divider">|</span>
                  <a href="https://github.com/xerrors/Bole" target="_blank">使用帮助</a>
                  <span class="divider">|</span>
                  <a href="https://github.com/xerrors/Bole/blob/main/LICENSE" target="_blank">隐私政策</a>
                </div>
                <div class="copyright">
                  &copy; {{ new Date().getFullYear() }} {{ brandName }}. All Rights Reserved.
                </div>
              </footer>
            </div>
          </section>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useInfoStore } from '@/stores/info'
import { useAgentStore } from '@/stores/agent'
import { message } from 'ant-design-vue'
import { healthApi } from '@/apis/system_api'
import AnimatedCharacters from '@/components/auth/AnimatedCharacters.vue'
import {
  UserOutlined,
  LockOutlined,
  WechatOutlined,
  QrcodeOutlined,
  ThunderboltOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const infoStore = useInfoStore()
const agentStore = useAgentStore()

const brandOrgName = computed(() => {
  return infoStore.organization?.name?.trim() || ''
})
const brandName = computed(() => {
  const orgName = brandOrgName.value
  const brandNameRaw = infoStore.branding?.name?.trim() || '伯乐'

  if (orgName && brandNameRaw && orgName !== brandNameRaw) {
    return brandNameRaw
  }

  return orgName || brandNameRaw
})

const isFirstRun = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const rememberMe = ref(false)
const serverStatus = ref('loading')
const serverError = ref('')
const healthChecking = ref(false)
const isTyping = ref(false)
const showPassword = ref(false)
const isLeaving = ref(false)

const isLocked = ref(false)
const lockRemainingTime = ref(0)
const lockCountdown = ref(null)

const loginForm = reactive({
  loginId: '',
  password: ''
})

const adminForm = reactive({
  user_id: '',
  password: '',
  confirmPassword: '',
  phone_number: ''
})

const activePasswordLength = computed(() => {
  return isFirstRun.value ? adminForm.password.length : loginForm.password.length
})

const showDevMessage = () => {
  message.info('该功能正在开发中，敬请期待！')
}

const smoothNavigate = async (path) => {
  isLeaving.value = true
  await new Promise((resolve) => setTimeout(resolve, 140))
  await router.push(path)
}

const goHome = () => {
  smoothNavigate('/')
}

const handleInputFocus = () => {
  isTyping.value = true
}

const handleInputBlur = () => {
  isTyping.value = false
}

const handlePasswordVisibleChange = (visible) => {
  showPassword.value = visible
}

const clearLockCountdown = () => {
  if (lockCountdown.value) {
    clearInterval(lockCountdown.value)
    lockCountdown.value = null
  }
}

const startLockCountdown = (remainingSeconds) => {
  clearLockCountdown()
  isLocked.value = true
  lockRemainingTime.value = remainingSeconds

  lockCountdown.value = setInterval(() => {
    lockRemainingTime.value--
    if (lockRemainingTime.value <= 0) {
      clearLockCountdown()
      isLocked.value = false
      errorMessage.value = ''
    }
  }, 1000)
}

const formatTime = (seconds) => {
  if (seconds < 60) {
    return `${seconds}秒`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}分${remainingSeconds}秒`
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时${minutes}分钟`
  } else {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    return `${days}天${hours}小时`
  }
}

const validateConfirmPassword = async (rule, value) => {
  if (value === '') {
    throw new Error('请确认密码')
  }
  if (value !== adminForm.password) {
    throw new Error('两次输入的密码不一致')
  }
}

const handleLogin = async () => {
  if (isLocked.value) {
    message.warning(`账户被锁定，请等待 ${formatTime(lockRemainingTime.value)}`)
    return
  }

  try {
    loading.value = true
    errorMessage.value = ''
    clearLockCountdown()

    await userStore.login({
      loginId: loginForm.loginId,
      password: loginForm.password
    })

    message.success('登录成功')

    const redirectPath = sessionStorage.getItem('redirect') || '/'
    sessionStorage.removeItem('redirect')

    if (redirectPath === '/') {
      if (userStore.isAdmin) {
        await agentStore.initialize()
        await smoothNavigate('/agent')
        return
      }

      try {
        await agentStore.initialize()
        await smoothNavigate('/agent')
      } catch (error) {
        console.error('获取智能体信息失败:', error)
        await smoothNavigate('/')
      }
    } else {
      await smoothNavigate(redirectPath)
    }
  } catch (error) {
    console.error('登录失败:', error)

    if (error.status === 423) {
      let remainingTime = 0
      if (error.headers && error.headers.get) {
        const lockRemainingHeader = error.headers.get('X-Lock-Remaining')
        if (lockRemainingHeader) {
          remainingTime = parseInt(lockRemainingHeader)
        }
      }

      if (remainingTime === 0) {
        const lockTimeMatch = error.message.match(/(\d+)\s*秒/)
        if (lockTimeMatch) {
          remainingTime = parseInt(lockTimeMatch[1])
        }
      }

      if (remainingTime > 0) {
        startLockCountdown(remainingTime)
        errorMessage.value = `由于多次登录失败，账户已被锁定 ${formatTime(remainingTime)}`
      } else {
        errorMessage.value = error.message || '账户被锁定，请稍后再试'
      }
    } else {
      errorMessage.value = error.message || '登录失败，请检查用户名和密码'
    }
  } finally {
    loading.value = false
  }
}

const handleInitialize = async () => {
  try {
    loading.value = true
    errorMessage.value = ''

    if (adminForm.password !== adminForm.confirmPassword) {
      errorMessage.value = '两次输入的密码不一致'
      return
    }

    await userStore.initialize({
      user_id: adminForm.user_id,
      password: adminForm.password,
      phone_number: adminForm.phone_number || null
    })

    message.success('管理员账户创建成功')
    await smoothNavigate('/')
  } catch (error) {
    console.error('初始化失败:', error)
    errorMessage.value = error.message || '初始化失败，请重试'
  } finally {
    loading.value = false
  }
}

const checkFirstRunStatus = async () => {
  try {
    loading.value = true
    const isFirst = await userStore.checkFirstRun()
    isFirstRun.value = isFirst
  } catch (error) {
    console.error('检查首次运行状态失败:', error)
    errorMessage.value = '系统出错，请稍后重试'
  } finally {
    loading.value = false
  }
}

const checkServerHealth = async () => {
  try {
    healthChecking.value = true
    const response = await healthApi.checkHealth()
    if (response.status === 'ok') {
      serverStatus.value = 'ok'
    } else {
      serverStatus.value = 'error'
      serverError.value = response.message || '服务端状态异常'
    }
  } catch (error) {
    console.error('检查服务器健康状态失败:', error)
    serverStatus.value = 'error'
    serverError.value = error.message || '无法连接到服务端，请检查网络连接'
  } finally {
    healthChecking.value = false
  }
}

onMounted(async () => {
  if (userStore.isLoggedIn) {
    router.push('/')
    return
  }

  await checkServerHealth()
  await checkFirstRunStatus()
})

onUnmounted(() => {
  clearLockCountdown()
})
</script>

<style lang="less" scoped>
.login-view {
  min-height: 100dvh;
  width: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--gray-10);

  &.has-alert {
    padding-top: 60px;
  }
}

.login-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}

.auth-container {
  width: min(1500px, 95vw);
  height: min(900px, 92dvh);
  border-radius: 22px;
  overflow: hidden;
  background: var(--gray-0);
  box-shadow: 0 10px 40px color-mix(in srgb, var(--gray-800) 18%, transparent);
  display: flex;
  flex-direction: column;
}

.login-navbar {
  width: 100%;
  padding: 16px 24px;
  z-index: 10;

  .navbar-content {
    display: flex;
    justify-content: flex-end;
    align-items: center;
  }
}

.visual-brand {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
  display: flex;
  align-items: center;
}

.auth-visual .visual-brand {
  color: var(--gray-0);
}

.back-home-btn {
  color: var(--gray-600);
  font-size: 14px;

  &:hover {
    color: var(--main-color);
    background-color: transparent;
  }
}

.auth-shell {
  width: 100%;
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: 1fr;
}

.auth-visual {
  display: none;
  position: relative;
  overflow: hidden;
  padding: 20px 48px 34px;
  color: var(--gray-0);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--main-color) 16%, var(--gray-500)) 0%,
    color-mix(in srgb, var(--main-color) 26%, var(--gray-700)) 45%,
    var(--gray-800) 100%
  );

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(color-mix(in srgb, var(--gray-0) 10%, transparent) 1px, transparent 1px),
      linear-gradient(90deg, color-mix(in srgb, var(--gray-0) 10%, transparent) 1px, transparent 1px);
    background-size: 20px 20px;
  }
}

.blob {
  position: absolute;
  border-radius: 999px;
  filter: blur(80px);
}

.blob.one {
  width: 280px;
  height: 280px;
  top: 20%;
  right: 14%;
  background: color-mix(in srgb, var(--main-color) 35%, transparent);
}

.blob.two {
  width: 420px;
  height: 420px;
  left: 10%;
  bottom: 10%;
  background: color-mix(in srgb, var(--gray-0) 24%, transparent);
}

.auth-visual-top,
.auth-visual-bottom,
.auth-visual-center {
  position: relative;
  z-index: 2;
}

.auth-visual-center {
  margin-top: auto;
  margin-bottom: auto;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  min-height: 460px;
}

.auth-visual-bottom {
  display: flex;
  gap: 22px;
  font-size: 14px;
  color: color-mix(in srgb, var(--gray-0) 88%, transparent);

  a:hover {
    color: var(--gray-0);
  }
}

.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 20px 24px;
  background: var(--gray-10);
}

.auth-card {
  width: min(100%, 430px);
}

.mobile-brand {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
}

.form-header {
  text-align: center;
  margin-bottom: 20px;

  .welcome-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--gray-500);
    margin: 0 0 8px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .init-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--main-color);
    margin: 0;
    line-height: 1.4;
  }
}

.login-form {
  :deep(.ant-form-item-label > label) {
    font-size: 14px;
    font-weight: 600;
    color: var(--gray-700);
  }

  :deep(.ant-input),
  :deep(.ant-input-affix-wrapper) {
    border-radius: 14px;
    min-height: 48px;
    border-color: var(--gray-300);
    background-color: var(--gray-0);
  }

  :deep(.ant-input-affix-wrapper-focused),
  :deep(.ant-input:focus) {
    border-color: var(--main-color);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--main-color) 15%, transparent);
  }

  :deep(.ant-btn) {
    height: 48px;
    border-radius: 999px;
    font-size: 15px;
    font-weight: 600;
  }
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.forgot-password {
  color: var(--main-color);
  font-weight: 600;

  &:hover {
    text-decoration: underline;
  }
}

.third-party-login {
  margin-top: 6px;

  .divider {
    position: relative;
    text-align: center;
    margin: 24px 0 16px;

    &::before,
    &::after {
      content: '';
      position: absolute;
      top: 50%;
      width: 30%;
      height: 1px;
      background-color: var(--gray-300);
    }

    &::before {
      left: 0;
    }

    &::after {
      right: 0;
    }

    span {
      display: inline-block;
      padding: 0 8px;
      background-color: var(--gray-10);
      color: var(--gray-500);
      font-size: 12px;
    }
  }

  .login-icons {
    display: flex;
    justify-content: center;
    gap: 20px;
  }

  .login-icon {
    width: 38px;
    height: 38px;
    font-size: 18px;
    color: var(--gray-500);
    border-color: var(--gray-300);
    display: flex;
    align-items: center;
    justify-content: center;

    &:hover {
      color: var(--main-color);
      border-color: var(--main-color);
      background-color: var(--main-10);
    }
  }
}

.error-message {
  margin-top: 16px;
  padding: 10px 12px;
  background-color: var(--color-error-50);
  border: 1px solid color-mix(in srgb, var(--color-error-500) 25%, transparent);
  border-radius: 12px;
  color: var(--color-error-700);
  font-size: 13px;
  text-align: center;
}

.page-footer {
  padding-top: 22px;
  text-align: center;
}

.footer-links {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;

  a {
    color: var(--gray-500);
    font-size: 13px;

    &:hover {
      color: var(--main-color);
    }
  }

  .divider {
    color: var(--gray-300);
    font-size: 12px;
  }
}

.copyright {
  font-size: 12px;
  color: var(--gray-400);
}

.server-status-alert {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background: var(--color-error-500);
  color: var(--gray-0);
  z-index: 1000;

  .alert-content {
    display: flex;
    align-items: center;
    max-width: 1500px;
    margin: 0 auto;

    .alert-icon {
      font-size: 20px;
      margin-right: 12px;
      color: var(--gray-0);
    }

    .alert-text {
      flex: 1;

      .alert-title {
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 2px;
      }

      .alert-message {
        font-size: 14px;
        opacity: 0.9;
      }
    }

    :deep(.ant-btn-link) {
      color: var(--gray-0);
      border-color: var(--gray-0);

      &:hover {
        color: var(--gray-0);
        background-color: color-mix(in srgb, var(--gray-0) 10%, transparent);
      }
    }
  }
}

@media (min-width: 1024px) {
  .auth-shell {
    grid-template-columns: 1fr 1fr;
  }

  .auth-visual {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .mobile-brand {
    display: none;
  }

  .auth-panel {
    padding: 20px 36px 26px;
  }
}

@media (max-width: 768px) {
  .login-main {
    padding: 0;
  }

  .auth-container {
    width: 100vw;
    height: 100dvh;
    border-radius: 0;
    box-shadow: none;
  }

  .auth-panel {
    padding: 12px 16px 24px;
  }
}
</style>
