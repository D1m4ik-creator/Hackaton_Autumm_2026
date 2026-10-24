import type { ClientDetail } from '../../../entities/client'
import { formatDateTime, formatEuroCents } from '../../../shared/lib/format'
import './client-activity.css'

export function ClientActivityTimeline({ detail }: { detail: ClientDetail }) {
  return (
    <section className="client-activity client-detail-card" aria-labelledby="client-activity-title">
      <h2 id="client-activity-title">Транзакции и расчёт</h2>
      <dl className="client-activity__list">
        <div><dt>Всего транзакций</dt><dd>{detail.transactions.total}</dd></div>
        <div><dt>Выполнено / не выполнено</dt><dd>{detail.transactions.performed} / {detail.transactions.notPerformed}</dd></div>
        <div><dt>Пополнения</dt><dd>{formatEuroCents(detail.client.totalReplenishedCents)}</dd></div>
        <div><dt>Данные на</dt><dd>{formatDateTime(detail.asOf)}</dd></div>
        <div><dt>Пересчёт</dt><dd>{formatDateTime(detail.calculatedAt)}</dd></div>
      </dl>
    </section>
  )
}
