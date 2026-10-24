import type { RiskReport, ReportPeriod } from '../model/types'

export const mockReport: Omit<RiskReport, 'dailyRisk'> = {
  totalClients: 1284,
  revenueAtRisk: 48920,
  high: 187,
  medium: 402,
  low: 695,
}

// Eight observations include the start and end of the seven-day interval in Figma.
export const mockRiskSeries: Record<ReportPeriod, RiskReport['dailyRisk']> = {
  week: [40, 65, 50, 80, 55, 108, 70, 45].map((count, index) => ({
    date: `2026-10-${17 + index}`, count,
  })),
  month: [31, 43, 36, 62, 49, 71, 65, 44, 58, 79, 52, 68, 87, 61, 48, 71, 83, 56, 67, 91, 72, 54, 69, 80, 55, 108, 70, 45, 60, 76].map((count, index) => ({
    date: new Date(Date.UTC(2026, 8, 25 + index)).toISOString().slice(0, 10), count,
  })),
}
