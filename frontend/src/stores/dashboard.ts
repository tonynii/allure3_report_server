import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getDashboard, type DashboardData } from '../api/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  const data = ref<DashboardData | null>(null)
  const loading = ref(false)

  async function fetch() {
    loading.value = true
    try {
      const { data: d } = await getDashboard()
      data.value = d
    } finally {
      loading.value = false
    }
  }

  return { data, loading, fetch }
})
