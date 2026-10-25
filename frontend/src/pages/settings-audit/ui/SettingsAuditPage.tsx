import { Alert, Button, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { useCallback } from 'react'
import { getSettingsAudit } from '../../../api/audit'
import type { AuditLogEntry } from '../../../api/audit'
import { useApiResource } from '../../../api/useApiResource'
import { formatDateTime } from '../../../shared/lib/format'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import { summarizeAuditDiff } from '../lib/diff'
import './settings-audit.css'

const ACTION_LABELS: Record<AuditLogEntry['action'], string> = { patch: 'Изменение', delete: 'Удаление' }

export function SettingsAuditPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const loadAudit = useCallback(() => getSettingsAudit(1, 100), [])
  const { data, loading, error, reload } = useApiResource(loadAudit)

  const columns: TableColumnsType<AuditLogEntry> = [
    { title: 'Когда', dataIndex: 'createdAt', width: 170, render: formatDateTime },
    { title: 'Кто', key: 'actor', width: 180, render: (_, entry) => <span>{entry.actorLogin} <Tag>{entry.actorRole}</Tag></span> },
    { title: 'Действие', dataIndex: 'action', width: 110, render: (action: AuditLogEntry['action']) => ACTION_LABELS[action] },
    { title: 'Что изменилось', key: 'diff', render: (_, entry) => {
      const lines = summarizeAuditDiff(entry.before, entry.after)
      return <ul className="settings-audit-diff">{lines.length ? lines.map((line) => <li key={line}>{line}</li>) : <li>—</li>}</ul>
    } },
  ]

  return <DashboardShell onSignOut={onSignOut}>
    <header className="settings-audit-heading"><h1>История изменений настроек</h1></header>
    {error && <Alert type="error" title={error} action={<Button onClick={reload}>Повторить</Button>} />}
    <Table<AuditLogEntry>
      rowKey="id"
      columns={columns}
      dataSource={data?.items ?? []}
      loading={loading}
      pagination={false}
      scroll={{ x: 900 }}
      locale={{ emptyText: 'Изменений пока не было' }}
    />
  </DashboardShell>
}
