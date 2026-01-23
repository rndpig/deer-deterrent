import { useState, useEffect } from 'react'
import './SnapshotViewer.css'

function SnapshotViewer({ onViewVideos, onViewArchive }) {
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // 'all', 'with_deer', 'without_deer'
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [detectionRunning, setDetectionRunning] = useState(false)
  const [threshold, setThreshold] = useState(0.60)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)

  const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'

  // Camera ID to name mapping
  const CAMERA_NAMES = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door',
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Side'
  }

  const formatCameraName = (cameraId) => {
    return CAMERA_NAMES[cameraId] || cameraId
  }

  useEffect(() => {
    loadSnapshots()
  }, [filter])

  const loadSnapshots = async () => {
    setLoading(true)
    try {
      let url = `${apiUrl}/api/ring-snapshots?limit=100`
      if (filter === 'with_deer') {
        url += '&with_deer=true'
      } else if (filter === 'without_deer') {
        url += '&with_deer=false'
      }

      const response = await fetch(url)
      if (!response.ok) throw new Error('Failed to load snapshots')

      const data = await response.json()
      setSnapshots(data.snapshots)
    } catch (error) {
      console.error('Error loading snapshots:', error)
      alert(`Failed to load snapshots: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const selectSnapshot = (snapshot) => {
    setSelectedSnapshot(snapshot)
  }

  const rerunDetection = async () => {
    if (!selectedSnapshot) return

    setDetectionRunning(true)
    try {
      const response = await fetch(
        `${apiUrl}/api/ring-snapshots/${selectedSnapshot.id}/rerun-detection?threshold=${threshold}`,
        { method: 'POST' }
      )

      if (!response.ok) throw new Error('Detection failed')

      const result = await response.json()

      // Update the selected snapshot with new results
      setSelectedSnapshot({
        ...selectedSnapshot,
        deer_detected: result.deer_detected,
        detection_confidence: result.max_confidence,
        detection_result: result
      })

      // Update in list
      setSnapshots(snapshots.map(s =>
        s.id === selectedSnapshot.id
          ? { ...s, deer_detected: result.deer_detected, detection_confidence: result.max_confidence }
          : s
      ))

      alert(`Detection complete! ${result.deer_detected ? 'Deer detected' : 'No deer'} (confidence: ${(result.max_confidence * 100).toFixed(1)}%)`)
    } catch (error) {
      console.error('Error running detection:', error)
      alert(`Detection failed: ${error.message}`)
    } finally {
      setDetectionRunning(false)
    }
  }

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    return date.toLocaleString()
  }

  const handleImageUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setUploadResult({ success: false, message: 'Please select an image file' })
      return
    }

    setUploadingImage(true)
    setUploadResult(null)

    try {
      const formData = new FormData()
      formData.append('image', file)
      formData.append('threshold', threshold)
      formData.append('save_to_database', 'true')

      const response = await fetch(`${apiUrl}/api/test-detection`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error('Detection failed')
      }

      const result = await response.json()
      setUploadResult({
        success: true,
        deerDetected: result.deer_detected,
        confidence: result.max_confidence,
        detectionCount: result.detections?.length || 0,
        message: result.deer_detected 
          ? `✅ Deer detected! Confidence: ${(result.max_confidence * 100).toFixed(1)}%`
          : `❌ No deer detected (max confidence: ${(result.max_confidence * 100).toFixed(1)}%)`
      })

      // Reload snapshots to show the newly uploaded image
      if (result.saved_event_id) {
        await loadSnapshots()
      }
    } catch (error) {
      console.error('Error testing image:', error)
      setUploadResult({ success: false, message: '❌ Error: ' + error.message })
    } finally {
      setUploadingImage(false)
      event.target.value = '' // Reset input
    }
  }

  if (loading) {
    return (
      <div className="snapshot-viewer">
        <div className="loading">Loading snapshots...</div>
      </div>
    )
  }

  if (snapshots.length === 0) {
    return (
      <div className="snapshot-viewer">
        <div className="empty-state">
          <h3>📸 No Snapshots Found</h3>
          <p>Snapshots will appear here as motion events are detected.</p>
          <p>The coordinator must be running with snapshot-saving enabled.</p>
          <button onClick={loadSnapshots} className="btn-reload">
            🔄 Reload
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="snapshot-viewer">
      <div className="snapshot-header-nav">
        <h1>📸 Snapshots ({snapshots.length})</h1>
        <div className="nav-buttons">
          <button 
            className="btn-nav"
            onClick={() => setShowUploadModal(true)}
            title="Upload and test an image"
          >
            📤 Upload Image
          </button>
          <button 
            className="btn-nav"
            onClick={() => window.dispatchEvent(new CustomEvent('navigate-to-videos'))}
            title="View uploaded videos"
          >
            🎬 Videos
          </button>
          <button 
            className="btn-nav"
            onClick={() => window.dispatchEvent(new CustomEvent('navigate-to-archive'))}
            title="View archive"
          >
            📦 Archive
          </button>
        </div>
      </div>
      <div className="snapshot-header">
        <div className="snapshot-filters">
          <button
            className={filter === 'all' ? 'active' : ''}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            className={filter === 'with_deer' ? 'active' : ''}
            onClick={() => setFilter('with_deer')}
          >
            With Deer
          </button>
          <button
            className={filter === 'without_deer' ? 'active' : ''}
            onClick={() => setFilter('without_deer')}
          >
            No Deer
          </button>
        </div>
      </div>

      <div className="snapshot-grid">
        {snapshots.map((snapshot) => (
          <div
            key={snapshot.id}
            className={`snapshot-card ${selectedSnapshot?.id === snapshot.id ? 'selected' : ''} ${snapshot.deer_detected ? 'with-deer' : ''}`}
            onClick={() => selectSnapshot(snapshot)}
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
                <span className="snapshot-camera">
                  {formatCameraName(snapshot.camera_id)}
                </span>
                <span className="snapshot-time">{formatTimestamp(snapshot.timestamp)}</span>
                {snapshot.detection_confidence !== null && snapshot.detection_confidence !== undefined && (
                  <span className="snapshot-confidence">
                    {(snapshot.detection_confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Snapshot Detail Modal */}
      {selectedSnapshot && (
        <div className="dialog-overlay" onClick={() => setSelectedSnapshot(null)}>
          <div className="snapshot-detail-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setSelectedSnapshot(null)} 
              className="btn-close-modal"
            >
              ✕
            </button>

            <div className="modal-content">
              <div className="detail-image">
                <img
                  src={`${apiUrl}/api/ring-snapshots/${selectedSnapshot.id}/image`}
                  alt={`Snapshot ${selectedSnapshot.id}`}
                />
                {selectedSnapshot.detection_result?.detections?.map((det, idx) => (
                  <div
                    key={idx}
                    className="detection-box"
                    style={{
                      left: `${det.bbox.x1}px`,
                      top: `${det.bbox.y1}px`,
                      width: `${det.bbox.x2 - det.bbox.x1}px`,
                      height: `${det.bbox.y2 - det.bbox.y1}px`
                    }}
                  >
                    <span className="detection-label">
                      {(det.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>

              <div className="detail-info-compact">
                <div className="info-grid">
                  <div className="info-item">
                    <span className="label">Camera:</span>
                    <span className="value">{formatCameraName(selectedSnapshot.camera_id)}</span>
                  </div>
                  <div className="info-item">
                    <span className="label">Time:</span>
                    <span className="value">{formatTimestamp(selectedSnapshot.timestamp)}</span>
                  </div>
                  <div className="info-item">
                    <span className="label">Deer:</span>
                    <span className={`value ${selectedSnapshot.deer_detected ? 'detected' : 'not-detected'}`}>
                      {selectedSnapshot.deer_detected ? '✓ Yes' : '✗ No'}
                    </span>
                  </div>
                  <div className="info-item">
                    <span className="label">Confidence:</span>
                    <span className="value">
                      {selectedSnapshot.detection_confidence !== null && selectedSnapshot.detection_confidence !== undefined
                        ? `${(selectedSnapshot.detection_confidence * 100).toFixed(1)}%`
                        : '0.0%'}
                    </span>
                  </div>
                </div>

                <div className="detection-controls">
                  <label className="threshold-label">
                    Confidence Threshold: {(threshold * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min="0.30"
                    max="0.95"
                    step="0.05"
                    value={threshold}
                    onChange={(e) => setThreshold(parseFloat(e.target.value))}
                    className="threshold-slider"
                  />
                  <button
                    onClick={rerunDetection}
                    disabled={detectionRunning}
                    className="btn-rerun"
                  >
                    {detectionRunning ? '⏳ Running...' : '🔍 Re-Detect'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upload Image Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
          <div className="upload-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🖼️ Upload & Test Image</h2>
              <button className="btn-close" onClick={() => setShowUploadModal(false)}>✕</button>
            </div>
            <div className="modal-content">
              <p className="upload-description">
                Upload an image to test deer detection. The image will be analyzed and saved to your snapshot gallery.
              </p>
              <input
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                disabled={uploadingImage}
                style={{ display: 'none' }}
                id="snapshot-upload-input"
              />
              <label htmlFor="snapshot-upload-input" style={{ width: '100%' }}>
                <button 
                  className="btn-upload-large"
                  disabled={uploadingImage}
                  onClick={() => document.getElementById('snapshot-upload-input').click()}
                >
                  {uploadingImage ? '⏳ Testing...' : '📤 Select Image'}
                </button>
              </label>
              {uploadResult && (
                <div className={`upload-result ${uploadResult.success ? 'success' : 'error'}`}>
                  <p className="result-message">{uploadResult.message}</p>
                  {uploadResult.success && uploadResult.detectionCount > 0 && (
                    <p className="detection-details">
                      Found {uploadResult.detectionCount} detection{uploadResult.detectionCount !== 1 ? 's' : ''}
                    </p>
                  )}
                  {uploadResult.success && (
                    <p className="save-info">✓ Image saved to snapshot gallery</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SnapshotViewer
