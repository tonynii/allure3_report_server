<script setup lang="ts">
import { h, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '../stores/dashboard'
import StatusTag from '../components/StatusTag.vue'
import { formatTime } from '../utils/format'

const router = useRouter()
const store = useDashboardStore()

onMounted(() => store.fetch())

const passRatePercent = computed(() => {
  if (!store.data) return '0%'
  return (store.data.overall_pass_rate * 100).toFixed(1) + '%'
})

const recentColumns = [
  { title: 'Run', key: 'id', width: 100, render: (row: any) => row.id.slice(0, 6) + '...' },
  { title: '项目', key: 'project_name', width: 120 },
  { title: '状态', key: 'status', width: 90, render: (row: any) => h(StatusTag, { status: row.status }) },
  { title: '通过', key: 'passed', width: 70, render: (row: any) => h('span', { style: { color: '#18a058' } }, row.passed) },
  { title: '失败', key: 'failed', width: 70, render: (row: any) => h('span', { style: { color: row.failed > 0 ? '#d03050' : '#999' } }, row.failed) },
  { title: 'Total', key: 'total', width: 60 },
  { title: '时间', key: 'created_at', render: (row: any) => formatTime(row.created_at) },
]
</script>

<template>
  <n-spin :show="store.loading">
    <n-h2 style="margin-top: 0; margin-bottom: 24px">📊 看板</n-h2>

    <n-grid :cols="3" :x-gap="16" style="margin-bottom: 24px">
      <n-gi>
        <n-card size="small" :bordered="false" style="background: #f0f9eb; text-align: center">
          <n-statistic label="项目数" :value="store.data?.project_count ?? '-'" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" :bordered="false" style="background: #ebf4ff; text-align: center">
          <n-statistic label="运行次数" :value="store.data?.total_runs ?? '-'" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small" :bordered="false" :style="{ background: (store.data?.overall_pass_rate ?? 0) >= 0.9 ? '#f0f9eb' : '#fef0f0', textAlign: 'center' }">
          <n-statistic label="总体通过率">
            <span :style="{ color: (store.data?.overall_pass_rate ?? 0) >= 0.9 ? '#18a058' : '#d03050', fontSize: '28px', fontWeight: 'bold' }">{{ passRatePercent }}</span>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <n-h3 style="margin-bottom: 12px">项目概况</n-h3>
    <n-grid :cols="2" :x-gap="16" :y-gap="16" style="margin-bottom: 24px">
      <n-gi v-for="p in store.data?.projects" :key="p.key">
        <n-card hoverable size="small" @click="router.push(`/projects/${p.key}`)">
          <n-space justify="space-between" align="center">
            <n-space vertical size="small">
              <n-text strong>{{ p.name }}</n-text>
              <n-text depth="3" style="font-size: 12px">{{ p.key }}</n-text>
            </n-space>
            <n-space vertical size="small" align="end">
              <StatusTag :status="p.latest_run?.status || 'unknown'" size="small" />
              <n-text v-if="p.latest_run" depth="3" style="font-size: 12px">
                {{ p.latest_run.passed }}/{{ p.latest_run.total }} 通过
              </n-text>
            </n-space>
          </n-space>
          <n-progress
            v-if="p.latest_run?.total"
            type="line"
            :percentage="Math.round((p.latest_run.passed / p.latest_run.total) * 100)"
            :color="(p.latest_run.passed / p.latest_run.total) >= 0.9 ? '#18a058' : (p.latest_run.passed / p.latest_run.total) >= 0.7 ? '#f0a020' : '#d03050'"
            :height="4"
            :border-radius="2"
            style="margin-top: 8px"
          />
          <n-text depth="3" style="font-size: 12px">{{ p.runs_count }} runs</n-text>
        </n-card>
      </n-gi>
    </n-grid>

    <n-h3 style="margin-bottom: 12px">最近运行</n-h3>
    <n-data-table
      :columns="recentColumns"
      :data="store.data?.recent_runs ?? []"
      :bordered="false"
      size="small"
      :row-props="(row: any) => ({ style: 'cursor: pointer', onClick: () => router.push(`/projects/${row.project_key}/runs/${row.id}`) })"
      :row-class-name="(_: any, i: number) => i % 2 ? 'row-alt' : ''"
      :pagination="false"
    />
    <n-empty v-if="!store.data?.recent_runs?.length" description="暂无运行记录" />
  </n-spin>
</template>

<style scoped>
:deep(.row-alt td) { background: #fafafa !important; }
</style>
