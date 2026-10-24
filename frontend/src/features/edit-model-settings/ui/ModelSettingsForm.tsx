import { Alert, App, Button, ConfigProvider, Input, InputNumber, Popconfirm, Slider, Spin } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { deleteCustomFeature, deleteModelWeight, getModelSettings, patchModelSettings } from '../../../api/model-settings'
import { useApiResource } from '../../../api/useApiResource'
import { useEventsStore } from '../../../api/events'
import { formatDateTime } from '../../../shared/lib/format'
import { defaultModelSettings, MODEL_FEATURES, readModelSettings, toSettingsPatch, validateModelSettings } from '../../../entities/model-settings'
import type { ModelSettings } from '../../../entities/model-settings'
import { useAuth } from '../../../context/AuthContext'
import { isAdminRole } from '../../../shared/lib/roles'
import './model-settings-form.css'

const weightColors = ['var(--dashboard-accent-bright)', 'var(--dashboard-text)', 'var(--dashboard-ring-medium)', 'var(--dashboard-muted)']
const sliderTheme = { components: { Slider: { railSize: 6, handleSize: 18, handleSizeHover: 18, handleLineWidth: 0, handleLineWidthHover: 0, railBg: 'var(--dashboard-ring-track)', railHoverBg: 'var(--dashboard-ring-track)' } } }
// Реальные веса — коэффициенты логрегрессии (app/ml/churn_model.py), не доли
// 0..1: диапазон слайдера даёт запас сверх текущих дефолтов (±3) для подбора.
const WEIGHT_RANGE = { min: -5, max: 5, step: 0.1 }
// Код метрики — как имя переменной Python (backend/app/analysis/churn.py: _CUSTOM_CODE_PATTERN).
const CUSTOM_CODE_PATTERN = /^[a-z][a-z0-9_]{2,40}$/
// Переменные формулы — backend/app/ml/features/base.py: context_variables().
const FORMULA_VARIABLES = [
  'balance', 'bonus_balance', 'bonus_state', 'available_funds', 'prolong_wait_cost', 'upcoming_cost',
  'expires_soon_days', 'total_services', 'active_services_count', 'prolong_wait_services_count',
  'suspended_services_count', 'gone_services_count', 'expiring_soon_count', 'total_transactions',
  'failed_transactions', 'total_replenished',
].join(', ')

