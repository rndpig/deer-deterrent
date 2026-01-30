import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings, onShowSettings, onViewVideos, onViewArchive }) {
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [timeFilter, setTimeFilter] = useState('last7d') // last24h, last7d, all
  const [feedbackFilter, setFeedbackFilter] = useState('all') // all, with_deer, without_deer
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedCamera, setSelectedCamera] = useState('side')
  const [captureDateTime, setCaptureDateTime] = useState('')

  const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'

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

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date
    const hours = Math.floor(diff / (1000 * 60 * 60))
    
    if (hours < 24) {
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    } else if (hours < 168) {
      return date.toLocaleDateString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' })
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  }

  useEffect(() => {
    loadSnapshots()
  }, [timeFilter, feedbackFilter])

  const loadSnapshots = async () => {
    setLoading(true)
    try {
      let url = `${apiUrl}/api/ring-snapshots?limit=500`
      
      // Apply feedback filter
      if (feedbackFilter === 'with_deer') {
        url += '&with_deer=true'
      } else if (feedbackFilter === 'without_deer') {
        url += '&with_deer=false'
      }
      
      const response = await fetch(url)
      if (!response.ok) throw new Error('Failed to fetch snapshots')
      
      const data = await response.json()
      let allSnapshots = data.snapshots || []
      
      // Apply time filter
      if (timeFilter !== 'all') {
        const hours = timeFilter === 'last24h' ? 24 : 168
        const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000)
        allSnapshots = allSnapshots.filter(s => new Date(s.timestamp) > cutoff)
      }
      
      setSnapshots(allSnapshots)
    } catch (error) {
      console.error('Error loading snapshots:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUploadImage = async () => {
    if (!selectedFile) {
      setUploadResult({ success: false, message: 'Please select an image file' })
      return
    }

    if (!captureDateTime) {
      setUploadResult({ success: false, message: 'Please enter the date/time when the photo was captured' })
      return
    }

    setUploadingImage(true)
    setUploadResult(null)

    try {
      const formData = new FormData()
      formData.append('image', selectedFile)
      formData.append('threshold', settings?.detection_threshold || 0.75)
      formData.append('save_to_database', 'true')
      formData.append('camera_id', selectedCamera === 'side' ? '10cea9e4511f' : '587a624d3fae')
      formData.append('captured_at', captureDateTime)

      const response = await fetch(`${apiUrl}/api/test-detection`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Detection failed')

      const result = await response.json()
      setUploadResult({
        success: true,
        deerDetected: result.deer_detected,
        confidence: result.max_confidence,
        message: result.deer_detected 
          ? `✅ Deer detected! Confidence: ${(result.max_confidence * 100).toFixed(1)}%`
          : `❌ No deer detected (max confidence: ${(result.max_confidence * 100).toFixed(1)}%)`
      })

      // Reload snapshots
      if (result.saved_event_id) {
        await loadSnapshots()
        setSelectedFile(null)
      }
    } catch (error) {
      console.error('Error testing image:', error)
      setUploadResult({ success: false, message: '❌ Error: ' + error.message })
    } finally {
      setUploadingImage(false)
    }
  }

  const updateSnapshotFeedback = async (snapshotId, hasDeer) => {
    try {
      const response = await fetch(`${apiUrl}/api/ring-snapshots/${snapshotId}/feedback`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deer_detected: hasDeer ? 1 : 0 })
      })

      if (response.ok) {
        // Update local state
        setSnapshots(prev => prev.map(s => 
          s.id === snapshotId ? { ...s, deer_detected: hasDeer ? 1 : 0 } : s
        ))
        if (selectedSnapshot?.id === snapshotId) {
          setSelectedSnapshot({ ...selectedSnapshot, deer_detected: hasDeer ? 1 : 0 })
        }
      }
    } catch (error) {
      console.error('Error updating feedback:', error)
    }
  }

  // Calculate stats from filtered snapshots
  const deerCount = snapshots.filter(s => s.deer_detected).length
  const irrigationCount = 0 // TODO: Add irrigation tracking if needed

  return (
    <div className="dashboard">
      {/* Header with stats and controls */}
      <div className="dashboard-header">
        <div className="stats-grid">
          <div className="stat-card">
            <h3>Total Snapshots</h3>
            <p className="stat-value">{snapshots.length}</p>
            <p className="stat-period">
              {timeFilter === 'last24h' ? 'Last 24 Hours' : 
               timeFilter === 'last7d' ? 'Last 7 Days' : 'All Time'}
            </p>
          </div>
          <div className="stat-card">
            <h3>Deer Detected</h3>
            <p className="stat-value">{deerCount}</p>
            <p className="stat-period">
              {timeFilter === 'last24h' ? 'Last 24 Hours' : 
               timeFilter === 'last7d' ? 'Last 7 Days' : 'All Time'}
            </p>
          </div>
          <div className="stat-card">
            <h3>Season Status</h3>
            <p className="stat-value status">
              {stats?.current_season ? '✅ Active' : '❄️ Off-Season'}
            </p>
          </div>
          <div className="stat-card">
            <button 
              className="btn-settings"
              onClick={onShowSettings}
              title="Open Settings"
            >
              ⚙️ Settings
            </button>
          </div>
        </div>
      </div>

      {/* Filter controls */}
      <div className="snapshot-controls">
        <div className="nav-buttons">
          <button 
            className="btn-nav"
            onClick={() => setShowUploadModal(true)}
          >
            📤 Upload Image
          </button>
          <button 
            className="btn-nav"
            onClick={onViewVideos}
          >
            🎬 Videos
          </button>
          <button 
            className="btn-nav"
            onClick={onViewArchive}
          >
            📦 Archive
          </button>
        </div>

        <div className="filter-section">
          <label className="filter-label">Time:</label>
          <div className="filter-buttons">
            <button
              className={timeFilter === 'last24h' ? 'active' : ''}
              onClick={() => setTimeFilter('last24h')}
            >
              Last 24h
            </button>
            <button
              className={timeFilter === 'last7d' ? 'active' : ''}
              onClick={() => setTimeFilter('last7d')}
            >
              Last 7 Days
            </button>
            <button
              className={timeFilter === 'all' ? 'active' : ''}
              onClick={() => setTimeFilter('all')}
            >
              All Time
            </button>
          </div>
        </div>

        <div className="filter-section">
          <label className="filter-label">Show:</label>
          <div className="filter-buttons">
            <button
              className={feedbackFilter === 'all' ? 'active' : ''}
              onClick={() => setFeedbackFilter('all')}
            >
              All
            </button>
            <button
              className={feedbackFilter === 'with_deer' ? 'active' : ''}
              onClick={() => setFeedbackFilter('with_deer')}
            >
              🦌 Deer
            </button>
            <button
              className={feedbackFilter === 'without_deer' ? 'active' : ''}
              onClick={() => setFeedbackFilter('without_deer')}
            >
              No Deer
            </button>
          </div>
        </div>
      </div>

      {/* Snapshot Grid */}
      {loading ? (
        <div className="loading">Loading snapshots...</div>
      ) : snapshots.length === 0 ? (
        <div className="empty-state">
          <h3>📸 No Snapshots Found</h3>
          <p>No snapshots match your filters.</p>
        </div>
      ) : (
        <div className="snapshot-grid">
          {snapshots.map((snapshot) => (
            <div
              key={snapshot.id}
              className={`snapshot-card ${snapshot.deer_detected ? 'with-deer' : ''}`}
              onClick={() => setSelectedSnapshot(snapshot)}
            >
              <div className="snapshot-thumbnail">
                <img
                  src={`${apiUrl}/api/ring-snapshots/${snapshot.id}/image`}
                  alt={`Snapshot ${snapshot.id}`}
                  loading="lazy"
                />
                {!!snapshot.deer_detected && (
                  <div className="deer-badge">🦌 Deer</div>
                )}
              </div>
              <div className="snapshot-info">
                <div className="snapshot-meta">
                  <span className="snapshot-id">#{snapshot.id}</span>
                  <span className="snapshot-camera">
                    {formatCameraName(snapshot.camera_id)}
                  </span>
                  <span className="snapshot-time">{formatTimestamp(snapshot.timestamp)}</span>
                  {snapshot.detection_confidence !== null && (
                    <span className="snapshot-confidence">
                      {(snapshot.detection_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
          <div className="upload-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setShowUploadModal(false)} 
              className="btn-close-modal"
            >
              ✕
            </button>
            <h2>📤 Upload Image</h2>
            <div className="upload-form">
              <div className="form-group">
                <label>Select Image:</label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setSelectedFile(e.target.files[0])}
                />
              </div>
              <div className="form-group">
                <label>Camera:</label>
                <select
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(e.target.value)}
                >
                  <option value="side">Side</option>
                  <option value="driveway">Driveway</option>
                </select>
              </div>
              <div className="form-group">
                <label>Capture Date/Time:</label>
                <input
                  type="datetime-local"
                  value={captureDateTime}
                  onChange={(e) => setCaptureDateTime(e.target.value)}
                />
              </div>
              {uploadResult && (
                <div className={`upload-result ${uploadResult.success ? 'success' : 'error'}`}>
                  {uploadResult.message}
                </div>
              )}
              <div className="modal-actions">
                <button
                  onClick={handleUploadImage}
                  disabled={uploadingImage || !selectedFile}
                  className="btn-primary"
                >
                  {uploadingImage ? 'Uploading...' : 'Upload & Detect'}
                </button>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Snapshot Detail Modal */}
      {selectedSnapshot && (
        <div className="modal-overlay" onClick={() => setSelectedSnapshot(null)}>
          <div className="image-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setSelectedSnapshot(null)} 
              className="btn-close-modal"
            >
              ✕
            </button>
            <div className="modal-content">
              <img 
                src={`${apiUrl}/api/ring-snapshots/${selectedSnapshot.id}/image`}
                alt="Snapshot"
              />
              <div className="image-info">
                <div className="info-row">
                  <span className="label">ID:</span>
                  <span className="value">#{selectedSnapshot.id}</span>
                </div>
                <div className="info-row">
                  <span className="label">Camera:</span>
                  <span className="value">{formatCameraName(selectedSnapshot.camera_id)}</span>
                </div>
                <div className="info-row">
                  <span className="label">Time:</span>
                  <span className="value">{new Date(selectedSnapshot.timestamp).toLocaleString()}</span>
                </div>
                {selectedSnapshot.detection_confidence !== null && (
                  <div className="info-row">
                    <span className="label">Confidence:</span>
                    <span className="value">{(selectedSnapshot.detection_confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
                <div className="feedback-section">
                  <p className="feedback-label">Is there a deer in this image?</p>
                  <div className="feedback-buttons">
                    <button
                      className={`btn-feedback ${selectedSnapshot.deer_detected ? 'active' : ''}`}
                      onClick={() => updateSnapshotFeedback(selectedSnapshot.id, true)}
                    >
                      ✅ Yes - Deer
                    </button>
                    <button
                      className={`btn-feedback ${!selectedSnapshot.deer_detected ? 'active' : ''}`}
                      onClick={() => updateSnapshotFeedback(selectedSnapshot.id, false)}
                    >
                      ❌ No - False Positive
                    </button>
                  </div>
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


