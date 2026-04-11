import { useState, useEffect, useRef } from 'react'
import './VideoLibrary.css'
import { apiFetch, API_URL } from '../api'

function VideoLibrary({ onStartReview, onTrainModel, syncing = false, onViewSnapshots, onViewArchive, hideSnapshotsButton = false }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [trainingStatus, setTrainingStatus] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadedVideo, setUploadedVideo] = useState(null)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [selectedCamera, setSelectedCamera] = useState('front')
  const [captureDateTime, setCaptureDateTime] = useState('')
  const [reanalyzing, setReanalyzing] = useState(false)
  const [reanalysisProgress, setReanalysisProgress] = useState(null)
  
  // Video player state
  const [showVideoPlayer, setShowVideoPlayer] = useState(false)
  const [playingVideo, setPlayingVideo] = useState(null)
  
  // Frame analysis state
  const [showFrameAnalysis, setShowFrameAnalysis] = useState(false)
  const [analysisVideo, setAnalysisVideo] = useState(null)
  const [videoFrames, setVideoFrames] = useState([])
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0)
  const thumbnailRefs = useRef([])
  
  // Annotation state
  const [annotationMode, setAnnotationMode] = useState(false)
  const [boxes, setBoxes] = useState([])
  const [drawing, setDrawing] = useState(false)
  const [currentBox, setCurrentBox] = useState(null)
  const [savingAnnotations, setSavingAnnotations] = useState(false)
  const [frameAnnotations, setFrameAnnotations] = useState({})
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const [imageLoaded, setImageLoaded] = useState(false)
  
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

  const loadVideos = async () => {    setLoading(true)
           try {
         const response = await apiFetch(`/api/videos`)
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
    const loadTrainingStatus = async () => {    try {
         const response = await apiFetch(`/api/videos/training/status`)
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
    }    setDeleting(videoId)
          try {
         const response = await apiFetch(`/api/videos/${videoId}`, {
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
    const archiveVideo = async (videoId, videoFilename) => {
    if (!confirm(`Archive "${videoFilename}"? This will hide it from the main gallery but preserve all data.`)) {
      return
    }
    try {
         const response = await apiFetch(`/api/videos/${videoId}/archive`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      // Reload videos
      await loadVideos()
      await loadTrainingStatus()
    } catch (error) {
      console.error('Error archiving video:', error)
      alert('Failed to archive video')
    }
  }
    const fillMissingFrames = async (videoId, videoFilename) => {
    if (!confirm(`Fill in missing frames for "${videoFilename}"? This will preserve all existing annotations.`)) {
      return
    }
    try {
         const response = await apiFetch(`/api/videos/${videoId}/fill-missing-frames`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to fill missing frames')
      }
              const result = await response.json()
      alert(`✅ Success! Added ${result.frames_added} missing frames. All annotations preserved.`)
      
      // Reload videos to update frame count
      await loadVideos()
      await loadTrainingStatus()
    } catch (error) {
      console.error('Error filling missing frames:', error)
      alert(`Failed to fill missing frames: ${error.message}`)
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
      case 'edit':
        handleEditVideo(video)
        break
      case 'archive':
        archiveVideo(video.id, video.filename)
        break
      case 'delete':
        deleteVideo(video.id, video.filename)
        break
    }
  }
    const handleStartReview = async () => {    try {
      // Trigger frame selection algorithm
      const response = await apiFetch(`/api/training/select-frames`, {
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
    const handleReanalyzeAll = async () => {    if (!confirm('🔄 Re-analyze all videos with the new model?\n\nThis will:\n1. Run the updated model on all videos\n2. Update detection counts\n3. Take a few minutes to complete\n\nContinue?')) {
      return
    }
    
    setReanalyzing(true)
    setReanalysisProgress({ current: 0, total: videos.length, results: [] })
          try {
         const response = await apiFetch(`/api/videos/reanalyze-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Re-analysis failed')
      }
              const result = await response.json()
      
      alert(
        `✅ Re-analysis complete!\n\n` +
        `Videos processed: ${result.processed}\n` +
        `Total detections: ${result.total_detections}\n` +
        `Average detections per video: ${(result.total_detections / result.processed).toFixed(1)}`
      )
      
      // Reload videos to show updated counts
      await loadVideos()
      
    } catch (error) {
      console.error('Re-analysis error:', error)
      alert(`❌ Re-analysis failed:\n\n${error.message}`)
    } finally {
      setReanalyzing(false)
      setReanalysisProgress(null)
    }
  }
    const handleVideoUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return    setUploading(true)
       try {
         const formData = new FormData()
      formData.append('video', file)

      const response = await apiFetch(`/api/videos/upload`, {
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
        const isEditing = !!videos.find(v => v.id === uploadedVideo.video_id)
      try {
      // Update video metadata
      const response = await apiFetch(`/api/videos/${uploadedVideo.video_id}`, {
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
        try {
      // Delete the uploaded video
      await apiFetch(`/api/videos/${uploadedVideo.video_id}`, {
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
      'Woods': 'woods',
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
    try {
      const response = await apiFetch(`/api/videos/${video.id}`)
      if (!response.ok) throw new Error('Failed to load video details')
      
      const data = await response.json()
      setAnalysisVideo(video)
      setVideoFrames(data.frames || [])
      setCurrentFrameIndex(0)
      setShowFrameAnalysis(true)
      // Reset annotation state
      setAnnotationMode(false)
      setBoxes([])
      setFrameAnnotations({})
      setImageLoaded(false)
    } catch (error) {
      console.error('Error loading frames:', error)
      alert('Failed to load video frames')
    }
  }

  // Load frame annotations when frame changes
  const loadFrameAnnotations = async (frameId) => {
    // Check cache first
    if (frameAnnotations[frameId]) {
      setBoxes(frameAnnotations[frameId])
      return
    }
    
    try {
      const response = await apiFetch(`/api/frames/${frameId}`)
      if (response.ok) {
        const data = await response.json()
        const annotations = (data.annotations || []).map(a => ({
          x: a.bbox_x,
          y: a.bbox_y,
          width: a.bbox_width,
          height: a.bbox_height
        }))
        setBoxes(annotations)
        setFrameAnnotations(prev => ({ ...prev, [frameId]: annotations }))
      }
    } catch (error) {
      console.error('Error loading annotations:', error)
    }
  }

  // Load annotations when frame changes in annotation mode
  useEffect(() => {
    if (showFrameAnalysis && annotationMode && videoFrames.length > 0) {
      const currentFrame = videoFrames[currentFrameIndex]
      if (currentFrame) {
        loadFrameAnnotations(currentFrame.id)
      }
    }
  }, [currentFrameIndex, annotationMode, showFrameAnalysis])

  const handleNextFrame = () => {
    if (currentFrameIndex < videoFrames.length - 1) {
      setCurrentFrameIndex(currentFrameIndex + 1)
      setImageLoaded(false)
    }
  }

  const handlePrevFrame = () => {
    if (currentFrameIndex > 0) {
      setCurrentFrameIndex(currentFrameIndex - 1)
      setImageLoaded(false)
    }
  }

  // Canvas drawing handlers
  const redrawCanvas = () => {
    const canvas = canvasRef.current
    const img = imageRef.current
    if (!canvas || !img || !imageLoaded) return

    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    // Draw existing boxes (normalized 0-1 coordinates)
    ctx.strokeStyle = '#10b981'
    ctx.lineWidth = 3
    ctx.fillStyle = 'rgba(16, 185, 129, 0.1)'
    
    boxes.forEach((box, index) => {
      const x = box.x * canvas.width
      const y = box.y * canvas.height
      const w = box.width * canvas.width
      const h = box.height * canvas.height
      
      ctx.fillRect(x, y, w, h)
      ctx.strokeRect(x, y, w, h)
      
      ctx.fillStyle = '#10b981'
      ctx.font = 'bold 14px sans-serif'
      ctx.fillText(`${index + 1}`, x + 5, y + 18)
      ctx.fillStyle = 'rgba(16, 185, 129, 0.1)'
    })
    
    // Draw current box being drawn
    if (currentBox) {
      ctx.strokeStyle = '#f59e0b'
      ctx.lineWidth = 3
      ctx.setLineDash([5, 5])
      ctx.fillStyle = 'rgba(245, 158, 11, 0.15)'
      ctx.fillRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height)
      ctx.strokeRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height)
      ctx.setLineDash([])
    }
  }

  useEffect(() => {
    if (annotationMode && imageLoaded) {
      redrawCanvas()
    }
  }, [boxes, currentBox, imageLoaded, annotationMode])

  const handleCanvasPointerDown = (e) => {
    if (!annotationMode) return
    const canvas = canvasRef.current
    canvas.setPointerCapture(e.pointerId)
    const rect = canvas.getBoundingClientRect()
    
    const pointerX = e.clientX - rect.left
    const pointerY = e.clientY - rect.top
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = pointerX * scaleX
    const y = pointerY * scaleY
    
    setDrawing(true)
    setCurrentBox({ x, y, width: 0, height: 0 })
  }

  const handleCanvasPointerMove = (e) => {
    if (!drawing || !currentBox) return
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    
    const pointerX = e.clientX - rect.left
    const pointerY = e.clientY - rect.top
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = pointerX * scaleX
    const y = pointerY * scaleY
    
    setCurrentBox({ ...currentBox, width: x - currentBox.x, height: y - currentBox.y })
  }

  const handleCanvasPointerUp = (e) => {
    if (!drawing || !currentBox) return
    const canvas = canvasRef.current
    canvas.releasePointerCapture(e.pointerId)
    
    // Only add box if it has meaningful size
    if (Math.abs(currentBox.width) > 10 && Math.abs(currentBox.height) > 10) {
      let { x, y, width, height } = currentBox
      if (width < 0) { x += width; width = Math.abs(width) }
      if (height < 0) { y += height; height = Math.abs(height) }
      
      const normalizedBox = {
        x: x / canvas.width,
        y: y / canvas.height,
        width: width / canvas.width,
        height: height / canvas.height
      }
      setBoxes([...boxes, normalizedBox])
    }
    
    setDrawing(false)
    setCurrentBox(null)
  }

  const handleRemoveBox = (index) => {
    setBoxes(boxes.filter((_, i) => i !== index))
  }

  const handleClearBoxes = () => {
    setBoxes([])
  }

  const handleSaveAnnotations = async () => {
    const currentFrame = videoFrames[currentFrameIndex]
    if (!currentFrame) return
    
    setSavingAnnotations(true)
    try {
      const response = await apiFetch(`/api/frames/${currentFrame.id}/annotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ annotations: boxes })
      })
      
      if (!response.ok) throw new Error('Failed to save annotations')
      
      // Update cache
      setFrameAnnotations(prev => ({ ...prev, [currentFrame.id]: boxes }))
      
      // Update frame detection count in the list
      setVideoFrames(prev => prev.map((f, i) => 
        i === currentFrameIndex 
          ? { ...f, annotation_count: boxes.length, detection_count: boxes.length }
          : f
      ))
      
    } catch (error) {
      console.error('Error saving annotations:', error)
      alert('Failed to save annotations')
    } finally {
      setSavingAnnotations(false)
    }
  }

  const toggleAnnotationMode = () => {
    const newMode = !annotationMode
    setAnnotationMode(newMode)
    if (newMode && videoFrames.length > 0) {
      const currentFrame = videoFrames[currentFrameIndex]
      if (currentFrame) {
        loadFrameAnnotations(currentFrame.id)
      }
    }
  }

  const handleImageLoad = (e) => {
    imageRef.current = e.target
    setImageLoaded(true)
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
        </div>
        
        <div className="header-right">
          {!hideSnapshotsButton && (
            <>
              <button 
                className="btn-view-snapshots"
                onClick={onViewSnapshots}
                title="View Ring snapshot collection"
              >
                📸 Snapshots
              </button>
            </>
          )}
          
          <button 
            className="btn-upload-video"
            onClick={handleUploadClick}
            disabled={uploading}
          >
            {uploading ? '⏳ Uploading...' : '📤 Upload Video'}
          </button>
          
          {!hideSnapshotsButton && (
            <button 
              className="btn-view-archive"
              onClick={onViewArchive}
              title="View archived videos"
            >
              📦 Archive
            </button>
          )}
          
          <button 
            className="btn-reanalyze"
            onClick={handleReanalyzeAll}
            title="Re-analyze all videos with updated model"
            disabled={uploading || syncing || reanalyzing || videos.length === 0}
          >
            {reanalyzing ? '⏳ Re-analyzing...' : '🔄 Re-analyze All'}
          </button>
          
          <button 
            className="btn-train-model"
            onClick={onTrainModel}
            title="Train model with collected annotations"
            disabled={uploading || syncing || reanalyzing}
          >
            {syncing ? '⏳ Exporting & syncing to Drive...' : '🚀 Train Model'}
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
                    src={`${API_URL}/api/videos/${video.id}/thumbnail`}
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
                      <span>Frames & Annotate</span>
                    </button>
                    <button 
                      className="menu-item"
                      onClick={(e) => handleMenuAction('edit', video, e)}
                    >
                      <span className="menu-icon">📝</span>
                      <span>Edit</span>
                    </button>
                    <button 
                      className="menu-item"
                      onClick={(e) => handleMenuAction('archive', video, e)}
                    >
                      <span className="menu-icon">🗄️</span>
                      <span>Archive</span>
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
                  <option value="woods">Woods</option>
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
                src={`${API_URL}/api/videos/${playingVideo.id}/stream`}
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

      {/* Frame Analysis Modal with Annotation */}
      {showFrameAnalysis && analysisVideo && (
        <div className="dialog-overlay" onClick={() => { setShowFrameAnalysis(false); setAnnotationMode(false); }}>
          <div className={`frame-analysis-modal ${annotationMode ? 'annotation-active' : ''}`} onClick={(e) => e.stopPropagation()}>
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
                    <span>{videoFrames[currentFrameIndex].annotation_count || videoFrames[currentFrameIndex].detection_count || 0} boxes</span>
                  </div>
                )}
              </div>
              <div className="header-actions">
                <button 
                  className={`btn-annotate-toggle ${annotationMode ? 'active' : ''}`}
                  onClick={toggleAnnotationMode}
                  title={annotationMode ? 'Exit annotation mode' : 'Enter annotation mode to draw bounding boxes'}
                >
                  {annotationMode ? '✏️ Drawing' : '✏️ Annotate'}
                </button>
                <button 
                  className="btn-close-modal"
                  onClick={() => { setShowFrameAnalysis(false); setAnnotationMode(false); }}
                >
                  ✕
                </button>
              </div>
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
                    {annotationMode ? (
                      <>
                        <img 
                          src={`${API_URL}/api/training-frames/${videoFrames[currentFrameIndex]?.image_path?.split('/').pop()}`}
                          alt={`Frame ${videoFrames[currentFrameIndex]?.frame_number}`}
                          className="frame-image-hidden"
                          onLoad={handleImageLoad}
                          crossOrigin="anonymous"
                        />
                        <canvas
                          ref={canvasRef}
                          width={1280}
                          height={720}
                          className="annotation-canvas"
                          onPointerDown={handleCanvasPointerDown}
                          onPointerMove={handleCanvasPointerMove}
                          onPointerUp={handleCanvasPointerUp}
                          style={{ cursor: drawing ? 'crosshair' : 'crosshair' }}
                        />
                      </>
                    ) : (
                      <img 
                        src={
                          (videoFrames[currentFrameIndex]?.annotation_count || videoFrames[currentFrameIndex]?.detection_count) > 0
                            ? `${API_URL}/api/frames/${videoFrames[currentFrameIndex]?.id}/annotated`
                            : `${API_URL}/api/training-frames/${videoFrames[currentFrameIndex]?.image_path?.split('/').pop()}`
                        }
                        alt={`Frame ${videoFrames[currentFrameIndex]?.frame_number}`}
                        className="frame-image"
                      />
                    )}
                  </div>
                  
                  <button 
                    className="frame-nav-btn next"
                    onClick={handleNextFrame}
                    disabled={currentFrameIndex >= videoFrames.length - 1}
                  >
                    ›
                  </button>
                </div>
                
                {/* Annotation Controls */}
                {annotationMode && (
                  <div className="annotation-controls">
                    <div className="annotation-info">
                      <span className="box-count">{boxes.length} box{boxes.length !== 1 ? 'es' : ''}</span>
                      {boxes.length > 0 && (
                        <div className="box-list">
                          {boxes.map((_, idx) => (
                            <button 
                              key={idx}
                              className="box-remove-btn"
                              onClick={() => handleRemoveBox(idx)}
                              title={`Remove box ${idx + 1}`}
                            >
                              🗑️ {idx + 1}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="annotation-actions">
                      <span className="annotation-hint">Click and drag to draw boxes around deer</span>
                      <button 
                        className="btn-clear-boxes"
                        onClick={handleClearBoxes}
                        disabled={boxes.length === 0}
                      >
                        Clear All
                      </button>
                      <button 
                        className="btn-save-annotations"
                        onClick={handleSaveAnnotations}
                        disabled={savingAnnotations}
                      >
                        {savingAnnotations ? '⏳ Saving...' : `💾 Save (${boxes.length})`}
                      </button>
                    </div>
                  </div>
                )}
                
                <div className="frame-navigation">
                  <div className="frame-thumbnails">
                    {videoFrames.map((frame, idx) => (
                      <div
                        key={frame.id}
                        ref={el => thumbnailRefs.current[idx] = el}
                        className={`frame-thumb ${idx === currentFrameIndex ? 'active' : ''} ${(frame.annotation_count || frame.detection_count) > 0 ? 'has-detection' : ''}`}
                        onClick={() => { setCurrentFrameIndex(idx); setImageLoaded(false); }}
                        title={`Frame ${frame.frame_number} - ${frame.annotation_count || frame.detection_count || 0} boxes`}
                      >
                        <img 
                          src={`${API_URL}/api/training-frames/${frame.image_path.split('/').pop()}`}
                          alt={`Thumb ${idx}`}
                        />
                        {(frame.annotation_count || frame.detection_count) > 0 && (
                          <div className="detection-badge">{frame.annotation_count || frame.detection_count}</div>
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


