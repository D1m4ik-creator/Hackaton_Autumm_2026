import { useState } from 'react'
import type { FormEvent } from 'react'
import { EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ApiError, OIDC_LOGIN_URL } from '../api/client'
import { getOidcStatus } from '../api/auth'
import { useApiResource } from '../api/useApiResource'
import { AuthLayout } from '../components/AuthLayout'

const OIDC_ERROR_MESSAGES: Record<string, string> = {
  oidc_failed: 'Не удалось войти через Authentik. Попробуйте ещё раз.',
  oidc_no_account: 'Для этого аккаунта нет доступа в панели — обратитесь к администратору.',
  oidc_unavailable: 'Authentik сейчас недоступен. Попробуйте через минуту или войдите по логину и паролю.',
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const oidcError = searchParams.get('error')
  const { data: oidcStatus } = useApiResource(getOidcStatus)
  const [loginValue, setLoginValue] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(oidcError ? (OIDC_ERROR_MESSAGES[oidcError] ?? null) : null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isOidcRedirecting, setIsOidcRedirecting] = useState(false)

  // Не <a href> — /auth/oidc/login не идемпотентен (пишет state/nonce в сессию
  // на каждый вызов), а браузер может спекулятивно подгрузить href по ховеру
  // ещё до клика (prerender/prefetch). Второй, "призрачный" вызов перезаписывает
  // state в сессионной cookie раньше настоящего — колбэк потом видит чужой state
  // и падает с oidc_failed. Кнопка с явной навигацией по клику и блокировкой
  // от повторного клика этого не допускает.
  function startOidcLogin() {
    setIsOidcRedirecting(true)
    window.location.href = OIDC_LOGIN_URL
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(loginValue, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout title="С возвращением" subtitle="Войдите, чтобы продолжить">
      <form onSubmit={handleSubmit}>
        <div className="auth-field">
          <label htmlFor="login">Логин</label>
          <input
            id="login"
            type="text"
            placeholder="Логин *"
            value={loginValue}
            onChange={(e) => setLoginValue(e.target.value)}
            required
          />
        </div>
        <div className="auth-field">
          <label htmlFor="password">Пароль</label>
          <div className="auth-password">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Пароль *"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="auth-password__toggle"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
              aria-pressed={showPassword}
              title={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
            >
              {showPassword ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            </button>
          </div>
        </div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button type="submit" className="auth-submit" disabled={isSubmitting}>
          Войти
        </button>
      </form>
      {oidcStatus?.enabled && <>
        <div className="auth-divider"><span>или</span></div>
        <button type="button" className="auth-submit auth-submit--secondary" onClick={startOidcLogin} disabled={isOidcRedirecting}>
          Войти через Authentik
        </button>
      </>}
    </AuthLayout>
  )
}
