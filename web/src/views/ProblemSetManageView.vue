<template>
  <div class="problemset-page">
    <div class="page-topbar">
      <div class="topbar-left">
        <h1 class="page-title">题库管理</h1>
        <p class="page-subtitle">{{ headerDescription }}</p>
      </div>
      <div class="topbar-actions">
        <a-button class="btn-secondary" :loading="loading" @click="loadProblemsets">刷新</a-button>
      </div>
    </div>

    <div class="summary-grid">
      <div v-for="item in overviewCards" :key="item.key" class="summary-card">
        <div class="summary-icon">
          <component :is="item.icon" />
        </div>
        <div class="summary-content">
          <div class="summary-label">{{ item.label }}</div>
          <div class="summary-value">{{ item.value }}</div>
          <div class="summary-hint">{{ item.hint }}</div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
    </div>

    <div v-else-if="!problems.length" class="empty-state">
      <h3 class="empty-title">暂无已导入题目</h3>
      <p class="empty-description">
        请先使用 freeproblemset 导入题包，导入完成后这里会自动生成题库概览。
      </p>
    </div>

    <div v-else class="page-main">
      <div class="toolbar-panel">
        <div class="toolbar-main">
          <a-input
            v-model:value="filters.keyword"
            allow-clear
            placeholder="搜索题目标题、题包路径或主题"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>

          <div class="toolbar-inline-filters">
            <div class="filter-chip-group">
              <span class="filter-chip-label">题面</span>
              <button
                v-for="item in languageQuickFilters"
                :key="`page-language-${item.value}`"
                type="button"
                class="filter-chip-button"
                :class="{ active: filters.statementLanguage === item.value }"
                @click="toggleStatementLanguage(item.value)"
              >
                {{ item.label }}
              </button>
            </div>
          </div>

          <a-select v-model:value="filters.difficulty" :options="difficultyOptions" />

          <a-button class="btn-secondary" @click="resetFilters">重置</a-button>
        </div>

        <div class="toolbar-meta">
          <span
            >当前显示 {{ filteredProblemCount }} 道题，覆盖
            {{ filteredPackageCount }} 个题包。</span
          >
          <span>{{ trackingSummaryText }}</span>
          <span v-if="hasActiveFilters">筛选仅作为辅助收敛，分类判断仍以三张题库卡片为主。</span>
          <span v-else>支持关键词、题面语言和难度轻筛选，不重复岗位分类。</span>
        </div>
      </div>

      <div v-if="!filteredProblemCount" class="filter-empty-state">
        <p class="empty-title">当前筛选条件下暂无题目</p>
        <p class="empty-description">调整关键词、题面语言或难度，或直接清空筛选查看全部题目。</p>
        <a-button class="btn-primary" type="primary" @click="resetFilters">清空筛选</a-button>
      </div>

      <div v-else class="group-grid">
        <div
          v-for="group in problemGroups"
          :key="group.key"
          class="group-card"
          :class="[`group-card--${group.key}`, { empty: !group.items.length }]"
          @click="handleGroupClick(group)"
        >
          <div class="group-card-top">
            <div class="group-icon">
              <component :is="group.icon" />
            </div>
            <span class="badge badge--solid">{{ group.items.length }} 题</span>
          </div>

          <div class="group-title-row">
            <div>
              <h3 class="group-title">{{ group.title }}</h3>
              <p class="group-description">{{ group.description }}</p>
            </div>
            <span class="group-package-count">{{ group.packageCount }} 个题包</span>
          </div>

          <div class="group-metric-grid">
            <div class="group-metric-card">
              <span class="metric-label">题目数</span>
              <strong>{{ group.items.length }}</strong>
            </div>
            <div class="group-metric-card">
              <span class="metric-label">题包数</span>
              <strong>{{ group.packageCount }}</strong>
            </div>
          </div>

          <div class="group-section">
            <div class="section-label">题面语言</div>
            <div class="chip-row">
              <span
                v-for="item in group.languageStats"
                :key="`${group.key}-language-${item.key}`"
                class="badge"
              >
                {{ item.label }} · {{ item.count }}
              </span>
            </div>
          </div>

          <div class="group-section">
            <div class="section-label">题目难度</div>
            <div class="chip-row">
              <span
                v-for="item in group.difficultyStats"
                :key="`${group.key}-difficulty-${item.key}`"
                class="badge"
              >
                {{ item.label }} · {{ item.count }}
              </span>
            </div>
          </div>

          <div v-if="group.topTopicTags.length" class="group-section">
            <div class="section-label">高频主题</div>
            <div class="chip-row">
              <span
                v-for="tag in group.topTopicTags"
                :key="`${group.key}-topic-${tag.tag}`"
                class="badge"
              >
                {{ tag.tag }} · {{ tag.count }}
              </span>
              <span v-if="group.hiddenTopicCount > 0" class="badge badge--muted"
                >+{{ group.hiddenTopicCount }}</span
              >
            </div>
          </div>

          <div v-if="group.previewTitles.length" class="group-section group-preview">
            <div class="section-label">浏览题目</div>
            <div class="preview-list">
              <div
                v-for="title in group.previewTitles"
                :key="`${group.key}-preview-${title}`"
                class="preview-item"
              >
                <span class="preview-dot" />
                <span class="preview-text">{{ title }}</span>
              </div>
            </div>
          </div>

          <div class="group-footer">
            <span class="group-footer-text">进入分类详情，浏览题目列表与题面内容</span>
            <a-button
              class="btn-secondary"
              :disabled="!group.items.length"
              @click.stop="openGroupDetail(group)"
            >
              查看题目
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <a-drawer
      :open="detailVisible"
      :title="activeGroup ? `${activeGroup.title} 题目详情` : '题目详情'"
      width="min(1280px, 94vw)"
      placement="right"
      class="problemset-drawer"
      :body-style="{ padding: '0' }"
      @close="closeDetail"
    >
      <div v-if="detailGroupLoading && !detailProblems.length" class="drawer-state">
        <a-spin size="large" />
      </div>

      <div v-else-if="!detailProblems.length" class="drawer-state">
        <p class="empty-description">暂无题目详情</p>
      </div>

      <div v-else class="detail-layout">
        <aside class="problem-list-panel">
          <div class="problem-list-header">
            <div>
              <div class="drawer-group-title">{{ activeGroup?.title }}</div>
              <div class="drawer-group-meta">
                {{ detailFilteredProblems.length }}
                <template v-if="hasDetailFilters"> / {{ detailProblems.length }}</template>
                题
              </div>
            </div>
            <span class="drawer-group-caption">面试题浏览器</span>
          </div>

          <div class="drawer-filter-stack">
            <a-input
              v-model:value="detailFilters.keyword"
              allow-clear
              placeholder="搜索题目标题或题包"
            >
              <template #prefix>
                <SearchOutlined />
              </template>
            </a-input>

            <div class="drawer-filter-grid">
              <div class="drawer-filter-field">
                <span class="drawer-field-label">题面语言</span>
                <div class="filter-chip-group compact">
                  <button
                    v-for="item in languageQuickFilters"
                    :key="`detail-language-${item.value}`"
                    type="button"
                    class="filter-chip-button"
                    :class="{ active: detailFilters.statementLanguage === item.value }"
                    @click="toggleStatementLanguage(item.value, 'detail')"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </div>

              <div class="drawer-filter-field">
                <span class="drawer-field-label">题目难度</span>
                <a-select v-model:value="detailFilters.difficulty" :options="difficultyOptions" />
              </div>
            </div>

            <div class="drawer-filter-tip">
              左侧列表会按关键词、题面语言和难度即时过滤。
              <a-button
                v-if="hasDetailFilters"
                type="link"
                class="drawer-reset-btn"
                @click="resetDetailFilters"
              >
                清空
              </a-button>
            </div>
          </div>

          <div
            v-if="detailFilteredProblems.length"
            class="problem-list"
            @scroll="handleProblemListScroll"
          >
            <button
              v-for="problem in displayedDetailProblems"
              :key="problemKey(problem)"
              type="button"
              class="problem-list-item"
              :class="{ active: activeProblemKey === problemKey(problem) }"
              @click="selectProblem(problem)"
            >
              <div class="problem-list-item-top">
                <span class="problem-index">#{{ problem.problem_index }}</span>
                <span class="problem-name">{{ problem.displayTitle }}</span>
              </div>
              <div class="problem-meta-row">
                <span class="problem-package">{{ problem.packageName }}</span>
                <span class="meta-tag-group">
                  <span class="badge">{{
                    statementLanguageLabelMap[problem.statement_language] || '未知'
                  }}</span>
                  <span class="badge">{{
                    difficultyLabelMap[problem.difficulty_tag] || '中等'
                  }}</span>
                </span>
              </div>
            </button>
          </div>

          <div v-else class="drawer-state drawer-state--inner">
            <p class="empty-description">筛选后暂无匹配题目</p>
            <a-button class="btn-secondary" @click="resetDetailFilters">清空筛选</a-button>
          </div>
        </aside>

        <section class="problem-detail-panel">
          <div v-if="detailLoading" class="detail-loading-mask">
            <a-spin size="large" />
          </div>

          <div v-if="activeProblem" class="detail-content">
            <div class="detail-body">
              <div class="detail-hero">
                <div class="detail-heading">
                  <div class="detail-eyebrow">题号 #{{ activeProblem.problem_index }}</div>
                  <h2 class="detail-title">{{ activeProblem.displayTitle }}</h2>
                  <p v-if="activeProblem.displaySummary" class="detail-summary">
                    {{ activeProblem.displaySummary }}
                  </p>
                </div>

                <div class="detail-info-grid">
                  <div class="detail-info-item detail-info-item--wide">
                    <span class="detail-info-label">来源</span>
                    <strong class="detail-info-value">{{ activeProblem.displaySource }}</strong>
                  </div>
                  <div class="detail-info-item">
                    <span class="detail-info-label">题包文件</span>
                    <strong class="detail-info-value">{{ activeProblem.packageName }}</strong>
                  </div>
                  <div class="detail-info-item">
                    <span class="detail-info-label">OJ 标识</span>
                    <strong class="detail-info-value">
                      {{
                        activeProblem.oj_display_ids?.length
                          ? activeProblem.oj_display_ids.join(', ')
                          : '未标注'
                      }}
                    </strong>
                  </div>
                  <div class="detail-info-item detail-info-item--wide">
                    <span class="detail-info-label">题包路径</span>
                    <strong class="detail-info-value">{{ activeProblem.package_path }}</strong>
                  </div>
                </div>
              </div>

              <div class="detail-tag-row">
                <span
                  v-for="tag in activeProblem.position_tags || []"
                  :key="`position-${tag}`"
                  class="badge badge--solid"
                >
                  {{ positionLabelMap[tag] || tag }}
                </span>
                <span class="badge">{{
                  statementLanguageLabelMap[activeProblem.statement_language] || '未知'
                }}</span>
                <span class="badge">{{
                  difficultyLabelMap[activeProblem.difficulty_tag] || '中等'
                }}</span>
                <span v-for="tag in visibleDetailExtraTags" :key="tag.id" class="badge">
                  {{ tag.label }}
                </span>
                <button
                  v-if="hiddenDetailExtraTagCount > 0"
                  type="button"
                  class="detail-tag-toggle"
                  @click="showAllDetailTags = true"
                >
                  +{{ hiddenDetailExtraTagCount }} 更多
                </button>
                <button
                  v-else-if="
                    showAllDetailTags && detailExtraTags.length > DETAIL_EXTRA_TAG_PREVIEW_COUNT
                  "
                  type="button"
                  class="detail-tag-toggle"
                  @click="showAllDetailTags = false"
                >
                  收起标签
                </button>
              </div>

              <div class="detail-section">
                <div class="detail-section-header">
                  <h3>题目描述</h3>
                  <a-button
                    v-if="canToggleText(activeProblem.displayDescription)"
                    type="link"
                    class="section-toggle-btn"
                    @click="toggleExpanded('description')"
                  >
                    {{ expandedSections.description ? '收起' : '展开' }}
                  </a-button>
                </div>
                <p
                  class="detail-paragraph"
                  :class="{
                    collapsed:
                      canToggleText(activeProblem.displayDescription) &&
                      !expandedSections.description
                  }"
                >
                  {{ activeProblem.displayDescription }}
                </p>
              </div>

              <div v-if="activeProblem.input_description" class="detail-section">
                <div class="detail-section-header">
                  <h3>输入说明</h3>
                  <a-button
                    v-if="canToggleText(activeProblem.displayInputDescription)"
                    type="link"
                    class="section-toggle-btn"
                    @click="toggleExpanded('input')"
                  >
                    {{ expandedSections.input ? '收起' : '展开' }}
                  </a-button>
                </div>
                <p
                  class="detail-paragraph"
                  :class="{
                    collapsed:
                      canToggleText(activeProblem.displayInputDescription) &&
                      !expandedSections.input
                  }"
                >
                  {{ activeProblem.displayInputDescription }}
                </p>
              </div>

              <div v-if="activeProblem.output_description" class="detail-section">
                <div class="detail-section-header">
                  <h3>输出说明</h3>
                  <a-button
                    v-if="canToggleText(activeProblem.displayOutputDescription)"
                    type="link"
                    class="section-toggle-btn"
                    @click="toggleExpanded('output')"
                  >
                    {{ expandedSections.output ? '收起' : '展开' }}
                  </a-button>
                </div>
                <p
                  class="detail-paragraph"
                  :class="{
                    collapsed:
                      canToggleText(activeProblem.displayOutputDescription) &&
                      !expandedSections.output
                  }"
                >
                  {{ activeProblem.displayOutputDescription }}
                </p>
              </div>

              <div v-if="activeProblem.examples?.length" class="detail-section">
                <div class="detail-section-header">
                  <h3>示例</h3>
                </div>
                <div class="example-grid">
                  <div
                    v-for="(example, index) in activeProblem.examples"
                    :key="index"
                    class="example-card"
                  >
                    <div>
                      <strong>输入</strong>
                      <pre>{{ example.displayInput }}</pre>
                    </div>
                    <div>
                      <strong>输出</strong>
                      <pre>{{ example.displayOutput }}</pre>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="starterCodeEntries.length" class="detail-section">
                <div class="detail-section-header">
                  <h3>模板代码</h3>
                </div>
                <div class="starter-grid">
                  <div
                    v-for="entry in starterCodeEntries"
                    :key="entry.language"
                    class="starter-card"
                  >
                    <div class="starter-header">
                      {{ languageLabelMap[entry.language] || entry.language }}
                    </div>
                    <pre>{{ entry.code }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="detail-empty">
            <p class="empty-description">请选择左侧题目查看详情</p>
          </div>
        </section>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  AppstoreOutlined,
  BookOutlined,
  DesktopOutlined,
  InboxOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'

import { problemsetApi } from '@/apis/problemset_api'

const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const detailGroupLoading = ref(false)
const problems = ref([])
const summary = ref({
  imported_package_count: 0,
  imported_problem_count: 0,
  tracked_package_count: 0,
  tracked_problem_count: 0
})

const activeGroup = ref(null)
const detailProblems = ref([])
const activeProblem = ref(null)
const activeProblemKey = ref('')
const packageDetailCache = new Map()
const DETAIL_LIST_PAGE_SIZE = 120
const detailListRenderCount = ref(DETAIL_LIST_PAGE_SIZE)

const filters = reactive({
  keyword: '',
  statementLanguage: '',
  difficulty: 'all'
})

const detailFilters = reactive({
  keyword: '',
  statementLanguage: '',
  difficulty: 'all'
})

const expandedSections = reactive({
  description: false,
  input: false,
  output: false
})
const showAllDetailTags = ref(false)
const DETAIL_EXTRA_TAG_PREVIEW_COUNT = 6

const languageLabelMap = {
  javascript: 'JavaScript',
  c: 'C',
  cpp: 'C++',
  java: 'Java',
  python: 'Python'
}

const statementLanguageLabelMap = {
  zh: '中文题面',
  en: '英文题面',
  mixed: '中英混合',
  unknown: '语言未知'
}

const difficultyLabelMap = {
  easy: '简单',
  medium: '中等',
  hard: '困难'
}

const positionLabelMap = {
  frontend: '前端',
  backend: '后端',
  algorithm_general: '通用'
}

const positionGroupDefs = [
  {
    key: 'frontend',
    title: '前端',
    icon: DesktopOutlined,
    description: '优先适配前端岗位的题目，适合页面交互、工程化与浏览器能力考察。'
  },
  {
    key: 'backend',
    title: '后端',
    icon: ApiOutlined,
    description: '优先适配后端岗位的题目，便于快速抽查数据结构、系统设计与服务能力。'
  },
  {
    key: 'algorithm_general',
    title: '通用',
    icon: AppstoreOutlined,
    description: '算法与通用编程能力题目，适合公共题池和基础能力面试场景。'
  }
]

const languageQuickFilters = [
  { label: '中文题面', value: 'zh' },
  { label: '英文题面', value: 'en' }
]

const difficultyOptions = [
  { label: '全部难度', value: 'all' },
  { label: '简单', value: 'easy' },
  { label: '中等', value: 'medium' },
  { label: '困难', value: 'hard' }
]

const htmlDecoder =
  typeof window !== 'undefined' && typeof document !== 'undefined'
    ? document.createElement('textarea')
    : null

const decodeHtml = (value) => {
  const text = String(value || '')
  if (!text) return ''
  if (!htmlDecoder) return text
  htmlDecoder.innerHTML = text
  return htmlDecoder.value
}

const fileName = (packagePath) => {
  const normalized = String(packagePath || '').replace(/\\/g, '/')
  return normalized.split('/').pop() || normalized
}

const normalizeText = (value) =>
  String(value || '')
    .trim()
    .toLowerCase()

const normalizeProblemItem = (item) => {
  const packagePath = String(item?.package_path || '')
  const packageName = fileName(packagePath)
  const displayTitle = decodeHtml(item?.title)
  const displaySource = decodeHtml(item?.source || '未知')
  const displaySummary = decodeHtml(item?.summary || '')
  const displayDescription = decodeHtml(item?.description || '暂无描述')
  const displayInputDescription = decodeHtml(item?.input_description || '')
  const displayOutputDescription = decodeHtml(item?.output_description || '')
  const examples = (item?.examples || []).map((example) => ({
    ...example,
    displayInput: decodeHtml(example?.input || '(空)'),
    displayOutput: decodeHtml(example?.output || '(空)')
  }))
  const starterCode = Object.fromEntries(
    Object.entries(item?.starter_code || {}).map(([language, code]) => [language, decodeHtml(code)])
  )

  return {
    ...item,
    package_path: packagePath,
    packageName,
    displayTitle,
    displaySource,
    displaySummary,
    displayDescription,
    displayInputDescription,
    displayOutputDescription,
    examples,
    starter_code: starterCode,
    searchableText: [
      displayTitle,
      packagePath,
      displaySource,
      packageName,
      ...(item?.topic_tags || []).map((tag) => String(tag || ''))
    ]
      .map((part) => normalizeText(part))
      .join(' ')
  }
}

const matchesFilters = (item, currentFilters) => {
  const keyword = normalizeText(currentFilters.keyword)
  if (
    currentFilters.statementLanguage &&
    (item.statement_language || 'unknown') !== currentFilters.statementLanguage
  ) {
    return false
  }
  if (
    currentFilters.difficulty !== 'all' &&
    (item.difficulty_tag || 'medium') !== currentFilters.difficulty
  ) {
    return false
  }
  if (!keyword) {
    return true
  }

  return String(item.searchableText || '').includes(keyword)
}

const sortProblems = (items) =>
  [...items].sort((a, b) => {
    const packageCompare = String(a.package_path || '').localeCompare(String(b.package_path || ''))
    if (packageCompare !== 0) {
      return packageCompare
    }
    return Number(a.problem_index || 0) - Number(b.problem_index || 0)
  })

const buildProblemGroups = (items) =>
  positionGroupDefs.map((group) => {
    const groupItems = sortProblems(items.filter((item) => item.primary_position_tag === group.key))
    const packageSet = new Set()
    const topicCounter = {}

    groupItems.forEach((item) => {
      packageSet.add(item.package_path)
      ;(item.topic_tags || []).forEach((tag) => {
        topicCounter[tag] = (topicCounter[tag] || 0) + 1
      })
    })

    const languageStats = ['zh', 'en']
      .map((key) => ({
        key,
        label: statementLanguageLabelMap[key],
        count: groupItems.filter((item) => (item.statement_language || 'unknown') === key).length
      }))
      .filter((item) => item.count > 0)

    const difficultyStats = ['easy', 'medium', 'hard']
      .map((key) => ({
        key,
        label: difficultyLabelMap[key],
        count: groupItems.filter((item) => (item.difficulty_tag || 'medium') === key).length
      }))
      .filter((item) => item.count > 0)

    const sortedTopics = Object.entries(topicCounter)
      .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))
      .map(([tag, count]) => ({ tag, count }))

    return {
      ...group,
      items: groupItems,
      packageCount: packageSet.size,
      languageStats,
      difficultyStats,
      topTopicTags: sortedTopics.slice(0, 2),
      hiddenTopicCount: Math.max(sortedTopics.length - 2, 0),
      previewTitles: groupItems.slice(0, 2).map((item) => item.displayTitle)
    }
  })

