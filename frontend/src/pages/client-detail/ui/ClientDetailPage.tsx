import { Result } from 'antd'
import { Link, useParams } from 'react-router-dom'
import { getMockClientDetail } from '../../../entities/client'
import { ThemeToggle } from '../../../features/switch-theme'
import { ClientActivityTimeline } from '../../../widgets/client-activity'
import { ClientProfile } from '../../../widgets/client-profile'
import { ClientRiskReasons } from '../../../widgets/client-risk-reasons'
import { ClientServices } from '../../../widgets/client-services'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './client-detail.css'

export function ClientDetailPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { clientId = '' } = useParams<{ clientId: string }>()
  const detail = getMockClientDetail(clientId)
  const clientsPath = onSignOut ? '/app/clients' : '/clients'

  return (
    <DashboardShell className="client-detail-page" onSignOut={onSignOut}>
      <header className="client-detail-toolbar">
        <Link to={clientsPath} className="client-detail-back">← Все клиенты под риском</Link>
        <ThemeToggle />
      </header>
      {detail ? <div className="client-detail-grid">
        <ClientProfile detail={detail} />
        <ClientActivityTimeline items={detail.activity} />
        <ClientRiskReasons reasons={detail.reasons} />
        <ClientServices services={detail.services} />
      </div> : <Result status="404" title="Клиент не найден" subTitle="Проверьте ID клиента или вернитесь к списку." />}
    </DashboardShell>
  )
}
