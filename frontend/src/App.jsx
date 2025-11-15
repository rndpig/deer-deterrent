import { useState, useEffect } from 'react'
import './App.css'
import './components/Auth.css'
import Dashboard from './components/Dashboard'
import Settings from './components/Settings'
import VideoUpload from './components/VideoUpload'
import AuthButton from './components/AuthButton'
import { useAuth } from './hooks/useAuth'

function App() {
  const { user, loading, signIn, signOut } = useAuth()
  const [stats, setStats] = useState(null)
  const [settings, setSettings] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [ws, setWs] = useState(null)
  const [unauthorized, setUnauthorized] = useState(false)

  // Check for error in URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('error') === 'unauthorized') {
      setUnauthorized(true)
    }
  }, [])

  // Connect to WebSocket
  useEffect(() => {
    if (!user) return // Only connect if authenticated
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const wsUrl = apiUrl.replace('http', 'ws') + '/ws'
    
    const websocket = new WebSocket(wsUrl)
    
    websocket.onopen = () => {
      console.log('WebSocket connected')
    }
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log('WebSocket message:', data)
      
      if (data.type === 'connected') {
        setStats(data.stats)
        setSettings(data.settings)
      } else if (data.type === 'settings_updated') {
        setSettings(data.settings)
      }
    }
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    websocket.onclose = () => {
      console.log('WebSocket disconnected')
    }
    
    setWs(websocket)
    
    return () => {
      websocket.close()
    }
  }, [user])

  // Fetch initial data
  useEffect(() => {
    if (!user) return // Only fetch if authenticated
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    fetch(`${apiUrl}/api/stats`)
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error('Error fetching stats:', err))
    
    fetch(`${apiUrl}/api/settings`)
      .then(res => res.json())
      .then(data => setSettings(data))
      .catch(err => console.error('Error fetching settings:', err))
  }, [user])

  // Show loading state
  if (loading) {
    return (
      <div className="login-container">
        <div className="login-box">
          <h1>🦌 Deer Deterrent</h1>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  // Show login screen if not authenticated
  if (!user) {
    return (
      <div className="login-container">
        <div className="login-box">
          <h1>🦌 Deer Deterrent System</h1>
          <p>Secure access required</p>
          {unauthorized && (
            <div className="unauthorized-message">
              <strong>Access Denied</strong>
              <p>Only rndpig@gmail.com is authorized to access this system.</p>
            </div>
          )}
          <AuthButton user={user} signIn={signIn} signOut={signOut} />
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>🦌 Deer Deterrent System</h1>
          <AuthButton user={user} signIn={signIn} signOut={signOut} />
        </div>
        <nav className="tabs">
          <button 
            className={activeTab === 'dashboard' ? 'active' : ''}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={activeTab === 'video' ? 'active' : ''}
            onClick={() => setActiveTab('video')}
          >
            Video Analysis
          </button>
          <button 
            className={activeTab === 'settings' ? 'active' : ''}
            onClick={() => setActiveTab('settings')}
          >
            Settings
          </button>
        </nav>
      </header>

      <main className="app-content">
        {activeTab === 'dashboard' && <Dashboard stats={stats} settings={settings} />}
        {activeTab === 'video' && <VideoUpload />}
        {activeTab === 'settings' && <Settings settings={settings} setSettings={setSettings} />}
      </main>
    </div>
  )
}

export default App
