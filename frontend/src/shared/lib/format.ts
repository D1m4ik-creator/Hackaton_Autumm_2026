const integer = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export const formatInteger = (value: number) => integer.format(value)
export const formatEuro = (value: number) => `€${integer.format(value)}`
export const formatEuroCents = (cents: number) => `€${(cents / 100).toFixed(2)}`
export const formatPercent = (value: number) => `${value.toFixed(1)}%`
