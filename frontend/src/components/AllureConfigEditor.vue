<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { updateProject, getDefaultAllureConfig } from '../api/projects'

const props = defineProps<{ projectKey: string; config: string | null }>()
const emit = defineEmits<{ (e: 'saved', config: string): void }>()
const message = useMessage()

const localConfig = ref(props.config ?? '')
const saving = ref(false)
const loadingDefault = ref(false)

watch(() => props.config, (v) => {
  if (v !== null && v !== localConfig.value) {
    localConfig.value = v
  }
})

onMounted(async () => {
  if (!props.config) {
    await loadDefault()
  }
})

async function handleSave() {
  saving.value = true
  try {
    await updateProject(props.projectKey, { allure_config: localConfig.value })
    message.success('配置已保存')
    emit('saved', localConfig.value)
  } catch (err: any) {
    message.error(err.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function loadDefault() {
  loadingDefault.value = true
  try {
    const { data } = await getDefaultAllureConfig(props.projectKey)
    localConfig.value = data.config
  } catch (err: any) {
    message.error('加载默认配置失败')
  } finally {
    loadingDefault.value = false
  }
}
</script>

<template>
  <div>
    <n-space justify="space-between" align="center" style="margin-bottom: 8px">
      <n-text depth="3" style="font-size: 12px">
        配置将在下次生成报告时生效。如有语法错误，报告生成将失败。
      </n-text>
      <n-button size="tiny" ghost :loading="loadingDefault" @click="loadDefault">
        加载默认配置
      </n-button>
    </n-space>
    <n-input
      v-model:value="localConfig"
      type="textarea"
      :rows="18"
      placeholder="export default { ... }"
      style="font-family: monospace; font-size: 13px"
    />
    <n-space justify="end" style="margin-top: 12px">
      <n-button type="primary" :loading="saving" @click="handleSave">保存配置</n-button>
    </n-space>
  </div>
</template>
