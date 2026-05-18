<script setup lang="ts">
import { h, computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { useProjectStore } from '../stores/project'
import { useRunStore } from '../stores/run'
import { uploadResults, deleteRun, regenerateReport } from '../api/reports'
import { updateProject } from '../api/projects'
import StatsCards from '../components/StatsCards.vue'
import PieChart from '../components/PieChart.vue'
import TrendChart from '../components/TrendChart.vue'
import StatusTag from '../components/StatusTag.vue'
import AllureConfigEditor from '../components/AllureConfigEditor.vue'
import { formatDuration, formatTime } from '../utils/format'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const runStore = useRunStore()
const message = useMessage()
const dialog = useDialog()
const uploading = ref(false)
const showSettings = ref(false)
const editForm = ref({ name: '', description: '', max_runs: 20, allure_config: null as string | null })
const hoverRow = ref<any>(null)
const hoverTimer = ref<number | null>(null)
const hoverPos = ref({ x: 0, y: 0 })

function onRowEnter(e: MouseEvent, row: any) {
  hoverPos.value = { x: e.clientX + 16, y: e.clientY - 120 }
  if (hoverTimer.value) clearTimeout(hoverTimer.value)
  hoverTimer.value = window.setTimeout(() => { hoverRow.value = row }, 350)
}

function onRowLeave() {
  if (hoverTimer.value) clearTimeout(hoverTimer.value)
  hoverTimer.value = window.setTimeout(() => { hoverRow.value = null }, 150)
}

function onCardEnter() {
  if (hoverTimer.value) clearTimeout(hoverTimer.value)
}

function onCardLeave() {
  if (hoverTimer.value) clearTimeout(hoverTimer.value)
  hoverRow.value = null
}

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

function handleDeleteRun(runId: string) {
  dialog.warning({
    title: '确认删除',
    content: '确定删除此报告？此操作不可撤销',
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteRun(key.value, runId)
        message.success('已删除')
        await runStore.fetchRuns(key.value)
      } catch (err: any) {
        message.error(err.response?.data?.detail || '删除失败')
      }
    },
  })
}

function viewReport(runId?: string) {
  if (runId) {
    window.open(`/reports/${key.value}/${runId}/`, '_blank')
  } else if (latest.value) {
    window.open(`/reports/${key.value}/${latest.value.id}/`, '_blank')
  }
}

const regeneratingRunId = ref<string | null>(null)

async function handleRegenerateRun(runId: string) {
  regeneratingRunId.value = runId
  try {
    await regenerateReport(key.value, runId)
    message.success('正在重新生成...')
    let attempts = 0
    while (attempts < 60) {
      await new Promise(r => setTimeout(r, 2000))
      await runStore.fetchRuns(key.value)
      const run = runStore.runs.find(r => r.id === runId)
      if (run && run.status !== 'processing') {
        if (run.status === 'completed') {
          message.success('报告重新生成完成')
          await projectStore.fetch(key.value)
        } else {
          message.error(`重新生成失败: ${(run as any).error_message || '未知错误'}`)
        }
        break
      }
      attempts++
    }
  } catch (err: any) {
    message.error(err.response?.data?.detail || '重新生成失败')
  } finally {
    regeneratingRunId.value = null
  }
}

function openSettings() {
  if (!projectStore.current) return
  editForm.value = {
    name: projectStore.current.name,
    description: projectStore.current.description || '',
    max_runs: projectStore.current.max_runs,
    allure_config: projectStore.current.allure_config,
  }
  showSettings.value = true
}

async function handleSave() {
  try {
    await updateProject(key.value, {
      name: editForm.value.name,
      description: editForm.value.description || undefined,
      max_runs: editForm.value.max_runs,
    })
    await projectStore.fetch(key.value)
    showSettings.value = false
    message.success('设置已保存')
  } catch (err: any) {
    message.error(err.response?.data?.detail || '保存失败')
  }
}

async function handleConfigSaved(c: string) {
  editForm.value.allure_config = c as string | null
  await projectStore.fetch(key.value)
}

