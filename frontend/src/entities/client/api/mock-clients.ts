import type { Client } from '../model/types'

export const mockClients: Client[] = [
  { id: 'CL-001', accountId: 10432, name: 'Иван Петров', email: 'ivan.petrov@mail.ru', risk: 'high', score: 82, revenueAtRisk: 1240, balanceCents: 12840, totalReplenishedCents: 124000, lastActivity: '2026-10-10', reason: 'Услуга ожидает оплаты, автопродление отключено, баланс ниже стоимости продления.' },
  { id: 'CL-002', accountId: 10218, name: 'ООО «Вектор»', email: 'finance@vector.ru', risk: 'high', score: 85, revenueAtRisk: 3860, balanceCents: 0, totalReplenishedCents: 386000, lastActivity: '2026-10-12', reason: 'Отключено автопродление, снизилась частота пополнений.' },
  { id: 'CL-003', accountId: 10877, name: 'Мария Седова', email: 'm.sedova@gmail.com', risk: 'medium', score: 55, revenueAtRisk: 420, balanceCents: 4210, totalReplenishedCents: 42000, lastActivity: '2026-10-19', reason: 'Объём потребления снизился по сравнению с предыдущим месяцем.' },
  { id: 'CL-005', accountId: 11023, name: 'Алексей Никитин', email: 'a.nikitin@corp.io', risk: 'medium', score: 55, revenueAtRisk: 690, balanceCents: 1500, totalReplenishedCents: 69000, lastActivity: '2026-10-18', reason: 'Количество заказов снизилось, остаток на балансе близок к нулю.' },
  { id: 'CL-006', accountId: 10560, name: 'Dark Horse LLC', email: 'billing@darkhorse.io', risk: 'medium', score: 55, revenueAtRisk: 2100, balanceCents: 31000, totalReplenishedCents: 210000, lastActivity: '2026-10-20', reason: 'Сократилось количество заказов за последние 30 дней.' },
  { id: 'CL-004', accountId: 10091, name: 'Ольга Крамер', email: 'o.kramer@yandex.ru', risk: 'low', score: 25, revenueAtRisk: 5400, balanceCents: 98000, totalReplenishedCents: 540000, lastActivity: '2026-10-23', reason: 'Регулярная активность и стабильные платежи.' },
  { id: 'CL-007', accountId: 10734, name: 'Pavel Zotov', email: 'pavel.z@proton.me', risk: 'low', score: 25, revenueAtRisk: 310, balanceCents: 6400, totalReplenishedCents: 31000, lastActivity: '2026-10-22', reason: 'Услуги активны, автопродление включено.' },
  { id: 'CL-008', accountId: 10399, name: 'Nikita Orlov', email: 'n.orlov@mail.ru', risk: 'high', score: 85, revenueAtRisk: 180, balanceCents: 0, totalReplenishedCents: 18000, lastActivity: '2026-10-08', reason: 'Нулевой баланс и отсутствие активности более двух недель.' },
]

const priorityIds = ['CL-001', 'CL-002', 'CL-003', 'CL-004']
export const mockPriorityClients = priorityIds.flatMap((id) => mockClients.filter((client) => client.id === id))
