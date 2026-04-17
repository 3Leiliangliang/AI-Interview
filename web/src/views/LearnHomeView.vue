<template>
  <div class="learn-home">
    <section class="hero-card">
      <div class="hero-copy">
        <span class="hero-badge">知识学习</span>
        <h1>按专题学习管理员维护的知识库内容</h1>
        <p>面向面试者的轻学习入口，支持按岗位筛选、专题浏览和文档学习。</p>
      </div>
      <div class="hero-search">
        <a-input
          v-model:value="keyword"
          size="large"
          allow-clear
          placeholder="搜索知识库名称或简介"
        />
      </div>
    </section>

    <section class="filter-card">
      <div class="filter-label">岗位分类</div>
      <div class="filter-pills">
        <button
          type="button"
          :class="['pill', { active: selectedPosition === 'all' }]"
          @click="selectedPosition = 'all'"
        >
          全部
        </button>
        <button
          v-for="item in positionOptions"
          :key="item.value"
          type="button"
          :class="['pill', { active: selectedPosition === item.value }]"
          @click="selectedPosition = item.value"
        >
          {{ item.shortLabel || item.label }}
        </button>
      </div>
    </section>

    <div v-if="loading" class="state-panel">
      <a-spin size="large" />
      <p>正在加载可学习知识库...</p>
    </div>

    <a-result
      v-else-if="errorMessage"
      status="warning"
      title="知识库加载失败"
      :sub-title="errorMessage"
    />

    <template v-else>
      <div class="result-meta">
        <span>共 {{ filteredDatabases.length }} 个知识专题</span>
      </div>

      <div v-if="filteredDatabases.length" class="database-grid">
        <article
          v-for="database in filteredDatabases"
          :key="database.db_id"
          class="database-card"
          @click="goToDatabase(database.db_id)"
        >
          <div class="database-card__top">
            <div class="database-card__icon">知</div>
            <div class="database-card__meta">
              <h3>{{ database.name }}</h3>
              <p>{{ database.description || '进入专题后查看详细知识内容。' }}</p>
            </div>
          </div>
          <div class="database-card__footer">
            <a-tag color="blue">{{ database.position || '未分类' }}</a-tag>
            <span>{{ database.file_count || 0 }} 篇文档</span>
          </div>
        </article>
      </div>

      <a-empty v-else description="没有匹配的知识专题" />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { learnApi } from '@/apis/learn_api'
import { usePositionTypes } from '@/composables/usePositionTypes'
import { normalizePositionType } from '@/utils/position_utils'

const router = useRouter()
const { positionTypeOptions, loadPositionTypes, positionTypes } = usePositionTypes()

const loading = ref(false)
const errorMessage = ref('')
const keyword = ref('')
const selectedPosition = ref('all')
const databases = ref([])

const positionOptions = computed(() => positionTypeOptions.value || [])

const filteredDatabases = computed(() => {
  const search = keyword.value.trim().toLowerCase()

  return databases.value.filter((item) => {
    const normalizedPosition = normalizePositionType(item.position, positionTypes.value, {
      fallbackToDefault: false
    })
    const matchesPosition =
      selectedPosition.value === 'all' ||
      item.position === selectedPosition.value ||
      normalizedPosition.label === selectedPosition.value
    const matchesKeyword =
      !search ||
      String(item.name || '')
        .toLowerCase()
        .includes(search) ||
      String(item.description || '')
        .toLowerCase()
        .includes(search)
    return matchesPosition && matchesKeyword
  })
})

const loadDatabases = async () => {
  loading.value = true
  errorMessage.value = ''

  try {
    const [data] = await Promise.all([learnApi.getDatabases(), loadPositionTypes()])
    databases.value = Array.isArray(data?.databases) ? data.databases : []
  } catch (error) {
    errorMessage.value = error.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

const goToDatabase = (dbId) => {
  router.push(`/learn/${dbId}`)
}

onMounted(() => {
  loadDatabases()
})
</script>

<style scoped lang="less">
.learn-home {
  min-height: 100%;
  padding: 28px;
  background:
    linear-gradient(180deg, var(--main-10) 0%, var(--gray-10) 200px, var(--gray-25) 100%);
}

.hero-card,
.filter-card {
  background: var(--gray-0);
  border: 1px solid var(--gray-150);
  border-radius: 24px;
  box-shadow: 0 10px 30px var(--shadow-0);
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 32px;
  margin-bottom: 20px;
}

.hero-copy {
  max-width: 720px;

  h1 {
    margin: 12px 0 10px;
    font-size: 32px;
    line-height: 1.2;
    color: var(--gray-2000);
  }

  p {
    margin: 0;
    font-size: 15px;
    line-height: 1.8;
    color: var(--gray-600);
  }
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--main-50);
  color: var(--main-700);
  font-size: 13px;
  font-weight: 600;
}

.hero-search {
  width: 320px;
  display: flex;
  align-items: flex-start;
}

.filter-card {
  padding: 18px 20px;
  margin-bottom: 20px;
}

.filter-label {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-800);
}

.filter-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.pill {
  border: 1px solid var(--gray-200);
  border-radius: 999px;
  background: var(--gray-10);
  color: var(--gray-700);
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease;

  &.active {
    border-color: var(--main-300);
    background: var(--main-50);
    color: var(--main-700);
  }
}

.result-meta {
  margin-bottom: 14px;
  color: var(--gray-600);
  font-size: 14px;
}

.database-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 18px;
}

.database-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 220px;
  padding: 22px;
  border-radius: 24px;
  border: 1px solid var(--gray-150);
  background: var(--gray-0);
  box-shadow: 0 12px 32px var(--shadow-0);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    border-color: var(--main-200);
    box-shadow: 0 16px 36px var(--shadow-1);
  }
}

.database-card__top {
  display: flex;
  gap: 16px;
}

.database-card__icon {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--main-100), #ffe8b0);
  color: var(--main-800);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  flex: 0 0 auto;
}

.database-card__meta {
  min-width: 0;

  h3 {
    margin: 0 0 10px;
    font-size: 20px;
    color: var(--gray-2000);
  }

  p {
    margin: 0;
    color: var(--gray-600);
    line-height: 1.7;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

.database-card__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  color: var(--gray-600);
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
  .learn-home {
    padding: 18px;
  }

  .hero-card {
    flex-direction: column;
    padding: 22px;
  }

  .hero-copy h1 {
    font-size: 28px;
  }

  .hero-search {
    width: 100%;
  }
}
</style>