const uniquePackageCount = (items) =>
  new Set(items.map((item) => item.package_path).filter(Boolean)).size

const allProblemGroups = computed(() => buildProblemGroups(problems.value))
const filteredProblems = computed(() =>
  problems.value.filter((item) => matchesFilters(item, filters))
)
const filteredProblemCount = computed(() => filteredProblems.value.length)
const filteredPackageCount = computed(() => uniquePackageCount(filteredProblems.value))
const problemGroups = computed(() => buildProblemGroups(filteredProblems.value))

const hasActiveFilters = computed(
  () =>
    Boolean(filters.keyword) || Boolean(filters.statementLanguage) || filters.difficulty !== 'all'
)

const hasDetailFilters = computed(
  () =>
    Boolean(detailFilters.keyword) ||
    Boolean(detailFilters.statementLanguage) ||
    detailFilters.difficulty !== 'all'
)

const headerDescription = computed(() => {
  const total = summary.value.imported_problem_count || problems.value.length
  if (!total) {
    return '按前端 / 后端 / 通用分类查看已导入到 OJ 与面试题池的题目。'
  }
  return `当前已导入 ${total} 道题，可按岗位方向快速浏览并查看题目详情。`
})

const trackingSummaryText = computed(
  () =>
    `已追踪 ${summary.value.tracked_problem_count || 0} 道题 / ${summary.value.tracked_package_count || 0} 个题包`
)

