import { Alert, Button, Empty } from 'antd'
import { getChurnTrend } from '../../../api/analytics'
import { useApiResource } from '../../../api/useApiResource'
import { formatInteger, formatShortDate } from '../../../shared/lib/format'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './churn-trend.css'

export function ChurnTrendPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { data, loading, error, reload } = useApiResource(getChurnTrend)
  const buckets = data?.buckets ?? []
  const maxChurned = Math.max(1, ...buckets.map((b) => b.churnedServices))
  const forecastChurn = buckets.filter((b) => b.isForecast).reduce((sum, b) => sum + b.churnedServices, 0)

  return (
    <DashboardShell className="churn-trend-page" onSignOut={onSignOut}>
      <header className="churn-trend-heading">
        <h1>График оттока</h1>
        <p>Услуги по неделе истечения срока: факт (уже решилось — продлена или нет) и прогноз (ещё активна, решение впереди)</p>
      </header>

      {error && <Alert type="error" message={error} action={<Button onClick={reload}>Повторить</Button>} />}

      <section className="churn-trend-stats" aria-label="Сводка по оттоку">
        <div className="churn-stat">
          <span className="churn-stat__label">УСЛУГ ПОД РИСКОМ</span>
          <span className="churn-stat__value">{data ? formatInteger(data.atRiskServices) : '—'}</span>
          <span className="churn-stat__hint">активные услуги на аккаунтах с высоким/средним риском</span>
        </div>
        <div className="churn-stat">
          <span className="churn-stat__label">ПРЕДСТОЯЩИЕ НЕПРОДЛЕНИЯ</span>
          <span className="churn-stat__value">{data ? formatInteger(forecastChurn) : '—'}</span>
          <span className="churn-stat__hint">прогноз по ещё активным услугам, срок которых истекает впереди</span>
        </div>
      </section>

      <section className="churn-chart-card" aria-label="График оттока по неделям">
        {!loading && buckets.length === 0
          ? <Empty description="Нет данных за выбранный период" />
          : <>
            <div className="churn-chart__bars" role="img" aria-label="Столбчатая диаграмма оттока по неделям: факт и прогноз">
              {buckets.map((bucket) => {
                const height = Math.round((bucket.churnedServices / maxChurned) * 100)
                return (
                  <div key={bucket.periodStart} className="churn-chart__column">
                    <span className="churn-chart__count">{bucket.churnedServices || ''}</span>
                    <div
                      className={`churn-chart__bar ${bucket.isForecast ? 'churn-chart__bar--forecast' : 'churn-chart__bar--fact'}`}
                      style={{ height: `${Math.max(height, bucket.churnedServices ? 4 : 0)}%` }}
                      title={`${formatShortDate(bucket.periodStart)} – ${formatShortDate(bucket.periodEnd)}: ${bucket.churnedServices} из ${bucket.expiredServices} услуг не продлены ${bucket.isForecast ? '(прогноз)' : '(факт)'}`}
                    />
                    <span className="churn-chart__label">{formatShortDate(bucket.periodStart)}</span>
                  </div>
                )
              })}
            </div>
            <div className="churn-chart__legend">
              <span className="churn-chart__legend-item"><span className="churn-chart__swatch churn-chart__swatch--fact" />Факт</span>
              <span className="churn-chart__legend-item"><span className="churn-chart__swatch churn-chart__swatch--forecast" />Прогноз</span>
            </div>
          </>}
      </section>
    </DashboardShell>
  )
}
