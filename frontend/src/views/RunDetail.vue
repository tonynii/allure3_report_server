<script setup lang="ts">
import { h, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useRunStore } from '../stores/run'
import { deleteRun } from '../api/reports'
import StatusTag from '../components/StatusTag.vue'
import StatsCards from '../components/StatsCards.vue'
import { formatDuration } from '../utils/format'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const store = useRunStore()
const key = computed(() => route.params.key as string)
const runId = computed(() => route.params.id as string)

onMounted(() => store.fetch(key.value, runId.value))

function goToTest(testId: string) {
  router.push(`/projects/${key.value}/runs/${runId.value}/tests/${testId}`)
}

async function handleDelete() {
  try {
    await deleteRun(key.value, runId.value)
    message.success('已删除')
    router.push(`/projects/${key.value}`)
  } catch (err: any) {
    message.error(err.response?.data?.detail || '删除失败')
  }
}

const filterOptions = [
  { label: '全部', value: '' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '异常', value: 'broken' },
  { label: '跳过', value: 'skipped' },
]

const tableColumns = [
  { title: 'Name', key: 'name', ellipsis: { tooltip: true } },
  { title: 'Status', key: 'status', width: 100, render: (row: any) => h(StatusTag, { status: row.status }) },
  { title: 'Duration', key: 'duration_ms', width: 100, render: (row: any) => formatDuration(row.duration_ms) },
]
</script>

<template>
  <div v-if="store.current">
    <n-space align="center" justify="space-between" style="margin-bottom: 24px">
      <n-space align="center">
        <n-button text @click="router.push(`/projects/${key}`)">← 返回</n-button>
        <n-h2 style="margin: 0">Run {{ runId.slice(0, 8) }}...</n-h2>
        <StatusTag :status="store.current.status" />
      </n-space>
      <n-popconfirm
        negative-text="取消"
        positive-text="确认删除"
        @positive-click="handleDelete"
      >
        <template #trigger>
          <n-button type="error" ghost size="small">🗑 删除</n-button>
        </template>
        确定删除此运行及其所有数据？此操作不可撤销
      </n-popconfirm>
    </n-space>

    <n-space style="margin-bottom: 8px">
      <n-tag :bordered="false" v-if="store.current.branch">branch: {{ store.current.branch }}</n-tag>
      <n-tag :bordered="false" v-if="store.current.commit_hash">commit: {{ store.current.commit_hash }}</n-tag>
    </n-space>

    <StatsCards v-bind="store.current" style="margin-bottom: 16px" />

    <n-space justify="space-between" align="center" style="margin-bottom: 12px">
      <n-radio-group v-model:value="store.statusFilter" size="small">
        <n-radio-button v-for="o in filterOptions" :key="o.value" :value="o.value">{{ o.label }}</n-radio-button>
      </n-radio-group>
      <n-input-group style="width: 300px">
        <n-input v-model:value="store.keyword" placeholder="搜索测试用例..." clearable />
      </n-input-group>
    </n-space>

    <n-data-table
      :columns="tableColumns"
      :data="store.filteredTests"
      :loading="store.loading"
      :row-props="(row: any) => ({ style: 'cursor: pointer', onClick: () => goToTest(row.id) })"
      :row-class-name="(_: any, i: number) => i % 2 ? 'row-alt' : ''"
      :pagination="{ pageSize: 20 }"
      :bordered="false"
    />
  </div>
</template>

<style scoped>
:deep(.row-alt td) { background: #fafafa !important; }
</style>
