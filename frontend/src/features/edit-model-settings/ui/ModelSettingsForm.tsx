import { Alert, App, Button, ConfigProvider, InputNumber, Slider } from 'antd'
import { useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { getWeightSum } from '../../../entities/model-settings'
import { useModelSettingsStore } from '../model/store'
import { AddModelFeatureModal } from './AddModelFeatureModal'
import './model-settings-form.css'

const weightColors = ['var(--dashboard-accent-bright)', 'var(--dashboard-text)', 'var(--dashboard-ring-medium)', 'var(--dashboard-muted)']
const sliderTheme = { components: { Slider: { railSize: 6, handleSize: 18, handleSizeHover: 18, handleLineWidth: 0, handleLineWidthHover: 0, railBg: 'var(--dashboard-ring-track)', railHoverBg: 'var(--dashboard-ring-track)' } } }

export function ModelSettingsForm() {
  const { draft, error, setWeight, setThreshold, save } = useModelSettingsStore()
  const { message } = App.useApp()
  const [addingFeature, setAddingFeature] = useState(false)
  const weightSum = getWeightSum(draft)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    try {
      if (save()) message.success('Настройки сохранены локально')
    } catch {
      message.error('Не удалось сохранить настройки в браузере.')
    }
  }

  return (
    <ConfigProvider theme={sliderTheme}>
      <form className="model-settings-form" onSubmit={submit}>
        <section className="model-settings-card model-settings-weights" aria-labelledby="model-weights-title">
          <h2 id="model-weights-title">Веса признаков</h2>
          <div className="model-settings-weights__controls">
            <div className="model-settings-weights__list">
              {draft.features.map((feature, index) => {
                const color = weightColors[Math.min(index, weightColors.length - 1)]
                return <div className="model-weight" key={feature.id} style={{ '--weight-color': color } as CSSProperties}>
                  <div className="model-weight__header">
                    <label id={`weight-label-${feature.id}`} htmlFor={`weight-${feature.id}`}>{feature.name}</label>
                    <InputNumber<number> id={`weight-${feature.id}`} aria-label={`Вес: ${feature.name}`} min={0} max={1} precision={2} step={0.01} controls={false} value={feature.weight} onChange={(value) => setWeight(feature.id, value ?? 0)} />
                  </div>
                  <Slider className="model-weight__slider" min={0} max={1} step={0.01} value={feature.weight} onChange={(value) => setWeight(feature.id, value)} ariaLabelledByForHandle={`weight-label-${feature.id}`} tooltip={{ formatter: (value) => value?.toFixed(2) }} styles={{ track: { background: color, borderRadius: 0 }, rail: { background: 'var(--dashboard-ring-track)', borderRadius: 0 } }} />
                </div>
              })}
            </div>
            <Button className="model-settings-add" htmlType="button" onClick={() => setAddingFeature(true)}>+ Добавить признак</Button>
            <p className="model-settings-weights__note">Сумма весов: {weightSum.toFixed(2)} · новый признак подключается без переработки модели</p>
          </div>
        </section>
        <section className="model-settings-card model-settings-thresholds" aria-labelledby="model-thresholds-title">
          <h2 id="model-thresholds-title">Пороги уровней риска</h2>
          <div className="model-settings-thresholds__fields">
            {(['high', 'medium'] as const).map((level) => <div className="model-threshold" key={level}>
              <label htmlFor={`threshold-${level}`}>{level === 'high' ? 'Высокий' : 'Средний'} риск, от</label>
              <InputNumber<number> id={`threshold-${level}`} aria-label={`${level === 'high' ? 'Высокий' : 'Средний'} риск, от`} min={0} max={100} precision={0} controls={false} value={draft.thresholds[level]} formatter={(value, { userTyping, input }) => userTyping ? input : `${value ?? ''} баллов`} parser={(value) => Number((value ?? '').replace(/[^\d-]/g, ''))} onChange={(value) => setThreshold(level, value ?? 0)} />
            </div>)}
          </div>
          <Button className="model-settings-save" htmlType="submit">СОХРАНИТЬ ИЗМЕНЕНИЯ</Button>
          <p className="model-settings-save-note">Сохраняется локально — переживёт перезапуск приложения</p>
          {error && <Alert className="model-settings-error" type="error" showIcon title={error} role="alert" />}
        </section>
      </form>
      <AddModelFeatureModal open={addingFeature} onClose={() => setAddingFeature(false)} />
    </ConfigProvider>
  )
}
