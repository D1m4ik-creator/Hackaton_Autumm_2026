import { request } from './client'

export interface ChurnTrendBucket {
  periodStart: string
  periodEnd: string
  isForecast: boolean
  expiredServices: number
  churnedServices: number
}

export interface ChurnTrend {
  buckets: ChurnTrendBucket[]
  atRiskServices: number
  generatedAt: string
}

export function getChurnTrend(weeksBack = 8, weeksForward = 8): Promise<ChurnTrend> {
  return request('/analytics/churn-trend', { params: { weeksBack, weeksForward } })
}
