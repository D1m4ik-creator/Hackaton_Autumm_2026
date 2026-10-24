import { request } from './client'

// Роли, которые реально хранятся в БД и приходят в списке /users
// (суперадмин живёт в .env и в этот список не попадает — backend/app/crud/auth.py)
export type ManagedUserRole = 'admin' | 'manager'

export interface Manager {
  id: string
  login: string
  email: string
  role: ManagedUserRole
  createdAt: string
}

// role необязателен и имеет смысл только при создании: по умолчанию бэк
// создаёт менеджера, роль admin может задать только суперадмин (иначе 403,
// backend/app/crud/users.py:_check_can_manage) — само поле при обновлении
// не отправляем, PATCH его не принимает (backend/app/db/schemas/users.py).
export interface ManagerInput { login: string; email: string; password: string; role?: ManagedUserRole }
export type ManagerUpdateInput = Omit<ManagerInput, 'role'>

export const getManagers = () => request<Manager[]>('/users')
export const createManager = (data: ManagerInput) => request<Manager>('/users', { method: 'POST', data })
export const updateManager = (id: string, data: Partial<ManagerUpdateInput>) => request<Manager>(`/users/${encodeURIComponent(id)}`, { method: 'PATCH', data })
export const deleteManager = (id: string) => request<void>(`/users/${encodeURIComponent(id)}`, { method: 'DELETE' })
