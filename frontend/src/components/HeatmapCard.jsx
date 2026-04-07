import { useState, useEffect, useRef } from 'react'
import { apiFetch, API_URL } from '../api'

const CAMERA_NAMES = {
  '587a624d3fae': 'Driveway',
  '4439c4de7a79': 'Front Door',
  'f045dae9383a': 'Back',
  '10cea9e4511f': 'Woods',
  'c4dbad08f862': 'Side',
}

/**
 * Draw a heatmap on a canvas from an array of {x, y} points (normalized 0-1).
 * Uses a simple gaussian blur approach for the heat effect.
 */
function drawHeatmap(canvas, points, options = {}) {
  const ctx = canvas.getContext('2d')
  const width = canvas.width
  const height = canvas.height
  const { radius = 25, maxOpacity = 0.7 } = options

  // Create offscreen canvas for accumulation
  const offscreen = document.createElement('canvas')
  offscreen.width = width
  offscreen.height = height
  const offCtx = offscreen.getContext('2d')

  // Draw each point as a radial gradient
  for (const point of points) {
    const x = point.x * width
    const y = point.y * height

    const gradient = offCtx.createRadialGradient(x, y, 0, x, y, radius)
    gradient.addColorStop(0, 'rgba(255, 0, 0, 0.3)')
    gradient.addColorStop(1, 'rgba(255, 0, 0, 0)')

    offCtx.fillStyle = gradient
    offCtx.fillRect(x - radius, y - radius, radius * 2, radius * 2)
  }

  // Get image data and apply color mapping
  const imageData = offCtx.getImageData(0, 0, width, height)
  const data = imageData.data

  // Find max intensity for normalization
  let maxIntensity = 0
  for (let i = 0; i < data.length; i += 4) {
    if (data[i] > maxIntensity) maxIntensity = data[i]
  }

  // Apply color gradient based on intensity
  for (let i = 0; i < data.length; i += 4) {
    const intensity = data[i] / (maxIntensity || 1)
    
    if (intensity > 0.01) {
      // Color gradient: blue -> cyan -> green -> yellow -> red
      let r, g, b
      if (intensity < 0.25) {
        // Blue to cyan
        const t = intensity / 0.25
        r = 0
        g = Math.round(255 * t)
        b = 255
      } else if (intensity < 0.5) {
        // Cyan to green
        const t = (intensity - 0.25) / 0.25
        r = 0
        g = 255
        b = Math.round(255 * (1 - t))
      } else if (intensity < 0.75) {
        // Green to yellow
        const t = (intensity - 0.5) / 0.25
        r = Math.round(255 * t)
        g = 255
        b = 0
      } else {
        // Yellow to red
        const t = (intensity - 0.75) / 0.25
        r = 255
        g = Math.round(255 * (1 - t))
        b = 0
      }

      data[i] = r
      data[i + 1] = g
      data[i + 2] = b
      data[i + 3] = Math.round(intensity * maxOpacity * 255)
    } else {
      data[i + 3] = 0
    }
  }

  offCtx.putImageData(imageData, 0, 0)

  // Draw to main canvas
  ctx.clearRect(0, 0, width, height)
  ctx.drawImage(offscreen, 0, 0)
}

function HeatmapCard() {
  const [heatmapData, setHeatmapData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedCamera, setSelectedCamera] = useState(null)
  const [imageLoaded, setImageLoaded] = useState(false)
  const canvasRef = useRef(null)
  const containerRef = useRef(null)

  // Fetch heatmap data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiFetch('/api/stats/heatmap')
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setHeatmapData(data)
        // Auto-select first camera with data
        if (data.cameras && data.cameras.length > 0) {
          setSelectedCamera(data.cameras[0].camera_id)
        }
      } catch (e) {
        console.error('Failed to load heatmap data:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // Get selected camera data
  const cameraData = heatmapData?.cameras?.find(c => c.camera_id === selectedCamera)

  // Draw heatmap when canvas and data are ready
  useEffect(() => {
    if (!canvasRef.current || !cameraData || !imageLoaded) return

    const canvas = canvasRef.current
    const container = containerRef.current
    if (!container) return

    // Set canvas size to match container
    const rect = container.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = rect.height

    drawHeatmap(canvas, cameraData.points, {
      radius: Math.max(20, rect.width / 25),
      maxOpacity: 0.65
    })
  }, [cameraData, imageLoaded, selectedCamera])

  // Handle image load
  const handleImageLoad = () => {
    setImageLoaded(true)
  }

  // Reset image loaded state when camera changes
  useEffect(() => {
    setImageLoaded(false)
  }, [selectedCamera])

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide mb-3">
          Detection Heatmap
        </h3>
        <div className="flex items-center justify-center h-48 text-white/30">
          Loading heatmap data...
        </div>
      </div>
    )
  }

  if (!heatmapData?.cameras?.length) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide mb-3">
          Detection Heatmap
        </h3>
        <div className="flex items-center justify-center h-48 text-white/30">
          No detection data available for heatmap
        </div>
      </div>
    )
  }

  const imageUrl = cameraData
    ? `${API_URL}/api/snapshots/${cameraData.reference_snapshot_id}/image`
    : null

  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide">
          Detection Heatmap
        </h3>
        <div className="flex items-center gap-3">
          <select
            value={selectedCamera || ''}
            onChange={(e) => setSelectedCamera(e.target.value)}
            className="bg-[#1e1e1e] border border-white/20 rounded px-2 py-1 text-sm text-white/90 focus:outline-none focus:border-blue-500"
            style={{ colorScheme: 'dark' }}
          >
            {heatmapData.cameras.map(cam => (
              <option key={cam.camera_id} value={cam.camera_id} className="bg-[#1e1e1e] text-white">
                {cam.camera_name} ({cam.deer_count} detections)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Heatmap visualization */}
      <div
        ref={containerRef}
        className="relative w-full aspect-video rounded overflow-hidden bg-black/50"
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={`${cameraData?.camera_name} camera view`}
            className="absolute inset-0 w-full h-full object-cover"
            onLoad={handleImageLoad}
            onError={() => setImageLoaded(true)} // Still show heatmap even if image fails
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-white/30">
            No reference image available
          </div>
        )}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />
        {!imageLoaded && imageUrl && (
          <div className="absolute inset-0 flex items-center justify-center text-white/30">
            Loading image...
          </div>
        )}
      </div>

      {/* Stats below heatmap */}
      {cameraData && (
        <div className="mt-3 flex items-center gap-4 text-xs text-white/50">
          <span>
            <span className="text-white/70 font-semibold">{cameraData.snapshot_count}</span> snapshots
          </span>
          <span>
            <span className="text-white/70 font-semibold">{cameraData.deer_count}</span> deer detected
          </span>
          <span className="ml-auto text-white/30">
            Red = high activity
          </span>
        </div>
      )}
    </div>
  )
}

export default HeatmapCard
