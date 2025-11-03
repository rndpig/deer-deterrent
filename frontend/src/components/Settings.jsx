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
    sprinkler_duration: 30,
    zone_cooldown: 300,
    dry_run: true
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

  const handleSave = async () => {
    setSaving(true)
    setMessage('')
    
    // Save to localStorage immediately
    try {
      localStorage.setItem('deer-deterrent-settings', JSON.stringify(localSettings))
      console.log('Settings saved to localStorage')
    } catch (err) {
      console.error('Error saving to localStorage:', err)
    }
    
    // Try to save to backend if available
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
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

  return (
    <div className="settings">
      <h2>System Settings</h2>
      
      {message && (
        <div className={`message ${message.includes('✅') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      <div className="settings-sections">
        <section className="settings-section">
          <h3>Detection Settings</h3>
          
          <div className="setting-item">
            <label htmlFor="confidence">
              Confidence Threshold
              <span className="help-text">Minimum confidence required for detection (0.0 - 1.0)</span>
            </label>
            <input
              id="confidence"
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={localSettings.confidence_threshold || 0.6}
              onChange={(e) => handleChange('confidence_threshold', parseFloat(e.target.value))}
            />
            <span className="value-display">
              {((localSettings.confidence_threshold || 0.6) * 100).toFixed(0)}%
            </span>
          </div>
        </section>

        <section className="settings-section">
          <h3>Seasonal Operation</h3>
          
          <div className="setting-item">
            <label htmlFor="season-start">
              Season Start Date
              <span className="help-text">Format: MM-DD (e.g., 04-01 for April 1st)</span>
            </label>
            <input
              id="season-start"
              type="text"
              pattern="\d{2}-\d{2}"
              placeholder="MM-DD"
              value={localSettings.season_start || '04-01'}
              onChange={(e) => handleChange('season_start', e.target.value)}
            />
          </div>
          
          <div className="setting-item">
            <label htmlFor="season-end">
              Season End Date
              <span className="help-text">Format: MM-DD (e.g., 10-31 for October 31st)</span>
            </label>
            <input
              id="season-end"
              type="text"
              pattern="\d{2}-\d{2}"
              placeholder="MM-DD"
              value={localSettings.season_end || '10-31'}
              onChange={(e) => handleChange('season_end', e.target.value)}
            />
          </div>
        </section>

        <section className="settings-section">
          <h3>Active Hours</h3>
          
          <div className="setting-item checkbox">
            <label>
              <input
                type="checkbox"
                checked={localSettings.active_hours_enabled || false}
                onChange={(e) => handleChange('active_hours_enabled', e.target.checked)}
              />
              Enable Active Hours Restriction
              <span className="help-text">Only activate deterrent during specific hours</span>
            </label>
          </div>
          
          {localSettings.active_hours_enabled && (
            <>
              <div className="setting-item">
                <label htmlFor="hours-start">
                  Active Start Hour (24-hour format)
                </label>
                <input
                  id="hours-start"
                  type="number"
                  min="0"
                  max="23"
                  value={localSettings.active_hours_start || 20}
                  onChange={(e) => handleChange('active_hours_start', parseInt(e.target.value))}
                />
                <span className="value-display">
                  {(localSettings.active_hours_start || 20)}:00
                </span>
              </div>
              
              <div className="setting-item">
                <label htmlFor="hours-end">
                  Active End Hour (24-hour format)
                </label>
                <input
                  id="hours-end"
                  type="number"
                  min="0"
                  max="23"
                  value={localSettings.active_hours_end || 6}
                  onChange={(e) => handleChange('active_hours_end', parseInt(e.target.value))}
                />
                <span className="value-display">
                  {(localSettings.active_hours_end || 6)}:00
                </span>
              </div>
            </>
          )}
        </section>

        <section className="settings-section">
          <h3>Sprinkler Settings</h3>
          
          <div className="setting-item">
            <label htmlFor="duration">
              Sprinkler Duration (seconds)
              <span className="help-text">How long to run sprinklers when deer detected</span>
            </label>
            <input
              id="duration"
              type="number"
              min="5"
              max="300"
              step="5"
              value={localSettings.sprinkler_duration || 30}
              onChange={(e) => handleChange('sprinkler_duration', parseInt(e.target.value))}
            />
            <span className="value-display">{localSettings.sprinkler_duration || 30}s</span>
          </div>
          
          <div className="setting-item">
            <label htmlFor="cooldown">
              Zone Cooldown (seconds)
              <span className="help-text">Minimum time between activations for same zone</span>
            </label>
            <input
              id="cooldown"
              type="number"
              min="60"
              max="3600"
              step="60"
              value={localSettings.zone_cooldown || 300}
              onChange={(e) => handleChange('zone_cooldown', parseInt(e.target.value))}
            />
            <span className="value-display">
              {Math.floor((localSettings.zone_cooldown || 300) / 60)} min
            </span>
          </div>
          
          <div className="setting-item checkbox">
            <label>
              <input
                type="checkbox"
                checked={localSettings.dry_run || false}
                onChange={(e) => handleChange('dry_run', e.target.checked)}
              />
              Dry Run Mode (Demo Only)
              <span className="help-text">Simulate sprinkler activation without actually running them</span>
            </label>
          </div>
        </section>
      </div>

      <div className="settings-actions">
        <button 
          className="save-button" 
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

export default Settings
