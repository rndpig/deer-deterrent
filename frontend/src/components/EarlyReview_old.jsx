import { useState, useEffect, useRef } from 'react'
import './EarlyReview.css'

function EarlyReview({ onBack }) {
  const [frames, setFrames] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [trainingStats, setTrainingStats] = useState(null)
  
  // Drawing state
  const [drawing, setDrawing] = useState(false)
  const [currentBox, setCurrentBox] = useState(null)
  const [manualBoxes, setManualBoxes] = useState([])
  
  // Canvas ref for drawing bounding boxes
  const canvasRef = useRef(null)
  const imageRef = useRef(null)

  // Current frame
  const currentFrame = frames[currentIndex]

  // Draw bounding boxes on canvas when frame changes
  useEffect(() => {
    if (!currentFrame || !imageRef.current || !canvasRef.current) return
    
    const img = imageRef.current
    const canvas = canvasRef.current
    
    // Wait for image to load
    const drawBoxes = () => {
      try {
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        
        // Set canvas dimensions to match image
        canvas.width = img.naturalWidth
        canvas.height = img.naturalHeight
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        
        // Draw detections (model predictions)
        if (currentFrame.detections && currentFrame.detections.length > 0) {
          currentFrame.detections.forEach((det, idx) => {
            // Draw bounding box
            ctx.strokeStyle = '#10b981' // Green for model predictions
            ctx.lineWidth = 3
            ctx.strokeRect(
              det.bbox_x * canvas.width,
              det.bbox_y * canvas.height,
              det.bbox_width * canvas.width,
              det.bbox_height * canvas.height
            )
            
            // Draw label
            ctx.fillStyle = '#10b981'
            ctx.font = '14px Arial'
            ctx.fillText(
              `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`,
              det.bbox_x * canvas.width + 5,
              det.bbox_y * canvas.height - 5
            )
          })
        }
        
        // Draw manual annotations
        if (currentFrame.annotations && currentFrame.annotations.length > 0) {
          currentFrame.annotations.forEach((box, idx) => {
            ctx.strokeStyle = '#3b82f6' // Blue for manual annotations
            ctx.lineWidth = 3
            ctx.strokeRect(
              box.x * canvas.width,
              box.y * canvas.height,
              box.width * canvas.width,
              box.height * canvas.height
            )
            
            ctx.fillStyle = '#3b82f6'
            ctx.font = '14px Arial'
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
  }, [currentFrame])

  useEffect(() => {
    loadFrames()
    loadTrainingStats()
  }, [])

  const loadFrames = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/training/frames`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('Loaded training frames:', data.length, 'items')
      
      // Filter only unreviewed frames
      const unreviewed = data.filter(f => !f.reviewed)
      console.log('Unreviewed frames:', unreviewed.length)
      
      setFrames(unreviewed)
      setCurrentIndex(0)
    } catch (error) {
      console.error('Error loading frames:', error)
      alert(`Failed to load frames: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const loadTrainingStats = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    
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

  const reviewFrame = async (reviewType) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    const frame = frames[currentIndex]
    
    if (!frame) return

    try {
      const response = await fetch(`${apiUrl}/api/frames/${frame.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          review_type: reviewType,
          reviewer: 'user'
        })
      })
      
      if (response.ok) {
        // Mark as reviewed in local state
        const updated = [...frames]
        updated[currentIndex] = { ...frame, reviewed: true, review_type: reviewType }
        setFrames(updated)
        
        // Auto-advance to next unreviewed
        if (currentIndex < frames.length - 1) {
          setCurrentIndex(currentIndex + 1)
        }
        
        // Reload stats
        loadTrainingStats()
      }
    } catch (error) {
      console.error('Error reviewing frame:', error)
      alert('❌ Error submitting review')
    }
  }

  const handleKeyPress = (e) => {
    // Don't trigger if user is typing in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
    
    if (e.key === 'ArrowRight') nextFrame()
    if (e.key === 'ArrowLeft') previousFrame()
    if (e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault()
      setShowAnnotationTool(true)
    }
    if (e.key === 'c' || e.key === 'C') reviewFrame('correct')
  }

  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [currentIndex, frames])

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

  const handleAnnotationSave = async (annotations) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    const frame = frames[currentIndex]
    
    try {
      const response = await fetch(`${apiUrl}/api/frames/${frame.id}/annotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ annotations })
      })
      
      if (response.ok) {
        // Update frame with new annotations
        const updated = [...frames]
        updated[currentIndex] = {
          ...frame,
          annotations: annotations.map(ann => ({
            x: ann.x,
            y: ann.y,
            width: ann.width,
            height: ann.height
          }))
        }
        setFrames(updated)
        setShowAnnotationTool(false)
        
        // Auto-mark as reviewed after annotation
        await reviewFrame('corrected')
      }
    } catch (error) {
      console.error('Error saving annotations:', error)
      alert('Failed to save annotations')
    }
  }

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

  const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
  const imageUrl = currentFrame.image_url?.startsWith('http') 
    ? currentFrame.image_url 
    : `${apiUrl}${currentFrame.image_url}`

  return (
    <div className="early-review-container">
      {/* Compact header with all info in one line */}
      <div className="review-header">
        <button className="btn-back-to-library" onClick={onBack}>
          ← Back
        </button>
        
        <div className="header-info">
          <span className="frame-counter"><strong>{currentIndex + 1}</strong> / {frames.length}</span>
          <span className="divider">|</span>
          <span>Video: {currentFrame.video_filename}</span>
          <span className="divider">|</span>
          <span>Frame: {currentFrame.frame_number}</span>
          <span className="divider">|</span>
          <span>Time: {currentFrame.timestamp_in_video?.toFixed(2)}s</span>
          <span className="divider">|</span>
          <span>Detections: {currentFrame.detection_count || 0}</span>
          <span className="divider">|</span>
          <span>Manual: {currentFrame.annotation_count || 0}</span>
        </div>

        <div className="header-actions">
          <button className="btn-header btn-prev" onClick={previousFrame} disabled={currentIndex === 0}>
            ←
          </button>
          <button className="btn-header btn-next" onClick={nextFrame} disabled={currentIndex === frames.length - 1}>
            →
          </button>
          <button className="btn-header btn-correct" onClick={() => reviewFrame('correct')}>
            ✓ Correct
          </button>
          <button className="btn-header btn-annotate" onClick={() => setShowAnnotationTool(true)}>
            ✏️ Add Box
          </button>
          <button className="btn-header btn-skip" onClick={nextFrame}>
            Skip
          </button>
        </div>
      </div>

      {/* Fullscreen image viewer */}
      <div className="review-content">
        <div className="image-container">
          <img 
            ref={imageRef}
            src={imageUrl}
            alt="Frame"
            className="frame-image"
          />
          <canvas 
            ref={canvasRef}
            className="frame-canvas"
          />
        </div>
      </div>

      {/* Footer with shortcuts */}
      <div className="review-footer">
        <span><strong>Shortcuts:</strong> Arrow Keys • C (correct) • Space (add box)</span>
        <span className="divider">|</span>
        <span><strong>Colors:</strong> <span style={{color: '#10b981'}}>Green = Model</span> • <span style={{color: '#3b82f6'}}>Blue = Manual</span></span>
      </div>

      {showAnnotationTool && (
        <AnnotationTool
          imageSrc={imageUrl}
          existingAnnotations={currentFrame.annotations || []}
          existingDetections={currentFrame.detections || []}
          onSave={handleAnnotationSave}
          onCancel={() => setShowAnnotationTool(false)}
          isOpen={showAnnotationTool}
          setIsOpen={setShowAnnotationTool}
        />
      )}
    </div>
  )
}

export default EarlyReview


