import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import * as authApi from '../api/auth'
import type { User } from '../types/user'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (login: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

// 401 здесь уже означает, что интерцептор в api/client.ts попробовал
// обновить сессию через /auth/refresh и всё равно не смог — сессии нет.
async function fetchCurrentUser(): Promise<User | null> {
  try {
    return await authApi.getCurrentUser()
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (login: string, password: string) => {
    await authApi.login({ login, password })
    setUser(await authApi.getCurrentUser())
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
