export interface ModelFeatureMeta {
  code: string
  label: string
  hint: string
}

export interface ModelSettings {
  // Ключи — коды признаков модели (app/ml/churn_model.py: ModelConfig.weights),
  // значения — коэффициенты логистической регрессии, не доли 0..1: могут быть
  // любым числом, отрицательные снижают риск (защитные признаки). Коды из
  // removed сюда не входят — они исключены из модели (DELETE .../weights/{code}).
  weights: Record<string, number>
  // Коды признаков, явно исключённых из подсчёта (не просто «вес по умолчанию» —
  // полностью отсутствуют в эффективных настройках, модель их не видит).
  removed: string[]
  bias: number
  thresholds: { high: number; medium: number }
  expiresSoonDays: number
  horizonDays: number
  asOf: string | null
}
