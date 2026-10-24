import { App, ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import type { ReactNode } from 'react'
import { themes } from '../../shared/config/theme'
import '../styles/global.css'

// Тёмная тема применяется только к левому сайдбару (см. DashboardShell),
// контент дашборда всегда светлый — поэтому ConfigProvider и :root
// фиксированы на light-палитре независимо от useThemeStore.
export function UiProvider({ children }: { children: ReactNode }) {
  return <ConfigProvider theme={themes.light} locale={ruRU}><App>{children}</App></ConfigProvider>
}
