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

  // Size of the ✕ delete button drawn on each box (in canvas internal pixels)
  const X_BTN_SIZE = 32

  // Compute the ✕ button hit area for a normalized box, in canvas internal coords
  const xButtonRect = (box, canvas) => {
    const x = box.x * canvas.width
    const y = box.y * canvas.height
    const w = box.width * canvas.width
    return { x: x + w - X_BTN_SIZE, y: y, w: X_BTN_SIZE, h: X_BTN_SIZE }
  }

  const redrawCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas || !imageRef.current) return

    const ctx = canvas.getContext('2d')
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    // Draw image
    ctx.drawImage(imageRef.current, 0, 0, canvas.width, canvas.height)
    
    // Draw existing boxes (stored in normalized 0-1 coordinates)
    boxes.forEach((box, index) => {
      const x = box.x * canvas.width
      const y = box.y * canvas.height
      const w = box.width * canvas.width
      const h = box.height * canvas.height
      
      ctx.strokeStyle = '#10b981'
      ctx.lineWidth = 3
      ctx.fillStyle = 'rgba(16, 185, 129, 0.1)'
      ctx.fillRect(x, y, w, h)
      ctx.strokeRect(x, y, w, h)
      
      // Box label (bottom-left, away from the ✕ button)
      ctx.fillStyle = '#10b981'
      ctx.font = 'bold 16px sans-serif'
      ctx.fillText(`Deer ${index + 1}`, x + 5, y + h - 6)
      
      // ✕ delete button: red square in top-right corner
      const btn = xButtonRect(box, canvas)
      ctx.fillStyle = '#ef4444'
      ctx.fillRect(btn.x, btn.y, btn.w, btn.h)
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.moveTo(btn.x + 8, btn.y + 8)
      ctx.lineTo(btn.x + btn.w - 8, btn.y + btn.h - 8)
      ctx.moveTo(btn.x + btn.w - 8, btn.y + 8)
      ctx.lineTo(btn.x + 8, btn.y + btn.h - 8)
      ctx.stroke()
    })
    
    // Draw current box being drawn
    if (currentBox) {
      ctx.strokeStyle = '#10b981'
      ctx.lineWidth = 5
      ctx.setLineDash([8, 6])
      ctx.fillStyle = 'rgba(16, 185, 129, 0.15)'
      ctx.fillRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height)
      ctx.strokeRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height)
      ctx.setLineDash([])
    }
  }

  const handlePointerDown = (e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    
    // Get pointer position relative to canvas display
    const pointerX = e.clientX - rect.left
    const pointerY = e.clientY - rect.top
    
    // Scale from display size to canvas internal size
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = pointerX * scaleX
    const y = pointerY * scaleY

    // Hit-test ✕ buttons (top-most box first)
    for (let i = boxes.length - 1; i >= 0; i--) {
      const btn = xButtonRect(boxes[i], canvas)
      if (x >= btn.x && x <= btn.x + btn.w && y >= btn.y && y <= btn.y + btn.h) {
        handleRemoveBox(i)
        return // don't start drawing
      }
    }

    canvas.setPointerCapture(e.pointerId)
    setDrawing(true)
    setCurrentBox({ x, y, width: 0, height: 0 })
  }

  const handlePointerMove = (e) => {
    if (!drawing || !currentBox) return
    
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    
    // Get pointer position relative to canvas display
    const pointerX = e.clientX - rect.left
    const pointerY = e.clientY - rect.top
    
    // Scale from display size to canvas internal size
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    
    const x = pointerX * scaleX
    const y = pointerY * scaleY
    
    const width = x - currentBox.x
    const height = y - currentBox.y
    
    setCurrentBox({ ...currentBox, width, height })
    redrawCanvas()
  }

  const handlePointerUp = (e) => {
    if (!drawing || !currentBox) return
    
    const canvas = canvasRef.current
    canvas.releasePointerCapture(e.pointerId)
    
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
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              style={{ cursor: drawing ? 'crosshair' : 'default' }}
            />
          </div>
        </div>

        <div className="annotation-tip">
          Drag to draw a box around each deer — click the red ✕ on a box to remove it. {boxes.length} box{boxes.length !== 1 ? 'es' : ''} drawn.
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


