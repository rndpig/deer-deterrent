import { useEffect, useRef, useState, useCallback } from 'react'
import './BoundingBoxImage.css'

function BoundingBoxImage({ src, alt, detections, className, onClick }) {
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const containerRef = useRef(null)
  const [imageLoaded, setImageLoaded] = useState(false)

  const drawBboxes = useCallback(() => {
    if (!detections || detections.length === 0 || !canvasRef.current || !imageRef.current || !containerRef.current) return

    const canvas = canvasRef.current
    const image = imageRef.current
    const container = containerRef.current
    const ctx = canvas.getContext('2d')

    // Safety: ensure natural dimensions are available
    if (!image.naturalWidth || !image.naturalHeight) return

    // Use the CONTAINER's rect for canvas sizing (the canvas fills the container via CSS).
    // Round to integers so that canvas.width/height (unsigned long) matches exactly.
    const containerRect = container.getBoundingClientRect()
    const canvasW = Math.round(containerRect.width)
    const canvasH = Math.round(containerRect.height)

    if (canvasW === 0 || canvasH === 0) return

    // Set canvas pixel buffer AND explicitly override CSS to match exactly.
    // This prevents any float→int mismatch between buffer and display size.
    canvas.width = canvasW
    canvas.height = canvasH
    canvas.style.width = canvasW + 'px'
    canvas.style.height = canvasH + 'px'

    // Calculate how object-fit: contain renders the image within the container.
    // The image content may be smaller than the container, centered with letterbox
    // padding. We need to know the rendered image area to map bbox pixel coords.
    const imgNatW = image.naturalWidth
    const imgNatH = image.naturalHeight
    const imgAspect = imgNatW / imgNatH
    const canvasAspect = canvasW / canvasH

    let renderedW, renderedH, offsetX, offsetY

    if (imgAspect > canvasAspect) {
      // Image is wider → constrained by width, letterboxed top/bottom
      renderedW = canvasW
      renderedH = canvasW / imgAspect
      offsetX = 0
      offsetY = (canvasH - renderedH) / 2
    } else {
      // Image is taller or equal → constrained by height, letterboxed left/right
      renderedH = canvasH
      renderedW = canvasH * imgAspect
      offsetX = (canvasW - renderedW) / 2
      offsetY = 0
    }

    // Uniform scale from image natural pixels to rendered area
    const scale = renderedW / imgNatW

    // Clear and draw
    ctx.clearRect(0, 0, canvasW, canvasH)

    detections.forEach((detection) => {
      const bbox = detection.bbox
      if (!bbox) return

      let x, y, w, h

      if (Array.isArray(bbox)) {
        // YOLO normalized format: [x_center, y_center, width, height] (0-1)
        const cx = bbox[0] * imgNatW
        const cy = bbox[1] * imgNatH
        const bw = bbox[2] * imgNatW
        const bh = bbox[3] * imgNatH
        x = offsetX + (cx - bw / 2) * scale
        y = offsetY + (cy - bh / 2) * scale
        w = bw * scale
        h = bh * scale
      } else if (bbox.x1 !== undefined) {
        // Pixel coordinate format: {x1, y1, x2, y2}
        x = offsetX + bbox.x1 * scale
        y = offsetY + bbox.y1 * scale
        w = (bbox.x2 - bbox.x1) * scale
        h = (bbox.y2 - bbox.y1) * scale
      } else {
        return
      }

      // Draw green bounding box
      ctx.strokeStyle = '#00ff00'
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, w, h)

      // Draw confidence label if available
      if (detection.confidence) {
        const label = `${Math.round(detection.confidence * 100)}%`
        ctx.font = '12px sans-serif'
        ctx.fillStyle = '#00ff00'
        const textW = ctx.measureText(label).width
        ctx.fillRect(x, y - 16, textW + 6, 16)
        ctx.fillStyle = '#000'
        ctx.fillText(label, x + 3, y - 4)
      }
    })
  }, [detections])

  // Draw bounding boxes when image loads or detections change
  useEffect(() => {
    if (!imageLoaded) return
    drawBboxes()
  }, [imageLoaded, detections, drawBboxes])

  const handleImageLoad = () => {
    setImageLoaded(true)
  }

  // Handle window resize to redraw boxes
  useEffect(() => {
    if (!imageLoaded || !detections || detections.length === 0) return

    const handleResize = () => {
      // Use requestAnimationFrame to ensure layout is settled before redrawing
      requestAnimationFrame(() => drawBboxes())
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [imageLoaded, detections, drawBboxes])

  return (
    <div className="bounding-box-container" ref={containerRef} onClick={onClick}>
      <img
        ref={imageRef}
        src={src}
        alt={alt}
        className={className}
        style={{ objectFit: 'contain' }}
        onLoad={handleImageLoad}
      />
      {detections && detections.length > 0 && (
        <canvas
          ref={canvasRef}
          className="bounding-box-canvas"
        />
      )}
    </div>
  )
}

export default BoundingBoxImage
