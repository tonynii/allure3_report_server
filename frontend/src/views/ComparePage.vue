<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { useMessage } from 'naive-ui'
import { listProjects, type Project } from '../api/projects'
import { listRuns, type Run } from '../api/reports'
import { compareRuns, type CompareResponse, type CompareTest } from '../api/compare'
import { statusColor, statusLabel } from '../utils/status'
import { formatDuration } from '../utils/format'

const message = useMessage()
const projects = ref<Project[]>([])
const runsCache = ref<Record<string, Run[]>>({})
const selections = ref<{ project: string; run: string }[]>([
  { project: '', run: '' },
  { project: '', run: '' },
])
const statusChangeOnly = ref(false)
const keyword = ref('')
const loading = ref(false)
const data = ref<CompareResponse | null>(null)
const expandedTestId = ref<string | null>(null)

const expandedTest = computed(() => {
  if (!data.value || !expandedTestId.value) return null
  return data.value.tests.find(t => t.historyId === expandedTestId.value) || null
})

onMounted(async () => {
  const { data: p } = await listProjects()
  projects.value = p
})

async function loadRuns(idx: number) {
  const proj = selections.value[idx].project
  if (!proj) return
  if (!runsCache.value[proj]) {
    const { data } = await listRuns(proj)
    runsCache.value[proj] = data
  }
  selections.value[idx].run = ''
}

function addSelection() {
  selections.value.push({ project: '', run: '' })
}

function removeSelection(idx: number) {
  if (selections.value.length <= 2) return
  selections.value.splice(idx, 1)
}

async function doCompare() {
  const runs = selections.value.filter(s => s.project && s.run)
  if (runs.length < 2) {
    message.warning('至少选择 2 个 Run')
    return
  }
  loading.value = true
  expandedTestId.value = null
  try {
    const { data: d } = await compareRuns({
      runs, status_change_only: statusChangeOnly.value, keyword: keyword.value,
    })
    if (d.error) { message.error(d.error); return }
    data.value = d
  } catch (err: any) {
    message.error(err.response?.data?.detail || '对比失败')
  } finally {
    loading.value = false
  }
}

const summaryCats = ['all_pass', 'all_fail', 'mixed', 'flaky'] as const
const summaryLabels: Record<string, string> = {
  all_pass: '全部通过', all_fail: '全部失败', mixed: '有差异', flaky: '不稳定',
}

function getResult(test: CompareTest, runId: string) {
  return test.results[runId] || null
}

const compareColumns = computed(() => {
  if (!data.value) return []
  return [
    { title: 'Test Name', key: 'name', width: 200, ellipsis: { tooltip: true },
      render: (row: CompareTest) => h('span', {}, row.name) },
    ...data.value.columns.map(c => ({
      title: c.label, key: c.run_id, width: 130, align: 'center' as const,
      render: (row: CompareTest) => {
        const r = getResult(row, c.run_id)
        if (!r) return h('span', { style: { color: '#ccc' } }, '-')
        return h('span', { style: { color: statusColor[r.status] || '#999', fontWeight: 'bold' } }, `${statusLabel[r.status]} ${formatDuration(r.duration_ms)}`)
      },
    })),
  ]
})

function toggleExpand(historyId: string) {
  expandedTestId.value = expandedTestId.value === historyId ? null : historyId
}

const showDetail = computed({
  get: () => !!expandedTest.value,
  set: (v) => { if (!v) expandedTestId.value = null },
})
</script>

<template>
  <div>
    <n-h2 style="margin-top: 0; margin-bottom: 16px">📊 横向对比</n-h2>

    <n-card size="small" style="margin-bottom: 16px">
      <n-space vertical size="small">
        <n-text>选择 Run 进行对比（至少 2 个）：</n-text>
        <div v-for="(s, i) in selections" :key="i">
          <n-space align="center">
            <n-select
              :value="s.project"
              :options="projects.map(p => ({ label: p.name, value: p.key }))"
              placeholder="项目"
              style="width: 180px"
              @update:value="(v: string) => { s.project = v; loadRuns(i) }"
            />
            <n-select
              v-model:value="s.run"
              :options="(runsCache[s.project] || []).map(r => ({
                label: `${r.id.slice(0,6)}... ${r.branch||''} ${r.passed}/${r.total} (${r.created_at?.slice(0,10)})`,
                value: r.id,
              }))"
              placeholder="Run"
              style="width: 320px"
              :disabled="!s.project"
            />
            <n-button v-if="selections.length > 2" size="tiny" circle @click="removeSelection(i)" type="error">✕</n-button>
          </n-space>
        </div>

        <n-space>
          <n-button size="small" ghost @click="addSelection">+ 添加 Run</n-button>
          <n-checkbox v-model:checked="statusChangeOnly">仅显示有变化</n-checkbox>
          <n-input v-model:value="keyword" placeholder="搜索测试..." size="small" style="width: 200px" clearable
            @keyup.enter="doCompare" />
          <n-button type="primary" @click="doCompare" :loading="loading">开始对比</n-button>
        </n-space>
      </n-space>
    </n-card>

    <n-spin :show="loading">
      <template v-if="data">
        <n-space style="margin-bottom: 12px">
          <n-tag v-for="cat in summaryCats" :key="cat"
            :type="cat === 'all_pass' ? 'success' : cat === 'all_fail' ? 'error' : cat === 'flaky' ? 'warning' : 'info'">
            {{ summaryLabels[cat] }}: {{ data.summary[cat] }}
          </n-tag>
        </n-space>

        <n-data-table
          :columns="compareColumns"
          :data="data.tests"
          :bordered="false"
          size="small"
          :row-class-name="(_: any, i: number) => i % 2 ? 'row-alt' : ''"
          :row-props="(row: CompareTest) => ({ style: 'cursor: pointer', onClick: () => toggleExpand(row.historyId) })"
          :pagination="{ pageSize: 30 }"
          :max-height="600"
        />

        <n-modal v-model:show="showDetail" preset="card" style="width: 700px" :title="expandedTest?.name || ''">
          <template v-if="expandedTest">
            <n-descriptions :columns="2" label-placement="left" size="small" style="margin-bottom: 12px">
              <n-descriptions-item label="History ID">{{ expandedTest.historyId }}</n-descriptions-item>
              <n-descriptions-item label="Full Name">{{ expandedTest.fullName }}</n-descriptions-item>
            </n-descriptions>
            <n-space v-if="expandedTest.labels?.length" style="margin-bottom: 12px">
              <n-tag v-for="l in expandedTest.labels" :key="l.name+l.value" size="tiny" round>
                {{ l.name }}: {{ l.value }}
              </n-tag>
            </n-space>
            <n-divider />
            <div v-for="c in data.columns" :key="c.run_id" style="margin-bottom: 10px">
              <n-text strong>{{ c.label }}: </n-text>
              <template v-if="getResult(expandedTest, c.run_id)">
                <span :style="{ color: statusColor[getResult(expandedTest, c.run_id)!.status] || '#999', fontWeight: 'bold' }">
                  {{ statusLabel[getResult(expandedTest, c.run_id)!.status] }}
                  {{ formatDuration(getResult(expandedTest, c.run_id)!.duration_ms) }}
                </span>
                <n-text v-if="getResult(expandedTest, c.run_id)!.error_message" depth="3" style="display: block; font-size: 12px; margin-top: 2px">
                  {{ getResult(expandedTest, c.run_id)!.error_message }}
                </n-text>
              </template>
              <span v-else style="color:#ccc">-</span>
            </div>
          </template>
        </n-modal>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
:deep(.row-alt td) { background: #fafafa !important; }
</style>
