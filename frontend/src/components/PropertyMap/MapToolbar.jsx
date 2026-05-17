import { useState } from 'react'

const LAYER_ICONS = {
  camera: '📷',
  'droplet-fill': '💧',
  droplet: '🌱',
  type: '🔤',
}

let _idCounter = Date.now()
const genId = (prefix) => `${prefix}-${(++_idCounter).toString(36)}`

export default function MapToolbar({
  overlay, layerVisibility, editMode, user, saveStatus,
  onEditToggle, onLayerToggle, onAddItem, onUploadImage, onClose,
}) {
  const [showAdd, setShowAdd] = useState(false)

  const addCamera = () => {
    setShowAdd(false)
    onAddItem('cameras', {
      id: genId('cam'),
      type: 'camera',
      label: 'New Camera',
      x: 0.5, y: 0.5,
      rotation_deg: 0,
      // Default to a typical Ring Floodlight Cam (140° HFOV). User can pick a
      // specific model in the editor to refine these.
      fov_deg: 140,
      range: 0.20,
      color: '#3b82f6',
      meta: {},
    })
  }

  const addZone = () => {
    setShowAdd(false)
    onAddItem('zones', {
      id: genId('zone'),
      type: 'polygon',
      label: 'New Zone',
      color: '#4ade80',
      fill_opacity: 0.35,
      stroke_width: 2,
      rings: [[[0.45, 0.45], [0.55, 0.45], [0.50, 0.55]]],
      meta: {},
    })
  }

  const addSensor = () => {
    setShowAdd(false)
    onAddItem('sensors', {
      id: genId('sensor'),
      type: 'marker',
      label: 'New Sensor',
      x: 0.5, y: 0.5,
      color: '#06b6d4',
      meta: {},
    })
  }

  const addLabel = () => {
    setShowAdd(false)
    onAddItem('labels', {
      id: genId('lbl'),
      type: 'label',
      label: 'Label',
      x: 0.5, y: 0.5,
      meta: {},
    })
  }

  const statusClass = saveStatus === 'saving' ? 'saving' : saveStatus === 'unsaved' ? 'unsaved' : 'saved'
  const statusText  = saveStatus === 'saving' ? 'Saving…' : saveStatus === 'unsaved' ? 'Unsaved changes' : 'Saved'

  return (
    <div className="pm-toolbar">
      <span className="pm-toolbar__title">Property Map</span>

      <div className="pm-toolbar__layers">
        {overlay?.layers?.map(layer => (
          <button
            key={layer.id}
            className={`pm-layer-chip${layerVisibility[layer.id] ? ' active' : ''}`}
            onClick={() => onLayerToggle(layer.id, !layerVisibility[layer.id])}
          >
            {LAYER_ICONS[layer.icon] ?? ''} {layer.name}
          </button>
        ))}
      </div>

      <div className="pm-toolbar__actions">
        {editMode && (
          <>
            <div className="pm-add-menu">
              <button className="pm-btn" onClick={() => setShowAdd(v => !v)}>+ Add ▾</button>
              {showAdd && (
                <div className="pm-add-dropdown">
                  <button onClick={addCamera}>📷 Camera</button>
                  <button onClick={addZone}>💧 Zone</button>
                  <button onClick={addSensor}>🌱 Sensor</button>
                  <button onClick={addLabel}>🔤 Label</button>
                </div>
              )}
            </div>
            <button className="pm-btn" onClick={onUploadImage}>Upload image</button>
          </>
        )}

        {user && (
          <button
            className={`pm-btn${editMode ? ' edit-active' : ' primary'}`}
            onClick={onEditToggle}
          >
            {editMode ? 'Exit Edit' : 'Edit'}
          </button>
        )}

        <span className={`pm-save-status ${statusClass}`}>{statusText}</span>

        {onClose && (
          <button
            className="pm-btn pm-close-btn"
            onClick={onClose}
            title="Close map"
            aria-label="Close map"
          >✕</button>
        )}
      </div>
    </div>
  )
}
