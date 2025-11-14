import { useState, useEffect } from 'react'
import './DetectionHistory.css'

function DetectionHistory() {
  const [detections, setDetections] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('last24h') // all, last24h, last7d

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

  return (
    <div className="detection-history">
      <div className="history-header">
        <h2>Detection History</h2>
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

      {loading ? (
        <div className="loading">Loading...</div>
      ) : detections.length === 0 ? (
        <div className="empty-state">
          <p>No detections found</p>
          <p className="hint">Detections will appear here as the system monitors for deer</p>
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
                    {detection.image_path && (
                      <a 
                        href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${detection.image_path}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="view-image-link"
                      >
                        View
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default DetectionHistory
