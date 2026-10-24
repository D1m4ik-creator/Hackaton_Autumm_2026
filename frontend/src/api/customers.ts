import { request } from './client'
import type { Client, ClientDetail, ClientRiskReason, RiskLevel } from '../entities/client'
import { formatShortDate } from '../shared/lib/format'

interface Customer {
  id: number
  email: string
  balance: number
  totalReplenished: number
  riskScore: number | null
  level: RiskLevel
  expectedLossCents: number
  reasonShort: string
}

interface CustomerCardService {
  id: number
  name: string
  status: string
  price: number
  autoProlong: boolean
  paymentTerm: string
  createdAt: string
  expiresAt: string
}

interface CustomerCardTransactions {
  total: number
  performed: number
  notPerformed: number
}

interface CustomerCard extends Customer {
  withdrawBalance: number
  bonusBalance: number
  bonusState: string
  reasons: { code: string; text: string }[]
  // details.contributions — вклад каждого признака (вес × значение) из модели
  // (app/ml/churn_model.py): используем только для признаков, уже отфильтрованных
  // бэком в reasons[] — там нет защитных факторов вроде sufficient_funds.
  details: { contributions?: Record<string, number> }
  services: CustomerCardService[]
  transactions: CustomerCardTransactions
  asOf: string | null
  calculatedAt: string | null
}

// Порядок = заметность полосы: первая (самый большой вклад) — акцентная,
// дальше темнее к бледнее. Выход за 4 причины — все последующие «subtle».
const REASON_TONES: ClientRiskReason['tone'][] = ['accent', 'strong', 'muted', 'subtle']

// Короткая подпись под причиной — по факту из services/transactions этого же
// клиента, не выдумка: для каждого кода признака модели (app/ml/churn_model.py)
// находим конкретную услугу или цифру, которая его объясняет.
function describeReason(code: string, services: CustomerCardService[], transactions: CustomerCardTransactions, balanceCents: number): string {
  switch (code) {
    case 'has_prolong_wait': {
      const service = services.find((s) => s.status === 'prolong_wait')
      return service ? `Услуга «${service.name}» ожидает продления` : 'Есть услуга в статусе «Ожидает продления»'
    }
    case 'prolong_wait_without_funds': {
      const service = services.find((s) => s.status === 'prolong_wait')
      return service
        ? `${(balanceCents / 100).toFixed(2)} € на счету против ${(service.price / 100).toFixed(2)} € к списанию`
        : 'На счету не хватает средств для услуги, ожидающей оплаты'
    }
    case 'failed_payment_ratio':
      return transactions.total ? `${transactions.notPerformed} из ${transactions.total} последних платежей не прошли` : 'Есть неуспешные платежи'
    case 'balance_deficit':
      return 'Баланса не хватит на ближайшие продления услуг'
    case 'autoprolong_off_ratio': {
      const live = services.filter((s) => s.status === 'active' || s.status === 'prolong_wait')
      const off = live.filter((s) => !s.autoProlong).length
      return live.length ? `У ${off} из ${live.length} активных услуг выключено автопродление` : 'Автопродление отключено на части услуг'
    }
    case 'expires_soon_no_autoprolong': {
      const service = services.filter((s) => !s.autoProlong).sort((a, b) => a.expiresAt.localeCompare(b.expiresAt))[0]
      return service ? `Услуга «${service.name}» истекает ${formatShortDate(service.expiresAt)}, автопродление выключено` : 'Скоро истекает услуга без автопродления'
    }
    case 'suspended_ratio': {
      const suspended = services.filter((s) => s.status === 'suspended').length
      return suspended ? `${suspended} из ${services.length} услуг приостановлены` : 'Часть услуг приостановлена'
    }
    case 'deleted_blocked_ratio': {
      const gone = services.filter((s) => s.status === 'deleted' || s.status === 'blocked').length
      return gone ? `Ранее удалено или заблокировано ${gone} из ${services.length} услуг` : 'Раньше удалял или терял услуги'
    }
    default:
      return ''
  }
}

function buildReasons(result: CustomerCard): ClientRiskReason[] {
  const contributions = result.details.contributions ?? {}
  const weighted = result.reasons.map((reason) => ({ reason, contribution: Math.max(contributions[reason.code] ?? 0, 0) }))
  const total = weighted.reduce((sum, { contribution }) => sum + contribution, 0)

  return weighted.map(({ reason, contribution }, index) => ({
    id: `${reason.code}-${index}`,
    title: reason.text,
    description: describeReason(reason.code, result.services, result.transactions, result.balance),
    contribution: total > 0 ? Math.round((contribution / total) * 100) : 0,
    tone: REASON_TONES[index] ?? 'subtle',
  }))
}

export type CustomerSort = 'id' | 'email' | 'balance' | 'totalReplenished' | 'riskScore' | 'expectedLossCents'
export interface CustomerQuery {
  level?: RiskLevel
  search?: string
  sort?: CustomerSort
  order?: 'asc' | 'desc'
  page?: number
  pageSize?: number
}

function toClient(customer: Customer): Client {
  return {
    id: String(customer.id), accountId: customer.id, name: `Клиент #${customer.id}`,
    email: customer.email, balanceCents: customer.balance, totalReplenishedCents: customer.totalReplenished,
    risk: customer.level, score: customer.riskScore, revenueAtRisk: customer.expectedLossCents / 100,
    reason: customer.reasonShort,
  }
}

export async function getCustomers(query: CustomerQuery = {}) {
  const result = await request<{ items: Customer[]; total: number; page: number; pageSize: number }>('/customers', { params: { ...query } })
  return { ...result, items: result.items.map(toClient) }
}

export async function getCustomer(id: string): Promise<ClientDetail> {
  const result = await request<CustomerCard>(`/customers/${encodeURIComponent(id)}`)
  return {
    client: toClient(result),
    reasons: buildReasons(result),
    services: result.services.map((service) => ({
      id: String(service.id), name: service.name, status: service.status, priceCents: service.price,
      period: service.paymentTerm, autoProlong: service.autoProlong, createdAt: service.createdAt, expiresAt: service.expiresAt,
    })),
    transactions: result.transactions, calculatedAt: result.calculatedAt, asOf: result.asOf,
    withdrawBalanceCents: result.withdrawBalance, bonusBalanceCents: result.bonusBalance,
  }
}
