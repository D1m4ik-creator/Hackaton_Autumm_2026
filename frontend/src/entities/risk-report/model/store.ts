import { create } from 'zustand'
import { request } from '../../../api/client'
import type { RiskReport } from './types'

interface RiskReportState {
  report: RiskReport
  loading: boolean
  error: string | null
  load: () => Promise<void>
  reset: () => void
}

const emptyReport: RiskReport = { totalClients: 0, revenueAtRisk: 0, high: 0, medium: 0, low: 0, no_data: 0, lossExplanation: '', asOf: null, recalculatedAt: null, version: 0 }
let requestId = 0

export const useRiskReportStore = create<RiskReportState>()((set) => ({
  report: emptyReport,
  loading: true,
  error: null,
  reset: () => { requestId++; set({ report: emptyReport, loading: true, error: null }) },
  load: async () => {
    const current = ++requestId
    set({ loading: true, error: null })
    try {
      const summary = await request<{
        customersTotal: number
        byLevel: Record<'high' | 'medium' | 'low' | 'noData', { customers: number; expectedLossCents: number }>
        expectedLossCents: number; lossExplanation: string; asOf: string | null; recalculatedAt: string | null; version: number
      }>('/analytics/summary')
      if (current !== requestId) return
      set({ loading: false, report: {
        totalClients: summary.customersTotal, revenueAtRisk: summary.expectedLossCents / 100,
        high: summary.byLevel.high.customers, medium: summary.byLevel.medium.customers,
        low: summary.byLevel.low.customers, no_data: summary.byLevel.noData.customers,
        lossExplanation: summary.lossExplanation, asOf: summary.asOf, recalculatedAt: summary.recalculatedAt, version: summary.version,
      } })
    } catch (error) {
      if (current === requestId) set({ loading: false, error: error instanceof Error ? error.message : 'Не удалось загрузить сводку' })
    }
  },
}))
