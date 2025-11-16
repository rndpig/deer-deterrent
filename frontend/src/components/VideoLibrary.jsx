import { useState, useEffect } from 'react'
import './VideoLibrary.css'

function VideoLibrary({ onStartReview }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [trainingStatus, setTrainingStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadedVideo, setUploadedVideo] = useState(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState('front')
  const [captureDateTime, setCaptureDateTime] = useState('')

  useEffect(() => {
    loadVideos()
    loadTrainingStatus()
  }, [])

  const loadVideos = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/videos`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const data = await response.json()
      console.log('Loaded videos:', data) // Debug: see what we're getting
      setVideos(data)
    } catch (error) {
      console.error('Error loading videos:', error)
      alert('Failed to load videos')
    } finally {
      setLoading(false)
    }
  }

  const loadTrainingStatus = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/training/status`)
      if (response.ok) {
        const data = await response.json()
        setTrainingStatus(data)
      }
    } catch (error) {
      console.error('Error loading training status:', error)
    }
  }

  const deleteVideo = async (videoId, videoFilename) => {
    if (!confirm(`Delete "${videoFilename}"? This will remove the video and all extracted frames.`)) {
      return
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setDeleting(videoId)
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/${videoId}`, {
        method: 'DELETE'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      // Reload videos and status
      await loadVideos()
      await loadTrainingStatus()
    } catch (error) {
      console.error('Error deleting video:', error)
      alert('Failed to delete video')
    } finally {
      setDeleting(null)
    }
  }

  const handleStartReview = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      // Trigger frame selection algorithm
      const response = await fetch(`${apiUrl}/api/training/select-frames`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_count: 120 })
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to select frames')
      }
      
      const result = await response.json()
      alert(`Selected ${result.frames_selected} diverse frames for review`)
      
      // Notify parent to switch to review mode
      if (onStartReview) {
        onStartReview()
      }
    } catch (error) {
      console.error('Error starting review:', error)
      alert(error.message)
    }
  }

  const handleUploadClick = () => {
    document.getElementById('video-upload-input').click()
  }

  const handleVideoUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setUploading(true)

    try {
      const formData = new FormData()
      formData.append('video', file)

      const response = await fetch(`${apiUrl}/api/videos/upload`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const result = await response.json()
      
      // Store upload result and show confirmation dialog
      setUploadedVideo({
        ...result,
        filename: file.name
      })
      
      // Set default date/time to now
      const now = new Date()
      const localDateTime = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16)
      setCaptureDateTime(localDateTime)
      
      // Set default camera to side (first in dropdown)
      setSelectedCamera('side')
      
      setShowConfirmDialog(true)
    } catch (error) {
      console.error('Error uploading video:', error)
      alert(`❌ Upload failed: ${error.message}`)
    } finally {
      setUploading(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const handleConfirmVideo = async () => {
    if (!uploadedVideo) return

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const isEditing = !!videos.find(v => v.id === uploadedVideo.video_id)

    try {
      // Update video metadata
      const response = await fetch(`${apiUrl}/api/videos/${uploadedVideo.video_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          camera: selectedCamera,
          captured_at: captureDateTime
        })
      })

      if (!response.ok) {
        throw new Error('Failed to update video metadata')
      }

      // Reload videos and status (no alert needed)
      await loadVideos()
      await loadTrainingStatus()

      // Close dialog
      setShowConfirmDialog(false)
      setUploadedVideo(null)
    } catch (error) {
      console.error('Error confirming video:', error)
      alert(`❌ Error: ${error.message}`)
    }
  }

  const handleCancelVideo = async () => {
    if (!uploadedVideo) return

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

    try {
      // Delete the uploaded video
      await fetch(`${apiUrl}/api/videos/${uploadedVideo.video_id}`, {
        method: 'DELETE'
      })

      setShowConfirmDialog(false)
      setUploadedVideo(null)
    } catch (error) {
      console.error('Error canceling video:', error)
    }
  }

  const handleEditVideo = (video) => {
    // Parse camera from camera_name (e.g., "Manual Upload" -> "side", or existing camera value)
    const cameraMap = {
      'Front': 'front',
      'Side': 'side',
      'Driveway': 'driveway',
      'Backyard': 'backyard'
    }
    const camera = video.camera || cameraMap[video.camera_name] || 'side'
    
    // Parse date/time
    const dateTime = video.captured_at || video.upload_date
    const localDateTime = new Date(dateTime)
      .toISOString()
      .slice(0, 16)
    
    // Set up for editing
    setUploadedVideo({
      video_id: video.id,
      filename: video.filename,
      frames_extracted: video.frame_count,
      detections: video.detection_count
    })
    setSelectedCamera(camera)
    setCaptureDateTime(localDateTime)
    setShowConfirmDialog(true)
  }

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const formatCameraName = (video) => {
    console.log('Formatting camera for video:', video.id, 'camera field:', video.camera, 'camera_name field:', video.camera_name) // Debug
    // Use camera field if available, otherwise fall back to camera_name
    if (video.camera) {
      const names = {
        'side': 'Side',
        'driveway': 'Driveway',
        'front': 'Front',
        'backyard': 'Backyard'
      }
      return names[video.camera] || video.camera
    }
    // Skip "Manual Upload" text
    return video.camera_name === 'Manual Upload' ? '—' : video.camera_name
  }

  if (loading) {
    return (
      <div className="video-library">
        <div className="loading">Loading videos...</div>
      </div>
    )
  }

  return (
    <div className="video-library">
      <input
        type="file"
        id="video-upload-input"
        accept="video/*"
        style={{ display: 'none' }}
        onChange={handleVideoUpload}
      />
      
      <div className="library-header">
        <div className="header-left">
          <h1>📹 Video Library</h1>
          <p className="library-subtitle">Collect videos for model training</p>
        </div>
        
        <div className="header-right">
          <button 
            className="btn-upload-video"
            onClick={handleUploadClick}
            disabled={uploading}
          >
            {uploading ? '⏳ Uploading...' : '📤 Upload Video'}
          </button>
          
          {trainingStatus && (
            <div className="training-status-card">
              <div className="status-row">
                <span className="status-label">Videos Collected:</span>
                <span className={`status-value ${trainingStatus.video_count >= 10 ? 'ready' : ''}`}>
                  {trainingStatus.video_count} / 10
                </span>
              </div>
              
              {trainingStatus.ready_for_review && !trainingStatus.reviewed_frames && (
                <button 
                  className="btn-start-review"
                  onClick={handleStartReview}
                >
                  ✅ Start Review Process
                </button>
              )}
              
              {trainingStatus.reviewed_frames > 0 && (
                <div className="status-row">
                  <span className="status-label">Reviewed:</span>
                  <span className="status-value">{trainingStatus.reviewed_frames} frames</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {videos.length === 0 ? (
        <div className="empty-library">
          <div className="empty-icon">📹</div>
          <h2>No videos uploaded yet</h2>
          <p>Upload videos to start collecting training data</p>
          <p className="empty-hint">Need at least 10 videos from different times/conditions before starting review</p>
        </div>
      ) : (
        <div className="video-grid">
          {videos.map((video) => (
            <div key={video.id} className="video-card">
              <div className="video-thumbnail">
                <div className="thumbnail-placeholder">
                  <span className="thumbnail-icon">🎥</span>
                </div>
                <div className="video-stats">
                  <span className="stat-badge">{video.frame_count} frames</span>
                  <span className="stat-badge">{video.detection_count} detections</span>
                  <span className="stat-badge stat-badge-dark">
                    {formatDuration(video.duration_seconds)} @ {Math.round(video.fps)}fps
                  </span>
                </div>
              </div>
              
              <div className="video-info">
                <h3 className="video-title">{video.filename}</h3>
                
                <div className="video-metadata">
                  <span className="metadata-left">{formatDate(video.captured_at || video.upload_date)}</span>
                  <span className="metadata-right">{formatCameraName(video)}</span>
                </div>
              </div>
              
              <div className="video-actions">
                <button 
                  className="btn-edit"
                  onClick={() => handleEditVideo(video)}
                  title="Edit camera and date/time"
                >
                  ✏️ Edit
                </button>
                <button 
                  className="btn-delete"
                  onClick={() => deleteVideo(video.id, video.filename)}
                  disabled={deleting === video.id}
                  title="Delete video and frames"
                >
                  {deleting === video.id ? '⏳' : '🗑️'} Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Video Confirmation Dialog */}
      {showConfirmDialog && uploadedVideo && (
        <div className="dialog-overlay">
          <div className="dialog-box">
            <h2>📹 Confirm Video Details</h2>
            <p className="dialog-subtitle">
              Extracted {uploadedVideo.frames_extracted} frames with {uploadedVideo.detections} detections
            </p>

            <div className="dialog-form">
              <div className="form-group">
                <label htmlFor="video-filename">Filename</label>
                <input
                  type="text"
                  id="video-filename"
                  value={uploadedVideo.filename}
                  disabled
                  className="form-input-disabled"
                />
              </div>

              <div className="form-group">
                <label htmlFor="video-camera">Camera *</label>
                <select
                  id="video-camera"
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(e.target.value)}
                  className="form-select"
                >
                  <option value="side">Side</option>
                  <option value="driveway">Driveway</option>
                  <option value="front">Front</option>
                  <option value="backyard">Backyard</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="video-datetime">Capture Date/Time *</label>
                <input
                  type="datetime-local"
                  id="video-datetime"
                  value={captureDateTime}
                  onChange={(e) => setCaptureDateTime(e.target.value)}
                  className="form-input"
                />
              </div>
            </div>

            <div className="dialog-actions">
              <button
                className="btn-dialog-cancel"
                onClick={handleCancelVideo}
              >
                Cancel & Delete
              </button>
              <button
                className="btn-dialog-confirm"
                onClick={handleConfirmVideo}
              >
                ✅ Confirm & Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoLibrary
