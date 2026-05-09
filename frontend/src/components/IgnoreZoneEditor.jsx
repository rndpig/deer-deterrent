import { useState, useRef, useEffect } from 'react'
import { API_URL, apiFetch } from '../api'
import './IgnoreZoneEditor.css'

/**
 * IgnoreZoneEditor — modal for drawing rectangular ignore zones on a camera reference image.
 *
 * Props:
 *   cameraId    — ring-mqtt camera ID (e.g. "587a624d3fae")
 *   cameraName  — display name (e.g. "Driveway")
 *   zones       — current array of {x1,y1,x2,y2} rects in 640×360 px coords
 *   onChange    — called with updated zones array when user adds/removes a zone
 *   onClose     — called when user clicks Done
 *
 * Coordinate system: all zones stored as 640×360 pixel values matching the ML pipeline.
 * The canvas renders at whatever size the container allows; mouse coords are scaled back
 * to 640×360 before storing.
 */
export default function IgnoreZoneEditor({ cameraId, cameraName, zones = [], onChange, onClose }) {
  // Canvas dimensions — the image is rendered into these
  const NATIVE_W = 640
  const NATIVE_H = 360

  const [imageUrl, setImageUrl] = useState(null)
  const [imageError, setImageError] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [drawing, setDrawing] = useState(false)
  const [dragStart, setDragStart] = useState(null)
  const [dragCurrent, setDragCurrent] = useState(null)
  const imgRef = useRef(null)
  const containerRef = useRef(null)

  // Load most-recent snapshot for this camera as reference image
  useEffect(() => {
    const fetchLatest = async () => {
      try {
        const res = await apiFetch(`/api/ring-events?camera_id=${cameraId}&hours=168`)
        const data = await res.json()
        const events = data.events || []
        // Find most recent event with a snapshot
        const withSnap = events.filter(e => e.snapshot_path)
        if (withSnap.length > 0) {
          const latest = withSnap[0]
          setImageUrl(`${API_URL}/api/snapshots/${latest.id}/image`)
        } else {
          setImageError(true)
        }
      } catch {
        setImageError(true)
      }
    }
    fetchLatest()
  }, [cameraId])

  // Convert a mouse event's offsetX/Y (relative to the image element) to native 640×360 coords
  const toNativeCoords = (e) => {
    const rect = imgRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    const scaleX = NATIVE_W / rect.width
    const scaleY = NATIVE_H / rect.height
    const x = (e.clientX - rect.left) * scaleX
    const y = (e.clientY - rect.top) * scaleY
    return {
      x: Math.max(0, Math.min(NATIVE_W, x)),
      y: Math.max(0, Math.min(NATIVE_H, y)),
    }
  }

  const handleMouseDown = (e) => {
    if (e.button !== 0) return
    e.preventDefault()
    const pt = toNativeCoords(e)
    setDragStart(pt)
    setDragCurrent(pt)
    setDrawing(true)
  }

  const handleMouseMove = (e) => {
    if (!drawing) return
    e.preventDefault()
    setDragCurrent(toNativeCoords(e))
  }

  const handleMouseUp = (e) => {
    if (!drawing) return
    e.preventDefault()
    setDrawing(false)

    const end = toNativeCoords(e)
    const x1 = Math.round(Math.min(dragStart.x, end.x))
    const y1 = Math.round(Math.min(dragStart.y, end.y))
    const x2 = Math.round(Math.max(dragStart.x, end.x))
    const y2 = Math.round(Math.max(dragStart.y, end.y))

    // Ignore tiny accidental clicks
    if (x2 - x1 < 10 || y2 - y1 < 10) {
      setDragStart(null)
      setDragCurrent(null)
      return
    }

    onChange([...zones, { x1, y1, x2, y2 }])
    setDragStart(null)
    setDragCurrent(null)
  }

  const handleMouseLeave = () => {
    if (drawing) {
      setDrawing(false)
      setDragStart(null)
      setDragCurrent(null)
    }
  }

  const removeZone = (index) => {
    onChange(zones.filter((_, i) => i !== index))
  }

  // Compute display rect for an in-progress drag (in image-relative %)
  const dragRect = () => {
    if (!dragStart || !dragCurrent) return null
    const rect = imgRef.current?.getBoundingClientRect()
    if (!rect) return null
    const scaleX = rect.width / NATIVE_W
    const scaleY = rect.height / NATIVE_H
    return {
      left: Math.min(dragStart.x, dragCurrent.x) * scaleX,
      top: Math.min(dragStart.y, dragCurrent.y) * scaleY,
      width: Math.abs(dragCurrent.x - dragStart.x) * scaleX,
      height: Math.abs(dragCurrent.y - dragStart.y) * scaleY,
    }
  }

  // Compute display rect for a stored zone
  const zoneToDisplay = (zone) => {
    const rect = imgRef.current?.getBoundingClientRect()
    if (!rect) return null
    const scaleX = rect.width / NATIVE_W
    const scaleY = rect.height / NATIVE_H
    return {
      left: zone.x1 * scaleX,
      top: zone.y1 * scaleY,
      width: (zone.x2 - zone.x1) * scaleX,
      height: (zone.y2 - zone.y1) * scaleY,
    }
  }

  const inProgress = dragRect()

  return (
    <div className="ize-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(zones) }}>
      <div className="ize-modal">
        <div className="ize-header">
          <h2>Ignore Zones — {cameraName}</h2>
          <button className="ize-close" onClick={() => onClose(zones)}>✕</button>
        </div>

        <p className="ize-hint">
          Drag to draw an ignore region. Click ✕ on a zone to remove it.
          {zones.length > 0 && <strong> {zones.length} zone{zones.length !== 1 ? 's' : ''} defined.</strong>}
        </p>

        <div className="ize-canvas-wrap" ref={containerRef}>
          {imageError && (
            <div className="ize-no-image">
              No recent snapshot available for this camera.
              <br />Wait for the camera to capture a snapshot, then re-open this editor.
            </div>
          )}

          {!imageError && (
            <div
              className="ize-img-container"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseLeave}
            >
              {imageUrl ? (
                <img
                  ref={imgRef}
                  src={imageUrl}
                  alt={`${cameraName} reference`}
                  className="ize-image"
                  draggable={false}
                  onLoad={() => setImgLoaded(true)}
                />
              ) : (
                <div className="ize-loading">Loading snapshot…</div>
              )}

              {/* Existing zones — only render after image has loaded so getBoundingClientRect() is valid */}
              {imageUrl && imgLoaded && zones.map((zone, i) => {
                const d = zoneToDisplay(zone)
                if (!d) return null
                return (
                  <div
                    key={i}
                    className="ize-zone"
                    style={{ left: d.left, top: d.top, width: d.width, height: d.height }}
                  >
                    <button
                      className="ize-zone-delete"
                      onClick={(e) => { e.stopPropagation(); removeZone(i) }}
                      title="Remove zone"
                    >✕</button>
                    <span className="ize-zone-label">{i + 1}</span>
                  </div>
                )
              })}

              {/* In-progress drag */}
              {inProgress && (
                <div
                  className="ize-zone ize-zone--drawing"
                  style={{ left: inProgress.left, top: inProgress.top, width: inProgress.width, height: inProgress.height }}
                />
              )}
            </div>
          )}
        </div>

        <div className="ize-footer">
          {zones.length > 0 && (
            <button className="ize-clear" onClick={() => onChange([])}>Clear All</button>
          )}
          <button className="ize-done" onClick={() => onClose(zones)}>Done</button>
        </div>
      </div>
    </div>
  )
}
