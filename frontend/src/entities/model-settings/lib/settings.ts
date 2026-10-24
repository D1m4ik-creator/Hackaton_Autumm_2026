import { defaultModelSettings } from '../model/defaults'
import type { ModelFeature, ModelSettings } from '../model/types'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function features(value: unknown): ModelFeature[] | null {
  if (!Array.isArray(value) || !value.every((item) => {
    const feature = record(item)
    return typeof feature.id === 'string' && typeof feature.name === 'string' && typeof feature.weight === 'number' && Number.isFinite(feature.weight)
  })) return null
  return value.map((item) => ({ id: item.id, name: item.name, weight: item.weight }))
}

export function readModelSettings(settings: Record<string, unknown>, defaults: Record<string, unknown>): ModelSettings {
  const thresholds = { ...defaultModelSettings.thresholds, ...record(defaults.thresholds), ...record(settings.thresholds) }
  const asOf = settings.asOf === undefined ? defaults.asOf : settings.asOf
  return {
    features: features(settings.features) ?? features(defaults.features) ?? structuredClone(defaultModelSettings.features),
    thresholds: {
      high: typeof thresholds.high === 'number' ? thresholds.high : defaultModelSettings.thresholds.high,
      medium: typeof thresholds.medium === 'number' ? thresholds.medium : defaultModelSettings.thresholds.medium,
    },
    asOf: typeof asOf === 'string' ? asOf : null,
  }
}

export const getWeightSum = (settings: ModelSettings) => settings.features.reduce((sum, feature) => sum + feature.weight, 0)

export function validateModelSettings(settings: ModelSettings): string | null {
  if (settings.features.length === 0) return 'Добавьте хотя бы один признак.'
  if (settings.features.some((feature) => !feature.name.trim() || !Number.isFinite(feature.weight) || feature.weight < 0 || feature.weight > 1)) return 'Для каждого признака укажите название и вес от 0 до 1.'
  if (Math.abs(getWeightSum(settings) - 1) > 0.00001) return 'Сумма весов должна быть равна 1.00.'
  const { high, medium } = settings.thresholds
  if (![high, medium].every((value) => Number.isInteger(value) && value >= 0 && value <= 100)) return 'Пороги должны быть целыми числами от 0 до 100.'
  if (medium >= high) return 'Порог высокого риска должен быть больше порога среднего риска.'
  if (settings.asOf !== null && !Number.isFinite(Date.parse(settings.asOf))) return 'Укажите корректную дату расчёта.'
  return null
}

export function toSettingsPatch(current: ModelSettings, saved: ModelSettings): Record<string, unknown> {
  const patch: Record<string, unknown> = {}
  if (JSON.stringify(current.features) !== JSON.stringify(saved.features)) patch.features = current.features
  const thresholds: Record<string, number> = {}
  for (const level of ['high', 'medium'] as const) {
    if (current.thresholds[level] !== saved.thresholds[level]) thresholds[level] = current.thresholds[level]
  }
  if (Object.keys(thresholds).length) patch.thresholds = thresholds
  if (current.asOf !== saved.asOf) patch.asOf = current.asOf
  return patch
}
