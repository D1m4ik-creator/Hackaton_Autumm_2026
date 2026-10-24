import { defaultModelSettings } from '../model/defaults'
import { MODEL_FEATURES } from '../model/features'
import type { ModelSettings } from '../model/types'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function toNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function readCustomFeatures(settings: Record<string, unknown>): Record<string, { label: string; formula: string }> {
  const raw = record(settings.customFeatures)
  const result: Record<string, { label: string; formula: string }> = {}
  for (const [code, spec] of Object.entries(raw)) {
    const { label, formula } = record(spec)
    if (typeof label === 'string' && typeof formula === 'string') result[code] = { label, formula }
  }
  return result
}

export function readModelSettings(settings: Record<string, unknown>, defaults: Record<string, unknown>): ModelSettings {
  // settings.weights — уже эффективные веса (дефолты + правки пользователя),
  // кроме явно удалённых: их там нет вообще (backend/app/crud/recalc.py:
  // apply_removals), это и отличает «удалён» от «используется дефолт».
  const settingsWeights = record(settings.weights)
  const customFeatures = readCustomFeatures(settings)
  const codes = [...MODEL_FEATURES.map(({ code }) => code), ...Object.keys(customFeatures)]
  const weights: Record<string, number> = {}
  const removed: string[] = []
  for (const code of codes) {
    if (Object.hasOwn(settingsWeights, code)) {
      weights[code] = toNumber(settingsWeights[code], defaultModelSettings.weights[code] ?? 0)
    } else {
      removed.push(code)
    }
  }

  const thresholds = { ...defaultModelSettings.thresholds, ...record(defaults.thresholds), ...record(settings.thresholds) }
  const asOf = settings.asOf === undefined ? defaults.asOf : settings.asOf

  return {
    weights,
    removed,
    customFeatures,
    bias: toNumber(settings.bias, toNumber(defaults.bias, defaultModelSettings.bias)),
    thresholds: {
      high: typeof thresholds.high === 'number' ? thresholds.high : defaultModelSettings.thresholds.high,
      medium: typeof thresholds.medium === 'number' ? thresholds.medium : defaultModelSettings.thresholds.medium,
    },
    expiresSoonDays: toNumber(settings.expiresSoonDays, toNumber(defaults.expiresSoonDays, defaultModelSettings.expiresSoonDays)),
    horizonDays: toNumber(settings.horizonDays, toNumber(defaults.horizonDays, defaultModelSettings.horizonDays)),
    asOf: typeof asOf === 'string' ? asOf : null,
  }
}

export function validateModelSettings(settings: ModelSettings): string | null {
  const codes = [...MODEL_FEATURES.map(({ code }) => code), ...Object.keys(settings.customFeatures)]
  if (codes.some((code) => !settings.removed.includes(code) && !Number.isFinite(settings.weights[code]))) return 'Все веса признаков должны быть числами.'
  if (!Number.isFinite(settings.bias)) return 'Смещение (bias) должно быть числом.'
  const { high, medium } = settings.thresholds
  if (![high, medium].every((value) => Number.isInteger(value) && value >= 0 && value <= 100)) return 'Пороги должны быть целыми числами от 0 до 100.'
  if (medium >= high) return 'Порог высокого риска должен быть больше порога среднего риска.'
  if (!Number.isInteger(settings.expiresSoonDays) || settings.expiresSoonDays <= 0) return '«Скоро истекает, дней» должно быть положительным целым числом.'
  if (!Number.isInteger(settings.horizonDays) || settings.horizonDays <= 0) return 'Горизонт прогноза (дней) должен быть положительным целым числом.'
  if (settings.asOf !== null && !Number.isFinite(Date.parse(settings.asOf))) return 'Укажите корректную дату расчёта.'
  return null
}

export function toSettingsPatch(current: ModelSettings, saved: ModelSettings): Record<string, unknown> {
  const patch: Record<string, unknown> = {}
  if (JSON.stringify(current.weights) !== JSON.stringify(saved.weights)) patch.weights = current.weights
  if (current.bias !== saved.bias) patch.bias = current.bias
  const thresholds: Record<string, number> = {}
  for (const level of ['high', 'medium'] as const) {
    if (current.thresholds[level] !== saved.thresholds[level]) thresholds[level] = current.thresholds[level]
  }
  if (Object.keys(thresholds).length) patch.thresholds = thresholds
  if (current.expiresSoonDays !== saved.expiresSoonDays) patch.expiresSoonDays = current.expiresSoonDays
  if (current.horizonDays !== saved.horizonDays) patch.horizonDays = current.horizonDays
  if (current.asOf !== saved.asOf) patch.asOf = current.asOf
  return patch
}
