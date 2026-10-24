import { create } from 'zustand'
import { mockReport, mockRiskSeries } from '../api/mock-report'
import type { ReportPeriod, RiskReport } from './types'

interface RiskReportState {
  report: RiskReport
  period: ReportPeriod
  setPeriod: (period: ReportPeriod) => void
}

export const useRiskReportStore = create<RiskReportState>()((set) => ({
  report: { ...mockReport, dailyRisk: mockRiskSeries.week },
  period: 'week',
  setPeriod: (period) => set((state) => ({
    period,
    report: { ...state.report, dailyRisk: mockRiskSeries[period] },
  })),
}))
