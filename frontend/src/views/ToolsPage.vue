<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { listProjects, type Project } from '../api/projects'
import { uploadResults } from '../api/reports'
import { useRouter } from 'vue-router'

const message = useMessage()
const router = useRouter()
const projects = ref<Project[]>([])
const selectedProject = ref<string | null>(null)
const uploading = ref(false)
const uploadStatus = ref('')

onMounted(async () => {
  const { data } = await listProjects()
  projects.value = data
})

async function handleUpload(data: { file: { file: File | null } }) {
  const file = data.file.file
  if (!file) return
  if (!selectedProject.value) {
    message.warning('请先选择项目')
    return
  }

  uploading.value = true
  uploadStatus.value = '上传中...'
  try {
    const { data: run } = await uploadResults(selectedProject.value, file)
    uploadStatus.value = '报告生成中，请稍候...'

    const runId = run.id
    const key = selectedProject.value

    let retries = 0
    const maxRetries = 60

    while (retries < maxRetries) {
      await new Promise(r => setTimeout(r, 2000))
      const resp = await fetch(`/api/projects/${key}/runs/${runId}`)
      const runData = await resp.json()
      if (runData.status === 'completed') {
        uploadStatus.value = '✅ 报告生成完成！'
        message.success('报告已就绪')
        router.push(`/projects/${key}`)
        return
      } else if (runData.status === 'failed') {
        uploadStatus.value = '❌ 报告生成失败: ' + (runData.error_message || '未知错误')
        message.error('生成失败')
        return
      }
      retries++
    }
    uploadStatus.value = '⏳ 超时，请在项目中手动查看状态'
  } catch (err: any) {
    message.error(err.response?.data?.detail || '上传失败')
    uploadStatus.value = '❌ 上传失败'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div>
    <n-h2 style="margin-top: 0; margin-bottom: 24px">🔧 工具</n-h2>

    <n-card title="上传 Allure Results" style="max-width: 640px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="目标项目" required>
          <n-select
            v-model:value="selectedProject"
            :options="projects.map(p => ({ label: `${p.name} (${p.key})`, value: p.key }))"
            placeholder="选择项目..."
          />
        </n-form-item>
        <n-form-item label="文件上传">
          <n-upload
            :show-file-list="true"
            accept=".zip"
            :max="1"
            @change="handleUpload"
            :disabled="uploading || !selectedProject"
          >
            <n-button :loading="uploading" type="primary" :disabled="!selectedProject">
              {{ uploading ? '上传中...' : '选择文件上传' }}
            </n-button>
          </n-upload>
        </n-form-item>
      </n-form>

      <n-alert v-if="uploadStatus" :type="uploadStatus.includes('❌') ? 'error' : uploadStatus.includes('✅') ? 'success' : 'info'" style="margin-top: 12px">
        {{ uploadStatus }}
      </n-alert>
    </n-card>

    <n-card title="📊 横向对比" size="small" style="max-width: 640px; margin-top: 16px">
      <n-text depth="3" style="margin-bottom: 12px; display: block">
        同时对比多个项目/分支/历史 Run 的测试结果，发现回归、共同失败、不稳定测试
      </n-text>
      <n-button type="primary" @click="router.push('/tools/compare')">
        打开横向对比
      </n-button>
    </n-card>
  </div>
</template>
