import { useEffect, useRef, useState } from 'react'
import './BoundingBoxImage.css'

function BoundingBoxImage({ src, alt, detections, className, onClick }) {
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const [imageLoaded, setImageLoaded] = useState(false)

  // Draw bounding boxes when image loads or detections change
  useEffect(() => {
    if (!imageLoaded || !detections || detections.length === 0 || !canvasRef.current || !imageRef.current) return

    const canvas = canvasRef.current
    const image = imageRef.current
    const ctx = canvas.getContext('2d')

    // Get the img element's layout dimensions (includes letterbox padding area)
    const rect = image.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height

    // Calculate how object-fit: contain renders the image within the element.
    // The actual rendered image may be smaller than the element, centered with
    // letterbox padding on sides or top/bottom.
    const naturalAspect = image.naturalWidth / image.naturalHeight
    const containerAspect = rect.width / rect.height

    let renderedWidth, renderedHeight, offsetX, offsetY

    if (naturalAspect > containerAspect) {
      // Image is wider than container — fits width, letterboxed top/bottom
      renderedWidth = rect.width
      renderedHeight = rect.width / naturalAspect
      offsetX = 0
      offsetY = (rect.height - renderedHeight) / 2
    } else {
      // Image is taller (or same) — fits height, letterboxed left/right
      renderedHeight = rect.height
      renderedWidth = rect.height * naturalAspect
      offsetX = (rect.width - renderedWidth) / 2
      offsetY = 0
    }

    // Uniform scale from natural image pixels to rendered area
    const scale = renderedWidth / image.naturalWidth

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw bounding boxes
    detections.forEach((detection) => {
      const bbox = detection.bbox

      let x, y, width, height

      // Check if bbox is in YOLO normalized format [x_center, y_center, width, height]
      // or in pixel format {x1, y1, x2, y2}
      if (Array.isArray(bbox)) {
        // YOLO normalized format: [x_center, y_center, width, height] (all normalized 0-1)
        const x_center = bbox[0] * image.naturalWidth
        const y_center = bbox[1] * image.naturalHeight
        const w = bbox[2] * image.naturalWidth
        const h = bbox[3] * image.naturalHeight
        x = offsetX + (x_center - w / 2) * scale
        y = offsetY + (y_center - h / 2) * scale
        width = w * scale
        height = h * scale
      } else if (bbox.x1 !== undefined) {
        // Pixel coordinate format: {x1, y1, x2, y2} - already in natural dimensions
        x = offsetX + bbox.x1 * scale
        y = offsetY + bbox.y1 * scale
        width = (bbox.x2 - bbox.x1) * scale
        height = (bbox.y2 - bbox.y1) * scale
      } else {
        return // Skip invalid bbox
      }

      // Draw green bounding box
      ctx.strokeStyle = '#00ff00'
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, width, height)
    })
  }, [imageLoaded, detections])

  const handleImageLoad = () => {
    setImageLoaded(true)
  }

  // Handle window resize to redraw boxes
  useEffect(() => {
    const handleResize = () => {
      if (imageLoaded && detections && detections.length > 0) {
        // Trigger redraw
        setImageLoaded(false)
        setTimeout(() => setImageLoaded(true), 0)
      }
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [imageLoaded, detections])

  return (
    <div className="bounding-box-container" onClick={onClick}>
      <img
        ref={imageRef}
        src={src}
        alt={alt}
        className={className}
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
