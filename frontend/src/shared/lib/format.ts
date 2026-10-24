const integer = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export const formatInteger = (value: number) => integer.format(value)
const money = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const formatEuro = (value: number) => `€${money.format(value)}`
export const formatEuroCents = (cents: number) => `€${money.format(cents / 100)}`
export const formatPercent = (value: number) => `${value.toFixed(1)}%`
export const formatDateTime = (value: string | null) => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '—'
const shortDate = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })
export const formatShortDate = (value: string) => shortDate.format(new Date(value))
