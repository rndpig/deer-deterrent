import { useState } from 'react'
import './VideoUpload.css'

function VideoUpload() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file) {
      // Check file type
      const validTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/avi']
      if (!validTypes.includes(file.type) && !file.name.match(/\.(mp4|mov|avi)$/i)) {
        setError('Please select a valid video file (MP4, MOV, or AVI)')
        return
      }
      
      // Check file size (max 100MB)
      if (file.size > 100 * 1024 * 1024) {
        setError('File size must be less than 100MB')
        return
      }
      
      setSelectedFile(file)
      setError(null)
      setResults(null)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    
    setUploading(true)
    setError(null)
    setResults(null)
    
    const formData = new FormData()
    formData.append('video', selectedFile)
    
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/detect/video`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }
      
      const data = await response.json()
      setResults(data)
    } catch (err) {
      setError(err.message || 'Error processing video')
      console.error('Upload error:', err)
    } finally {
      setUploading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setResults(null)
    setError(null)
  }

  return (
    <div className="video-upload">
      <div className="upload-header">
        <h2>🎥 Video Analysis</h2>
        <p className="description">
          Upload Ring camera footage to analyze for deer detections. 
          This helps diagnose missed detections and gather training data.
        </p>
      </div>

      {!results ? (
        <div className="upload-section">
          <div className="file-input-container">
            <input 
              type="file" 
              id="video-file"
              accept="video/mp4,video/quicktime,video/x-msvideo,.mp4,.mov,.avi"
              onChange={handleFileSelect}
              disabled={uploading}
            />
            <label htmlFor="video-file" className="file-input-label">
              {selectedFile ? (
                <>
                  <span className="file-name">📹 {selectedFile.name}</span>
                  <span className="file-size">
                    ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                  </span>
                </>
              ) : (
                <>
                  <span className="upload-icon">⬆️</span>
                  <span>Choose video file or drag here</span>
                  <span className="file-hint">MP4, MOV, or AVI (max 100MB)</span>
                </>
              )}
            </label>
          </div>

          {error && (
            <div className="error-message">
              ⚠️ {error}
            </div>
          )}

          <div className="upload-actions">
            {selectedFile && !uploading && (
              <>
                <button 
                  className="upload-button primary"
                  onClick={handleUpload}
                >
                  🔍 Analyze Video
                </button>
                <button 
                  className="upload-button secondary"
                  onClick={handleReset}
                >
                  Clear
                </button>
              </>
            )}
          </div>

          {uploading && (
            <div className="uploading-state">
              <div className="spinner"></div>
              <p>Processing video... This may take a minute.</p>
              <p className="hint">Analyzing frames for deer detections</p>
            </div>
          )}
        </div>
      ) : (
        <div className="results-section">
          <div className="results-header">
            <h3>📊 Analysis Results</h3>
            <button className="upload-button secondary" onClick={handleReset}>
              Upload Another Video
            </button>
          </div>

          <div className="results-summary">
            <div className="summary-card">
              <div className="summary-label">Video Info</div>
              <div className="summary-value">
                <div>{results.filename}</div>
                <div className="meta">{results.fps.toFixed(1)} FPS • {results.total_frames} frames</div>
              </div>
            </div>
            
            <div className="summary-card">
              <div className="summary-label">Frames Analyzed</div>
              <div className="summary-value">{results.frames_processed}</div>
            </div>
            
            <div className={`summary-card ${results.frames_with_detections > 0 ? 'highlight' : ''}`}>
              <div className="summary-label">Detections Found</div>
              <div className="summary-value">
                {results.frames_with_detections > 0 ? (
                  <>
                    <span className="detection-count">✅ {results.total_deer_detected} deer</span>
                    <div className="meta">in {results.frames_with_detections} frames</div>
                  </>
                ) : (
                  <span className="no-detections">❌ No deer detected</span>
                )}
              </div>
            </div>
            
            {results.max_confidence > 0 && (
              <div className="summary-card">
                <div className="summary-label">Max Confidence</div>
                <div className="summary-value">{(results.max_confidence * 100).toFixed(1)}%</div>
              </div>
            )}
          </div>

          {results.frames_with_detections > 0 ? (
            <div className="detections-grid">
              <h4>Detected Frames</h4>
              {results.detections.map((detection, idx) => (
                <div key={idx} className="detection-result">
                  <div className="detection-info">
                    <div className="frame-number">Frame {detection.frame_number}</div>
                    <div className="timestamp">
                      {detection.timestamp_seconds.toFixed(1)}s
                    </div>
                    <div className="deer-count">
                      🦌 {detection.deer_count} deer detected
                    </div>
                  </div>
                  <div className="detection-image">
                    <img src={detection.annotated_image} alt={`Frame ${detection.frame_number}`} />
                  </div>
                  <div className="detection-details">
                    {detection.detections.map((det, i) => (
                      <div key={i} className="detection-item">
                        <span>Deer {i + 1}:</span>
                        <span className="confidence">{(det.confidence * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="no-detections-info">
              <h4>🔍 Diagnostic Information</h4>
              <p>No deer were detected in this video. This could mean:</p>
              <ul>
                <li>The deer were not in frame during sampled moments</li>
                <li>Lighting conditions made detection difficult</li>
                <li>Deer were too far away or partially obscured</li>
                <li>The ML model needs additional training for this scenario</li>
              </ul>
              <p className="hint">
                Consider extracting still frames from the video and uploading them 
                to the training dataset for model improvement.
              </p>
            </div>
          )}

          <div className="diagnostic-info">
            <details>
              <summary>🔧 Technical Details</summary>
              <div className="diagnostic-details">
                <p><strong>Sample Rate:</strong> {results.diagnostic_info.sample_rate} (processing ~2 frames/second)</p>
                <p><strong>Frames Sampled:</strong> {results.diagnostic_info.frames_sampled} of {results.total_frames}</p>
                <p><strong>Video FPS:</strong> {results.fps.toFixed(2)}</p>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoUpload
