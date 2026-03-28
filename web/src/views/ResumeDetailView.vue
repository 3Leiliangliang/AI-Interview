<template>
  <div class="resume-detail-page">
    <HeaderComponent
      :title="resume?.filename || '简历详情'"
      description="智能提取简历关键信息，全面展示个人背景与能力"
      :loading="loading"
    >
      <template #left>
        <a-button @click="goBack">
          <ArrowLeft :size="14" />
          返回列表
        </a-button>
      </template>
      <template #actions>
        <a-button :loading="loading" @click="loadResumeDetail">
          <RefreshCw :size="14" />
          刷新
        </a-button>
        <a-popconfirm
          title="确认删除这份简历吗？"
          ok-text="删除"
          cancel-text="取消"
          @confirm="handleDelete"
        >
          <a-button danger :loading="deleting">
            <Trash2 :size="14" />
            删除
          </a-button>
        </a-popconfirm>
      </template>
    </HeaderComponent>

    <div class="resume-detail-content">
      <div v-if="loading" class="state-wrapper">
        <a-spin />
      </div>

      <template v-else-if="resume">
        <div class="detail-grid">
          <!-- Hero 区域：姓名 + 联系方式 + 亮点标签 -->
          <div class="summary-panel">
            <div class="summary-hero">
              <div class="hero-top">
                <div class="hero-avatar">
                  {{ summary.name?.charAt(0) || '姓' }}
                </div>
                <div class="hero-main">
                  <div class="hero-name">{{ summary.name }}</div>
                  <div class="hero-contact" v-if="summary.phone || summary.email">
                    <div v-if="summary.phone" class="contact-item">
                      <Phone :size="14" />
                      <span>{{ summary.phone }}</span>
                    </div>
                    <div v-if="summary.email" class="contact-item">
                      <Mail :size="14" />
                      <span>{{ summary.email }}</span>
                    </div>
                    <div v-if="summary.basicInfo?.location" class="contact-item">
                      <MapPin :size="14" />
                      <span>{{ summary.basicInfo.location }}</span>
                    </div>
                    <div v-if="summary.basicInfo?.github" class="contact-item">
                      <Github :size="14" />
                      <a :href="summary.basicInfo.github" target="_blank" class="hero-link">
                        {{ formatGithubUrl(summary.basicInfo.github) }}
                      </a>
                    </div>
                  </div>
                </div>
              </div>
              <!-- 亮点标签 -->
              <div v-if="highlightTags.length" class="hero-tags">
                <a-tag v-for="tag in highlightTags" :key="tag.text" :color="tag.color" class="highlight-tag">
                  <component :is="tag.icon" :size="12" />
                  {{ tag.text }}
                </a-tag>
              </div>
            </div>

            <!-- 简历完整度 -->
            <div v-if="hasSummaryData" class="completeness-bar">
              <div class="completeness-header">
                <span class="completeness-label">简历完整度</span>
                <span class="completeness-score" :class="completenessClass">{{ completenessScore }}%</span>
              </div>
              <a-progress
                :percent="completenessScore"
                :show-info="false"
                :stroke-color="completenessColor"
                :trail-color="'rgba(30, 58, 95, 0.1)'"
                size="small"
              />
              <div v-if="completenessTips.length" class="completeness-tips">
                <span v-for="tip in completenessTips" :key="tip" class="tip-item">
                  <Plus :size="12" /> {{ tip }}
                </span>
              </div>
            </div>

            <!-- 正文内容 -->
            <div class="summary-body">
              <!-- 左侧主栏 -->
              <div class="summary-main">
                <!-- 教育经历 -->
                <section v-if="summary.education.length" class="summary-section">
                  <div class="section-title">
                    <GraduationCap :size="16" />
                    教育经历
                  </div>
                  <div
                    v-for="(item, index) in summary.education"
                    :key="`education-${index}`"
                    class="timeline-item"
                  >
                    <div class="timeline-head">
                      <div class="timeline-title">{{ item.school }}</div>
                      <div v-if="item.duration" class="timeline-date">
                        <CalendarDays :size="13" />
                        <span>{{ item.duration }}</span>
                      </div>
                    </div>
                    <div v-if="item.major || item.degree" class="timeline-subtitle">
                      {{ item.major }}{{ item.degree ? ` · ${item.degree}` : '' }}
                    </div>
                    <div v-if="item.gpa || item.ranking" class="timeline-tags">
                      <a-tag v-if="item.gpa" color="blue" class="info-tag">GPA: {{ item.gpa }}</a-tag>
                      <a-tag v-if="item.ranking" color="cyan" class="info-tag">{{ item.ranking }}</a-tag>
                    </div>
                  </div>
                </section>

                <!-- 工作经历 -->
                <section v-if="summary.work.length" class="summary-section">
                  <div class="section-title">
                    <Briefcase :size="16" />
                    工作经历
                  </div>
                  <div
                    v-for="(item, index) in summary.work"
                    :key="`work-${index}`"
                    class="timeline-item"
                  >
                    <div class="timeline-head">
                      <div class="timeline-title">{{ item.company }}</div>
                      <div v-if="item.duration" class="timeline-date">
                        <CalendarDays :size="13" />
                        <span>{{ item.duration }}</span>
                      </div>
                    </div>
                    <div v-if="item.position" class="timeline-subtitle">{{ item.position }}</div>
                    <div v-if="item.highlights?.length" class="timeline-details">
                      <p v-for="(h, hi) in item.highlights" :key="hi">
                        <span class="bullet">·</span> {{ h }}
                      </p>
                    </div>
                  </div>
                </section>

                <!-- 项目经历 -->
                <section v-if="summary.projects.length" class="summary-section">
                  <div class="section-title">
                    <FolderGit :size="16" />
                    项目经历
                  </div>
                  <div
                    v-for="(item, index) in summary.projects"
                    :key="`project-${index}`"
                    class="timeline-item"
                  >
                    <div class="timeline-head">
                      <div class="timeline-title">{{ item.name }}</div>
                      <div v-if="item.duration" class="timeline-date">
                        <CalendarDays :size="13" />
                        <span>{{ item.duration }}</span>
                      </div>
                    </div>
                    <div v-if="item.role" class="timeline-subtitle">{{ item.role }}</div>
                    <div v-if="item.tech_stack?.length" class="timeline-tags">
                      <a-tag v-for="tech in item.tech_stack" :key="tech" color="purple" class="info-tag">
                        {{ tech }}
                      </a-tag>
                    </div>
                    <div v-if="item.description" class="timeline-desc">{{ item.description }}</div>
                    <div v-if="item.results?.length" class="timeline-details">
                      <p v-for="(r, ri) in item.results" :key="ri">
                        <span class="bullet green">✓</span> {{ r }}
                      </p>
                    </div>
                  </div>
                </section>

                <!-- 获奖情况 -->
                <section v-if="summary.awards.length" class="summary-section">
                  <div class="section-title">
                    <Award :size="16" />
                    获奖情况
                  </div>
                  <div class="awards-grid">
                    <div v-for="(award, index) in summary.awards" :key="`award-${index}`" class="award-card">
                      <Trophy :size="14" class="award-icon" />
                      {{ award }}
                    </div>
                  </div>
                </section>

                <!-- 培训经历 -->
                <section v-if="summary.training.length" class="summary-section">
                  <div class="section-title">
                    <BookOpen :size="16" />
                    培训经历
                  </div>
                  <div class="training-list">
                    <div v-for="(t, i) in summary.training" :key="i" class="training-item">
                      {{ t }}
                    </div>
                  </div>
                </section>
              </div>

              <!-- 右侧侧边栏 -->
              <div class="summary-side">
                <!-- 求职偏好 -->
                <section v-if="summary.jobPreference" class="summary-section side-card">
                  <div class="section-title">
                    <Target :size="16" />
                    求职偏好
                  </div>
                  <div class="preference-list">
                    <div v-if="summary.jobPreference.job_intention" class="pref-item">
                      <span class="pref-label">意向岗位</span>
                      <span class="pref-value">{{ summary.jobPreference.job_intention }}</span>
                    </div>
                    <div v-if="summary.jobPreference.expected_salary" class="pref-item">
                      <span class="pref-label">期望薪资</span>
                      <span class="pref-value">{{ summary.jobPreference.expected_salary }}</span>
                    </div>
                    <div v-if="summary.jobPreference.desired_location" class="pref-item">
                      <span class="pref-label">期望地点</span>
                      <span class="pref-value">{{ summary.jobPreference.desired_location }}</span>
                    </div>
                  </div>
                </section>

                <!-- 技能标签 -->
                <section v-if="skillTags.length" class="summary-section side-card">
                  <div class="section-title">
                    <Wrench :size="16" />
                    技能标签
                  </div>
                  <div class="skills-category">
                    <div v-if="skillTags.technical.length" class="skill-group">
                      <div class="skill-group-label">技术技能</div>
                      <div class="skills-wrap">
                        <a-tag
                          v-for="skill in skillTags.technical"
                          :key="skill"
                          color="blue"
                          class="skill-tag"
                        >
                          {{ skill }}
                        </a-tag>
                      </div>
                    </div>
                    <div v-if="skillTags.languages.length" class="skill-group">
                      <div class="skill-group-label">语言能力</div>
                      <div class="skills-wrap">
                        <a-tag
                          v-for="lang in skillTags.languages"
                          :key="lang"
                          color="green"
                          class="skill-tag"
                        >
                          {{ lang }}
                        </a-tag>
                      </div>
                    </div>
                    <div v-if="skillTags.certifications.length" class="skill-group">
                      <div class="skill-group-label">证书资质</div>
                      <div class="skills-wrap">
                        <a-tag
                          v-for="cert in skillTags.certifications"
                          :key="cert"
                          color="orange"
                          class="skill-tag"
                        >
                          {{ cert }}
                        </a-tag>
                      </div>
                    </div>
                  </div>
                </section>

                <!-- 自我评价 -->
                <section v-if="summary.selfEvaluation" class="summary-section side-card">
                  <div class="section-title">
                    <MessageSquare :size="16" />
                    自我评价
                  </div>
                  <div class="self-eval-text">{{ summary.selfEvaluation }}</div>
                </section>

                <!-- 简历信息 -->
                <section class="summary-section side-card meta-section">
                  <div class="section-title">
                    <FileText :size="16" />
                    简历信息
                  </div>
                  <a-descriptions :column="1" size="small" class="meta-descriptions">
                    <a-descriptions-item label="文件名">{{ resume.filename }}</a-descriptions-item>
                    <a-descriptions-item label="文件大小">{{ formatFileSize(resume.file_size) }}</a-descriptions-item>
                    <a-descriptions-item label="解析状态">
                      <a-tag :color="resume.summary_status === 'completed' ? 'success' : 'warning'" size="small">
                        {{ statusText }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item label="更新时间">
                      {{ formatDateTime(resume.updated_at || resume.created_at) }}
                    </a-descriptions-item>
                  </a-descriptions>
                </section>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-if="!hasSummaryData" class="empty-state">
              <a-empty description="暂未从当前简历中提取到结构化信息">
                <template #image>
                  <FileSearch :size="48" class="empty-icon" />
                </template>
              </a-empty>
              <p class="empty-hint">简历正在解析中，请稍后刷新页面</p>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="state-wrapper">
        <a-empty description="未找到该简历" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeft,
  CalendarDays,
  Mail,
  Phone,
  RefreshCw,
  Trash2,
  MapPin,
  Github,
  GraduationCap,
  Briefcase,
  FolderGit,
  Award,
  Trophy,
  BookOpen,
  Target,
  Wrench,
  MessageSquare,
  FileText,
  FileSearch,
  Plus,
  Star,
  Zap,
  Code2,
  Globe,
  TrendingUp
} from 'lucide-vue-next'

