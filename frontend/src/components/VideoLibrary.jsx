import { useState, useEffect, useRef } from 'react'
import './VideoLibrary.css'

function VideoLibrary({ onStartReview, onTrainModel }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [trainingStatus, setTrainingStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadedVideo, setUploadedVideo] = useState(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState('front')
  const [captureDateTime, setCaptureDateTime] = useState('')
  
  // Video player state
  const [showVideoPlayer, setShowVideoPlayer] = useState(false)
  const [playingVideo, setPlayingVideo] = useState(null)
  
  // Frame analysis state
  const [showFrameAnalysis, setShowFrameAnalysis] = useState(false)
  const [analysisVideo, setAnalysisVideo] = useState(null)
  const [videoFrames, setVideoFrames] = useState([])
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const thumbnailRefs = useRef([])
  
  // Hamburger menu state
  const [openMenuId, setOpenMenuId] = useState(null)

  useEffect(() => {
    loadVideos()
    loadTrainingStatus()
  }, [])
  
  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (openMenuId && !event.target.closest('.video-menu')) {
        setOpenMenuId(null)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [openMenuId])

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

  const toggleMenu = (videoId, event) => {
    event.stopPropagation()
    setOpenMenuId(openMenuId === videoId ? null : videoId)
  }
  
  const handleMenuAction = (action, video, event) => {
    event.stopPropagation()
    setOpenMenuId(null)
    
    switch(action) {
      case 'frames':
        handleViewFrames(video)
        break
      case 'annotate':
        onStartReview(video.id)
        break
      case 'edit':
        handleEditVideo(video)
        break
      case 'delete':
        deleteVideo(video.id, video.filename)
        break
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

      // Navigate to review
      if (onStartReview) {
        onStartReview()
      }
    } catch (error) {
      console.error('Error starting review:', error)
      alert('❌ Failed to start review: ' + error.message)
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
      
      // Try to use recording timestamp from metadata, otherwise default to now
      let defaultDateTime
      if (result.recording_timestamp) {
        try {
          // Parse the recording timestamp (format: "YYYY-MM-DD HH:MM:SS")
          // Replace space with 'T' to make it ISO 8601 compatible
          const isoTimestamp = result.recording_timestamp.replace(' ', 'T')
          const recordingDate = new Date(isoTimestamp)
          defaultDateTime = new Date(recordingDate.getTime() - recordingDate.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, 16)
        } catch (e) {
          console.warn('Could not parse recording timestamp, using current time')
          const now = new Date()
          defaultDateTime = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, 16)
        }
      } else {
        // Default to current time if no metadata found
        const now = new Date()
        defaultDateTime = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16)
      }
      setCaptureDateTime(defaultDateTime)
      
      // Set default camera from detected_camera, or default to 'side'
      if (result.detected_camera) {
        setSelectedCamera(result.detected_camera.toLowerCase())
      } else {
        setSelectedCamera('side')
      }
      
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

  const handlePlayVideo = (video) => {
    setPlayingVideo(video)
    setShowVideoPlayer(true)
  }

  const handleViewFrames = async (video) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/${video.id}`)
      if (!response.ok) throw new Error('Failed to load video details')
      
      const data = await response.json()
      setAnalysisVideo(video)
      setVideoFrames(data.frames || [])
      setCurrentFrameIndex(0)
      setShowFrameAnalysis(true)
    } catch (error) {
      console.error('Error loading frames:', error)
      alert('Failed to load video frames')
    }
  }

  const handleNextFrame = () => {
    if (currentFrameIndex < videoFrames.length - 1) {
      setCurrentFrameIndex(currentFrameIndex + 1)
    }
  }

  const handlePrevFrame = () => {
    if (currentFrameIndex > 0) {
      setCurrentFrameIndex(currentFrameIndex - 1)
    }
  }

  // Keyboard navigation for frame analysis
  useEffect(() => {
    if (!showFrameAnalysis) return

    const handleKeyDown = (e) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        handlePrevFrame()
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        handleNextFrame()
      } else if (e.key === 'Escape') {
        e.preventDefault()
        setShowFrameAnalysis(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showFrameAnalysis, currentFrameIndex, videoFrames.length])

  // Auto-scroll thumbnail carousel to center selected frame
  useEffect(() => {
    if (!showFrameAnalysis || videoFrames.length === 0) return
    
    const activeThumbnail = thumbnailRefs.current[currentFrameIndex]
    if (activeThumbnail) {
      activeThumbnail.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'center'
      })
    }
  }, [currentFrameIndex, showFrameAnalysis, videoFrames.length])

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const formatCameraName = (video) => {
    // Use camera_name from database (updated by backend)
    if (video.camera_name && video.camera_name !== 'Manual Upload' && video.camera_name !== 'Unknown Camera') {
      return video.camera_name
    }
    // Use camera field if available (for edit dialog)
    if (video.camera) {
      const names = {
        'side': 'Side',
        'driveway': 'Driveway',
        'front': 'Front',
        'backyard': 'Backyard'
      }
      return names[video.camera] || video.camera
    }
    return '—'
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
          
          <button 
            className="btn-train-model"
            onClick={onTrainModel}
            title="Train model with collected annotations"
          >
            🚀 Train Model
          </button>
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
              <div 
                className="video-thumbnail"
                onClick={() => handlePlayVideo(video)}
                style={{ cursor: 'pointer' }}
                title="Click to play video"
              >
                {video.video_path ? (
                  <img 
                    src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/videos/${video.id}/thumbnail`}
                    alt={video.filename}
                    className="thumbnail-image"
                    onError={(e) => {
                      e.target.style.display = 'none'
                      e.target.nextElementSibling.style.display = 'flex'
                    }}
                  />
                ) : null}
                <div className="thumbnail-placeholder" style={video.video_path ? { display: 'none' } : {}}>
                  <span className="thumbnail-icon">🎥</span>
                </div>
                <div className="play-overlay">
                  <div className="play-button">▶</div>
                </div>
                <div className="video-stats">
                  <span className="stat-badge">{video.frame_count} frames</span>
                  <span className="stat-badge">{video.detection_count} detections</span>
                  {video.fully_annotated && (
                    <span className="stat-badge stat-badge-success" title="Annotations complete">
                      ✓
                    </span>
                  )}
                </div>
                
                {/* Hamburger Menu Button */}
                <button 
                  className="video-menu-btn"
                  onClick={(e) => toggleMenu(video.id, e)}
                  title="Video actions"
                >
                  ⋮
                </button>
                
                {/* Dropdown Menu */}
                {openMenuId === video.id && (
                  <div className="video-menu">
                    <button 
                      className="menu-item"
                      onClick={(e) => handleMenuAction('frames', video, e)}
                    >
                      <span className="menu-icon">📊</span>
                      <span>Frames</span>
                    </button>
                    <button 
                      className="menu-item"
                      onClick={(e) => handleMenuAction('annotate', video, e)}
                    >
                      <span className="menu-icon">✏️</span>
                      <span>Annotate</span>
                    </button>
                    <button 
                      className="menu-item"
                      onClick={(e) => handleMenuAction('edit', video, e)}
                    >
                      <span className="menu-icon">📝</span>
                      <span>Edit</span>
                    </button>
                    <button 
                      className="menu-item menu-item-delete"
                      onClick={(e) => handleMenuAction('delete', video, e)}
                      disabled={deleting === video.id}
                    >
                      <span className="menu-icon">🗑️</span>
                      <span>{deleting === video.id ? 'Wait...' : 'Delete'}</span>
                    </button>
                  </div>
                )}
              </div>
              
              <div className="video-info">
                <h3 className="video-title">{video.filename}</h3>
                
                <div className="video-metadata">
                  <span className="metadata-left">{formatDate(video.captured_at || video.upload_date)}</span>
                  <span className="metadata-right">{formatCameraName(video)}</span>
                </div>
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
              
              <div className="form-group">
                <label>Duration & Frame Rate</label>
                <input
                  type="text"
                  value={uploadedVideo.video_id ? 
                    `${formatDuration(videos.find(v => v.id === uploadedVideo.video_id)?.duration_seconds || 0)} @ ${Math.round(videos.find(v => v.id === uploadedVideo.video_id)?.fps || 0)}fps` : 
                    'N/A'
                  }
                  disabled
                  className="form-input-disabled"
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

      {/* Video Player Modal */}
      {showVideoPlayer && playingVideo && (
        <div className="dialog-overlay" onClick={() => setShowVideoPlayer(false)}>
          <div className="video-player-modal" onClick={(e) => e.stopPropagation()}>
            <div className="video-player-header">
              <h2>{playingVideo.filename}</h2>
              <button 
                className="btn-close-modal"
                onClick={() => setShowVideoPlayer(false)}
              >
                ✕
              </button>
            </div>
            <div className="video-player-content">
              <video 
                controls 
                autoPlay
                className="video-player"
                src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/videos/${playingVideo.id}/stream`}
              >
                Your browser does not support video playback.
              </video>
            </div>
            <div className="video-player-info">
              <span>{formatCameraName(playingVideo)}</span>
              <span>•</span>
              <span>{formatDate(playingVideo.captured_at || playingVideo.upload_date)}</span>
              <span>•</span>
              <span>{playingVideo.frame_count} frames</span>
              <span>•</span>
              <span>{playingVideo.detection_count} detections</span>
            </div>
          </div>
        </div>
      )}

      {/* Frame Analysis Modal */}
      {showFrameAnalysis && analysisVideo && (
        <div className="dialog-overlay" onClick={() => setShowFrameAnalysis(false)}>
          <div className="frame-analysis-modal" onClick={(e) => e.stopPropagation()}>
            <div className="frame-analysis-header">
              <div className="header-content">
                <h2>🔍 {analysisVideo.filename}</h2>
                {videoFrames.length > 0 && videoFrames[currentFrameIndex] && (
                  <div className="frame-metadata">
                    <span className="meta-highlight">Frame {currentFrameIndex + 1} of {videoFrames.length}</span>
                    <span>•</span>
                    <span>#{videoFrames[currentFrameIndex].frame_number}</span>
                    <span>•</span>
                    <span>{videoFrames[currentFrameIndex].timestamp_in_video?.toFixed(2)}s</span>
                    <span>•</span>
                    <span>{videoFrames[currentFrameIndex].detection_count || 0} detections</span>
                  </div>
                )}
              </div>
              <button 
                className="btn-close-modal"
                onClick={() => setShowFrameAnalysis(false)}
              >
                ✕
              </button>
            </div>
            
            {videoFrames.length === 0 ? (
              <div className="no-frames">
                <p>No frames extracted from this video yet.</p>
              </div>
            ) : (
              <>
                <div className="frame-viewer">
                  <button 
                    className="frame-nav-btn prev"
                    onClick={handlePrevFrame}
                    disabled={currentFrameIndex === 0}
                  >
                    ‹
                  </button>
                  
                  <div className="frame-display">
                    <img 
                      src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/frames/${videoFrames[currentFrameIndex]?.id}/annotated`}
                      alt={`Frame ${videoFrames[currentFrameIndex]?.frame_number}`}
                      className="frame-image"
                    />
                  </div>
                  
                  <button 
                    className="frame-nav-btn next"
                    onClick={handleNextFrame}
                    disabled={currentFrameIndex >= videoFrames.length - 1}
                  >
                    ›
                  </button>
                </div>
                
                <div className="frame-navigation">
                  <div className="frame-thumbnails">
                    {videoFrames.map((frame, idx) => (
                      <div
                        key={frame.id}
                        ref={el => thumbnailRefs.current[idx] = el}
                        className={`frame-thumb ${idx === currentFrameIndex ? 'active' : ''} ${frame.detection_count > 0 ? 'has-detection' : ''}`}
                        onClick={() => setCurrentFrameIndex(idx)}
                        title={`Frame ${frame.frame_number} - ${frame.detection_count} detections`}
                      >
                        <img 
                          src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${frame.image_path}`}
                          alt={`Thumb ${idx}`}
                        />
                        {frame.detection_count > 0 && (
                          <div className="detection-badge">{frame.detection_count}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoLibrary
