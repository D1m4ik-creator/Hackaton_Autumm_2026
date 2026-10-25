import { Alert, App, Button, Input, InputNumber, Modal, Popconfirm, Table, Tag } from 'antd'
import type { TableColumnsType } from 'antd'
import { CopyOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { createShareLink, listShareLinks, revokeShareLink } from '../../../api/share-links'
import type { ShareLink } from '../../../api/share-links'
import { useApiResource } from '../../../api/useApiResource'
import { formatDateTime } from '../../../shared/lib/format'

function shareUrl(token: string): string {
  return `${window.location.origin}/report/${token}`
}

export function ShareReportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const { data, loading, reload } = useApiResource(listShareLinks)
  const [label, setLabel] = useState('')
  const [expiresInDays, setExpiresInDays] = useState(7)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [newLinkUrl, setNewLinkUrl] = useState<string | null>(null)
  const [revoking, setRevoking] = useState<string | null>(null)

  async function create() {
    setCreating(true)
    setCreateError(null)
    try {
      const created = await createShareLink({ label: label.trim() || undefined, expiresInDays })
      setNewLinkUrl(shareUrl(created.token))
      setLabel('')
      reload()
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : 'Не удалось создать ссылку')
    } finally { setCreating(false) }
  }

  async function revoke(link: ShareLink) {
    setRevoking(link.id)
    try {
      await revokeShareLink(link.id)
      reload()
      message.success('Ссылка отозвана')
    } catch (error) { message.error(error instanceof Error ? error.message : 'Не удалось отозвать ссылку') }
    finally { setRevoking(null) }
  }

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url)
      message.success('Ссылка скопирована')
    } catch { message.info(url) }
  }

  const columns: TableColumnsType<ShareLink> = [
    { title: 'Метка', dataIndex: 'label', render: (label: string | null) => label || '—' },
    { title: 'Создал', dataIndex: 'createdByLogin' },
    { title: 'Истекает', dataIndex: 'expiresAt', render: formatDateTime },
    { title: 'Статус', key: 'status', render: (_, link) => <Tag color={link.active ? 'green' : 'default'}>{link.active ? 'Активна' : link.revokedAt ? 'Отозвана' : 'Истекла'}</Tag> },
    { title: '', key: 'actions', render: (_, link) => link.active && (
      <Popconfirm title="Отозвать ссылку?" okText="Отозвать" cancelText="Отмена" onConfirm={() => revoke(link)}>
        <Button danger size="small" loading={revoking === link.id}>Отозвать</Button>
      </Popconfirm>
    ) },
  ]

  return <Modal title="Поделиться отчётом" open={open} onCancel={onClose} footer={null} width={640} afterClose={() => { setNewLinkUrl(null); setCreateError(null); setLabel(''); setExpiresInDays(7) }}>
    <p>Публичная read-only ссылка на отчёт (без email клиентов) — доступна без входа в панель.</p>

    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 12 }}>
      <Input placeholder="Метка (например, «для жюри»)" value={label} onChange={(event) => setLabel(event.target.value)} maxLength={200} disabled={creating} />
      <InputNumber min={1} max={90} value={expiresInDays} onChange={(value) => setExpiresInDays(value ?? 7)} addonAfter="дней" disabled={creating} style={{ width: 140 }} />
      <Button type="primary" loading={creating} onClick={() => void create()}>Создать</Button>
    </div>
    {createError && <Alert type="error" showIcon title={createError} role="alert" style={{ marginBottom: 12 }} />}
    {newLinkUrl && <Alert
      type="success" showIcon style={{ marginBottom: 12 }}
      title="Ссылка создана — сохраните сейчас, второй раз токен не показывается"
      description={<div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <Input readOnly value={newLinkUrl} onFocus={(event) => event.target.select()} />
        <Button icon={<CopyOutlined />} onClick={() => void copy(newLinkUrl)}>Копировать</Button>
      </div>}
    />}

    <Table<ShareLink> rowKey="id" columns={columns} dataSource={data ?? []} loading={loading} pagination={false} size="small" locale={{ emptyText: 'Ссылок пока нет' }} />
  </Modal>
}
