export default function AuthButton({ user, signIn, signOut }) {
  if (!user) {
    return (
      <button onClick={signIn} className="auth-button sign-in">
        Sign in with Google
      </button>
    )
  }

  return (
    <button onClick={signOut} className="auth-button sign-out">
      Sign Out
    </button>
  )
}


