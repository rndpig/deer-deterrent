import { useEffect, useState } from 'react'

export function useAuth() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const response = await fetch('/api/auth/session')
      const data = await response.json()
      setUser(data.user || null)
    } catch (error) {
      console.error('Auth check failed:', error)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const signIn = () => {
    window.location.href = '/api/auth/signin'
  }

  const signOut = async () => {
    await fetch('/api/auth/signout', { method: 'POST' })
    window.location.href = '/'
  }

  return { user, loading, signIn, signOut }
}
