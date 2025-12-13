import { useState, useEffect } from 'react'
import './ArchivedVideos.css'

function ArchivedVideos({ onBack, onAnnotate }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadArchivedVideos()
  }, [])

  const loadArchivedVideos = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/archived`)
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorText}`)
      }
      
      const data = await response.json()
      setVideos(Array.isArray(data) ? data : [])
      setLoading(false)
    } catch (error) {
      console.error('Error loading archived videos:', error)
      setLoading(false)
      alert(`Failed to load archived videos: ${error.message}`)
    }
  }

  const unarchiveVideo = async (videoId, filename) => {
    if (!confirm(`Restore "${filename}" to main gallery?`)) {
      return
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    
    try {
      const response = await fetch(`${apiUrl}/api/videos/${videoId}/unarchive`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      // Reload archived videos
      await loadArchivedVideos()
    } catch (error) {
      console.error('Error unarchiving video:', error)
      alert('Failed to restore video')
    }
  }

  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})
  }

  const formatCameraName = (video) => {
    if (video.camera) return video.camera.charAt(0).toUpperCase() + video.camera.slice(1)
    if (video.camera_name) return video.camera_name
    return 'Unknown'
  }

  if (loading) {
    return (
      <div className="archived-videos-container">
        <div className="archived-header">
          <button className="btn-back" onClick={onBack}>
            ← Back
          </button>
          <h1>📦 Archived Videos</h1>
        </div>
        <div className="loading-message">Loading archived videos...</div>
      </div>
    )
  }

  return (
    <div className="archived-videos-container">
      <div className="archived-header">
        <button className="btn-back" onClick={onBack}>
          ← Back
        </button>
        <h1>📦 Archived Videos</h1>
        <div className="archived-count">{videos.length} archived</div>
      </div>

      {videos.length === 0 ? (
        <div className="empty-archive">
          <p>No archived videos</p>
        </div>
      ) : (
        <div className="archived-table-container">
          <table className="archived-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Camera</th>
                <th>Date/Time</th>
                <th>Frames</th>
                <th>Detections</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((video) => (
                <tr key={video.id}>
                  <td className="filename-cell">{video.filename}</td>
                  <td>{formatCameraName(video)}</td>
                  <td>{formatDate(video.captured_at || video.upload_date)}</td>
                  <td className="number-cell">{video.frame_count}</td>
                  <td className="number-cell">{video.detection_count}</td>
                  <td>
                    {video.fully_annotated ? (
                      <span className="status-badge complete">✓ Complete</span>
                    ) : video.has_annotations ? (
                      <span className="status-badge partial">⚠ Partial</span>
                    ) : (
                      <span className="status-badge none">—</span>
                    )}
                  </td>
                  <td className="actions-cell">
                    <button 
                      className="btn-table-action btn-annotate"
                      onClick={() => onAnnotate(video.id)}
                      title="View/annotate frames"
                    >
                      ✏️ Annotate
                    </button>
                    <button 
                      className="btn-table-action btn-restore"
                      onClick={() => unarchiveVideo(video.id, video.filename)}
                      title="Restore to main gallery"
                    >
                      ↩️ Restore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default ArchivedVideos


