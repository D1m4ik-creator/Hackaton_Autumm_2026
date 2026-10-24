import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { defaultModelSettings, isModelSettings, validateModelSettings } from '../../../entities/model-settings'
import type { ModelSettings } from '../../../entities/model-settings'

interface ModelSettingsState {
  draft: ModelSettings
  saved: ModelSettings
  error: string | null
  setWeight: (id: string, weight: number) => void
  setThreshold: (level: 'high' | 'medium', value: number) => void
  addFeature: (name: string, weight: number) => void
  save: () => boolean
}

export const useModelSettingsStore = create<ModelSettingsState>()(
  persist(
    (set, get) => ({
      draft: structuredClone(defaultModelSettings),
      saved: structuredClone(defaultModelSettings),
      error: null,
      setWeight: (id, weight) => set((state) => ({
        draft: { ...state.draft, features: state.draft.features.map((feature) => feature.id === id ? { ...feature, weight: Math.round(Math.min(1, Math.max(0, weight)) * 100) / 100 } : feature) },
        error: null,
      })),
      setThreshold: (level, value) => set((state) => ({
        draft: { ...state.draft, thresholds: { ...state.draft.thresholds, [level]: Math.round(Math.min(100, Math.max(0, value))) } },
        error: null,
      })),
      addFeature: (name, weight) => set((state) => ({
        draft: { ...state.draft, features: [...state.draft.features, { id: `custom-${crypto.randomUUID()}`, name: name.trim(), weight }] },
        error: null,
      })),
      save: () => {
        const error = validateModelSettings(get().draft)
        if (error) { set({ error }); return false }
        set({ saved: structuredClone(get().draft), error: null })
        return true
      },
    }),
    {
      name: 'retain-model-settings',
      partialize: (state) => ({ saved: state.saved }),
      merge: (persisted, current) => {
        const saved = (persisted as { saved?: unknown } | null)?.saved
        const settings = isModelSettings(saved) ? saved : defaultModelSettings
        return { ...current, saved: structuredClone(settings), draft: structuredClone(settings), error: null }
      },
    },
  ),
)
