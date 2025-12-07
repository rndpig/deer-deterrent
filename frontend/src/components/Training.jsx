import { useState, useEffect, useRef } from 'react'
import './Training.css'
import AnnotationTool from './AnnotationTool'
import VideoLibrary from './VideoLibrary'
import VideoSelector from './VideoSelector'
import EarlyReview from './EarlyReview'

function Training() {
  const [viewMode, setViewMode] = useState('library') // 'library', 'selector', or 'review'
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [detections, setDetections] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [trainingStats, setTrainingStats] = useState(null)
  const [filter, setFilter] = useState('unreviewed') // unreviewed, all, reviewed
  
  // Video upload state
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const [showVideoSection, setShowVideoSection] = useState(true)
  const [sampleRate, setSampleRate] = useState(15) // Default: every 15th frame (~2/sec at 30fps)
  const [estimatedFrames, setEstimatedFrames] = useState(0)
  
  // Annotation tool state
  const [showAnnotationTool, setShowAnnotationTool] = useState(false)
  const [annotating, setAnnotating] = useState(false)
  
  // Camera selection for uploaded frames
  const [selectedCamera, setSelectedCamera] = useState('Front')
  const cameraOptions = ['Front', 'Side', 'Driveway', 'Backyard']
  
  // Canvas ref for drawing bounding boxes
  const canvasRef = useRef(null)
  const imageRef = useRef(null)

  // Current detection
  const currentDetection = detections[currentIndex]

  // Draw bounding boxes on canvas when detection changes
  useEffect(() => {
    if (!currentDetection || !imageRef.current || !canvasRef.current) return
    
    const img = imageRef.current
    const canvas = canvasRef.current
    
    // Wait for image to load
    const drawBoxes = () => {
      try {
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        
        canvas.width = img.naturalWidth || img.width
        canvas.height = img.naturalHeight || img.height
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        
        // Draw auto-detected boxes (green solid)
        if (currentDetection.detections?.length > 0) {
          ctx.strokeStyle = '#10b981'
          ctx.lineWidth = 3
          ctx.setLineDash([])
          
          currentDetection.detections.forEach(det => {
            const bbox = det.bbox
            ctx.strokeRect(
              bbox.x1,
              bbox.y1,
              bbox.x2 - bbox.x1,
              bbox.y2 - bbox.y1
            )
            
            // Draw label
            ctx.fillStyle = '#10b981'
            ctx.fillRect(bbox.x1, bbox.y1 - 20, 80, 20)
            ctx.fillStyle = 'white'
            ctx.font = '12px Arial'
            ctx.fillText(`Auto ${(det.confidence * 100).toFixed(0)}%`, bbox.x1 + 5, bbox.y1 - 5)
          })
        }
        
        // Draw manual annotation boxes (orange dashed)
        if (currentDetection.manual_annotations?.length > 0) {
          ctx.strokeStyle = '#f59e0b'
          ctx.lineWidth = 3
          ctx.setLineDash([8, 4])
          
          currentDetection.manual_annotations.forEach((box, idx) => {
            ctx.strokeRect(
              box.x * canvas.width,
              box.y * canvas.height,
              box.width * canvas.width,
              box.height * canvas.height
            )
            
            // Draw label
            ctx.setLineDash([])
            ctx.fillStyle = '#f59e0b'
            ctx.fillRect(box.x * canvas.width, box.y * canvas.height - 20, 70, 20)
            ctx.fillStyle = 'white'
            ctx.font = '12px Arial'
            ctx.fillText(`Manual ${idx + 1}`, box.x * canvas.width + 5, box.y * canvas.height - 5)
          })
        }
      } catch (error) {
        console.error('Error drawing boxes:', error)
      }
    }
    
    if (img.complete && img.naturalWidth > 0) {
      drawBoxes()
    } else {
      img.onload = drawBoxes
    }
  }, [currentDetection])

  useEffect(() => {
    loadDetections()
    loadTrainingStats()
  }, [filter])

  const loadDetections = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    // If in review mode, load training frames instead of all detections
    const endpoint = viewMode === 'review' 
      ? `${apiUrl}/api/training/frames`
      : `${apiUrl}/api/detections?limit=200`
    
    console.log('Loading detections from:', endpoint)
    
    try {
      const response = await fetch(endpoint)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('Loaded detections:', data.length, 'items')
      
      // Filter based on selection (only for legacy detections endpoint)
      let filtered = data
      if (viewMode !== 'review') {
        if (filter === 'unreviewed') {
          filtered = data.filter(d => !d.reviewed)
        } else if (filter === 'reviewed') {
          filtered = data.filter(d => d.reviewed)
        }
      }
      
      console.log('Filtered detections:', filtered.length, 'items (filter:', filter, ')')
      setDetections(filtered)
      setCurrentIndex(0)
    } catch (error) {
      console.error('Error loading detections:', error)
      alert(`Failed to load detections: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const loadTrainingStats = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/training/stats`)
      if (response.ok) {
        const data = await response.json()
        setTrainingStats(data)
      }
    } catch (error) {
      console.error('Error loading training stats:', error)
    }
  }

  const reviewDetection = async (reviewType, correctedCount = null) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const detection = detections[currentIndex]
    
    if (!detection) return

    try {
      const payload = {
        detection_id: detection.id,
        review_type: reviewType,
        reviewer: 'user'
      }
      
      if (correctedCount !== null) {
        payload.corrected_deer_count = correctedCount
      }

      const response = await fetch(`${apiUrl}/api/detections/${detection.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      if (response.ok) {
        // Mark as reviewed in local state
        const updated = [...detections]
        updated[currentIndex] = { ...detection, reviewed: true, review_type: reviewType }
        setDetections(updated)
        
        // Auto-advance to next unreviewed
        if (filter === 'unreviewed' && currentIndex < detections.length - 1) {
          setCurrentIndex(currentIndex + 1)
        }
        
        // Reload stats
        loadTrainingStats()
      }
    } catch (error) {
      console.error('Error reviewing detection:', error)
      alert('❌ Error submitting review')
    }
  }

  const handleKeyPress = (e) => {
    // Don't trigger if user is typing in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
    
    if (e.key === 'ArrowRight') nextDetection()
    if (e.key === 'ArrowLeft') previousDetection()
    if (e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault()
      setShowAnnotationTool(true)
    }
    if (e.key === 'c' || e.key === 'C') reviewDetection('correct')
    if (e.key === 'Delete') deleteCurrentFrame()
  }

  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [currentIndex, detections])

  const nextDetection = () => {
    if (currentIndex < detections.length - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }

  const previousDetection = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  const exportAndSync = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setSyncing(true)
    
    try {
      // Export
      const exportResponse = await fetch(`${apiUrl}/api/training/export`)
      if (!exportResponse.ok) throw new Error('Export failed')
      const exportData = await exportResponse.json()
      
      // Sync to Drive
      const syncResponse = await fetch(`${apiUrl}/api/training/sync-to-drive`, {
        method: 'POST'
      })
      if (!syncResponse.ok) throw new Error('Drive sync failed')
      const syncData = await syncResponse.json()
      
      alert(`✅ Success!\n\n📦 ${exportData.total_images} images exported\n☁️ Synced: ${syncData.version}\n\nReady for Google Colab training!`)
      
    } catch (error) {
      console.error('Error:', error)
      alert('❌ Error: ' + error.message)
    } finally {
      setSyncing(false)
    }
  }

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file) {
      const validTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/avi']
      if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|mov|avi)$/i)) {
        setUploadError('Please select a valid video file (MP4, MOV, or AVI)')
        return
      }
      
      if (file.size > 100 * 1024 * 1024) {
        setUploadError('File size must be less than 100MB')
        return
      }
      
      setSelectedFile(file)
      setUploadError(null)
      setUploadSuccess(null)
      
      // Estimate frames (assume 30fps, will be adjusted by actual video)
      const videoElement = document.createElement('video')
      videoElement.preload = 'metadata'
      videoElement.onloadedmetadata = () => {
        const duration = videoElement.duration
        const fps = 30 // Estimate, actual will be calculated on backend
        const totalFrames = Math.floor(duration * fps)
        const estimated = Math.floor(totalFrames / sampleRate)
        setEstimatedFrames(estimated)
        URL.revokeObjectURL(videoElement.src)
      }
      videoElement.src = URL.createObjectURL(file)
    }
  }

  const handleVideoUpload = async () => {
    if (!selectedFile) return
    
    setUploading(true)
    setUploadError(null)
    setUploadSuccess(null)
    
    const formData = new FormData()
    formData.append('video', selectedFile)
    formData.append('sample_rate', sampleRate.toString())
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/upload`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }
      
      const data = await response.json()
      setUploadSuccess(`✅ Video processed! ${data.frames_extracted} frames extracted (every ${sampleRate}${sampleRate === 1 ? 'st' : sampleRate === 2 ? 'nd' : sampleRate === 3 ? 'rd' : 'th'} frame), ${data.detections_found} with detections. Scroll down to review frames below.`)
      setSelectedFile(null)
      setEstimatedFrames(0)
      
      // Close upload section to show review interface
      setShowVideoSection(false)
      
      // Switch to 'All' filter to show newly uploaded frames
      // The useEffect will automatically reload when filter changes
      setFilter('all')
      setCurrentIndex(0)
      loadTrainingStats()
      
    } catch (err) {
      setUploadError(err.message || 'Error processing video')
      console.error('Upload error:', err)
    } finally {
      setUploading(false)
    }
  }

  const handleResetUpload = () => {
    setSelectedFile(null)
    setUploadError(null)
    setUploadSuccess(null)
  }

  const handleSaveAnnotations = async (boxes) => {
    if (!currentDetection) return
    
    setAnnotating(true)
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/detections/${currentDetection.id}/annotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bounding_boxes: boxes,
          deer_count: boxes.length,
          annotator: 'user'
        })
      })
      
      if (response.ok) {
        // Update local detection with annotations
        setDetections(prev => prev.map(d => 
          d.id === currentDetection.id 
            ? { ...d, manual_annotations: boxes, deer_count: boxes.length }
            : d
        ))
        setShowAnnotationTool(false)
        loadTrainingStats()
      } else {
        alert('❌ Error saving annotations')
      }
    } catch (error) {
      console.error('Error saving annotations:', error)
      alert('❌ Error saving annotations')
    } finally {
      setAnnotating(false)
    }
  }

  const deleteCurrentFrame = async () => {
    if (!currentDetection) return
    
    if (!confirm('Delete this frame? This cannot be undone.')) return
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/detections/${currentDetection.id}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        // Remove from local state
        const newDetections = detections.filter(d => d.id !== currentDetection.id)
        setDetections(newDetections)
        
        // Adjust index if needed
        if (currentIndex >= newDetections.length) {
          setCurrentIndex(Math.max(0, newDetections.length - 1))
        }
        
        loadTrainingStats()
      } else {
        alert('❌ Error deleting frame')
      }
    } catch (error) {
      console.error('Error deleting frame:', error)
      alert('❌ Error deleting frame')
    }
  }

  const clearAllFrames = async () => {
    if (detections.length === 0) return
    
    const message = filter === 'all' 
      ? `Delete all ${detections.length} frames? This cannot be undone.`
      : filter === 'reviewed'
      ? `Delete all ${detections.length} reviewed frames? This cannot be undone.`
      : `Delete all ${detections.length} unreviewed frames? This cannot be undone.`
    
    if (!confirm(message)) return
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const ids = detections.map(d => d.id)
      const response = await fetch(`${apiUrl}/api/detections/batch-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ids)
      })
      
      if (response.ok) {
        const data = await response.json()
        setDetections([])
        setCurrentIndex(0)
        loadTrainingStats()
        alert(`✅ Deleted ${data.deleted_count} frames`)
      } else {
        alert('❌ Error deleting frames')
      }
    } catch (error) {
      console.error('Error deleting frames:', error)
      alert('❌ Error deleting frames')
    }
  }

  const handleStartReview = async (videoId = null) => {
    if (videoId) {
      // Direct annotation: find the video and go straight to review
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      
      try {
        // First, get the video details
        const videoResponse = await fetch(`${apiUrl}/api/videos/${videoId}`)
        if (!videoResponse.ok) {
          throw new Error('Failed to load video')
        }
        const video = await videoResponse.json()
        
        // Check if frames are already extracted
        const checkResponse = await fetch(`${apiUrl}/api/videos/${videoId}/has-frames`)
        if (checkResponse.ok) {
          const checkData = await checkResponse.json()
          
          if (checkData.has_frames && checkData.frame_count > 0) {
            // Frames exist, go directly to review
            setSelectedVideo(video)
            setViewMode('review')
            setFilter('unreviewed')
            return
          }
        }
        
        // No frames exist, need to extract them first - go to selector
        alert('This video needs frames extracted first. Please select a sampling rate.')
        setViewMode('selector')
        
      } catch (err) {
        console.error('Error loading video:', err)
        alert('Failed to load video for annotation')
      }
    } else {
      // Go to selector view (old behavior)
      setViewMode('selector')
    }
  }

  const handleVideoSelected = (video) => {
    // Frames have been extracted or will be extracted, go to review view
    setSelectedVideo(video)
    setViewMode('review')
    setFilter('unreviewed')
    loadDetections()
  }

  const handleBackToSelector = () => {
    setViewMode('selector') // Go back to video selector
    setSelectedVideo(null)
  }

  const handleBackFromSelector = () => {
    setViewMode('library')
  }

  const handleTrainModel = async () => {
    // Placeholder for model training
    alert('Model training feature coming soon!\n\nThis will:\n1. Export all annotations to YOLO format\n2. Upload to training environment\n3. Start model training\n4. Download improved model')
  }

  // Show library view
  if (viewMode === 'library') {
    return (
      <div className="training-container">
        <VideoLibrary 
          onStartReview={handleStartReview}
          onTrainModel={handleTrainModel}
        />
      </div>
    )
  }

  // Show video selector view
  if (viewMode === 'selector') {
    return (
      <VideoSelector 
        onBack={handleBackFromSelector}
        onVideoSelected={handleVideoSelected}
        onTrainModel={handleTrainModel}
      />
    )
  }

  // Show review view
  if (viewMode === 'review') {
    return (
      <EarlyReview 
        onBack={handleBackToSelector}
        selectedVideo={selectedVideo}
      />
    )
  }

  if (loading) {
    return (
      <div className="training-container">
        <div className="loading">Loading detections...</div>
      </div>
    )
  }

  // Debug logging
  console.log('Detections:', detections.length, 'Current:', currentIndex, 'Detection:', currentDetection)

  return (
    <div className="training-container">
      <div className="training-header">
        <div className="header-row">
          <button 
            className="btn-back-to-library"
            onClick={handleBackToLibrary}
            title="Back to Video Library"
          >
            ← Back to Library
          </button>
          <h1>🎓 Frame Review</h1>
        </div>
        
        {/* Video Upload Section */}
        <div className="video-upload-section">
          <button 
            className="section-toggle"
            onClick={() => setShowVideoSection(!showVideoSection)}
          >
            🎥 Upload Video for Analysis {showVideoSection ? '▼' : '▶'}
          </button>
          
          {showVideoSection && (
            <div className="upload-panel">
              <p className="upload-description">
                Upload Ring footage with missed deer detections. Video will be split into frames 
                and processed for review.
              </p>
              
              <div className="sampling-controls">
                <label className="sampling-label">
                  <span className="label-text">Frame Sampling Rate:</span>
                  <select 
                    value={sampleRate} 
                    onChange={(e) => setSampleRate(parseInt(e.target.value))}
                    className="sampling-select"
                  >
                    <option value="10">High Detail (every 10th frame, ~3/sec)</option>
                    <option value="15">Balanced (every 15th frame, ~2/sec) - Recommended</option>
                    <option value="30">Quick Review (every 30th frame, ~1/sec)</option>
                    <option value="60">Sparse (every 60th frame, ~0.5/sec)</option>
                  </select>
                </label>
                {selectedFile && estimatedFrames > 0 && (
                  <span className="frame-estimate">
                    📊 Estimated: ~{estimatedFrames} frames to review
                  </span>
                )}
              </div>
              
              <div className="file-input-wrapper">
                <input 
                  type="file" 
                  id="video-file"
                  accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.avi"
                  onChange={handleFileSelect}
                  disabled={uploading}
                  style={{ display: 'none' }}
                />
                <label htmlFor="video-file" className="file-select-label">
                  {selectedFile ? (
                    <span>📹 {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)</span>
                  ) : (
                    <span>⬆️ Choose Video File (MP4, MOV, AVI - max 100MB)</span>
                  )}
                </label>
                
                {selectedFile && !uploading && (
                  <div className="upload-actions-inline">
                    <button className="btn-primary" onClick={handleVideoUpload}>
                      🔍 Process Video
                    </button>
                    <button className="btn-secondary" onClick={handleResetUpload}>
                      Clear
                    </button>
                  </div>
                )}
              </div>
              
              {uploading && (
                <div className="upload-status">
                  <div className="spinner-small"></div>
                  <span>Processing video... Extracting frames and running detection...</span>
                </div>
              )}
              
              {uploadError && (
                <div className="error-banner">⚠️ {uploadError}</div>
              )}
              
              {uploadSuccess && (
                <div className="success-banner">{uploadSuccess}</div>
              )}
            </div>
          )}
        </div>

        <div className="training-actions">
          <div className="filter-group">
            <button 
              className={filter === 'unreviewed' ? 'active' : ''}
              onClick={() => setFilter('unreviewed')}
            >
              Unreviewed ({detections.filter(d => !d.reviewed).length})
            </button>
            <button 
              className={filter === 'all' ? 'active' : ''}
              onClick={() => setFilter('all')}
            >
              All
            </button>
            <button 
              className={filter === 'reviewed' ? 'active' : ''}
              onClick={() => setFilter('reviewed')}
            >
              Reviewed ({detections.filter(d => d.reviewed).length})
            </button>
          </div>
          
          <div className="action-buttons">
            {trainingStats && (
              <div className="training-badge-compact" title={`Reviewed: ${trainingStats.reviewed_detections} | Correct: ${trainingStats.review_breakdown.correct} | False: ${trainingStats.review_breakdown.false_positive}`}>
                {trainingStats.ready_for_training 
                  ? '✅ Ready to Train' 
                  : `📊 ${trainingStats.reviewed_detections}/50 reviewed`
                }
              </div>
            )}
            {detections.length > 0 && (
              <button 
                className="clear-button"
                onClick={clearAllFrames}
                title={filter === 'all' ? 'Delete all frames' : `Delete all ${filter} frames`}
              >
                🗑️ Clear {filter === 'all' ? 'All' : filter === 'reviewed' ? 'Reviewed' : 'Unreviewed'}
              </button>
            )}
            <button 
              className="sync-button"
              onClick={exportAndSync}
              disabled={syncing || !trainingStats?.ready_for_training}
            >
              {syncing ? '⏳ Syncing...' : '☁️ Export & Sync to Drive'}
            </button>
          </div>
        </div>
      </div>

      {detections.length === 0 ? (
        <div className="empty-state">
          <h2>No detections to review</h2>
          <p>
            {filter === 'unreviewed' 
              ? 'All detections have been reviewed! 🎉'
              : 'No detections found. Wait for deer to be detected or load demo data.'
            }
          </p>
        </div>
      ) : (
        <>
          {/* Fullscreen Review Interface */}
          <div className="fullscreen-review">
            {/* Compact header with all info in one line */}
            <div className="review-header">
              <button className="btn-back-to-library-compact" onClick={handleBackToLibrary}>
                ← Back
              </button>
              
              <div className="header-info">
                <span className="frame-counter"><strong>{currentIndex + 1}</strong> / {detections.length}</span>
                <span className="divider">|</span>
                <span>Camera: {currentDetection.camera_name}</span>
                <span className="divider">|</span>
                <span>Frame: {currentDetection.frame_number || 'N/A'}</span>
                <span className="divider">|</span>
                <span className="info-badge-inline green">Auto: {currentDetection.deer_count}</span>
                <span className="divider">|</span>
                <span className="info-badge-inline blue">Manual: {currentDetection.manual_annotations?.length || 0}</span>
                {currentDetection.reviewed && (
                  <>
                    <span className="divider">|</span>
                    <span className="info-badge-inline reviewed">✓ {currentDetection.review_type}</span>
                  </>
                )}
              </div>

              <div className="header-actions">
                <button className="btn-header btn-prev" onClick={previousDetection} disabled={currentIndex === 0}>
                  ←
                </button>
                <button className="btn-header btn-next" onClick={nextDetection} disabled={currentIndex === detections.length - 1}>
                  →
                </button>
                <button 
                  className="btn-header btn-correct" 
                  onClick={() => reviewDetection('correct')}
                  disabled={currentDetection?.reviewed}
                >
                  ✓ Correct
                </button>
                <button 
                  className="btn-header btn-annotate" 
                  onClick={() => setShowAnnotationTool(true)}
                  disabled={currentDetection?.reviewed && currentDetection?.review_type === 'correct'}
                >
                  ✏️ Add Box
                </button>
                <button className="btn-header btn-skip" onClick={nextDetection}>
                  Skip
                </button>
              </div>
            </div>

            {/* Fullscreen image viewer */}
            <div className="review-content">
              <div className="image-container-fullscreen">
                {currentDetection.image_path ? (
                  <>
                    <img 
                      ref={imageRef}
                      src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${currentDetection.image_path}`}
                      alt="Detection"
                      className="frame-image-fullscreen"
                      onError={(e) => {
                        console.error('Image failed to load:', e)
                      }}
                    />
                    <canvas 
                      ref={canvasRef}
                      className="frame-canvas-fullscreen"
                    />
                  </>
                ) : (
                  <div className="no-image">
                    <p>📷 No image available</p>
                  </div>
                )}
              </div>
            </div>

            {/* Footer with shortcuts and legend */}
            <div className="review-footer">
              <span><strong>Shortcuts:</strong> Arrow Keys • C (correct) • Space (add box)</span>
              <span className="divider">|</span>
              <span><strong>Colors:</strong> <span style={{color: '#10b981'}}>Green = Model</span> • <span style={{color: '#3b82f6'}}>Blue = Manual</span></span>
            </div>
          </div>
        </>
      )}
      
      {/* Annotation Tool Modal */}
      {showAnnotationTool && currentDetection && (
        <AnnotationTool
          imageSrc={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${currentDetection.image_path}`}
          existingBoxes={currentDetection.manual_annotations || []}
          onSave={handleSaveAnnotations}
          onCancel={() => setShowAnnotationTool(false)}
        />
      )}
    </div>
  )
}

export default Training