const columns = [
  { title: 'Run ID', key: 'id', render: (row: any) => h('span', { onMouseenter: (e: MouseEvent) => onRowEnter(e, row), onMouseleave: onRowLeave, style: 'cursor: pointer' }, row.id.slice(0, 8) + '...') },
  { title: '时间', key: 'created_at', render: (row: any) => h('span', { onMouseenter: (e: MouseEvent) => onRowEnter(e, row), onMouseleave: onRowLeave, style: 'cursor: pointer' }, formatTime(row.created_at)) },
  { title: '状态', key: 'status', render: (row: any) => h('span', { onMouseenter: (e: MouseEvent) => onRowEnter(e, row), onMouseleave: onRowLeave, style: 'cursor: pointer' }, h(StatusTag, { status: row.status })) },
  { title: 'Branch', key: 'branch', render: (row: any) => row.branch || '-' },
  { title: '结果', key: 'stats', render: (row: any) =>
    h('span', {}, [
      h('span', {}, `${row.total} `),
      h('span', { style: { color: '#18a058' } }, `✅${row.passed} `),
      h('span', { style: { color: '#d03050' } }, `❌${row.failed} `),
      h('span', { style: { color: '#f0a020' } }, `💥${row.broken}`),
    ])
  },
  { title: '通过率', key: 'pass_rate', width: 80,
    render: (row: any) => {
      const d = row.passed + row.failed + row.broken
      if (d === 0) return h('span', { style: { color: '#999' } }, '-')
      const rate = Math.round((row.passed / d) * 100)
      const color = rate >= 90 ? '#18a058' : rate >= 70 ? '#f0a020' : '#d03050'
      return h('span', { style: { color, fontWeight: 'bold' } }, `${rate}%`)
    },
  },
  { title: 'Duration', key: 'duration_ms', render: (row: any) => formatDuration(row.duration_ms) },
  {
    title: '操作',
    key: 'actions',
    width: 280,
    render: (row: any) =>
      h('n-space', { size: 'small' }, [
        h('n-button', {
          size: 'small', ghost: true, type: 'primary',
          onClick: (e: Event) => { e.stopPropagation(); goToRun(row.id) },
        }, { default: () => '📊 详情' }),
        row.status === 'completed'
          ? h('n-button', {
              size: 'small', ghost: true, type: 'success',
              onClick: (e: Event) => { e.stopPropagation(); viewReport(row.id) },
            }, { default: () => '📄 报告' })
          : h('span', {}, '-'),
        row.status === 'completed' || row.status === 'failed'
          ? h('n-button', {
              size: 'small', ghost: true, type: 'warning',
              loading: regeneratingRunId.value === row.id,
              onClick: (e: Event) => { e.stopPropagation(); handleRegenerateRun(row.id) },
            }, { default: () => '🔄 重生成' })
          : h('span', {}, '-'),
        h('n-button', {
          size: 'small', ghost: true, type: 'error',
          onClick: (e: Event) => { e.stopPropagation(); handleDeleteRun(row.id) },
        }, { default: () => '🗑 删除' }),
      ]),
  },
]
</script>

<template>
  <div v-if="projectStore.current">
    <n-space align="center" style="margin-bottom: 24px">
      <n-button text @click="router.push('/projects')">← 返回</n-button>
      <n-h2 style="margin: 0">{{ projectStore.current.name }}</n-h2>
      <n-text depth="3">({{ projectStore.current.key }})</n-text>

      <n-space style="margin-left: auto">
        <n-upload :show-file-list="false" accept=".zip" @change="handleUpload" :disabled="uploading">
          <n-button :loading="uploading" type="primary">{{ uploading ? '上传中...' : '📤 上传报告' }}</n-button>
        </n-upload>
        <n-button v-if="latest?.status === 'completed'" ghost type="primary" @click="goToRun(latest!.id)">📊 最新详情</n-button>
        <n-button v-if="latest?.status === 'completed'" ghost type="success" @click="viewReport()">📄 最新报告</n-button>
        <n-button ghost @click="openSettings">⚙️ 设置</n-button>
      </n-space>
    </n-space>

    <StatsCards v-if="latest" v-bind="latest" style="margin-bottom: 24px" />

    <n-grid :cols="2" :x-gap="16" style="margin-bottom: 24px">
      <n-gi><PieChart v-if="latest" v-bind="latest" /></n-gi>
      <n-gi><TrendChart v-if="trendData.length > 1" :data="trendData" /></n-gi>
    </n-grid>

    <n-card title="Run 历史" size="small">
      <n-data-table :columns="columns" :data="runStore.runs" :bordered="false"
        :row-props="() => ({ style: 'cursor: pointer' })"
        :row-class-name="(_: any, i: number) => i % 2 ? 'row-alt' : ''"
        :pagination="{ pageSize: 10 }" />
    </n-card>

    <div v-if="hoverRow" :style="{
      position: 'fixed', top: hoverPos.y + 'px', left: hoverPos.x + 'px',
      zIndex: 9999, minWidth: '260px', maxWidth: '480px', maxHeight: '60vh', overflowY: 'auto',
    }" @mouseenter="onCardEnter" @mouseleave="onCardLeave">
      <n-card size="small" :bordered="true">
        <template #header>
          <n-text strong style="font-size: 13px">{{ hoverRow.branch || 'Run' }} {{ hoverRow.id?.slice(0, 8) }}...</n-text>
        </template>
        <n-descriptions v-if="hoverRow.environment?.length" :columns="1" size="small" label-placement="left">
          <n-descriptions-item v-for="e in hoverRow.environment" :key="e.key" :label="e.key">
            {{ e.value }}
          </n-descriptions-item>
        </n-descriptions>
        <n-text v-else depth="3" style="font-size: 12px">无环境信息</n-text>
      </n-card>
    </div>

    <n-modal v-model:show="showSettings" title="⚙️ 项目设置" style="width: 700px">
      <n-card role="dialog" :bordered="false">
        <n-tabs type="line" default-value="basic">
          <n-tab-pane name="basic" tab="基本信息">
            <n-form label-placement="left" label-width="100">
              <n-form-item label="名称" required>
                <n-input v-model:value="editForm.name" placeholder="项目名称" />
              </n-form-item>
              <n-form-item label="描述">
                <n-input v-model:value="editForm.description" type="textarea" placeholder="项目描述" />
              </n-form-item>
              <n-form-item label="保留 Runs">
                <n-input-number v-model:value="editForm.max_runs" :min="1" :max="200" />
              </n-form-item>
            </n-form>
            <n-space justify="end">
              <n-button @click="showSettings = false">取消</n-button>
              <n-button type="primary" @click="handleSave">保存</n-button>
            </n-space>
          </n-tab-pane>
          <n-tab-pane name="config" tab="Allure 配置">
            <AllureConfigEditor
              :project-key="key"
              :config="editForm.allure_config ?? null"
              @saved="handleConfigSaved"
            />
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </n-modal>
  </div>
</template>

<style scoped>
:deep(.row-alt td) { background: #fafafa !important; }
</style>
