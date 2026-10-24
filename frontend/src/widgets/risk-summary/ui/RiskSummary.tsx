import { Progress, Tooltip } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useRiskReportStore } from '../../../entities/risk-report'
import { useClientFiltersStore } from '../../../features/filter-clients'
import { formatEuro, formatInteger, formatPercent } from '../../../shared/lib/format'
import { BentoCard } from '../../../shared/ui/bento-card'

export function AccountSummary() {
  const report = useRiskReportStore((state) => state.report)

  return (
    <BentoCard className="account-summary" label="Сводка клиентской базы">
      <p className="stat-label">КЛИЕНТОВ ВСЕГО</p>
      <p className="total-value">{formatInteger(report.totalClients)}</p>
      <div className="summary-divider" />
      <Tooltip title="Потенциальная потеря выручки за следующие 30 дней">
        <p className="stat-label">ПОД УГРОЗОЙ, 30Д</p>
      </Tooltip>
      <p className="revenue-value">{formatEuro(report.revenueAtRisk)}</p>
    </BentoCard>
  )
}

export function RiskSummary({ level }: { level: 'high' | 'medium' | 'low' }) {
  const report = useRiskReportStore((state) => state.report)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const clientsPath = pathname.startsWith('/app/') ? '/app/clients' : '/clients'
  const count = report[level]
  const percent = count / report.totalClients * 100
  const isHigh = level === 'high'
  const title = { high: 'ВЫСОКИЙ РИСК', medium: 'СРЕДНИЙ РИСК', low: 'НИЗКИЙ РИСК' }[level]
  const color = {
    high: 'var(--dashboard-accent-bright)',
    medium: 'var(--dashboard-ring-medium)',
    low: 'var(--dashboard-ring-low)',
  }[level]
  const angle = percent / 100 * Math.PI * 2

  function openFilteredClients() {
    useClientFiltersStore.getState().setRisk(level)
    navigate(clientsPath)
  }

  return (
    <BentoCard className={`risk-summary risk-summary--${level}`} label={title}>
      <button className="risk-summary__button" onClick={openFilteredClients} aria-label={`${title}: ${count} клиентов. Перейти к списку`}>
        <div className="risk-dial" style={{ width: isHigh ? 170 : 90, height: isHigh ? 170 : 90 }}>
          <Progress className="risk-dial__progress" type="circle" percent={percent} size={isHigh ? 170 : 90} strokeWidth={isHigh ? 17.65 : 20} strokeColor={color} railColor="var(--dashboard-ring-track)" strokeLinecap="butt" showInfo={false} />
          {isHigh && <>
            <span className="risk-dial__value">{formatPercent(percent)}</span>
            <span className="risk-dial__head" style={{ left: `${50 + Math.cos(angle) * 50}%`, top: `${50 + Math.sin(angle) * 50}%` }} />
          </>}
        </div>
        <div className="risk-summary__text">
          <h2>{title}</h2>
          {isHigh ? <p className="risk-summary__sub">{count} клиентов</p> : <>
            <p className="risk-summary__count">{formatInteger(count)}</p>
            <p className="risk-summary__sub">{formatPercent(percent)} базы</p>
          </>}
        </div>
      </button>
    </BentoCard>
  )
}
