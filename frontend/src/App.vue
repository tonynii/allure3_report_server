<script setup lang="ts">
import { zhCN } from 'naive-ui'
</script>

<template>
  <n-config-provider :locale="zhCN" :theme="null">
    <n-message-provider>
      <n-notification-provider>
        <n-layout style="min-height: 100vh">
          <AppHeader />
          <n-layout-content style="padding: 24px 48px">
            <router-view />
          </n-layout-content>
        </n-layout>
      </n-notification-provider>
    </n-message-provider>
  </n-config-provider>
</template>
