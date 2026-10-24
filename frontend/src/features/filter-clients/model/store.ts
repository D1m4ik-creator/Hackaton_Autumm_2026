import { create } from 'zustand'
import type { Client, RiskLevel } from '../../../entities/client'

export type ClientSortField = 'accountId' | 'name' | 'balanceCents' | 'totalReplenishedCents' | 'score'
export type ClientSortOrder = 'ascend' | 'descend' | null

interface ClientFiltersState {
  risk: RiskLevel | 'all'
  sortField: ClientSortField | null
  sortOrder: ClientSortOrder
  setRisk: (risk: RiskLevel | 'all') => void
  setSort: (sortField: ClientSortField | null, sortOrder: ClientSortOrder) => void
}

export const useClientFiltersStore = create<ClientFiltersState>()((set) => ({
  risk: 'all',
  sortField: null,
  sortOrder: null,
  setRisk: (risk) => set({ risk }),
  setSort: (sortField, sortOrder) => set({ sortField, sortOrder }),
}))

export function selectVisibleClients(clients: Client[], filters: Pick<ClientFiltersState, 'risk' | 'sortField' | 'sortOrder'>): Client[] {
  const filtered = clients.filter((client) => filters.risk === 'all' || client.risk === filters.risk)
  const { sortField, sortOrder } = filters
  if (!sortField || !sortOrder) return filtered

  return filtered.sort((a, b) => {
    const comparison = sortField === 'name'
      ? `${a.name} ${a.email}`.localeCompare(`${b.name} ${b.email}`, 'ru')
      : a[sortField] - b[sortField]
    return sortOrder === 'ascend' ? comparison : -comparison
  })
}
