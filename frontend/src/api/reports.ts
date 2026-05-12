import client from './client'

export interface Run {
  id: string
  project_key: string
  status: string
  branch: string | null
  commit_hash: string | null
  total: number
  passed: number
  failed: number
  broken: number
  skipped: number
  unknown: number
  duration_ms: number | null
  error_message: string | null
  environment: { key: string; value: string }[] | null
  created_at: string
  completed_at: string | null
}

export interface RunDetail extends Run {
  test_results: TestResultSummary[]
}

export interface TestResultSummary {
  id: string
  uuid: string
  history_id: string | null
  full_name: string | null
  name: string
  status: string
  duration_ms: number | null
  labels: { name: string; value: string }[] | null
}

export interface TestResultDetail extends TestResultSummary {
  test_case_id: string | null
  description: string | null
  stage: string | null
  start_time: string | null
  stop_time: string | null
  links: { type: string; name: string; url: string }[] | null
  parameters: { name: string; value: string }[] | null
  status_details: { message?: string; trace?: string; known?: boolean; muted?: boolean; flaky?: boolean } | null
  steps: TestStepSummary[]
  attachments: TestAttachmentSummary[]
}

export interface TestStepSummary {
  id: string
  name: string
  status: string
  duration_ms: number | null
  children: TestStepSummary[]
}

export interface TestAttachmentSummary {
  id: string
  name: string
  source: string
  type: string
  size: number
}

export const uploadResults = (key: string, file: File, branch?: string, commit?: string) => {
  const fd = new FormData()
  fd.append('file', file)
  return client.post<Run>(`/api/projects/${key}/runs`, fd, {
    params: { branch, commit_hash: commit },
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const listRuns = (key: string) => client.get<Run[]>(`/api/projects/${key}/runs`)
export const getRun = (key: string, id: string) => client.get<RunDetail>(`/api/projects/${key}/runs/${id}`)
export const getTestResult = (key: string, runId: string, testId: string) =>
  client.get<TestResultDetail>(`/api/projects/${key}/runs/${runId}/tests/${testId}`)

export const deleteRun = (key: string, id: string) =>
  client.delete(`/api/projects/${key}/runs/${id}`)
