<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <n-layout-header bordered style="padding: 0 24px; height: 56px; display: flex; align-items: center">
    <n-space align="center">
      <n-h3 style="margin: 0; cursor: pointer" @click="router.push('/')">
        📊 Allure3 Report Server
      </n-h3>
    </n-space>
    <n-space style="margin-left: auto">
      <n-button text @click="router.push('/')">项目</n-button>
    </n-space>
  </n-layout-header>
</template>
