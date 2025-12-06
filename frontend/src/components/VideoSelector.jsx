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

  const handleExtractFrames = async (video) => {
    const videoToExtract = video || selectedVideo
    if (!videoToExtract) return
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setProcessing(true)

    try {
      const response = await fetch(`${apiUrl}/api/videos/${videoToExtract.id}/extract-frames`, {
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
      onVideoSelected(videoToExtract)
    } catch (error) {
      console.error('Error extracting frames:', error)
      alert('❌ Failed to extract frames: ' + error.message)
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
        
        <div className="sampling-rate-control">
          <label htmlFor="sampling-rate">Frame Sampling:</label>
          <select 
            id="sampling-rate"
            value={samplingRate} 
            onChange={(e) => setSamplingRate(e.target.value)}
            disabled={processing}
          >
            <option value="all">All Frames (~30 fps)</option>
            <option value="high">High (~6/sec)</option>
            <option value="balanced">Balanced (~2/sec)</option>
            <option value="low">Low (~1/sec)</option>
            <option value="sparse">Sparse (~0.5/sec)</option>
          </select>
        </div>
      </div>

      {processing ? (
        <div className="processing-overlay">
          <div className="processing-message">
            <h2>⏳ Extracting Frames...</h2>
            <p>Please wait while frames are being extracted from the video.</p>
          </div>
        </div>
      ) : (
        <div className="selector-content">
          <div className="video-grid">
            {videos.map(video => {
              const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
              const thumbnailUrl = `${apiUrl}/api/videos/${video.id}/thumbnail`
              const hasAnnotations = video.has_annotations || false

              return (
                <div 
                  key={video.id}
                  className={`video-card ${hasAnnotations ? 'annotated' : ''}`}
                  onClick={() => {
                    setSelectedVideo(video)
                    handleExtractFrames(video)
                  }}
                >
                  <div className="video-thumbnail">
                    <img src={thumbnailUrl} alt={video.filename} />
                    {hasAnnotations && (
                      <div className="annotation-badge">✓ Annotated</div>
                    )}
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
      )}
    </div>
  )
}

export default VideoSelector
