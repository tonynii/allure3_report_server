<script setup lang="ts">
import StatusTag from './StatusTag.vue'
import { formatDuration } from '../utils/format'

defineProps<{
  steps: {
    id: string
    name: string
    status: string
    duration_ms: number | null
    children: any[]
  }[]
  level?: number
}>()

const defaultLevel = 0
</script>

<template>
  <div v-for="step in steps" :key="step.id" :style="{ marginLeft: (level ?? defaultLevel) * 24 + 'px' }">
    <n-space align="center" style="padding: 6px 0">
      <StatusTag :status="step.status" size="small" />
      <span>{{ step.name }}</span>
      <n-text depth="3" style="font-size: 12px">{{ formatDuration(step.duration_ms) }}</n-text>
    </n-space>
    <StepTree v-if="step.children?.length" :steps="step.children" :level="(level ?? defaultLevel) + 1" />
  </div>
</template>
