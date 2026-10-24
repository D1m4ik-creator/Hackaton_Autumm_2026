import { Tag } from 'antd'
import type { ClientService } from '../../../entities/client'
import { formatDateTime, formatEuroCents } from '../../../shared/lib/format'
import './client-services.css'

const periods: Record<string, string> = { hour: 'час', week: 'нед', month: 'мес', quarter_year: 'квартал', half_year: 'полгода', year: 'год' }

export function ClientServices({ services }: { services: ClientService[] }) {
  return (
    <section className="client-services client-detail-card" aria-labelledby="client-services-title">
      <h2 id="client-services-title">Услуги клиента</h2>
      {services.length === 0 && <p>Услуг нет</p>}
      <ul className="client-services__list">
        {services.map((service) => <li key={service.id}>
          <div className="client-services__header">
            <h3>{service.name}</h3>
            <Tag className={`client-services__status client-services__status--${service.status}`}>{service.status}</Tag>
          </div>
          <p className="client-services__price">{formatEuroCents(service.priceCents)} / {periods[service.period] ?? service.period} · до {formatDateTime(service.expiresAt)}</p>
          <p className="client-services__auto-prolong">Автопродление: {service.autoProlong ? 'вкл' : 'выкл'}</p>
        </li>)}
      </ul>
    </section>
  )
}
