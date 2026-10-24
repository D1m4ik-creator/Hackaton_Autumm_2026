import { Alert, App, Button, ConfigProvider, Input, InputNumber, Slider, Spin } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { getModelSettings, patchModelSettings } from '../../../api/model-settings'
import { useApiResource } from '../../../api/useApiResource'
import { useEventsStore } from '../../../api/events'
import { formatDateTime } from '../../../shared/lib/format'
import { getWeightSum, readModelSettings, toSettingsPatch, validateModelSettings } from '../../../entities/model-settings'
import type { ModelSettings } from '../../../entities/model-settings'
import { AddModelFeatureModal } from './AddModelFeatureModal'
import { useAuth } from '../../../context/AuthContext'
import './model-settings-form.css'

const weightColors = ['var(--dashboard-accent-bright)', 'var(--dashboard-text)', 'var(--dashboard-ring-medium)', 'var(--dashboard-muted)']
const sliderTheme = { components: { Slider: { railSize: 6, handleSize: 18, handleSizeHover: 18, handleLineWidth: 0, handleLineWidthHover: 0, railBg: 'var(--dashboard-ring-track)', railHoverBg: 'var(--dashboard-ring-track)' } } }

function localDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function ModelSettingsForm() {
  const { user } = useAuth()
  const readOnly = user?.role !== 'admin'
  const { data, loading, error, reload, setData } = useApiResource(getModelSettings)
  const { message } = App.useApp()
  const [draft, setDraft] = useState<{ value: ModelSettings; baseline: ModelSettings } | null>(null)
  const [addingFeature, setAddingFeature] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const saved = data ? readModelSettings(data.settings, data.defaults) : null
  const value = draft?.value ?? saved
  const dirty = draft !== null && JSON.stringify(draft.value) !== JSON.stringify(draft.baseline)

  function edit(update: (settings: ModelSettings) => ModelSettings) {
    if (!value || readOnly || saving) return
    setDraft({ value: update(value), baseline: draft?.baseline ?? value })
    setSaveError(null)
  }

  function setWeight(id: string, weight: number) {
    edit((settings) => ({ ...settings, features: settings.features.map((feature) => feature.id === id ? { ...feature, weight } : feature) }))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaveError(null)
    if (!value || !saved || saving || readOnly) return
    const validationError = validateModelSettings(value)
    if (validationError) { setSaveError(validationError); return }
    setSaving(true)
    try {
      const response = await patchModelSettings(toSettingsPatch(value, draft?.baseline ?? saved))
      setData(response)
      setDraft(null)
      useEventsStore.getState().invalidate()
      message.success('Настройки сохранены, оценки пересчитаны')
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Не удалось сохранить настройки')
    } finally { setSaving(false) }
  }

  if (!data || !value) return error
    ? <Alert type="error" title={error} action={<Button onClick={reload}>Повторить</Button>} />
    : <Spin />

  return (
    <ConfigProvider theme={sliderTheme}>
    <Spin spinning={loading}>
      <form className="model-settings-form" onSubmit={submit}>
        <section className="model-settings-card model-settings-weights" aria-labelledby="model-weights-title">
          <h2 id="model-weights-title">Веса признаков</h2>
          <div className="model-settings-weights__controls">
            <div className="model-settings-weights__list">
              {value.features.map((feature, index) => {
                const color = weightColors[Math.min(index, weightColors.length - 1)]
                return <div className="model-weight" key={feature.id} style={{ '--weight-color': color } as CSSProperties}>
                  <div className="model-weight__header">
                    <label id={`weight-label-${feature.id}`} htmlFor={`weight-${feature.id}`}>{feature.name}</label>
                    <div className="model-weight__actions">
                      <InputNumber<number> id={`weight-${feature.id}`} aria-label={`Вес: ${feature.name}`} min={0} max={1} precision={2} step={0.01} controls={false} value={feature.weight} disabled={saving || readOnly} onChange={(weight) => setWeight(feature.id, weight ?? 0)} />
                      {!readOnly && <Button className="model-weight__remove" type="text" htmlType="button" icon={<DeleteOutlined />} aria-label={`Удалить признак: ${feature.name}`} title="Удалить признак" disabled={saving} onClick={() => edit((settings) => ({ ...settings, features: settings.features.filter((item) => item.id !== feature.id) }))} />}
                    </div>
                  </div>
                  <Slider className="model-weight__slider" min={0} max={1} step={0.01} value={feature.weight} disabled={saving || readOnly} onChange={(weight) => setWeight(feature.id, weight)} ariaLabelledByForHandle={`weight-label-${feature.id}`} tooltip={{ formatter: (weight) => weight?.toFixed(2) }} styles={{ track: { background: color, borderRadius: 0 }, rail: { background: 'var(--dashboard-ring-track)', borderRadius: 0 } }} />
                </div>
              })}
            </div>
            {!readOnly && <Button className="model-settings-add" htmlType="button" disabled={saving} onClick={() => setAddingFeature(true)}>+ Добавить признак</Button>}
            <p className="model-settings-weights__note">Сумма весов: {getWeightSum(value).toFixed(2)} · должна быть равна 1.00</p>
            {!Array.isArray(data.defaults.features) && <p className="model-settings-weights__note">Модель расчёта пока не подключена. Веса и пороги сохраняются, но пока не влияют на оценку.</p>}
          </div>
        </section>
        <section className="model-settings-card model-settings-thresholds" aria-labelledby="model-thresholds-title">
          <h2 id="model-thresholds-title">Пороги уровней риска</h2>
          <div className="model-settings-thresholds__fields">
            {(['high', 'medium'] as const).map((level) => <div className="model-threshold" key={level}>
              <label htmlFor={`threshold-${level}`}>{level === 'high' ? 'Высокий' : 'Средний'} риск, от</label>
              <InputNumber<number> id={`threshold-${level}`} aria-label={`${level === 'high' ? 'Высокий' : 'Средний'} риск, от`} min={0} max={100} precision={0} controls={false} value={value.thresholds[level]} disabled={saving || readOnly} formatter={(number, { userTyping, input }) => userTyping ? input : `${number ?? ''} баллов`} parser={(number) => Number((number ?? '').replace(/[^\d-]/g, ''))} onChange={(number) => edit((settings) => ({ ...settings, thresholds: { ...settings.thresholds, [level]: number ?? 0 } }))} />
            </div>)}
            <div className="model-threshold">
              <label htmlFor="model-as-of">Дата расчёта</label>
              <Input id="model-as-of" type="datetime-local" value={localDateTime(value.asOf)} disabled={saving || readOnly} onChange={(event) => edit((settings) => ({ ...settings, asOf: event.target.value ? new Date(event.target.value).toISOString() : null }))} />
              <p className="model-settings-save-note">Оставьте пустым для текущего времени</p>
            </div>
          </div>
          {readOnly ? <p className="model-settings-save-note" role="status">Режим просмотра. Изменять настройки может администратор.</p> : <Button className="model-settings-save" htmlType="submit" loading={saving} disabled={loading || !dirty}>СОХРАНИТЬ ИЗМЕНЕНИЯ</Button>}
          <p className="model-settings-save-note">Обновлено: {formatDateTime(data.updatedAt)}</p>
          {(saveError || error) && <Alert className="model-settings-error" type="error" showIcon title={saveError ?? error} role="alert" />}
        </section>
      </form>
    </Spin>
    {!readOnly && <AddModelFeatureModal open={addingFeature} features={value.features} onClose={() => setAddingFeature(false)} onAdd={(name, weight) => edit((settings) => ({ ...settings, features: [...settings.features, { id: `custom-${crypto.randomUUID()}`, name, weight }] }))} />}
    </ConfigProvider>
  )
}
