import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { listRuns, getRun, type Run, type RunDetail } from '../api/reports'

export const useRunStore = defineStore('run', () => {
  const runs = ref<Run[]>([])
  const current = ref<RunDetail | null>(null)
  const loading = ref(false)
  const statusFilter = ref('')
  const keyword = ref('')

  const filteredTests = computed(() => {
    if (!current.value) return []
    let list = current.value.test_results
    if (statusFilter.value) list = list.filter((t: any) => t.status === statusFilter.value)
    if (keyword.value) {
      const kw = keyword.value.toLowerCase()
      list = list.filter((t: any) => t.name.toLowerCase().includes(kw) || (t.full_name && t.full_name.toLowerCase().includes(kw)))
    }
    return list
  })

  async function fetchRuns(key: string) {
    const { data } = await listRuns(key)
    runs.value = data
  }

  async function fetch(key: string, id: string) {
    loading.value = true
    try {
      const { data } = await getRun(key, id)
      current.value = data
    } finally {
      loading.value = false
    }
  }

  return { runs, current, loading, statusFilter, keyword, filteredTests, fetchRuns, fetch }
})
