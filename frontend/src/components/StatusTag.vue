<script setup lang="ts">
import { statusColor, statusLabel } from '../utils/status'

const props = defineProps<{
  status: string
  size?: 'small' | 'medium' | 'large'
}>()
</script>

<template>
  <n-tag :color="{ color: statusColor[status] || '#999', textColor: '#fff' }" :size="size" round>
    {{ statusLabel[status] || status }}
  </n-tag>
</template>
