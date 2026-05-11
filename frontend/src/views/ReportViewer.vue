<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const key = computed(() => route.params.key as string)
const runId = computed(() => route.params.runId as string | undefined)

const reportPath = computed(() => {
  if (runId.value) return `/api/projects/${key.value}/reports/${runId.value}/`
  return `/api/projects/${key.value}/reports/latest/`
})
</script>

<template>
  <div style="display: flex; flex-direction: column; height: calc(100vh - 120px)">
    <n-space align="center" style="margin-bottom: 12px">
      <n-button text @click="router.push(`/projects/${key}`)">← 返回</n-button>
      <n-h3 style="margin: 0">Allure Report</n-h3>
    </n-space>
    <iframe :src="reportPath" style="flex: 1; border: 1px solid #e5e5e5; border-radius: 4px; width: 100%" />
  </div>
</template>
