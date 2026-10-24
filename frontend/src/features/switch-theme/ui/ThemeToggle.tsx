import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Button } from 'antd'
import { useThemeStore } from '../../../shared/lib/theme'
import './theme-toggle.css'

export function ThemeToggle() {
  const mode = useThemeStore((state) => state.mode)
  const toggleTheme = useThemeStore((state) => state.toggleTheme)
  const isDark = mode === 'dark'

  return (
    <Button
      className="theme-toggle"
      icon={isDark ? <SunOutlined /> : <MoonOutlined />}
      onClick={toggleTheme}
      aria-label={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'}
      aria-pressed={isDark}
    >
      {isDark ? 'Светлая тема' : 'Тёмная тема'}
    </Button>
  )
}
