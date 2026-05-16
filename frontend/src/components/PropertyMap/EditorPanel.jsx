const CAMERA_IDS = [
  { id: '10cea9e4511f', label: 'Woods' },
  { id: 'c4dbad08f862', label: 'Side' },
  { id: '587a624d3fae', label: 'Driveway' },
  { id: '4439c4de7a79', label: 'Front Door' },
  { id: 'f045dae9383a', label: 'Back' },
]

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
      <SliderField label="Rotation" value={item.rotation_deg ?? 0} min={-180} max={180} onChange={v => onUpdate({ rotation_deg: v })} />
      <SliderField label="FOV" value={item.fov_deg ?? 90} min={10} max={360} onChange={v => onUpdate({ fov_deg: v })} />
      <SliderField label="Range" value={item.range ?? 0.15} min={0.01} max={1} step={0.01} onChange={v => onUpdate({ range: v })} />
      <Field label="Ring Camera">
        <select
          value={meta.ring_camera_id ?? ''}
          onChange={e => onUpdate({ meta: { ...meta, ring_camera_id: e.target.value } })}
        >
          <option value="">— none —</option>
          {CAMERA_IDS.map(c => <option key={c.id} value={c.id}>{c.label} ({c.id.slice(0, 8)}…)</option>)}
        </select>
      </Field>
      <div className="pm-coords">x: {(item.x ?? 0).toFixed(3)}, y: {(item.y ?? 0).toFixed(3)}</div>
      <button className="pm-delete-btn" onClick={() => {
        if (window.confirm(`Delete camera "${item.label}"?`)) onDelete()
      }}>Delete camera</button>
    </>
  )
}

function PolygonEditor({ item, onUpdate, onDelete }) {
  const meta = item.meta ?? {}
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
      <div className="pm-coords">Vertices: {(item.polygon ?? []).length}</div>
      <button className="pm-delete-btn" onClick={() => {
        if (window.confirm(`Delete zone "${item.label}"?`)) onDelete()
      }}>Delete zone</button>
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
      <div className="pm-coords">x: {(item.x ?? 0).toFixed(3)}, y: {(item.y ?? 0).toFixed(3)}</div>
      <button className="pm-delete-btn" onClick={() => {
        if (window.confirm(`Delete sensor "${item.label}"?`)) onDelete()
      }}>Delete sensor</button>
    </>
  )
}

function LabelEditor({ item, onUpdate, onDelete }) {
  return (
    <>
      <Field label="Text">
        <input type="text" value={item.label ?? ''} onChange={e => onUpdate({ label: e.target.value })} />
      </Field>
      <div className="pm-coords">x: {(item.x ?? 0).toFixed(3)}, y: {(item.y ?? 0).toFixed(3)}</div>
      <button className="pm-delete-btn" onClick={() => {
        if (window.confirm(`Delete label "${item.label}"?`)) onDelete()
      }}>Delete label</button>
    </>
  )
}

const TYPE_LABEL = { camera: 'Camera', polygon: 'Zone', marker: 'Sensor', label: 'Label' }

export default function EditorPanel({ item, layerId, onUpdate, onDelete }) {
  if (!item) return null
  return (
    <div className="pm-editor">
      <div className="pm-editor__header">
        <span>{TYPE_LABEL[item.type] ?? item.type}</span>
        <span style={{ color: '#64748b', fontSize: '0.75rem' }}>{item.id}</span>
      </div>
      <div className="pm-editor__body">
        {item.type === 'camera'  && <CameraEditor  item={item} onUpdate={onUpdate} onDelete={onDelete} />}
        {item.type === 'polygon' && <PolygonEditor item={item} onUpdate={onUpdate} onDelete={onDelete} />}
        {item.type === 'marker'  && <MarkerEditor  item={item} onUpdate={onUpdate} onDelete={onDelete} />}
        {item.type === 'label'   && <LabelEditor   item={item} onUpdate={onUpdate} onDelete={onDelete} />}
      </div>
    </div>
  )
}
