import { useState } from 'react'
import { postImage } from './propertyMapApi'

export default function ImageUploadModal({ onUploaded, onClose }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const result = await postImage(file)
      onUploaded({ intrinsic_width: result.intrinsic_width, intrinsic_height: result.intrinsic_height })
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="pm-modal-backdrop" onClick={onClose}>
      <div className="pm-modal" onClick={e => e.stopPropagation()}>
        <h3>Upload new base image</h3>
        <p style={{ color: '#94a3b8', fontSize: '0.82rem', margin: '0 0 0.75rem' }}>
          PNG only, max 5 MB. Existing overlay positions (normalized 0-1) remain valid.
        </p>
        <input
          type="file"
          accept="image/png"
          onChange={e => setFile(e.target.files?.[0] ?? null)}
        />
        {error && <div className="pm-modal__error">{error}</div>}
        <div className="pm-modal__actions">
          <button className="pm-btn" onClick={onClose}>Cancel</button>
          <button
            className="pm-btn primary"
            disabled={!file || uploading}
            onClick={handleUpload}
          >
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}
