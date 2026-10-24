import type { Client } from './types'

export type ClientServiceStatus = 'active' | 'prolong_wait'

export interface ClientRiskReason {
  id: string
  title: string
  description: string
  contribution: number
  tone: 'accent' | 'strong' | 'muted' | 'subtle'
}

export interface ClientActivity {
  id: string
  timeLabel: string
  description: string
  highlighted?: boolean
}

export interface ClientService {
  id: string
  name: string
  status: ClientServiceStatus
  priceCents: number
  period: 'month' | 'year'
  renewalDescription: string
  autoProlong: boolean
}

export interface ClientDetail {
  client: Client
  status: ClientServiceStatus
  reasons: ClientRiskReason[]
  activity: ClientActivity[]
  services: ClientService[]
}
