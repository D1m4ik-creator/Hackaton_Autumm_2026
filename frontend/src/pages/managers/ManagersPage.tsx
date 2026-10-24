import { Alert, App, Button, Form, Input, Modal, Popconfirm, Select, Space, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { useState } from 'react'
import { createManager, deleteManager, getManagers, updateManager } from '../../api/users'
import type { Manager, ManagerInput } from '../../api/users'
import { useApiResource } from '../../api/useApiResource'
import { useAuth } from '../../context/AuthContext'
import { formatDateTime } from '../../shared/lib/format'
import { isSuperadmin } from '../../shared/lib/roles'
import { DashboardShell } from '../../widgets/dashboard-shell'
import './managers.css'

const roleLabels: Record<Manager['role'], string> = { admin: 'Администратор', manager: 'Менеджер' }

export function ManagersPage({ onSignOut }: { onSignOut?: () => Promise<void> }) {
  const { user } = useAuth()
  // Только суперадмин создаёт админов и видит их в списке (backend/app/crud/users.py:
  // list_users фильтрует по role="manager" для всех остальных) — обычному админу
  // выбор роли вообще не нужен, он всегда создаёт менеджера.
  const canManageAdmins = isSuperadmin(user?.role)
  const { data, loading, error, reload } = useApiResource(getManagers)
  const { message } = App.useApp()
  const [form] = Form.useForm<ManagerInput>()
  const [editing, setEditing] = useState<Manager | null>(null)
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  const pageTitle = canManageAdmins ? 'Управление пользователями' : 'Управление менеджерами'
  const addLabel = canManageAdmins ? 'Добавить пользователя' : 'Добавить менеджера'

  function showEditor(manager: Manager | null) {
    setEditing(manager)
    setSaveError(null)
    form.resetFields()
    form.setFieldsValue({ login: manager?.login ?? '', email: manager?.email ?? '', password: '', role: manager?.role ?? 'manager' })
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
        await createManager({ login, email, password: values.password, role: canManageAdmins ? values.role : undefined })
      }
      setOpen(false)
      form.resetFields()
      reload()
      message.success(editing ? 'Пользователь обновлён' : 'Пользователь создан')
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Не удалось сохранить пользователя')
    } finally { setSaving(false) }
  }

  async function remove(manager: Manager) {
    setDeleting(manager.id)
    try {
      await deleteManager(manager.id)
      reload()
      message.success('Пользователь удалён')
    } catch { /* The API client displays the error. */ }
    finally { setDeleting(null) }
  }

  const columns: TableColumnsType<Manager> = [
    { title: 'Логин', dataIndex: 'login' },
    { title: 'Email', dataIndex: 'email' },
    ...(canManageAdmins ? [{ title: 'Роль', dataIndex: 'role', render: (role: Manager['role']) => roleLabels[role] }] : []),
    { title: 'Создан', dataIndex: 'createdAt', render: formatDateTime },
    { title: 'Действия', key: 'actions', render: (_, manager) => <Space wrap>
      <Button onClick={() => showEditor(manager)}>Изменить</Button>
      <Popconfirm title={`Удалить пользователя ${manager.login}?`} description="Его сессии будут закрыты." okText="Удалить" cancelText="Отмена" onConfirm={() => remove(manager)}>
        <Button danger loading={deleting === manager.id}>Удалить</Button>
      </Popconfirm>
    </Space> },
  ]

  return <DashboardShell onSignOut={onSignOut}>
    <header className="managers-heading"><h1>{pageTitle}</h1><Button type="primary" onClick={() => showEditor(null)}>{addLabel}</Button></header>
    {error && <Alert type="error" title={error} action={<Button onClick={reload}>Повторить</Button>} />}
    <Table<Manager> rowKey="id" columns={columns} dataSource={data ?? []} loading={loading} scroll={{ x: 700 }} locale={{ emptyText: canManageAdmins ? 'Пользователей пока нет' : 'Менеджеров пока нет' }} />
    <Modal forceRender title={editing ? 'Изменить пользователя' : addLabel} open={open} confirmLoading={saving} okText="Сохранить" cancelText="Отмена" onOk={() => form.submit()} onCancel={() => { if (!saving) { setOpen(false); form.resetFields() } }}>
      <Form form={form} layout="vertical" onFinish={save} disabled={saving}>
        <Form.Item name="login" label="Логин" rules={[{ required: true, message: 'Укажите логин' }, { min: 3, max: 50, message: 'От 3 до 50 символов' }, { pattern: /^[A-Za-z0-9_.-]+$/, message: 'Латинские буквы, цифры, _, . и -' }]}><Input autoComplete="off" maxLength={50} /></Form.Item>
        <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Укажите email' }, { type: 'email', message: 'Укажите корректный email' }]}><Input type="email" autoComplete="off" /></Form.Item>
        {!editing && canManageAdmins && <Form.Item name="role" label="Роль" initialValue="manager" rules={[{ required: true, message: 'Выберите роль' }]}>
          <Select options={[{ value: 'manager', label: roleLabels.manager }, { value: 'admin', label: roleLabels.admin }]} />
        </Form.Item>}
        <Form.Item name="password" label={editing ? 'Новый пароль (необязательно)' : 'Пароль'} rules={[{ required: !editing, message: 'Укажите пароль' }, { min: 8, max: 128, message: 'От 8 до 128 символов' }]}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        {saveError && <Alert type="error" title={saveError} role="alert" />}
      </Form>
    </Modal>
  </DashboardShell>
}
