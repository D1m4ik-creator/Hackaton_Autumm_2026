export interface RiskReport {
  totalClients: number
  revenueAtRisk: number
  high: number
  medium: number
  low: number
  no_data: number
  lossExplanation: string
  asOf: string | null
  recalculatedAt: string | null
  version: number
}
