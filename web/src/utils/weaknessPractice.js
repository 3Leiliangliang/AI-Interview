// 面试报告弱项 → 练习页专题筛选的共享纯函数。
// 被 InterviewResultView（报告 CTA）与 PracticeHomeView（按弱项推荐 Tab）共用，
// 保证两处阈值、去重与匹配规则不漂移。全部为纯数据转换，无 Vue 生命周期、无网络请求。

// ---------------------------------------------------------------------------
// 报告弱项提取（面试 → 候选）
// ---------------------------------------------------------------------------

export const REPORT_SCORE_THRESHOLD = 70 // 低分技术题
export const WEAK_DIMENSION_THRESHOLD = 75 // 薄弱维度
export const MAX_REPORT_WEAKNESSES = 4

const pickFirst = (values) => {
  for (const value of values) {
    const text = String(value || '').trim()
    if (text) return text
  }
  return ''
}

// 统一候选结构：{ type, label, query, question_index, score, reason, locator, file_name, kb_name }
export const extractReportWeaknesses = ({ technicalReviews = [], dimensions = [] }) => {
  const candidates = []
  const seen = new Set()

  const push = (candidate) => {
    const query = String(candidate.query || '').trim().toLowerCase()
    if (!query || seen.has(query)) return
    seen.add(query)
    candidates.push(candidate)
  }

  // 1) 低分技术题——最具体的可行动信号。query 缺失则跳过该候选，不用完整题干制造无效专题。
  const sortedReviews = [...technicalReviews]
    .filter((review) => review.score !== null && Number(review.score) < REPORT_SCORE_THRESHOLD)
    .sort((a, b) => Number(a.score ?? 100) - Number(b.score ?? 100))
    .slice(0, 3)

  for (const review of sortedReviews) {
    const query = pickFirst([
      review.suggested_keywords?.[0],
      review.matched_keywords?.[0],
      review.kb_name,
    ])
    if (!query) continue
    push({
      type: 'review',
      label: query,
      query,
      question_index: Number(review.question_index ?? 0),
      score: Number(review.score),
      reason: review.gaps?.[0] || `第 ${review.question_index} 题得分 ${review.score} 分`,
      locator: review.locator || null,
      file_name: review.file_name || '',
      kb_name: review.kb_name || '',
    })
    if (candidates.length >= MAX_REPORT_WEAKNESSES) break
  }

  // 2) 薄弱维度——高层方向，用归一化后的维度显示名作 query。
  for (const dim of dimensions) {
    if (candidates.length >= MAX_REPORT_WEAKNESSES) break
    const score = Number(dim.score)
    if (!Number.isFinite(score) || score >= WEAK_DIMENSION_THRESHOLD) continue
    const label = String(dim.label || '').trim()
    if (!label) continue
    push({
      type: 'dimension',
      label,
      query: label,
      score,
      reason: `本轮 ${score} 分，是相对薄弱的维度`,
      locator: null,
      file_name: '',
      kb_name: '',
    })
  }

  return candidates.slice(0, MAX_REPORT_WEAKNESSES)
}

// ---------------------------------------------------------------------------
// URL 弱项 token 解析（string / 数组兼容）
// ---------------------------------------------------------------------------

export const MAX_URL_TOKENS = 4
export const MAX_TOKEN_LENGTH = 40

// Vue Router 会把重复 query key 编码成数组；兼容 string 与数组输入。
export const parseWeaknessTokens = (raw) => {
  const values = Array.isArray(raw) ? raw : [raw]
  const seen = new Set()
  const tokens = []
  for (const value of values) {
    const token = String(value || '').trim().toLowerCase()
    if (!token || token.length > MAX_TOKEN_LENGTH || seen.has(token)) continue
    seen.add(token)
    tokens.push(token)
    if (tokens.length >= MAX_URL_TOKENS) break
  }
  return tokens
}

