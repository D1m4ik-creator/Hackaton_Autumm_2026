import type { ClientRiskReason } from '../../../entities/client'
import './client-risk-reasons.css'

export function ClientRiskReasons({ reasons }: { reasons: ClientRiskReason[] }) {
  return (
    <section className="client-risk-reasons client-detail-card" aria-labelledby="client-risk-reasons-title">
      <h2 id="client-risk-reasons-title">Причины риска</h2>
      {reasons.length === 0 && <p>Причины оценки отсутствуют</p>}
      <ol className="client-risk-reasons__list">
        {reasons.map((reason) => <li key={reason.id}>
          <p className="client-risk-reasons__text">{reason.title}</p>
        </li>)}
      </ol>
    </section>
  )
}
