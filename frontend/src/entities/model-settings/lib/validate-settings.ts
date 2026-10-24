import type { ModelSettings } from '../model/types'

export const getWeightSum = (settings: ModelSettings) => settings.features.reduce((sum, feature) => sum + feature.weight, 0)

export function validateModelSettings(settings: ModelSettings): string | null {
  if (settings.features.length === 0) return 'Добавьте хотя бы один признак.'
  if (settings.features.some((feature) => !feature.name.trim() || !Number.isFinite(feature.weight) || feature.weight < 0 || feature.weight > 1)) {
    return 'Для каждого признака укажите название и вес от 0 до 1.'
  }
  if (Math.abs(getWeightSum(settings) - 1) > 0.00001) return 'Сумма весов должна быть равна 1.00.'
  const { high, medium } = settings.thresholds
  if (![high, medium].every((value) => Number.isInteger(value) && value >= 0 && value <= 100)) return 'Пороги должны быть целыми числами от 0 до 100.'
  if (medium >= high) return 'Порог высокого риска должен быть больше порога среднего риска.'
  return null
}

export function isModelSettings(value: unknown): value is ModelSettings {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<ModelSettings>
  if (!Array.isArray(candidate.features) || !candidate.thresholds) return false
  if (!candidate.features.every((feature) => feature && typeof feature.id === 'string' && typeof feature.name === 'string' && typeof feature.weight === 'number')) return false
  return validateModelSettings(candidate as ModelSettings) === null
}
