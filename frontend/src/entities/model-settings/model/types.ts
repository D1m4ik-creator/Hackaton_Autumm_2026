export interface ModelFeature {
  id: string
  name: string
  weight: number
}

export interface ModelSettings {
  features: ModelFeature[]
  thresholds: { high: number; medium: number }
}
