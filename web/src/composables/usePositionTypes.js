import { computed, ref } from 'vue'

import { jobApi } from '@/apis/job_api'
import {
  getDefaultPositionType,
  getFallbackPositionTypes,
  getSelectablePositionTypes,
  sortPositionTypes
} from '@/utils/position_utils'

const positionTypes = ref(getFallbackPositionTypes())
const loading = ref(false)
let loadPromise = null

const loadPositionTypes = async ({ force = false } = {}) => {
  if (loadPromise && !force) {
    return loadPromise
  }

  loading.value = true
  loadPromise = jobApi
    .getPositionTypes()
    .then((data) => {
      const items = Array.isArray(data?.position_types) ? data.position_types : []
      if (items.length) {
        positionTypes.value = sortPositionTypes(items)
      }
      return positionTypes.value
    })
    .catch((error) => {
      console.error('Failed to load position types:', error)
      return positionTypes.value
    })
    .finally(() => {
      loading.value = false
      loadPromise = null
    })

  return loadPromise
}

export const usePositionTypes = () => {
  const selectablePositionTypes = computed(() => getSelectablePositionTypes(positionTypes.value))
  const defaultPositionType = computed(() => getDefaultPositionType(positionTypes.value))

  return {
    positionTypes,
    selectablePositionTypes,
    defaultPositionType,
    positionTypeOptions: computed(() =>
      selectablePositionTypes.value.map((item) => ({
        label: item.label,
        value: item.label,
        shortLabel: item.short_label,
        key: item.key
      }))
    ),
    loadingPositionTypes: loading,
    loadPositionTypes
  }
}
