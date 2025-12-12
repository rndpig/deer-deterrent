import { useState, useEffect, useRef } from 'react'
import './EarlyReview.css'

function EarlyReview({ onBack, selectedVideo }) {
  const [frames, setFrames] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  
  // Drawing state
  const [drawing, setDrawing] = useState(false)
  const [currentBox, setCurrentBox] = useState(null)
  const [drawnBoxes, setDrawnBoxes] = useState([])
  
  const canvasRef = useRef(null)
  const imageRef = useRef(null)

  const currentFrame = frames[currentIndex]

  // Load manual boxes when frame changes
  useEffect(() => {
    if (currentFrame) {
      console.log('Loading frame:', currentFrame.id, 'with', currentFrame.detection_count, 'detections')
      console.log('Frame data:', currentFrame)
      console.log('Annotations count:', currentFrame.annotation_count)
      console.log('Annotations array:', currentFrame.annotations)
      
      // Convert existing annotations to drawn boxes format
      const existing = (currentFrame.annotations || []).map(ann => ({
        x: ann.x,
        y: ann.y,
        width: ann.width,
        height: ann.height
      }))
      
      console.log('Loaded manual boxes:', existing.length)
      setDrawnBoxes(existing)
    }
  }, [currentFrame])

  // Redraw canvas when anything changes
  useEffect(() => {
    redrawCanvas()
  }, [currentFrame, drawnBoxes, currentBox, drawing])

  const redrawCanvas = () => {
    if (!currentFrame || !imageRef.current || !canvasRef.current) return
    
    const img = imageRef.current
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    
    if (!ctx || !img.complete || img.naturalWidth === 0) return
    
    // Wait for layout to complete before getting client dimensions
    if (img.clientWidth === 0 || img.clientHeight === 0) {
      requestAnimationFrame(() => redrawCanvas())
      return
    }
    
    // Set canvas size to match DISPLAYED image size, not natural size
    // This ensures coordinates align with what the user sees
    canvas.width = img.clientWidth
    canvas.height = img.clientHeight
    
    console.log('Canvas size:', canvas.width, 'x', canvas.height)
    console.log('Image natural:', img.naturalWidth, 'x', img.naturalHeight)
    console.log('Scale factors:', canvas.width / img.naturalWidth, canvas.height / img.naturalHeight)
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // Debug logging
    console.log('Frame detections:', currentFrame.detections)
    console.log('Manual boxes:', drawnBoxes)
    
    // Draw model detections (green)
    if (currentFrame.detections && currentFrame.detections.length > 0) {
      currentFrame.detections.forEach((det, idx) => {
        // Detections come with bbox object containing x1, y1, x2, y2
        const bbox = det.bbox
        
        console.log(`Detection ${idx}:`, bbox)
        
        // Check if coordinates are normalized (0-1) or pixel values
        const isNormalized = bbox.x1 <= 1 && bbox.y1 <= 1 && bbox.x2 <= 1 && bbox.y2 <= 1
        
        console.log('Is normalized?', isNormalized)
        
        // Scale from natural image size to displayed canvas size
        const scaleX = canvas.width / img.naturalWidth
        const scaleY = canvas.height / img.naturalHeight
        
        const x1 = isNormalized ? bbox.x1 * canvas.width : bbox.x1 * scaleX
        const y1 = isNormalized ? bbox.y1 * canvas.height : bbox.y1 * scaleY
        const x2 = isNormalized ? bbox.x2 * canvas.width : bbox.x2 * scaleX
        const y2 = isNormalized ? bbox.y2 * canvas.height : bbox.y2 * scaleY
        
        console.log('Scaled coordinates:', { x1, y1, x2, y2 })
        
        const x = x1
        const y = y1
        const w = x2 - x1
        const h = y2 - y1
        
        ctx.strokeStyle = '#10b981'
        ctx.lineWidth = 3
        ctx.strokeRect(x, y, w, h)
        
        ctx.fillStyle = '#10b981'
        ctx.font = '14px Arial'
        ctx.fillText(
          `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`,
          x + 5,
          y - 5
        )
      })
    }
    
    // Draw manual boxes (blue)
    drawnBoxes.forEach((box, idx) => {
      ctx.strokeStyle = '#3b82f6'
      ctx.lineWidth = 3
      ctx.strokeRect(
        box.x * canvas.width,
        box.y * canvas.height,
        box.width * canvas.width,
        box.height * canvas.height
      )
      
      ctx.fillStyle = '#3b82f6'
      ctx.font = '14px Arial'
      ctx.fillText(`Deer ${idx + 1}`, box.x * canvas.width + 5, box.y * canvas.height - 5)
    })
    
    // Draw current box being drawn (dashed blue)
    if (currentBox && drawing) {
      ctx.strokeStyle = '#2563eb'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.strokeRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height)
      ctx.setLineDash([])
    }
  }

  const handleMouseDown = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = mouseX * scaleX
    const y = mouseY * scaleY
    
    setDrawing(true)
    setCurrentBox({ x, y, width: 0, height: 0 })
  }

  const handleMouseMove = (e) => {
    if (!drawing || !currentBox) return
    
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = mouseX * scaleX
    const y = mouseY * scaleY
    
    const width = x - currentBox.x
    const height = y - currentBox.y
    
    setCurrentBox({ ...currentBox, width, height })
  }

  const handleMouseUp = () => {
    if (!drawing || !currentBox) return
    
    // Only add box if it has meaningful size
    if (Math.abs(currentBox.width) > 10 && Math.abs(currentBox.height) > 10) {
      let { x, y, width, height } = currentBox
      
      // Normalize negative dimensions
      if (width < 0) {
        x += width
        width = Math.abs(width)
      }
      if (height < 0) {
        y += height
        height = Math.abs(height)
      }
      
      // Convert to normalized coordinates (0-1)
      const canvas = canvasRef.current
      const normalizedBox = {
        x: x / canvas.width,
        y: y / canvas.height,
        width: width / canvas.width,
        height: height / canvas.height
      }
      
      setDrawnBoxes([...drawnBoxes, normalizedBox])
    }
    
    setDrawing(false)
    setCurrentBox(null)
  }

  const handleRemoveBox = async (index) => {
    const updatedBoxes = drawnBoxes.filter((_, i) => i !== index)
    setDrawnBoxes(updatedBoxes)
    
    // Save immediately to persist the deletion
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/frames/${currentFrame.id}/annotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          annotations: updatedBoxes
        })
      })
      
      if (response.ok) {
        console.log(`✓ Removed box ${index + 1}, saved ${updatedBoxes.length} remaining boxes`)
        // Update local frame data
        const updated = [...frames]
        updated[currentIndex] = {
          ...currentFrame,
          annotations: updatedBoxes,
          annotation_count: updatedBoxes.length
        }
        setFrames(updated)
      } else {
        console.error('Failed to save after removal:', response.status)
        alert('❌ Failed to save removal. Please try again.')
        // Revert the UI change
        setDrawnBoxes(drawnBoxes)
      }
    } catch (error) {
      console.error('Error saving removal:', error)
      alert('❌ Error saving removal. Please try again.')
      // Revert the UI change
      setDrawnBoxes(drawnBoxes)
    }
  }

  const handleSaveBoxes = async () => {
    if (drawnBoxes.length === 0) return
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    console.log('Saving annotations for frame:', currentFrame.id)
    console.log('Boxes to save:', drawnBoxes)
    
    try {
      const response = await fetch(`${apiUrl}/api/frames/${currentFrame.id}/annotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          annotations: drawnBoxes
        })
      })
      
      if (response.ok) {
        const result = await response.json()
        console.log('Annotations saved successfully:', result)
        
        // Update local frame data with saved annotations
        const updated = [...frames]
        updated[currentIndex] = {
          ...currentFrame,
          annotations: drawnBoxes,
          annotation_count: drawnBoxes.length,
          reviewed: true
        }
        setFrames(updated)
        
        // Move to next frame
        if (currentIndex < frames.length - 1) {
          setCurrentIndex(currentIndex + 1)
        }
      } else {
        const errorText = await response.text()
        console.error('Server error:', response.status, errorText)
        alert(`❌ Error saving annotations: ${response.status} - ${errorText}`)
      }
    } catch (error) {
      console.error('Error saving annotations:', error)
      alert(`❌ Error saving annotations: ${error.message}`)
    }
  }

  const handleClearBoxes = async () => {
    setDrawnBoxes([])
    
    // Save immediately to persist the clearing
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/frames/${currentFrame.id}/annotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          annotations: []
        })
      })
      
      if (response.ok) {
        console.log('✓ Cleared all manual boxes')
        // Update local frame data
        const updated = [...frames]
        updated[currentIndex] = {
          ...currentFrame,
          annotations: [],
          annotation_count: 0
        }
        setFrames(updated)
      } else {
        console.error('Failed to save clear operation:', response.status)
        alert('❌ Failed to clear boxes. Please try again.')
      }
    } catch (error) {
      console.error('Error clearing boxes:', error)
      alert('❌ Error clearing boxes. Please try again.')
    }
  }

  const handleClearFrames = async () => {
    if (!selectedVideo) return
    
    if (!confirm(`Delete all extracted frames for video "${currentFrame.video_filename}"? You will need to re-extract frames to annotate again.`)) {
      return
    }
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/${selectedVideo.id}/clear-frames`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        const result = await response.json()
        alert(`✓ Deleted ${result.frames_deleted} frames. Returning to video selection.`)
        onBack()
      } else {
        const errorData = await response.json().catch(() => ({}))
        const errorMsg = errorData.detail || response.statusText || 'Unknown error'
        console.error('Clear frames error:', errorMsg)
        alert(`❌ Failed to clear frames: ${errorMsg}`)
      }
    } catch (error) {
      console.error('Error clearing frames:', error)
      alert(`❌ Error: ${error.message}`)
    }
  }

  useEffect(() => {
    loadFrames()
  }, [])

  const loadFrames = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/training/frames`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      console.log('=== FRAMES LOADED FROM API ===')
      console.log(`Total frames from API: ${data.length}`)
      
      // Filter by selected video if provided
      let filteredFrames = data
      if (selectedVideo) {
        filteredFrames = data.filter(f => f.video_id === selectedVideo.id)
        console.log(`Filtered to ${filteredFrames.length} frames from video ${selectedVideo.id}`)
        console.log('Sample frame data:', filteredFrames[0])
        console.log('Frames with detections:', filteredFrames.filter(f => f.detections && f.detections.length > 0).length)
        console.log('Frames without detections:', filteredFrames.filter(f => !f.detections || f.detections.length === 0).length)
      }
      
      // Show ALL frames for the video (don't filter out reviewed ones)
      // User needs to see all frames to review/annotate them
      setFrames(filteredFrames)
      setCurrentIndex(0)
    } catch (error) {
      console.error('Error loading frames:', error)
      alert(`Failed to load frames: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const reviewFrame = async (reviewType) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    if (!currentFrame) return

    try {
      const response = await fetch(`${apiUrl}/api/frames/${currentFrame.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          review_type: reviewType,
          reviewer: 'user'
        })
      })
      
      if (response.ok) {
        // Mark frame as reviewed locally
        const updated = [...frames]
        updated[currentIndex] = { ...currentFrame, reviewed: true, review_type: reviewType }
        setFrames(updated)
        
        // Move to next frame automatically
        if (currentIndex < frames.length - 1) {
          setCurrentIndex(currentIndex + 1)
        }
      } else {
        const errorText = await response.text()
        console.error('Review error:', response.status, errorText)
        alert(`❌ Error marking frame as ${reviewType}: ${response.status} - ${errorText}`)
      }
    } catch (error) {
      console.error('Error reviewing frame:', error)
      alert(`❌ Error submitting review: ${error.message}`)
    }
  }

  const nextFrame = () => {
    if (currentIndex < frames.length - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }

  const previousFrame = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  const handleKeyPress = (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
    
    if (e.key === 'ArrowRight') nextFrame()
    if (e.key === 'ArrowLeft') previousFrame()
    if (e.key === 'c' || e.key === 'C') reviewFrame('correct')
    if (e.key === 's' || e.key === 'S') handleSaveBoxes()
  }

  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [currentIndex, frames, drawnBoxes])

  if (loading) {
    return (
      <div className="early-review-container">
        <div className="loading-message">Loading frames...</div>
      </div>
    )
  }

  if (frames.length === 0) {
    return (
      <div className="early-review-container">
        <div className="empty-state">
          <h2>No frames to review</h2>
          <p>All sampled frames have been reviewed! 🎉</p>
          <p>Go back to the Video Library to upload more videos.</p>
        </div>
      </div>
    )
  }

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const imageUrl = currentFrame.image_url?.startsWith('http') 
    ? currentFrame.image_url 
    : `${apiUrl}${currentFrame.image_url}`

  // Check if all frames are annotated
  const allAnnotated = frames.every(f => f.annotation_count > 0 || f.reviewed)
  const annotatedCount = frames.filter(f => f.annotation_count > 0 || f.reviewed).length

  return (
    <div className="review-container-with-sidebar">
      {/* Header */}
      <div className="review-header-compact">
        <button className="btn-back" onClick={onBack}>← Back</button>
        <span className="frame-counter"><strong>{currentIndex + 1}</strong> / {frames.length}</span>
        {allAnnotated && (
          <span className="completion-badge">✓ Complete</span>
        )}
        {!allAnnotated && annotatedCount > 0 && (
          <span style={{fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginLeft: 'auto'}}>
            {annotatedCount} / {frames.length} annotated
          </span>
        )}
        <span style={{fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)', marginLeft: allAnnotated || annotatedCount === 0 ? 'auto' : '0.5rem'}}>
          {currentFrame.video_filename}
        </span>
        <span style={{fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)'}}>
          F:{currentFrame.frame_number}
        </span>
        <span style={{fontSize: '0.8rem', color: '#10b981'}}>A:{currentFrame.detection_count || 0}</span>
        <span style={{fontSize: '0.8rem', color: '#3b82f6'}}>M:{currentFrame.annotation_count || 0}</span>
        
        <div className="header-actions">
          <button className="btn-nav" onClick={previousFrame} disabled={currentIndex === 0}>←</button>
          <button className="btn-nav" onClick={nextFrame} disabled={currentIndex === frames.length - 1}>→</button>
          <button 
            className={`btn-correct ${currentFrame.review_type === 'correct' ? 'active' : ''}`}
            onClick={() => reviewFrame('correct')}
          >
            ✓ Correct
          </button>
          <button 
            className={`btn-no-deer ${currentFrame.review_type === 'no_deer' ? 'active' : ''}`}
            onClick={() => reviewFrame('no_deer')}
          >
            ∅ No Deer
          </button>
          <button 
            className="btn-clear-frames" 
            onClick={handleClearFrames}
          >
            🗑️ Clear All
          </button>
        </div>
      </div>

      <div className="review-main-area">
        {/* Canvas area */}
        <div className="canvas-area">
          <div className="image-wrapper">
            <img 
              ref={imageRef}
              src={imageUrl}
              alt="Frame"
              className="review-image"
              onLoad={() => redrawCanvas()}
            />
            <canvas 
              ref={canvasRef}
              className="drawing-canvas"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              style={{ 
                cursor: 'crosshair',
                width: imageRef.current?.clientWidth || 0,
                height: imageRef.current?.clientHeight || 0
              }}
            />
          </div>
        </div>

        {/* Sidebar */}
        <div className="annotation-sidebar">
          <h3>🎯 Add Bounding Boxes</h3>
          <p className="instructions">Click and drag on the image to draw a box around each deer</p>
          
          <div className="box-list">
            <h4>Boxes ({drawnBoxes.length})</h4>
            {drawnBoxes.length === 0 ? (
              <p className="no-boxes">No boxes drawn yet</p>
            ) : (
              <ul>
                {drawnBoxes.map((box, index) => (
                  <li key={index}>
                    <span>Deer {index + 1}</span>
                    <button 
                      className="btn-remove"
                      onClick={() => handleRemoveBox(index)}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="sidebar-actions">
            <button 
              className="btn-clear"
              onClick={handleClearBoxes}
              disabled={drawnBoxes.length === 0}
            >
              Clear All
            </button>
            <button 
              className="btn-save-primary"
              onClick={handleSaveBoxes}
              disabled={drawnBoxes.length === 0}
            >
              Save {drawnBoxes.length} Box{drawnBoxes.length !== 1 ? 'es' : ''}
            </button>
          </div>
        </div>
      </div>

      {/* Footer with legend and shortcuts */}
      <div className="review-footer">
        <div className="footer-legend">
          <span><strong>Colors:</strong></span>
          <span style={{color: '#10b981'}}>■ Green</span> = Model Detections
          <span className="divider">•</span>
          <span style={{color: '#3b82f6'}}>■ Blue</span> = Manual Boxes
        </div>
        <div className="footer-shortcuts">
          <span><strong>Shortcuts:</strong></span>
          <span>← → Arrow Keys</span>
          <span className="divider">•</span>
          <span>C = Mark Correct</span>
          <span className="divider">•</span>
          <span>S = Save Boxes</span>
        </div>
      </div>
    </div>
  )
}

export default EarlyReview