import HeaderComponent from '@/components/HeaderComponent.vue'
import { resumeApi } from '@/apis/resume_api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const deleting = ref(false)
const resume = ref(null)

// 知名公司列表（用于亮点标记）
const FAMOUS_COMPANIES = ['腾讯', '阿里', '字节', '百度', '京东', '美团', '拼多多', '华为', '网易', '滴滴', '快手', '哔哩', '小米', 'OPPO', 'vivo', '蚂蚁', '饿了么']

// 优先使用 LLM 提取的 summary_json，fallback 到 structured_resume
const summary = computed(() => {
  // 尝试从 summary_json（LLM 提取）获取数据
  const llmData = resume.value?.summary_json
  // fallback 到 structured_resume（旧规则解析）
  const legacyData = resume.value?.structured_resume

  const data = llmData || legacyData || {}

  // 教育经历：兼容两种格式
  // summary_json: [{school, major, degree, gpa, ranking, duration}]
  // structured_resume: [{title, subtitle, date, details}]
  const education = (data.education || []).map(item => ({
    school: item.school || item.title || '',
    major: item.major || item.subtitle || '',
    degree: item.degree || '',
    gpa: item.gpa || '',
    ranking: item.ranking || '',
    duration: item.duration || item.date || ''
  }))

  // 工作经历：兼容两种格式
  // summary_json: [{company, position, duration, highlights}]
  // structured_resume: [{title, subtitle, date, details}]
  const work = (data.work_experience || data.work || []).map(item => ({
    company: item.company || item.title || '',
    position: item.position || item.subtitle || '',
    duration: item.duration || item.date || '',
    highlights: item.highlights || item.details || []
  }))

  // 项目经历：兼容两种格式
  // summary_json: [{name, role, tech_stack, description, results, duration}]
  // structured_resume: [{title, subtitle, date, details}]
  const projects = (data.project_experience || data.projects || []).map(item => ({
    name: item.name || item.title || '',
    role: item.role || item.subtitle || '',
    tech_stack: item.tech_stack || [],
    description: item.description || '',
    results: item.results || [],
    duration: item.duration || item.date || ''
  }))

  return {
    name: data.basic_info?.name || data.name || resume.value?.filename?.replace(/\.pdf$/i, '') || '简历',
    phone: data.basic_info?.phone || data.phone || '',
    email: data.basic_info?.email || data.email || '',
    basicInfo: data.basic_info || {},
    education,
    work,
    projects,
    skills: data.skills || {},
    awards: data.awards || [],
    training: data.training || [],
    selfEvaluation: data.self_evaluation || '',
    jobPreference: data.job_preference || {}
  }
})

