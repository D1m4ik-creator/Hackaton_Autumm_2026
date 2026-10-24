import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'light' | 'dark'

interface ThemeState {
  mode: ThemeMode
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      mode: 'light',
      toggleTheme: () => set((state) => ({ mode: state.mode === 'light' ? 'dark' : 'light' })),
    }),
    {
      name: 'retain-theme',
      partialize: (state) => ({ mode: state.mode }),
      merge: (persisted, current) => {
        const saved = persisted as { mode?: unknown } | null
        return { ...current, mode: saved?.mode === 'dark' ? 'dark' : 'light' }
      },
    },
  ),
)
