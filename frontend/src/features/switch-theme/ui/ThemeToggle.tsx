import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Switch } from 'antd'
import { useThemeStore } from '../../../shared/lib/theme'
import './theme-toggle.css'

export function ThemeToggle() {
  const mode = useThemeStore((state) => state.mode)
  const toggleTheme = useThemeStore((state) => state.toggleTheme)
  const isDark = mode === 'dark'

  return (
    <Switch
      className="theme-toggle"
      checked={isDark}
      onChange={toggleTheme}
      checkedChildren={<MoonOutlined />}
      unCheckedChildren={<SunOutlined />}
      aria-label={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'}
    />
  )
}
