import { GRAFANA_URL } from '../../../api/client'
import { useThemeStore } from '../../../shared/lib/theme'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './grafana.css'

// kiosk — прячет собственные шапку/меню Grafana (остаются только панели
// дашборда), theme синхронизируется с переключателем темы панели
// (ThemeToggle, shared/lib/theme) — анонимный Viewer настроен в compose
// (GF_AUTH_ANONYMOUS_*), т.к. cookie-сессия Grafana не доходит до iframe
// на другом порту без HTTPS (SameSite).
function dashboardUrl(theme: 'light' | 'dark'): string {
  return `${GRAFANA_URL}/d/churn-overview/churn-overview?orgId=1&kiosk&theme=${theme}`
}

export function GrafanaPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const theme = useThemeStore((state) => state.mode)

  return (
    <DashboardShell className="grafana-page" onSignOut={onSignOut}>
      <header className="grafana-heading">
        <h1>Графики (Grafana)</h1>
        <p>Та же история по /metrics, что хранит Prometheus — числа по уровням риска и ожидаемым потерям во времени, с алертами (см. ops/README.md).</p>
      </header>
      <div className="grafana-frame-card">
        <iframe key={theme} className="grafana-frame" src={dashboardUrl(theme)} title="Дашборд Grafana: Churn Overview" loading="lazy" />
      </div>
    </DashboardShell>
  )
}
