import { MenuOutlined } from '@ant-design/icons'
import { App, Button, Drawer, Modal } from 'antd'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useRiskReportStore } from '../../../entities/risk-report'
import { useThemeStore } from '../../../shared/lib/theme'
import './dashboard-shell.css'

interface DashboardShellProps {
  children: ReactNode
  onSignOut?: () => Promise<void>
  className?: string
}

export function DashboardShell({ children, onSignOut, className = '' }: DashboardShellProps) {
  const navigate = useNavigate()
  const { message } = App.useApp()
  const report = useRiskReportStore((state) => state.report)
  const sidebarTheme = useThemeStore((state) => state.mode)
  const [menuOpen, setMenuOpen] = useState(false)
  const [metricsOpen, setMetricsOpen] = useState(false)
  const [isSigningOut, setIsSigningOut] = useState(false)
  const dashboardPath = onSignOut ? '/' : '/dashboard'
  const clientsPath = onSignOut ? '/app/clients' : '/clients'
  const modelSettingsPath = onSignOut ? '/app/model-settings' : '/model-settings'
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

  const sidebar = <div className="dashboard-sidebar-panel" data-theme={sidebarTheme}>
    <Link to={dashboardPath} className="dashboard-brand" aria-label="RETAIN — Дашборд" onClick={() => setMenuOpen(false)}>
      <span className="dashboard-brand__mark">R</span><span>RETAIN</span>
    </Link>
    <nav className="dashboard-nav" aria-label="Основная навигация">
      <NavLink to={dashboardPath} end className={navClassName} onClick={() => setMenuOpen(false)}>Дашборд</NavLink>
      <NavLink to={clientsPath} className={navClassName} onClick={() => setMenuOpen(false)}>Клиенты под риском</NavLink>
      <NavLink to={modelSettingsPath} className={navClassName} onClick={() => setMenuOpen(false)}>Настройка модели</NavLink>
      <button className="dashboard-nav__item" onClick={() => closeMenu(() => setMetricsOpen(true))}>Метрики /metrics</button>
    </nav>
    <Button className="dashboard-signout" type="text" onClick={signOut} loading={isSigningOut}>Выйти</Button>
  </div>

  return (
    <div className={`dashboard-layout ${className}`}>
      <a className="skip-to-content" href="#dashboard-content">К содержимому</a>
      <aside className="dashboard-sidebar">{sidebar}</aside>
      <div className="dashboard-mobile-header" data-theme={sidebarTheme}>
        <span className="dashboard-mobile-brand"><span className="dashboard-brand__mark">R</span> RETAIN</span>
        <Button type="text" icon={<MenuOutlined />} aria-label="Открыть меню" onClick={() => setMenuOpen(true)} />
      </div>
      <Drawer title="Навигация" placement="left" open={menuOpen} onClose={() => setMenuOpen(false)} className="dashboard-mobile-menu" size={260} styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}>{sidebar}</Drawer>
      <main id="dashboard-content" className="dashboard-main" tabIndex={-1}>{children}</main>
      <Modal open={metricsOpen} title="Метрики модели" onCancel={() => setMetricsOpen(false)} footer={<Button onClick={() => setMetricsOpen(false)}>Закрыть</Button>}>
        <div>
          <p>Демонстрационный снимок на 24 октября 2026 года.</p>
          <pre className="metrics-preview">{`retain_clients_total ${report.totalClients}\nretain_clients_high_risk ${report.high}\nretain_clients_medium_risk ${report.medium}\nretain_clients_low_risk ${report.low}\nretain_revenue_at_risk_eur ${report.revenueAtRisk}`}</pre>
        </div>
      </Modal>
    </div>
  )
}
