import { Button } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { mockPriorityClients, RiskBadge } from '../../../entities/client'
import { formatEuro } from '../../../shared/lib/format'
import { BentoCard } from '../../../shared/ui/bento-card'

export function PriorityClients() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const clientsPath = pathname === '/' ? '/app/clients' : '/clients'

  return (
    <BentoCard className="priority-clients" label="Клиенты, которым нужно внимание">
      <div className="priority-clients__header">
        <h2>Клиенты, которым нужно внимание</h2>
        <Button type="text" className="see-all" onClick={() => navigate(clientsPath)}>Все →</Button>
      </div>
      <ul className="priority-clients__list">
        {mockPriorityClients.map((client) => (
          <li key={client.id}>
            <button className="priority-client" onClick={() => navigate(`${clientsPath}/${client.accountId}`)} aria-label={`Открыть клиента ${client.name}`}>
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
