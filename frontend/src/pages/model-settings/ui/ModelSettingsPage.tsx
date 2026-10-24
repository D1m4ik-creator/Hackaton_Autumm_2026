import { ModelSettingsForm } from '../../../features/edit-model-settings'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './model-settings.css'

export function ModelSettingsPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  return (
    <DashboardShell className="model-settings-page" onSignOut={onSignOut}>
      <header className="model-settings-heading">
        <h1>Настройка модели</h1>
        <p>Изменения пересчитывают risk-score сразу, без перезагрузки страницы</p>
      </header>
      <ModelSettingsForm />
    </DashboardShell>
  )
}
