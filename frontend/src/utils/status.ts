export type Status = 'passed' | 'failed' | 'broken' | 'skipped' | 'unknown' | 'processing' | 'completed'

export const statusColor: Record<string, string> = {
  passed: '#18a058',
  failed: '#d03050',
  broken: '#f0a020',
  skipped: '#909399',
  unknown: '#c0c0c0',
  processing: '#2080f0',
  completed: '#18a058',
}

export const statusLabel: Record<string, string> = {
  passed: '通过',
  failed: '失败',
  broken: '异常',
  skipped: '跳过',
  unknown: '未知',
  processing: '处理中',
  completed: '已完成',
}
