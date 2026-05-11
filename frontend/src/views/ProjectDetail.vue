<script setup lang="ts">
import { h, computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useProjectStore } from '../stores/project'
import { useRunStore } from '../stores/run'
import { uploadResults } from '../api/reports'
import StatsCards from '../components/StatsCards.vue'
import PieChart from '../components/PieChart.vue'
import TrendChart from '../components/TrendChart.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDuration, formatTime } from '../utils/format'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const runStore = useRunStore()
const message = useMessage()
const uploading = ref(false)

const key = computed(() => route.params.key as string)

onMounted(async () => {
  await projectStore.fetch(key.value)
  await runStore.fetchRuns(key.value)
})

const trendData = computed(() =>
  [...runStore.runs]
    .reverse()
    .map(r => ({ timestamp: r.created_at, passed: r.passed, failed: r.failed, total: r.total }))
)

const latest = computed(() => runStore.runs[0] || null)

async function handleUpload(data: { file: { file: File | null } }) {
  const file = data.file.file
  if (!file) return
  uploading.value = true
  try {
    await uploadResults(key.value, file)
    message.success('上传成功，正在生成报告...')
    setTimeout(() => runStore.fetchRuns(key.value), 2000)
  } catch (err: any) {
    message.error(err.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

function goToRun(id: string) {
  router.push(`/projects/${key.value}/runs/${id}`)
}

function viewReport(runId?: string) {
  const id = runId || 'latest'
  window.open(`/api/projects/${key.value}/reports/${id}/`, '_blank')
}

const columns = [
  { title: 'Run ID', key: 'id', render: (row: any) => row.id.slice(0, 8) + '...' },
  { title: '时间', key: 'created_at', render: (row: any) => formatTime(row.created_at) },
  { title: '状态', key: 'status', render: (row: any) => h(StatusTag, { status: row.status }) },
  { title: 'Branch', key: 'branch', render: (row: any) => row.branch || '-' },
  { title: 'Total', key: 'total' },
  { title: 'Passed', key: 'passed', render: (row: any) => h('span', { style: { color: '#18a058' } }, row.passed) },
  { title: 'Failed', key: 'failed', render: (row: any) => h('span', { style: { color: '#d03050' } }, row.failed) },
  { title: 'Duration', key: 'duration_ms', render: (row: any) => formatDuration(row.duration_ms) },
  {
    title: '操作',
    key: 'actions',
    render: (row: any) =>
      row.status === 'completed'
        ? h('a', { href: '#', onClick: (e: Event) => { e.preventDefault(); viewReport(row.id) } }, '查看报告')
        : '-',
  },
]
</script>

<template>
  <div v-if="projectStore.current">
    <n-space align="center" style="margin-bottom: 24px">
      <n-button text @click="router.push('/')">← 返回</n-button>
      <n-h2 style="margin: 0">{{ projectStore.current.name }}</n-h2>
      <n-text depth="3">({{ projectStore.current.key }})</n-text>

      <n-space style="margin-left: auto">
        <n-upload :show-file-list="false" accept=".zip" @change="handleUpload" :disabled="uploading">
          <n-button :loading="uploading" type="primary">{{ uploading ? '上传中...' : '📤 上传报告' }}</n-button>
        </n-upload>
        <n-button v-if="latest?.status === 'completed'" @click="viewReport()">查看最新报告</n-button>
      </n-space>
    </n-space>

    <StatsCards v-if="latest" v-bind="latest" style="margin-bottom: 24px" />

    <n-grid :cols="2" :x-gap="16" style="margin-bottom: 24px">
      <n-gi><PieChart v-if="latest" v-bind="latest" /></n-gi>
      <n-gi><TrendChart v-if="trendData.length > 1" :data="trendData" /></n-gi>
    </n-grid>

    <n-card title="Run 历史" size="small">
      <n-data-table :columns="columns" :data="runStore.runs" :bordered="false"
        :row-props="(row: any) => ({ style: 'cursor: pointer', onClick: () => goToRun(row.id) })"
        :pagination="{ pageSize: 10 }" />
    </n-card>
  </div>
</template>
