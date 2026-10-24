// Соответствует CurrentUser на бэке (backend/app/db/schemas/auth.py)
export type UserRole = 'admin' | 'manager'

export interface User {
  login: string
  role: UserRole
  email: string | null
}
