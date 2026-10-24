import { Progress, Tooltip } from 'antd'
import { riskLabels } from '../model/types'
import type { Client } from '../model/types'
import './client-risk-indicator.css'

const riskColors = { high: '#de2626', medium: '#ff7a00', low: '#ffc76b' }

export function ClientRiskIndicator({ client }: { client: Client }) {
  const label = `${riskLabels[client.risk]} риск · ${client.score}%`

  return (
    <Tooltip title={label}>
      <span className="client-risk-indicator" role="img" aria-label={label} tabIndex={0}>
        <Progress type="circle" percent={client.score} size={40} strokeWidth={9} strokeColor={riskColors[client.risk]} railColor="var(--dashboard-ring-track)" strokeLinecap="round" />
      </span>
    </Tooltip>
  )
}
