import { Button, Result, Spin } from 'antd'
import { useCallback } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { getCustomer } from '../../../api/customers'
import { useApiResource } from '../../../api/useApiResource'
import { clientsPath as resolveClientsPath } from '../../../shared/lib/app-paths'
import { ClientActivityTimeline } from '../../../widgets/client-activity'
import { ClientProfile } from '../../../widgets/client-profile'
import { ClientRiskReasons } from '../../../widgets/client-risk-reasons'
import { ClientServices } from '../../../widgets/client-services'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './client-detail.css'

export function ClientDetailPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { clientId = '' } = useParams<{ clientId: string }>()
  const { pathname } = useLocation()
  const loader = useCallback(() => getCustomer(clientId), [clientId])
  const { data: detail, loading, error, reload } = useApiResource(loader)
  const clientsPath = resolveClientsPath(pathname)

  return (
    <DashboardShell className="client-detail-page" onSignOut={onSignOut}>
      <header className="client-detail-toolbar">
        <Link to={clientsPath} className="client-detail-back">← Все клиенты под риском</Link>
      </header>
      {error ? <Result status="error" title="Не удалось загрузить клиента" subTitle={error} extra={<Button onClick={reload}>Повторить</Button>} /> : loading && !detail ? <Spin /> : detail ? <Spin spinning={loading}><div className="client-detail-grid">
        <ClientProfile detail={detail} />
        <ClientActivityTimeline detail={detail} />
        <ClientRiskReasons reasons={detail.reasons} />
        <ClientServices services={detail.services} />
      </div></Spin> : null}
    </DashboardShell>
  )
}
