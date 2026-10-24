import axios from 'axios'
import type { AxiosError, AxiosRequestConfig, Method } from 'axios'
import { message } from 'antd'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
// Все роуты бэка, кроме /metrics, смонтированы под этим префиксом (backend/app/main.py)
const API_PREFIX = '/api/v1'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type RetriableConfig = AxiosRequestConfig & { _retry?: boolean }

export const http = axios.create({
  baseURL: `${API_URL}${API_PREFIX}`,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

function extractMessage(data: unknown): string | null {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => (d as { msg?: string }).msg).filter(Boolean).join(', ')
    }
  }
  return null
}

let refreshPromise: Promise<void> | null = null

function refreshSession(): Promise<void> {
  refreshPromise ??= http.post('/auth/refresh').then(() => undefined).finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

// login/refresh/logout — это сами операции с сессией: ретраить их через
// refresh-and-retry бессмысленно (логичный результат неверного пароля или
// протухшего refresh-токена — просто ошибка, а не рекурсивный refresh).
// /auth/me сюда НЕ входит — это проверка "залогинен ли я", и именно для
// неё refresh-and-retry нужен больше всего (короткоживущий access-токен
// истёк — молча обновляем и повторяем запрос, а не разлогиниваем).
const AUTH_ACTION_PATTERN = /\/auth\/(login|refresh|logout)(?:[/?]|$)/

function isAuthAction(url: string | undefined): boolean {
  return !!url && AUTH_ACTION_PATTERN.test(url)
}

function isCurrentUserCheck(url: string | undefined): boolean {
  return !!url && /\/auth\/me(?:[/?]|$)/.test(url)
}

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableConfig | undefined
    const url = originalRequest?.url

    if (!error.response) {
      message.error('Нет соединения с сервером. Проверьте интернет и попробуйте снова.')
      return Promise.reject(new ApiError(0, 'Network error'))
    }

    const { status } = error.response

    if (status === 401 && originalRequest && !originalRequest._retry && !isAuthAction(url)) {
      originalRequest._retry = true
      try {
        await refreshSession()
        return await http(originalRequest)
      } catch {
        // refresh тоже не удался — отдаём исходную ошибку ниже
      }
    }

    const apiMessage = extractMessage(error.response.data) ?? error.message ?? 'Request failed'

    // Своя ошибка на форме логина (login/refresh/logout) и тихий статус
    // "ещё не залогинен" (me) не дублируем глобальным тостом.
    if (!isAuthAction(url) && !isCurrentUserCheck(url)) {
      if (status >= 500) {
        message.error('Сервер временно недоступен. Попробуйте позже.')
      } else if (status !== 401) {
        message.error(apiMessage)
      }
    }

    return Promise.reject(new ApiError(status, apiMessage))
  },
)

export async function request<T>(
  path: string,
  options: { method?: Method; data?: unknown } = {},
): Promise<T> {
  const response = await http.request<T>({
    url: path,
    method: options.method ?? 'GET',
    data: options.data,
  })
  return response.data
}
