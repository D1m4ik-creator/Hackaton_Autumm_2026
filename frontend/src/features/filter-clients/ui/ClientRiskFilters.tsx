import { Button } from 'antd'
import { riskLabels } from '../../../entities/client'
import type { RiskLevel } from '../../../entities/client'
import { useClientFiltersStore } from '../model/store'
import './client-risk-filters.css'

const filters: { value: RiskLevel | 'all'; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'high', label: riskLabels.high },
  { value: 'medium', label: riskLabels.medium },
  { value: 'low', label: riskLabels.low },
]

export function ClientRiskFilters() {
  const risk = useClientFiltersStore((state) => state.risk)
  const setRisk = useClientFiltersStore((state) => state.setRisk)

  return (
    <div className="client-risk-filters" role="group" aria-label="Фильтр по уровню риска">
      {filters.map((filter) => <Button key={filter.value} className={`client-risk-filter ${risk === filter.value ? 'client-risk-filter--active' : ''}`} aria-pressed={risk === filter.value} onClick={() => setRisk(filter.value)}>{filter.label}</Button>)}
    </div>
  )
}
