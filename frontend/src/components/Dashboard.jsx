import { useState, useEffect } from 'react'
import './Dashboard.css'
import BoundingBoxImage from './BoundingBoxImage'
import AnnotationTool from './AnnotationTool'
import { apiFetch, API_URL } from '../api'

function Dashboard({ stats, settings }) {
  const [snapshots, setSnapshots] = useState([])
  const [allDeerSnapshots, setAllDeerSnapshots] = useState([]) // all deer detections (all-time) for accurate stats
  const [chaseVideoMap, setChaseVideoMap] = useState({}) // { [event_id]: video_id } — events with chase recordings
  const [loading, setLoading] = useState(true)
  const [timeFilter, setTimeFilter] = useState('lastCycle') // lastCycle, last7d, all
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(99) // 99 = 33 rows × 3 cards (no orphans)
  const [feedbackFilter, setFeedbackFilter] = useState('with_deer') // all, with_deer, without_deer
  const [cameraFilter, setCameraFilter] = useState('all') // all, or specific camera ID
  const [jumpHour, setJumpHour] = useState('') // hour-of-day for jump-to filter (string for select)
  const [jumpMinute, setJumpMinute] = useState('') // minute (5-min granularity)
  const [selectedSnapshot, setSelectedSnapshot] = useState(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedCamera, setSelectedCamera] = useState('side')
  const [captureDateTime, setCaptureDateTime] = useState('')
  const [showAnnotationTool, setShowAnnotationTool] = useState(false)

  // Camera ID to name mapping
  const CAMERA_NAMES = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door',
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Woods',
    'c4dbad08f862': 'Side',
    'manual_upload': 'Manual Upload'
  }
    const formatCameraName = (cameraId) => {
    return CAMERA_NAMES[cameraId] || cameraId
  }
    const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const year = date.getFullYear()
    let hours = date.getHours()
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const ampm = hours >= 12 ? 'PM' : 'AM'
    hours = hours % 12 || 12
    
    return `${month}/${day}/${year} ${hours}:${minutes} ${ampm}`
  }

  useEffect(() => {
    loadSnapshots()
    setCurrentPage(1) // Reset to page 1 when filters change
  }, [timeFilter, feedbackFilter, cameraFilter])

  // Listen for upload modal trigger from header
  useEffect(() => {
    const handleShowUpload = () => setShowUploadModal(true)
    window.addEventListener('show-upload-modal', handleShowUpload)
    return () => window.removeEventListener('show-upload-modal', handleShowUpload)
  }, [])

  // Compute the [start, end) datetime range for the "most recent" active-hours cycle.
  // Returns null when no cycle bounds apply (e.g. timeFilter !== 'lastCycle').
  const getMostRecentCycleRange = () => {
    const cycleStartHour = settings?.active_hours_start ?? 20
    const cycleEndHour = settings?.active_hours_end ?? 6
    const cycleLengthHours = ((cycleEndHour - cycleStartHour + 24) % 24) || 24
    const now = new Date()

    // Start with today's cycle-start datetime, walk back if it's still in the future.
    let cycleStartDate = new Date(now)
    cycleStartDate.setHours(cycleStartHour, 0, 0, 0)
    if (cycleStartDate > now) {
      cycleStartDate.setDate(cycleStartDate.getDate() - 1)
    }

    // If we're less than halfway through the current cycle, fall back to the previous
    // (fully-completed) cycle so users see last night's data instead of an empty page.
    const elapsedHours = (now - cycleStartDate) / 3600000
    if (elapsedHours < cycleLengthHours / 2) {
      cycleStartDate = new Date(cycleStartDate.getTime() - 24 * 3600000)
    }

    const cycleEndDate = new Date(cycleStartDate.getTime() + cycleLengthHours * 3600000)
    return { start: cycleStartDate, end: cycleEndDate }
  }

  const loadSnapshots = async () => {
    setLoading(true)
      try {
      // Build server-side filter params
      const displayParams = new URLSearchParams({ limit: '5000' })
      const deerParams = new URLSearchParams({ limit: '50000', with_deer: 'true' })

      if (feedbackFilter === 'with_deer') displayParams.set('with_deer', 'true')
      else if (feedbackFilter === 'without_deer') displayParams.set('with_deer', 'false')

      if (cameraFilter !== 'all') {
        displayParams.set('camera_id', cameraFilter)
        deerParams.set('camera_id', cameraFilter)
      }

      let cycleRange = null
      if (timeFilter !== 'all') {
        let hours = 168
        if (timeFilter === 'lastCycle') {
          cycleRange = getMostRecentCycleRange()
          // Fetch a generous window from the server — we trim to exact cycle bounds below.
          const now = new Date()
          hours = Math.ceil((now - cycleRange.start) / 3600000) + 1
        }
        displayParams.set('time_hours', String(hours))
      }
        const [displayRes, deerRes, chaseRes] = await Promise.all([
        apiFetch(`/api/snapshots?${displayParams}`),
        apiFetch(`/api/snapshots?${deerParams}`),
        apiFetch('/api/chase-videos')
      ])

      if (!displayRes.ok) throw new Error(`HTTP ${displayRes.status}: ${displayRes.statusText}`)
      if (!deerRes.ok) throw new Error(`Deer fetch HTTP ${deerRes.status}: ${deerRes.statusText}`)

      const [displayData, deerData] = await Promise.all([displayRes.json(), deerRes.json()])
      if (chaseRes.ok) {
        try {
          const chaseData = await chaseRes.json()
          setChaseVideoMap(chaseData.mapping || {})
        } catch { /* non-fatal */ }
      }

      let displaySnapshots = displayData.snapshots || []
      if (cycleRange) {
        const startMs = cycleRange.start.getTime()
        const endMs = cycleRange.end.getTime()
        displaySnapshots = displaySnapshots.filter(s => {
          const t = new Date(s.timestamp).getTime()
          return t >= startMs && t < endMs
        })
      }

      setAllDeerSnapshots(deerData.snapshots || [])
      setSnapshots(displaySnapshots)
      setCurrentPage(1)
    } catch (error) {
      console.error('Error loading snapshots:', error)
      alert(`Failed to load snapshots: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  // Build the list of hours that fall within the configured active-hours window.
  // Wraps across midnight when start > end (e.g. 20 → 6).
  const activeHourOptions = (() => {
    const start = settings?.active_hours_start ?? 20
    const end = settings?.active_hours_end ?? 6
    const out = []
    let h = start
    // length includes start, excludes end (matches "between start and end" intent)
    const length = ((end - start + 24) % 24) || 24
    for (let i = 0; i < length; i++) {
      out.push(h % 24)
      h++
    }
    return out
  })()

  // Format a 0-23 hour value as a 12-hour clock label with AM/PM (e.g. 0 -> "12 AM", 20 -> "8 PM").
  const formatHour12 = (h) => {
    const hour = Number(h)
    const period = hour < 12 ? 'AM' : 'PM'
    const display = hour % 12 === 0 ? 12 : hour % 12
    return `${display} ${period}`
  }

  // Auto-jump to the snapshot nearest to the chosen hour:minute (within currently-loaded snapshots).
  // Navigates to the page containing the matching card and scrolls/flashes it (does NOT open the modal).
  const jumpToHourMinute = (h, m) => {
    if (h === '' || m === '' || snapshots.length === 0) return
    const targetMin = Number(h) * 60 + Number(m)
    let bestIdx = 0
    let bestDelta = Infinity
    for (let i = 0; i < snapshots.length; i++) {
      const d = new Date(snapshots[i].timestamp)
      const sm = d.getHours() * 60 + d.getMinutes()
      // circular distance on a 24h clock so 23:55 vs 00:05 = 10 min
      let delta = Math.abs(sm - targetMin)
      if (delta > 720) delta = 1440 - delta
      if (delta < bestDelta) {
        bestDelta = delta
        bestIdx = i
      }
    }
    const page = Math.floor(bestIdx / itemsPerPage) + 1
    const targetId = snapshots[bestIdx].id
    setCurrentPage(page)
    // Wait for the page to render, then scroll to the card and highlight it briefly.
    setTimeout(() => {
      const el = document.querySelector(`[data-snapshot-id="${targetId}"]`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        el.classList.add('snapshot-jump-highlight')
        setTimeout(() => el.classList.remove('snapshot-jump-highlight'), 2200)
      }
    }, 80)
  }

    const handleUploadImage = async () => {
    if (!selectedFile) {
      setUploadResult({ success: false, message: 'Please select an image file' })
      return
    }
      if (!captureDateTime) {
      setUploadResult({ success: false, message: 'Please enter the date/time when the photo was captured' })
      return
    }

    setUploadingImage(true)
    setUploadResult(null)
      try {
         const formData = new FormData()
      formData.append('image', selectedFile)
      formData.append('threshold', settings?.detection_threshold || 0.75)
      formData.append('save_to_database', 'true')
      formData.append('camera_id', selectedCamera === 'side' ? 'c4dbad08f862' : '587a624d3fae')
      formData.append('captured_at', captureDateTime)

      const response = await apiFetch('/api/test-detection', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) throw new Error('Detection failed')

      const result = await response.json()
      setUploadResult({
        success: true,
        deerDetected: result.deer_detected,
        confidence: result.max_confidence,
        message: result.deer_detected 
          ? `✅ Deer detected! Confidence: ${(result.max_confidence * 100).toFixed(1)}%`
          : `❌ No deer detected (max confidence: ${(result.max_confidence * 100).toFixed(1)}%)`
      })

      // Reload snapshots
      if (result.saved_event_id) {
        await loadSnapshots()
        setSelectedFile(null)
      }
    } catch (error) {
      console.error('Error testing image:', error)
      setUploadResult({ success: false, message: '❌ Error: ' + error.message })
    } finally {
      setUploadingImage(false)
    }
  }
    const updateSnapshotFeedback = async (snapshotId, hasDeer) => {
    try {
         const response = await apiFetch(`/api/ring-events/${snapshotId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deer_detected: hasDeer ? 1 : 0, false_positive: hasDeer ? 0 : 1 })
      })

      if (response.ok) {
        // Close modal
        setSelectedSnapshot(null)
        // Reload snapshots to reflect the change
        loadSnapshots()
      }
    } catch (error) {
      console.error('Error updating feedback:', error)
    }
  }

  // Convert stored bboxes ({bbox: {x1,y1,x2,y2}}) to AnnotationTool format ({x,y,width,height} normalized 0-1)
  const bboxesToAnnotationFormat = (bboxes, imgWidth, imgHeight) => {
    if (!bboxes || !imgWidth || !imgHeight) return []
    return bboxes.map(d => {
      const b = d.bbox
      if (!b || b.x1 === undefined) return null
      return {
        x: b.x1 / imgWidth,
        y: b.y1 / imgHeight,
        width: (b.x2 - b.x1) / imgWidth,
        height: (b.y2 - b.y1) / imgHeight,
        confidence: d.confidence  // preserve original model confidence
      }
    }).filter(Boolean)
  }

  // Convert AnnotationTool format back to stored bbox format
  const annotationToBboxFormat = (normalizedBoxes, imgWidth, imgHeight) => {
    return normalizedBoxes.map(b => ({
      bbox: {
        x1: Math.round(b.x * imgWidth * 100) / 100,
        y1: Math.round(b.y * imgHeight * 100) / 100,
        x2: Math.round((b.x + b.width) * imgWidth * 100) / 100,
        y2: Math.round((b.y + b.height) * imgHeight * 100) / 100
      },
      confidence: b.confidence ?? null  // preserve original, null for manual
    }))
  }
    const handleOpenAnnotation = () => {
    setShowAnnotationTool(true)
  }
    const handleSaveAnnotation = async (normalizedBoxes) => {
    if (!selectedSnapshot) return

    // Ring snapshots are 640x360
    const bboxes = annotationToBboxFormat(normalizedBoxes, 640, 360)
       try {
         const response = await apiFetch(`/api/snapshots/${selectedSnapshot.id}/bboxes`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ detection_bboxes: bboxes })
      })

      if (response.ok) {
        // Update local state so bboxes show immediately
        const updated = { ...selectedSnapshot, detection_bboxes: bboxes, deer_detected: 1 }
        setSelectedSnapshot(updated)
        const updateSnapshot = s =>
          s.id === selectedSnapshot.id ? { ...s, detection_bboxes: bboxes, deer_detected: 1 } : s
        setSnapshots(prev => prev.map(updateSnapshot))
        setAllDeerSnapshots(prev => prev.map(updateSnapshot))

        // Also mark as deer in backend (drawing bboxes implies deer present)
        await apiFetch(`/api/ring-events/${selectedSnapshot.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ deer_detected: 1 })
        })
      } else {
        console.error('Failed to save bboxes:', response.status)
      }
    } catch (error) {
      console.error('Error saving annotations:', error)
    }

    setShowAnnotationTool(false)
    setSelectedSnapshot(null) // Return directly to dashboard
  }

  // Stats computed from ALL deer snapshots (separate fetch, not limited by display window)
  // Stats computed from displayed snapshots (server-side filtered)
  // This ensures the count matches what's actually shown on screen
  const displayedDeerSnapshots = snapshots.filter(s => s.deer_detected)
  const deerCount = displayedDeerSnapshots.length

  // Total number of deer (sum of all bboxes across filtered snapshots)
  const totalDeerCount = displayedDeerSnapshots.reduce((sum, s) => sum + (s.detection_bboxes?.length || 0), 0)

  // For other stats, use displayed deer snapshots (time-filtered by server)
  const timeFilteredDeer = displayedDeerSnapshots

  // Detections this month (from all deer data, not affected by time filter)
  const now = new Date()
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  const thisMonthCount = allDeerSnapshots.filter(s => new Date(s.timestamp) >= monthStart).length

  // Mean sighting hour (circular mean to handle midnight crossing)
  const meanSightingTime = (() => {
    if (timeFilteredDeer.length === 0) return null
    let sinSum = 0, cosSum = 0
    for (const s of timeFilteredDeer) {
      const d = new Date(s.timestamp)
      const fractionalHour = d.getHours() + d.getMinutes() / 60
      const angle = (fractionalHour / 24) * 2 * Math.PI
      sinSum += Math.sin(angle)
      cosSum += Math.cos(angle)
    }
     let meanAngle = Math.atan2(sinSum / timeFilteredDeer.length, cosSum / timeFilteredDeer.length)
    if (meanAngle < 0) meanAngle += 2 * Math.PI
    const meanHourFrac = (meanAngle / (2 * Math.PI)) * 24
    const avgHours = Math.floor(meanHourFrac)
    const avgMins = Math.round((meanHourFrac - avgHours) * 60)
    const ampm = avgHours >= 12 ? 'PM' : 'AM'
    const displayHour = avgHours % 12 || 12
    return `${displayHour}:${String(avgMins).padStart(2, '0')} ${ampm}`
  })()

  // Most recent detection
  const lastDetection = timeFilteredDeer.length > 0
    ? formatTimestamp(timeFilteredDeer.reduce((latest, s) =>
        new Date(s.timestamp) > new Date(latest.timestamp) ? s : latest
      ).timestamp)
    : null

  // Average confidence (exclude manual-only detections with 0% confidence)
  const avgConfidence = (() => {
    const withConf = timeFilteredDeer.filter(s => s.detection_confidence > 0)
    if (withConf.length === 0) return null
    const avg = withConf.reduce((sum, s) => sum + s.detection_confidence, 0) / withConf.length
    return `${(avg * 100).toFixed(0)}%`
  })()

  // Irrigation this month
  const irrigationThisMonth = allDeerSnapshots.filter(s => s.irrigation_activated && new Date(s.timestamp) >= monthStart).length

  return (
    <div className="dashboard">
      {/* Compact stats bar - stacked on mobile, horizontal on desktop */}
      <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-6 px-4 md:px-6 py-3 border-b border-white/10">
        {/* Row 1: Primary stats (green numbers) */}
        <div className="flex items-center gap-4 md:gap-6">
          {/* Snapshots with deer */}
          <div className="flex items-center gap-2">
            <span className="text-3xl font-bold text-green-400">{deerCount}</span>
            <div className="flex flex-col text-xs uppercase tracking-wide text-white/50 leading-tight">
              <span>snapshots with</span>
              <span>deer detected</span>
            </div>
          </div>

          {/* Divider */}
          <div className="w-px h-8 bg-white/15 shrink-0" />

          {/* Total deer count (bbox count) */}
          <div className="flex items-center gap-2">
            <span className="text-3xl font-bold text-green-400">{totalDeerCount}</span>
            <div className="flex flex-col text-xs uppercase tracking-wide text-white/50 leading-tight">
              <span>number of</span>
              <span>deer detected</span>
            </div>
          </div>

          {/* Divider - desktop only */}
          <div className="hidden md:block w-px h-8 bg-white/15 shrink-0" />
        </div>

        {/* Row 2 (mobile) / continues inline (desktop): This Month + Avg Time */}
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="text-white/40 text-xs">This Month</span>
            <span className="font-semibold text-green-400">🦌 {thisMonthCount}</span>
            <span className="font-semibold text-blue-400">💦 {irrigationThisMonth}</span>
          </div>
          {meanSightingTime && (
            <div className="flex items-center gap-1.5">
              <span className="text-white/40 text-xs">Avg Time</span>
              <span className="font-semibold text-white/90">{meanSightingTime}</span>
            </div>
          )}
        </div>

        {/* Row 3 (mobile) / continues inline (desktop): Avg Conf + Latest */}
        <div className="flex items-center gap-4 text-sm">
          {avgConfidence && (
            <div className="flex items-center gap-1.5">
              <span className="text-white/40 text-xs">Avg Conf</span>
              <span className="font-semibold text-white/90">{avgConfidence}</span>
            </div>
          )}
          {lastDetection && (
            <div className="flex items-center gap-1.5">
              <span className="text-white/40 text-xs">Latest</span>
              <span className="font-semibold text-white/90">{lastDetection}</span>
            </div>
          )}
        </div>
      </div>

      {/* Filter controls */}
      <div className="snapshot-controls">
        <div className="filter-section">
          <label className="filter-label">Time:</label>
          <div className="filter-buttons">
            <button
              className={timeFilter === 'lastCycle' ? 'active' : ''}
              onClick={() => setTimeFilter('lastCycle')}
            >
              Last Cycle
            </button>
            <button
              className={timeFilter === 'last7d' ? 'active' : ''}
              onClick={() => setTimeFilter('last7d')}
            >
              Last 7d
            </button>
            <button
              className={timeFilter === 'all' ? 'active' : ''}
              onClick={() => setTimeFilter('all')}
            >
              All Time
            </button>
          </div>
        </div>
        
        <div className="filter-section">
          <label className="filter-label">Show:</label>
          <div className="filter-buttons">
            <button
              className={feedbackFilter === 'with_deer' ? 'active' : ''}
              onClick={() => setFeedbackFilter('with_deer')}
            >
              🦌 Deer
            </button>
            <button
              className={feedbackFilter === 'without_deer' ? 'active' : ''}
              onClick={() => setFeedbackFilter('without_deer')}
            >
              No Deer
            </button>
          </div>
        </div>

        <div className="filter-row-camera-jump">
          <div className="filter-section">
            <label className="filter-label">Camera:</label>
            <div className="camera-select-wrapper">
              <select
                className="camera-select"
                value={cameraFilter}
                onChange={(e) => setCameraFilter(e.target.value)}
              >
                <option value="all">All Cameras</option>
                <option value="10cea9e4511f">Woods</option>
                <option value="c4dbad08f862">Side</option>
                <option value="587a624d3fae">Driveway</option>
                <option value="4439c4de7a79">Front Door</option>
                <option value="f045dae9383a">Back</option>
              </select>
              <span className="camera-select-arrow">▾</span>
            </div>
          </div>

          <div className="filter-section filter-section-jump">
            <label className="filter-label">Jump:</label>
            <div className="jump-controls">
              <select
                className="jump-select"
                value={jumpHour}
                onChange={(e) => { setJumpHour(e.target.value); jumpToHourMinute(e.target.value, jumpMinute) }}
                title="Hour"
              >
                <option value="">HH</option>
                {activeHourOptions.map(h => (
                  <option key={h} value={h}>{formatHour12(h)}</option>
                ))}
              </select>
              <span className="jump-colon">:</span>
              <select
                className="jump-select"
                value={jumpMinute}
                onChange={(e) => { setJumpMinute(e.target.value); jumpToHourMinute(jumpHour, e.target.value) }}
                title="Minute"
              >
                <option value="">MM</option>
                {Array.from({ length: 12 }, (_, i) => i * 5).map(m => (
                  <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Snapshot Grid */}
      {loading ? (
        <div className="loading">Loading snapshots...</div>
      ) : snapshots.length === 0 ? (
        <div className="empty-state">
          <h3>📸 No Snapshots Found</h3>
        </div>
      ) : (
        <>
          <div className="snapshot-grid">
            {snapshots.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage).map((snapshot) => (
            <div
              key={snapshot.id}
              data-snapshot-id={snapshot.id}
              className={`snapshot-card ${snapshot.deer_detected ? 'with-deer' : ''}`}
              onClick={() => setSelectedSnapshot(snapshot)}
            >
              <div className="snapshot-thumbnail">
                <BoundingBoxImage
                  src={`${API_URL}/api/snapshots/${snapshot.id}/image`}
                  alt={`Snapshot ${snapshot.id}`}
                  detections={(snapshot.detection_bboxes?.length || 0) > 0 ? snapshot.detection_bboxes : null}
                  className="snapshot-img"
                />
                {!!snapshot.deer_detected && (snapshot.detection_bboxes?.length || 0) > 0 && (
                  <div className="deer-count-badge">
                    🦌 {snapshot.detection_bboxes.length}
                  </div>
                )}
                {!!snapshot.irrigation_activated && (
                  <div className="irrigation-badge">
                    💦
                  </div>
                )}
                {chaseVideoMap[String(snapshot.id)] && (
                  <div
                    className="chase-video-badge"
                    title="Chase recording available — click to open in Videos tab"
                    onClick={(e) => {
                      e.stopPropagation()
                      const videoId = chaseVideoMap[String(snapshot.id)]
                      try {
                        sessionStorage.setItem('focusVideoId', String(videoId))
                      } catch { /* ignore */ }
                      window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'videos', videoId } }))
                    }}
                  >
                    🎬
                  </div>
                )}
              </div>
              <div className="snapshot-info">
                <div className="snapshot-meta">
                  <span className="snapshot-id">#{snapshot.id}</span>
                  <span className="snapshot-camera">
                    {formatCameraName(snapshot.camera_id)}
                  </span>
                  <span className="snapshot-time">{formatTimestamp(snapshot.timestamp)}</span>
                  {snapshot.detection_confidence !== null && (
                    <span className="snapshot-confidence">
                      {(snapshot.detection_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {/* Pagination Controls */}
        {snapshots.length > itemsPerPage && (
          <div className="pagination-controls">
            <button 
              onClick={() => { setCurrentPage(currentPage - 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }} 
              disabled={currentPage === 1}
            >
              « Prev
            </button>
            <button 
              onClick={() => { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }}
            >
              ↓ Bottom
            </button>
            <span className="page-indicator">
              Page {currentPage} of {Math.ceil(snapshots.length / itemsPerPage)}
            </span>
            <button 
              onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); }}
            >
              ↑ Top
            </button>
            <button 
              onClick={() => { setCurrentPage(currentPage + 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }} 
              disabled={currentPage >= Math.ceil(snapshots.length / itemsPerPage)}
            >
              Next »
            </button>
          </div>
        )}
        </>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
          <div className="upload-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setShowUploadModal(false)} 
              className="btn-close-modal"
            >
              ✕
            </button>
            <h2>📤 Upload Image</h2>
            <div className="upload-form">
              <div className="form-group">
                <label>Select Image:</label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setSelectedFile(e.target.files[0])}
                />
              </div>
              <div className="form-group">
                <label>Camera:</label>
                <select
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(e.target.value)}
                >
                  <option value="side">Side</option>
                  <option value="driveway">Driveway</option>
                </select>
              </div>
              <div className="form-group">
                <label>Capture Date/Time:</label>
                <input
                  type="datetime-local"
                  value={captureDateTime}
                  onChange={(e) => setCaptureDateTime(e.target.value)}
                />
              </div>
              {uploadResult && (
                <div className={`upload-result ${uploadResult.success ? 'success' : 'error'}`}>
                  {uploadResult.message}
                </div>
              )}
              <div className="modal-actions">
                <button
                  onClick={handleUploadImage}
                  disabled={uploadingImage || !selectedFile}
                  className="btn-primary"
                >
                  {uploadingImage ? 'Uploading...' : 'Upload & Detect'}
                </button>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Snapshot Detail Modal */}
      {selectedSnapshot && (
        <div className="modal-overlay" onClick={() => setSelectedSnapshot(null)}>
          <div className="image-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              onClick={() => setSelectedSnapshot(null)} 
              className="btn-close-modal"
            >
              ✕
            </button>
            <div className="modal-content">
              <div className="modal-image-wrapper">
                <BoundingBoxImage
                  src={`${API_URL}/api/snapshots/${selectedSnapshot.id}/image`}
                  alt="Snapshot"
                  detections={(selectedSnapshot.detection_bboxes?.length || 0) > 0 ? selectedSnapshot.detection_bboxes : null}
                  className="modal-img"
                />
              </div>
              <div className="modal-sidebar">
                <div className="modal-meta">
                  <div className="meta-row">
                    <span className="meta-label">ID</span>
                    <span className="meta-value">#{selectedSnapshot.id}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Camera</span>
                    <span className="meta-value">{formatCameraName(selectedSnapshot.camera_id)}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Confidence</span>
                    <span className="meta-value">
                      {selectedSnapshot.detection_confidence !== null
                        ? `${(selectedSnapshot.detection_confidence * 100).toFixed(0)}%`
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Time</span>
                    <span className="meta-value">{new Date(selectedSnapshot.timestamp).toLocaleString()}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Model</span>
                    <span className="meta-value">{selectedSnapshot.model_version || 'Unknown'}</span>
                  </div>
                  {(selectedSnapshot.detection_bboxes?.length || 0) > 0 && (
                    <div className="meta-row">
                      <span className="meta-label">Detections</span>
                      <span className="meta-value">🦌 {selectedSnapshot.detection_bboxes.length}</span>
                    </div>
                  )}
                  {!!selectedSnapshot.irrigation_activated && (
                    <div className="meta-row">
                      <span className="meta-label">Irrigation</span>
                      <span className="meta-value irrigation-fired">💦 Activated</span>
                    </div>
                  )}
                </div>
                <div className="modal-actions-section">
                  <button
                    className={`btn-feedback ${selectedSnapshot.deer_detected ? 'active' : ''}`}
                    onClick={() => updateSnapshotFeedback(selectedSnapshot.id, true)}
                  >
                    ✅ Deer
                  </button>
                  <button
                    className={`btn-feedback ${!selectedSnapshot.deer_detected ? 'active' : ''}`}
                    onClick={() => updateSnapshotFeedback(selectedSnapshot.id, false)}
                  >
                    ❌ False Positive
                  </button>
                  <button
                    className="btn-annotate"
                    onClick={handleOpenAnnotation}
                  >
                    ✏️ Draw Boxes
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Annotation Tool Modal */}
      {showAnnotationTool && selectedSnapshot && (
        <AnnotationTool
          imageSrc={`${API_URL}/api/snapshots/${selectedSnapshot.id}/image`}
          existingBoxes={bboxesToAnnotationFormat(
            selectedSnapshot.detection_bboxes,
            640, 360
          )}
          onSave={handleSaveAnnotation}
          onCancel={() => setShowAnnotationTool(false)}
        />
      )}
    </div>
  )
}

export default Dashboard


