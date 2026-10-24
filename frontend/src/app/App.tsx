import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes, useParams } from 'react-router-dom'
import { ProtectedRoute } from '../components/ProtectedRoute'
import { AuthProvider, useAuth } from '../context/AuthContext'
import { SplashScreen } from '../shared/ui/splash-screen/SplashScreen'
import { DashboardPage } from '../pages/dashboard'
import { ClientDetailPage } from '../pages/client-detail'
import { TopClientsPage } from '../pages/top-clients'
import { ModelSettingsPage } from '../pages/model-settings'
import { LoginPage } from '../pages/LoginPage'

// Минимум, сколько держим сплэш на экране — даже если сессия проверилась
// мгновенно. Без этого лого мелькает долей секунды и анимация выглядит рвано.
const MIN_SPLASH_MS = 900

// Держит сплэш-экран (лого Aeza), пока AuthProvider не закончит первую
// проверку сессии (покрывает и первую загрузку, и F5), и плавно
// кросс-фейдит его в контент приложение — без резкого обрыва анимации.
function AuthGate({ children }: { children: ReactNode }) {
  const { isLoading } = useAuth()
  const [minTimeElapsed, setMinTimeElapsed] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setMinTimeElapsed(true), MIN_SPLASH_MS)
    return () => clearTimeout(timer)
  }, [])

  const showSplash = isLoading || !minTimeElapsed

  return (
    <AnimatePresence mode="wait">
      {showSplash
        ? <SplashScreen key="splash" />
        : <motion.div key="app" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, ease: 'easeOut' }}>{children}</motion.div>}
    </AnimatePresence>
  )
}

// Анимация перехода между страницами живёт в DashboardShell (только вокруг
// <main>) — сайдбар общий для всех защищённых страниц и не должен
// переанимироваться при каждой навигации, иначе весь экран "смазывается".
function SessionLayout() {
  return (
    <AuthProvider>
      <AuthGate>
        <Outlet />
      </AuthGate>
    </AuthProvider>
  )
}

function RedirectToClientDetail() {
  const { clientId } = useParams()
  return <Navigate to={`/app/clients/${clientId}`} replace />
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
      <Route path="/dashboard" element={<Navigate to="/" replace />} />
      <Route path="/clients" element={<Navigate to="/app/clients" replace />} />
      <Route path="/clients/:clientId" element={<RedirectToClientDetail />} />
      <Route path="/model-settings" element={<Navigate to="/app/model-settings" replace />} />
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
