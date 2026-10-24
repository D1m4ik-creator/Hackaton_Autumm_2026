import { ModelSettingsForm } from '../../../features/edit-model-settings'
import { DashboardShell } from '../../../widgets/dashboard-shell'
import './model-settings.css'
import { useAuth } from '../../../context/AuthContext'

export function ModelSettingsPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { user } = useAuth()
  return (
    <DashboardShell className="model-settings-page" onSignOut={onSignOut}>
      <header className="model-settings-heading">
        <h1>Настройка модели</h1>
        <p>{user?.role === 'admin' ? 'Веса признаков, пороги риска и дата расчёта' : 'Просмотр параметров модели'}</p>
      </header>
      <ModelSettingsForm />
    </DashboardShell>
  )
}
