import { Alert, Button, Spin } from 'antd'
import { useRiskReportStore } from '../../../entities/risk-report'
import { formatDateTime } from '../../../shared/lib/format'
import { useEventsStore } from '../../../api/events'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import { PriorityClients } from '../../../widgets/priority-clients'
import { AccountSummary, RiskSummary } from '../../../widgets/risk-summary'
import { RiskTrend } from '../../../widgets/risk-trend'
import './dashboard.css'

export function DashboardPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { report, loading, error, load } = useRiskReportStore()
  const status = useEventsStore((state) => state.status)
  const updates = {
    idle: 'Живые обновления отключены',
    connecting: 'Подключаем обновления…',
    connected: 'Обновляется в реальном времени при пересчёте модели',
    reconnecting: 'Восстанавливаем соединение для обновлений…',
    offline: 'Живые обновления временно недоступны. Повторяем подключение…',
  }[status]
  return (
    <DashboardShell onSignOut={onSignOut}>
      <header className="dashboard-heading">
        <div>
          <h1>Обзор рисков оттока</h1>
          <p role="status" className="dashboard-updates">{updates}</p>
          <p className="dashboard-as-of">Данные на: {formatDateTime(report.asOf)}</p>
          {report.lossExplanation && <p className="dashboard-loss-explanation">{report.lossExplanation}</p>}
        </div>
      </header>
      {error && <Alert type="error" showIcon title="Не удалось загрузить сводку" description={error} action={<Button onClick={() => void load()}>Повторить</Button>} />}
      <Spin spinning={loading}>
        <div className="dashboard-grid">
          <AccountSummary />
          <RiskSummary level="high" />
          <PriorityClients />
          <RiskSummary level="medium" />
          <RiskSummary level="low" />
          <RiskTrend />
        </div>
      </Spin>
    </DashboardShell>
  )
}
