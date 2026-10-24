export type RiskLevel = 'high' | 'medium' | 'low' | 'no_data'

export interface Client {
  id: string
  accountId: number
  name: string
  email: string
  risk: RiskLevel
  score: number | null
  revenueAtRisk: number
  balanceCents: number
  totalReplenishedCents: number
  reason: string
}

export const riskLabels: Record<RiskLevel, string> = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
  no_data: 'нет оценки',
}
