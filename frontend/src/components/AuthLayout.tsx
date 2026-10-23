import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { GradientBlinds } from './GradientBlinds'
import '../styles/auth.css'

interface AuthLayoutProps {
  title: string
  subtitle: string
  switchHint: string
  switchLinkLabel: string
  switchLinkTo: string
  children: ReactNode
}

export function AuthLayout({
  title,
  subtitle,
  switchHint,
  switchLinkLabel,
  switchLinkTo,
  children,
}: AuthLayoutProps) {
  return (
    <div className="auth-layout">
      <aside className="auth-visual">
        <div className="auth-visual__bg">
          <GradientBlinds
            gradientColors={['#050505', '#6b6b6b', '#e8e8e8']}
            angle={15}
            noise={0.15}
            blindCount={20}
            blindMinWidth={40}
            spotlightRadius={1}
            spotlightSoftness={1.1}
            spotlightOpacity={0.85}
            mouseDampening={0.15}
            shineDirection="left"
            mixBlendMode="lighten"
          />
        </div>
        <div className="auth-visual__brand">
          <span className="auth-visual__brand-mark">A</span>
          <span>Проект</span>
        </div>
        <div className="auth-visual__footer">
          <p className="auth-visual__quote">
            «Это приложение сэкономило нам кучу времени и помогло выкатить результат быстрее.»
          </p>
          <p className="auth-visual__wordmark">Hackathon.</p>
        </div>
      </aside>

      <div className="auth-panel">
        <div className="auth-card">
          <h1 className="auth-card__title">{title}</h1>
          <p className="auth-card__subtitle">{subtitle}</p>

          {children}

          <p className="auth-switch">
            {switchHint} <Link to={switchLinkTo}>{switchLinkLabel}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
