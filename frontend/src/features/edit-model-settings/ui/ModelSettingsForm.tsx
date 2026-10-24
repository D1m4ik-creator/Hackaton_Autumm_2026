import { Alert, App, Button, Input, Spin } from 'antd'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { getModelSettings, patchModelSettings } from '../../../api/model-settings'
import { useApiResource } from '../../../api/useApiResource'
import { useEventsStore } from '../../../api/events'
import { formatDateTime } from '../../../shared/lib/format'
import './model-settings-form.css'

export function ModelSettingsForm() {
  const { data, loading, error, reload, setData } = useApiResource(getModelSettings)
  const { message } = App.useApp()
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const value = draft ?? (data ? JSON.stringify(data.settings, null, 2) : '')
  const dirty = draft !== null && draft !== JSON.stringify(data?.settings, null, 2)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaveError(null)
    let settings: unknown
    try { settings = JSON.parse(value) } catch {
      setSaveError('Проверьте формат JSON.'); return
    }
    if (!settings || typeof settings !== 'object' || Array.isArray(settings)) {
      setSaveError('Настройки должны быть объектом JSON.'); return
    }
    setSaving(true)
    try {
      const saved = await patchModelSettings(settings as Record<string, unknown>)
      setData(saved)
      setDraft(null)
      useEventsStore.getState().invalidate()
      message.success('Настройки сохранены, оценки пересчитаны')
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Не удалось сохранить настройки')
    } finally { setSaving(false) }
  }

  if (!data) return error
    ? <Alert type="error" title={error} action={<Button onClick={reload}>Повторить</Button>} />
    : <Spin />

  return (
    <Spin spinning={loading}>
      <form className="model-settings-form" onSubmit={submit}>
        <section className="model-settings-card" aria-labelledby="model-config-title">
          <h2 id="model-config-title">Параметры текущей модели</h2>
          <p>Конфигурация в формате JSON. asOf — дата расчёта в ISO-8601 или null для текущего времени.</p>
          <Input.TextArea aria-label="Настройки модели JSON" value={value} onChange={(event) => { setDraft(event.target.value); setSaveError(null) }} disabled={saving} autoSize={{ minRows: 14, maxRows: 28 }} spellCheck={false} />
          <Button className="model-settings-save" htmlType="submit" loading={saving} disabled={loading || !dirty}>СОХРАНИТЬ ИЗМЕНЕНИЯ</Button>
          <p className="model-settings-save-note">Обновлено: {formatDateTime(data.updatedAt)}</p>
          {(saveError || error) && <Alert type="error" title={saveError ?? error} role="alert" />}
        </section>
        <section className="model-settings-card">
          <h2>Значения по умолчанию</h2>
          <pre className="model-settings-defaults">{JSON.stringify(data.defaults, null, 2)}</pre>
          <Button disabled={saving} onClick={() => setDraft(JSON.stringify(data.defaults, null, 2))}>Подставить значения</Button>
        </section>
      </form>
    </Spin>
  )
}
