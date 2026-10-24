import { Select, Tooltip } from 'antd'
import { useRiskReportStore } from '../../../entities/risk-report'
import { BentoCard } from '../../../shared/ui/bento-card'

const dateFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', timeZone: 'UTC' })

export function RiskTrend() {
  const { report, period, setPeriod } = useRiskReportStore()
  const max = Math.max(...report.dailyRisk.map((point) => point.count), 1)

  return (
    <BentoCard className="risk-trend" label="Новые клиенты под риском, по дням">
      <div className="risk-trend__header">
        <h2>Новые клиенты под риском, по дням</h2>
        <Select aria-label="Период графика" value={period} onChange={setPeriod} variant="borderless" suffixIcon={null} popupMatchSelectWidth={120} options={[
          { value: 'week', label: '7 дней' }, { value: 'month', label: '30 дней' },
        ]} />
      </div>
      <div className="risk-trend__bars" role="list" aria-label={period === 'week' ? 'Наблюдения за последние 7 дней' : 'Наблюдения за последние 30 дней'}>
        {report.dailyRisk.map((point) => {
          const date = dateFormatter.format(new Date(point.date))
          return (
            <Tooltip key={point.date} title={`${date}: ${point.count} клиентов`}>
              <div role="listitem" tabIndex={0} aria-label={`${date}: ${point.count} клиентов`} className={`risk-trend__bar ${point.count === max ? 'risk-trend__bar--peak' : ''}`} style={{ height: `${point.count / max * 100}%` }} />
            </Tooltip>
          )
        })}
      </div>
    </BentoCard>
  )
}
