import { Database, DatabaseZap } from 'lucide-vue-next'

export const getKbTypeLabel = (type) => {
  const labels = {
    milvus: 'CommonRAG'
  }
  return labels[type] || type
}

export const getKbTypeIcon = (type) => {
  const icons = {
    milvus: DatabaseZap
  }
  return icons[type] || Database
}

export const getKbTypeColor = (type) => {
  const colors = {
    milvus: 'red'
  }
  return colors[type] || 'blue'
}
