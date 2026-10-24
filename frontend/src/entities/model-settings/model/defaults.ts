import type { ModelSettings } from './types'

// Запасные значения на случай, пока GET /model/settings ещё не ответил —
// совпадают с дефолтами реальной модели (backend/app/ml/churn_model.py:
// ModelConfig), не выдуманные.
export const defaultModelSettings: ModelSettings = {
  weights: {
    has_prolong_wait: 3,
    prolong_wait_without_funds: 2,
    failed_payment_ratio: 2,
    balance_deficit: 1.5,
    autoprolong_off_ratio: 1.5,
    expires_soon_no_autoprolong: 1.2,
    suspended_ratio: 1,
    deleted_blocked_ratio: 1,
    full_autoprolong_coverage: -1,
    sufficient_funds: -0.8,
    customer_value: 0,
  },
  removed: [],
  bias: -2.5,
  thresholds: { high: 70, medium: 35 },
  expiresSoonDays: 7,
  horizonDays: 30,
  asOf: null,
}
