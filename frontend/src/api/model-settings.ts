import { request } from './client'

export interface ModelSettingsResponse {
  settings: Record<string, unknown>
  defaults: Record<string, unknown>
  updatedAt: string
  version?: number
  recalculatedAt?: string | null
}

export const getModelSettings = () => request<ModelSettingsResponse>('/model/settings')
export const patchModelSettings = (settings: Record<string, unknown>) => request<ModelSettingsResponse>('/model/settings', { method: 'PATCH', data: settings })
