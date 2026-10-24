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

export function filterClientsByRisk(clients: Client[], risk: RiskLevel | 'all'): Client[] {
  return clients.filter((client) => risk === 'all' || client.risk === risk)
}

export function sortClients(clients: Client[], sortField: ClientSortField | null, sortOrder: ClientSortOrder): Client[] {
  if (!sortField || !sortOrder) return clients

  return [...clients].sort((a, b) => {
    const comparison = sortField === 'name'
      ? `${a.name} ${a.email}`.localeCompare(`${b.name} ${b.email}`, 'ru')
      : a[sortField] - b[sortField]
    return sortOrder === 'ascend' ? comparison : -comparison
  })
}

export function selectVisibleClients(clients: Client[], filters: Pick<ClientFiltersState, 'risk' | 'sortField' | 'sortOrder'>): Client[] {
  return sortClients(filterClientsByRisk(clients, filters.risk), filters.sortField, filters.sortOrder)
}
