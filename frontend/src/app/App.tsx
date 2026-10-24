import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { ProtectedRoute } from '../components/ProtectedRoute'
import { AuthProvider, useAuth } from '../context/AuthContext'
import { SplashScreen } from '../shared/ui/splash-screen/SplashScreen'
import { DashboardPage } from '../pages/dashboard'
import { ClientDetailPage } from '../pages/client-detail'
import { TopClientsPage } from '../pages/top-clients'
import { ModelSettingsPage } from '../pages/model-settings'
import { LoginPage } from '../pages/LoginPage'

// Держит сплэш-экран (лого Aeza), пока AuthProvider не закончит
// первую проверку сессии — покрывает и первую загрузку, и F5.
function AuthGate({ children }: { children: ReactNode }) {
  const { isLoading } = useAuth()
  if (isLoading) return <SplashScreen />
  return <>{children}</>
}

function SessionLayout() {
  const location = useLocation()
  const shouldReduceMotion = useReducedMotion()

  return (
    <AuthProvider>
      <AuthGate>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={shouldReduceMotion ? undefined : { opacity: 0, y: -8 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.22, ease: [0.4, 0, 0.2, 1] }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
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