const overviewCards = computed(() => [
  {
    key: 'problem-count',
    label: '总题量',
    value: summary.value.imported_problem_count || problems.value.length,
    hint: hasActiveFilters.value
      ? `当前筛选命中 ${filteredProblemCount.value} 道题`
      : '按岗位方向快速浏览',
    icon: BookOutlined
  },
  {
    key: 'package-count',
    label: '题包数',
    value: summary.value.imported_package_count || uniquePackageCount(problems.value),
    hint: hasActiveFilters.value
      ? `当前筛选覆盖 ${filteredPackageCount.value} 个题包`
      : trackingSummaryText.value,
    icon: InboxOutlined
  },
  {
    key: 'category-count',
    label: '分类数',
    value: allProblemGroups.value.filter((group) => group.items.length > 0).length,
    hint: hasActiveFilters.value ? '首页卡片会同步响应筛选' : '前端、后端、通用三类题库',
    icon: AppstoreOutlined
  }
])

const detailFilteredProblems = computed(() =>
  detailProblems.value.filter((item) => matchesFilters(item, detailFilters))
)
const displayedDetailProblems = computed(() =>
  detailFilteredProblems.value.slice(0, detailListRenderCount.value)
)

const detailExtraTags = computed(() => {
  if (!activeProblem.value) {
    return []
  }

  return [
    ...(activeProblem.value.topic_tags || []).map((tag) => ({
      id: `topic-${tag}`,
      label: tag
    })),
    ...(activeProblem.value.allowed_languages || []).map((language) => ({
      id: `lang-${language}`,
      label: languageLabelMap[language] || language
    }))
  ]
})