function localDateTime(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function ModelSettingsForm() {
  const { user } = useAuth()
  const readOnly = !isAdminRole(user?.role)
  const { data, loading, error, reload, setData } = useApiResource(getModelSettings)
  const { message } = App.useApp()
  const [draft, setDraft] = useState<{ value: ModelSettings; baseline: ModelSettings } | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [togglingFeature, setTogglingFeature] = useState<string | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [newFormula, setNewFormula] = useState('')
  const [creatingFeature, setCreatingFeature] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const saved = data ? readModelSettings(data.settings, data.defaults) : null
  const value = draft?.value ?? saved
  const dirty = draft !== null && JSON.stringify(draft.value) !== JSON.stringify(draft.baseline)

  function edit(update: (settings: ModelSettings) => ModelSettings) {
    if (!value || readOnly || saving) return
    setDraft({ value: update(value), baseline: draft?.baseline ?? value })
    setSaveError(null)
  }

  function setWeight(code: string, weight: number) {
    edit((settings) => ({ ...settings, weights: { ...settings.weights, [code]: weight } }))
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

  // Исключение/возврат признака — отдельные немедленные запросы (DELETE/PATCH
  // одного веса), а не часть черновика формы: это структурное изменение набора
  // признаков модели, а не правка значения веса. Сбрасываем черновик следом,
  // чтобы несохранённые правки слайдеров не разошлись с новым списком признаков.
  async function removeFeature(code: string, label: string) {
    if (readOnly || togglingFeature) return
    setTogglingFeature(code)
    try {
      const response = await deleteModelWeight(code)
      setData(response)
      setDraft(null)
      useEventsStore.getState().invalidate()
      message.success(`Признак «${label}» исключён из модели`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Не удалось исключить признак')
    } finally { setTogglingFeature(null) }
  }

  async function restoreFeature(code: string, label: string) {
    if (readOnly || togglingFeature) return
    setTogglingFeature(code)
    try {
      const response = await patchModelSettings({ weights: { [code]: defaultModelSettings.weights[code] ?? 0 } })
      setData(response)
      setDraft(null)
      useEventsStore.getState().invalidate()
      message.success(`Признак «${label}» возвращён в модель`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Не удалось вернуть признак')
    } finally { setTogglingFeature(null) }
  }

  // Пользовательская метрика по формуле — отдельный запрос (PATCH сразу
  // customFeatures + вес 0), а не часть черновика формы: это новый признак
  // модели, а не правка значения, см. removeFeature/restoreFeature выше.
  async function removeCustomFeature(code: string, label: string) {
    if (readOnly || togglingFeature) return
    setTogglingFeature(code)
    try {
      const response = await deleteCustomFeature(code)
      setData(response)
      setDraft(null)
      useEventsStore.getState().invalidate()
      message.success(`Метрика «${label}» удалена`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Не удалось удалить метрику')
    } finally { setTogglingFeature(null) }
  }

  async function createCustomFeature() {
    if (readOnly || creatingFeature || !value) return
    const code = newCode.trim()
    const label = newLabel.trim()
    const formula = newFormula.trim()
    if (!CUSTOM_CODE_PATTERN.test(code)) { setCreateError('Код: латиница в нижнем регистре, цифры и _, начинается с буквы, длина 3-41'); return }
    if (value.weights[code] !== undefined || MODEL_FEATURES.some((f) => f.code === code)) { setCreateError(`Код «${code}» уже используется`); return }
    if (!label) { setCreateError('Укажите название метрики'); return }
    if (!formula) { setCreateError('Укажите формулу'); return }
    setCreatingFeature(true)
    setCreateError(null)
    try {
      const response = await patchModelSettings({ customFeatures: { [code]: { label, formula } }, weights: { [code]: 0 } })
      setData(response)
      setDraft(null)
      useEventsStore.getState().invalidate()
      setNewCode(''); setNewLabel(''); setNewFormula('')
      message.success(`Метрика «${label}» добавлена`)
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : 'Не удалось добавить метрику')
    } finally { setCreatingFeature(false) }
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
              {MODEL_FEATURES.map((feature, index) => {
                const color = weightColors[Math.min(index, weightColors.length - 1)]
                const isRemoved = value.removed.includes(feature.code)
                const isToggling = togglingFeature === feature.code
                const toggleDisabled = readOnly || (togglingFeature !== null && !isToggling)

                if (isRemoved) {
                  return <div className="model-weight model-weight--removed" key={feature.code}>
                    <div className="model-weight__header">
                      <label>{feature.label}</label>
                      {!readOnly && <Button className="model-weight__restore" htmlType="button" icon={<PlusOutlined />} loading={isToggling} disabled={toggleDisabled} onClick={() => restoreFeature(feature.code, feature.label)}>Вернуть в модель</Button>}
                    </div>
                    <p className="model-weight__hint">Признак исключён из модели — не участвует в оценке риска</p>
                  </div>
                }

                const weight = value.weights[feature.code] ?? 0
                return <div className="model-weight" key={feature.code} style={{ '--weight-color': color } as CSSProperties}>
                  <div className="model-weight__header">
                    <label id={`weight-label-${feature.code}`} htmlFor={`weight-${feature.code}`}>{feature.label}</label>
                    <div className="model-weight__actions">
                      <InputNumber<number> id={`weight-${feature.code}`} aria-label={`Вес: ${feature.label}`} min={WEIGHT_RANGE.min} max={WEIGHT_RANGE.max} precision={1} step={WEIGHT_RANGE.step} controls={false} value={weight} disabled={saving || readOnly} onChange={(next) => setWeight(feature.code, next ?? 0)} />
                      {!readOnly && <Popconfirm title={`Исключить «${feature.label}» из модели?`} okText="Исключить" cancelText="Отмена" onConfirm={() => removeFeature(feature.code, feature.label)}>
                        <Button className="model-weight__remove" type="text" htmlType="button" icon={<DeleteOutlined />} aria-label={`Исключить признак: ${feature.label}`} title="Исключить из модели" loading={isToggling} disabled={toggleDisabled} />
                      </Popconfirm>}
                    </div>
                  </div>
                  {feature.hint && <p className="model-weight__hint">{feature.hint}</p>}
                  <Slider className="model-weight__slider" min={WEIGHT_RANGE.min} max={WEIGHT_RANGE.max} step={WEIGHT_RANGE.step} value={weight} disabled={saving || readOnly} onChange={(next) => setWeight(feature.code, next)} ariaLabelledByForHandle={`weight-label-${feature.code}`} tooltip={{ formatter: (next) => next?.toFixed(1) }} styles={{ track: { background: color, borderRadius: 0 }, rail: { background: 'var(--dashboard-ring-track)', borderRadius: 0 } }} />
                </div>
              })}
            </div>
            <p className="model-settings-weights__note">Веса — коэффициенты логистической регрессии: чем больше по модулю, тем сильнее признак двигает оценку. Отрицательные значения снижают риск.</p>
          </div>
        </section>
        <section className="model-settings-card model-settings-custom-features" aria-labelledby="model-custom-features-title">
          <h2 id="model-custom-features-title">Пользовательские метрики</h2>
          <div className="model-settings-weights__list">
            {Object.entries(value.customFeatures).map(([code, spec], index) => {
              const color = weightColors[Math.min(MODEL_FEATURES.length + index, weightColors.length - 1)]
              const isToggling = togglingFeature === code
              const toggleDisabled = readOnly || (togglingFeature !== null && !isToggling)
              const weight = value.weights[code] ?? 0
              return <div className="model-weight" key={code} style={{ '--weight-color': color } as CSSProperties}>
                <div className="model-weight__header">
                  <label id={`weight-label-${code}`} htmlFor={`weight-${code}`}>{spec.label}</label>
                  <div className="model-weight__actions">
                    <InputNumber<number> id={`weight-${code}`} aria-label={`Вес: ${spec.label}`} min={WEIGHT_RANGE.min} max={WEIGHT_RANGE.max} precision={1} step={WEIGHT_RANGE.step} controls={false} value={weight} disabled={saving || readOnly} onChange={(next) => setWeight(code, next ?? 0)} />
                    {!readOnly && <Popconfirm title={`Удалить метрику «${spec.label}»?`} okText="Удалить" cancelText="Отмена" onConfirm={() => removeCustomFeature(code, spec.label)}>
                      <Button className="model-weight__remove" type="text" htmlType="button" icon={<DeleteOutlined />} aria-label={`Удалить метрику: ${spec.label}`} title="Удалить метрику" loading={isToggling} disabled={toggleDisabled} />
                    </Popconfirm>}
                  </div>
                </div>
                <p className="model-weight__hint model-weight__formula"><code>{spec.formula}</code></p>
                <Slider className="model-weight__slider" min={WEIGHT_RANGE.min} max={WEIGHT_RANGE.max} step={WEIGHT_RANGE.step} value={weight} disabled={saving || readOnly} onChange={(next) => setWeight(code, next)} ariaLabelledByForHandle={`weight-label-${code}`} tooltip={{ formatter: (next) => next?.toFixed(1) }} styles={{ track: { background: color, borderRadius: 0 }, rail: { background: 'var(--dashboard-ring-track)', borderRadius: 0 } }} />
              </div>
            })}
            {Object.keys(value.customFeatures).length === 0 && <p className="model-settings-save-note">Пользовательских метрик пока нет.</p>}
          </div>
          {!readOnly && <div className="model-custom-feature-create">
            <h3>Добавить метрику</h3>
            <div className="model-custom-feature-create__fields">
              <label htmlFor="custom-feature-code">Код (латиницей)</label>
              <Input id="custom-feature-code" value={newCode} onChange={(event) => setNewCode(event.target.value)} placeholder="big_spender" disabled={creatingFeature} />
              <label htmlFor="custom-feature-label">Название</label>
              <Input id="custom-feature-label" value={newLabel} onChange={(event) => setNewLabel(event.target.value)} placeholder="Крупный плательщик" disabled={creatingFeature} />
              <label htmlFor="custom-feature-formula">Формула</label>
              <Input.TextArea id="custom-feature-formula" value={newFormula} onChange={(event) => setNewFormula(event.target.value)} placeholder="total_replenished > 300000" rows={3} disabled={creatingFeature} />
              <p className="model-settings-save-note">Переменные: {FORMULA_VARIABLES}. Функции: min, max, abs.</p>
            </div>
            <Button htmlType="button" loading={creatingFeature} onClick={() => createCustomFeature()}>Добавить метрику</Button>
            {createError && <Alert className="model-settings-error" type="error" showIcon title={createError} role="alert" />}
          </div>}
        </section>
        <section className="model-settings-card model-settings-thresholds" aria-labelledby="model-thresholds-title">
          <h2 id="model-thresholds-title">Пороги и параметры</h2>
          <div className="model-settings-thresholds__fields">
            {(['high', 'medium'] as const).map((level) => <div className="model-threshold" key={level}>
              <label htmlFor={`threshold-${level}`}>{level === 'high' ? 'Высокий' : 'Средний'} риск, от</label>
              <InputNumber<number> id={`threshold-${level}`} aria-label={`${level === 'high' ? 'Высокий' : 'Средний'} риск, от`} min={0} max={100} precision={0} controls={false} value={value.thresholds[level]} disabled={saving || readOnly} formatter={(number, { userTyping, input }) => userTyping ? input : `${number ?? ''} баллов`} parser={(number) => Number((number ?? '').replace(/[^\d-]/g, ''))} onChange={(number) => edit((settings) => ({ ...settings, thresholds: { ...settings.thresholds, [level]: number ?? 0 } }))} />
            </div>)}
            <div className="model-threshold">
              <label htmlFor="model-bias">Смещение (bias)</label>
              <InputNumber<number> id="model-bias" min={-20} max={20} precision={1} step={0.1} controls={false} value={value.bias} disabled={saving || readOnly} onChange={(number) => edit((settings) => ({ ...settings, bias: number ?? 0 }))} />
            </div>
            <div className="model-threshold">
              <label htmlFor="model-expires-soon">Скоро истекает, дней</label>
              <InputNumber<number> id="model-expires-soon" min={1} max={365} precision={0} controls={false} value={value.expiresSoonDays} disabled={saving || readOnly} onChange={(number) => edit((settings) => ({ ...settings, expiresSoonDays: number ?? settings.expiresSoonDays }))} />
            </div>
            <div className="model-threshold">
              <label htmlFor="model-horizon">Горизонт прогноза, дней</label>
              <InputNumber<number> id="model-horizon" min={1} max={365} precision={0} controls={false} value={value.horizonDays} disabled={saving || readOnly} onChange={(number) => edit((settings) => ({ ...settings, horizonDays: number ?? settings.horizonDays }))} />
            </div>
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
    </ConfigProvider>
  )
}
