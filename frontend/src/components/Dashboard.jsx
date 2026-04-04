import { useState, useEffect } from 'react'
import './Dashboard.css'
import BoundingBoxImage from './BoundingBoxImage'
import AnnotationTool from './AnnotationTool'
import { apiFetch, API_URL } from '../api'

function Dashboard({ stats, settings }) {
  const [snapshots, setSnapshots] = useState([])
  const [allDeerSnapshots, setAllDeerSnapshots] = useState([]) // all deer detections (all-time) for accurate stats
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
  const [showAnnotationTool, setShowAnnotationTool] = useState(false)

  // Camera ID to name mapping
  const CAMERA_NAMES = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door',
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Woods',
    'c4dbad08f862': 'Side',
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
      // Build server-side filter params
      const displayParams = new URLSearchParams({ limit: '5000' })
      const deerParams = new URLSearchParams({ limit: '50000', with_deer: 'true' })

      if (feedbackFilter === 'with_deer') displayParams.set('with_deer', 'true')
      else if (feedbackFilter === 'without_deer') displayParams.set('with_deer', 'false')

      if (cameraFilter !== 'all') {
        displayParams.set('camera_id', cameraFilter)
        deerParams.set('camera_id', cameraFilter)
      }
        if (timeFilter !== 'all') {
        const hours = timeFilter === 'last24h' ? '24' : '168'
        displayParams.set('time_hours', hours)
      }
        const [displayRes, deerRes] = await Promise.all([
        apiFetch(`/api/snapshots?${displayParams}`),
        apiFetch(`/api/snapshots?${deerParams}`)
      ])

      if (!displayRes.ok) throw new Error(`HTTP ${displayRes.status}: ${displayRes.statusText}`)
      if (!deerRes.ok) throw new Error(`Deer fetch HTTP ${deerRes.status}: ${deerRes.statusText}`)

      const [displayData, deerData] = await Promise.all([displayRes.json(), deerRes.json()])

      setAllDeerSnapshots(deerData.snapshots || [])
      setSnapshots(displayData.snapshots || [])
      setCurrentPage(1)
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
      formData.append('camera_id', selectedCamera === 'side' ? 'c4dbad08f862' : '587a624d3fae')
      formData.append('captured_at', captureDateTime)

      const response = await apiFetch('/api/test-detection', {
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
         const response = await apiFetch(`/api/ring-events/${snapshotId}`, {
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

  // Convert stored bboxes ({bbox: {x1,y1,x2,y2}}) to AnnotationTool format ({x,y,width,height} normalized 0-1)
  const bboxesToAnnotationFormat = (bboxes, imgWidth, imgHeight) => {
    if (!bboxes || !imgWidth || !imgHeight) return []
    return bboxes.map(d => {
      const b = d.bbox
      if (!b || b.x1 === undefined) return null
      return {
        x: b.x1 / imgWidth,
        y: b.y1 / imgHeight,
        width: (b.x2 - b.x1) / imgWidth,
        height: (b.y2 - b.y1) / imgHeight,
        confidence: d.confidence  // preserve original model confidence
      }
    }).filter(Boolean)
  }

  // Convert AnnotationTool format back to stored bbox format
  const annotationToBboxFormat = (normalizedBoxes, imgWidth, imgHeight) => {
    return normalizedBoxes.map(b => ({
      bbox: {
        x1: Math.round(b.x * imgWidth * 100) / 100,
        y1: Math.round(b.y * imgHeight * 100) / 100,
        x2: Math.round((b.x + b.width) * imgWidth * 100) / 100,
        y2: Math.round((b.y + b.height) * imgHeight * 100) / 100
      },
      confidence: b.confidence ?? null  // preserve original, null for manual
    }))
  }
    const handleOpenAnnotation = () => {
    setShowAnnotationTool(true)
  }
    const handleSaveAnnotation = async (normalizedBoxes) => {
    if (!selectedSnapshot) return

    // Ring snapshots are 640x360
    const bboxes = annotationToBboxFormat(normalizedBoxes, 640, 360)
       try {
         const response = await apiFetch(`/api/snapshots/${selectedSnapshot.id}/bboxes`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ detection_bboxes: bboxes })
      })

      if (response.ok) {
        // Update local state so bboxes show immediately
        const updated = { ...selectedSnapshot, detection_bboxes: bboxes, deer_detected: 1 }
        setSelectedSnapshot(updated)
        const updateSnapshot = s =>
          s.id === selectedSnapshot.id ? { ...s, detection_bboxes: bboxes, deer_detected: 1 } : s
        setSnapshots(prev => prev.map(updateSnapshot))
        setAllDeerSnapshots(prev => prev.map(updateSnapshot))

        // Also mark as deer in backend (drawing bboxes implies deer present)
        await apiFetch(`/api/ring-events/${selectedSnapshot.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ deer_detected: 1 })
        })
      } else {
        console.error('Failed to save bboxes:', response.status)
      }
    } catch (error) {
      console.error('Error saving annotations:', error)
    }

    setShowAnnotationTool(false)
    setSelectedSnapshot(null) // Return directly to dashboard
  }

  // Stats computed from ALL deer snapshots (separate fetch, not limited by display window)
  // Apply time filter for time-dependent stats, but "This Month" always uses all-time
  const timeFilteredDeer = (() => {
    if (timeFilter === 'all') return allDeerSnapshots
    const hours = timeFilter === 'last24h' ? 24 : 168
    const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000)
    return allDeerSnapshots.filter(s => new Date(s.timestamp) > cutoff)
  })()

  const deerCount = timeFilteredDeer.length

  // Detections this month (from all deer data, not affected by time filter)
  const now = new Date()
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  const thisMonthCount = allDeerSnapshots.filter(s => new Date(s.timestamp) >= monthStart).length

  // Mean sighting hour (circular mean to handle midnight crossing)
  const meanSightingTime = (() => {
    if (timeFilteredDeer.length === 0) return null
    let sinSum = 0, cosSum = 0
    for (const s of timeFilteredDeer) {
      const d = new Date(s.timestamp)
      const fractionalHour = d.getHours() + d.getMinutes() / 60
      const angle = (fractionalHour / 24) * 2 * Math.PI
      sinSum += Math.sin(angle)
      cosSum += Math.cos(angle)
    }
     let meanAngle = Math.atan2(sinSum / timeFilteredDeer.length, cosSum / timeFilteredDeer.length)
    if (meanAngle < 0) meanAngle += 2 * Math.PI
    const meanHourFrac = (meanAngle / (2 * Math.PI)) * 24
    const avgHours = Math.floor(meanHourFrac)
    const avgMins = Math.round((meanHourFrac - avgHours) * 60)
    const ampm = avgHours >= 12 ? 'PM' : 'AM'
    const displayHour = avgHours % 12 || 12
    return `${displayHour}:${String(avgMins).padStart(2, '0')} ${ampm}`
  })()

  // Most recent detection
  const lastDetection = timeFilteredDeer.length > 0
    ? formatTimestamp(timeFilteredDeer.reduce((latest, s) =>
        new Date(s.timestamp) > new Date(latest.timestamp) ? s : latest
      ).timestamp)
    : null

  // Average confidence
  const avgConfidence = (() => {
    const withConf = timeFilteredDeer.filter(s => s.detection_confidence != null)
    if (withConf.length === 0) return null
    const avg = withConf.reduce((sum, s) => sum + s.detection_confidence, 0) / withConf.length
    return `${(avg * 100).toFixed(0)}%`
  })()

  // Irrigation this month
  const irrigationThisMonth = allDeerSnapshots.filter(s => s.irrigation_activated && new Date(s.timestamp) >= monthStart).length

  return (
    <div className="dashboard">
      {/* Compact stats bar */}
      <div className="flex items-center gap-6 px-6 py-3 border-b border-white/10">
        {/* Primary stat */}
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-green-400">{deerCount}</span>
          <span className="text-xs uppercase tracking-wide text-white/50">deer detected</span>
        </div>

        {/* Divider */}
        <div className="w-px h-8 bg-white/15 shrink-0" />

        {/* Secondary stats */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="text-white/40 text-xs">This Month</span>
            <span className="font-semibold text-green-400">🦌 {thisMonthCount}</span>
            <span className="font-semibold text-blue-400">💦 {irrigationThisMonth}</span>
          </div>
          {meanSightingTime && (
            <div className="flex items-center gap-1.5">
              <span className="text-white/40 text-xs">Avg Time</span>
              <span className="font-semibold text-white/90">{meanSightingTime}</span>
            </div>
          )}
          {avgConfidence && (
            <div className="flex items-center gap-1.5">
              <span className="text-white/40 text-xs">Avg Conf</span>
              <span className="font-semibold text-white/90">{avgConfidence}</span>
            </div>
          )}
          {lastDetection && (
            <div className="flex items-center gap-1.5">
              <span className="text-white/40 text-xs">Latest</span>
              <span className="font-semibold text-white/90">{lastDetection}</span>
            </div>
          )}
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
          <div className="camera-select-wrapper">
            <select
              className="camera-select"
              value={cameraFilter}
              onChange={(e) => setCameraFilter(e.target.value)}
            >
              <option value="all">All Cameras</option>
              <option value="10cea9e4511f">Woods</option>
              <option value="c4dbad08f862">Side</option>
              <option value="587a624d3fae">Driveway</option>
              <option value="4439c4de7a79">Front Door</option>
              <option value="f045dae9383a">Back</option>
            </select>
            <span className="camera-select-arrow">▾</span>
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
          <div className="snapshot-grid">
            {snapshots.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage).map((snapshot) => (
            <div
              key={snapshot.id}
              className={`snapshot-card ${snapshot.deer_detected ? 'with-deer' : ''}`}
              onClick={() => setSelectedSnapshot(snapshot)}
            >
              <div className="snapshot-thumbnail">
                <BoundingBoxImage
                  src={`${API_URL}/api/snapshots/${snapshot.id}/image`}
                  alt={`Snapshot ${snapshot.id}`}
                  detections={(snapshot.detection_bboxes?.length || 0) > 0 ? snapshot.detection_bboxes : null}
                  className="snapshot-img"
                />
                {!!snapshot.deer_detected && (snapshot.detection_bboxes?.length || 0) > 0 && (
                  <div className="deer-count-badge">
                    🦌 {snapshot.detection_bboxes.length}
                  </div>
                )}
                {!!snapshot.irrigation_activated && (
                  <div className="irrigation-badge">
                    💦
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
              onClick={() => { setCurrentPage(currentPage - 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }} 
              disabled={currentPage === 1}
            >
              « Prev
            </button>
            <button 
              onClick={() => { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }}
            >
              ↓ Bottom
            </button>
            <span className="page-indicator">
              Page {currentPage} of {Math.ceil(snapshots.length / itemsPerPage)}
            </span>
            <button 
              onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); }}
            >
              ↑ Top
            </button>
            <button 
              onClick={() => { setCurrentPage(currentPage + 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }} 
              disabled={currentPage >= Math.ceil(snapshots.length / itemsPerPage)}
            >
              Next »
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
                <BoundingBoxImage
                  src={`${API_URL}/api/snapshots/${selectedSnapshot.id}/image`}
                  alt="Snapshot"
                  detections={(selectedSnapshot.detection_bboxes?.length || 0) > 0 ? selectedSnapshot.detection_bboxes : null}
                  className="modal-img"
                />
              </div>
              <div className="modal-sidebar">
                <div className="modal-meta">
                  <div className="meta-row">
                    <span className="meta-label">ID</span>
                    <span className="meta-value">#{selectedSnapshot.id}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Camera</span>
                    <span className="meta-value">{formatCameraName(selectedSnapshot.camera_id)}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Confidence</span>
                    <span className="meta-value">
                      {selectedSnapshot.detection_confidence !== null
                        ? `${(selectedSnapshot.detection_confidence * 100).toFixed(0)}%`
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Time</span>
                    <span className="meta-value">{new Date(selectedSnapshot.timestamp).toLocaleString()}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Model</span>
                    <span className="meta-value">{selectedSnapshot.model_version || 'Unknown'}</span>
                  </div>
                  {(selectedSnapshot.detection_bboxes?.length || 0) > 0 && (
                    <div className="meta-row">
                      <span className="meta-label">Detections</span>
                      <span className="meta-value">🦌 {selectedSnapshot.detection_bboxes.length}</span>
                    </div>
                  )}
                  {!!selectedSnapshot.irrigation_activated && (
                    <div className="meta-row">
                      <span className="meta-label">Irrigation</span>
                      <span className="meta-value irrigation-fired">💦 Activated</span>
                    </div>
                  )}
                </div>
                <div className="modal-actions-section">
                  <button
                    className={`btn-feedback ${selectedSnapshot.deer_detected ? 'active' : ''}`}
                    onClick={() => updateSnapshotFeedback(selectedSnapshot.id, true)}
                  >
                    ✅ Deer
                  </button>
                  <button
                    className={`btn-feedback ${!selectedSnapshot.deer_detected ? 'active' : ''}`}
                    onClick={() => updateSnapshotFeedback(selectedSnapshot.id, false)}
                  >
                    ❌ False Positive
                  </button>
                  <button
                    className="btn-annotate"
                    onClick={handleOpenAnnotation}
                  >
                    ✏️ Draw Boxes
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Annotation Tool Modal */}
      {showAnnotationTool && selectedSnapshot && (
        <AnnotationTool
          imageSrc={`${API_URL}/api/snapshots/${selectedSnapshot.id}/image`}
          existingBoxes={bboxesToAnnotationFormat(
            selectedSnapshot.detection_bboxes,
            640, 360
          )}
          onSave={handleSaveAnnotation}
          onCancel={() => setShowAnnotationTool(false)}
        />
      )}
    </div>
  )
}

export default Dashboard


