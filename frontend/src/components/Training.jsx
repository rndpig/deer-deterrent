import { useState, useEffect } from 'react'
import './Training.css'
import AnnotationTool from './AnnotationTool'

function Training() {
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

  useEffect(() => {
    loadDetections()
    loadTrainingStats()
  }, [filter])

  const loadDetections = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/detections?limit=200`)
      const data = await response.json()
      
      // Filter based on selection
      let filtered = data
      if (filter === 'unreviewed') {
        filtered = data.filter(d => !d.reviewed)
      } else if (filter === 'reviewed') {
        filtered = data.filter(d => d.reviewed)
      }
      
      setDetections(filtered)
      setCurrentIndex(0)
    } catch (error) {
      console.error('Error loading detections:', error)
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
    if (e.key === 'ArrowRight') nextDetection()
    if (e.key === 'ArrowLeft') previousDetection()
    if (e.key === '1') reviewDetection('correct')
    if (e.key === '2') reviewDetection('false_positive')
    if (e.key === '3') {
      const count = prompt('Enter correct deer count:')
      if (count) reviewDetection('incorrect_count', parseInt(count))
    }
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

  const currentDetection = detections[currentIndex]

  if (loading) {
    return (
      <div className="training-container">
        <div className="loading">Loading detections...</div>
      </div>
    )
  }

  return (
    <div className="training-container">
      <div className="training-header">
        <h1>🎓 Model Improvement</h1>
        
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
        
        {trainingStats && (
          <div className="training-progress">
            <div className="progress-stat">
              <span className="progress-label">Reviewed</span>
              <span className="progress-value">{trainingStats.reviewed_detections}</span>
            </div>
            <div className="progress-stat">
              <span className="progress-label">Correct</span>
              <span className="progress-value correct">{trainingStats.review_breakdown.correct}</span>
            </div>
            <div className="progress-stat">
              <span className="progress-label">False Positive</span>
              <span className="progress-value false">{trainingStats.review_breakdown.false_positive}</span>
            </div>
            <div className={`readiness-badge ${trainingStats.ready_for_training ? 'ready' : 'not-ready'}`}>
              {trainingStats.ready_for_training 
                ? '✅ Ready' 
                : `Need ${50 - trainingStats.reviewed_detections} more`
              }
            </div>
          </div>
        )}

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
        <div className="review-interface">
          <div className="image-viewer">
            <div className="navigation-controls">
              <button 
                onClick={previousDetection}
                disabled={currentIndex === 0}
                className="nav-button"
              >
                ← Previous
              </button>
              
              <span className="image-counter">
                {currentIndex + 1} / {detections.length}
              </span>
              
              <button 
                onClick={nextDetection}
                disabled={currentIndex === detections.length - 1}
                className="nav-button"
              >
                Next →
              </button>
            </div>

            {currentDetection && (
              <>
                <div className="image-container">
                  {currentDetection.image_path ? (
                    <img 
                      src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${currentDetection.image_path}`}
                      alt="Detection"
                      className="detection-image"
                    />
                  ) : (
                    <div className="no-image">
                      <p>📷 No image available</p>
                    </div>
                  )}
                </div>

                <div className="detection-info">
                  <div className="info-row">
                    <span className="info-label">Camera:</span>
                    <span className="info-value">{currentDetection.camera_name}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Zone:</span>
                    <span className="info-value">{currentDetection.zone_name}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Deer Count:</span>
                    <span className="info-value deer-count">🦌 {currentDetection.deer_count}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Confidence:</span>
                    <span className="info-value">{(currentDetection.max_confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Time:</span>
                    <span className="info-value">{new Date(currentDetection.timestamp).toLocaleString()}</span>
                  </div>
                  {currentDetection.reviewed && (
                    <div className="info-row reviewed-status">
                      <span className="info-label">Status:</span>
                      <span className="info-value reviewed">
                        ✓ Reviewed as {currentDetection.review_type}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="review-panel">
            <h2>Review This Detection</h2>
            
            <div className="review-buttons-large">
              <button 
                className="review-button correct"
                onClick={() => reviewDetection('correct')}
                disabled={currentDetection?.reviewed}
              >
                <div className="button-icon">✓</div>
                <div className="button-label">Correct</div>
                <div className="button-hint">Keyboard: 1</div>
              </button>
              
              <button 
                className="review-button false-positive"
                onClick={() => reviewDetection('false_positive')}
                disabled={currentDetection?.reviewed}
              >
                <div className="button-icon">✗</div>
                <div className="button-label">False Positive</div>
                <div className="button-hint">Keyboard: 2</div>
              </button>
              
              <button 
                className="review-button incorrect-count"
                onClick={() => {
                  const count = prompt('Enter correct deer count:')
                  if (count) reviewDetection('incorrect_count', parseInt(count))
                }}
                disabled={currentDetection?.reviewed}
              >
                <div className="button-icon">#</div>
                <div className="button-label">Wrong Count</div>
                <div className="button-hint">Keyboard: 3</div>
              </button>
            </div>
            
            <div className="annotation-section">
              <h3>📦 Missed Detection?</h3>
              <p className="annotation-hint">
                If deer were present but not detected, draw bounding boxes to improve the model.
              </p>
              <button 
                className="annotation-button"
                onClick={() => setShowAnnotationTool(true)}
                disabled={currentDetection?.reviewed}
              >
                ✏️ Draw Bounding Boxes
              </button>
              {currentDetection?.manual_annotations?.length > 0 && (
                <div className="annotation-status">
                  ✅ {currentDetection.manual_annotations.length} box{currentDetection.manual_annotations.length !== 1 ? 'es' : ''} drawn
                </div>
              )}
            </div>

            <div className="delete-section">
              <button 
                className="delete-button"
                onClick={deleteCurrentFrame}
                title="Delete this frame from the review queue"
              >
                🗑️ Delete This Frame
              </button>
            </div>

            <div className="keyboard-shortcuts">
              <h3>⌨️ Keyboard Shortcuts</h3>
              <div className="shortcut-list">
                <div className="shortcut">
                  <kbd>←</kbd> <kbd>→</kbd> <span>Navigate</span>
                </div>
                <div className="shortcut">
                  <kbd>1</kbd> <span>Mark Correct</span>
                </div>
                <div className="shortcut">
                  <kbd>2</kbd> <span>False Positive</span>
                </div>
                <div className="shortcut">
                  <kbd>3</kbd> <span>Wrong Count</span>
                </div>
              </div>
            </div>
          </div>
        </div>
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