const visibleDetailExtraTags = computed(() =>
  showAllDetailTags.value
    ? detailExtraTags.value
    : detailExtraTags.value.slice(0, DETAIL_EXTRA_TAG_PREVIEW_COUNT)
)

const hiddenDetailExtraTagCount = computed(() =>
  Math.max(detailExtraTags.value.length - visibleDetailExtraTags.value.length, 0)
)

const starterCodeEntries = computed(() => {
  const starterCode = activeProblem.value?.starter_code || {}
  return Object.entries(starterCode).map(([language, code]) => ({ language, code }))
})

const problemKey = (item) => `${item.package_path}::${item.problem_index}`

const resetFilters = () => {
  filters.keyword = ''
  filters.statementLanguage = ''
  filters.difficulty = 'all'
}

const resetDetailFilters = () => {
  detailFilters.keyword = ''
  detailFilters.statementLanguage = ''
  detailFilters.difficulty = 'all'
}

const resetDetailListRenderCount = () => {
  detailListRenderCount.value = DETAIL_LIST_PAGE_SIZE
}

const loadMoreDetailProblems = () => {
  if (detailListRenderCount.value >= detailFilteredProblems.value.length) {
    return
  }
  detailListRenderCount.value = Math.min(
    detailListRenderCount.value + DETAIL_LIST_PAGE_SIZE,
    detailFilteredProblems.value.length
  )
}

