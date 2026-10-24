import { LetterA } from './LetterA'
import { LetterE } from './LetterE'
import { LetterZ } from './LetterZ'
import './aeza-logo.css'

// Собран из трёх разных SVG-букв: А, Е, З — последняя «а» переиспользует
// тот же компонент, что и первая.
export function AezaLogo({ className }: { className?: string }) {
  return (
    <span className={`aeza-logo ${className ?? ''}`} role="img" aria-label="Аеза">
      <LetterA className="aeza-logo__letter" />
      <LetterE className="aeza-logo__letter" />
      <LetterZ className="aeza-logo__letter" />
      <LetterA className="aeza-logo__letter" />
    </span>
  )
}
