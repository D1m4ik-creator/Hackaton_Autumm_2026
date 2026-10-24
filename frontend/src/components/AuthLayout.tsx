import type { ReactNode } from 'react'
import { GradientBlinds } from './GradientBlinds'
import '../styles/auth.css'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
}

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="auth-layout">
      <aside className="auth-visual">
        <div className="auth-visual__bg">
          <GradientBlinds
            gradientColors={['#120f0c', '#ff7a00', '#ffd9a8']}
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
          
          <span></span>
        </div>
        <div className="auth-visual__footer">
          <p className="auth-visual__quote">
            «Это приложение меня заебало»
          </p>
          <p className="auth-visual__wordmark">ебанный в рот.</p>
        </div>
      </aside>

      <div className="auth-panel">
        <div className="auth-card">
          <h1 className="auth-card__title">{title}</h1>
          <p className="auth-card__subtitle">{subtitle}</p>

          {children}
        </div>
      </div>
    </div>
  )
}
