export default function AuthButton({ user, signIn, signOut }) {
  if (!user) {
    return (
      <button onClick={signIn} className="auth-button sign-in">
        Sign in with Google
      </button>
    )
  }

  return (
    <div className="user-info">
      <img src={user.image} alt={user.name} className="user-avatar" />
      <span className="user-name">{user.name}</span>
      <button onClick={signOut} className="auth-button sign-out">
        Sign Out
      </button>
    </div>
  )
}
