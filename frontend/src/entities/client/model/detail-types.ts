import type { Client } from './types'

export interface ClientRiskReason {
  id: string
  title: string
}

export interface ClientService {
  id: string
  name: string
  status: string
  priceCents: number
  period: string
  createdAt: string
  expiresAt: string
  autoProlong: boolean
}

export interface ClientDetail {
  client: Client
  reasons: ClientRiskReason[]
  services: ClientService[]
  transactions: { total: number; performed: number; notPerformed: number }
  calculatedAt: string | null
  asOf: string | null
  withdrawBalanceCents: number
  bonusBalanceCents: number
}
