import { Progress } from 'antd'
import { useRiskReportStore } from '../../../entities/risk-report'
import { riskLabels } from '../../../entities/client'
import { BentoCard } from '../../../shared/ui/bento-card'

export function RiskTrend() {
  const report = useRiskReportStore((state) => state.report)

  return (
    <BentoCard className="risk-trend" label="Распределение клиентов по риску">
      <div className="risk-trend__header">
        <h2>Распределение клиентов по риску</h2>
      </div>
      <div className="risk-distribution">
        {(['high', 'medium', 'low', 'no_data'] as const).map((level) => <div key={level}>
          <span>{riskLabels[level]}: {report[level]}</span>
          <Progress percent={report.totalClients ? report[level] / report.totalClients * 100 : 0} showInfo={false} strokeColor="var(--dashboard-accent-bright)" />
        </div>)}
      </div>
    </BentoCard>
  )
}