// ---------------------------------------------------------------------------
// 个性化路线候选（直接访问练习页时的 fallback）
// ---------------------------------------------------------------------------

// problem_ref 精确匹配优先；维度标题只做保守文本匹配候选，不做硬映射。
export const extractPersonalizedWeaknesses = (payload) => {
  const candidates = []
  const seen = new Set()
  const push = (query, source) => {
    const q = String(query || '').trim()
    if (!q || seen.has(q)) return
    seen.add(q)
    candidates.push({ query: q, label: q, type: source, source })
  }
  for (const resource of payload?.recommended_resources || []) {
    if (String(resource.problem_ref || '').trim()) push(resource.problem_ref, 'resource')
  }
  for (const weakness of payload?.weaknesses || []) {
    push(weakness.title || weakness.reason, 'weakness')
  }
  for (const task of payload?.practice_tasks || []) {
    push(task.title, 'practice')
  }
  return candidates
}

// ---------------------------------------------------------------------------
// 题库匹配
// ---------------------------------------------------------------------------

// 解析顺序：problem_ref 精确 → topic_key 精确 → topic_name 精确 → topic_tags 精确
// → 保守 substring（topic_name / tag / 题目标题）。未匹配保持 unresolved，不扩大到全部题。
export const matchWeaknessCandidates = (candidates, topics) => {
  const topicByKey = new Map()
  const problemRefToTopic = new Map()
  for (const topic of topics || []) {
    topicByKey.set(String(topic.topic_key).toLowerCase(), topic)
    for (const problem of topic.problems || []) {
      problemRefToTopic.set(String(problem.problem_ref).toLowerCase(), {
        topic,
        problemRef: String(problem.problem_ref),
      })
    }
  }

  const matchedTopicKeys = []
  const matchedProblemRefs = []
  const matched = []
  const unresolved = []

  const pushMatched = (candidate, topicKey, resolvedBy) => {
    matched.push({ ...candidate, topic_key: topicKey, resolvedBy })
    if (!matchedTopicKeys.includes(topicKey)) matchedTopicKeys.push(topicKey)
  }

  for (const candidate of candidates || []) {
    const query = String(candidate.query || '').trim().toLowerCase()
    if (!query) {
      unresolved.push(candidate)
      continue
    }

    // 1) problem_ref 精确匹配（URL / 个性化资源等来源统一支持）
    if (problemRefToTopic.has(query)) {
      const { topic, problemRef } = problemRefToTopic.get(query)
      matchedProblemRefs.push(problemRef)
      pushMatched(candidate, topic.topic_key, 'problem_ref')
      continue
    }

    // 2) topic_key 精确
    if (topicByKey.has(query)) {
      pushMatched(candidate, query, 'topic_key')
      continue
    }

    // 3) topic_name 精确
    let found = null
    for (const topic of topics || []) {
      if (String(topic.topic_name || '').trim().toLowerCase() === query) {
        found = topic
        break
      }
    }
    if (found) {
      pushMatched(candidate, found.topic_key, 'topic_name')
      continue
    }

    // 4) topic_tags 精确 / 保守 substring
    found = null
    for (const topic of topics || []) {
      const name = String(topic.topic_name || '').trim().toLowerCase()
      const tags = (topic.topic_tags || []).map((tag) => String(tag || '').trim().toLowerCase())
      if (name && name.includes(query)) {
        found = topic
        break
      }
      if (tags.some((tag) => tag.includes(query))) {
        found = topic
        break
      }
      const titleHit = (topic.problems || []).some((problem) =>
        String(problem.title || '').trim().toLowerCase().includes(query),
      )
      if (titleHit) {
        found = topic
        break
      }
    }
    if (found) {
      pushMatched(candidate, found.topic_key, 'substring')
      continue
    }

    unresolved.push(candidate)
  }

  return { matchedTopicKeys, matchedProblemRefs, matched, unresolved }
}
