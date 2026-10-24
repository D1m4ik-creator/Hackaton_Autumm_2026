const fieldLabels: Record<string, string> = {
  accounts: 'Аккаунты', services: 'Услуги', transactions: 'Транзакции',
  id: 'ID', ownerId: 'ID владельца', serviceId: 'ID услуги', email: 'Email', login: 'Логин', password: 'Пароль',
  balance: 'Баланс', withdrawBalance: 'Баланс для вывода', totalReplenished: 'Пополнения', bonusBalance: 'Бонусный баланс', bonusState: 'Состояние бонусов',
  name: 'Название', status: 'Статус', price: 'Цена', autoProlong: 'Автопродление', autoprolong: 'Автопродление', paymentTerm: 'Период оплаты',
  createdAt: 'Дата создания', expiresAt: 'Дата окончания', performedAt: 'Дата выполнения', amount: 'Сумма', type: 'Тип',
  features: 'Признаки', weight: 'Вес', thresholds: 'Пороги риска', high: 'Высокий риск', medium: 'Средний риск', asOf: 'Дата расчёта',
}

function validationMessage(issue: Record<string, unknown>): string {
  const ctx = issue.ctx && typeof issue.ctx === 'object' ? issue.ctx as Record<string, unknown> : {}
  const loc = Array.isArray(issue.loc) ? issue.loc : []
  const field = loc.at(-1)
  const message = typeof issue.msg === 'string' ? issue.msg.replace(/^Value error, /, '') : ''
  if (/[а-яё]/i.test(message)) return message
  if (field === 'email') return 'Укажите корректный email.'
  switch (issue.type) {
    case 'missing': return 'Обязательное поле.'
    case 'int_parsing': case 'int_type': return 'Ожидается целое число.'
    case 'float_parsing': case 'float_type': return 'Ожидается число.'
    case 'string_type': return 'Ожидается текст.'
    case 'bool_parsing': case 'bool_type': return 'Укажите true или false.'
    case 'string_too_short': return `Минимум ${ctx.min_length} символов.`
    case 'string_too_long': return `Не более ${ctx.max_length} символов.`
    case 'greater_than_equal': return `Значение должно быть не меньше ${ctx.ge}.`
    case 'greater_than': return `Значение должно быть больше ${ctx.gt}.`
    case 'less_than_equal': return `Значение должно быть не больше ${ctx.le}.`
    case 'less_than': return `Значение должно быть меньше ${ctx.lt}.`
    case 'literal_error': return `Допустимые значения: ${ctx.expected ?? 'проверьте формат поля'}.`
    case 'string_pattern_mismatch': return field === 'login' ? 'Используйте латинские буквы, цифры, _, . и -.' : 'Неверный формат значения.'
    case 'json_invalid': return 'Некорректный формат JSON.'
    default: return 'Некорректное значение.'
  }
}

export function formatApiError(status: number, data: unknown, url = ''): string {
  if (status === 403) return 'Недостаточно прав для выполнения этого действия.'
  if (status === 429) return /\/auth\/login(?:[/?]|$)/.test(url)
    ? 'Слишком много попыток входа. Попробуйте позже.'
    : 'Слишком много запросов. Попробуйте позже.'
  const detail = data && typeof data === 'object' && 'detail' in data ? (data as { detail: unknown }).detail : null
  if (Array.isArray(detail)) {
    return detail.map((value: unknown) => {
      if (!value || typeof value !== 'object') return 'Проверьте введённые данные.'
      const issue = value as Record<string, unknown>
      const path = (Array.isArray(issue.loc) ? issue.loc : []).filter((part) => !['body', 'query', 'path'].includes(String(part))).map((part) =>
        typeof part === 'number' ? `запись ${part + 1}` : fieldLabels[String(part)] ?? String(part),
      ).join(' → ')
      return `${path ? `${path}: ` : ''}${validationMessage(issue)}`
    }).join('\n') || 'Проверьте введённые данные.'
  }
  if (typeof detail === 'string' && /[а-яё]/i.test(detail)) return detail
  if (status === 401) return 'Сессия истекла. Войдите снова.'
  if (status === 422) return 'Проверьте введённые данные.'
  if (status === 404) return 'Запрошенные данные не найдены.'
  if (status >= 500) return 'Сервер временно недоступен. Попробуйте позже.'
  return 'Не удалось выполнить запрос. Повторите попытку.'
}
