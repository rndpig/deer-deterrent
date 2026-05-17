import { useRef, useState, useCallback, useEffect } from 'react'
import { API_URL, apiFetch } from '../../api'
import { pixelToNormalized, normalizedToPercent, clamp01 } from './coords'
import { useMapDrag } from './useMapDrag'
import { getRings, ringsPatch, replaceRing, pointsAttr } from './polygonUtils'
import CameraLiveView from './CameraLiveView'
import { RING_ID_TO_STREAM_NAME } from './cameraDefaults'

const DEG2RAD = Math.PI / 180
const WEATHER_API_URL = import.meta.env.VITE_WEATHER_API_URL || 'https://weather-api.rndpig.com'

function fovPath(cx, cy, rotation, fovDeg, range) {
  const halfFov = fovDeg / 2
  const startAngle = (rotation - halfFov) * DEG2RAD
  const endAngle   = (rotation + halfFov) * DEG2RAD
  const r = range * 100
  const sx = cx + r * Math.sin(startAngle)
  const sy = cy - r * Math.cos(startAngle)
  const ex = cx + r * Math.sin(endAngle)
  const ey = cy - r * Math.cos(endAngle)
  const large = fovDeg > 180 ? 1 : 0
  return `M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey} Z`
}



/* -------------------------------------------------------------------------
 * Cameras are split between SVG (FOV cone) and HTML (the circular dot +
 * rotation handle). The SVG uses preserveAspectRatio="none" so it can
 * stretch to non-square aspect ratios — that's what was squashing the
 * camera circle into an oval. HTML overlay elements aren't affected.
 * ------------------------------------------------------------------------- */
function CameraCone({ item }) {
  const cx = item.x * 100
  const cy = item.y * 100
  const rotation = item.rotation_deg ?? 0
  const fovDeg = item.fov_deg ?? 90
  const range = item.range ?? 0.15
  const color = item.color ?? '#3b82f6'
  return (
    <path
      d={fovPath(cx, cy, rotation, fovDeg, range)}
      fill={color}
      fillOpacity={0.25}
      stroke={color}
      strokeWidth={0.3}
      className="pm-fov-cone"
      pointerEvents="none"
    />
  )
}

function CameraMarker({ item, selected, editMode, containerRef, onSelect, onUpdate, onViewClick }) {
  const color = item.color ?? '#3b82f6'
  const rotation = item.rotation_deg ?? 0
  const pctX = normalizedToPercent(item.x)
  const pctY = normalizedToPercent(item.y)

  const startDrag = useMapDrag({
    containerRef,
    onStart: () => onSelect(item.id),
    onMove: (me, rect) => {
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      onUpdate({ x: n.x, y: n.y })
    },
  })

  const startRotate = useMapDrag({
    containerRef,
    onMove: (me, rect) => {
      const cxPx = rect.left + item.x * rect.width
      const cyPx = rect.top  + item.y * rect.height
      const dx = me.clientX - cxPx
      const dy = me.clientY - cyPx
      const angle = Math.atan2(dx, -dy) / DEG2RAD
      onUpdate({ rotation_deg: Math.round(angle) })
    },
  })

  const onDotPointerDown = (e) => {
    if (!editMode) {
      onSelect(item.id)
      onViewClick?.(e)
      return
    }
    startDrag(e)
  }

  // Rotation handle position (~6% of container width along rotation vector)
  const handleOffsetPct = 6
  const rad = rotation * DEG2RAD
  const handleLeft = clamp01(item.x + (handleOffsetPct / 100) * Math.sin(rad))
  const handleTop  = clamp01(item.y - (handleOffsetPct / 100) * Math.cos(rad))

  return (
    <>
      <div
        className={`pm-cam-dot${editMode ? ' edit-mode' : ''}${selected ? ' selected' : ''}`}
        style={{ left: pctX, top: pctY, background: color }}
        onPointerDown={onDotPointerDown}
        title={item.label}
      >
        <span className="pm-cam-dot-label">{item.label}</span>
      </div>
      {selected && editMode && (
        <div
          className="pm-cam-rotate-handle"
          style={{
            left: normalizedToPercent(handleLeft),
            top:  normalizedToPercent(handleTop),
            borderColor: color,
          }}
          onPointerDown={startRotate}
          title="Drag to rotate"
        />
      )}
    </>
  )
}

