<script setup lang="ts">
import { h, ref, computed, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import { getSettings, type SettingsData, type SettingsProject } from '../api/dashboard'
import { updateProject, deleteProject, getProject } from '../api/projects'
import AllureConfigEditor from '../components/AllureConfigEditor.vue'

const message = useMessage()
const dialog = useDialog()
const data = ref<SettingsData | null>(null)
const loading = ref(true)
const editProject = ref<SettingsProject | null>(null)
const editForm = ref({ name: '', description: '', max_runs: 20, allure_config: null as string | null })
const showEdit = computed({
  get: () => !!editProject.value,
  set: (v) => { if (!v) editProject.value = null },
})

onMounted(async () => {
  try {
    const { data: d } = await getSettings()
    data.value = d
  } finally {
    loading.value = false
  }
})

async function openEdit(p: SettingsProject) {
  editProject.value = p
  editForm.value = { name: p.name, description: p.description || '', max_runs: p.max_runs, allure_config: null }
  try {
    const { data } = await getProject(p.key)
    editForm.value.allure_config = data.allure_config ?? null
  } catch {}
}

async function handleSave() {
  if (!editProject.value) return
  try {
    await updateProject(editProject.value.key, {
      name: editForm.value.name,
      description: editForm.value.description || undefined,
      max_runs: editForm.value.max_runs,
    })
    message.success('已保存')
    editProject.value = null
    const { data: d } = await getSettings()
    data.value = d
  } catch (err: any) {
    message.error(err.response?.data?.detail || '保存失败')
  }
}

async function handleConfigSaved(c: string) {
  editForm.value.allure_config = c as string | null
  if (editProject.value) {
    editProject.value = { ...editProject.value }
  }
  const { data: d } = await getSettings()
  data.value = d
}

function handleDelete(p: SettingsProject) {
  dialog.warning({
    title: '确认删除项目',
    content: `确定删除「${p.name}」及其所有数据？此操作不可撤销`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteProject(p.key)
        message.success('已删除')
        const { data: d } = await getSettings()
        data.value = d
      } catch (err: any) {
        message.error(err.response?.data?.detail || '删除失败')
      }
    },
  })
}

const columns = [
  { title: '项目', key: 'name', render: (row: SettingsProject) => h('span', {}, row.name) },
  { title: 'Key', key: 'key', width: 140 },
  { title: 'Runs', key: 'runs_count', width: 70 },
  { title: '空间', key: 'storage_human', width: 100 },
  { title: 'Max', key: 'max_runs', width: 60 },
  {
    title: '操作',
    key: 'actions',
    width: 140,
    render: (row: SettingsProject) =>
      h('n-space', { size: 'small' }, [
        h('n-button', { size: 'small', ghost: true, onClick: () => openEdit(row) }, { default: () => '✏️ 编辑' }),
        h('n-button', { size: 'small', ghost: true, type: 'error', onClick: () => handleDelete(row) }, { default: () => '🗑 删除' }),
      ]),
  },
]
</script>

<template>
  <div>
    <n-h2 style="margin-top: 0; margin-bottom: 24px">⚙️ 配置</n-h2>

    <n-spin :show="loading">
      <n-grid :cols="2" :x-gap="16" style="margin-bottom: 24px">
        <n-gi>
          <n-card size="small" title="全局信息">
            <n-descriptions :columns="1" label-placement="left">
              <n-descriptions-item label="数据目录">{{ data?.data_dir || '-' }}</n-descriptions-item>
              <n-descriptions-item label="目录大小">{{ data?.total_dir_size_human || '-' }}</n-descriptions-item>
              <n-descriptions-item label="数据库大小">{{ data?.database_size_human || '-' }}</n-descriptions-item>
              <n-descriptions-item label="Allure 版本">{{ data?.allure_version || '-' }}</n-descriptions-item>
              <n-descriptions-item label="默认保留">{{ data?.default_max_runs || '-' }} runs</n-descriptions-item>
            </n-descriptions>
          </n-card>
        </n-gi>
        <n-gi v-if="data?.mcp">
          <n-card size="small" title="MCP Server">
            <n-descriptions :columns="1" label-placement="left" size="small">
              <n-descriptions-item label="端点">{{ data.mcp.endpoint }}</n-descriptions-item>
              <n-descriptions-item label="协议">{{ data.mcp.protocol }}</n-descriptions-item>
              <n-descriptions-item label="SDK">v{{ data.mcp.version }}</n-descriptions-item>
              <n-descriptions-item label="Tools">{{ data.mcp.tools_count }}</n-descriptions-item>
              <n-descriptions-item label="Resources">{{ data.mcp.resources_count }}</n-descriptions-item>
              <n-descriptions-item label="Prompts">{{ data.mcp.prompts_count }}</n-descriptions-item>
            </n-descriptions>
            <n-divider style="margin: 12px 0" />
            <n-text depth="3" style="font-size: 12px">Cursor / VS Code / Chatbox 连接配置：</n-text>
            <n-code
              code='{"mcpServers":{"allure3":{"url":"http://..."}}}'
              language="json"
              style="margin-top: 6px; font-size: 12px"
            />
          </n-card>
        </n-gi>
      </n-grid>

      <n-h3 style="margin-bottom: 12px">项目概况</n-h3>
      <n-data-table :columns="columns" :data="data?.projects ?? []" :bordered="false" size="small"
        :row-props="() => ({ style: 'cursor: pointer' })"
        :row-class-name="(_: any, i: number) => i % 2 ? 'row-alt' : ''" />
    </n-spin>

    <n-modal v-model:show="showEdit" title="编辑项目" style="width: 700px">
      <n-card v-if="editProject" role="dialog" :bordered="false">
        <n-tabs type="line" default-value="basic">
          <n-tab-pane name="basic" tab="基本信息">
            <n-form label-placement="left" label-width="100">
              <n-form-item label="Key">
                <n-text>{{ editProject.key }}</n-text>
              </n-form-item>
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
              <n-button @click="editProject = null">取消</n-button>
              <n-button type="primary" @click="handleSave">保存</n-button>
            </n-space>
          </n-tab-pane>
          <n-tab-pane name="config" tab="Allure 配置">
            <AllureConfigEditor
              :project-key="editProject.key"
              :config="editForm.allure_config"
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
