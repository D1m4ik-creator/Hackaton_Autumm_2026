import type { ClientActivity } from '../../../entities/client'
import './client-activity.css'

export function ClientActivityTimeline({ items }: { items: ClientActivity[] }) {
  return (
    <section className="client-activity client-detail-card" aria-labelledby="client-activity-title">
      <h2 id="client-activity-title">Активность</h2>
      <ol className="client-activity__list">
        {items.map((item) => <li key={item.id} className={item.highlighted ? 'client-activity__item--highlighted' : ''}>
          <p className="client-activity__time">{item.timeLabel}</p>
          <p className="client-activity__description">{item.description}</p>
        </li>)}
      </ol>
    </section>
  )
}
