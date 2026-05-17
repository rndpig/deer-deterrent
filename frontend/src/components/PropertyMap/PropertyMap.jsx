import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { fetchOverlays, putOverlays } from './propertyMapApi'
import MapCanvas from './MapCanvas'
import MapToolbar from './MapToolbar'
import EditorPanel from './EditorPanel'
import ImageUploadModal from './ImageUploadModal'
import './PropertyMap.css'

const STORAGE_KEY = 'propertyMap_layerVisibility'

function initLayerVisibility(layers) {
  let stored = {}
  try { stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') } catch {}
  const result = {}
  for (const layer of (layers ?? [])) {
    result[layer.id] = layer.id in stored
      ? stored[layer.id]
      : (layer.default_visible_in ?? []).includes('deer')
  }
  return result
}

export default function PropertyMap({ onClose }) {
  const { user } = useAuth()
  const [overlay, setOverlay] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedItemId, setSelectedItemId] = useState(null)
  const [editMode, setEditMode] = useState(false)
  const [layerVisibility, setLayerVisibility] = useState({})
  const [saveStatus, setSaveStatus] = useState('saved')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const saveTimer = useRef(null)

  useEffect(() => {
    fetchOverlays()
      .then(data => {
        setOverlay(data)
        setLayerVisibility(initLayerVisibility(data.layers))
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // Escape closes the fullscreen modal
  useEffect(() => {
    if (!onClose) return
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const persistLayers = useCallback((vis) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(vis)) } catch {}
  }, [])

  const scheduleSave = useCallback((nextOverlay) => {
    setSaveStatus('unsaved')
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      setSaveStatus('saving')
      try {
        const saved = await putOverlays(nextOverlay)
        setOverlay(saved)
        setSaveStatus('saved')
      } catch (err) {
        console.error('Auto-save failed:', err)
        setSaveStatus('unsaved')
      }
    }, 2000)
  }, [])

  const updateItem = useCallback((layerId, itemId, patch) => {
    setOverlay(prev => {
      const next = {
        ...prev,
        layers: prev.layers.map(layer =>
          layer.id !== layerId ? layer : {
            ...layer,
            items: layer.items.map(item =>
              item.id !== itemId ? item : { ...item, ...patch }
            )
          }
        )
      }
      scheduleSave(next)
      return next
    })
  }, [scheduleSave])

  const addItem = useCallback((layerId, item) => {
    setOverlay(prev => {
      const next = {
        ...prev,
        layers: prev.layers.map(layer =>
          layer.id !== layerId ? layer : { ...layer, items: [...layer.items, item] }
        )
      }
      scheduleSave(next)
      return next
    })
    setSelectedItemId(item.id)
  }, [scheduleSave])

  const deleteItem = useCallback((layerId, itemId) => {
    setOverlay(prev => {
      const next = {
        ...prev,
        layers: prev.layers.map(layer =>
          layer.id !== layerId ? layer : {
            ...layer,
            items: layer.items.filter(item => item.id !== itemId)
          }
        )
      }
      scheduleSave(next)
      return next
    })
    setSelectedItemId(null)
  }, [scheduleSave])

  const setLayerVisible = useCallback((layerId, visible) => {
    setLayerVisibility(prev => {
      const next = { ...prev, [layerId]: visible }
      persistLayers(next)
      return next
    })
  }, [persistLayers])

  const handleImageUploaded = useCallback((dims) => {
    setOverlay(prev => {
      const next = { ...prev, image: { ...prev.image, ...dims } }
      scheduleSave(next)
      return next
    })
    setShowUploadModal(false)
  }, [scheduleSave])

  const getSelection = () => {
    if (!overlay || !selectedItemId) return null
    for (const layer of overlay.layers) {
      const item = layer.items.find(i => i.id === selectedItemId)
      if (item) return { item, layerId: layer.id }
    }
    return null
  }

  if (loading) return <div className="pm-loading">Loading map…</div>
  if (error)   return <div className="pm-error">Error: {error}</div>
  if (!overlay) return null

  const selection = getSelection()

  const containerClass = onClose ? 'pm-container pm-container--modal' : 'pm-container'

  return (
    <div className={containerClass} role={onClose ? 'dialog' : undefined} aria-modal={onClose ? 'true' : undefined}>
      <MapToolbar
        overlay={overlay}
        layerVisibility={layerVisibility}
        editMode={editMode}
        user={user}
        saveStatus={saveStatus}
        onEditToggle={() => { setEditMode(e => !e); setSelectedItemId(null) }}
        onLayerToggle={setLayerVisible}
        onAddItem={addItem}
        onUploadImage={() => setShowUploadModal(true)}
        onClose={onClose}
      />
      <div className="pm-body">
        <MapCanvas
          overlay={overlay}
          layerVisibility={layerVisibility}
          selectedItemId={selectedItemId}
          editMode={editMode}
          onSelect={setSelectedItemId}
          onDeselect={() => setSelectedItemId(null)}
          onUpdateItem={updateItem}
        />
        {editMode && selection && (
          <EditorPanel
            item={selection.item}
            layerId={selection.layerId}
            onUpdate={(patch) => updateItem(selection.layerId, selection.item.id, patch)}
            onDelete={() => deleteItem(selection.layerId, selection.item.id)}
          />
        )}
      </div>
      {showUploadModal && (
        <ImageUploadModal
          onUploaded={handleImageUploaded}
          onClose={() => setShowUploadModal(false)}
        />
      )}
    </div>
  )
}
