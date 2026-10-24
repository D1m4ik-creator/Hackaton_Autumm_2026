import { Alert, App, Button, Form, Input, Modal, Popconfirm, Space, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'
import { createManager, deleteManager, getManagers, updateManager } from '../../api/users'
import type { Manager, ManagerInput } from '../../api/users'
import { useApiResource } from '../../api/useApiResource'
import { formatDateTime } from '../../shared/lib/format'
import { DashboardShell } from '../../widgets/dashboard-shell'
import './managers.css'

export function ManagersPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { data, loading, error, reload } = useApiResource(getManagers)
  const { message } = App.useApp()
  const [form] = Form.useForm<ManagerInput>()
  const [editing, setEditing] = useState<Manager | null>(null)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  function showEditor(manager: Manager | null) {
    setEditing(manager)
    setSaveError(null)
    form.resetFields()
    form.setFieldsValue({ login: manager?.login ?? '', email: manager?.email ?? '', password: '' })
    setOpen(true)
  }

  async function save(values: ManagerInput) {
    setSaving(true)
    setSaveError(null)
    try {
      const login = values.login.trim(), email = values.email.trim()
      if (editing) {
        await updateManager(editing.id, {
          ...(login !== editing.login ? { login } : {}),
          ...(email !== editing.email ? { email } : {}),
          ...(values.password ? { password: values.password } : {}),
        })
      } else {
        await createManager({ login, email, password: values.password })
      }
      setOpen(false)
      form.resetFields()
      reload()
      message.success(editing ? 'Менеджер обновлён' : 'Менеджер создан')
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Не удалось сохранить менеджера')
    } finally { setSaving(false) }
  }

  async function remove(manager: Manager) {
    setDeleting(manager.id)
    try {
      await deleteManager(manager.id)
      reload()
      message.success('Менеджер удалён')
    } catch { /* The API client displays the error. */ }
    finally { setDeleting(null) }
  }

  const columns: TableColumnsType<Manager> = [
    { title: 'Логин', dataIndex: 'login' },
    { title: 'Email', dataIndex: 'email' },
    { title: 'Создан', dataIndex: 'createdAt', render: formatDateTime },
    { title: 'Действия', key: 'actions', render: (_, manager) => <Space wrap>
      <Button onClick={() => showEditor(manager)}>Изменить</Button>
      <Popconfirm title={`Удалить менеджера ${manager.login}?`} description="Его сессии будут закрыты." okText="Удалить" cancelText="Отмена" onConfirm={() => remove(manager)}>
        <Button danger loading={deleting === manager.id}>Удалить</Button>
      </Popconfirm>
    </Space> },
  ]

  return <DashboardShell onSignOut={onSignOut}>
    <header className="managers-heading"><h1>Управление менеджерами</h1><Button type="primary" onClick={() => showEditor(null)}>Добавить менеджера</Button></header>
    {error && <Alert type="error" title={error} action={<Button onClick={reload}>Повторить</Button>} />}
    <Table<Manager> rowKey="id" columns={columns} dataSource={data ?? []} loading={loading} scroll={{ x: 700 }} locale={{ emptyText: 'Менеджеров пока нет' }} />
    <Modal forceRender title={editing ? 'Изменить менеджера' : 'Добавить менеджера'} open={open} confirmLoading={saving} okText="Сохранить" cancelText="Отмена" onOk={() => form.submit()} onCancel={() => { if (!saving) { setOpen(false); form.resetFields() } }}>
      <Form form={form} layout="vertical" onFinish={save} disabled={saving}>
        <Form.Item name="login" label="Логин" rules={[{ required: true, message: 'Укажите логин' }, { min: 3, max: 50, message: 'От 3 до 50 символов' }, { pattern: /^[A-Za-z0-9_.-]+$/, message: 'Латинские буквы, цифры, _, . и -' }]}><Input autoComplete="off" maxLength={50} /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Укажите email' }, { type: 'email', message: 'Укажите корректный email' }]}><Input type="email" autoComplete="off" /></Form.Item>
        <Form.Item name="password" label={editing ? 'Новый пароль (необязательно)' : 'Пароль'} rules={[{ required: !editing, message: 'Укажите пароль' }, { min: 8, max: 128, message: 'От 8 до 128 символов' }]}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        {saveError && <Alert type="error" title={saveError} role="alert" />}
      </Form>
    </Modal>
  </DashboardShell>
}