const hasSummaryData = computed(() => {
  const s = summary.value
  return (
    s.basicInfo?.name ||
    s.education?.length ||
    s.work?.length ||
    s.projects?.length ||
    s.skills?.technical?.length ||
    s.awards?.length
  )
})

// 简历完整度评分
const completenessScore = computed(() => {
  const s = summary.value
  let score = 0
  let total = 0

  // 基础信息 20%
  if (s.basicInfo?.name) score += 5
  if (s.basicInfo?.phone) score += 3
  if (s.basicInfo?.email) score += 3
  if (s.basicInfo?.location) score += 3
  if (s.basicInfo?.github || s.basicInfo?.linkedin) score += 6
  total += 20

  // 教育经历 15%
  if (s.education?.length) score += 15
  total += 15

  // 工作经历 20%
  if (s.work?.length) score += 20
  total += 20

  // 项目经历 20%
  if (s.projects?.length) score += 20
  total += 20

  // 技能 10%
  if (s.skills?.technical?.length) score += 10
  total += 10

  // 获奖/培训/自我评价 15%
  if (s.awards?.length) score += 5
  if (s.training?.length) score += 5
  if (s.selfEvaluation) score += 5
  total += 15

  return Math.round((score / total) * 100)
})

const completenessClass = computed(() => {
  const score = completenessScore.value
  if (score >= 80) return 'high'
  if (score >= 60) return 'medium'
  return 'low'
})

