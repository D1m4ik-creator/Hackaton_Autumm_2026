import axios from 'axios'
import { API_BASE_URL } from './client'

// Отдельный клиент для публичного read-only отчёта (frontend/src/pages/public-report):
// токен передаётся в query, не в cookie — withCredentials и refresh-интерсептор
// основного `http` (api/client.ts) здесь не нужны и не должны срабатывать.
export const publicHttp = axios.create({ baseURL: API_BASE_URL })
