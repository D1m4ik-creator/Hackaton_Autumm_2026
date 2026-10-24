import type { ClientRiskReason } from '../../../entities/client'
import './client-risk-reasons.css'

export function ClientRiskReasons({ reasons }: { reasons: ClientRiskReason[] }) {
  return (
    <section className="client-risk-reasons client-detail-card" aria-labelledby="client-risk-reasons-title">
      <h2 id="client-risk-reasons-title">Причины риска</h2>
      {reasons.length === 0 && <p>Причины оценки отсутствуют</p>}
      <ol className="client-risk-reasons__list">
        {reasons.map((reason) => <li key={reason.id}>
          <p className="client-risk-reasons__text">{reason.title}{reason.description && <><br />{reason.description}</>}</p>
          <div className={`client-risk-reasons__bar client-risk-reasons__bar--${reason.tone}`} role="progressbar" aria-label={reason.title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={reason.contribution}>
            <span className="client-risk-reasons__fill" style={{ width: `${reason.contribution}%` }} />
            <span className="client-risk-reasons__percent">{reason.contribution}%</span>
          </div>
        </li>)}
      </ol>
    </section>
  )
}
