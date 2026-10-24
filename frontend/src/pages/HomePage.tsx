import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function HomePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div>
      <h1>Привет, {user?.login}</h1>
      <button type="button" onClick={handleLogout}>
        Выйти
      </button>
    </div>
  )
}