const completenessColor = computed(() => {
  const score = completenessScore.value
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#f5222d'
})

const completenessTips = computed(() => {
  const tips = []
  const s = summary.value
  if (!s.basicInfo?.github && !s.basicInfo?.linkedin) tips.push('添加 GitHub/LinkedIn')
  if (!s.basicInfo?.phone) tips.push('补充手机号')
  if (!s.basicInfo?.email) tips.push('补充邮箱')
  if (!s.education?.length) tips.push('补充教育经历')
  if (!s.work?.length) tips.push('补充工作经历')
  if (!s.projects?.length) tips.push('补充项目经历')
  if (!s.awards?.length) tips.push('补充获奖情况')
  if (!s.selfEvaluation) tips.push('添加自我评价')
  return tips.slice(0, 3)
})

// 亮点标签
const highlightTags = computed(() => {
  const tags = []
  const s = summary.value

  // 高 GPA
  if (s.education?.[0]?.gpa) {
    const gpaStr = s.education[0].gpa.toString()
    if (/\b(3\.[7-9]|4\.0|前10%|前5%|前3%)\b/i.test(gpaStr)) {
      tags.push({ text: '高 GPA', color: 'gold', icon: TrendingUp })
    }
  }

  // 名企经验
  if (s.work?.some(w => FAMOUS_COMPANIES.some(c => (w.company || '').includes(c)))) {
    tags.push({ text: '名企经验', color: 'red', icon: Star })
  }

  // 有 GitHub
  if (s.basicInfo?.github) {
    tags.push({ text: '有开源作品', color: 'purple', icon: Code2 })
  }

  // 有 LinkedIn
  if (s.basicInfo?.linkedin) {
    tags.push({ text: '有 LinkedIn', color: 'blue', icon: Globe })
  }

  // 竞赛获奖
  if (s.awards?.length) {
    tags.push({ text: '竞赛获奖', color: 'orange', icon: Trophy })
  }

  // 多个项目
  if (s.projects?.length >= 3) {
    tags.push({ text: '项目丰富', color: 'cyan', icon: FolderGit })
  }

  // 技术栈多
  if (s.skills?.technical?.length >= 5) {
    tags.push({ text: '技术栈广', color: 'green', icon: Zap })
  }

  return tags.slice(0, 4)
})

