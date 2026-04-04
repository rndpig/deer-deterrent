import { useState, useEffect } from 'react'
import './CombinedArchive.css'
import { apiFetch, API_URL } from '../api'

function CombinedArchive({ onBack, onAnnotate }) {
  const [activeTab, setActiveTab] = useState('snapshots') // 'snapshots' or 'videos'
  const [snapshots, setSnapshots] = useState([])
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [selectedVideo, setSelectedVideo] = useState(null)

  // Camera ID to name mapping
  const CAMERA_NAMES = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door',
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Woods',
    'c4dbad08f862': 'Side',
    'manual_upload': 'Manual Upload',
    'gml.27c3cea0rmpl.ab1ef9f8': 'Driveway' // Legacy ID format
  }

  useEffect(() => {
    loadArchived()
  }, [])

  const loadArchived = async () => {
    setLoading(true)
    await Promise.all([
      loadArchivedSnapshots(),
      loadArchivedVideos()
    ])
    setLoading(false)
  }
    const loadArchivedSnapshots = async () => {    try {
         const response = await apiFetch(`/api/snapshots/archived`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
              const data = await response.json()
      setSnapshots(data.snapshots || [])
    } catch (error) {
      console.error('Error loading archived snapshots:', error)
      setSnapshots([])
    }
  }
    const loadArchivedVideos = async () => {    try {
         const response = await apiFetch(`/api/videos/archived`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
              const data = await response.json()
      setVideos(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Error loading archived videos:', error)
      setVideos([])
    }
  }
    const unarchiveSnapshot = async (eventId) => {
    if (!confirm('Restore this snapshot to main gallery?')) {
      return
    }
    try {
         const response = await apiFetch(`/api/snapshots/${eventId}/unarchive`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      await loadArchivedSnapshots()
    } catch (error) {
      console.error('Error unarchiving snapshot:', error)
      alert('Failed to restore snapshot')
    }
  }
    const unarchiveVideo = async (videoId, filename) => {
    if (!confirm(`Restore "${filename}" to main gallery?`)) {
      return
    }
    try {
         const response = await apiFetch(`/api/videos/${videoId}/unarchive`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
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
    const formatCameraName = (item) => {
    const cameraId = item.camera_id || item.camera
    if (cameraId && CAMERA_NAMES[cameraId.toLowerCase()]) {
      return CAMERA_NAMES[cameraId.toLowerCase()]
    }
     if (item.camera_name) return item.camera_name
    if (item.camera) return item.camera.charAt(0).toUpperCase() + item.camera.slice(1)
    return 'Unknown'
  }
    if (loading) {
    return (
      <div className="combined-archive-container">
        <div className="archive-header">
          <button className="btn-back" onClick={onBack}>
            ← Back
          </button>
          <h1>📦 Archive</h1>
        </div>
        <div className="loading-message">Loading archive...</div>
      </div>
    )
  }

  return (
    <div className="combined-archive-container">
      <div className="archive-header">
        <button className="btn-back" onClick={onBack}>
          ← Back
        </button>
        <h1>📦 Archive</h1>
      </div>

      <div className="archive-tabs">
        <button 
          className={`tab-button ${activeTab === 'snapshots' ? 'active' : ''}`}
          onClick={() => setActiveTab('snapshots')}
        >
          📸 Snapshots ({snapshots.length})
        </button>
        <button 
          className={`tab-button ${activeTab === 'videos' ? 'active' : ''}`}
          onClick={() => setActiveTab('videos')}
        >
          🎬 Videos ({videos.length})
        </button>
      </div>

      {activeTab === 'snapshots' ? (
        <div className="archive-content">
          {snapshots.length === 0 ? (
            <div className="empty-archive">
              <p>No archived snapshots</p>
            </div>
          ) : (
            <div className="archive-table-container">
              <table className="archive-table">
                <thead>
                  <tr>
                    <th>Confidence</th>
                    <th>Camera</th>
                    <th>Date/Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((snapshot) => (
                    <tr key={snapshot.event_id}>
                      <td className="number-cell">
                        {snapshot.confidence_score 
                          ? `${Math.round(snapshot.confidence_score * 100)}%`
                          : '0%'}
                      </td>
                      <td>{formatCameraName(snapshot)}</td>
                      <td>{formatDate(snapshot.event_time)}</td>
                      <td className="actions-cell">
                        <button 
                          className="btn-table-action btn-view"
                          onClick={() => setSelectedSnapshot(snapshot)}
                          title="View snapshot image"
                        >
                          👁️ View
                        </button>
                        <button 
                          className="btn-table-action btn-restore"
                          onClick={() => unarchiveSnapshot(snapshot.event_id)}
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
      ) : (
        <div className="archive-content">
          {videos.length === 0 ? (
            <div className="empty-archive">
              <p>No archived videos</p>
            </div>
          ) : (
            <div className="archive-table-container">
              <table className="archive-table video-archive-table">
                <thead>
                  <tr>
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
                          className="btn-table-action btn-view"
                          onClick={() => setSelectedVideo(video)}
                          title="Play video"
                        >
                          👁️ View
                        </button>
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
      )}

      {/* Snapshot Modal */}
      {selectedSnapshot && (
        <div className="modal-overlay" onClick={() => setSelectedSnapshot(null)}>
          <div className="snapshot-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formatCameraName(selectedSnapshot)} - {formatDate(selectedSnapshot.event_time)}</h3>
              <button className="btn-close" onClick={() => setSelectedSnapshot(null)}>✕</button>
            </div>
            <div className="modal-body">
              <img 
                src={`${API_URL}/api/snapshots/${selectedSnapshot.event_id}/image`}
                alt="Archived snapshot"
                className="modal-image"
              />
            </div>
          </div>
        </div>
      )}

      {/* Video Modal */}
      {selectedVideo && (
        <div className="modal-overlay" onClick={() => setSelectedVideo(null)}>
          <div className="video-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formatCameraName(selectedVideo)} - {formatDate(selectedVideo.captured_at || selectedVideo.upload_date)}</h3>
              <button className="btn-close" onClick={() => setSelectedVideo(null)}>✕</button>
            </div>
            <div className="modal-body">
              <video 
                controls
                autoPlay
                className="modal-video"
                src={`${API_URL}/api/videos/${selectedVideo.id}/stream`}
              >
                Your browser does not support video playback.
              </video>
            </div>
          </div>
        </div>
      )}

      {/* Snapshot Modal */}
      {selectedSnapshot && (
        <div className="modal-overlay" onClick={() => setSelectedSnapshot(null)}>
          <div className="snapshot-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formatCameraName(selectedSnapshot)} - {formatDate(selectedSnapshot.event_time)}</h3>
              <button className="btn-close" onClick={() => setSelectedSnapshot(null)}>✕</button>
            </div>
            <div className="modal-body">
              <img 
                src={`${API_URL}/api/snapshots/${selectedSnapshot.event_id}/image`}
                alt="Archived snapshot"
                className="modal-image"
              />
            </div>
          </div>
        </div>
      )}

      {/* Video Modal */}
      {selectedVideo && (
        <div className="modal-overlay" onClick={() => setSelectedVideo(null)}>
          <div className="video-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{formatCameraName(selectedVideo)} - {formatDate(selectedVideo.captured_at || selectedVideo.upload_date)}</h3>
              <button className="btn-close" onClick={() => setSelectedVideo(null)}>✕</button>
            </div>
            <div className="modal-body">
              <video 
                controls
                autoPlay
                className="modal-video"
                src={`${API_URL}/api/videos/${selectedVideo.id}/stream`}
              >
                Your browser does not support video playback.
              </video>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CombinedArchive
