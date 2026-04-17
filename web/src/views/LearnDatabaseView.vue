<template>
  <div class="learn-database">
    <div class="page-header">
      <a-button type="text" class="back-btn" @click="router.push('/learn')">返回知识专题</a-button>
    </div>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
      <p>正在加载专题内容...</p>
    </div>

    <a-result
      v-else-if="errorMessage"
      status="warning"
      title="专题加载失败"
      :sub-title="errorMessage"
    />

    <template v-else-if="database">
      <section class="hero-card">
        <div class="hero-card__content">
          <span class="hero-badge">{{ database.position || '知识专题' }}</span>
          <h1>{{ database.name }}</h1>
          <p>{{ database.description || '浏览该专题下的知识文档，进入后可按分块或全文阅读。' }}</p>
        </div>
        <div class="hero-card__stats">
          <div class="stat-item">
            <strong>{{ database.file_count || 0 }}</strong>
            <span>篇文档</span>
          </div>
          <div class="stat-item hint">
            <strong>浏览学习</strong>
            <span>选择任意文档进入学习页</span>
          </div>
        </div>
      </section>

      <section class="toolbar-card">
        <a-input
          v-model:value="keyword"
          allow-clear
          size="large"
          placeholder="搜索文档名称"
        />
        <span class="toolbar-count">共 {{ filteredDocuments.length }} 篇</span>
      </section>

      <div v-if="filteredDocuments.length" class="document-list">
        <article
          v-for="document in filteredDocuments"
          :key="document.file_id"
          class="document-card"
          @click="goToDocument(document.file_id)"
        >
          <div class="document-card__top">
            <div class="document-card__title-wrap">
              <h3>{{ formatDisplayName(document.filename) }}</h3>
              <p>{{ document.summary || '点击进入学习。' }}</p>
            </div>
            <a-button type="link">进入学习</a-button>
          </div>
          <div class="document-card__footer">
            <span v-if="document.folder_path">{{ document.folder_path }}</span>
            <span v-else>根目录文档</span>
            <span v-if="document.updated_at">{{ formatDateTime(document.updated_at) }}</span>
          </div>
        </article>
      </div>

      <a-empty v-else description="没有匹配的文档" />
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { learnApi } from '@/apis/learn_api'
import { formatDateTime } from '@/utils/time'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const errorMessage = ref('')
const keyword = ref('')
const database = ref(null)

const formatDisplayName = (value) => String(value || '').replace(/\.md$/i, '')

const filteredDocuments = computed(() => {
  const search = keyword.value.trim().toLowerCase()
  const list = Array.isArray(database.value?.documents) ? database.value.documents : []
  if (!search) {
    return list
  }

  return list.filter((item) => {
    const values = [item.filename, item.path, item.summary]
    return values.some((value) => String(value || '').toLowerCase().includes(search))
  })
})

const loadDatabase = async () => {
  const dbId = String(route.params.db_id || '').trim()
  if (!dbId) {
    database.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    database.value = await learnApi.getDatabaseDetail(dbId)
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

const goToDocument = (fileId) => {
  router.push(`/learn/${route.params.db_id}/doc/${fileId}`)
}

watch(
  () => route.params.db_id,
  () => {
    keyword.value = ''
    loadDatabase()
  },
  { immediate: true }
)
</script>

<style scoped lang="less">
.learn-database {
  min-height: 100%;
  padding: 24px 28px 32px;
  background:
    linear-gradient(180deg, var(--main-10) 0%, var(--gray-10) 180px, var(--gray-25) 100%);
}

.page-header {
  margin-bottom: 16px;
}

.back-btn {
  padding-left: 0;
  color: var(--gray-700);
}

.hero-card,
.toolbar-card,
.document-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 24px;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
  margin-bottom: 20px;
  box-shadow: 0 10px 30px var(--shadow-0);
}

.hero-card__content {
  max-width: 820px;

  h1 {
    margin: 12px 0 10px;
    font-size: 30px;
    color: var(--gray-2000);
  }

  p {
    margin: 0;
    color: var(--gray-600);
    font-size: 15px;
    line-height: 1.8;
  }
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 12px;
  background: var(--main-50);
  color: var(--main-700);
  font-size: 13px;
  font-weight: 600;
}

.hero-card__stats {
  display: flex;
  gap: 14px;
}

.stat-item {
  min-width: 120px;
  padding: 18px 20px;
  border-radius: 20px;
  background: var(--gray-10);
  display: flex;
  flex-direction: column;
  gap: 8px;

  strong {
    font-size: 24px;
    color: var(--gray-2000);
  }

  span {
    color: var(--gray-600);
    font-size: 13px;
  }

  &.hint {
    min-width: 200px;
  }
}

.toolbar-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  margin-bottom: 18px;
}

.toolbar-count {
  color: var(--gray-600);
  font-size: 14px;
  white-space: nowrap;
}

.document-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.document-card {
  padding: 20px 22px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    box-shadow: 0 14px 32px var(--shadow-1);
  }
}

.document-card__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.document-card__title-wrap {
  min-width: 0;

  h3 {
    margin: 0 0 10px;
    font-size: 18px;
    color: var(--gray-2000);
  }

  p {
    margin: 0;
    color: var(--gray-600);
    line-height: 1.7;
  }
}

.document-card__footer {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 14px;
  color: var(--gray-500);
  font-size: 13px;
}

.state-panel {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--gray-600);
}

@media (max-width: 900px) {
  .learn-database {
    padding: 18px;
  }

  .hero-card,
  .toolbar-card,
  .document-card__top,
  .document-card__footer {
    flex-direction: column;
  }

  .hero-card__stats {
    width: 100%;
    flex-direction: column;
  }
}
</style>
