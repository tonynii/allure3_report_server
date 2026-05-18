import { ref } from 'vue'
import { defineStore } from 'pinia'
import { listProjects, getProject, createProject, deleteProject, type Project, type ProjectCreate } from '../api/projects'

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const current = ref<Project | null>(null)
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try {
      const { data } = await listProjects()
      projects.value = data
    } finally {
      loading.value = false
    }
  }

  async function fetch(key: string) {
    const { data } = await getProject(key)
    current.value = data
  }

  async function create(data: ProjectCreate) {
    const { data: p } = await createProject(data)
    projects.value.unshift(p)
    return p
  }

  async function remove(key: string) {
    await deleteProject(key)
    projects.value = projects.value.filter((p: Project) => p.key !== key)
  }

  return { projects, current, loading, fetchAll, fetch, create, remove }
})
