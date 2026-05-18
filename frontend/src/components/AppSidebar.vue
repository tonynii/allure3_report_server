<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const menuItems = [
  { label: '📊 看板', key: '/', path: '/' },
  { label: '📁 项目', key: '/projects', path: '/projects' },
  { label: '🔧 工具', key: '/tools', path: '/tools' },
  { label: '⚙️ 配置', key: '/settings', path: '/settings' },
]

function currentKey(): string {
  const p = route.path
  if (p === '/') return '/'
  if (p.startsWith('/tools')) return '/tools'
  if (p.startsWith('/settings')) return '/settings'
  if (p.startsWith('/projects')) return '/projects'
  return '/'
}
</script>

<template>
  <n-layout-sider bordered collapse-mode="width" :collapsed-width="64" :width="180" show-trigger>
    <n-menu
      :value="currentKey()"
      :options="menuItems"
      @update:value="(v: string) => router.push(v)"
    />
    <template #footer>
      <n-text depth="3" style="padding: 12px; display: block; text-align: center; font-size: 12px">
        Allure3 v1.0
      </n-text>
    </template>
  </n-layout-sider>
</template>
