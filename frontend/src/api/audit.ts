import { request } from './client'

export interface AuditLogEntry {
  id: number
  actorLogin: string
  actorRole: string
  action: 'patch' | 'delete'
  section: string | null
  before: Record<string, unknown>
  after: Record<string, unknown>
  createdAt: string
}

export interface AuditLogPage {
  items: AuditLogEntry[]
  total: number
  page: number
  pageSize: number
}

export function getSettingsAudit(page = 1, pageSize = 50): Promise<AuditLogPage> {
  return request('/model/settings/audit', { params: { page, pageSize } })
}
