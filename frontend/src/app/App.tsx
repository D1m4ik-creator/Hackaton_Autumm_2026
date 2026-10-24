import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from '../components/ProtectedRoute'
import { AuthProvider, useAuth } from '../context/AuthContext'
import { DashboardPage } from '../pages/dashboard'
import { ClientDetailPage } from '../pages/client-detail'
import { TopClientsPage } from '../pages/top-clients'
import { ModelSettingsPage } from '../pages/model-settings'
import { LoginPage } from '../pages/LoginPage'

function SessionLayout() {
  return <AuthProvider><Outlet /></AuthProvider>
}

function AuthenticatedDashboard() {
  const { logout } = useAuth()
  return <DashboardPage onSignOut={logout} />
}

function AuthenticatedClients() {
  const { logout } = useAuth()
  return <TopClientsPage onSignOut={logout} />
}

function AuthenticatedClientDetail() {
  const { logout } = useAuth()
  return <ClientDetailPage onSignOut={logout} />
}

function AuthenticatedModelSettings() {
  const { logout } = useAuth()
  return <ModelSettingsPage onSignOut={logout} />
}

export default function App() {
  return (
    <Routes>
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/clients" element={<TopClientsPage />} />
      <Route path="/clients/:clientId" element={<ClientDetailPage />} />
      <Route path="/model-settings" element={<ModelSettingsPage />} />
      <Route element={<SessionLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><AuthenticatedDashboard /></ProtectedRoute>} />
        <Route path="/app/clients" element={<ProtectedRoute><AuthenticatedClients /></ProtectedRoute>} />
        <Route path="/app/clients/:clientId" element={<ProtectedRoute><AuthenticatedClientDetail /></ProtectedRoute>} />
        <Route path="/app/model-settings" element={<ProtectedRoute><AuthenticatedModelSettings /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
