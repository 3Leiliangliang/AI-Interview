import { Database, DatabaseZap } from 'lucide-vue-next'

export const getKbTypeLabel = (type) => {
  const labels = {
    openviking: 'OpenViking'
  }
  return labels[type] || type
}

export const getKbTypeIcon = (type) => {
  const icons = {
    openviking: DatabaseZap
  }
  return icons[type] || Database
}

export const getKbTypeColor = (type) => {
  const colors = {
    openviking: 'purple'
  }
  return colors[type] || 'blue'
}
