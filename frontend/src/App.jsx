import { useState, useEffect } from 'react'
import './App.css'
import './components/Auth.css'
import Dashboard from './components/Dashboard'
import Stats from './components/Stats'
import Settings from './components/Settings'
import AuthButton from './components/AuthButton'
import VideoLibrary from './components/VideoLibrary'
import { useAuth } from './hooks/useAuth'
import { apiFetch, API_URL } from './api'

function App() {
  const { user, loading, signIn, signOut } = useAuth()
  const [stats, setStats] = useState(null)
  const [settings, setSettings] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  const [ws, setWs] = useState(null)
  const [diskUsage, setDiskUsage] = useState(null)

  // Connect to WebSocket
  useEffect(() => {
    if (!user) return // Only connect if authenticated
    
    // Get Firebase token for WebSocket authentication
    const connectWebSocket = async () => {
      try {
        const token = await user.getIdToken()
        const wsUrl = API_URL.replace('http', 'ws') + '/ws?token=' + encodeURIComponent(token)
        
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
        
        return websocket
      } catch (error) {
        console.error('Failed to get token for WebSocket:', error)
        return null
      }
    }
    
    let websocket = null
    connectWebSocket().then(ws => { websocket = ws })
    
    return () => {
      if (websocket) websocket.close()
    }
  }, [user])

  // Fetch initial data
  useEffect(() => {
    if (!user) return // Only fetch if authenticated
    
    apiFetch('/api/stats')
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error('Error fetching stats:', err))
    
    apiFetch('/api/settings')
      .then(res => res.json())
      .then(data => setSettings(data))
      .catch(err => console.error('Error fetching settings:', err))
    
    apiFetch('/api/disk-usage')
      .then(res => res.json())
      .then(data => setDiskUsage(data))
      .catch(err => console.error('Error fetching disk usage:', err))
  }, [user])

  // Cross-component navigation: Dashboard chase-video badge dispatches a 'navigate-tab'
  // CustomEvent to jump to the Videos tab (and optionally focus a specific video).
  useEffect(() => {
    const handler = (e) => {
      const tab = e?.detail?.tab
      if (tab) setActiveTab(tab)
    }
    window.addEventListener('navigate-tab', handler)
    return () => window.removeEventListener('navigate-tab', handler)
  }, [])

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
            {diskUsage && (
              <div className="disk-bar-wrapper" title={`${diskUsage.free_gb} GB free of ${diskUsage.total_gb} GB (${diskUsage.percent_used}% used)`}>
                <div className="disk-bar-track">
                  <div
                    className={`disk-bar-fill ${diskUsage.percent_used > 85 ? 'disk-critical' : diskUsage.percent_used > 70 ? 'disk-warn' : 'disk-ok'}`}
                    style={{ width: `${Math.min(diskUsage.percent_used, 100)}%` }}
                  />
                </div>
                <span className="disk-bar-label">{diskUsage.free_gb}GB free</span>
              </div>
            )}
          </div>
        </div>
        <nav className="tabs">
          <button 
            className={activeTab === 'dashboard' ? 'active' : ''}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={activeTab === 'videos' ? 'active' : ''}
            onClick={() => setActiveTab('videos')}
          >
            Videos
          </button>
          <button 
            className={activeTab === 'stats' ? 'active' : ''}
            onClick={() => setActiveTab('stats')}
          >
            Stats
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
        {activeTab === 'dashboard' && (
          <Dashboard 
            stats={stats} 
            settings={settings}
          />
        )}
        {activeTab === 'videos' && (
          <VideoLibrary />
        )}
        {activeTab === 'stats' && (
          <Stats />
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
