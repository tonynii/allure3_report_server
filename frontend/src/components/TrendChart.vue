<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { statusColor } from '../utils/status'
import { formatTime } from '../utils/format'

use([LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

export interface TrendPoint {
  timestamp: string
  passed: number
  failed: number
  total: number
}

const props = defineProps<{
  data: TrendPoint[]
}>()

const option = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  grid: { left: 50, right: 20, top: 20, bottom: 40 },
  xAxis: {
    type: 'category' as const,
    data: props.data.map(d => formatTime(d.timestamp)),
    axisLabel: { rotate: 30, fontSize: 10 },
  },
  yAxis: { type: 'value' as const },
  series: [
    { name: '通过', type: 'line' as const, data: props.data.map(d => d.passed), lineStyle: { color: statusColor.passed }, itemStyle: { color: statusColor.passed }, smooth: true },
    { name: '失败', type: 'line' as const, data: props.data.map(d => d.failed), lineStyle: { color: statusColor.failed }, itemStyle: { color: statusColor.failed }, smooth: true },
    { name: '总计', type: 'line' as const, data: props.data.map(d => d.total), lineStyle: { color: statusColor.processing }, itemStyle: { color: statusColor.processing }, smooth: true },
  ],
}))
</script>

<template>
  <n-card title="历史趋势" size="small">
    <v-chart :option="option" style="height: 300px" autoresize />
  </n-card>
</template>
