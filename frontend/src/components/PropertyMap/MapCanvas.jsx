import { useRef, useState, useCallback } from 'react'
import { API_URL, apiFetch } from '../../api'
import { pixelToNormalized, normalizedToPercent } from './coords'

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

function CameraItem({ item, selected, editMode, containerRef, onSelect, onUpdate }) {
  const cx = item.x * 100
  const cy = item.y * 100
  const rotation = item.rotation_deg ?? 0
  const fovDeg = item.fov_deg ?? 90
  const range = item.range ?? 0.15
  const color = item.color ?? '#3b82f6'

  const handleMarkerDown = useCallback((e) => {
    if (!editMode) { onSelect(item.id); return }
    e.preventDefault(); e.stopPropagation()
    onSelect(item.id)
    e.currentTarget.setPointerCapture(e.pointerId)
    const move = (me) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      onUpdate({ x: n.x, y: n.y })
    }
    const up = () => {
      e.currentTarget?.releasePointerCapture?.(e.pointerId)
      e.currentTarget?.removeEventListener('pointermove', move)
      e.currentTarget?.removeEventListener('pointerup', up)
    }
    e.currentTarget.addEventListener('pointermove', move)
    e.currentTarget.addEventListener('pointerup', up)
  }, [editMode, item.id, containerRef, onSelect, onUpdate])

  const rad = rotation * DEG2RAD
  const handleX = cx + 3 * Math.sin(rad)
  const handleY = cy - 3 * Math.cos(rad)

  const handleRotateDown = useCallback((e) => {
    if (!editMode) return
    e.preventDefault(); e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    const move = (me) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const nx = (me.clientX - rect.left) / rect.width * 100
      const ny = (me.clientY - rect.top)  / rect.height * 100
      const dx = nx - cx, dy = ny - cy
      const angle = Math.atan2(dx, -dy) / DEG2RAD
      onUpdate({ rotation_deg: Math.round(angle) })
    }
    const up = () => {
      e.currentTarget?.releasePointerCapture?.(e.pointerId)
      e.currentTarget?.removeEventListener('pointermove', move)
      e.currentTarget?.removeEventListener('pointerup', up)
    }
    e.currentTarget.addEventListener('pointermove', move)
    e.currentTarget.addEventListener('pointerup', up)
  }, [editMode, cx, cy, containerRef, onUpdate])

  return (
    <g>
      <path
        d={fovPath(cx, cy, rotation, fovDeg, range)}
        fill={color}
        fillOpacity={0.25}
        stroke={color}
        strokeWidth={0.3}
        className="pm-fov-cone"
        onClick={() => onSelect(item.id)}
      />
      <circle
        cx={cx} cy={cy} r={1.2}
        fill={color}
        stroke="#fff"
        strokeWidth={0.3}
        style={{ cursor: editMode ? 'grab' : 'pointer' }}
        onPointerDown={handleMarkerDown}
      />
      {selected && (
        <line
          x1={cx} y1={cy} x2={handleX} y2={handleY}
          stroke="#fff" strokeWidth={0.2} strokeDasharray="0.5 0.5"
        />
      )}
      {editMode && selected && (
        <circle
          cx={handleX} cy={handleY} r={0.8}
          fill="#fff" stroke={color} strokeWidth={0.3}
          className="pm-rotate-handle"
          onPointerDown={handleRotateDown}
        />
      )}
    </g>
  )
}

