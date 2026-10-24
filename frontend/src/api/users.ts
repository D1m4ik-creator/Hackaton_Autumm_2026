import { request } from './client'

export interface Manager {
  id: string
  login: string
  email: string
  role: 'manager'
  createdAt: string
}

export interface ManagerInput { login: string; email: string; password: string }
export const getManagers = () => request<Manager[]>('/users')
export const createManager = (data: ManagerInput) => request<Manager>('/users', { method: 'POST', data })
export const updateManager = (id: string, data: Partial<ManagerInput>) => request<Manager>(`/users/${encodeURIComponent(id)}`, { method: 'PATCH', data })
export const deleteManager = (id: string) => request<void>(`/users/${encodeURIComponent(id)}`, { method: 'DELETE' })
