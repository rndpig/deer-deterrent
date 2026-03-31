import { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Legend, CartesianGrid, Cell
} from 'recharts'

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const YEAR_COLORS = ['#4ade80','#60a5fa','#f59e0b','#f472b6','#a78bfa','#fb923c']

const CAMERA_NAMES = {
  '587a624d3fae': 'Driveway',
  '4439c4de7a79': 'Front Door',
  'f045dae9383a': 'Back',
  '10cea9e4511f': 'Woods',
  'c4dbad08f862': 'Side',
  'manual_upload': 'Manual Upload'
}

function circularMeanTime(timestamps) {
  if (timestamps.length === 0) return null
  let sinSum = 0, cosSum = 0
  for (const ts of timestamps) {
    const d = new Date(ts)
    const frac = d.getHours() + d.getMinutes() / 60
    const angle = (frac / 24) * 2 * Math.PI
    sinSum += Math.sin(angle)
    cosSum += Math.cos(angle)
  }
  let mean = Math.atan2(sinSum / timestamps.length, cosSum / timestamps.length)
  if (mean < 0) mean += 2 * Math.PI
  const h = (mean / (2 * Math.PI)) * 24
  const hours = Math.floor(h)
  const mins = Math.round((h - hours) * 60)
  const ampm = hours >= 12 ? 'PM' : 'AM'
  const display = hours % 12 || 12
  return `${display}:${String(mins).padStart(2, '0')} ${ampm}`
}

function formatCameraName(cameraId) {
  return CAMERA_NAMES[cameraId] || cameraId
}

