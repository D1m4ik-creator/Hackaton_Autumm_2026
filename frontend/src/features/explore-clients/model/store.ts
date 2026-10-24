import { create } from 'zustand'
import type { RiskLevel } from '../../../entities/client'

interface ExploreClientsState {
  isOpen: boolean
  query: string
  riskFilter: RiskLevel | 'all'
  selectedClientId: string | null
  openClients: (risk?: RiskLevel) => void
  closeClients: () => void
  setQuery: (query: string) => void
  setRiskFilter: (riskFilter: RiskLevel | 'all') => void
  selectClient: (selectedClientId: string | null) => void
}

export const useExploreClientsStore = create<ExploreClientsState>()((set) => ({
  isOpen: false,
  query: '',
  riskFilter: 'all',
  selectedClientId: null,
  openClients: (riskFilter = undefined) => set({ isOpen: true, riskFilter: riskFilter ?? 'all', query: '', selectedClientId: null }),
  closeClients: () => set({ isOpen: false, selectedClientId: null }),
  setQuery: (query) => set({ query }),
  setRiskFilter: (riskFilter) => set({ riskFilter }),
  selectClient: (selectedClientId) => set({ selectedClientId }),
}))
