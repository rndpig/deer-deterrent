import { useState, useEffect } from 'react'
import './Dashboard.css'

function Dashboard({ stats, settings }) {
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [timeFilter, setTimeFilter] = useState('last24h') // last24h, last7d, all
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(100)
  const [feedbackFilter, setFeedbackFilter] = useState('with_deer') // all, with_deer, without_deer
  const [cameraFilter, setCameraFilter] = useState('all') // all, or specific camera ID
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
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const year = date.getFullYear()
    let hours = date.getHours()
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const ampm = hours >= 12 ? 'PM' : 'AM'
    hours = hours % 12 || 12
    
    return `${month}/${day}/${year} ${hours}:${minutes} ${ampm}`
  }

  useEffect(() => {
    loadSnapshots()
    setCurrentPage(1) // Reset to page 1 when filters change
  }, [timeFilter, feedbackFilter, cameraFilter])

  // Listen for upload modal trigger from header
  useEffect(() => {
    const handleShowUpload = () => setShowUploadModal(true)
    window.addEventListener('show-upload-modal', handleShowUpload)
    return () => window.removeEventListener('show-upload-modal', handleShowUpload)
  }, [])

  const loadSnapshots = async () => {
    setLoading(true)
    try {
      let url = `${apiUrl}/api/snapshots?limit=5000`
      
      // Apply feedback filter
      if (feedbackFilter === 'with_deer') {
        url += '&with_deer=true'
      } else if (feedbackFilter === 'without_deer') {
        url += '&with_deer=false'
      }
      
      console.log('Fetching snapshots from:', url)
      const response = await fetch(url)
      console.log('Response status:', response.status)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('Received data:', data)
      let allSnapshots = data.snapshots || []
      console.log('Total snapshots from API:', allSnapshots.length)
      
      // Apply time filter
      if (timeFilter !== 'all') {
        const hours = timeFilter === 'last24h' ? 24 : 168
        const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000)
        allSnapshots = allSnapshots.filter(s => new Date(s.timestamp) > cutoff)
        console.log('After time filter:', allSnapshots.length)
      }
      
      // Apply camera filter
      if (cameraFilter !== 'all') {
        allSnapshots = allSnapshots.filter(s => s.camera_id === cameraFilter)
        console.log('After camera filter:', allSnapshots.length)
      }
      
      console.log('Final snapshots to display:', allSnapshots.length)
      setSnapshots(allSnapshots)
      setCurrentPage(1) // Reset to first page
    } catch (error) {
      console.error('Error loading snapshots:', error)
      alert(`Failed to load snapshots: ${error.message}`)
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
      const response = await fetch(`${apiUrl}/api/ring-events/${snapshotId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deer_detected: hasDeer ? 1 : 0 })
      })

      if (response.ok) {
        // Close modal
        setSelectedSnapshot(null)
        // Reload snapshots to reflect the change
        loadSnapshots()
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
      {/* Header with stats and time filters in single row */}
      <div className="dashboard-header">
        <div className="header-row">
          <div className="stat-card">
            <h3>Total Snapshots</h3>
            <p className="stat-value">{snapshots.length}</p>
          </div>
          <div className="stat-card">
            <h3>Deer Detected</h3>
            <p className="stat-value">{deerCount}</p>
          </div>
        </div>
      </div>

      {/* Filter controls */}
      <div className="snapshot-controls">
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
              Last 7d
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

        <div className="filter-section">
          <label className="filter-label">Camera:</label>
          <div className="filter-buttons">
            <button
              className={cameraFilter === 'all' ? 'active' : ''}
              onClick={() => setCameraFilter('all')}
            >
              All
            </button>
            <button
              className={cameraFilter === '10cea9e4511f' ? 'active' : ''}
              onClick={() => setCameraFilter('10cea9e4511f')}
            >
              Side
            </button>
            <button
              className={cameraFilter === '587a624d3fae' ? 'active' : ''}
              onClick={() => setCameraFilter('587a624d3fae')}
            >
              Driveway
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
        <>
          {/* Pagination Info */}
          <div className="pagination-info">
            Showing {Math.min((currentPage - 1) * itemsPerPage + 1, snapshots.length)}-{Math.min(currentPage * itemsPerPage, snapshots.length)} of {snapshots.length} snapshots
          </div>
          
          <div className="snapshot-grid">
            {snapshots.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage).map((snapshot) => (
            <div
              key={snapshot.id}
              className={`snapshot-card ${snapshot.deer_detected ? 'with-deer' : ''}`}
              onClick={() => setSelectedSnapshot(snapshot)}
            >
              <div className="snapshot-thumbnail">
                <img
                  src={`${apiUrl}/api/snapshots/${snapshot.id}/image`}
                  alt={`Snapshot ${snapshot.id}`}
                  loading="lazy"
                />
                {snapshot.deer_detected && (snapshot.detection_bboxes?.length || 0) > 0 && (
                  <div className="deer-count-badge">
                    🦌 {snapshot.detection_bboxes.length}
                  </div>
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
        
        {/* Pagination Controls */}
        {snapshots.length > itemsPerPage && (
          <div className="pagination-controls">
            <button 
              onClick={() => setCurrentPage(1)} 
              disabled={currentPage === 1}
            >
              « First
            </button>
            <button 
              onClick={() => setCurrentPage(currentPage - 1)} 
              disabled={currentPage === 1}
            >
              ‹ Prev
            </button>
            <span className="page-indicator">
              Page {currentPage} of {Math.ceil(snapshots.length / itemsPerPage)}
            </span>
            <button 
              onClick={() => setCurrentPage(currentPage + 1)} 
              disabled={currentPage >= Math.ceil(snapshots.length / itemsPerPage)}
            >
              Next ›
            </button>
            <button 
              onClick={() => setCurrentPage(Math.ceil(snapshots.length / itemsPerPage))} 
              disabled={currentPage >= Math.ceil(snapshots.length / itemsPerPage)}
            >
              Last »
            </button>
          </div>
        )}
        </>
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
              <div className="modal-image-wrapper">
                <img 
                  src={`${apiUrl}/api/snapshots/${selectedSnapshot.id}/image`}
                  alt="Snapshot"
                />
                {selectedSnapshot.deer_detected && (selectedSnapshot.detection_bboxes?.length || 0) > 0 && (
                  <div className="deer-count-badge deer-count-badge-modal">
                    🦌 {selectedSnapshot.detection_bboxes.length}
                  </div>
                )}
              </div>
              <div className="image-info">
                <div className="info-grid-compact">
                  <span className="label">ID:</span>
                  <span className="value">#{selectedSnapshot.id}</span>
                  <span className="label">Camera:</span>
                  <span className="value">{formatCameraName(selectedSnapshot.camera_id)}</span>
                  <span className="label">Confidence:</span>
                  <span className="value">
                    {selectedSnapshot.detection_confidence !== null
                      ? `${(selectedSnapshot.detection_confidence * 100).toFixed(0)}%`
                      : 'N/A'}
                  </span>
                  
                  <span className="label">Time:</span>
                  <span className="value time-value">{new Date(selectedSnapshot.timestamp).toLocaleString()}</span>
                  <span className="label">Model:</span>
                  <span className="value model-value">{selectedSnapshot.model_version || 'Unknown'}</span>
                </div>
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


