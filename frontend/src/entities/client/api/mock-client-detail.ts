import { mockClients } from './mock-clients'
import type { ClientDetail } from '../model/detail-types'

const referenceDetail: Omit<ClientDetail, 'client'> = {
  status: 'prolong_wait',
  reasons: [
    { id: 'payment', title: 'Услуга в «Ожидает оплаты» — 4 из 5 дней', description: 'VPS Pro #4821 не оплачен, через день будет удалена', contribution: 42, tone: 'accent' },
    { id: 'auto-prolong', title: 'Автопродление отключено', description: 'Клиент сам выключил автопродление на ключевой услуге', contribution: 28, tone: 'strong' },
    { id: 'balance', title: 'Баланс ниже стоимости продления', description: '128,40 € на счету против 310 € к списанию', contribution: 18, tone: 'muted' },
    { id: 'activity', title: 'Падение активности пополнений', description: 'Последнее пополнение 46 дней назад, раньше — раз в 2 недели', contribution: 12, tone: 'subtle' },
  ],
  activity: [
    { id: 'reminder', timeLabel: 'Сегодня, 09:12', description: 'Автонапоминание об оплате VPS Pro #4821', highlighted: true },
    { id: 'payment-wait', timeLabel: '4 дня назад', description: 'Услуга перешла в статус «Ожидает оплаты»' },
    { id: 'auto-prolong-off', timeLabel: '5 дней назад', description: 'Клиент отключил автопродление' },
    { id: 'last-payment', timeLabel: '46 дней назад', description: 'Последнее пополнение баланса, €50' },
  ],
  services: [
    { id: '4821', name: 'VPS Pro #4821', status: 'prolong_wait', priceCents: 31000, period: 'month', renewalDescription: 'ожидает оплаты 4-й день', autoProlong: false },
    { id: 'retain-domain', name: 'Домен retain.io', status: 'active', priceCents: 1200, period: 'year', renewalDescription: 'продление через 128 дней', autoProlong: true },
  ],
}

export function getMockClientDetail(accountId: string): ClientDetail | undefined {
  const client = mockClients.find((item) => String(item.accountId) === accountId)
  if (!client) return undefined
  if (client.accountId === 10432) return { client, ...referenceDetail }

  const waitingForPayment = client.risk === 'high'
  const serviceName = `VPS Pro #${client.accountId}`
  return {
    client,
    status: waitingForPayment ? 'prolong_wait' : 'active',
    reasons: [{ id: 'activity', title: waitingForPayment ? 'Снижение активности клиента' : 'Оценка активности клиента', description: client.reason, contribution: 100, tone: waitingForPayment ? 'accent' : 'muted' }],
    activity: [
      { id: 'review', timeLabel: 'Сегодня, 09:12', description: 'Обновлена оценка риска клиента', highlighted: true },
      { id: 'last-activity', timeLabel: new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC' }).format(new Date(client.lastActivity)), description: 'Последняя активность клиента' },
    ],
    services: [{ id: String(client.accountId), name: serviceName, status: waitingForPayment ? 'prolong_wait' : 'active', priceCents: waitingForPayment ? 31000 : 1200, period: 'month', renewalDescription: waitingForPayment ? 'ожидает оплаты 4-й день' : 'продление через 14 дней', autoProlong: !waitingForPayment }],
  }
}
