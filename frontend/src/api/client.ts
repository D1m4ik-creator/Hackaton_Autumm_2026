import axios from 'axios'
import type { AxiosError, AxiosRequestConfig, Method } from 'axios'
import { message } from 'antd'
import { formatApiError } from './error-message'

const API_URL = (import.meta.env.VITE_API_URL ?? `${window.location.protocol}//${window.location.hostname}:8000`).replace(/\/$/, '')
// Все роуты бэка, кроме /metrics, смонтированы под этим префиксом (backend/app/main.py)
const API_PREFIX = '/api/v1'
export const API_BASE_URL = `${API_URL}${API_PREFIX}`
export const METRICS_URL = `${API_URL}/metrics`
// Grafana — отдельный сервис (ops/README.md), не проксируется через API
export const GRAFANA_URL = (import.meta.env.VITE_GRAFANA_URL ?? `${window.location.protocol}//${window.location.hostname}:3001`).replace(/\/$/, '')
// Полный переход браузера (не XHR) — backend/app/routers/oidc.py редиректит на Authentik
export const OIDC_LOGIN_URL = `${API_BASE_URL}/auth/oidc/login`

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type RetriableConfig = AxiosRequestConfig & { _retry?: boolean }

export const http = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

let refreshPromise: Promise<void> | null = null

export function refreshSession(): Promise<void> {
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

// Тихая фоновая проверка "доступен ли вход через OIDC" (рисовать ли кнопку
// на LoginPage) — не действие пользователя, 404/5xx тут не должны всплывать
// тостом (например, пока бэк со свежим /auth/oidc/* ещё не пересобран).
function isOidcStatusCheck(url: string | undefined): boolean {
  return !!url && /\/auth\/oidc\/status(?:[/?]|$)/.test(url)
}

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableConfig | undefined
    const url = originalRequest?.url

    if (!error.response) {
      message.error('Нет соединения с сервером. Проверьте интернет и попробуйте снова.')
      return Promise.reject(new ApiError(0, 'Нет соединения с сервером'))
    }

    const { status } = error.response

    if (status === 401 && originalRequest && !originalRequest._retry && !isAuthAction(url)) {
      originalRequest._retry = true
      try {
        await refreshSession()
      } catch (refreshError) {
        if (refreshError instanceof ApiError && refreshError.status === 401) {
          window.dispatchEvent(new Event('session-expired'))
        }
        // Сетевые ошибки, 429 и 5xx не подтверждают истечение сессии.
        return Promise.reject(refreshError)
      }
      // Повторный запрос не оборачиваем в этот же try — если он упадёт по
      // другой причине (например 500), его ошибка должна дойти до вызывающего
      // кода как есть, а не быть подменена исходной 401-ошибкой ниже.
      return http(originalRequest)
    }

    const apiMessage = formatApiError(status, error.response.data, url)
    if (status === 401 && !isAuthAction(url)) window.dispatchEvent(new Event('session-expired'))

    // Своя ошибка на форме логина (login/refresh/logout), тихий статус
    // "ещё не залогинен" (me) и фоновая проверка доступности OIDC не
    // дублируем глобальным тостом.
    if (!isAuthAction(url) && !isCurrentUserCheck(url) && !isOidcStatusCheck(url)) {
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
  options: { method?: Method; data?: unknown; params?: Record<string, unknown> } = {},
): Promise<T> {
  const response = await http.request<T>({
    url: path,
    method: options.method ?? 'GET',
    data: options.data,
    params: options.params,
  })
  return response.data
}
