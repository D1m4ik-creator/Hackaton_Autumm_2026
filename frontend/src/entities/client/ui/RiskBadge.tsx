import { Tag } from 'antd'
import { riskLabels } from '../model/types'
import type { RiskLevel } from '../model/types'
import './client.css'

export function RiskBadge({ level }: { level: RiskLevel }) {
  return <Tag className={`risk-badge risk-badge--${level}`}>{riskLabels[level]}</Tag>
}