// Vertex handle — rendered as an HTML overlay div so it stays circular
// regardless of the map image's aspect ratio. The SVG layer uses
// preserveAspectRatio="none", which would squash an SVG <circle> into an oval.
function PolyVertex({
  ringIdx, idx, x, y, color, ring, rings, containerRef,
  isActive, onSelect, onUpdate, onContextMenu, onSetActive,
}) {
  const start = useMapDrag({
    containerRef,
    onStart: () => { onSelect(); onSetActive() },
    onMove: (me, rect) => {
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      const newRing = ring.map((pt, i) => (i === idx ? [n.x, n.y] : pt))
      onUpdate(ringsPatch(replaceRing(rings, ringIdx, newRing)))
    },
  })
  const canDelete = ring.length > 3
  return (
    <div
      className={`pm-vertex-handle${isActive ? ' active' : ''}`}
      style={{
        left: `${x * 100}%`,
        top: `${y * 100}%`,
        borderColor: color,
        background: isActive ? color : '#fff',
      }}
      onPointerDown={start}
      onContextMenu={onContextMenu}
      title={canDelete ? 'Drag to move · right-click or click ✕ to remove' : 'Drag to move'}
    >
      {canDelete && (
        <button
          type="button"
          className="pm-vertex-delete"
          onPointerDown={(e) => {
            e.preventDefault(); e.stopPropagation()
            onContextMenu(e)
          }}
          title="Remove vertex"
        >×</button>
      )}
    </div>
  )
}

// Midpoint handle (HTML overlay) — press and drag inserts a new vertex at
// the midpoint and immediately starts dragging it. Standard pattern from
// Leaflet.Draw, Mapbox GL Draw, Google My Maps.
function MidpointHandle({
  ringIdx, idx, ring, rings, color, containerRef, onSelect, onUpdate, onSetActive,
}) {
  const a = ring[idx]
  const b = ring[(idx + 1) % ring.length]
  const mx = (a[0] + b[0]) / 2
  const my = (a[1] + b[1]) / 2

  const insertedRingRef = useRef(null)
  const newVertexIdxRef = useRef(idx + 1)

  const drag = useMapDrag({
    containerRef,
    onMove: (me, rect) => {
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      const baseRing = insertedRingRef.current
      if (!baseRing) return
      const newRing = baseRing.map((pt, i) =>
        (i === newVertexIdxRef.current ? [n.x, n.y] : pt)
      )
      onUpdate(ringsPatch(replaceRing(rings, ringIdx, newRing)))
    },
  })

  const handleDown = (e) => {
    onSelect()
    const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
    const newRing = [...ring.slice(0, idx + 1), mid, ...ring.slice(idx + 1)]
    insertedRingRef.current = newRing
    newVertexIdxRef.current = idx + 1
    onUpdate(ringsPatch(replaceRing(rings, ringIdx, newRing)))
    onSetActive(idx + 1)
    drag(e)
  }

  return (
    <div
      className="pm-midpoint-handle"
      style={{
        left: `${mx * 100}%`,
        top: `${my * 100}%`,
        borderColor: color,
      }}
      onPointerDown={handleDown}
      title="Drag to insert a vertex"
    />
  )
}

function PolygonItem({
  item, selected, editMode, containerRef, onSelect, onUpdate, onViewClick,
}) {
  const color = item.color ?? '#4ade80'
  const fillOpacity = item.fill_opacity ?? 0.35
  const strokeWidth = item.stroke_width ?? 2
  const rings = getRings(item)

  const handlePolyDown = useCallback((e) => {
    if (!editMode) {
      onSelect(item.id)
      onViewClick?.(e)
      return
    }
    e.preventDefault(); e.stopPropagation()
    onSelect(item.id)
  }, [editMode, item.id, onSelect, onViewClick])

  const sw = strokeWidth * 0.05

  return (
    <g>
      {rings.map((ring, ringIdx) => (
        <polygon
          key={`ring-${ringIdx}`}
          points={pointsAttr(ring)}
          fill={color}
          fillOpacity={selected ? fillOpacity * 1.3 : fillOpacity}
          stroke={color}
          strokeWidth={sw}
          style={{ cursor: editMode ? 'default' : 'pointer' }}
          onPointerDown={handlePolyDown}
        />
      ))}
    </g>
  )
}

