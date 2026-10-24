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
// Удаляет вес признака из сохранённых настроек — признак перестаёт участвовать
// в скоринге (не сбрасывается на дефолт, а полностью выключается; backend/app/crud/model_settings.py)
export const deleteModelWeight = (code: string) => request<ModelSettingsResponse>(`/model/settings/weights/${encodeURIComponent(code)}`, { method: 'DELETE' })
// Удаляет пользовательскую метрику по формуле целиком (admin/superadmin, app/ml/features/custom.py)
export const deleteCustomFeature = (code: string) => request<ModelSettingsResponse>(`/model/settings/customFeatures/${encodeURIComponent(code)}`, { method: 'DELETE' })
