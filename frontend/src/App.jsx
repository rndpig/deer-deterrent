import { useState, useEffect } from 'react'
import './App.css'
import './components/Auth.css'
import Dashboard from './components/Dashboard'
import Settings from './components/Settings'
import AuthButton from './components/AuthButton'
import CombinedArchive from './components/CombinedArchive'
import VideoLibrary from './components/VideoLibrary'
import { useAuth } from './hooks/useAuth'

function App() {
  const { user, loading, signIn, signOut } = useAuth()
  const [stats, setStats] = useState(null)
  const [settings, setSettings] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [showArchive, setShowArchive] = useState(false)
  const [selectedVideoFromArchive, setSelectedVideoFromArchive] = useState(null)
  const [ws, setWs] = useState(null)
  const [showMenu, setShowMenu] = useState(false)

  // Connect to WebSocket
  useEffect(() => {
    if (!user) return // Only connect if authenticated
    
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
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
    
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    
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
          <div className="header-actions">
            <button 
              className="btn-hamburger"
              onClick={() => setShowMenu(!showMenu)}
              aria-label="Menu"
            >
              ☰
            </button>
            {showMenu && (
              <div className="dropdown-menu">
                <button 
                  className="dropdown-item"
                  onClick={() => {
                    setActiveTab('videos')
                    setShowArchive(false)
                    setShowMenu(false)
                  }}
                >
                  🎬 Videos
                </button>
                <button 
                  className="dropdown-item"
                  onClick={() => {
                    setActiveTab('dashboard')
                    setShowArchive(true)
                    setShowMenu(false)
                  }}
                >
                  📦 Archive
                </button>
                <button 
                  className="dropdown-item"
                  onClick={() => {
                    signOut()
                    setShowMenu(false)
                  }}
                >
                  Sign Out
                </button>
              </div>
            )}
          </div>
        </div>
        <nav className="tabs">
          <button 
            className={activeTab === 'dashboard' ? 'active' : ''}
            onClick={() => { setActiveTab('dashboard'); setShowArchive(false); }}
          >
            Dashboard
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
        {activeTab === 'dashboard' && !showArchive && (
          <Dashboard 
            stats={stats} 
            settings={settings}
          />
        )}
        {activeTab === 'dashboard' && showArchive && (
          <CombinedArchive 
            onBack={() => setShowArchive(false)} 
            onAnnotate={(videoId) => {
              setSelectedVideoFromArchive(videoId)
              setShowArchive(false)
            }}
          />
        )}
        {activeTab === 'videos' && (
          <VideoLibrary 
            onStartReview={() => setActiveTab('dashboard')}
            onTrainModel={() => {}}
            onViewSnapshots={() => setActiveTab('dashboard')}
            onViewArchive={() => { setActiveTab('dashboard'); setShowArchive(true); }}
            hideSnapshotsButton={false}
          />
        )}
        {activeTab === 'settings' && (
          <Settings 
            settings={settings} 
            setSettings={setSettings}
          />
        )}
      </main>
    </div>
  )
}

export default App
