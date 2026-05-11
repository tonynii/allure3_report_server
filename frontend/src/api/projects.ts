import client from './client'

export interface Project {
  key: string
  name: string
  description: string | null
  max_runs: number
  runs_count: number
  latest_run_status: string | null
  created_at: string
  updated_at?: string
}

export interface ProjectCreate {
  key: string
  name: string
  description?: string
  max_runs?: number
}

export const listProjects = () => client.get<Project[]>('/api/projects')
export const getProject = (key: string) => client.get<Project>(`/api/projects/${key}`)
export const createProject = (data: ProjectCreate) => client.post<Project>('/api/projects', data)
export const updateProject = (key: string, data: Partial<ProjectCreate>) =>
  client.put<Project>(`/api/projects/${key}`, data)
export const deleteProject = (key: string) => client.delete(`/api/projects/${key}`)
