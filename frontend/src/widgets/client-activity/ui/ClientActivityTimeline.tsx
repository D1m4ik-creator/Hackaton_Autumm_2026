import type { ClientDetail } from '../../../entities/client'
import { formatDateTime } from '../../../shared/lib/format'
import './client-activity.css'

const time = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })
const relativeTime = new Intl.RelativeTimeFormat('ru-RU', { numeric: 'always' })
const calendarDay = (date: Date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())

function activityTimeLabel(value: string) {
  const date = new Date(value)
  const daysAgo = Math.round((calendarDay(new Date()) - calendarDay(date)) / 86_400_000)
  if (daysAgo === 0) return `Сегодня, ${time.format(date)}`
  if (daysAgo > 0) return relativeTime.format(-daysAgo, 'day')
  return formatDateTime(value)
}

export function ClientActivityTimeline({ detail }: { detail: ClientDetail }) {
  const items = [
    ...(detail.calculatedAt ? [{
      id: 'calculation', occurredAt: detail.calculatedAt, description: 'Обновлена оценка риска клиента',
    }] : []),
    ...detail.services.map((service) => ({
      id: `service-created-${service.id}`, occurredAt: service.createdAt, description: `Создана услуга «${service.name}»`,
    })),
  ]
    .filter((item) => Number.isFinite(Date.parse(item.occurredAt)))
    .sort((left, right) => Date.parse(right.occurredAt) - Date.parse(left.occurredAt))
    .slice(0, 4)

  return (
    <section className="client-activity client-detail-card" aria-labelledby="client-activity-title">
      <h2 id="client-activity-title">Активность</h2>
      <ol className="client-activity__list">
        {items.map((item, index) => <li key={item.id} className={index === 0 ? 'client-activity__item--highlighted' : ''}>
          <p className="client-activity__time">{activityTimeLabel(item.occurredAt)}</p>
          <p className="client-activity__description">{item.description}</p>
        </li>)}
      </ol>
      {items.length === 0 && <p className="client-activity__empty">Нет событий активности</p>}
    </section>
  )
}
