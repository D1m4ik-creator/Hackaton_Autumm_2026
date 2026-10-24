import { DashboardShell } from '../../../widgets/dashboard-shell'
import { PriorityClients } from '../../../widgets/priority-clients'
import { AccountSummary, RiskSummary } from '../../../widgets/risk-summary'
import { RiskTrend } from '../../../widgets/risk-trend'
import './dashboard.css'

export function DashboardPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  return (
    <DashboardShell onSignOut={onSignOut}>
      <header className="dashboard-heading">
        <div>
          <h1>Обзор рисков оттока</h1>
          <p>Обновляется в реальном времени · пересчёт risk-score каждую ночь</p>
        </div>
      </header>
      <div className="dashboard-grid">
        <AccountSummary />
        <RiskSummary level="high" />
        <PriorityClients />
        <RiskSummary level="medium" />
        <RiskSummary level="low" />
        <RiskTrend />
      </div>
    </DashboardShell>
  )
}
