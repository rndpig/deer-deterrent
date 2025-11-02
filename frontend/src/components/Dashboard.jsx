import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings }) {
  const [recentDetections, setRecentDetections] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    fetch(`${apiUrl}/api/detections/recent?hours=24`)
      .then(res => res.json())
      .then(data => {
        setRecentDetections(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Error fetching recent detections:', err)
        setLoading(false)
      })
  }, [])

  const loadDemoData = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/demo/load`, { method: 'POST' })
      const data = await response.json()
      console.log('Demo data loaded:', data)
      window.location.reload()
    } catch (err) {
      console.error('Error loading demo data:', err)
      alert('Error loading demo data. Make sure backend is running and demo images exist.')
    }
  }

  return (
    <div className="dashboard">
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Detections</h3>
          <p className="stat-value">{stats?.total_detections || 0}</p>
        </div>
        <div className="stat-card">
          <h3>Total Deer</h3>
          <p className="stat-value">{stats?.total_deer || 0}</p>
        </div>
        <div className="stat-card">
          <h3>Sprinklers Activated</h3>
          <p className="stat-value">{stats?.sprinklers_activated || 0}</p>
        </div>
        <div className="stat-card">
          <h3>Season Status</h3>
          <p className="stat-value status">
            {stats?.current_season ? '✅ Active' : '❄️ Off-Season'}
          </p>
        </div>
      </div>

      <div className="system-status">
        <h2>System Status</h2>
        <div className="status-info">
          <div className="status-item">
            <span className="label">Mode:</span>
            <span className="value">{settings?.dry_run ? '🧪 Demo Mode' : '💦 Live Mode'}</span>
          </div>
          <div className="status-item">
            <span className="label">Confidence Threshold:</span>
            <span className="value">{settings?.confidence_threshold ? `${(settings.confidence_threshold * 100).toFixed(0)}%` : 'N/A'}</span>
          </div>
          <div className="status-item">
            <span className="label">Season:</span>
            <span className="value">{settings?.season_start} to {settings?.season_end}</span>
          </div>
          <div className="status-item">
            <span className="label">Sprinkler Duration:</span>
            <span className="value">{settings?.sprinkler_duration}s</span>
          </div>
        </div>
      </div>

      <div className="recent-activity">
        <div className="section-header">
          <h2>Recent Activity (Last 24 Hours)</h2>
          <button className="demo-button" onClick={loadDemoData}>
            Load Demo Data
          </button>
        </div>
        
        {loading ? (
          <p>Loading...</p>
        ) : recentDetections.length === 0 ? (
          <div className="empty-state">
            <p>No recent detections</p>
            <p className="hint">Click "Load Demo Data" to see example detections</p>
          </div>
        ) : (
          <div className="detection-cards">
            {recentDetections.slice(0, 5).map((detection, index) => (
              <div key={index} className="detection-card">
                <div className="detection-header">
                  <span className="timestamp">
                    {new Date(detection.timestamp).toLocaleString()}
                  </span>
                  <span className="deer-count">
                    🦌 {detection.deer_count} deer
                  </span>
                </div>
                <div className="detection-body">
                  <p><strong>Location:</strong> {detection.zone_name}</p>
                  <p><strong>Confidence:</strong> {(detection.max_confidence * 100).toFixed(1)}%</p>
                  <p><strong>Action:</strong> {detection.sprinklers_activated ? '💦 Sprinklers activated' : '🧪 Demo mode - no action'}</p>
                </div>
                {detection.image_path && (
                  <div className="detection-image">
                    <img 
                      src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${detection.image_path}`} 
                      alt="Detection" 
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
