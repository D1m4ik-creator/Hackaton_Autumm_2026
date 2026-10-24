import { Alert, App, Button, Modal, Upload } from 'antd'
import { useState } from 'react'
import { request } from '../../api/client'
import { useEventsStore } from '../../api/events'

export function SnapshotUpload({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null)
  const [fileName, setFileName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function upload() {
    if (!snapshot) return
    setLoading(true)
    setError(null)
    try {
      await request('/source/snapshot', { method: 'PUT', data: snapshot })
      useEventsStore.getState().invalidate()
      message.success('Снимок загружен, оценки пересчитаны')
      onClose()
    } catch (error) { setError(error instanceof Error ? error.message : 'Не удалось загрузить снимок') }
    finally { setLoading(false) }
  }

  return <Modal title="Загрузка снимка" open={open} onCancel={() => { if (!loading) onClose() }} onOk={() => void upload()} okText="Заменить данные" cancelText="Отмена" okButtonProps={{ disabled: !snapshot }} confirmLoading={loading} afterClose={() => { setSnapshot(null); setFileName(''); setError(null) }}>
    <p>Снимок полностью заменит текущие аккаунты, услуги и транзакции. После загрузки оценки будут пересчитаны.</p>
    <Upload accept=".json,application/json" showUploadList={false} disabled={loading} beforeUpload={async (file) => {
      setError(null)
      setSnapshot(null)
      setFileName('')
      try {
        const data: unknown = JSON.parse(await file.text())
        if (!data || typeof data !== 'object' || !['accounts', 'services', 'transactions'].every((key) => Array.isArray((data as Record<string, unknown>)[key]))) throw new Error('Снимок должен содержать массивы accounts, services и transactions.')
        setSnapshot(data as Record<string, unknown>)
        setFileName(file.name)
      } catch (error) { setError(error instanceof Error ? error.message : 'Не удалось прочитать JSON') }
      return false
    }}><Button>Выбрать JSON-файл</Button></Upload>
    {fileName && <p>{fileName}</p>}
    {error && <Alert type="error" title={error} role="alert" />}
  </Modal>
}
