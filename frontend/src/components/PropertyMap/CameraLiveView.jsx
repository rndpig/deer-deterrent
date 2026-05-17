import { useEffect, useRef, useState } from 'react'
import { API_URL } from '../../api'
import { auth } from '../../firebase'

// All camera traffic goes through the deer backend (same-origin), which
// reverse-proxies go2rtc. This removes the need for cross-origin cookies,
// CORS allow-lists, or a public cam-stream hostname.
const CAMS_BASE = `${API_URL}/cams`

let go2rtcScriptPromise = null
function loadGo2rtcScript() {
  if (go2rtcScriptPromise) return go2rtcScriptPromise
  go2rtcScriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector('script[data-go2rtc]')
    if (existing) { resolve(); return }
    const script = document.createElement('script')
    script.type = 'module'
    script.src = `${CAMS_BASE}/video-stream.js`
    script.dataset.go2rtc = '1'
    script.onload = () => resolve()
    script.onerror = () => {
      go2rtcScriptPromise = null
      reject(new Error('Could not load video-stream.js from the backend proxy.'))
    }
    document.head.appendChild(script)
  })
  return go2rtcScriptPromise
}

/**
 * Live Ring camera view via the deer backend's /cams proxy to go2rtc.
 * Uses MSE over a same-origin WebSocket authenticated with the user's
 * Firebase ID token (no Cloudflare Access, no CORS).
 */
export default function CameraLiveView({ streamName, label }) {
  const containerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [errMsg, setErrMsg] = useState('')
  const [wsUrl, setWsUrl] = useState(null)

  useEffect(() => {
    let cancelled = false
    let pollId = null
    let timeoutId = null

    ;(async () => {
      try {
        const user = auth.currentUser
        if (!user) throw new Error('You must be signed in to view live cameras.')
        const token = await user.getIdToken()
        if (cancelled) return

        const url = new URL(CAMS_BASE)
        const proto = url.protocol === 'https:' ? 'wss' : 'ws'
        setWsUrl(
          `${proto}://${url.host}/cams/ws?src=${encodeURIComponent(streamName)}&token=${encodeURIComponent(token)}`
        )

        await loadGo2rtcScript()
        if (cancelled) return

        pollId = setInterval(() => {
          const video = containerRef.current?.querySelector('video')
          if (!video) return
          clearInterval(pollId); pollId = null
          const markPlaying = () => {
            if (cancelled) return
            setStatus('playing')
            video.removeEventListener('loadeddata', markPlaying)
            video.removeEventListener('playing', markPlaying)
          }
          video.addEventListener('loadeddata', markPlaying)
          video.addEventListener('playing', markPlaying)
          if (video.readyState >= 2) markPlaying()
        }, 250)

        timeoutId = setTimeout(() => {
          if (cancelled) return
          setStatus((s) => {
            if (s === 'playing') return s
            setErrMsg('No video received after 20s. Ring streams can be slow to start — try again.')
            return 'error'
          })
        }, 20000)
      } catch (e) {
        if (cancelled) return
        setErrMsg(e.message || String(e))
        setStatus('error')
      }
    })()

    return () => {
      cancelled = true
      if (pollId) clearInterval(pollId)
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [streamName])

  return (
    <div ref={containerRef} className="pm-livecam">
      {wsUrl && (
        /* eslint-disable-next-line react/no-unknown-property */
        <video-stream
          src={wsUrl}
          mode="mse"
          muted=""
          autoplay=""
          playsinline=""
          background=""
          class="pm-livecam__video"
        />
      )}
      {status === 'loading' && (
        <div className="pm-livecam__overlay">
          <div>Connecting to {label}…</div>
          <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: 4 }}>
            Ring live streams can take 5–15 s to start.
          </div>
        </div>
      )}
      {status === 'error' && (
        <div className="pm-livecam__overlay pm-livecam__overlay--error">
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Stream unavailable</div>
          <div style={{ fontSize: '0.75rem', color: '#cbd5e1', maxWidth: 360, textAlign: 'center' }}>
            {errMsg}
          </div>
        </div>
      )}
    </div>
  )
}