// 技能分类
const skillTags = computed(() => {
  const skills = summary.value.skills || {}
  return {
    technical: skills.technical || [],
    languages: skills.languages || [],
    certifications: skills.certifications || []
  }
})

// 简历状态文字
const statusText = computed(() => {
  const status = resume.value?.summary_status
  const map = {
    completed: '已完成',
    processing: '处理中',
    failed: '失败',
    pending: '等待中'
  }
  return map[status] || '未知'
})

const formatGithubUrl = (url) => {
  if (!url) return ''
  return url.replace(/^https?:\/\/github\.com\/?/, '').replace(/\/$/, '')
}

const loadResumeDetail = async () => {
  loading.value = true
  try {
    const data = await resumeApi.getResumeDetail(route.params.resume_id)
    resume.value = data?.resume || null
  } catch (error) {
    console.error('加载简历详情失败:', error)
    message.error(error.message || '加载简历详情失败')
    resume.value = null
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/resume')
}

const handleDelete = async () => {
  if (!resume.value?.id) {
    return
  }

  try {
    deleting.value = true
    await resumeApi.deleteResume(resume.value.id)
    message.success('简历已删除')
    router.push('/resume')
  } catch (error) {
    console.error('删除简历失败:', error)
    message.error(error.message || '删除简历失败')
  } finally {
    deleting.value = false
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) {
    return '0 B'
  }

  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }

  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

const formatDateTime = (value) => {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

onMounted(() => {
  loadResumeDetail()
})
</script>

<style scoped lang="less">
.resume-detail-page {
  min-height: 100%;
  background: var(--gray-25);
}

.resume-detail-content {
  padding: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  align-items: start;
}

.summary-panel {
  border: 1px solid var(--gray-200);
  border-radius: 20px;
  background: var(--gray-0);
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
}

// Hero 区域 - 专业深蓝色调
.summary-hero {
  position: relative;
  padding: 36px 40px 28px;
  background: linear-gradient(135deg, #1e3a5f 0%, #2d4a6f 50%, #1a365d 100%);
  color: #fff;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    pointer-events: none;
  }
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 24px;
}

.hero-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0.1) 100%);
  backdrop-filter: blur(12px);
  border: 3px solid rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  position: relative;
  overflow: hidden;

  // 照片占位符纹理
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, transparent 50%);
    pointer-events: none;
  }
}

