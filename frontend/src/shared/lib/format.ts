const integer = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export const formatInteger = (value: number) => integer.format(value)
const money = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const formatEuro = (value: number) => `€${money.format(value)}`
export const formatEuroCents = (cents: number) => `€${(cents / 100).toFixed(2)}`
export const formatPercent = (value: number) => `${value.toFixed(1)}%`
export const formatDateTime = (value: string | null) => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '—'
