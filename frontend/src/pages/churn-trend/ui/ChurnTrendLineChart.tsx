import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { ChurnTrendBucket } from '../../../api/analytics'
import { formatShortDate } from '../../../shared/lib/format'

interface LinePoint {
  periodStart: string
  isForecast: boolean
  churnedFact: number | null
  churnedForecast: number | null
}

// Разрыв факт/прогноз — две серии, в остальных точках null (recharts рвёт
// линию на null). Последняя фактическая точка дублируется в начало
// прогнозной серии, чтобы линии визуально соединялись на границе недель,
// а не оставляли зазор.
function toLinePoints(buckets: ChurnTrendBucket[]): LinePoint[] {
  const firstForecastIndex = buckets.findIndex((b) => b.isForecast)
  return buckets.map((bucket, index) => ({
    periodStart: bucket.periodStart,
    isForecast: bucket.isForecast,
    churnedFact: bucket.isForecast ? null : bucket.churnedServices,
    churnedForecast:
      bucket.isForecast || index === firstForecastIndex - 1
        ? bucket.churnedServices
        : null,
  }))
}

function ChurnTooltip({ active, payload, label }: TooltipContentProps) {
  if (!active || !payload?.length) return null
  const value = payload.find((p) => typeof p.value === 'number')?.value as number | undefined
  return (
    <div className="churn-line-tooltip">
      <p className="churn-line-tooltip__date">{formatShortDate(String(label))}</p>
      <p className="churn-line-tooltip__value">{value ?? 0} услуг не продлено</p>
    </div>
  )
}

export function ChurnTrendLineChart({ buckets }: { buckets: ChurnTrendBucket[] }) {
  const data = toLinePoints(buckets)

  return (
    <div className="churn-line-chart" role="img" aria-label="Линейный график оттока по неделям: факт и прогноз">
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--dashboard-border)" vertical={false} />
          <XAxis
            dataKey="periodStart"
            tickFormatter={(value: string) => formatShortDate(value)}
            tick={{ fill: 'var(--dashboard-muted)', fontSize: 10 }}
            axisLine={{ stroke: 'var(--dashboard-border)' }}
            tickLine={false}
          />
          <YAxis allowDecimals={false} tick={{ fill: 'var(--dashboard-muted)', fontSize: 10 }} axisLine={false} tickLine={false} width={28} />
          <Tooltip content={(props) => <ChurnTooltip {...props} />} />
          <Line type="monotone" dataKey="churnedFact" stroke="var(--dashboard-accent-bright)" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="churnedForecast" stroke="var(--dashboard-accent-bright)" strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="churn-chart__legend">
        <span className="churn-chart__legend-item"><span className="churn-chart__swatch churn-chart__swatch--fact" />Факт</span>
        <span className="churn-chart__legend-item"><span className="churn-chart__swatch churn-chart__swatch--forecast" />Прогноз</span>
      </div>
    </div>
  )
}
