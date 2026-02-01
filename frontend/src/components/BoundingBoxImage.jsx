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

    // Set canvas size to match image display size
    const rect = image.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height

    // Get image natural dimensions for scaling
    const scaleX = canvas.width / image.naturalWidth
    const scaleY = canvas.height / image.naturalHeight

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw bounding boxes
    detections.forEach((detection) => {
      const bbox = detection.bbox
      const confidence = detection.confidence

      let x, y, width, height

      // Check if bbox is in YOLO normalized format [x_center, y_center, width, height]
      // or in pixel format {x1, y1, x2, y2}
      if (Array.isArray(bbox)) {
        // YOLO normalized format: [x_center, y_center, width, height] (all normalized 0-1)
        const x_center = bbox[0] * canvas.width
        const y_center = bbox[1] * canvas.height
        width = bbox[2] * canvas.width
        height = bbox[3] * canvas.height
        x = x_center - width / 2
        y = y_center - height / 2
      } else if (bbox.x1 !== undefined) {
        // Pixel coordinate format: {x1, y1, x2, y2} - scale to display size
        x = bbox.x1 * scaleX
        y = bbox.y1 * scaleY
        width = (bbox.x2 - bbox.x1) * scaleX
        height = (bbox.y2 - bbox.y1) * scaleY
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