function Stats() {
  const [allSnapshots, setAllSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedYears, setSelectedYears] = useState([])
  const [aiSynopsis, setAiSynopsis] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)

  const apiUrl = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/snapshots?limit=50000&with_deer=true`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setAllSnapshots(data.snapshots || [])
      } catch (e) {
        console.error('Failed to load snapshots for stats:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
  }, [])

  // Deer-only snapshots
  const deerSnapshots = useMemo(
    () => allSnapshots.filter(s => s.deer_detected),
    [allSnapshots]
  )

  // Available years
  const availableYears = useMemo(() => {
    const years = new Set(deerSnapshots.map(s => new Date(s.timestamp).getFullYear()))
    return [...years].sort((a, b) => b - a)
  }, [deerSnapshots])

  // Auto-select current year on first load
  useEffect(() => {
    if (availableYears.length > 0 && selectedYears.length === 0) {
      setSelectedYears([availableYears[0]])
    }
  }, [availableYears])

  const toggleYear = (year) => {
    setSelectedYears(prev =>
      prev.includes(year) ? prev.filter(y => y !== year) : [...prev, year]
    )
  }

  // Filtered snapshots by selected years
  const filtered = useMemo(
    () => deerSnapshots.filter(s => selectedYears.includes(new Date(s.timestamp).getFullYear())),
    [deerSnapshots, selectedYears]
  )

  // ── Key Metrics ──
  const metrics = useMemo(() => {
    if (filtered.length === 0) return null

    const timestamps = filtered.map(s => s.timestamp)
    const confidences = filtered.filter(s => s.detection_confidence != null).map(s => s.detection_confidence)

    // Max deer in a single snapshot
    const maxDeerInShot = filtered.reduce((max, s) => {
      const count = s.detection_bboxes?.length || 0
      return count > max ? count : max
    }, 0)

    // Most active camera
    const cameraCounts = {}
    for (const s of filtered) {
      const name = formatCameraName(s.camera_id)
      cameraCounts[name] = (cameraCounts[name] || 0) + 1
    }
    const topCamera = Object.entries(cameraCounts).sort((a, b) => b[1] - a[1])[0]

    // Peak month
    const monthCounts = {}
    for (const s of filtered) {
      const d = new Date(s.timestamp)
      const key = `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`
      monthCounts[key] = (monthCounts[key] || 0) + 1
    }
    const peakMonth = Object.entries(monthCounts).sort((a, b) => b[1] - a[1])[0]

    // Peak hour (using 1-hour buckets)
    const hourCounts = new Array(24).fill(0)
    for (const s of filtered) {
      hourCounts[new Date(s.timestamp).getHours()]++
    }
    const peakHourIdx = hourCounts.indexOf(Math.max(...hourCounts))
    const peakHourAmpm = peakHourIdx >= 12 ? 'PM' : 'AM'
    const peakHourDisplay = peakHourIdx % 12 || 12
    const peakHour = `${peakHourDisplay} ${peakHourAmpm}`

    // Days with sightings vs total days in range
    const daySet = new Set(filtered.map(s => new Date(s.timestamp).toDateString()))
    const firstDate = new Date(Math.min(...filtered.map(s => new Date(s.timestamp))))
    const lastDate = new Date(Math.max(...filtered.map(s => new Date(s.timestamp))))
    const totalDays = Math.max(1, Math.ceil((lastDate - firstDate) / (1000 * 60 * 60 * 24)) + 1)

    // Irrigation count
    const irrigationCount = filtered.filter(s => s.irrigation_activated).length

    return {
      total: filtered.length,
      irrigationCount,
      meanTime: circularMeanTime(timestamps),
      avgConfidence: confidences.length > 0
        ? `${(confidences.reduce((a, b) => a + b, 0) / confidences.length * 100).toFixed(0)}%`
        : '—',
      maxDeerInShot,
      topCamera: topCamera ? `${topCamera[0]} (${topCamera[1]})` : '—',
      peakMonth: peakMonth ? `${peakMonth[0]} (${peakMonth[1]})` : '—',
      peakHour,
      activeDays: daySet.size,
      totalDays,
      frequency: `${(daySet.size / totalDays * 100).toFixed(0)}%`,
      cameraCounts,
      hourCounts,
    }
  }, [filtered])

  // ── Monthly chart data (deer + irrigation) ──
  const monthlyChartData = useMemo(() => {
    const data = MONTH_NAMES.map((m, i) => ({ month: m, monthIdx: i }))
    for (const year of selectedYears) {
      const yearSnaps = deerSnapshots.filter(s => new Date(s.timestamp).getFullYear() === year)
      const deerCounts = new Array(12).fill(0)
      const irrigCounts = new Array(12).fill(0)
      for (const s of yearSnaps) {
        const mi = new Date(s.timestamp).getMonth()
        deerCounts[mi]++
        if (s.irrigation_activated) irrigCounts[mi]++
      }
      data.forEach((d, i) => {
        d[`deer_${year}`] = deerCounts[i]
        d[`irrig_${year}`] = irrigCounts[i]
      })
    }
    return data
  }, [deerSnapshots, selectedYears])

  // ── Hourly distribution data (active hours only: 8 PM – 6 AM) ──
  const hourlyChartData = useMemo(() => {
    if (!metrics) return []
    const activeHours = [20, 21, 22, 23, 0, 1, 2, 3, 4, 5]
    return activeHours.map(hour => {
      const ampm = hour >= 12 ? 'PM' : 'AM'
      const display = hour % 12 || 12
      return { hour: `${display}${ampm}`, count: metrics.hourCounts[hour], hourIdx: hour }
    })
  }, [metrics])

  // ── AI Synopsis ──
  const generateSynopsis = async () => {
    if (!metrics || filtered.length === 0) return
    setAiLoading(true)
    setAiSynopsis(null)
    try {
      // Build a data summary to send to the backend
      const payload = {
        total_sightings: metrics.total,
        selected_years: selectedYears,
        mean_time: metrics.meanTime,
        avg_confidence: metrics.avgConfidence,
        max_deer_in_shot: metrics.maxDeerInShot,
        peak_month: metrics.peakMonth,
        peak_hour: metrics.peakHour,
        active_days: metrics.activeDays,
        total_days: metrics.totalDays,
        frequency: metrics.frequency,
        camera_breakdown: metrics.cameraCounts,
        monthly_data: monthlyChartData.map(d => {
          const entry = { month: d.month }
          selectedYears.forEach(y => { entry[y] = d[y] || 0 })
          return entry
        }),
        hourly_distribution: metrics.hourCounts,
      }
      const res = await fetch(`${apiUrl}/api/stats/synopsis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setAiSynopsis(data.synopsis)
    } catch (e) {
      setAiSynopsis(`Unable to generate synopsis: ${e.message}`)
    } finally {
      setAiLoading(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-white/50">Loading stats...</div>
  }

  if (deerSnapshots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-white/50 gap-2">
        <span className="text-4xl">🦌</span>
        <span>No deer detections to analyze yet.</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4 max-w-[1400px] mx-auto">

      {/* ── Year Selector ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-white/40 font-semibold">Compare Years</span>
        {availableYears.map(year => (
          <button
            key={year}
            onClick={() => toggleYear(year)}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors border ${
              selectedYears.includes(year)
                ? 'bg-blue-600 border-blue-500 text-white'
                : 'bg-white/5 border-white/10 text-white/50 hover:text-white hover:border-white/30'
            }`}
          >
            {year}
          </button>
        ))}
      </div>

      {metrics && (
        <>
          {/* ── Key Metrics Grid ── */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <MetricCard label="🦌 Total Sightings" value={metrics.total} />
            <MetricCard label="💦 Irrigation Events" value={metrics.irrigationCount} />
            <MetricCard label="Mean Sighting Time" value={metrics.meanTime} />
            <MetricCard label="Peak Sighting Hour" value={metrics.peakHour} />
            <MetricCard label="Mean Confidence" value={metrics.avgConfidence} />
            <MetricCard label="Activity Rate" value={metrics.frequency} sub={`${metrics.activeDays} of ${metrics.totalDays} days`} />
          </div>

          {/* ── Charts: Monthly Sightings + Hourly Distribution ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Monthly sightings */}
            <div className="bg-white/5 border border-white/10 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide mb-3">
                Monthly Sightings & Irrigation
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={monthlyChartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="month" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: '#1e1e1e', border: '1px solid #333', borderRadius: 8 }}
                    labelStyle={{ color: '#fff' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  {selectedYears.flatMap((year, i) => [
                    <Bar key={`deer_${year}`} dataKey={`deer_${year}`} name={`🦌 ${year}`}
                      fill="#4ade80" radius={[3, 3, 0, 0]} />,
                    <Bar key={`irrig_${year}`} dataKey={`irrig_${year}`} name={`💦 ${year}`}
                      fill="#60a5fa" radius={[3, 3, 0, 0]} />
                  ])}
                  <Legend wrapperStyle={{ color: 'rgba(255,255,255,0.7)' }} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Hourly distribution */}
            <div className="bg-white/5 border border-white/10 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide mb-3">
                Hourly Distribution
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={hourlyChartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="hour" tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10 }} interval={0} />
                  <YAxis allowDecimals={false} tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: '#1e1e1e', border: '1px solid #333', borderRadius: 8 }}
                    labelStyle={{ color: '#fff' }}
                  />
                  <Bar dataKey="count" name="Sightings" radius={[2, 2, 0, 0]}>
                    {hourlyChartData.map((entry, i) => (
                      <Cell key={i} fill={entry.count > 0 ? '#4ade80' : 'rgba(255,255,255,0.05)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── AI Synopsis ── */}
          <div className="bg-white/5 border border-white/10 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide">
                AI Synopsis
              </h3>
              <button
                onClick={generateSynopsis}
                disabled={aiLoading}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  aiLoading
                    ? 'bg-white/10 text-white/30 cursor-wait'
                    : 'bg-purple-600 hover:bg-purple-500 text-white'
                }`}
              >
                {aiLoading ? 'Generating...' : '✨ Generate Synopsis'}
              </button>
            </div>
            {aiSynopsis ? (
              <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap">{aiSynopsis}</p>
            ) : (
              <p className="text-sm text-white/30 italic">
                Click "Generate Synopsis" for an AI-powered analysis of your deer activity data.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function MetricCard({ label, value, sub }) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 flex flex-col">
      <span className="text-[0.65rem] uppercase tracking-wide text-white/40 leading-tight">{label}</span>
      <span className="text-lg font-bold text-white/90 mt-0.5 leading-tight">{value}</span>
      {sub && <span className="text-[0.6rem] text-white/30 mt-0.5">{sub}</span>}
    </div>
  )
}

export default Stats
