import { Alert, Button, Empty, Spin } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { RiskBadge } from '../../../entities/client'
import { getCustomers } from '../../../api/customers'
import { useApiResource } from '../../../api/useApiResource'
import { clientDetailPath, clientsPath as resolveClientsPath } from '../../../shared/lib/app-paths'
import { formatEuro } from '../../../shared/lib/format'
import { BentoCard } from '../../../shared/ui/bento-card'

const loadPriorityClients = () => getCustomers({ sort: 'riskScore', order: 'desc', pageSize: 4 })

export function PriorityClients() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const clientsPath = resolveClientsPath(pathname)
  const { data, loading, error, reload } = useApiResource(loadPriorityClients)

  return (
    <BentoCard className="priority-clients" label="Клиенты, которым нужно внимание">
      <div className="priority-clients__header">
        <h2>Клиенты, которым нужно внимание</h2>
        <Button type="text" className="see-all" onClick={() => navigate(clientsPath)}>Все →</Button>
      </div>
      {error && <Alert type="error" title={error} action={<Button onClick={reload}>Повторить</Button>} />}
      {loading && !data && <Spin />}
      {!loading && !error && data?.items.length === 0 && <Empty description="Клиентов пока нет" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      <ul className="priority-clients__list">
        {data?.items.map((client) => (
          <li key={client.id}>
            <button className="priority-client" onClick={() => navigate(clientDetailPath(pathname, client.accountId))} aria-label={`Открыть клиента ${client.name}`}>
              <span className="client-cell"><strong>{client.name}</strong><span>{client.email}</span></span>
              <RiskBadge level={client.risk} />
              <span className="priority-client__revenue">{formatEuro(client.revenueAtRisk)}</span>
            </button>
          </li>
        ))}
      </ul>
    </BentoCard>
  )
}
