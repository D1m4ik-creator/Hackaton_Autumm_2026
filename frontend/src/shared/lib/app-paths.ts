// Легаси-пути "/dashboard", "/clients", "/model-settings" (см. app/App.tsx)
// — чистые редиректы на "/" и "/app/*" и никогда не рендерят контент, но
// виджеты всё ещё строят ссылки по текущему pathname, а не жёстко на "/app/*",
// на случай прямого использования вне SessionLayout.
export function isAppRoute(pathname: string): boolean {
  return pathname === '/' || pathname.startsWith('/app/')
}

export function dashboardPath(pathname: string): string {
  return isAppRoute(pathname) ? '/' : '/dashboard'
}

export function clientsPath(pathname: string): string {
  return isAppRoute(pathname) ? '/app/clients' : '/clients'
}

export function clientDetailPath(pathname: string, accountId: number | string): string {
  return `${clientsPath(pathname)}/${accountId}`
}

export function modelSettingsPath(pathname: string): string {
  return isAppRoute(pathname) ? '/app/model-settings' : '/model-settings'
}
