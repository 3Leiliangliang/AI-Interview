const FALLBACK_POSITION_TYPES = [
  {
    key: 'frontend',
    label: '前端工程师',
    short_label: '前端',
    order: 10,
    selectable: true,
    aliases: ['前端', 'frontend', 'react', 'vue'],
    keywords: ['前端', 'frontend', 'react', 'vue', 'javascript', 'typescript', 'html', 'css'],
    problemset_tag: 'frontend'
  },
  {
    key: 'backend',
    label: '后端工程师',
    short_label: '后端',
    order: 20,
    selectable: true,
    aliases: ['后端', 'backend', 'java', 'python', 'go', '数据库', 'database', 'sql', 'mysql', 'postgresql'],
    keywords: [
      '后端',
      'backend',
      'java',
      'spring',
      'python',
      'go',
      'golang',
      'redis',
      '数据库',
      'database',
      'sql',
      'mysql',
      'postgresql',
      'postgres',
      '索引',
      '事务'
    ],
    problemset_tag: 'backend'
  },
  {
    key: 'algorithm',
    label: '算法工程师',
    short_label: '算法',
    order: 30,
    selectable: true,
    aliases: ['算法', '算法工程师', '数据结构', 'dsa', 'algorithm'],
    keywords: ['算法', '数据结构', 'dsa', 'leetcode', '动态规划', '链表', '二叉树', '图', '数组'],
    problemset_tag: 'algorithm_general'
  },
  {
    key: 'system_design',
    label: '系统架构师',
    short_label: '架构',
    order: 40,
    selectable: true,
    aliases: ['系统设计', 'system design', '架构设计'],
    keywords: ['系统设计', 'system design', '架构', '分布式', '高并发', '缓存', '消息队列'],
    problemset_tag: 'backend'
  },
  {
    key: 'ai_app',
    label: 'AI 应用开发',
    short_label: 'AI应用',
    order: 60,
    selectable: true,
    aliases: ['ai 应用开发', 'ai应用开发', 'llm', 'rag', 'agent', 'mcp'],
    keywords: ['ai', 'llm', 'rag', 'agent', 'mcp', 'prompt', 'embedding', '向量数据库'],
    problemset_tag: 'backend'
  },
  {
    key: 'unclassified',
    label: '未分类',
    short_label: '未分类',
    order: 999,
    selectable: false,
    aliases: ['未分类'],
    keywords: [],
    problemset_tag: 'algorithm_general'
  }
]

export const DEFAULT_POSITION_KEY = 'backend'
export const UNCLASSIFIED_POSITION_KEY = 'unclassified'

export const sortPositionTypes = (items = []) =>
  [...items].sort((a, b) => Number(a.order || 0) - Number(b.order || 0))

export const getFallbackPositionTypes = () => sortPositionTypes(FALLBACK_POSITION_TYPES)

export const buildPositionTypeMap = (positionTypes = []) =>
  new Map(positionTypes.map((item) => [item.key, item]))

export const getDefaultPositionType = (positionTypes = getFallbackPositionTypes()) =>
  positionTypes.find((item) => item.key === DEFAULT_POSITION_KEY) || positionTypes[0] || FALLBACK_POSITION_TYPES[0]

export const getUnclassifiedPositionType = (positionTypes = getFallbackPositionTypes()) =>
  positionTypes.find((item) => item.key === UNCLASSIFIED_POSITION_KEY) || FALLBACK_POSITION_TYPES.at(-1)

export const getSelectablePositionTypes = (positionTypes = getFallbackPositionTypes()) =>
  sortPositionTypes(positionTypes).filter((item) => item.selectable !== false)

export const normalizePositionType = (
  value,
  positionTypes = getFallbackPositionTypes(),
  { fallbackToDefault = true } = {}
) => {
  const normalizedValue = String(value || '').trim().toLowerCase()
  const defaultType = getDefaultPositionType(positionTypes)
  const unclassifiedType = getUnclassifiedPositionType(positionTypes)

  if (!normalizedValue) {
    return fallbackToDefault ? defaultType : unclassifiedType
  }

  const exactMatch = positionTypes.find((item) => {
    const candidates = [item.key, item.label, item.short_label, ...(item.aliases || [])]
    return candidates.some((candidate) => String(candidate || '').trim().toLowerCase() === normalizedValue)
  })
  if (exactMatch) {
    return exactMatch
  }

  const keywordMatch = positionTypes.find((item) =>
    (item.keywords || []).some((keyword) => {
      const normalizedKeyword = String(keyword || '').trim().toLowerCase()
      return normalizedKeyword && normalizedValue.includes(normalizedKeyword)
    })
  )
  if (keywordMatch) {
    return keywordMatch
  }

  return fallbackToDefault ? defaultType : unclassifiedType
}

export const inferPositionType = (
  primaryValue,
  secondaryValue = '',
  positionTypes = getFallbackPositionTypes(),
  { fallbackToDefault = false } = {}
) => {
  const joined = [primaryValue, secondaryValue].filter(Boolean).join(' ')
  return normalizePositionType(joined, positionTypes, { fallbackToDefault })
}
