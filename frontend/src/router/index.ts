import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/DashboardPage.vue'),
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('../views/ProjectsPage.vue'),
    },
    {
      path: '/projects/:key',
      name: 'project-detail',
      component: () => import('../views/ProjectDetail.vue'),
    },
    {
      path: '/projects/:key/runs/:id',
      name: 'run-detail',
      component: () => import('../views/RunDetail.vue'),
    },
    {
      path: '/projects/:key/runs/:runId/tests/:testId',
      name: 'test-detail',
      component: () => import('../views/TestDetail.vue'),
    },
    {
      path: '/projects/:key/reports/latest',
      name: 'report-latest',
      component: () => import('../views/ReportViewer.vue'),
    },
    {
      path: '/projects/:key/reports/:runId',
      name: 'report-run',
      component: () => import('../views/ReportViewer.vue'),
    },
    {
      path: '/tools',
      name: 'tools',
      component: () => import('../views/ToolsPage.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsPage.vue'),
    },
  ],
})

export default router
