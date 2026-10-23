import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../api/client'
import { AuthLayout } from '../components/AuthLayout'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(name, email, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрироваться')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout
      title="Создать аккаунт"
      subtitle="Укажите данные, чтобы начать"
      switchHint="Уже есть аккаунт?"
      switchLinkLabel="Войти"
      switchLinkTo="/login"
    >
      <form onSubmit={handleSubmit}>
        <div className="auth-field">
          <label htmlFor="name">Имя</label>
          <input
            id="name"
            type="text"
            placeholder="Имя *"
            value={name}
            onChange={(e) => setName(e.target.value)}
            minLength={2}
            maxLength={50}
            required
          />
        </div>
        <div className="auth-field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            placeholder="Email *"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="auth-field">
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            placeholder="Пароль *"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <p className="auth-field__hint">
            Минимум 8 символов: заглавная и строчная буквы, цифра и спецсимвол
          </p>
        </div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button type="submit" className="auth-submit" disabled={isSubmitting}>
          Зарегистрироваться
        </button>
      </form>
    </AuthLayout>
  )
}