function PolygonItem({ item, selected, editMode, containerRef, onSelect, onUpdate }) {
  const color = item.color ?? '#4ade80'
  const fillOpacity = item.fill_opacity ?? 0.35
  const strokeWidth = item.stroke_width ?? 2
  const poly = item.polygon ?? []

  const handlePolyDown = useCallback((e) => {
    if (!editMode) { onSelect(item.id); return }
    e.preventDefault(); e.stopPropagation()
    onSelect(item.id)
  }, [editMode, item.id, onSelect])

  const handleVertexDown = useCallback((e, idx) => {
    e.preventDefault(); e.stopPropagation()
    if (!editMode) return
    onSelect(item.id)
    e.currentTarget.setPointerCapture(e.pointerId)
    const move = (me) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      const newPoly = poly.map((pt, i) => i === idx ? [n.x, n.y] : pt)
      onUpdate({ polygon: newPoly })
    }
    const up = () => {
      e.currentTarget?.releasePointerCapture?.(e.pointerId)
      e.currentTarget?.removeEventListener('pointermove', move)
      e.currentTarget?.removeEventListener('pointerup', up)
    }
    e.currentTarget.addEventListener('pointermove', move)
    e.currentTarget.addEventListener('pointerup', up)
  }, [editMode, item.id, poly, containerRef, onSelect, onUpdate])

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
        <circle
          key={idx}
          cx={x * 100} cy={y * 100} r={1.0}
          fill="#fff" stroke={color} strokeWidth={0.3}
          className="pm-vertex-handle"
          onPointerDown={(e) => handleVertexDown(e, idx)}
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

  const handleDown = useCallback((e) => {
    if (!editMode) { onSelect(item.id); return }
    e.preventDefault(); e.stopPropagation()
    onSelect(item.id)
    e.currentTarget.setPointerCapture(e.pointerId)
    const move = (me) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      onUpdate({ x: n.x, y: n.y })
    }
    const up = () => {
      e.currentTarget?.releasePointerCapture?.(e.pointerId)
      e.currentTarget?.removeEventListener('pointermove', move)
      e.currentTarget?.removeEventListener('pointerup', up)
    }
    e.currentTarget.addEventListener('pointermove', move)
    e.currentTarget.addEventListener('pointerup', up)
  }, [editMode, item.id, containerRef, onSelect, onUpdate])

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

  const handleDown = useCallback((e) => {
    if (!editMode) { onSelect(item.id); return }
    e.preventDefault(); e.stopPropagation()
    onSelect(item.id)
    e.currentTarget.setPointerCapture(e.pointerId)
    const move = (me) => {
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const n = pixelToNormalized(me.clientX, me.clientY, rect)
      onUpdate({ x: n.x, y: n.y })
    }
    const up = () => {
      e.currentTarget?.releasePointerCapture?.(e.pointerId)
      e.currentTarget?.removeEventListener('pointermove', move)
      e.currentTarget?.removeEventListener('pointerup', up)
    }
    e.currentTarget.addEventListener('pointermove', move)
    e.currentTarget.addEventListener('pointerup', up)
  }, [editMode, item.id, containerRef, onSelect, onUpdate])

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

  useState(() => {
    if (!cameraId) return
    apiFetch(`/api/snapshots?camera_id=${cameraId}&limit=1`)
      .then(r => r.json())
      .then(data => { if (data?.length) setSnapshot(data[0]) })
      .catch(() => {})
  })

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

  const handleItemViewClick = (type, item, e) => {
    if (editMode) return
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top }
    onSelect(item.id)
    if (type === 'camera') setPopover({ type: 'camera', item, pos })
    else if (type === 'polygon') setPopover({ type: 'zone', item, pos })
    else setPopover(null)
  }

  if (!overlay) return null

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

        <svg
          className={`pm-svg-overlay${editMode ? ' edit-mode' : ''}`}
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {overlay.layers.filter(l => layerVisibility[l.id]).map(layer =>
            layer.items.map(item => {
              if (item.type === 'camera') {
                return (
                  <CameraItem
                    key={item.id}
                    item={item}
                    selected={selectedItemId === item.id}
                    editMode={editMode}
                    containerRef={containerRef}
                    onSelect={(id) => {
                      onSelect(id)
                      if (!editMode) handleItemViewClick('camera', item, window.event)
                    }}
                    onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                  />
                )
              }
              if (item.type === 'polygon') {
                return (
                  <PolygonItem
                    key={item.id}
                    item={item}
                    selected={selectedItemId === item.id}
                    editMode={editMode}
                    containerRef={containerRef}
                    onSelect={(id) => {
                      onSelect(id)
                      if (!editMode) handleItemViewClick('polygon', item, window.event)
                    }}
                    onUpdate={(patch) => onUpdateItem(layer.id, item.id, patch)}
                  />
                )
              }
              return null
            })
          )}
        </svg>

        {overlay.layers.filter(l => layerVisibility[l.id]).map(layer =>
          layer.items.map(item => {
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
