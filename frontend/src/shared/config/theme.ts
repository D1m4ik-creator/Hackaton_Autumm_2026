import { theme as antTheme } from 'antd'
import type { ThemeConfig } from 'antd'
import type { ThemeMode } from '../lib/theme'

const commonTheme: ThemeConfig = {
  token: {
    borderRadius: 10,
    fontFamily: '"Inter Variable", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  components: {
    Card: { borderRadiusLG: 24, paddingLG: 24 },
    Button: { primaryShadow: 'none' },
  },
}

export const themes: Record<ThemeMode, ThemeConfig> = {
  light: {
    ...commonTheme,
    algorithm: antTheme.defaultAlgorithm,
    token: {
      ...commonTheme.token,
      colorPrimary: '#db6600',
      colorInfo: '#db6600',
      colorLink: '#db6600',
      colorText: '#121110',
      colorTextSecondary: '#7a7875',
      colorBgLayout: '#f2f1ef',
      colorBgContainer: '#ffffff',
      colorBgElevated: '#ffffff',
      colorBorder: '#e4e2df',
    },
    components: {
      ...commonTheme.components,
      Tag: { defaultBg: '#f2f1ef', defaultColor: '#7a7875' },
    },
  },
  dark: {
    ...commonTheme,
    algorithm: antTheme.darkAlgorithm,
    token: {
      ...commonTheme.token,
      colorPrimary: '#ff7a00',
      colorInfo: '#ff7a00',
      colorLink: '#ff7a00',
      colorText: '#fafafa',
      colorTextSecondary: '#a8a5a1',
      colorBgLayout: '#191816',
      colorBgContainer: '#211f1c',
      colorBgElevated: '#262420',
      colorBorder: '#2b2a29',
      colorBorderSecondary: '#242321',
    },
    components: {
      ...commonTheme.components,
      Tag: { defaultBg: '#2b2a29', defaultColor: '#bfbfc7' },
    },
  },
}
