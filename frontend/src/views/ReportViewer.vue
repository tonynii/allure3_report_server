<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listRuns } from '../api/reports'

const route = useRoute()
const router = useRouter()
const key = computed(() => route.params.key as string)
const runId = computed(() => route.params.runId as string | undefined)
const reportPath = ref('')
const error = ref<string | null>(null)

onMounted(async () => {
  if (runId.value) {
    reportPath.value = `/reports/${key.value}/${runId.value}/`
    return
  }
  try {
    const { data } = await listRuns(key.value)
    const latest = data.find(r => r.status === 'completed')
    if (latest) {
      reportPath.value = `/reports/${key.value}/${latest.id}/`
    } else {
      error.value = '暂无已完成报告'
    }
  } catch {
    error.value = '加载失败'
  }
})
</script>

<template>
  <div style="display: flex; flex-direction: column; height: calc(100vh - 120px)">
    <n-space align="center" style="margin-bottom: 12px">
      <n-button text @click="router.push(`/projects/${key}`)">← 返回</n-button>
      <n-h3 style="margin: 0">Allure Report</n-h3>
    </n-space>
    <n-result v-if="error" status="info" :title="error" style="flex: 1" />
    <iframe v-else-if="reportPath" :src="reportPath" style="flex: 1; border: 1px solid #e5e5e5; border-radius: 4px; width: 100%" />
  </div>
</template>
