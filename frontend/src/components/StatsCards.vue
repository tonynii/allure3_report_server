<script setup lang="ts">
defineProps<{
  total: number
  passed: number
  failed: number
  broken: number
  skipped: number
}>()
</script>

<template>
  <n-grid :cols="5" :x-gap="12">
    <n-gi>
      <n-card size="small" :bordered="false" style="background: #f0f9eb">
        <n-statistic label="Total" :value="total" />
      </n-card>
    </n-gi>
    <n-gi>
      <n-card size="small" :bordered="false" style="background: #f0f9eb">
        <n-statistic label="Passed">
          <span style="color: #18a058; font-size: 28px; font-weight: bold">{{ passed }}</span>
        </n-statistic>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card size="small" :bordered="false" :style="{ background: failed > 0 ? '#fef0f0' : '#fafafa' }">
        <n-statistic label="Failed">
          <span :style="{ color: '#d03050', fontSize: '28px', fontWeight: 'bold' }">{{ failed }}</span>
        </n-statistic>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card size="small" :bordered="false" :style="{ background: broken > 0 ? '#fdf6ec' : '#fafafa' }">
        <n-statistic label="Broken">
          <span :style="{ color: '#f0a020', fontSize: '28px', fontWeight: 'bold' }">{{ broken }}</span>
        </n-statistic>
      </n-card>
    </n-gi>
    <n-gi>
      <n-card size="small" :bordered="false" style="background: #fafafa">
        <n-statistic label="Skipped">
          <span :style="{ color: '#909399', fontSize: '28px', fontWeight: 'bold' }">{{ skipped }}</span>
        </n-statistic>
      </n-card>
    </n-gi>
  </n-grid>
</template>
