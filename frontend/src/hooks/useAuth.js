import { useEffect, useState } from 'react'

export function useAuth() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Check if auth is disabled for local development
  const authDisabled = import.meta.env.VITE_DISABLE_AUTH === 'true'

  useEffect(() => {
    if (authDisabled) {
      // Mock user for local development
      setUser({ email: 'local-user@localhost', name: 'Local User' })
      setLoading(false)
    } else {
      checkAuth()
    }
  }, [authDisabled])

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
    console.log('Sign in clicked, redirecting to:', '/api/auth/signin')
    window.location.href = '/api/auth/signin'
  }

  const signOut = async () => {
    await fetch('/api/auth/signout', { method: 'POST' })
    window.location.href = '/'
  }

  return { user, loading, signIn, signOut }
}
