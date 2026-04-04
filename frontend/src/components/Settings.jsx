import { useState, useEffect } from 'react'
import './Settings.css'
import { apiFetch, API_URL } from '../api'

function Settings({ settings, setSettings }) {
  // Default settings that match backend defaults
  const defaultSettings = {
    confidence_threshold: 0.6,
    season_start: '04-01',
    season_end: '10-31',
    active_hours_enabled: true,
    active_hours_start: 20,
    active_hours_end: 6,
    irrigation_duration: 60,
    zone_cooldown: 300,
    dry_run: true,
    default_sampling_rate: 1.0,  // frames per second
    snapshot_archive_days: 3,  // days before auto-archiving
    enabled_cameras: ['10cea9e4511f', 'c4dbad08f862'],  // Default: Woods + Side cameras
    camera_zones: {}  // Camera ID → Rainbird zone number
  }

  // Initialize settings from API (passed as prop) or defaults
  // Do NOT use localStorage on initialization - API is source of truth
  const [localSettings, setLocalSettings] = useState(settings || defaultSettings)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [rainbirdZones, setRainbirdZones] = useState([])
  const [ringCameras, setRingCameras] = useState([])
  const [cameraZones, setCameraZones] = useState({})
  const [testingIrrigation, setTestingIrrigation] = useState(false)
  const [testMessage, setTestMessage] = useState('')
  const [coordinatorStats, setCoordinatorStats] = useState(null)
  const [showEventLog, setShowEventLog] = useState(false)
  const [events, setEvents] = useState([])
  const [loadingEvents, setLoadingEvents] = useState(false)

  // Camera name mapping
  const CAMERA_NAMES = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door',
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Woods',
    'c4dbad08f862': 'Side'
  }
    const formatCameraName = (cameraId) => {
    return CAMERA_NAMES[cameraId] || cameraId
  }
  // Fetch Rainbird zones on component mount
  useEffect(() => {
    const fetchRainbirdZones = async () => {
      try {
          const response = await apiFetch(`/api/rainbird/zones`)
        const data = await response.json()
        
        if (data.zones && data.zones.length > 0) {
          setRainbirdZones(data.zones)
        }
      } catch (err) {
        console.error('Error fetching Rainbird zones:', err)
      }
    }
    
    fetchRainbirdZones()
  }, [])

  // Fetch Ring cameras on component mount
  useEffect(() => {
    const fetchRingCameras = async () => {
      try {
          const response = await apiFetch(`/api/ring/cameras`)
        const data = await response.json()
        
        if (data.cameras && data.cameras.length > 0) {
          // Sort cameras in preferred order: Side > Driveway > Front > Backyard
          const cameraOrder = ['woods', 'side', 'driveway', 'front', 'backyard']
          const sortedCameras = data.cameras.sort((a, b) => {
            const aIndex = cameraOrder.findIndex(name => a.name.toLowerCase().includes(name))
            const bIndex = cameraOrder.findIndex(name => b.name.toLowerCase().includes(name))
            // If not found, put at end (-1 becomes large number)
            return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex)
          })
          
          setRingCameras(sortedCameras)
          // Initialize cameraZones state with camera IDs
          const initialZones = {}
          sortedCameras.forEach(cam => {
            initialZones[cam.id] = null
          })
          setCameraZones(prev => ({ ...initialZones, ...prev }))
        }
      } catch (err) {
        console.error('Error fetching Ring cameras:', err)
        // Use fallback cameras in preferred order
        const fallbackCameras = [
          { name: 'Woods', id: '10cea9e4511f', type: 'camera' },
          { name: 'Side', id: 'c4dbad08f862', type: 'camera' },
          { name: 'Driveway', id: '587a624d3fae', type: 'camera' },
          { name: 'Front', id: '4439c4de7a79', type: 'camera' },
          { name: 'Backyard', id: 'f045dae9383a', type: 'camera' }
        ]
        setRingCameras(fallbackCameras)
        const initialZones = {}
        fallbackCameras.forEach(cam => {
          initialZones[cam.id] = null
        })
        setCameraZones(prev => ({ ...initialZones, ...prev }))
      }
    }
    
    fetchRingCameras()
  }, [])

  // Load camera-zone mappings from backend settings
  useEffect(() => {
    if (settings && settings.camera_zones) {
      setCameraZones(prev => ({ ...prev, ...settings.camera_zones }))
    }
  }, [settings])

  useEffect(() => {
    if (settings) {
      // API settings are the definitive source of truth
      setLocalSettings(settings)
      console.log('✅ Loaded settings from API (source of truth):', settings)
      // Update localStorage cache to match API
      try {
        localStorage.setItem('deer-deterrent-settings', JSON.stringify(settings))
      } catch (err) {
        console.error('Error caching settings to localStorage:', err)
      }
    }
  }, [settings])

  const handleChange = (field, value) => {
    const updated = {
      ...localSettings,
      [field]: value
    }
    setLocalSettings(updated)
    console.log(`📝 Field '${field}' changed to:`, value)
    
    // Auto-save to backend for critical camera settings
    // Only auto-save if we have loaded settings from the API (not just defaults)
    if (field === 'enabled_cameras' && settings) {      const cleanUpdated = {
        ...updated,
        camera_zones: Object.fromEntries(
          Object.entries(updated.camera_zones || {}).filter(([, v]) => v != null)
        )
      }
      apiFetch(`/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cleanUpdated)
      }).then(response => {
        if (response.ok) {
          return response.json()
        } else {
          throw new Error(`Backend save failed with status: ${response.status}`)
        }
      }).then(data => {
        console.log('✅ Camera settings auto-saved to backend (definitive):', data.settings.enabled_cameras)
        if (setSettings) {
          setSettings(data.settings)
        }
        // Cache to localStorage after successful backend save
        try {
          localStorage.setItem('deer-deterrent-settings', JSON.stringify(data.settings))
        } catch (err) {
          console.error('Error caching settings:', err)
        }
      }).catch(err => {
        console.error('❌ Backend auto-save failed:', err)
      })
    }
  }
    const setZoneForCamera = (cameraId, zoneNumber) => {
    const newZones = { ...cameraZones, [cameraId]: zoneNumber }
    setCameraZones(newZones)
    // Also update localSettings so it gets included in the save payload
    setLocalSettings(prev => ({ ...prev, camera_zones: newZones }))
  }
    const handleSave = async () => {
    setSaving(true)
    setMessage('')
    
    // Save to backend API first - this is the definitive source of truth
    try {      // Filter out null zone values — backend expects Dict[str, int]
      const cleanSettings = {
        ...localSettings,
        camera_zones: Object.fromEntries(
          Object.entries(localSettings.camera_zones || {}).filter(([, v]) => v != null)
        )
      }
      
      console.log('💾 Saving settings to backend (definitive source):', `${API_URL}/api/settings`)
      console.log('Settings data:', cleanSettings)
      
      const response = await apiFetch(`/api/settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(cleanSettings),
      })
      
      console.log('Response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Response error:', errorText)
        throw new Error(`Backend returned ${response.status}`)
      }
              const data = await response.json()
      
      // Update parent state to trigger re-render with backend data
      if (setSettings) {
        setSettings(data.settings)
      }
      
      // Cache to localStorage only after successful backend save
      try {
        localStorage.setItem('deer-deterrent-settings', JSON.stringify(data.settings))
      } catch (err) {
        console.error('Error caching to localStorage:', err)
      }
      
      setMessage('✅ Settings saved successfully to server!')
      console.log('✅ Settings persisted to backend and cached locally')
    } catch (err) {
      console.error('❌ Backend save failed:', err)
      setMessage('❌ Failed to save settings to server. Please try again.')
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 5000)
    }
  }
    const testIrrigation = async (zone, duration) => {
    setTestingIrrigation(true)
    setTestMessage('')
          try {
        const response = await apiFetch(`/api/test-irrigation`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ zone: zone.toString(), duration }),
      })
      
      const data = await response.json()
      
      if (data.status === 'success') {
        setTestMessage(`✅ ${data.message}`)
      } else {
        setTestMessage(`⚠️ ${data.message}`)
      }
    } catch (err) {
      console.error('Test irrigation error:', err)
      setTestMessage(`❌ Failed to test irrigation: ${err.message}`)
    } finally {
      setTestingIrrigation(false)
      setTimeout(() => setTestMessage(''), 8000)
    }
  }
    const stopIrrigation = async () => {
    setTestingIrrigation(true)
    setTestMessage('')
     try {
        const response = await apiFetch(`/api/stop-irrigation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      const data = await response.json()
      if (data.status === 'success') {
        setTestMessage(`✅ ${data.message}`)
      } else {
        setTestMessage(`⚠️ ${data.message}`)
      }
    } catch (err) {
      console.error('Stop irrigation error:', err)
      setTestMessage(`❌ Failed to stop irrigation: ${err.message}`)
    } finally {
      setTestingIrrigation(false)
      setTimeout(() => setTestMessage(''), 8000)
    }
  }
    const loadCoordinatorStats = async () => {
    try {
        const response = await apiFetch(`/api/coordinator/stats`)
      const data = await response.json()
      setCoordinatorStats(data)
    } catch (err) {
      console.error('Failed to load coordinator stats:', err)
    }
  }
    const viewRecentEvents = async () => {
    setLoadingEvents(true)
    setShowEventLog(true)
      try {
        const response = await apiFetch(`/api/ring-events?hours=24`)
      const data = await response.json()
      setEvents(data.events || [])
    } catch (error) {
      console.error('Error fetching events:', error)
      setEvents([])
    } finally {
      setLoadingEvents(false)
    }
  }
    const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    // Don't adjust timezone for timestamps that are already in local time
    // (Only adjust for Ring camera snapshots which are in EST)
    if (!timestamp.includes('.')) {
      // Manual upload - already in correct timezone
      return date.toLocaleString()
    }
    // Adjust for EST to CST conversion (subtract 1 hour)
    date.setHours(date.getHours() - 1)
    return date.toLocaleString()
  }

  return (
    <div className="settings">
      <div className="settings-header-row">
        <h2>System Settings</h2>
        <div className="header-actions">
          <button 
            className="btn-save-settings"
            onClick={handleSave}
            disabled={saving}
            title="Save all settings"
          >
            {saving ? '⏳ Saving...' : '💾 Save Settings'}
          </button>
        </div>
      </div>
      
      {message && (
        <div className={`message ${message.includes('✅') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      <div className="settings-sections">
        {/* Compact Card Grid for Quick Settings */}
        <div className="settings-grid">
          {/* Combined Camera Detection + Zone Mapping - Double-wide card */}
          <div className="settings-card camera-zones-card">
            <h3>Detection Cameras</h3>
            <div className="card-content">
              <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#666' }}>
                Select which cameras to use for deer detection and link to irrigation zones
              </p>
              {ringCameras.length > 0 && rainbirdZones.length > 0 ? (
                <div className="camera-zone-compact">
                  {ringCameras.map(camera => (
                    <div key={camera.id} className="camera-zone-row-combined">
                      <label className="checkbox-inline" style={{ marginBottom: 0, minWidth: '140px' }}>
                        <input
                          type="checkbox"
                          checked={(localSettings.enabled_cameras || []).includes(camera.id)}
                          onChange={(e) => {
                            const current = localSettings.enabled_cameras || [];
                            const updated = e.target.checked
                              ? [...current, camera.id]
                              : current.filter(id => id !== camera.id);
                            handleChange('enabled_cameras', updated);
                          }}
                        />
                        {camera.name}
                      </label>
                      <select
                        className="zone-select-compact"
                        value={cameraZones[camera.id] || ''}
                        onChange={(e) => setZoneForCamera(camera.id, e.target.value ? parseInt(e.target.value) : null)}
                        disabled={!(localSettings.enabled_cameras || []).includes(camera.id)}
                      >
                        <option value="">No Zone</option>
                        {rainbirdZones.map(zone => (
                          <option key={zone.number} value={zone.number}>
                            Zone {zone.number} - {zone.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="loading-zones-compact">
                  <p>Loading cameras and zones...</p>
                </div>
              )}
            </div>
          </div>

          {/* Snapshot Archive + Active Hours */}
          <div className="settings-card">
            <h3>Snapshot Management</h3>
            <div className="card-content">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={localSettings.active_hours_enabled || false}
                  onChange={(e) => handleChange('active_hours_enabled', e.target.checked)}
                />
                Active Hours Enabled
              </label>
              {localSettings.active_hours_enabled && (
                <>
                  <div className="inline-field">
                    <label htmlFor="hours-start">Start (24h)</label>
                    <input
                      id="hours-start"
                      type="number"
                      min="0"
                      max="23"
                      value={localSettings.active_hours_start || 20}
                      onChange={(e) => handleChange('active_hours_start', parseInt(e.target.value))}
                    />
                  </div>
                  <div className="inline-field">
                    <label htmlFor="hours-end">End (24h)</label>
                    <input
                      id="hours-end"
                      type="number"
                      min="0"
                      max="23"
                      value={localSettings.active_hours_end || 6}
                      onChange={(e) => handleChange('active_hours_end', parseInt(e.target.value))}
                    />
                  </div>
                </>
              )}
              <div className="inline-field">
                <label htmlFor="snapshot-freq">Frequency</label>
                <select
                  id="snapshot-freq"
                  className="settings-select"
                  value={localSettings.snapshot_frequency || 60}
                  onChange={(e) => handleChange('snapshot_frequency', parseInt(e.target.value))}
                >
                  <option value={180}>3 min</option>
                  <option value={60}>1 min</option>
                  <option value={30}>30 sec</option>
                  <option value={15}>15 sec</option>
                </select>
              </div>
              <div className="inline-field">
                <label htmlFor="archive-days">Auto-archive (d)</label>
                <input
                  id="archive-days"
                  type="number"
                  min="1"
                  max="30"
                  step="1"
                  value={localSettings.snapshot_archive_days || 3}
                  onChange={(e) => handleChange('snapshot_archive_days', parseInt(e.target.value))}
                  className="value-input"
                />
              </div>
            </div>
          </div>

          {/* Season + Irrigation */}
          <div className="settings-card">
            <h3>Irrigation Season</h3>
            <div className="card-content">
              <label htmlFor="season-start">Season Start Date</label>
              <input
                id="season-start"
                type="text"
                pattern="\d{2}-\d{2}"
                placeholder="MM-DD"
                value={localSettings.season_start || '04-01'}
                onChange={(e) => handleChange('season_start', e.target.value)}
              />
              <label htmlFor="season-end">Season End Date</label>
              <input
                id="season-end"
                type="text"
                pattern="\d{2}-\d{2}"
                placeholder="MM-DD"
                value={localSettings.season_end || '10-31'}
                onChange={(e) => handleChange('season_end', e.target.value)}
              />
              <label htmlFor="duration">Duration (min)</label>
              <input
                id="duration"
                type="number"
                min="1"
                max="10"
                step="1"
                value={Math.round((localSettings.irrigation_duration || 60) / 60)}
                onChange={(e) => handleChange('irrigation_duration', parseInt(e.target.value) * 60)}
              />
              <label htmlFor="cooldown">Cooldown (min)</label>
              <input
                id="cooldown"
                type="number"
                min="0"
                max="60"
                value={Math.floor((localSettings.zone_cooldown ?? 300) / 60)}
                onChange={(e) => handleChange('zone_cooldown', parseInt(e.target.value) * 60)}
              />
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={localSettings.dry_run || false}
                  onChange={(e) => handleChange('dry_run', e.target.checked)}
                />
                Dry Run Mode
              </label>
            </div>
          </div>
          
          {/* Detection + Training */}
          <div className="settings-card">
            <h3>Detection & Training</h3>
            <div className="card-content">
              <label htmlFor="confidence">Confidence Threshold</label>
              <div className="input-with-display">
                <input
                  id="confidence"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={localSettings.confidence_threshold || 0.6}
                  onChange={(e) => handleChange('confidence_threshold', parseFloat(e.target.value))}
                />
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={localSettings.confidence_threshold || 0.6}
                  onChange={(e) => handleChange('confidence_threshold', parseFloat(e.target.value))}
                  className="value-input"
                />
              </div>
              <label htmlFor="sampling-rate">Default Frame Sampling Rate</label>
              <div className="input-with-unit">
                <input
                  id="sampling-rate"
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={localSettings.default_sampling_rate || 1.0}
                  onChange={(e) => handleChange('default_sampling_rate', parseFloat(e.target.value))}
                  className="value-input"
                />
                <span className="unit-label">frames/sec</span>
              </div>
              <p className="setting-hint">Number of frames to extract per second for annotation (default: 1.0)</p>
            </div>
          </div>
        </div>

        {/* System Testing & Diagnostics */}
        <div className="settings-section">
          <h3>🔧 System Testing & Diagnostics</h3>
          
          {testMessage && (
            <div className={`message ${testMessage.includes('✅') ? 'success' : 'error'}`} style={{ marginBottom: '1rem' }}>
              {testMessage}
            </div>
          )}

          <div className="testing-grid">
            {/* Irrigation Test - Full Width */}
            <div className="test-card test-card-full">
              <h4>💧 Test Irrigation</h4>
              <p>Tap a zone to run for 1 minute. Use Stop All to cancel.</p>
              <div className="irrigation-zone-grid">
                {rainbirdZones.map(zone => (
                  <button
                    key={zone.number}
                    className="btn-zone"
                    onClick={() => testIrrigation(zone.number, 60)}
                    disabled={testingIrrigation}
                    title={`Test ${zone.name} for 1 minute`}
                  >
                    <span className="zone-number">Zone {zone.number}</span>
                    <span className="zone-name">{zone.name}</span>
                  </button>
                ))}
              </div>
              <div className="irrigation-actions">
                <button
                  className="btn-stop-all"
                  onClick={stopIrrigation}
                  disabled={testingIrrigation}
                  title="Stop all irrigation zones"
                >
                  {testingIrrigation ? '⏳' : '⏹️'} Stop All Zones
                </button>
              </div>
            </div>

            {/* Recent Events */}
            <div className="test-card">
              <h4>📜 Recent Events</h4>
              <p>View Ring camera motion events from the past 24 hours</p>
              <button 
                className="btn-test"
                onClick={viewRecentEvents}
              >
                🔗 Open Event Log
              </button>
            </div>

            {/* System Status */}
            <div className="test-card">
              <h4>📊 Coordinator Stats</h4>
              <button 
                className="btn-test"
                onClick={loadCoordinatorStats}
              >
                🔄 Refresh Stats
              </button>
              {coordinatorStats && (
                <div className="stats-grid">
                  <div className="stat-item">
                    <div className="stat-label">MQTT Connected</div>
                    <div className={`stat-value ${coordinatorStats.mqtt_connected ? 'status-good' : 'status-bad'}`}>
                      {coordinatorStats.mqtt_connected ? '✅ Yes' : '❌ No'}
                    </div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-label">Snapshots Cached</div>
                    <div className="stat-value">{coordinatorStats.total_snapshots.toLocaleString()}</div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-label">Active Hours</div>
                    <div className={`stat-value ${coordinatorStats.active_hours ? 'status-good' : 'status-neutral'}`}>
                      {coordinatorStats.active_hours ? '🟢 Active' : '🔴 Inactive'}
                    </div>
                  </div>
                  <div className="stat-item">
                    <div className="stat-label">Cooldown</div>
                    <div className="stat-value">{coordinatorStats.cooldown_remaining_seconds}s</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Event Log Modal */}
      {showEventLog && (
        <div className="modal-overlay" onClick={() => setShowEventLog(false)}>
          <div className="event-log-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>📜 Recent Events (Last 24 Hours)</h2>
              <button className="btn-close" onClick={() => setShowEventLog(false)}>✕</button>
            </div>
            <div className="modal-content">
              {loadingEvents ? (
                <div className="loading-message">Loading events...</div>
              ) : events.length === 0 ? (
                <div className="empty-message">No events found in the last 24 hours</div>
              ) : (
                <table className="event-log-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Camera</th>
                      <th>Type</th>
                      <th>Deer</th>
                      <th>Confidence</th>
                      <th>Snapshot</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((event) => (
                      <tr key={event.id}>
                        <td>{formatTimestamp(event.timestamp)}</td>
                        <td>{formatCameraName(event.camera_id)}</td>
                        <td>{event.event_type}</td>
                        <td className={event.deer_detected ? 'detected' : 'not-detected'}>
                          {event.deer_detected ? '✓ Yes' : '✗ No'}
                        </td>
                        <td>
                          {event.detection_confidence !== null && event.detection_confidence !== undefined
                            ? `${(event.detection_confidence * 100).toFixed(1)}%`
                            : '—'}
                        </td>
                        <td className="text-center">
                          {event.snapshot_available ? '📸' : '—'}
                        </td>
                        <td>
                          {event.archived ? '📦 Archived' : event.processed ? '✓ Processed' : '⏳ Pending'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Settings


