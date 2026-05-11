import client from './client'

export interface CompareColumn {
  run_id: string
  project: string
  branch: string
  label: string
  total: number
  passed: number
  failed: number
}

export interface CompareResult {
  status: string
  duration_ms: number | null
  error_message: string | null
  labels: { name: string; value: string }[] | null
}

export interface CompareTest {
  historyId: string
  name: string
  fullName: string
  labels: { name: string; value: string }[] | null
  results: Record<string, CompareResult>
  summary: string
}

export interface CompareRequest {
  runs: { project: string; run: string }[]
  status_change_only: boolean
  keyword: string
}

export interface CompareResponse {
  error?: string
  columns: CompareColumn[]
  summary: { all_pass: number; all_fail: number; mixed: number; flaky: number }
  tests: CompareTest[]
}

export const compareRuns = (data: CompareRequest) =>
  client.post<CompareResponse>('/api/compare', data)
