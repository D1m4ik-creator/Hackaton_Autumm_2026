function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function stringify(value: unknown): string {
  if (value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// Короткий человекочитаемый диф верхнего уровня (и один уровень вложенности
// для словарей вроде weights/customFeatures/thresholds) — для полного JSON
// есть разворачиваемая деталь рядом.
export function summarizeAuditDiff(before: Record<string, unknown>, after: Record<string, unknown>): string[] {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)])
  const lines: string[] = []

  for (const key of keys) {
    const beforeValue = before[key]
    const afterValue = after[key]
    if (JSON.stringify(beforeValue) === JSON.stringify(afterValue)) continue

    if (isPlainObject(beforeValue) || isPlainObject(afterValue)) {
      const beforeObj = isPlainObject(beforeValue) ? beforeValue : {}
      const afterObj = isPlainObject(afterValue) ? afterValue : {}
      const subKeys = new Set([...Object.keys(beforeObj), ...Object.keys(afterObj)])
      for (const subKey of subKeys) {
        if (JSON.stringify(beforeObj[subKey]) === JSON.stringify(afterObj[subKey])) continue
        lines.push(`${key}.${subKey}: ${stringify(beforeObj[subKey])} → ${stringify(afterObj[subKey])}`)
      }
    } else {
      lines.push(`${key}: ${stringify(beforeValue)} → ${stringify(afterValue)}`)
    }
  }

  return lines
}