const handleProblemListScroll = (event) => {
  const element = event?.target
  if (!element) {
    return
  }

  const remaining = element.scrollHeight - element.scrollTop - element.clientHeight
  if (remaining < 140) {
    loadMoreDetailProblems()
  }
}

const toggleStatementLanguage = (value, scope = 'page') => {
  const targetFilters = scope === 'detail' ? detailFilters : filters
  targetFilters.statementLanguage = targetFilters.statementLanguage === value ? '' : value
}

const resetExpandedSections = () => {
  expandedSections.description = false
  expandedSections.input = false
  expandedSections.output = false
}

const canToggleText = (value) => {
  const text = String(value || '')
  return text.length > 220 || text.split('\n').length > 6
}

const toggleExpanded = (key) => {
  expandedSections[key] = !expandedSections[key]
}

const loadProblemsets = async () => {
  loading.value = true
  try {
    const data = await problemsetApi.getImportedProblemsets()
    problems.value = (data?.problems || []).map((item) => normalizeProblemItem(item))
    summary.value = {
      ...summary.value,
      ...(data?.summary || {})
    }
  } catch (error) {
    message.error(error.message || '加载题库失败')
  } finally {
    loading.value = false
  }
}

const loadProblemDetail = async (item) => {
  if (!packageDetailCache.has(item.package_path)) {
    const data = await problemsetApi.getProblemsetDetail(item.package_path)
    packageDetailCache.set(
      item.package_path,
      (data?.problems || []).map((problem) =>
        normalizeProblemItem({ ...problem, package_path: item.package_path })
      )
    )
  }
  const packageProblems = packageDetailCache.get(item.package_path) || []
  return (
    packageProblems.find(
      (problem) => Number(problem.problem_index) === Number(item.problem_index)
    ) || null
  )
}

