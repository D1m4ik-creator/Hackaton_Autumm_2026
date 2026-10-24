export type RiskLevel = 'high' | 'medium' | 'low'

export interface Client {
  id: string
  accountId: number
  name: string
  email: string
  risk: RiskLevel
  score: number
  revenueAtRisk: number
  balanceCents: number
  totalReplenishedCents: number
  lastActivity: string
  reason: string
}

export const riskLabels: Record<RiskLevel, string> = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
}
