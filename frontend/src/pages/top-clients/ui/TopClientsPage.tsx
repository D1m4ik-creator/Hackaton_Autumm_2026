import { useEffect } from 'react'
import { useRiskReportStore } from '../../../entities/risk-report'
import { ClientRiskFilters, useClientFiltersStore } from '../../../features/filter-clients'
import { formatInteger } from '../../../shared/lib/format'
import { ClientRiskTable } from '../../../widgets/client-risk-table'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './top-clients.css'

export function TopClientsPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const totalClients = useRiskReportStore((state) => state.report.totalClients)

  // Фильтр по риску — это состояние конкретного визита на страницу (например,
  // клика по карточке риска на дашборде), а не постоянная настройка: без
  // сброса при уходе со страницы следующий заход через сайдбар показывал бы
  // список всё ещё отфильтрованным с прошлого раза.
  useEffect(() => () => useClientFiltersStore.getState().setRisk('all'), [])

  return (
    <DashboardShell className="top-clients-page" onSignOut={onSignOut}>
      <header className="top-clients-heading">
        <h1>Клиенты под риском</h1>
        <p>Всего клиентов: {formatInteger(totalClients)} · сортировка по любому столбцу</p>
      </header>
      <ClientRiskFilters />
      <ClientRiskTable />
    </DashboardShell>
  )
}
