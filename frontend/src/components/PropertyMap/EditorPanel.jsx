import { CAMERA_ID_LIST, getCameraDefaults, getCameraModelInfo } from './cameraDefaults'
import { getRings } from './polygonUtils'

function Field({ label, children }) {
  return (
    <div className="pm-field">
      <label>{label}</label>
      {children}
    </div>
  )
}

function SliderField({ label, value, min, max, step = 1, onChange }) {
  return (
    <Field label={`${label}: ${typeof value === 'number' ? value.toFixed(step < 1 ? 2 : 0) : value}`}>
      <input
        type="range" min={min} max={max} step={step}
        value={value ?? 0}
        onChange={e => onChange(Number(e.target.value))}
      />
    </Field>
  )
}

function CameraEditor({ item, onUpdate, onDelete }) {
  const meta = item.meta ?? {}
  const modelInfo = getCameraModelInfo(meta.ring_camera_id)

  const handleRingCameraChange = (e) => {
    const ringId = e.target.value
    const patch = { meta: { ...meta, ring_camera_id: ringId } }
    // Auto-apply hardware FOV/range when selecting a known camera, but only
    // if the user hasn't already set custom values that differ from the
    // previous model's defaults (we always apply on first selection).
    const defaults = getCameraDefaults(ringId)
    if (defaults) {
      patch.fov_deg = defaults.fov_deg
      patch.range = defaults.range
      if (!item.label || item.label === 'New Camera') {
        const info = getCameraModelInfo(ringId)
        if (info) patch.label = info.label
      }
    }
    onUpdate(patch)
  }

  const handleResetDefaults = () => {
    const defaults = getCameraDefaults(meta.ring_camera_id)
    if (defaults) onUpdate(defaults)
  }

  return (
    <>
      <Field label="Label">
        <input type="text" value={item.label ?? ''} onChange={e => onUpdate({ label: e.target.value })} />
      </Field>
      <Field label="Color">
        <div className="pm-field-row">
          <input type="color" value={item.color ?? '#3b82f6'} onChange={e => onUpdate({ color: e.target.value })} />
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{item.color}</span>
        </div>
      </Field>
      <Field label="Ring Camera">
        <select
          value={meta.ring_camera_id ?? ''}
          onChange={handleRingCameraChange}
        >
          <option value="">— none —</option>
          {CAMERA_ID_LIST.map(c => (
            <option key={c.id} value={c.id}>{c.label} — {c.model}</option>
          ))}
        </select>
      </Field>
      {modelInfo && (
        <div className="pm-field-row" style={{ justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
            {modelInfo.model}
          </span>
          <button
            type="button"
            className="pm-btn"
            onClick={handleResetDefaults}
            title="Reset FOV and range to this camera model's hardware specs"
          >
            Reset to model defaults
          </button>
        </div>
      )}
      <SliderField label="Rotation" value={item.rotation_deg ?? 0} min={-180} max={180} onChange={v => onUpdate({ rotation_deg: v })} />
      <SliderField label="FOV" value={item.fov_deg ?? 90} min={10} max={360} onChange={v => onUpdate({ fov_deg: v })} />
      <SliderField label="Range" value={item.range ?? 0.15} min={0.01} max={1} step={0.01} onChange={v => onUpdate({ range: v })} />
    </>
  )
}

function PolygonEditor({
  item, onUpdate, onDelete,
  drawingItemId, drawingRing,
  onStartDrawingRing, onFinishDrawingRing, onCancelDrawingRing, onRemoveRing,
}) {
  const meta = item.meta ?? {}
  const rings = getRings(item)
  const isDrawingThis = drawingItemId === item.id
  const isDrawingOther = drawingItemId && drawingItemId !== item.id

  return (
    <>
      <Field label="Label">
        <input type="text" value={item.label ?? ''} onChange={e => onUpdate({ label: e.target.value })} />
      </Field>
      <Field label="Color">
        <div className="pm-field-row">
          <input type="color" value={item.color ?? '#4ade80'} onChange={e => onUpdate({ color: e.target.value })} />
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{item.color}</span>
        </div>
      </Field>
      <SliderField label="Fill opacity" value={item.fill_opacity ?? 0.35} min={0} max={1} step={0.05} onChange={v => onUpdate({ fill_opacity: v })} />
      <SliderField label="Stroke width" value={item.stroke_width ?? 2} min={0.5} max={6} step={0.5} onChange={v => onUpdate({ stroke_width: v })} />
      <Field label="Rainbird Zone #">
        <input type="number" min={1} max={14} value={meta.rainbird_zone ?? ''} onChange={e => {
          const n = parseInt(e.target.value, 10)
          onUpdate({ meta: { ...meta, rainbird_zone: isNaN(n) ? undefined : n } })
        }} />
      </Field>

      {/* Shapes (rings) ---------------------------------------------------- */}
      <div className="pm-section-header">Shapes</div>
      <div className="pm-shape-list">
        {rings.map((ring, idx) => (
          <div key={idx} className="pm-shape-row">
            <span>Shape {idx + 1} <span style={{ color: '#64748b' }}>({ring.length} vertices)</span></span>
            <button
              type="button"
              className="pm-btn pm-shape-del"
              disabled={rings.length <= 1}
              onClick={() => {
                if (window.confirm(`Remove shape ${idx + 1} from "${item.label}"?`)) onRemoveRing?.(idx)
              }}
              title={rings.length <= 1 ? 'A zone must have at least one shape' : 'Remove this shape'}
            >×</button>
          </div>
        ))}
      </div>

      {isDrawingThis ? (
        <div className="pm-drawing-banner">
          <div style={{ fontSize: '0.78rem', color: '#facc15', marginBottom: '0.4rem' }}>
            Drawing new shape: <strong>{drawingRing?.length ?? 0}</strong> vertices
          </div>
          <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
            Click on the map to drop vertices. Double-click or press Enter to finish. Esc to cancel.
          </div>
          <div className="pm-field-row">
            <button
              type="button"
              className="pm-btn primary"
              disabled={(drawingRing?.length ?? 0) < 3}
              onClick={onFinishDrawingRing}
            >Finish ({drawingRing?.length ?? 0})</button>
            <button type="button" className="pm-btn" onClick={onCancelDrawingRing}>Cancel</button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="pm-btn"
          style={{ marginTop: '0.4rem', width: '100%' }}
          disabled={isDrawingOther}
          onClick={onStartDrawingRing}
          title={isDrawingOther ? 'Finish or cancel the current drawing first' : 'Draw an additional disconnected shape for this zone'}
        >+ Add shape</button>
      )}

      <div className="pm-hint">
        {rings.reduce((sum, r) => sum + r.length, 0)} vertices total · drag to move · drag a midpoint to insert · hover a vertex → click × (or Delete key) to remove.
      </div>
    </>
  )
}

function MarkerEditor({ item, onUpdate, onDelete }) {
  const meta = item.meta ?? {}
  return (
    <>
      <Field label="Label">
        <input type="text" value={item.label ?? ''} onChange={e => onUpdate({ label: e.target.value })} />
      </Field>
      <Field label="Color">
        <div className="pm-field-row">
          <input type="color" value={item.color ?? '#06b6d4'} onChange={e => onUpdate({ color: e.target.value })} />
          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{item.color}</span>
        </div>
      </Field>
      <Field label="Kind">
        <select value={meta.kind ?? ''} onChange={e => onUpdate({ meta: { ...meta, kind: e.target.value } })}>
          <option value="">— none —</option>
          <option value="soil_moisture">Soil moisture</option>
          <option value="light">Light sensor</option>
        </select>
      </Field>
      <Field label="Channel / Name">
        <input type="text" value={meta.channel ?? meta.name ?? ''} onChange={e => {
          const v = e.target.value
          onUpdate({ meta: { ...meta, channel: v ? Number(v) || v : undefined, name: v || undefined } })
        }} />
      </Field>
    </>
  )
}

function LabelEditor({ item, onUpdate, onDelete }) {
  return (
    <>
      <Field label="Text">
        <input type="text" value={item.label ?? ''} onChange={e => onUpdate({ label: e.target.value })} />
      </Field>
    </>
  )
}

const TYPE_LABEL = { camera: 'Camera', polygon: 'Zone', marker: 'Sensor', label: 'Label' }
const TYPE_NOUN  = { camera: 'camera', polygon: 'zone', marker: 'sensor', label: 'label' }

export default function EditorPanel({
  item, layerId, onUpdate, onDelete,
  drawingItemId, drawingRing,
  onStartDrawingRing, onFinishDrawingRing, onCancelDrawingRing, onRemoveRing,
}) {
  if (!item) return null
  const noun = TYPE_NOUN[item.type] ?? 'item'
  const hasXY = typeof item.x === 'number' && typeof item.y === 'number'
  return (
    <div className="pm-editor">
      <div className="pm-editor__header">
        <span className="pm-editor__title">{TYPE_LABEL[item.type] ?? item.type}</span>
        {hasXY && (
          <span className="pm-editor__coords">x: {item.x.toFixed(3)}, y: {item.y.toFixed(3)}</span>
        )}
        <span className="pm-editor__id">{item.id}</span>
        <button
          type="button"
          className="pm-editor__delete"
          onClick={() => {
            if (window.confirm(`Delete ${noun} "${item.label}"?`)) onDelete()
          }}
          title={`Delete ${noun}`}
        >Delete</button>
      </div>
      <div className="pm-editor__body">
        {item.type === 'camera'  && <CameraEditor  item={item} onUpdate={onUpdate} onDelete={onDelete} />}
        {item.type === 'polygon' && (
          <PolygonEditor
            item={item} onUpdate={onUpdate} onDelete={onDelete}
            drawingItemId={drawingItemId}
            drawingRing={drawingRing}
            onStartDrawingRing={onStartDrawingRing}
            onFinishDrawingRing={onFinishDrawingRing}
            onCancelDrawingRing={onCancelDrawingRing}
            onRemoveRing={onRemoveRing}
          />
        )}
        {item.type === 'marker'  && <MarkerEditor  item={item} onUpdate={onUpdate} onDelete={onDelete} />}
        {item.type === 'label'   && <LabelEditor   item={item} onUpdate={onUpdate} onDelete={onDelete} />}
      </div>
    </div>
  )
}
