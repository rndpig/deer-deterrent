import { useState, useEffect } from 'react'
import './SnapshotViewer.css'

function SnapshotViewer() {
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // 'all', 'with_deer', 'without_deer'
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [detectionRunning, setDetectionRunning] = useState(false)
  const [threshold, setThreshold] = useState(0.15)

  const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'

  useEffect(() => {
    loadSnapshots()
  }, [filter])

  const loadSnapshots = async () => {
    setLoading(true)
    try {
      let url = `${apiUrl}/api/ring-snapshots?limit=100`
      if (filter === 'with_deer') {
        url += '&with_deer=true'
      } else if (filter === 'without_deer') {
        url += '&with_deer=false'
      }

      const response = await fetch(url)
      if (!response.ok) throw new Error('Failed to load snapshots')

      const data = await response.json()
      setSnapshots(data.snapshots)
    } catch (error) {
      console.error('Error loading snapshots:', error)
      alert(`Failed to load snapshots: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const selectSnapshot = (snapshot) => {
    setSelectedSnapshot(snapshot)
  }

  const rerunDetection = async () => {
    if (!selectedSnapshot) return

    setDetectionRunning(true)
    try {
      const response = await fetch(
        `${apiUrl}/api/ring-snapshots/${selectedSnapshot.id}/rerun-detection?threshold=${threshold}`,
        { method: 'POST' }
      )

      if (!response.ok) throw new Error('Detection failed')

      const result = await response.json()

      // Update the selected snapshot with new results
      setSelectedSnapshot({
        ...selectedSnapshot,
        deer_detected: result.deer_detected,
        detection_confidence: result.max_confidence,
        detection_result: result
      })

      // Update in list
      setSnapshots(snapshots.map(s =>
        s.id === selectedSnapshot.id
          ? { ...s, deer_detected: result.deer_detected, detection_confidence: result.max_confidence }
          : s
      ))

      alert(`Detection complete! ${result.deer_detected ? 'Deer detected' : 'No deer'} (confidence: ${(result.max_confidence * 100).toFixed(1)}%)`)
    } catch (error) {
      console.error('Error running detection:', error)
      alert(`Detection failed: ${error.message}`)
    } finally {
      setDetectionRunning(false)
    }
  }

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    return date.toLocaleString()
  }

  if (loading) {
    return (
      <div className="snapshot-viewer">
        <div className="loading">Loading snapshots...</div>
      </div>
    )
  }

  if (snapshots.length === 0) {
    return (
      <div className="snapshot-viewer">
        <div className="empty-state">
          <h3>📸 No Snapshots Found</h3>
          <p>Snapshots will appear here as motion events are detected.</p>
          <p>The coordinator must be running with snapshot-saving enabled.</p>
          <button onClick={loadSnapshots} className="btn-reload">
            🔄 Reload
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="snapshot-viewer">
      <div className="snapshot-header">
        <h2>📸 Ring Snapshots ({snapshots.length})</h2>
        <div className="snapshot-filters">
          <button
            className={filter === 'all' ? 'active' : ''}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            className={filter === 'with_deer' ? 'active' : ''}
            onClick={() => setFilter('with_deer')}
          >
            With Deer
          </button>
          <button
            className={filter === 'without_deer' ? 'active' : ''}
            onClick={() => setFilter('without_deer')}
          >
            No Deer
          </button>
        </div>
      </div>

      <div className="snapshot-content">
        <div className="snapshot-grid">
          {snapshots.map((snapshot) => (
            <div
              key={snapshot.id}
              className={`snapshot-card ${selectedSnapshot?.id === snapshot.id ? 'selected' : ''} ${snapshot.deer_detected ? 'with-deer' : ''}`}
              onClick={() => selectSnapshot(snapshot)}
            >
              <div className="snapshot-thumbnail">
                <img
                  src={`${apiUrl}/api/ring-snapshots/${snapshot.id}/image`}
                  alt={`Snapshot ${snapshot.id}`}
                  loading="lazy"
                />
                {snapshot.deer_detected && (
                  <div className="deer-badge">🦌 Deer</div>
                )}
                {snapshot.detection_confidence && (
                  <div className="confidence-badge">
                    {(snapshot.detection_confidence * 100).toFixed(0)}%
                  </div>
                )}
              </div>
              <div className="snapshot-info">
                <div className="snapshot-camera">{snapshot.camera_id}</div>
                <div className="snapshot-time">{formatTimestamp(snapshot.timestamp)}</div>
                <div className="snapshot-size">
                  {snapshot.snapshot_size ? `${(snapshot.snapshot_size / 1024).toFixed(1)} KB` : 'Unknown size'}
                </div>
              </div>
            </div>
          ))}
        </div>

        {selectedSnapshot && (
          <div className="snapshot-detail">
            <div className="detail-header">
              <h3>Snapshot Details</h3>
              <button onClick={() => setSelectedSnapshot(null)} className="btn-close">
                ✕
              </button>
            </div>

            <div className="detail-image">
              <img
                src={`${apiUrl}/api/ring-snapshots/${selectedSnapshot.id}/image`}
                alt={`Snapshot ${selectedSnapshot.id}`}
              />
              {selectedSnapshot.detection_result?.detections?.map((det, idx) => (
                <div
                  key={idx}
                  className="detection-box"
                  style={{
                    left: `${det.bbox.x1}px`,
                    top: `${det.bbox.y1}px`,
                    width: `${det.bbox.x2 - det.bbox.x1}px`,
                    height: `${det.bbox.y2 - det.bbox.y1}px`
                  }}
                >
                  <span className="detection-label">
                    {(det.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>

            <div className="detail-info">
              <div className="info-row">
                <span className="label">Event ID:</span>
                <span className="value">#{selectedSnapshot.id}</span>
              </div>
              <div className="info-row">
                <span className="label">Camera:</span>
                <span className="value">{selectedSnapshot.camera_id}</span>
              </div>
              <div className="info-row">
                <span className="label">Timestamp:</span>
                <span className="value">{formatTimestamp(selectedSnapshot.timestamp)}</span>
              </div>
              <div className="info-row">
                <span className="label">Deer Detected:</span>
                <span className={`value ${selectedSnapshot.deer_detected ? 'detected' : 'not-detected'}`}>
                  {selectedSnapshot.deer_detected ? '✓ Yes' : '✗ No'}
                </span>
              </div>
              {selectedSnapshot.detection_confidence && (
                <div className="info-row">
                  <span className="label">Confidence:</span>
                  <span className="value">{(selectedSnapshot.detection_confidence * 100).toFixed(1)}%</span>
                </div>
              )}
              <div className="info-row">
                <span className="label">File Size:</span>
                <span className="value">
                  {selectedSnapshot.snapshot_size ? `${(selectedSnapshot.snapshot_size / 1024).toFixed(1)} KB` : 'Unknown'}
                </span>
              </div>
            </div>

            <div className="detail-actions">
              <h4>Re-run Detection</h4>
              <div className="threshold-control">
                <label>
                  Confidence Threshold: {threshold.toFixed(2)}
                  <input
                    type="range"
                    min="0.10"
                    max="0.50"
                    step="0.05"
                    value={threshold}
                    onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  />
                </label>
              </div>
              <button
                onClick={rerunDetection}
                disabled={detectionRunning}
                className="btn-rerun"
              >
                {detectionRunning ? '⏳ Running...' : '🔍 Run Detection'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SnapshotViewer