// HTML-overlay handles for the selected polygon. Rendered outside the
// stretched SVG so circles stay circular and have a fixed pixel size.
function PolygonHandles({
  item, containerRef, onSelect, onUpdate, activeVertex, onSetActiveVertex,
}) {
  const color = item.color ?? '#4ade80'
  const rings = getRings(item)

  const handleVertexRemove = (e, ringIdx, idx) => {
    e.preventDefault()
    const ring = rings[ringIdx]
    if (!ring || ring.length <= 3) return
    const newRing = ring.filter((_, i) => i !== idx)
    onUpdate(ringsPatch(replaceRing(rings, ringIdx, newRing)))
    onSetActiveVertex?.(null)
  }

  return (
    <>
      {rings.map((ring, ringIdx) => (
        <div key={`pm-h-${ringIdx}`}>
          {ring.map(([x, y], idx) => (
            <PolyVertex
              key={`v-${ringIdx}-${idx}`}
              ringIdx={ringIdx}
              idx={idx}
              x={x} y={y}
              color={color}
              ring={ring}
              rings={rings}
              containerRef={containerRef}
              isActive={activeVertex?.ringIdx === ringIdx && activeVertex?.idx === idx}
              onSelect={() => onSelect(item.id)}
              onUpdate={onUpdate}
              onContextMenu={(e) => handleVertexRemove(e, ringIdx, idx)}
              onSetActive={() => onSetActiveVertex?.({ ringIdx, idx })}
            />
          ))}
          {ring.map((_, idx) => (
            <MidpointHandle
              key={`m-${ringIdx}-${idx}`}
              ringIdx={ringIdx}
              idx={idx}
              ring={ring}
              rings={rings}
              color={color}
              containerRef={containerRef}
              onSelect={() => onSelect(item.id)}
              onUpdate={onUpdate}
              onSetActive={(newIdx) => onSetActiveVertex?.({ ringIdx, idx: newIdx })}
            />
          ))}
        </div>
      ))}
    </>
  )
}

function MarkerItem({ item, selected, editMode, containerRef, onSelect, onUpdate, onViewClick }) {
  const color = item.color ?? '#06b6d4'
  const pctX = normalizedToPercent(item.x)
  const pctY = normalizedToPercent(item.y)

  const startDrag = useMapDrag({
    containerRef,
    onStart: () => onSelect(item.id),
    onMove: (me, rect) => {
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      onUpdate({ x: n.x, y: n.y })
    },
  })

  const handleDown = (e) => {
    if (!editMode) {
      onSelect(item.id)
      onViewClick?.(e)
      return
    }
    startDrag(e)
  }

  return (
    <div
      className={`pm-marker${editMode ? ' edit-mode' : ''}${selected ? ' selected' : ''}`}
      style={{ left: pctX, top: pctY, cursor: editMode ? 'grab' : 'pointer' }}
      onPointerDown={handleDown}
    >
      <div className="pm-marker-dot" style={{ background: color }} />
      <div className="pm-marker-label">{item.label}</div>
    </div>
  )
}

function LabelItem({ item, selected, editMode, containerRef, onSelect, onUpdate }) {
  const pctX = normalizedToPercent(item.x)
  const pctY = normalizedToPercent(item.y)

  const startDrag = useMapDrag({
    containerRef,
    onStart: () => onSelect(item.id),
    onMove: (me, rect) => {
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      onUpdate({ x: n.x, y: n.y })
    },
  })

  const handleDown = (e) => {
    if (!editMode) { onSelect(item.id); return }
    startDrag(e)
  }

  return (
    <div
      className={`pm-marker${editMode ? ' edit-mode' : ''}`}
      style={{ left: pctX, top: pctY, cursor: editMode ? 'grab' : 'default' }}
      onPointerDown={handleDown}
    >
      <div style={{
        background: 'rgba(0,0,0,0.55)',
        padding: '2px 6px',
        borderRadius: 4,
        fontSize: '0.7rem',
        whiteSpace: 'nowrap',
        border: selected ? '1px solid #3b82f6' : '1px solid transparent',
      }}>
        {item.label}
      </div>
    </div>
  )
}

function CameraPopover({ item, pos, onClose }) {
  const cameraId = item.meta?.ring_camera_id
  const streamName = cameraId ? RING_ID_TO_STREAM_NAME[cameraId] : null
  const isStreaming = !!streamName

  // When we have a live stream, render as a centered modal (large video).
  // Otherwise keep the small anchored popover.
  if (isStreaming) {
    return (
      <>
        <div className="pm-modal-backdrop" onClick={onClose} />
        <div className="pm-popover pm-popover--modal">
          <button className="pm-popover__close" onClick={onClose}>✕</button>
          <div className="pm-popover__title">{item.label}</div>
          <CameraLiveView streamName={streamName} label={item.label} />
        </div>
      </>
    )
  }

  return (
    <div className="pm-popover" style={{ left: pos.x, top: pos.y }}>
      <button className="pm-popover__close" onClick={onClose}>✕</button>
      <div className="pm-popover__title">{item.label}</div>
      {cameraId
        ? <div style={{ color: '#64748b', fontSize: '0.75rem' }}>Stream not configured</div>
        : <div style={{ color: '#64748b', fontSize: '0.75rem' }}>No Ring ID configured</div>
      }
    </div>
  )
}

function ZonePopover({ item, pos, onClose }) {
  const zone = item.meta?.rainbird_zone
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState(null)

  const runZone = async () => {
    if (!zone) return
    if (!window.confirm(`Run zone ${zone} for 30 seconds?`)) return
    setRunning(true)
    try {
      await apiFetch('/api/test-irrigation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zones: [zone], duration: 30 }),
      })
      setDone(true)
    } catch (e) {
      setErr(e.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="pm-popover" style={{ left: pos.x, top: pos.y }}>
      <button className="pm-popover__close" onClick={onClose}>✕</button>
      <div className="pm-popover__title">{item.label}</div>
      {zone ? (
        done
          ? <div style={{ color: '#4ade80', fontSize: '0.8rem' }}>Zone {zone} running!</div>
          : err
            ? <div style={{ color: '#f87171', fontSize: '0.75rem' }}>{err}</div>
            : (
              <div className="pm-popover__actions">
                <button className="pm-btn primary" onClick={runZone} disabled={running}>
                  {running ? 'Starting…' : `Run zone ${zone} (30s)`}
                </button>
              </div>
            )
      ) : (
        <div style={{ color: '#64748b', fontSize: '0.75rem' }}>No Rainbird zone configured</div>
      )}
    </div>
  )
}

function formatRelative(iso) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const secs = Math.max(0, Math.round((Date.now() - t) / 1000))
  if (secs < 60) return `${secs}s ago`
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

function SensorPopover({ item, pos, onClose }) {
  const meta = item.meta ?? {}
  const kind = meta.kind
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [data, setData] = useState(null) // { value, unit, timestamp }

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true); setErr(null); setData(null)
      try {
        if (kind === 'soil_moisture') {
          const ch = Number(meta.channel)
          if (!ch || ch < 1 || ch > 8) throw new Error('No channel configured (1-8)')
          const res = await fetch(`${WEATHER_API_URL}/api/current`)
          if (!res.ok) throw new Error(`Weather API: ${res.status}`)
          const json = await res.json()
          const value = json[`soil_moisture_${ch}`]
          if (value == null) throw new Error(`No reading for channel ${ch}`)
          if (!cancelled) setData({ value, unit: '%', timestamp: json.timestamp, sub: `Channel ${ch}` })
        } else if (kind === 'light') {
          const res = await fetch(`${WEATHER_API_URL}/api/light/current`)
          if (!res.ok) throw new Error(`Weather API: ${res.status}`)
          const json = await res.json()
          const sensors = json.sensors ?? []
          const name = meta.name || meta.channel
          const found = name
            ? sensors.find(s => s.name === String(name))
            : sensors[0]
          if (!found) throw new Error(name ? `Sensor '${name}' not found` : 'No light sensors')
          if (!cancelled) setData({ value: found.lux, unit: 'lux', timestamp: found.timestamp, sub: found.name })
        } else {
          throw new Error('Sensor kind not configured')
        }
      } catch (e) {
        if (!cancelled) setErr(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [kind, meta.channel, meta.name])

  const renderValue = () => {
    if (loading) return <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Loading…</div>
    if (err) return <div style={{ color: '#f87171', fontSize: '0.75rem' }}>{err}</div>
    if (!data) return null
    const v = typeof data.value === 'number' ? data.value.toFixed(data.unit === 'lux' ? 0 : 1) : data.value
    return (
      <div>
        <div style={{ fontSize: '1.4rem', fontWeight: 600, color: '#f1f5f9' }}>
          {v}<span style={{ fontSize: '0.85rem', color: '#94a3b8', marginLeft: 4 }}>{data.unit}</span>
        </div>
        {data.sub && <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 2 }}>{data.sub}</div>}
        <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: 4 }}>
          {formatRelative(data.timestamp)}
        </div>
      </div>
    )
  }

  return (
    <div className="pm-popover" style={{ left: pos.x, top: pos.y }}>
      <button className="pm-popover__close" onClick={onClose}>✕</button>
      <div className="pm-popover__title">{item.label}</div>
      {renderValue()}
    </div>
  )
}

export default function MapCanvas({
  overlay, layerVisibility, selectedItemId, editMode,
  onSelect, onDeselect, onUpdateItem,
  drawingItemId, drawingRing, onDrawingAddVertex, onDrawingFinish, onDrawingCancel,
}) {
  const containerRef = useRef(null)
  const [popover, setPopover] = useState(null)
  const [activeVertex, setActiveVertex] = useState(null) // { ringIdx, idx } for selected polygon

  const ratio = overlay?.image
    ? overlay.image.intrinsic_width / overlay.image.intrinsic_height
    : 1782 / 768
  const imgSrc = `${API_URL}/api/property-map/image`

  const isDrawing = !!drawingItemId

  // Keyboard: Delete/Backspace removes active vertex; Enter finishes drawing; Esc cancels.
  useEffect(() => {
    const handler = (e) => {
      if (isDrawing) {
        if (e.key === 'Enter') {
          e.preventDefault()
          onDrawingFinish?.()
        } else if (e.key === 'Escape') {
          e.preventDefault()
          onDrawingCancel?.()
        }
        return
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && activeVertex && selectedItemId && editMode) {
        // Find the polygon item being edited
        for (const layer of overlay?.layers ?? []) {
          const item = layer.items.find(i => i.id === selectedItemId)
          if (!item || item.type !== 'polygon') continue
          const rings = getRings(item)
          const ring = rings[activeVertex.ringIdx]
          if (!ring || ring.length <= 3) return
          e.preventDefault()
          const newRing = ring.filter((_, i) => i !== activeVertex.idx)
          onUpdateItem(layer.id, item.id, ringsPatch(replaceRing(rings, activeVertex.ringIdx, newRing)))
          setActiveVertex(null)
          return
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isDrawing, activeVertex, selectedItemId, editMode, overlay, onDrawingFinish, onDrawingCancel, onUpdateItem])

  // Clear active vertex when selection changes
  useEffect(() => { setActiveVertex(null) }, [selectedItemId])

  const handleCanvasClick = (e) => {
    if (isDrawing) return // drawing handles its own clicks below
    if (e.target === e.currentTarget || e.target.tagName === 'IMG') {
      onDeselect()
      setPopover(null)
      setActiveVertex(null)
    }
  }

  const handleMapPointerDown = (e) => {
    if (!isDrawing) return
    // Only respond to primary button on the SVG background (not on existing items)
    if (e.button !== 0) return
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    e.preventDefault(); e.stopPropagation()
    const n = pixelToNormalized(e.clientX, e.clientY, rect)
    onDrawingAddVertex?.([n.x, n.y])
  }

  const handleMapDoubleClick = (e) => {
    if (!isDrawing) return
    e.preventDefault(); e.stopPropagation()
    onDrawingFinish?.()
  }

  const popoverPosFromEvent = (e) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return { x: 0, y: 0 }
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  if (!overlay) return null

  const visibleLayers = overlay.layers.filter(l => layerVisibility[l.id])

  return (
    <div className="pm-canvas-wrapper" onClick={handleCanvasClick}>
      <div
        className={`pm-map-container${isDrawing ? ' pm-drawing' : ''}`}
        ref={containerRef}
        style={{ aspectRatio: `${ratio}`, '--pm-ratio': ratio }}
        onPointerDown={handleMapPointerDown}
        onDoubleClick={handleMapDoubleClick}
      >
        <img
          src={imgSrc}
          alt="Property map"
          draggable={false}
          onError={(e) => { e.target.style.background = '#1e293b'; e.target.alt = 'Map image not yet uploaded' }}
        />

        {/* SVG layer: cones, polygons, vertex/midpoint handles. */}
        <svg
          className={`pm-svg-overlay${editMode ? ' edit-mode' : ''}${isDrawing ? ' drawing' : ''}`}
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {visibleLayers.map(layer =>
            layer.items.map(item => {
              if (item.type === 'camera') {
                return <CameraCone key={`${item.id}-cone`} item={item} />
              }
              if (item.type === 'polygon') {
                return (
                  <PolygonItem
                    key={item.id}
                    item={item}
                    selected={selectedItemId === item.id}
                    editMode={editMode}
                    containerRef={containerRef}
                    onSelect={onSelect}
                    onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                    onViewClick={(e) => {
                      if (editMode) return
                      setPopover({ type: 'zone', item, pos: popoverPosFromEvent(e) })
                    }}
                  />
                )
              }
              return null
            })
          )}

          {/* In-progress drawing preview */}
          {isDrawing && drawingRing && drawingRing.length > 0 && (
            <g className="pm-drawing-preview" pointerEvents="none">
              {drawingRing.length >= 2 && (
                <polyline
                  points={drawingRing.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')}
                  fill="none" stroke="#facc15" strokeWidth={0.4} strokeDasharray="0.8 0.4"
                />
              )}
              {drawingRing.length >= 3 && (
                <polygon
                  points={drawingRing.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')}
                  fill="#facc15" fillOpacity={0.15} stroke="none"
                />
              )}
              {drawingRing.map(([x, y], i) => (
                <circle key={i} cx={x * 100} cy={y * 100} r={0.9}
                  fill="#facc15" stroke="#fff" strokeWidth={0.25} />
              ))}
            </g>
          )}
        </svg>

        {/* HTML overlay: camera dots (circular regardless of aspect),
            sensors, labels, rotation handles. */}
        {visibleLayers.map(layer =>
          layer.items.map(item => {
            if (item.type === 'camera') {
              return (
                <CameraMarker
                  key={item.id}
                  item={item}
                  selected={selectedItemId === item.id}
                  editMode={editMode}
                  containerRef={containerRef}
                  onSelect={onSelect}
                  onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                  onViewClick={(e) => {
                    if (editMode) return
                    setPopover({ type: 'camera', item, pos: popoverPosFromEvent(e) })
                  }}
                />
              )
            }
            if (item.type === 'marker') {
              return (
                <MarkerItem
                  key={item.id}
                  item={item}
                  selected={selectedItemId === item.id}
                  editMode={editMode}
                  containerRef={containerRef}
                  onSelect={onSelect}
                  onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                  onViewClick={(e) => {
                    if (editMode) return
                    setPopover({ type: 'sensor', item, pos: popoverPosFromEvent(e) })
                  }}
                />
              )
            }
            if (item.type === 'label') {
              return (
                <LabelItem
                  key={item.id}
                  item={item}
                  selected={selectedItemId === item.id}
                  editMode={editMode}
                  containerRef={containerRef}
                  onSelect={onSelect}
                  onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                />
              )
            }
            return null
          })
        )}

        {/* Polygon vertex/midpoint handles \u2014 HTML overlay so they stay
            circular (the SVG layer uses preserveAspectRatio="none"). */}
        {editMode && visibleLayers.map(layer =>
          layer.items
            .filter(it => it.type === 'polygon' && it.id === selectedItemId)
            .map(item => (
              <PolygonHandles
                key={`handles-${item.id}`}
                item={item}
                containerRef={containerRef}
                onSelect={onSelect}
                onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                activeVertex={activeVertex}
                onSetActiveVertex={setActiveVertex}
              />
            ))
        )}

        {popover?.type === 'camera' && (
          <CameraPopover item={popover.item} pos={popover.pos} onClose={() => setPopover(null)} />
        )}
        {popover?.type === 'zone' && (
          <ZonePopover item={popover.item} pos={popover.pos} onClose={() => setPopover(null)} />
        )}
        {popover?.type === 'sensor' && (
          <SensorPopover item={popover.item} pos={popover.pos} onClose={() => setPopover(null)} />
        )}
      </div>
    </div>
  )
}
