import { useState, useEffect } from 'react'
import './VideoSelector.css'

function VideoSelector({ onBack, onVideoSelected }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [samplingRate, setSamplingRate] = useState('balanced')
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    loadVideos()
  }, [])

  const loadVideos = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/videos`)
      if (!response.ok) throw new Error('Failed to load videos')
      
      const data = await response.json()
      setVideos(data)
    } catch (error) {
      console.error('Error loading videos:', error)
      alert('Failed to load videos: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleExtractFrames = async () => {
    if (!selectedVideo) return
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setProcessing(true)

    try {
      const response = await fetch(`${apiUrl}/api/videos/${selectedVideo.id}/extract-frames`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          sampling_rate: samplingRate 
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to extract frames')
      }

      const result = await response.json()
      console.log('Extracted frames:', result)
      
      // Navigate to annotation view
      onVideoSelected(selectedVideo)
    } catch (error) {
      console.error('Error extracting frames:', error)
      alert('❌ Failed to extract frames: ' + error.message)
    } finally {
      setProcessing(false)
    }
  }

  const formatCameraName = (video) => {
    if (video.camera_name && video.camera_name !== 'Unknown Camera') {
      return video.camera_name
    }
    return 'Unknown Camera'
  }

  const formatDate = (timestamp) => {
    if (!timestamp) return 'Unknown date'
    const date = new Date(timestamp)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  if (loading) {
    return (
      <div className="video-selector-container">
        <div className="loading-message">Loading videos...</div>
      </div>
    )
  }

  return (
    <div className="video-selector-container">
      <div className="selector-header">
        <button className="btn-back" onClick={onBack}>
          ← Back to Library
        </button>
        <h1>🎬 Select Video for Annotation</h1>
      </div>

      <div className="selector-content">
        <div className="video-grid">
          {videos.map(video => {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
            const thumbnailUrl = `${apiUrl}/api/videos/${video.id}/thumbnail`
            const isSelected = selectedVideo?.id === video.id

            return (
              <div 
                key={video.id}
                className={`video-card ${isSelected ? 'selected' : ''}`}
                onClick={() => setSelectedVideo(video)}
              >
                <div className="video-thumbnail">
                  <img src={thumbnailUrl} alt={video.filename} />
                  {isSelected && <div className="selected-badge">✓</div>}
                </div>
                <div className="video-info">
                  <div className="video-camera">{formatCameraName(video)}</div>
                  <div className="video-filename">{video.filename}</div>
                  <div className="video-date">{formatDate(video.upload_date)}</div>
                </div>
              </div>
            )
          })}
        </div>

        {videos.length === 0 && (
          <div className="empty-state">
            <p>No videos uploaded yet. Go back to upload videos first.</p>
          </div>
        )}
      </div>

      {selectedVideo && (
        <div className="extraction-panel">
          <h2>Frame Extraction Settings</h2>
          
          <div className="settings-row">
            <label htmlFor="sampling-rate">Frame Sampling Rate:</label>
            <select 
              id="sampling-rate"
              value={samplingRate} 
              onChange={(e) => setSamplingRate(e.target.value)}
              disabled={processing}
            >
              <option value="all">All Frames (~30 fps)</option>
              <option value="high">High (every 5th frame, ~6/sec)</option>
              <option value="balanced">Balanced (every 15th frame, ~2/sec) - Recommended</option>
              <option value="low">Low (every 30th frame, ~1/sec)</option>
              <option value="sparse">Sparse (every 60th frame, ~0.5/sec)</option>
            </select>
          </div>

          <div className="extraction-info">
            <p>Selected video: <strong>{selectedVideo.filename}</strong></p>
            <p>Camera: <strong>{formatCameraName(selectedVideo)}</strong></p>
          </div>

          <button 
            className="btn-extract"
            onClick={handleExtractFrames}
            disabled={processing}
          >
            {processing ? '⏳ Extracting Frames...' : '✅ Extract Frames & Start Annotation'}
          </button>
        </div>
      )}
    </div>
  )
}

export default VideoSelector
