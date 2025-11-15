import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings }) {
  const [detections, setDetections] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('last24h') // last24h, last7d, all
  const [demoMode, setDemoMode] = useState(false)
  const [reviewingId, setReviewingId] = useState(null)

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    const endpoint = filter === 'all' 
      ? `${apiUrl}/api/detections?limit=100`
      : `${apiUrl}/api/detections/recent?hours=${filter === 'last24h' ? 24 : 168}`
    
    fetch(endpoint)
      .then(res => res.json())
      .then(data => {
        setDetections(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Error fetching detections:', err)
        setLoading(false)
      })
  }, [filter])

  const loadDemoData = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      setLoading(true)
      const response = await fetch(`${apiUrl}/api/demo/load`, { method: 'POST' })
      
      if (!response.ok) {
        throw new Error(`Failed to load demo data: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('Demo data loaded:', data)
      
      // Refresh the detections by re-fetching
      const endpoint = filter === 'all' 
        ? `${apiUrl}/api/detections?limit=100`
        : `${apiUrl}/api/detections/recent?hours=${filter === 'last24h' ? 24 : 168}`
      
      const refreshResponse = await fetch(endpoint)
      const refreshData = await refreshResponse.json()
      setDetections(refreshData)
      setDemoMode(true)
      setLoading(false)
    } catch (err) {
      console.error('Error loading demo data:', err)
      setLoading(false)
      alert('❌ Error loading demo data. Make sure backend is running.')
    }
  }

  const clearData = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      setLoading(true)
      const response = await fetch(`${apiUrl}/api/demo/clear`, { method: 'POST' })
      
      if (!response.ok) {
        throw new Error(`Failed to clear data: ${response.statusText}`)
      }
      
      console.log('Data cleared')
      
      // Refresh to show empty state
      setDetections([])
      setDemoMode(false)
      setLoading(false)
    } catch (err) {
      console.error('Error clearing data:', err)
      setLoading(false)
      alert('❌ Error clearing data. Make sure backend is running.')
    }
  }

  const toggleMode = async () => {
    if (demoMode) {
      await clearData()
    } else {
      await loadDemoData()
    }
  }

  const reviewDetection = async (detectionId, reviewType, correctedCount = null) => {
    setReviewingId(detectionId)
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const payload = {
        detection_id: detectionId,
        review_type: reviewType,
        reviewer: 'user'
      }
      
      if (correctedCount !== null) {
        payload.corrected_deer_count = correctedCount
      }

      const response = await fetch(`${apiUrl}/api/detections/${detectionId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      if (response.ok) {
        // Update the detection in state to show it's been reviewed
        setDetections(prev => prev.map(d => 
          d.id === detectionId ? { ...d, reviewed: true, review_type: reviewType } : d
        ))
      } else {
        alert('❌ Error submitting review')
      }
    } catch (error) {
      console.error('Error reviewing detection:', error)
      alert('❌ Error submitting review')
    } finally {
      setReviewingId(null)
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

      <div className="detection-history">
        <div className="history-header">
          <h2>Detection History</h2>
          <div className="header-actions">
            <div className="filter-buttons">
              <button 
                className={filter === 'last24h' ? 'active' : ''}
                onClick={() => setFilter('last24h')}
              >
                Last 24 Hours
              </button>
              <button 
                className={filter === 'last7d' ? 'active' : ''}
                onClick={() => setFilter('last7d')}
              >
                Last 7 Days
              </button>
              <button 
                className={filter === 'all' ? 'active' : ''}
                onClick={() => setFilter('all')}
              >
                All Time
              </button>
            </div>
            <button 
              className={`mode-toggle ${demoMode ? 'demo-active' : ''}`} 
              onClick={toggleMode}
              title={demoMode ? 'Switch to Live Mode' : 'Load Demo Data'}
            >
              {demoMode ? '🧪 Demo Mode - Switch to Live' : '💦 Live Mode - Load Demo'}
            </button>
          </div>
        </div>
        
        {loading ? (
          <div className="loading">Loading...</div>
        ) : detections.length === 0 ? (
          <div className="empty-state">
            <p>No detections found</p>
            <p className="hint">Click "Load Demo Data" to see example detections or wait for deer to be detected</p>
          </div>
        ) : (
          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Camera</th>
                  <th>Zone</th>
                  <th>Deer Count</th>
                  <th>Confidence</th>
                  <th>Action</th>
                  <th>Image</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {detections.map((detection, index) => (
                  <tr key={index}>
                    <td>{new Date(detection.timestamp).toLocaleString()}</td>
                    <td>{detection.camera_name}</td>
                    <td>{detection.zone_name}</td>
                    <td className="deer-count">🦌 {detection.deer_count}</td>
                    <td className="confidence">
                      {(detection.max_confidence * 100).toFixed(1)}%
                    </td>
                    <td className="action">
                      {detection.sprinklers_activated ? '💦 Activated' : '🧪 Demo'}
                    </td>
                    <td>
                      {detection.image_path ? (
                        <a 
                          href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${detection.image_path}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="view-image-link"
                        >
                          📷 View
                        </a>
                      ) : (
                        <span className="no-image">—</span>
                      )}
                    </td>
                    <td className="review-cell">
                      {detection.reviewed ? (
                        <span className="reviewed-badge">
                          {detection.review_type === 'correct' && '✓ Correct'}
                          {detection.review_type === 'false_positive' && '✗ False'}
                          {detection.review_type === 'incorrect_count' && '# Adjusted'}
                          {detection.review_type === 'missed_deer' && '+ Missed'}
                        </span>
                      ) : reviewingId === detection.id ? (
                        <span className="reviewing">...</span>
                      ) : (
                        <div className="review-buttons">
                          <button 
                            className="review-btn correct"
                            onClick={() => reviewDetection(detection.id, 'correct')}
                            title="Mark as correct"
                          >
                            ✓
                          </button>
                          <button 
                            className="review-btn false-positive"
                            onClick={() => reviewDetection(detection.id, 'false_positive')}
                            title="Mark as false positive"
                          >
                            ✗
                          </button>
                          <button 
                            className="review-btn incorrect-count"
                            onClick={() => {
                              const count = prompt('Enter correct deer count:')
                              if (count) reviewDetection(detection.id, 'incorrect_count', parseInt(count))
                            }}
                            title="Adjust deer count"
                          >
                            #
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
