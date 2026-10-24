import './splash-screen.css'

export function SplashScreen() {
  return (
    <div className="app-splash" role="status" aria-live="polite" aria-label="Загрузка">
      <div className="app-splash__mark">
        <span>A</span>
        <span className="app-splash__ring" aria-hidden="true" />
      </div>
      <p className="app-splash__brand">Aeza</p>
    </div>
  )
}
