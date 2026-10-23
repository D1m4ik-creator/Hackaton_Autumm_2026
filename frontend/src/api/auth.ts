import { request } from './client'
import type { User } from '../types/user'

export interface LoginPayload {
  email: string
  password: string
}

export function login(payload: LoginPayload): Promise<{ message: string }> {
  return request('/auth/login_user/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function logout(): Promise<{ message: string }> {
  return request('/auth/logout/', { method: 'POST' })
}

export function refresh(): Promise<{ status: string }> {
  return request('/auth/refresh/', { method: 'POST' })
}

export function getCurrentUser(): Promise<User> {
  return request('/users/me/')
}
