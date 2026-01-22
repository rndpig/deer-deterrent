import { useState, useEffect } from 'react'
import './Settings.css'

function Settings({ settings, setSettings }) {
  // Default settings that match backend defaults
  const defaultSettings = {
    confidence_threshold: 0.6,
    season_start: '04-01',
    season_end: '10-31',
    active_hours_enabled: true,
    active_hours_start: 20,
    active_hours_end: 6,
    irrigation_duration: 30,
    zone_cooldown: 300,
    dry_run: true,
    default_sampling_rate: 1.0,  // frames per second
    snapshot_archive_days: 3  // days before auto-archiving
  }

  // Initialize from localStorage or defaults
  const getInitialSettings = () => {
    try {
      const saved = localStorage.getItem('deer-deterrent-settings')
      if (saved) {
        return JSON.parse(saved)
      }
    } catch (err) {
      console.error('Error loading saved settings:', err)
    }
    return settings || defaultSettings
  }

  const [localSettings, setLocalSettings] = useState(getInitialSettings())
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [rainbirdZones, setRainbirdZones] = useState([])
  const [ringCameras, setRingCameras] = useState([])
  const [cameraZones, setCameraZones] = useState({})
  const [testingIrrigation, setTestingIrrigation] = useState(false)
  const [testMessage, setTestMessage] = useState('')
  const [coordinatorStats, setCoordinatorStats] = useState(null)
  // Fetch Rainbird zones on component mount
  useEffect(() => {
    const fetchRainbirdZones = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
        const response = await fetch(`${apiUrl}/api/rainbird/zones`)
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
        const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
        const response = await fetch(`${apiUrl}/api/ring/cameras`)
        const data = await response.json()
        
        if (data.cameras && data.cameras.length > 0) {
          // Sort cameras in preferred order: Side > Driveway > Front > Backyard
          const cameraOrder = ['side', 'driveway', 'front', 'backyard']
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
          { name: 'Side', id: 'side', type: 'camera' },
          { name: 'Driveway', id: 'driveway', type: 'camera' },
          { name: 'Front', id: 'front', type: 'camera' },
          { name: 'Backyard', id: 'backyard', type: 'camera' }
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

  // Load camera-zone mappings from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('deer-deterrent-camera-zones')
      if (saved) {
        setCameraZones(JSON.parse(saved))
      }
    } catch (err) {
      console.error('Error loading camera zones:', err)
    }
  }, [])

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings)
    }
  }, [settings])

  const handleChange = (field, value) => {
    setLocalSettings(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const setZoneForCamera = (cameraId, zoneNumber) => {
    setCameraZones(prev => ({
      ...prev,
      [cameraId]: zoneNumber
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage('')
    
    // Save settings to localStorage immediately
    try {
      localStorage.setItem('deer-deterrent-settings', JSON.stringify(localSettings))
      localStorage.setItem('deer-deterrent-camera-zones', JSON.stringify(cameraZones))
      console.log('Settings saved to localStorage:', localSettings)
      
      // Update parent state immediately to ensure persistence
      if (setSettings) {
        setSettings(localSettings)
      }
    } catch (err) {
      console.error('Error saving to localStorage:', err)
    }
    
    // Try to save to backend if available
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
      console.log('Attempting to save to backend:', `${apiUrl}/api/settings`)
      console.log('Settings data:', localSettings)
      
      const response = await fetch(`${apiUrl}/api/settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(localSettings),
      })
      
      console.log('Response status:', response.status)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Response error:', errorText)
        throw new Error(`Backend returned ${response.status}`)
      }
      
      const data = await response.json()
      if (setSettings) {
        setSettings(data.settings)
      }
      setMessage('✅ Settings saved successfully (backend and local)!')
    } catch (err) {
      console.error('Backend save failed:', err)
      // Still consider it a success since we saved locally
      setMessage('✅ Settings saved locally (backend offline)')
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 5000)
    }
  }

  const testIrrigation = async (zone, duration) => {
    setTestingIrrigation(true)
    setTestMessage('')
    
    try {
      const coordinatorUrl = 'http://192.168.7.215:5000'
      const response = await fetch(`${coordinatorUrl}/test-irrigation`, {
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

  const loadCoordinatorStats = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
      const response = await fetch(`${apiUrl}/api/coordinator/stats`)
      const data = await response.json()
      setCoordinatorStats(data)
    } catch (err) {
      console.error('Failed to load coordinator stats:', err)
    }
  }

  const viewRecentEvents = () => {
    const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'
    window.open(`${apiUrl}/api/ring-events?hours=24`, '_blank')
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
          <div className="settings-card">
            <h3>Detection</h3>
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
            </div>
          </div>
          
          <div className="settings-card">
            <h3>Training</h3>
            <div className="card-content">
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

          <div className="settings-card">
            <h3>Snapshot Archive</h3>
            <div className="card-content">
              <label htmlFor="archive-days">Auto-Archive After</label>
              <div className="input-with-unit">
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
                <span className="unit-label">days</span>
              </div>
              <p className="setting-hint">Snapshots older than this will be automatically archived</p>
            </div>
          </div>

          <div className="settings-card">
            <h3>Season</h3>
            <div className="card-content">
              <label htmlFor="season-start">Start Date</label>
              <input
                id="season-start"
                type="text"
                pattern="\d{2}-\d{2}"
                placeholder="MM-DD"
                value={localSettings.season_start || '04-01'}
                onChange={(e) => handleChange('season_start', e.target.value)}
              />
              <label htmlFor="season-end">End Date</label>
              <input
                id="season-end"
                type="text"
                pattern="\d{2}-\d{2}"
                placeholder="MM-DD"
                value={localSettings.season_end || '10-31'}
                onChange={(e) => handleChange('season_end', e.target.value)}
              />
            </div>
          </div>

          <div className="settings-card">
            <h3>Active Hours</h3>
            <div className="card-content">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={localSettings.active_hours_enabled || false}
                  onChange={(e) => handleChange('active_hours_enabled', e.target.checked)}
                />
                Enabled
              </label>
              {localSettings.active_hours_enabled && (
                <>
                  <label htmlFor="hours-start">Start (24h)</label>
                  <input
                    id="hours-start"
                    type="number"
                    min="0"
                    max="23"
                    value={localSettings.active_hours_start || 20}
                    onChange={(e) => handleChange('active_hours_start', parseInt(e.target.value))}
                  />
                  <label htmlFor="hours-end">End (24h)</label>
                  <input
                    id="hours-end"
                    type="number"
                    min="0"
                    max="23"
                    value={localSettings.active_hours_end || 6}
                    onChange={(e) => handleChange('active_hours_end', parseInt(e.target.value))}
                  />
                </>
              )}
            </div>
          </div>

          <div className="settings-card">
            <h3>Irrigation</h3>
            <div className="card-content">
              <label htmlFor="duration">Duration (sec)</label>
              <input
                id="duration"
                type="number"
                min="5"
                max="300"
                step="5"
                value={localSettings.irrigation_duration || 30}
                onChange={(e) => handleChange('irrigation_duration', parseInt(e.target.value))}
              />
              <label htmlFor="cooldown">Cooldown (min)</label>
              <input
                id="cooldown"
                type="number"
                min="1"
                max="60"
                value={Math.floor((localSettings.zone_cooldown || 300) / 60)}
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

          {/* Camera Zone Mappings - Double-wide card */}
          <div className="settings-card camera-zones-card">
            <h3>Camera → Zone</h3>
            <div className="card-content">
              {rainbirdZones.length > 0 && ringCameras.length > 0 ? (
                <div className="camera-zone-compact">
                  {ringCameras.map(camera => (
                    <div key={camera.id} className="camera-zone-row-compact">
                      <label className="camera-label-compact">
                        📹 {camera.name}
                      </label>
                      <select
                        className="zone-select-compact"
                        value={cameraZones[camera.id] || ''}
                        onChange={(e) => setZoneForCamera(camera.id, e.target.value ? parseInt(e.target.value) : null)}
                      >
                        <option value="">None</option>
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
            {/* Irrigation Test */}
            <div className="test-card">
              <h4>💧 Test Irrigation</h4>
              <p>Manually trigger irrigation to verify zone operation</p>
              <div className="test-controls">
                {rainbirdZones.map(zone => (
                  <button
                    key={zone.number}
                    className="btn-test"
                    onClick={() => testIrrigation(zone.number, 10)}
                    disabled={testingIrrigation}
                    title={`Test ${zone.name} for 10 seconds`}
                  >
                    {testingIrrigation ? '⏳' : '▶️'} Zone {zone.number}
                  </button>
                ))}
              </div>
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
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings


