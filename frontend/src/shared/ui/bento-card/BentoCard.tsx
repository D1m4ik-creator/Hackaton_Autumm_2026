import { Card } from 'antd'
import type { ReactNode } from 'react'

interface BentoCardProps {
  className?: string
  children: ReactNode
  label: string
}

export function BentoCard({ className = '', children, label }: BentoCardProps) {
  return (
    <section aria-label={label} className={`bento-section ${className}`}>
      <Card className="bento-card">{children}</Card>
    </section>
  )
}
