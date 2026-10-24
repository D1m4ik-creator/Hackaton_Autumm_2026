import { Avatar, Tag } from 'antd'
import { riskLabels } from '../../../entities/client'
import type { ClientDetail } from '../../../entities/client'
import { formatEuro, formatEuroCents } from '../../../shared/lib/format'
import './client-profile.css'

export function ClientProfile({ detail }: { detail: ClientDetail }) {
  const { client } = detail
  const initials = client.name.replace(/[«»]/g, '').split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toLocaleUpperCase('ru')

  return (
    <section className="client-profile" aria-labelledby="client-profile-name">
      <div className="client-profile__identity">
        <Avatar size={64} className="client-profile__avatar">{initials}</Avatar>
        <div className="client-profile__identity-text">
          <h1 id="client-profile-name">{client.name}</h1>
          <p>{client.email} · ID #{client.accountId}</p>
        </div>
      </div>
      <div className="client-profile__tags">
        <Tag className="client-profile__risk">{client.risk === 'no_data' ? 'нет оценки' : `${riskLabels[client.risk].toLocaleUpperCase('ru')} РИСК`}</Tag>
      </div>
      <div className="client-profile__divider" />
      <dl className="client-profile__stats">
        <div><dt>Risk-score</dt><dd>{client.score ?? 'нет оценки'}</dd></div>
        <div><dt>Баланс</dt><dd>{formatEuroCents(client.balanceCents)}</dd></div>
        <div><dt>Потери</dt><dd className="client-profile__loss">{formatEuro(client.revenueAtRisk)}</dd></div>
      </dl>
    </section>
  )
}
