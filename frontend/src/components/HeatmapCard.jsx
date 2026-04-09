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
 * Uses intensity accumulation with proper color gradient from cold (blue) to hot (red).
 */
function drawHeatmap(canvas, points, options = {}) {
  const ctx = canvas.getContext('2d')
  const width = canvas.width
  const height = canvas.height
  const { radius = 30, maxOpacity = 0.75, blur = 15 } = options

  // Clear canvas
  ctx.clearRect(0, 0, width, height)
  
  if (!points || points.length === 0) return

  // Calculate intensity contribution per point based on total points
  // Fewer points = higher contribution, more points = lower to prevent saturation
  const pointCount = points.length
  const alphaPerPoint = Math.min(0.15, Math.max(0.02, 3 / pointCount))

  // Create offscreen canvas for intensity accumulation
  // Use a Float32 array for better precision
  const intensityMap = new Float32Array(width * height)

  // Accumulate intensity for each point with gaussian falloff
  for (const point of points) {
    const cx = point.x * width
    const cy = point.y * height

    // Only process pixels within radius
    const minX = Math.max(0, Math.floor(cx - radius))
    const maxX = Math.min(width - 1, Math.ceil(cx + radius))
    const minY = Math.max(0, Math.floor(cy - radius))
    const maxY = Math.min(height - 1, Math.ceil(cy + radius))

    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        const dx = x - cx
        const dy = y - cy
        const dist = Math.sqrt(dx * dx + dy * dy)
        
        if (dist <= radius) {
          // Gaussian falloff
          const falloff = Math.exp(-dist * dist / (radius * radius * 0.5))
          intensityMap[y * width + x] += alphaPerPoint * falloff
        }
      }
    }
  }

  // Find max intensity for normalization
  let maxIntensity = 0
  for (let i = 0; i < intensityMap.length; i++) {
    if (intensityMap[i] > maxIntensity) maxIntensity = intensityMap[i]
  }

  // Ensure we have a reasonable range
  maxIntensity = Math.max(maxIntensity, 0.1)

  // Create output canvas with color mapping
  const colorCanvas = document.createElement('canvas')
  colorCanvas.width = width
  colorCanvas.height = height
  const colorCtx = colorCanvas.getContext('2d')
  const colorData = colorCtx.createImageData(width, height)

  // Apply color gradient based on intensity
  // Use square root scaling to spread out the values better
  for (let i = 0; i < intensityMap.length; i++) {
    const rawIntensity = intensityMap[i]
    // Apply square root for better distribution of mid-range values
    const intensity = Math.sqrt(rawIntensity / maxIntensity)
    
    const pixelIdx = i * 4
    
    if (intensity > 0.05) {
      let r, g, b, a
      
      if (intensity < 0.2) {
        // Light blue (low activity)
        const t = intensity / 0.2
        r = Math.round(50 + 50 * (1 - t))
        g = Math.round(100 + 80 * t)
        b = 255
        a = 0.3 + t * 0.15
      } else if (intensity < 0.35) {
        // Blue to cyan
        const t = (intensity - 0.2) / 0.15
        r = Math.round(50 * (1 - t))
        g = Math.round(180 + 75 * t)
        b = 255
        a = 0.45 + t * 0.1
      } else if (intensity < 0.5) {
        // Cyan to green
        const t = (intensity - 0.35) / 0.15
        r = 0
        g = 255
        b = Math.round(255 * (1 - t))
        a = 0.55 + t * 0.1
      } else if (intensity < 0.65) {
        // Green to yellow
        const t = (intensity - 0.5) / 0.15
        r = Math.round(255 * t)
        g = 255
        b = 0
        a = 0.65 + t * 0.1
      } else if (intensity < 0.8) {
        // Yellow to orange
        const t = (intensity - 0.65) / 0.15
        r = 255
        g = Math.round(255 - 80 * t)
        b = 0
        a = 0.75 + t * 0.1
      } else {
        // Orange to red (hottest)
        const t = Math.min((intensity - 0.8) / 0.2, 1)
        r = 255
        g = Math.round(175 - 175 * t)
        b = 0
        a = 0.85 + t * 0.1
      }

      colorData.data[pixelIdx] = r
      colorData.data[pixelIdx + 1] = g
      colorData.data[pixelIdx + 2] = b
      colorData.data[pixelIdx + 3] = Math.round(a * maxOpacity * 255)
    } else {
      colorData.data[pixelIdx + 3] = 0
    }
  }

  colorCtx.putImageData(colorData, 0, 0)

  // Apply blur for smoother appearance
  ctx.filter = `blur(${blur}px)`
  ctx.drawImage(colorCanvas, 0, 0)
  ctx.filter = 'none'
  
  // Draw again without blur for sharper hotspots  
  ctx.globalAlpha = 0.4
  ctx.drawImage(colorCanvas, 0, 0)
  ctx.globalAlpha = 1.0
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
      radius: Math.max(25, rect.width / 20),
      maxOpacity: 0.8,
      blur: Math.max(8, rect.width / 80)
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

  // Prefer reference_image_url (from captured daytime images) over snapshot
  const imageUrl = cameraData
    ? (cameraData.reference_image_url 
        ? `${API_URL}${cameraData.reference_image_url}`
        : (cameraData.reference_snapshot_id 
            ? `${API_URL}/api/snapshots/${cameraData.reference_snapshot_id}/image`
            : null))
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
          <span className="ml-auto flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: 'linear-gradient(90deg, #6482e6, #00ffff, #00ff00, #ffff00, #ff9900, #ff0000)' }}></span>
            <span className="text-white/30">Low → High activity</span>
          </span>
        </div>
      )}
    </div>
  )
}

export default HeatmapCard