.hero-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.hero-name {
  font-size: 32px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: 1px;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.hero-contact {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 28px;
  margin-top: 16px;
}

.contact-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  opacity: 0.95;
  background: rgba(255, 255, 255, 0.12);
  padding: 6px 14px;
  border-radius: 20px;
  backdrop-filter: blur(8px);
  transition: all 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }

  a {
    color: inherit;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}

.hero-link {
  color: #fff !important;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.highlight-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  backdrop-filter: blur(8px);
  transition: all 0.2s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    transform: translateY(-1px);
  }
}

// 完整度条
.completeness-bar {
  padding: 20px 40px;
  background: linear-gradient(180deg, rgba(30, 58, 95, 0.04) 0%, transparent 100%);
  border-bottom: 1px solid rgba(30, 58, 95, 0.08);
}

.completeness-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.completeness-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-700);
  display: flex;
  align-items: center;
  gap: 6px;

  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    background: #1e3a5f;
    border-radius: 2px;
  }
}

.completeness-score {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.5px;

  &.high { color: #52c41a; }
  &.medium { color: #faad14; }
  &.low { color: #f5222d; }
}

.completeness-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.tip-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--gray-600);
  background: var(--gray-50);
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid var(--gray-200);

  svg {
    color: #1e3a5f;
  }
}

// 正文区域
.summary-body {
  padding: 28px 40px;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 32px;
  align-items: start;
}

.summary-section {
  & + .summary-section {
    margin-top: 32px;
  }
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 2px solid #1e3a5f;
  color: #1e3a5f;
  font-size: 17px;
  font-weight: 700;
  position: relative;

  svg {
    opacity: 0.8;
  }
}

// 时间线样式
.timeline-item {
  padding: 20px 22px;
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  background: var(--gray-0);
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    background: linear-gradient(180deg, #1e3a5f 0%, #2d4a6f 100%);
    opacity: 0;
    transition: opacity 0.25s ease;
  }

  &:hover {
    border-color: rgba(30, 58, 95, 0.3);
    box-shadow: 0 4px 16px rgba(30, 58, 95, 0.08);
    transform: translateY(-2px);

    &::before {
      opacity: 1;
    }
  }

  & + .timeline-item {
    margin-top: 16px;
  }
}

.timeline-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.timeline-title {
  color: var(--gray-950);
  font-size: 17px;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: 0.2px;
}

.timeline-date {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--gray-500);
  font-size: 13px;
  background: var(--gray-50);
  padding: 4px 10px;
  border-radius: 12px;
}

.timeline-subtitle {
  margin-top: 6px;
  color: #2d4a6f;
  font-size: 14px;
  font-weight: 600;
}

.timeline-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.info-tag {
  border-radius: 8px;
  font-size: 12px;
  padding: 3px 10px;
  font-weight: 500;
}

.timeline-desc {
  margin-top: 12px;
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.8;
  padding: 12px 16px;
  background: var(--gray-50);
  border-radius: 10px;
  border-left: 3px solid var(--gray-300);
}

.timeline-details {
  margin-top: 12px;
  color: var(--gray-800);
  font-size: 14px;
  line-height: 1.9;

  p {
    margin: 0;
    display: flex;
    align-items: flex-start;
    gap: 10px;

    & + p {
      margin-top: 8px;
    }
  }

  .bullet {
    color: #1e3a5f;
    font-weight: 700;
    font-size: 16px;
    line-height: 1.4;

    &.green {
      color: #52c41a;
    }
  }
}

