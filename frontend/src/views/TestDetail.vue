<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTestResult, type TestResultDetail } from '../api/reports'
import { formatDuration, formatTime, formatSize } from '../utils/format'

const route = useRoute()
const router = useRouter()
const key = computed(() => route.params.key as string)
const runId = computed(() => route.params.runId as string)
const testId = computed(() => route.params.testId as string)
const loading = ref(true)
const error = ref<string | null>(null)
const test = ref<TestResultDetail | null>(null)

onMounted(async () => {
  try {
    const { data } = await getTestResult(key.value, runId.value, testId.value)
    test.value = data
  } catch (err: any) {
    error.value = err.response?.data?.detail || err.message || '加载失败'
  } finally {
    loading.value = false
  }
})

function downloadAttachment(attId: string) {
  window.open(`/api/projects/${key.value}/attachments/${attId}`, '_blank')
}
</script>

<template>
  <n-spin :show="loading">
    <n-result v-if="error" status="error" title="加载失败" :description="error">
      <template #footer>
        <n-button @click="router.push(`/projects/${key}/runs/${runId}`)">返回</n-button>
      </template>
    </n-result>

    <div v-else-if="test">
    <n-space align="center" style="margin-bottom: 24px">
      <n-button text @click="router.push(`/projects/${key}/runs/${runId}`)">← 返回</n-button>
      <n-h2 style="margin: 0">{{ test.name }}</n-h2>
      <StatusTag :status="test.status" />
    </n-space>

    <n-grid :cols="2" :x-gap="16" style="margin-bottom: 16px">
        <n-gi>
          <n-thing title="基本信息">
            <n-descriptions :columns="1" label-placement="left">
              <n-descriptions-item label="Full Name">{{ test.full_name }}</n-descriptions-item>
              <n-descriptions-item label="Status"><StatusTag :status="test.status" /></n-descriptions-item>
              <n-descriptions-item label="Duration">{{ formatDuration(test.duration_ms) }}</n-descriptions-item>
              <n-descriptions-item label="Start">{{ formatTime(test.start_time) }}</n-descriptions-item>
            </n-descriptions>
          </n-thing>
        </n-gi>
        <n-gi>
          <n-thing title="Labels">
            <n-space v-if="test.labels?.length">
              <n-tag v-for="l in test.labels" :key="l.name + l.value" round size="small">
                {{ l.name }}: {{ l.value }}
              </n-tag>
            </n-space>
            <n-text depth="3" v-else>无</n-text>
          </n-thing>
          <n-thing title="Links" v-if="test.links?.length" style="margin-top: 12px">
            <n-space>
              <n-a v-for="l in test.links" :key="l.url" :href="l.url" target="_blank">
                {{ l.name || l.type }}
              </n-a>
            </n-space>
          </n-thing>
        </n-gi>
      </n-grid>

      <n-card title="错误信息" v-if="test.status_details?.message || test.status_details?.trace" style="margin-bottom: 16px">
        <n-text type="error">{{ test.status_details?.message }}</n-text>
        <n-code v-if="test.status_details?.trace" :code="test.status_details.trace" language="text"
          style="max-height: 400px; overflow: auto; margin-top: 8px" />
      </n-card>

      <n-card title="测试步骤" style="margin-bottom: 16px" v-if="test.steps?.length">
        <StepTree :steps="test.steps" />
      </n-card>
      <n-card title="测试步骤" style="margin-bottom: 16px" v-else>
        <n-text depth="3">无步骤</n-text>
      </n-card>

      <n-card title="附件" v-if="test.attachments?.length">
        <n-list>
          <n-list-item v-for="a in test.attachments" :key="a.id">
            <n-space align="center" justify="space-between">
              <n-space align="center">
                <n-text>📎 {{ a.name || a.source }}</n-text>
                <n-text depth="3">({{ a.type }}, {{ formatSize(a.size) }})</n-text>
              </n-space>
              <n-button size="tiny" ghost @click="downloadAttachment(a.id)">下载</n-button>
            </n-space>
          </n-list-item>
        </n-list>
      </n-card>
    </div>
  </n-spin>
</template>
