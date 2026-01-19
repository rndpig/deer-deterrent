import { useEffect, useState } from 'react'
import { auth, googleProvider } from '../firebase'
import { signInWithPopup, signOut as firebaseSignOut, onAuthStateChanged } from 'firebase/auth'

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
      return
    }

    // Subscribe to Firebase auth state changes
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      if (firebaseUser) {
        setUser({
          email: firebaseUser.email,
          name: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL
        })
      } else {
        setUser(null)
      }
      setLoading(false)
    })

    return () => unsubscribe()
  }, [authDisabled])

  const signIn = async () => {
    try {
      await signInWithPopup(auth, googleProvider)
    } catch (error) {
      console.error('Sign in failed:', error)
    }
  }

  const signOut = async () => {
    try {
      await firebaseSignOut(auth)
    } catch (error) {
      console.error('Sign out failed:', error)
    }
  }

  return { user, loading, signIn, signOut }
}
