import type { ReactNode } from 'react'
import { AezaLogo } from '../shared/ui/aeza-logo/AezaLogo'
import { GradientBlinds } from './GradientBlinds'
import '../styles/auth.css'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
}

// Стабильная ссылка вне компонента: GradientBlinds держит этот массив в
// зависимостях своего useEffect. Инлайн-литерал пересоздавался бы на
// каждый ре-рендер AuthLayout (а он ре-рендерится на каждое нажатие клавиши
// в форме логина) — эффект думал бы, что проп изменился, и пересоздавал
// WebGL-рендерер с нуля, отсюда дёрганый рестарт анимации при вводе.
const GRADIENT_COLORS = ['#120f0c', '#ff7a00', '#ffd9a8']

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="auth-layout">
      <aside className="auth-visual">
        <div className="auth-visual__bg">
          <GradientBlinds
            gradientColors={GRADIENT_COLORS}
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
          <AezaLogo className="auth-visual__brand-logo" />
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
