import { useState, useEffect } from 'react'
import './VideoLibrary.css'

function VideoLibrary({ onStartReview }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [trainingStatus, setTrainingStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [uploading, setUploading] = useState(false)

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

      const response = await fetch(`${apiUrl}/api/upload`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const result = await response.json()
      alert(`✅ Video uploaded! Extracted ${result.frames_extracted} frames with ${result.detections} detections`)

      // Reload videos and status
      await loadVideos()
      await loadTrainingStatus()
    } catch (error) {
      console.error('Error uploading video:', error)
      alert(`❌ Upload failed: ${error.message}`)
    } finally {
      setUploading(false)
      // Reset file input
      event.target.value = ''
    }
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
                </div>
              </div>
              
              <div className="video-info">
                <h3 className="video-title">{video.filename}</h3>
                
                <div className="video-details">
                  <div className="detail-row">
                    <span className="detail-label">📅</span>
                    <span className="detail-value">{formatDate(video.upload_date)}</span>
                  </div>
                  
                  <div className="detail-row">
                    <span className="detail-label">📷</span>
                    <span className="detail-value">{video.camera_name}</span>
                  </div>
                  
                  <div className="detail-row">
                    <span className="detail-label">⏱️</span>
                    <span className="detail-value">
                      {formatDuration(video.duration_seconds)} @ {Math.round(video.fps)}fps
                    </span>
                  </div>
                  
                  {video.annotation_count > 0 && (
                    <div className="detail-row">
                      <span className="detail-label">📦</span>
                      <span className="detail-value">{video.annotation_count} annotations</span>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="video-actions">
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
      
      {videos.length > 0 && trainingStatus && !trainingStatus.ready_for_review && (
        <div className="progress-footer">
          <div className="progress-message">
            <span className="progress-icon">📊</span>
            <span>
              {10 - trainingStatus.video_count} more video{10 - trainingStatus.video_count !== 1 ? 's' : ''} needed 
              before review process can begin
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoLibrary
