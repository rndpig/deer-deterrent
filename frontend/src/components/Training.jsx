import { useState, useEffect } from 'react'
import './Training.css'

function Training() {
  const [detections, setDetections] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [trainingStats, setTrainingStats] = useState(null)
  const [filter, setFilter] = useState('unreviewed') // unreviewed, all, reviewed

  useEffect(() => {
    loadDetections()
    loadTrainingStats()
  }, [filter])

  const loadDetections = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setLoading(true)
    
    try {
      const response = await fetch(`${apiUrl}/api/detections?limit=200`)
      const data = await response.json()
      
      // Filter based on selection
      let filtered = data
      if (filter === 'unreviewed') {
        filtered = data.filter(d => !d.reviewed)
      } else if (filter === 'reviewed') {
        filtered = data.filter(d => d.reviewed)
      }
      
      setDetections(filtered)
      setCurrentIndex(0)
    } catch (error) {
      console.error('Error loading detections:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadTrainingStats = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    
    try {
      const response = await fetch(`${apiUrl}/api/training/stats`)
      if (response.ok) {
        const data = await response.json()
        setTrainingStats(data)
      }
    } catch (error) {
      console.error('Error loading training stats:', error)
    }
  }

  const reviewDetection = async (reviewType, correctedCount = null) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const detection = detections[currentIndex]
    
    if (!detection) return

    try {
      const payload = {
        detection_id: detection.id,
        review_type: reviewType,
        reviewer: 'user'
      }
      
      if (correctedCount !== null) {
        payload.corrected_deer_count = correctedCount
      }

      const response = await fetch(`${apiUrl}/api/detections/${detection.id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      if (response.ok) {
        // Mark as reviewed in local state
        const updated = [...detections]
        updated[currentIndex] = { ...detection, reviewed: true, review_type: reviewType }
        setDetections(updated)
        
        // Auto-advance to next unreviewed
        if (filter === 'unreviewed' && currentIndex < detections.length - 1) {
          setCurrentIndex(currentIndex + 1)
        }
        
        // Reload stats
        loadTrainingStats()
      }
    } catch (error) {
      console.error('Error reviewing detection:', error)
      alert('❌ Error submitting review')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'ArrowRight') nextDetection()
    if (e.key === 'ArrowLeft') previousDetection()
    if (e.key === '1') reviewDetection('correct')
    if (e.key === '2') reviewDetection('false_positive')
    if (e.key === '3') {
      const count = prompt('Enter correct deer count:')
      if (count) reviewDetection('incorrect_count', parseInt(count))
    }
  }

  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [currentIndex, detections])

  const nextDetection = () => {
    if (currentIndex < detections.length - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }

  const previousDetection = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  const exportAndSync = async () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    setSyncing(true)
    
    try {
      // Export
      const exportResponse = await fetch(`${apiUrl}/api/training/export`)
      if (!exportResponse.ok) throw new Error('Export failed')
      const exportData = await exportResponse.json()
      
      // Sync to Drive
      const syncResponse = await fetch(`${apiUrl}/api/training/sync-to-drive`, {
        method: 'POST'
      })
      if (!syncResponse.ok) throw new Error('Drive sync failed')
      const syncData = await syncResponse.json()
      
      alert(`✅ Success!\n\n📦 ${exportData.total_images} images exported\n☁️ Synced: ${syncData.version}\n\nReady for Google Colab training!`)
      
    } catch (error) {
      console.error('Error:', error)
      alert('❌ Error: ' + error.message)
    } finally {
      setSyncing(false)
    }
  }

  const currentDetection = detections[currentIndex]

  if (loading) {
    return (
      <div className="training-container">
        <div className="loading">Loading detections...</div>
      </div>
    )
  }

  return (
    <div className="training-container">
      <div className="training-header">
        <h1>🎓 Training Review</h1>
        
        {trainingStats && (
          <div className="training-progress">
            <div className="progress-stat">
              <span className="progress-label">Reviewed</span>
              <span className="progress-value">{trainingStats.reviewed_detections}</span>
            </div>
            <div className="progress-stat">
              <span className="progress-label">Correct</span>
              <span className="progress-value correct">{trainingStats.review_breakdown.correct}</span>
            </div>
            <div className="progress-stat">
              <span className="progress-label">False Positive</span>
              <span className="progress-value false">{trainingStats.review_breakdown.false_positive}</span>
            </div>
            <div className={`readiness-badge ${trainingStats.ready_for_training ? 'ready' : 'not-ready'}`}>
              {trainingStats.ready_for_training 
                ? '✅ Ready' 
                : `Need ${50 - trainingStats.reviewed_detections} more`
              }
            </div>
          </div>
        )}

        <div className="training-actions">
          <div className="filter-group">
            <button 
              className={filter === 'unreviewed' ? 'active' : ''}
              onClick={() => setFilter('unreviewed')}
            >
              Unreviewed ({detections.filter(d => !d.reviewed).length})
            </button>
            <button 
              className={filter === 'all' ? 'active' : ''}
              onClick={() => setFilter('all')}
            >
              All
            </button>
            <button 
              className={filter === 'reviewed' ? 'active' : ''}
              onClick={() => setFilter('reviewed')}
            >
              Reviewed ({detections.filter(d => d.reviewed).length})
            </button>
          </div>
          
          <button 
            className="sync-button"
            onClick={exportAndSync}
            disabled={syncing || !trainingStats?.ready_for_training}
          >
            {syncing ? '⏳ Syncing...' : '☁️ Export & Sync to Drive'}
          </button>
        </div>
      </div>

      {detections.length === 0 ? (
        <div className="empty-state">
          <h2>No detections to review</h2>
          <p>
            {filter === 'unreviewed' 
              ? 'All detections have been reviewed! 🎉'
              : 'No detections found. Wait for deer to be detected or load demo data.'
            }
          </p>
        </div>
      ) : (
        <div className="review-interface">
          <div className="image-viewer">
            <div className="navigation-controls">
              <button 
                onClick={previousDetection}
                disabled={currentIndex === 0}
                className="nav-button"
              >
                ← Previous
              </button>
              
              <span className="image-counter">
                {currentIndex + 1} / {detections.length}
              </span>
              
              <button 
                onClick={nextDetection}
                disabled={currentIndex === detections.length - 1}
                className="nav-button"
              >
                Next →
              </button>
            </div>

            {currentDetection && (
              <>
                <div className="image-container">
                  {currentDetection.image_path ? (
                    <img 
                      src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${currentDetection.image_path}`}
                      alt="Detection"
                      className="detection-image"
                    />
                  ) : (
                    <div className="no-image">
                      <p>📷 No image available</p>
                    </div>
                  )}
                </div>

                <div className="detection-info">
                  <div className="info-row">
                    <span className="info-label">Camera:</span>
                    <span className="info-value">{currentDetection.camera_name}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Zone:</span>
                    <span className="info-value">{currentDetection.zone_name}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Deer Count:</span>
                    <span className="info-value deer-count">🦌 {currentDetection.deer_count}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Confidence:</span>
                    <span className="info-value">{(currentDetection.max_confidence * 100).toFixed(1)}%</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">Time:</span>
                    <span className="info-value">{new Date(currentDetection.timestamp).toLocaleString()}</span>
                  </div>
                  {currentDetection.reviewed && (
                    <div className="info-row reviewed-status">
                      <span className="info-label">Status:</span>
                      <span className="info-value reviewed">
                        ✓ Reviewed as {currentDetection.review_type}
                      </span>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="review-panel">
            <h2>Review This Detection</h2>
            
            <div className="review-buttons-large">
              <button 
                className="review-button correct"
                onClick={() => reviewDetection('correct')}
                disabled={currentDetection?.reviewed}
              >
                <div className="button-icon">✓</div>
                <div className="button-label">Correct</div>
                <div className="button-hint">Keyboard: 1</div>
              </button>
              
              <button 
                className="review-button false-positive"
                onClick={() => reviewDetection('false_positive')}
                disabled={currentDetection?.reviewed}
              >
                <div className="button-icon">✗</div>
                <div className="button-label">False Positive</div>
                <div className="button-hint">Keyboard: 2</div>
              </button>
              
              <button 
                className="review-button incorrect-count"
                onClick={() => {
                  const count = prompt('Enter correct deer count:')
                  if (count) reviewDetection('incorrect_count', parseInt(count))
                }}
                disabled={currentDetection?.reviewed}
              >
                <div className="button-icon">#</div>
                <div className="button-label">Wrong Count</div>
                <div className="button-hint">Keyboard: 3</div>
              </button>
            </div>

            <div className="keyboard-shortcuts">
              <h3>⌨️ Keyboard Shortcuts</h3>
              <div className="shortcut-list">
                <div className="shortcut">
                  <kbd>←</kbd> <kbd>→</kbd> <span>Navigate</span>
                </div>
                <div className="shortcut">
                  <kbd>1</kbd> <span>Mark Correct</span>
                </div>
                <div className="shortcut">
                  <kbd>2</kbd> <span>False Positive</span>
                </div>
                <div className="shortcut">
                  <kbd>3</kbd> <span>Wrong Count</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Training
