import type { ModelSettings } from './types'

export const defaultModelSettings: ModelSettings = {
  features: [
    { id: 'prolong_wait', name: 'Ожидает оплаты (prolong_wait)', weight: 0.42 },
    { id: 'autoprolong_off', name: 'Автопродление выключено', weight: 0.28 },
    { id: 'insufficient_balance', name: 'Баланс ниже стоимости продления', weight: 0.18 },
    { id: 'replenishment_drop', name: 'Падение активности пополнений', weight: 0.12 },
  ],
  thresholds: { high: 70, medium: 35 },
}
