export type ReportPeriod = 'week' | 'month'

export interface RiskReport {
  totalClients: number
  revenueAtRisk: number
  high: number
  medium: number
  low: number
  dailyRisk: { date: string; count: number }[]
}
