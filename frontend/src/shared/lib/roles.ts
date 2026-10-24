import type { UserRole } from '../../types/user'

// admin и superadmin — обе «административные» роли (настройки модели,
// загрузка данных, управление менеджерами доступны обеим); отличие только
// в том, что создавать/менять админов и видеть их в списке может лишь
// superadmin — это проверяется отдельно, на бэке (backend/app/crud/users.py).
export function isAdminRole(role: UserRole | undefined | null): boolean {
  return role === 'admin' || role === 'superadmin'
}

export function isSuperadmin(role: UserRole | undefined | null): boolean {
  return role === 'superadmin'
}
