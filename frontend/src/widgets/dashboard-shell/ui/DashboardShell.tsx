import { MenuOutlined } from '@ant-design/icons'
import { App, Button, Drawer } from 'antd'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { METRICS_URL } from '../../../api/client'
import { ThemeToggle } from '../../../features/switch-theme'
import { clientsPath as resolveClientsPath, dashboardPath as resolveDashboardPath, modelSettingsPath as resolveModelSettingsPath } from '../../../shared/lib/app-paths'
import { isAdminRole, isSuperadmin } from '../../../shared/lib/roles'
import { AezaLogo } from '../../../shared/ui/aeza-logo/AezaLogo'
import { useAuth } from '../../../context/AuthContext'
import { SnapshotUpload } from '../../../features/upload-snapshot/SnapshotUpload'
import './dashboard-shell.css'

interface DashboardShellProps {
  children: ReactNode
  onSignOut?: () => Promise<void>
  className?: string
}

export function DashboardShell({ children, onSignOut, className = '' }: DashboardShellProps) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const shouldReduceMotion = useReducedMotion()
  const { message } = App.useApp()
  const { user } = useAuth()
  const isAdmin = isAdminRole(user?.role)
  const usersNavLabel = isSuperadmin(user?.role) ? 'Управление пользователями' : 'Управление менеджерами'
  const [menuOpen, setMenuOpen] = useState(false)
  const [snapshotOpen, setSnapshotOpen] = useState(false)
  const [isSigningOut, setIsSigningOut] = useState(false)
  const dashboardPath = resolveDashboardPath(pathname)
  const clientsPath = resolveClientsPath(pathname)
  const modelSettingsPath = resolveModelSettingsPath(pathname)
  const navClassName = ({ isActive }: { isActive: boolean }) => `dashboard-nav__item ${isActive ? 'dashboard-nav__item--active' : ''}`

  async function signOut() {
    setIsSigningOut(true)
    try {
      await onSignOut?.()
      navigate('/login')
    } catch {
      message.error('Не удалось выйти. Повторите попытку.')
    } finally {
      setIsSigningOut(false)
    }
  }

  function closeMenu(action: () => void) {
    setMenuOpen(false)
    action()
  }

  const sidebar = <div className="dashboard-sidebar-panel">
    <Link to={dashboardPath} className="dashboard-brand" aria-label="Аеза — Дашборд" onClick={() => setMenuOpen(false)}>
      <AezaLogo className="dashboard-brand__logo" />
    </Link>
    <nav className="dashboard-nav" aria-label="Основная навигация">
      <NavLink to={dashboardPath} end className={navClassName} onClick={() => setMenuOpen(false)}>Дашборд</NavLink>
      <NavLink to={clientsPath} className={navClassName} onClick={() => setMenuOpen(false)}>Клиенты под риском</NavLink>
      <NavLink to={modelSettingsPath} className={navClassName} onClick={() => setMenuOpen(false)}>Настройка модели</NavLink>
      <NavLink to="/app/churn-trend" className={navClassName} onClick={() => setMenuOpen(false)}>График оттока</NavLink>
      {isAdmin && <NavLink to="/app/users" className={navClassName} onClick={() => setMenuOpen(false)}>{usersNavLabel}</NavLink>}
      {isAdmin && <button className="dashboard-nav__item" onClick={() => closeMenu(() => setSnapshotOpen(true))}>Загрузить снимок</button>}
      <a className="dashboard-nav__item" href={METRICS_URL} target="_blank" rel="noopener noreferrer" onClick={() => setMenuOpen(false)}>Метрики /metrics</a>
    </nav>
    <div className="dashboard-sidebar-footer">
      <Button className="dashboard-signout" type="text" onClick={signOut} loading={isSigningOut}>Выйти</Button>
      <ThemeToggle />
    </div>
  </div>

  return (
    <div className={`dashboard-layout ${className}`}>
      <a className="skip-to-content" href="#dashboard-content">К содержимому</a>
      <aside className="dashboard-sidebar">{sidebar}</aside>
      <div className="dashboard-mobile-header">
        <span className="dashboard-mobile-brand"><AezaLogo className="dashboard-brand__logo" /></span>
        <Button type="text" icon={<MenuOutlined />} aria-label="Открыть меню" onClick={() => setMenuOpen(true)} />
      </div>
      <Drawer title="Навигация" placement="right" open={menuOpen} onClose={() => setMenuOpen(false)} className="dashboard-mobile-menu" size={260} styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}>{sidebar}</Drawer>
      <main id="dashboard-content" className="dashboard-main" tabIndex={-1}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={pathname}
            initial={shouldReduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={shouldReduceMotion ? undefined : { opacity: 0 }}
            transition={{ duration: shouldReduceMotion ? 0 : 0.42, ease: [0.22, 1, 0.36, 1] }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
      {isAdmin && <SnapshotUpload open={snapshotOpen} onClose={() => setSnapshotOpen(false)} />}
    </div>
  )
}
