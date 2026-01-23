import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings }) {
  const [detections, setDetections] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('last24h') // last24h, last7d, all
  const [selectedImage, setSelectedImage] = useState(null)

  // Camera ID to name mapping
  const CAMERA_NAMES = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door',
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Side',
    'manual_upload': 'Manual Upload'
  }

  const formatCameraName = (cameraId) => {
    return CAMERA_NAMES[cameraId] || cameraId
  }

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    
    // Fetch snapshots with deer detections instead of video detections
    const limit = filter === 'all' ? 100 : (filter === 'last24h' ? 50 : 100)
    
    fetch(`${apiUrl}/api/ring-snapshots?limit=${limit}&with_deer=true`)
      .then(res => res.json())
      .then(data => {
        // Convert snapshots to detection format
        const snapshotDetections = (data.snapshots || []).map(snapshot => ({
          timestamp: snapshot.timestamp,
          camera_id: snapshot.camera_id,
          camera_name: formatCameraName(snapshot.camera_id),
          deer_count: 1, // We know deer was detected
          max_confidence: snapshot.detection_confidence || 0,
          image_path: `/api/ring-snapshots/${snapshot.id}/image`,
          snapshot_id: snapshot.id,
          event_id: snapshot.id
        }))
        
        // Filter by time if needed
        if (filter !== 'all') {
          const hours = filter === 'last24h' ? 24 : 168
          const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000)
          setDetections(snapshotDetections.filter(d => new Date(d.timestamp) > cutoff))
        } else {
          setDetections(snapshotDetections)
        }
        
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
          <p className="stat-value">{detections.length}</p>
          <p className="stat-period">{filter === 'last24h' ? 'Last 24 Hours' : filter === 'last7d' ? 'Last 7 Days' : 'All Time'}</p>
        </div>
        <div className="stat-card">
          <h3>Total Deer</h3>
          <p className="stat-value">{detections.length}</p>
          <p className="stat-period">{filter === 'last24h' ? 'Last 24 Hours' : filter === 'last7d' ? 'Last 7 Days' : 'All Time'}</p>
        </div>
        <div className="stat-card">
          <h3>Irrigation Zone Activations</h3>
          <p className="stat-value">{detections.filter(d => d.irrigation_activated).length}</p>
          <p className="stat-period">{filter === 'last24h' ? 'Last 24 Hours' : filter === 'last7d' ? 'Last 7 Days' : 'All Time'}</p>
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
                  <th>Confidence</th>
                  <th>Snapshot</th>
                </tr>
              </thead>
              <tbody>
                {detections.map((detection, index) => (
                  <tr key={index}>
                    <td>{new Date(detection.timestamp).toLocaleString()}</td>
                    <td>{detection.camera_name}</td>
                    <td className="confidence">
                      {(detection.max_confidence * 100).toFixed(0)}%
                    </td>
                    <td>
                      {detection.image_path ? (
                        <button 
                          onClick={() => setSelectedImage({
                            url: `${import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'}${detection.image_path}`,
                            ...detection
                          })}
                          className="view-image-button"
                        >
                          📷 View
                        </button>
                      ) : (
                        <span className="no-image">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Image Modal */}
      {selectedImage && (
        <div className="modal-overlay" onClick={() => setSelectedImage(null)}>
          <div className="image-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setSelectedImage(null)} 
              className="btn-close-modal"
            >
              ✕
            </button>
            <div className="modal-content">
              <img 
                src={selectedImage.url} 
                alt="Detection snapshot"
              />
              <div className="image-info">
                <div className="info-row">
                  <span className="label">Camera:</span>
                  <span className="value">{selectedImage.camera_name}</span>
                </div>
                <div className="info-row">
                  <span className="label">Time:</span>
                  <span className="value">{new Date(selectedImage.timestamp).toLocaleString()}</span>
                </div>
                <div className="info-row">
                  <span className="label">Confidence:</span>
                  <span className="value">{(selectedImage.max_confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard


