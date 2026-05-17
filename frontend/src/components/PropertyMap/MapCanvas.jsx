import { useRef, useState, useCallback, useEffect } from 'react'
import { API_URL, apiFetch } from '../../api'
import { pixelToNormalized, normalizedToPercent, clamp01 } from './coords'
import { useMapDrag } from './useMapDrag'

const DEG2RAD = Math.PI / 180

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

function polygonPoints(poly) {
  return poly.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')
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

// Polygon vertex extracted as a component so each gets its own hook instance
// (Rules of Hooks: can't call hooks inside loops/map callbacks).
function PolyVertex({ idx, x, y, color, poly, containerRef, onSelect, onUpdate, onContextMenu }) {
  const start = useMapDrag({
    containerRef,
    onStart: onSelect,
    onMove: (me, rect) => {
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      const newPoly = poly.map((pt, i) => i === idx ? [n.x, n.y] : pt)
      onUpdate({ polygon: newPoly })
    },
  })
  return (
    <circle
      cx={x * 100} cy={y * 100} r={1.0}
      fill="#fff" stroke={color} strokeWidth={0.3}
      className="pm-vertex-handle"
      onPointerDown={start}
      onContextMenu={onContextMenu}
    />
  )
}

function PolygonItem({ item, selected, editMode, containerRef, onSelect, onUpdate, onViewClick }) {
  const color = item.color ?? '#4ade80'
  const fillOpacity = item.fill_opacity ?? 0.35
  const strokeWidth = item.stroke_width ?? 2
  const poly = item.polygon ?? []

  const handlePolyDown = useCallback((e) => {
    if (!editMode) {
      onSelect(item.id)
      onViewClick?.(e)
      return
    }
    e.preventDefault(); e.stopPropagation()
    onSelect(item.id)
  }, [editMode, item.id, onSelect, onViewClick])

  const handleVertexRightClick = useCallback((e, idx) => {
    e.preventDefault()
    if (!editMode || poly.length <= 3) return
    const newPoly = poly.filter((_, i) => i !== idx)
    onUpdate({ polygon: newPoly })
  }, [editMode, poly, onUpdate])

  const handleMidpointClick = useCallback((e, idx) => {
    e.preventDefault(); e.stopPropagation()
    if (!editMode) return
    const a = poly[idx], b = poly[(idx + 1) % poly.length]
    const mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
    const newPoly = [...poly.slice(0, idx + 1), mid, ...poly.slice(idx + 1)]
    onUpdate({ polygon: newPoly })
  }, [editMode, poly, onUpdate])

  const sw = strokeWidth * 0.05

  return (
    <g>
      <polygon
        points={polygonPoints(poly)}
        fill={color}
        fillOpacity={selected ? fillOpacity * 1.3 : fillOpacity}
        stroke={color}
        strokeWidth={sw}
        style={{ cursor: editMode ? 'default' : 'pointer' }}
        onPointerDown={handlePolyDown}
      />
      {selected && editMode && poly.map(([x, y], idx) => (
        <PolyVertex
          key={idx}
          idx={idx}
          x={x}
          y={y}
          color={color}
          poly={poly}
          containerRef={containerRef}
          onSelect={() => onSelect(item.id)}
          onUpdate={onUpdate}
          onContextMenu={(e) => handleVertexRightClick(e, idx)}
        />
      ))}
      {selected && editMode && poly.map(([x, y], idx) => {
        const next = poly[(idx + 1) % poly.length]
        const mx = (x + next[0]) / 2 * 100
        const my = (y + next[1]) / 2 * 100
        return (
          <circle
            key={`mid-${idx}`}
            cx={mx} cy={my} r={0.7}
            fill={color} className="pm-midpoint-handle"
            onClick={(e) => handleMidpointClick(e, idx)}
          />
        )
      })}
    </g>
  )
}

function MarkerItem({ item, selected, editMode, containerRef, onSelect, onUpdate }) {
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
    if (!editMode) { onSelect(item.id); return }
    startDrag(e)
  }

  return (
    <div
      className={`pm-marker${editMode ? ' edit-mode' : ''}${selected ? ' selected' : ''}`}
      style={{ left: pctX, top: pctY }}
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
  const [snapshot, setSnapshot] = useState(null)
  const cameraId = item.meta?.ring_camera_id

  useEffect(() => {
    if (!cameraId) return
    apiFetch(`/api/snapshots?camera_id=${cameraId}&limit=1`)
      .then(r => r.json())
      .then(data => { if (data?.length) setSnapshot(data[0]) })
      .catch(() => {})
  }, [cameraId])

  return (
    <div className="pm-popover" style={{ left: pos.x, top: pos.y }}>
      <button className="pm-popover__close" onClick={onClose}>✕</button>
      <div className="pm-popover__title">{item.label}</div>
      {snapshot && (
        <img src={`${API_URL}/api/snapshots/${snapshot.id}/image`} alt={item.label} />
      )}
      {!snapshot && cameraId && <div style={{ color: '#64748b', fontSize: '0.75rem' }}>No recent snapshot</div>}
      {!cameraId && <div style={{ color: '#64748b', fontSize: '0.75rem' }}>No Ring ID configured</div>}
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

export default function MapCanvas({
  overlay, layerVisibility, selectedItemId, editMode,
  onSelect, onDeselect, onUpdateItem
}) {
  const containerRef = useRef(null)
  const [popover, setPopover] = useState(null)

  const ratio = overlay?.image
    ? overlay.image.intrinsic_width / overlay.image.intrinsic_height
    : 1782 / 768
  const imgSrc = `${API_URL}/api/property-map/image`

  const handleCanvasClick = (e) => {
    if (e.target === e.currentTarget || e.target.tagName === 'IMG') {
      onDeselect()
      setPopover(null)
    }
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
        className="pm-map-container"
        ref={containerRef}
        style={{ aspectRatio: `${ratio}` }}
      >
        <img
          src={imgSrc}
          alt="Property map"
          draggable={false}
          onError={(e) => { e.target.style.background = '#1e293b'; e.target.alt = 'Map image not yet uploaded' }}
        />

        {/* SVG layer: cones, polygons, vertex/midpoint handles. */}
        <svg
          className={`pm-svg-overlay${editMode ? ' edit-mode' : ''}`}
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

        {popover?.type === 'camera' && (
          <CameraPopover item={popover.item} pos={popover.pos} onClose={() => setPopover(null)} />
        )}
        {popover?.type === 'zone' && (
          <ZonePopover item={popover.item} pos={popover.pos} onClose={() => setPopover(null)} />
        )}
      </div>
    </div>
  )
}
