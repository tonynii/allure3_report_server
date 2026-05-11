<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { statusColor, statusLabel } from '../utils/status'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  passed: number
  failed: number
  broken: number
  skipped: number
}>()

const option = computed(() => ({
  tooltip: { trigger: 'item' as const },
  legend: { bottom: 0 },
  series: [{
    type: 'pie' as const,
    radius: ['40%', '70%'],
    avoidLabelOverlap: false,
    label: { show: false },
    data: [
      { value: props.passed, name: statusLabel.passed, itemStyle: { color: statusColor.passed } },
      { value: props.failed, name: statusLabel.failed, itemStyle: { color: statusColor.failed } },
      { value: props.broken, name: statusLabel.broken, itemStyle: { color: statusColor.broken } },
      { value: props.skipped, name: statusLabel.skipped, itemStyle: { color: statusColor.skipped } },
    ].filter(d => d.value > 0),
  }],
}))
</script>

<template>
  <n-card title="测试结果分布" size="small">
    <v-chart :option="option" style="height: 300px" autoresize />
  </n-card>
</template>
