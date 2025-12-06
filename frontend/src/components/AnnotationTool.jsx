import { useState, useRef, useEffect } from 'react'
import './AnnotationTool.css'

function AnnotationTool({ imageSrc, existingBoxes = [], onSave, onCancel }) {
  const canvasRef = useRef(null)
  const [boxes, setBoxes] = useState(existingBoxes)
  const [drawing, setDrawing] = useState(false)
  const [currentBox, setCurrentBox] = useState(null)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 })
  const imageRef = useRef(null)

  useEffect(() => {
    const img = new Image()
    img.onload = () => {
      setImageDimensions({ width: img.width, height: img.height })
      setImageLoaded(true)
      imageRef.current = img
      redrawCanvas()
    }
    img.src = imageSrc
  }, [imageSrc])

  useEffect(() => {
    if (imageLoaded) {
      redrawCanvas()
    }
  }, [boxes, imageLoaded])

  const redrawCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas || !imageRef.current) return

    const ctx = canvas.getContext('2d')
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // Draw image
    ctx.drawImage(imageRef.current, 0, 0, canvas.width, canvas.height)
    
    // Calculate scale factors
    const scaleX = canvas.width / imageDimensions.width
    const scaleY = canvas.height / imageDimensions.height
    
    // Draw existing boxes (stored in normalized 0-1 coordinates)
    ctx.strokeStyle = '#10b981'
    ctx.lineWidth = 3
    ctx.fillStyle = 'rgba(16, 185, 129, 0.1)'
    
    boxes.forEach((box, index) => {
      // Convert normalized coordinates to canvas coordinates
      const x = box.x * canvas.width
      const y = box.y * canvas.height
      const w = box.width * canvas.width
      const h = box.height * canvas.height
      
      ctx.fillRect(x, y, w, h)
      ctx.strokeRect(x, y, w, h)
      
      // Draw box number
      ctx.fillStyle = '#10b981'
      ctx.font = 'bold 16px sans-serif'
      ctx.fillText(`Deer ${index + 1}`, x + 5, y + 20)
      ctx.fillStyle = 'rgba(16, 185, 129, 0.1)'
    })
    
    // Draw current box being drawn
    if (currentBox) {
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
    
    // Get mouse position relative to canvas display
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    
    // Scale from display size to canvas internal size
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
    
    // Get mouse position relative to canvas display
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    
    // Scale from display size to canvas internal size
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = mouseX * scaleX
    const y = mouseY * scaleY
    
    const width = x - currentBox.x
    const height = y - currentBox.y
    
    setCurrentBox({ ...currentBox, width, height })
    redrawCanvas()
  }

  const handleMouseUp = () => {
    if (!drawing || !currentBox) return
    
    // Only add box if it has meaningful size
    if (Math.abs(currentBox.width) > 10 && Math.abs(currentBox.height) > 10) {
      // Normalize box (handle negative width/height from dragging up/left)
      let { x, y, width, height } = currentBox
      if (width < 0) {
        x += width
        width = Math.abs(width)
      }
      if (height < 0) {
        y += height
        height = Math.abs(height)
      }
      
      // Convert canvas coordinates to normalized coordinates (0-1 range)
      const canvas = canvasRef.current
      
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

  const handleSave = () => {
    onSave(boxes)
  }

  const handleClear = () => {
    setBoxes([])
  }

  return (
    <div className="annotation-tool-modal">
      <div className="annotation-tool-fullscreen">
        <div className="annotation-header-compact">
          <h2>📦 Draw Bounding Boxes</h2>
          <button className="close-btn" onClick={onCancel}>✕</button>
        </div>
        
        <div className="annotation-main-area">
          <div className="annotation-canvas-full">
            {!imageLoaded && <div className="loading">Loading image...</div>}
            <canvas
              ref={canvasRef}
              width={1920}
              height={1080}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              style={{ cursor: drawing ? 'crosshair' : 'default' }}
            />
          </div>
          
          <div className="annotation-sidebar-compact">
            <div className="annotation-instructions-compact">
              <p>🖱️ Click and drag to draw a box around each deer</p>
              <p>📐 Draw tight boxes around the deer's body</p>
              <p>🗑️ Click "Remove" to undo mistakes</p>
            </div>
            
            <div className="box-list-compact">
              <h3>Bounding Boxes ({boxes.length})</h3>
              {boxes.length === 0 ? (
                <p className="no-boxes">No boxes drawn yet</p>
              ) : (
                <ul>
                  {boxes.map((box, index) => (
                    <li key={index}>
                      <span>Deer {index + 1}</span>
                      <button 
                        className="remove-box-btn"
                        onClick={() => handleRemoveBox(index)}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
        
        <div className="annotation-actions">
          <button 
            className="btn-secondary" 
            onClick={handleClear}
            disabled={boxes.length === 0}
          >
            Clear All
          </button>
          <button 
            className="btn-secondary" 
            onClick={onCancel}
          >
            Cancel
          </button>
          <button 
            className="btn-primary" 
            onClick={handleSave}
            disabled={boxes.length === 0}
          >
            Save {boxes.length} Box{boxes.length !== 1 ? 'es' : ''}
          </button>
        </div>
      </div>
    </div>
  )
}

export default AnnotationTool
