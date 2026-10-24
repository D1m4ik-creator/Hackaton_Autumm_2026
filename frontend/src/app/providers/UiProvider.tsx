import { App, ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import { useLayoutEffect } from 'react'
import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { themes } from '../../shared/config/theme'
import { useThemeStore } from '../../shared/lib/theme'
import '../styles/global.css'

export function UiProvider({ children }: { children: ReactNode }) {
  const preferredMode = useThemeStore((state) => state.mode)
  const { pathname } = useLocation()
  const isDashboard = pathname === '/' || /^\/dashboard\/?$/.test(pathname)
  const isClientDetail = /^\/(?:app\/)?clients\/[^/]+\/?$/.test(pathname)
  const mode = isDashboard || isClientDetail ? preferredMode : 'light'

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = mode
  }, [mode])

  return <ConfigProvider theme={themes[mode]} locale={ruRU}><App>{children}</App></ConfigProvider>
}
