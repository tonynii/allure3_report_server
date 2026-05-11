import client from './client'

export interface DashboardProject {
  key: string
  name: string
  description: string | null
  runs_count: number
  max_runs: number
  latest_run: {
    id: string | null
    status: string | null
    passed: number
    failed: number
    broken: number
    skipped: number
    total: number
    duration_ms: number | null
    created_at: string | null
  } | null
}

export interface RecentRun {
  id: string
  project_key: string
  project_name: string
  status: string
  passed: number
  failed: number
  broken: number
  skipped: number
  total: number
  duration_ms: number | null
  created_at: string | null
}

export interface DashboardData {
  project_count: number
  total_runs: number
  overall_pass_rate: number
  projects: DashboardProject[]
  recent_runs: RecentRun[]
}

export const getDashboard = () => client.get<DashboardData>('/api/dashboard')

export interface SettingsProject {
  key: string
  name: string
  description: string | null
  runs_count: number
  max_runs: number
  storage_bytes: number
  storage_human: string
  created_at: string | null
}

export interface SettingsData {
  data_dir: string
  default_max_runs: number
  allure_version: string
  projects: SettingsProject[]
}

export const getSettings = () => client.get<SettingsData>('/api/settings')