const selectProblem = async (problemSummary) => {
  activeProblemKey.value = problemKey(problemSummary)
  detailLoading.value = true
  showAllDetailTags.value = false
  resetExpandedSections()

  try {
    const detail = await loadProblemDetail(problemSummary)
    activeProblem.value = detail ? { ...problemSummary, ...detail } : { ...problemSummary }
  } catch (error) {
    message.error(error.message || '加载题目详情失败')
  } finally {
    detailLoading.value = false
  }
}

const openGroupDetail = async (group) => {
  detailVisible.value = true
  activeGroup.value = group
  detailGroupLoading.value = true
  detailProblems.value = []
  activeProblem.value = null
  activeProblemKey.value = ''
  resetDetailFilters()
  resetDetailListRenderCount()
  resetExpandedSections()

  await nextTick()
  requestAnimationFrame(() => {
    if (!detailVisible.value) {
      return
    }
    detailProblems.value = [...group.items]
    detailGroupLoading.value = false
  })
}

const handleGroupClick = (group) => {
  if (!group.items.length) {
    return
  }
  openGroupDetail(group)
}

const closeDetail = () => {
  detailVisible.value = false
  detailGroupLoading.value = false
  activeGroup.value = null
  detailProblems.value = []
  activeProblem.value = null
  activeProblemKey.value = ''
  showAllDetailTags.value = false
  resetDetailFilters()
  resetDetailListRenderCount()
  resetExpandedSections()
}

watch(
  [
    () => detailVisible.value,
    () => detailProblems.value,
    () => detailFilters.keyword,
    () => detailFilters.statementLanguage,
    () => detailFilters.difficulty
  ],
  () => {
    if (!detailVisible.value) {
      return
    }

    resetDetailListRenderCount()

    if (!detailFilteredProblems.value.length) {
      activeProblem.value = null
      activeProblemKey.value = ''
      return
    }

    const hasActiveItem = detailFilteredProblems.value.some(
      (item) => problemKey(item) === activeProblemKey.value
    )
    if (!hasActiveItem) {
      selectProblem(detailFilteredProblems.value[0])
    }
  }
)

onMounted(() => {
  loadProblemsets()
})
</script>

<style scoped lang="less">
// 视觉风格对齐设计稿 [UI v3]：零圆角、1px 分隔线、扁平徽章、蓝色只用于主操作与强调
.problemset-page {
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

.topbar-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

// ===================== 按钮（深度覆盖 Ant Design） =====================
.topbar-actions,
.group-footer,
.filter-empty-state,
.drawer-state,
.toolbar-main {
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

  :deep(.ant-btn[disabled]) {
    background: var(--gray-100);
    border-color: var(--gray-200);
    color: var(--gray-500);
  }
}

// ===================== 输入控件（扁平化） =====================
.problemset-page,
.problemset-drawer {
  :deep(.ant-input-affix-wrapper),
  :deep(.ant-input),
  :deep(.ant-select-selector) {
    border-radius: 0 !important;
    border-color: var(--gray-200);
    box-shadow: none !important;
  }

  :deep(.ant-input-affix-wrapper),
  :deep(.ant-select-single .ant-select-selector) {
    height: 34px;
  }

  :deep(.ant-input-affix-wrapper:hover),
  :deep(.ant-input:hover),
  :deep(.ant-select:hover .ant-select-selector) {
    border-color: var(--gray-500) !important;
  }

  :deep(.ant-input-affix-wrapper-focused),
  :deep(.ant-select-focused .ant-select-selector) {
    border-color: var(--main-color) !important;
  }
}

// ===================== 概览指标 =====================
.summary-grid,
.toolbar-panel,
.group-grid {
  padding-left: 32px;
  padding-right: 32px;
}

.summary-grid {
  padding-top: 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-bottom: 1px solid var(--gray-200);
  flex-shrink: 0;
}

.page-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.summary-card {
  padding: 4px 24px 18px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border-right: 1px solid var(--gray-100);

  &:first-child {
    padding-left: 0;
  }

  &:last-child {
    padding-right: 0;
    border-right: none;
  }
}

.summary-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
  font-size: 16px;
  color: var(--gray-500);
  flex-shrink: 0;
}

