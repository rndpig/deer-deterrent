import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

function formatDateTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function RecentIrrigationCard() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiFetch('/api/stats/recent-irrigation?limit=15')
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setEvents(data.events || [])
      } catch (e) {
        console.error('Failed to load recent irrigation events:', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-4 flex flex-col h-full">
      <h3 className="text-sm font-semibold text-white/70 uppercase tracking-wide mb-3 flex-shrink-0">
        💦 Recent Irrigation
      </h3>
      {loading ? (
        <div className="text-white/30 text-sm">Loading…</div>
      ) : events.length === 0 ? (
        <div className="text-white/30 text-sm italic">No irrigation triggers yet.</div>
      ) : (
        <ol className="flex flex-col gap-1 flex-1 min-h-0 overflow-auto">
          {events.map((ev) => (
            <li
              key={ev.id}
              className="flex items-center justify-between text-xs text-white/80 border-b border-white/5 pb-1 last:border-b-0"
            >
              <span className="font-mono tabular-nums">{formatDateTime(ev.timestamp)}</span>
              <span className="text-white/50 ml-2 text-right">{ev.zones || '—'}</span>
            </li>
          ))}
        </ol>
      )}
      <div className="mt-2 text-[11px] text-white/30 flex-shrink-0">
        Last {events.length} trigger{events.length === 1 ? '' : 's'}
      </div>
    </div>
  )
}

export default RecentIrrigationCard