// 获奖卡片
.awards-grid {
  display: grid;
  gap: 12px;
}

.award-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--gray-200);
  border-left: 4px solid #faad14;
  border-radius: 12px;
  color: var(--gray-900);
  line-height: 1.6;
  background: linear-gradient(135deg, var(--gray-0) 0%, #fffbeb 100%);
  transition: all 0.25s ease;

  &:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 12px rgba(250, 173, 20, 0.15);
  }
}

.award-icon {
  color: #faad14;
  flex-shrink: 0;
}

// 培训
.training-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.training-item {
  padding: 14px 18px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  color: var(--gray-800);
  font-size: 14px;
  background: var(--gray-0);
  transition: all 0.25s ease;

  &:hover {
    border-color: #1e3a5f;
    background: rgba(30, 58, 95, 0.02);
  }
}

// 侧边栏卡片
.side-card {
  padding: 22px;
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  background: var(--gray-0);
  transition: all 0.25s ease;

  &:hover {
    border-color: rgba(30, 58, 95, 0.2);
    box-shadow: 0 4px 16px rgba(30, 58, 95, 0.06);
  }
}

// 求职偏好
.preference-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pref-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 14px;
  background: var(--gray-50);
  border-radius: 10px;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(30, 58, 95, 0.04);
  }
}

.pref-label {
  font-size: 12px;
  color: var(--gray-500);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pref-value {
  font-size: 15px;
  color: var(--gray-900);
  font-weight: 600;
}

// 技能
.skills-category {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skill-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-group-label {
  font-size: 12px;
  color: var(--gray-500);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 6px;

  &::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--gray-200);
  }
}

.skills-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.skill-tag {
  border-radius: 10px;
  font-size: 13px;
  padding: 5px 12px;
  font-weight: 500;
  transition: all 0.2s ease;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

// 自我评价
.self-eval-text {
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.9;
  padding: 16px;
  background: var(--gray-50);
  border-radius: 12px;
  border-left: 4px solid #1e3a5f;
}

// 元信息
.meta-section {
  background: linear-gradient(180deg, var(--gray-50) 0%, var(--gray-0) 100%);
  border-color: var(--gray-200);
}

.meta-descriptions {
  :deep(.ant-descriptions-item-label) {
    color: var(--gray-500);
    font-size: 12px;
    font-weight: 500;
  }

  :deep(.ant-descriptions-item-content) {
    font-size: 13px;
    color: var(--gray-700);
  }
}

// 空状态
.empty-state {
  padding: 80px 40px;
  text-align: center;
  background: linear-gradient(180deg, var(--gray-50) 0%, var(--gray-0) 100%);
}

.empty-icon {
  color: var(--gray-300);
}

.empty-hint {
  margin-top: 16px;
  color: var(--gray-500);
  font-size: 14px;
}

.state-wrapper {
  min-height: calc(100vh - 220px);
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 1100px) {
  .summary-body {
    grid-template-columns: 1fr;
  }

  .summary-hero {
    padding: 28px 24px 24px;
  }

  .hero-name {
    font-size: 28px;
  }

  .hero-top {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .hero-avatar {
    width: 64px;
    height: 64px;
    font-size: 24px;
  }

  .hero-contact {
    gap: 10px 16px;
  }

  .summary-body {
    padding: 20px 20px;
  }
}

@media (max-width: 780px) {
  .summary-hero {
    padding: 24px 20px 20px;
  }

  .hero-name {
    font-size: 24px;
  }

  .hero-avatar {
    width: 56px;
    height: 56px;
    font-size: 22px;
  }

  .summary-body {
    padding: 16px;
  }

  .hero-tags {
    gap: 8px;
  }

  .highlight-tag {
    font-size: 12px;
    padding: 5px 12px;
  }
}
</style>
