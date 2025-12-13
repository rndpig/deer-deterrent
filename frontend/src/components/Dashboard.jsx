import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings }) {
  const [detections, setDetections] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('last24h') // last24h, last7d, all

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    
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
          <h3>Irrigation Zone Activations</h3>
          <p className="stat-value">{stats?.irrigation_activated || 0}</p>
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
          </div>
        </div>
        
        {loading ? (
          <div className="loading">Loading...</div>
        ) : detections.length === 0 ? (
          <div className="empty-state">
            <p>No detections found</p>
            <p className="hint">Wait for deer to be detected or check the Model Improvement tab to review uploaded videos</p>
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
                      <td>
                      {detection.irrigation_activated ? '💦 Activated' : '🧪 Demo'}
                    </td>
                    </td>
                    <td>
                      {detection.image_path ? (
                        <a 
                          href={`${import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'}${detection.image_path}`}
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
                      ) : (
                        <span className="not-reviewed">—</span>
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


