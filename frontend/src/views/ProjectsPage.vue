<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useProjectStore } from '../stores/project'
import StatusTag from '../components/StatusTag.vue'
import type { ProjectCreate } from '../api/projects'

const router = useRouter()
const store = useProjectStore()
const showCreate = ref(false)
const newProject = ref<ProjectCreate>({ key: '', name: '', max_runs: 20 })
const message = useMessage()

onMounted(() => store.fetchAll())

function goTo(key: string) {
  router.push(`/projects/${key}`)
}

async function handleCreate() {
  try {
    await store.create({ ...newProject.value })
    showCreate.value = false
    newProject.value = { key: '', name: '', max_runs: 20 }
    message.success('项目创建成功')
  } catch (e: any) {
    const detail = e.response?.data?.detail
    if (Array.isArray(detail)) {
      message.error(detail[0]?.msg || '参数校验失败')
    } else {
      message.error(detail || '创建失败')
    }
  }
}

function handleDelete(key: string, e: Event) {
  e.stopPropagation()
  store.remove(key).then(() => message.success('已删除'))
    .catch(() => message.error('删除失败'))
}
</script>

<template>
  <div>
    <n-space justify="space-between" align="center" style="margin-bottom: 24px">
      <n-h2 style="margin: 0">项目列表</n-h2>
      <n-button type="primary" @click="showCreate = true">+ 创建项目</n-button>
    </n-space>

    <n-spin :show="store.loading">
      <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen">
        <n-gi v-for="p in store.projects" :key="p.key">
          <n-card hoverable @click="goTo(p.key)" style="cursor: pointer">
            <template #header-extra>
              <n-popconfirm @positive-click="(e: any) => handleDelete(p.key, e)">
                <template #trigger>
                  <n-button text type="error" size="tiny" @click.stop>删除</n-button>
                </template>
                确定删除项目 "{{ p.name }}" 及其所有数据？
              </n-popconfirm>
            </template>
            <n-space vertical>
              <n-text strong style="font-size: 16px">{{ p.name }}</n-text>
              <n-text depth="3" v-if="p.description">{{ p.description }}</n-text>
              <n-space align="center">
                <StatusTag :status="p.latest_run_status || 'unknown'" />
                <n-text depth="3">{{ p.runs_count }} runs</n-text>
              </n-space>
            </n-space>
          </n-card>
        </n-gi>
      </n-grid>
      <n-empty v-if="!store.loading && store.projects.length === 0" description="暂无项目，点击上方按钮创建一个" />
    </n-spin>

    <n-modal v-model:show="showCreate" title="创建项目">
      <n-card style="width: 500px" :bordered="false" role="dialog">
        <n-form :model="newProject" label-placement="left" label-width="100">
          <n-form-item label="Key" required>
            <n-input v-model:value="newProject.key" placeholder="my-app-backend" />
          </n-form-item>
          <n-form-item label="名称" required>
            <n-input v-model:value="newProject.name" placeholder="我的应用" />
          </n-form-item>
          <n-form-item label="描述">
            <n-input v-model:value="newProject.description" type="textarea" placeholder="可选" />
          </n-form-item>
          <n-form-item label="保留 Runs">
            <n-input-number v-model:value="newProject.max_runs" :min="1" :max="200" />
          </n-form-item>
        </n-form>
        <n-space justify="end">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" @click="handleCreate">创建</n-button>
        </n-space>
      </n-card>
    </n-modal>
  </div>
</template>
