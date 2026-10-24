import { request } from './client'
import type { Client, ClientDetail, RiskLevel } from '../entities/client'

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

interface CustomerCard extends Customer {
  withdrawBalance: number
  bonusBalance: number
  bonusState: string
  reasons: { code: string; text: string }[]
  details: Record<string, unknown>
  services: { id: number; name: string; status: string; price: number; autoProlong: boolean; paymentTerm: string; createdAt: string; expiresAt: string }[]
  transactions: { total: number; performed: number; notPerformed: number }
  asOf: string | null
  calculatedAt: string | null
}

export type CustomerSort = 'id' | 'email' | 'balance' | 'totalReplenished' | 'riskScore'
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
    reasons: result.reasons.map((reason, index) => ({ id: `${reason.code}-${index}`, title: reason.text })),
    services: result.services.map((service) => ({
      id: String(service.id), name: service.name, status: service.status, priceCents: service.price,
      period: service.paymentTerm, autoProlong: service.autoProlong, expiresAt: service.expiresAt,
    })),
    transactions: result.transactions, calculatedAt: result.calculatedAt, asOf: result.asOf,
    withdrawBalanceCents: result.withdrawBalance, bonusBalanceCents: result.bonusBalance,
  }
}
