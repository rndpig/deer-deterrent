import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings }) {
  const [detections, setDetections] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('last24h') // last24h, last7d, all
  const [demoMode, setDemoMode] = useState(false)
  const [reviewingId, setReviewingId] = useState(null)
  const [trainingStats, setTrainingStats] = useState(null)

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
    
    // Fetch training stats
    fetch(`${apiUrl}/api/training/stats`)
      .then(res => res.json())
      .then(data => setTrainingStats(data))
      .catch(err => console.error('Error fetching training stats:', err))
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

  const exportAndSyncToGoogleDrive = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    try {
      // Step 1: Export training data
      const exportResponse = await fetch(`${apiUrl}/api/training/export`)
      if (!exportResponse.ok) {
        throw new Error('Export failed')
      }
      const exportData = await exportResponse.json()
      
      // Step 2: Sync to Google Drive
      const syncResponse = await fetch(`${apiUrl}/api/training/sync-to-drive`, {
        method: 'POST'
      })
      if (!syncResponse.ok) {
        throw new Error('Drive sync failed')
      }
      const syncData = await syncResponse.json()
      
      alert(`✅ Success!\n\n📦 Exported ${exportData.total_images} images with ${exportData.total_annotations} annotations\n\n☁️ Synced to Google Drive: ${syncData.version}\n\nReady for training in Google Colab!`)
      
    } catch (error) {
      console.error('Error exporting/syncing:', error)
      alert('❌ Error: ' + error.message + '\n\nMake sure backend is running and Google Drive is configured.')
    } finally {
      setLoading(false)
    }
  }

  const reportMissedDetection = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    // Prompt for details
    const timestamp = prompt('When did you see the deer? (e.g., "2024-11-15 18:30" or leave blank for now)')
    if (timestamp === null) return // User cancelled
    
    const camera = prompt('Which camera? (e.g., Front Yard, Back Yard)')
    if (!camera) {
      alert('❌ Camera name is required')
      return
    }
    
    const deerCount = prompt('How many deer did you see?', '1')
    if (!deerCount) return
    
    const notes = prompt('Any additional notes? (optional)', '')
    
    try {
      const response = await fetch(`${apiUrl}/api/detections/missed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          timestamp: timestamp || new Date().toISOString(),
          camera_name: camera,
          deer_count: parseInt(deerCount),
          notes: notes || '',
          reporter: 'user'
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        alert(`✅ Missed detection reported!\n\nReport ID: ${data.report_id}\nTotal missed reports: ${data.total_missed}\n\nThis will help improve the model during next training.`)
      } else {
        alert('❌ Error reporting missed detection')
      }
    } catch (error) {
      console.error('Error reporting missed detection:', error)
      alert('❌ Error reporting missed detection')
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

      {trainingStats && (
        <div className="training-stats-banner">
          <div className="training-stat">
            <span className="stat-label">📊 Reviewed</span>
            <span className="stat-number">{trainingStats.reviewed_detections}</span>
          </div>
          <div className="training-stat">
            <span className="stat-label">✓ Correct</span>
            <span className="stat-number">{trainingStats.review_breakdown.correct}</span>
          </div>
          <div className="training-stat">
            <span className="stat-label">✗ False Positives</span>
            <span className="stat-number">{trainingStats.review_breakdown.false_positive}</span>
          </div>
          <div className="training-stat">
            <span className="stat-label">➕ Missed</span>
            <span className="stat-number">{trainingStats.missed_reports}</span>
          </div>
          <div className={`training-readiness ${trainingStats.ready_for_training ? 'ready' : 'not-ready'}`}>
            {trainingStats.ready_for_training 
              ? '✅ Ready for Training' 
              : `⏳ Need ${50 - trainingStats.reviewed_detections} more reviews`
            }
          </div>
        </div>
      )}

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
              className="sync-button"
              onClick={exportAndSyncToGoogleDrive}
              disabled={loading}
              title="Export reviewed detections and sync to Google Drive for training"
            >
              {loading ? '⏳ Syncing...' : '☁️ Sync to Drive'}
            </button>
            <button 
              className="report-missed-button"
              onClick={reportMissedDetection}
              title="Report a deer detection that the system missed"
            >
              ➕ Report Missed
            </button>
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