.summary-content {
  min-width: 0;
}

.summary-label,
.section-label,
.metric-label,
.drawer-field-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}

.summary-value {
  margin-top: 6px;
  font-size: 36px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--gray-1000);
}

.summary-hint {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-600);
}

// ===================== 筛选工具条 =====================
.toolbar-panel {
  padding-top: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--gray-200);
  flex-shrink: 0;
}

.toolbar-main {
  display: grid;
  grid-template-columns: minmax(260px, 2fr) minmax(260px, 1.4fr) minmax(160px, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.toolbar-inline-filters,
.filter-chip-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-chip-label {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
  white-space: nowrap;
}

.filter-chip-button {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--gray-200);
  border-radius: 0;
  background: var(--gray-0);
  color: var(--gray-700);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.filter-chip-button:hover {
  border-color: var(--gray-500);
  color: var(--gray-1000);
}

.filter-chip-button.active {
  background: var(--gray-100);
  color: var(--gray-1000);
  font-weight: 700;
}

.filter-chip-group.compact .filter-chip-button {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
}

.toolbar-meta {
  margin-top: 12px;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-600);
}

// ===================== 状态占位 =====================
.state-panel,
.empty-state,
.filter-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 96px 32px;
  text-align: center;
}

.empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--gray-1000);
}

.empty-description {
  max-width: 460px;
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--gray-500);
}

// ===================== 分类卡片 =====================
.group-grid {
  flex: 1;
  min-height: 0;
  padding-top: 20px;
  padding-bottom: 20px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  overflow: hidden;
}

.group-card {
  min-height: 0;
  height: 100%;
  padding: 0 24px;
  border-right: 1px solid var(--gray-100);
  background: var(--gray-0);
  display: flex;
  flex-direction: column;
  gap: 14px;
  cursor: pointer;
  overflow: hidden;

  &:first-child {
    padding-left: 0;
  }

  &:last-child {
    padding-right: 0;
    border-right: none;
  }
}

.group-card:hover .group-title {
  color: var(--main-800);
}

.group-card.empty {
  cursor: default;
  opacity: 0.7;
}

.group-card.empty:hover .group-title {
  color: var(--gray-1000);
}

.group-card-top,
.group-title-row,
.group-footer,
.problem-meta-row,
.detail-section-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.group-card-top {
  align-items: center;
}

.group-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--gray-500);
}

.group-card:hover .group-icon {
  color: var(--main-color);
}

.group-title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  color: var(--gray-1000);
}

.group-description {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--gray-600);
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.group-package-count,
.group-footer-text,
.drawer-group-caption,
.problem-package {
  font-size: 12px;
  color: var(--gray-500);
  white-space: nowrap;
}

.group-metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--gray-100);
  border-bottom: 1px solid var(--gray-100);
}

.group-metric-card {
  padding: 12px 16px 12px 0;

  & + .group-metric-card {
    padding-left: 16px;
    border-left: 1px solid var(--gray-100);
  }
}

.metric-label {
  display: block;
}

.group-metric-card strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  font-weight: 800;
  color: var(--gray-1000);
}

.group-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

// ===================== 徽章 =====================
.badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid var(--gray-200);
  color: var(--gray-600);
  white-space: nowrap;

  &--solid {
    background: var(--gray-100);
    color: var(--gray-1000);
  }

  &--accent {
    background: var(--main-color);
    border-color: var(--main-color);
    color: #fff;
  }

  &--muted {
    border-color: var(--gray-400);
    color: var(--gray-500);
  }
}

.group-preview {
  min-height: 0;
}

.preview-list {
  display: flex;
  flex-direction: column;
}

.preview-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  padding: 8px 0;
  border-top: 1px solid var(--gray-100);

  &:last-child {
    border-bottom: 1px solid var(--gray-100);
  }
}

.preview-dot {
  width: 4px;
  height: 4px;
  margin-top: 8px;
  background: var(--gray-500);
}

.preview-text {
  min-width: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--gray-800);
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.group-footer {
  margin-top: auto;
  align-items: center;
  padding: 12px 0 0;
  border-top: 1px solid var(--gray-200);
}

// ===================== 抽屉 =====================
.problemset-drawer {
  :deep(.ant-drawer-content) {
    border-radius: 0;
  }

  :deep(.ant-drawer-header) {
    border-bottom: 1px solid var(--gray-200);
    padding: 16px 24px;
  }

  :deep(.ant-drawer-title) {
    font-size: 17px;
    font-weight: 800;
    color: var(--gray-1000);
  }
}

.drawer-state {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
}

.drawer-state--inner {
  min-height: 180px;
}

.detail-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  min-height: calc(100vh - 108px);
}

.problem-list-panel {
  border-right: 1px solid var(--gray-200);
  background: var(--gray-25);
  padding: 20px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.problem-list-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.drawer-group-title {
  font-size: 19px;
  font-weight: 800;
  color: var(--gray-1000);
}

.drawer-group-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--gray-500);
}

.drawer-filter-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-filter-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(120px, 0.7fr);
  gap: 14px;
  align-items: end;
}

.drawer-filter-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.drawer-filter-field :deep(.ant-select) {
  width: 100%;
}

.drawer-filter-tip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--gray-500);
}

.drawer-reset-btn,
.section-toggle-btn {
  padding: 0;
  height: auto;
  font-size: 12px;
  color: var(--main-800);
}

.problem-list {
  display: flex;
  flex-direction: column;
  overflow: auto;
  border-top: 1px solid var(--gray-200);
}

.problem-list-item {
  width: 100%;
  text-align: left;
  padding: 12px 14px;
  border: none;
  border-bottom: 1px solid var(--gray-150);
  border-left: 3px solid transparent;
  background: transparent;
  cursor: pointer;
  content-visibility: auto;
  contain-intrinsic-size: 84px;
  font: inherit;
}

.problem-list-item:hover {
  background: var(--gray-100);
}

.problem-list-item.active {
  background: var(--gray-0);
  border-left-color: var(--main-color);
}

.problem-list-item-top {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.problem-index {
  flex-shrink: 0;
  padding: 1px 6px;
  background: var(--gray-100);
  color: var(--gray-700);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.6;
}

.problem-name {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--gray-1000);
}

.problem-meta-row {
  margin-top: 8px;
  align-items: center;
}

.meta-tag-group,
.detail-tag-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

// ===================== 题目详情 =====================
.problem-detail-panel {
  position: relative;
  padding: 28px 32px 32px;
  overflow: auto;
  background: var(--gray-0);
}

.detail-loading-mask {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.detail-content {
  position: relative;
  z-index: 0;
}

.detail-body {
  width: min(100%, 940px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.detail-hero {
  padding-bottom: 20px;
  border-bottom: 1px solid var(--gray-200);
}

.detail-heading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-eyebrow {
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--main-800);
}

.detail-title {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.01em;
  line-height: 1.35;
  color: var(--gray-1000);
}

.detail-summary {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--gray-600);
}

.detail-info-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--gray-100);
}

.detail-info-item {
  padding: 12px 16px 12px 0;
  border-bottom: 1px solid var(--gray-100);

  &:nth-child(2n) {
    padding-left: 16px;
    border-left: 1px solid var(--gray-100);
  }
}

.detail-info-item--wide {
  grid-column: 1 / -1;
  padding-left: 0;
  border-left: none;
}

.detail-info-label {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}

.detail-info-value {
  display: block;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.7;
  color: var(--gray-900);
  word-break: break-word;
}

.detail-tag-row {
  margin-top: 16px;
}

.detail-tag-toggle {
  height: 22px;
  padding: 0 8px;
  border: 1px dashed var(--gray-400);
  background: transparent;
  color: var(--gray-500);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.detail-tag-toggle:hover {
  border-color: var(--main-color);
  color: var(--main-color);
}

.detail-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--gray-200);
}

.detail-section-header {
  align-items: center;
  margin-bottom: 12px;
}

.detail-section-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: var(--gray-1000);
}

.detail-paragraph {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-800);
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-paragraph.collapsed {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 6;
}

.example-grid,
.starter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.example-card,
.starter-card {
  padding: 14px;
  border: 1px solid var(--gray-200);
  background: var(--gray-25);
}

.example-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.example-card strong,
.starter-header {
  display: block;
  margin-bottom: 8px;
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
  color: var(--gray-500);
}

.example-card pre,
.starter-card pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  line-height: 1.7;
  color: var(--gray-900);
}

.detail-empty {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 1280px) {
  .group-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .group-card:nth-child(2n) {
    padding-right: 0;
    border-right: none;
  }

  .group-card:nth-child(2n + 1) {
    padding-left: 0;
  }

  .toolbar-main {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}

@media (max-width: 960px) {
  .summary-grid,
  .group-grid,
  .detail-info-grid {
    grid-template-columns: 1fr;
  }

  .summary-card,
  .group-card {
    padding-left: 0;
    padding-right: 0;
    border-right: none;
  }

  .summary-card + .summary-card {
    border-top: 1px solid var(--gray-100);
    padding-top: 16px;
  }

  .detail-info-item:nth-child(2n) {
    padding-left: 0;
    border-left: none;
  }

  .page-main {
    overflow: auto;
  }

  .detail-layout {
    grid-template-columns: 1fr;
  }

  .problem-list-panel {
    border-right: none;
    border-bottom: 1px solid var(--gray-200);
  }
}

@media (max-width: 768px) {
  .page-topbar,
  .summary-grid,
  .toolbar-panel,
  .group-grid {
    padding-left: 16px;
    padding-right: 16px;
  }

  .group-grid {
    overflow: visible;
  }

  .toolbar-main,
  .drawer-filter-grid,
  .group-metric-grid {
    grid-template-columns: 1fr;
  }

  .group-metric-card + .group-metric-card {
    padding-left: 0;
    border-left: none;
    border-top: 1px solid var(--gray-100);
  }

  .filter-chip-group {
    align-items: flex-start;
  }

  .problem-detail-panel {
    padding: 20px 16px;
  }
}
</style>
