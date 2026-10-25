import { Alert, App, Button, Modal, Segmented, Upload } from 'antd'
import { useRef, useState } from 'react'
import { request } from '../../api/client'
import { useEventsStore } from '../../api/events'
import { formatDateTime } from '../../shared/lib/format'

type SnapshotMode = 'replace' | 'merge'

interface SnapshotResult {
  accounts: number
  services: number
  transactions: number
  version: number
  recalculatedAt: string
  mode: SnapshotMode
}

const MODE_COPY: Record<SnapshotMode, { warning: string; okText: string; resultLabel: string }> = {
  replace: {
    warning: 'Снимок полностью заменит текущие аккаунты, услуги и транзакции. После загрузки оценки будут пересчитаны.',
    okText: 'Заменить данные',
    resultLabel: 'Режим: замена',
  },
  merge: {
    warning: 'Новые записи добавятся к существующим данным. Если какой-то ID или email уже есть — весь снимок будет отклонён, старые данные не тронутся.',
    okText: 'Добавить данные',
    resultLabel: 'Режим: добавление',
  },
}

export function SnapshotUpload({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [mode, setMode] = useState<SnapshotMode>('replace')
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null)
  const [fileName, setFileName] = useState('')
  const [loading, setLoading] = useState(false)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SnapshotResult | null>(null)
  const selection = useRef(0)

  function close() {
    if (loading) return
    selection.current++
    onClose()
  }

  async function upload() {
    if (!snapshot || loading || reading) return
    setLoading(true)
    setError(null)
    try {
      const loaded = await request<SnapshotResult>('/source/snapshot', { method: 'PUT', data: snapshot, params: { mode } })
      setResult(loaded)
      useEventsStore.getState().invalidate()
      message.success(mode === 'merge' ? 'Снимок добавлен, оценки пересчитаны' : 'Снимок загружен, оценки пересчитаны')
    } catch (error) { setError(error instanceof Error ? error.message : 'Не удалось загрузить снимок') }
    finally { setLoading(false) }
  }

  return <Modal title="Загрузка снимка" open={open} onCancel={close} onOk={() => result ? close() : void upload()} okText={result ? 'Готово' : MODE_COPY[mode].okText} cancelText="Закрыть" okButtonProps={{ disabled: !result && (!snapshot || reading) }} confirmLoading={loading} afterClose={() => { setMode('replace'); setSnapshot(null); setFileName(''); setError(null); setResult(null); setReading(false) }}>
    {!result && <Segmented<SnapshotMode> style={{ marginBottom: 12 }} value={mode} onChange={setMode} disabled={loading} options={[{ label: 'Заменить', value: 'replace' }, { label: 'Добавить', value: 'merge' }]} aria-label="Режим загрузки снимка" />}
    <p>{result ? MODE_COPY[result.mode].warning : MODE_COPY[mode].warning}</p>
    <Upload accept=".json,application/json" showUploadList={false} disabled={loading} beforeUpload={async (file) => {
      const current = ++selection.current
      setReading(true)
      setError(null)
      setResult(null)
      setSnapshot(null)
      setFileName('')
      try {
        let data: unknown
        try { data = JSON.parse(await file.text()) } catch { throw new Error('Не удалось прочитать JSON. Проверьте формат файла.') }
        if (!data || typeof data !== 'object' || !['accounts', 'services', 'transactions'].every((key) => Array.isArray((data as Record<string, unknown>)[key]))) throw new Error('Снимок должен содержать массивы accounts, services и transactions.')
        if (current === selection.current) {
          setSnapshot(data as Record<string, unknown>)
          setFileName(file.name)
        }
      } catch (error) {
        if (current === selection.current) setError(error instanceof Error ? error.message : 'Не удалось прочитать JSON')
      } finally {
        if (current === selection.current) setReading(false)
      }
      return false
    }}><Button loading={reading}>Выбрать JSON-файл</Button></Upload>
    {fileName && <p>{fileName}</p>}
    {result && <Alert type="success" showIcon title="Снимок загружен" description={<div>
      <p>{MODE_COPY[result.mode].resultLabel}</p>
      <p>Аккаунтов: {result.accounts}</p>
      <p>Услуг: {result.services}</p>
      <p>Транзакций: {result.transactions}</p>
      <p>Пересчёт: {formatDateTime(result.recalculatedAt)}</p>
    </div>} />}
    {error && <Alert type="error" showIcon title="Не удалось загрузить снимок" description={<div style={{ whiteSpace: 'pre-line' }}>{error}</div>} role="alert" />}
  </Modal>
}
