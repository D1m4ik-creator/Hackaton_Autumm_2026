import { App, ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import { useLayoutEffect } from 'react'
import type { ReactNode } from 'react'
import { themes } from '../../shared/config/theme'
import { useThemeStore } from '../../shared/lib/theme'
import '../styles/global.css'

// Левый сайдбар всегда тёмный (см. dashboard-shell.css). Тема контента —
// общая для всего приложения, переключается из useThemeStore.
export function UiProvider({ children }: { children: ReactNode }) {
  const mode = useThemeStore((state) => state.mode)

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = mode
  }, [mode])

  return <ConfigProvider theme={themes[mode]} locale={ruRU}><App>{children}</App></ConfigProvider>
}
