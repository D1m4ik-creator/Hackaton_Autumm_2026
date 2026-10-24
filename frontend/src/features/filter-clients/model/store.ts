import { create } from 'zustand'
import type { RiskLevel } from '../../../entities/client'
import type { CustomerSort } from '../../../api/customers'

export type ClientSortField = CustomerSort
export type ClientSortOrder = 'ascend' | 'descend' | null

interface ClientFiltersState {
  risk: RiskLevel | 'all'
  sortField: ClientSortField | null
  sortOrder: ClientSortOrder
  search: string
  setRisk: (risk: RiskLevel | 'all') => void
  setSort: (sortField: ClientSortField | null, sortOrder: ClientSortOrder) => void
  setSearch: (search: string) => void
}

export const useClientFiltersStore = create<ClientFiltersState>()((set) => ({
  risk: 'all',
  sortField: 'riskScore',
  sortOrder: 'descend',
  search: '',
  setSearch: (search) => set({ search }),
  setRisk: (risk) => set({ risk }),
  setSort: (sortField, sortOrder) => set({ sortField, sortOrder }),
}))
