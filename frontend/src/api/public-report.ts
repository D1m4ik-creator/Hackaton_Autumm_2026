import { publicHttp } from './publicClient'

export interface PublicSummary {
  customersTotal: number
  byLevel: Record<'high' | 'medium' | 'low' | 'noData', { customers: number; expectedLossCents: number }>
  expectedLossCents: number
  lossExplanation: string
  asOf: string | null
  recalculatedAt: string | null
  version: number
}

export interface PublicCustomerItem {
  id: number
  balance: number
  totalReplenished: number
  riskScore: number | null
  level: 'high' | 'medium' | 'low' | 'no_data'
  expectedLossCents: number
  reasonShort: string
}

export interface PublicCustomerPage {
  items: PublicCustomerItem[]
  total: number
  page: number
  pageSize: number
}

export function getPublicSummary(token: string): Promise<PublicSummary> {
  return publicHttp.get('/public/report/summary', { params: { token } }).then((res) => res.data)
}

export function getPublicCustomers(
  token: string,
  query: { sort?: string; order?: 'asc' | 'desc'; page?: number; pageSize?: number } = {},
): Promise<PublicCustomerPage> {
  return publicHttp.get('/public/report/customers', { params: { token, ...query } }).then((res) => res.data)
}
