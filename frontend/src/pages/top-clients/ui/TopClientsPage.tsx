import { useRiskReportStore } from '../../../entities/risk-report'
import { ClientRiskFilters } from '../../../features/filter-clients'
import { formatInteger } from '../../../shared/lib/format'
import { ClientRiskTable } from '../../../widgets/client-risk-table'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './top-clients.css'

export function TopClientsPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const totalClients = useRiskReportStore((state) => state.report.totalClients)

  return (
    <DashboardShell className="top-clients-page" onSignOut={onSignOut}>
      <header className="top-clients-heading">
        <h1>Клиенты под риском</h1>
        <p>{formatInteger(totalClients)} клиента · сортировка по любому столбцу</p>
      </header>
      <ClientRiskFilters />
      <ClientRiskTable />
    </DashboardShell>
  )
}
