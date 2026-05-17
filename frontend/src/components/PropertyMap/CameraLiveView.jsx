import { useEffect, useState } from 'react'

const CAM_STREAM_URL =
  import.meta.env.VITE_CAM_STREAM_URL || 'https://cam-stream.rndpig.com'

// Guard: only inject the go2rtc video-stream.js script once per page load
let go2rtcScriptInjected = false

/**
 * Renders a live camera stream from the go2rtc relay (deer-go2rtc container)
 * via the go2rtc <video-stream> web component over WebSocket (MSE mode).
 *
 * MSE mode is used because the server is on a private LAN behind Cloudflare;
 * WebRTC UDP ICE won't traverse the Cloudflare HTTP tunnel for remote users.
 * MSE streams entirely over WebSocket (wss://) which Cloudflare proxies fine.
 *
 * Stream teardown happens automatically when the component unmounts because
 * React removes the <video-stream> element from the DOM, triggering the web
 * component's disconnectedCallback which closes the WebSocket.
 */
export default function CameraLiveView({ streamName, label }) {
  // Show a "connecting" overlay for a few seconds while the WS + Ring cloud
  // stream establishes. go2rtc's web component handles subsequent error states.
  const [showOverlay, setShowOverlay] = useState(true)

  useEffect(() => {
    // Inject go2rtc's video-stream.js web component script once
    if (!go2rtcScriptInjected) {
      const script = document.createElement('script')
      script.type = 'module'
      script.src = `${CAM_STREAM_URL}/video-stream.js`
      document.head.appendChild(script)
      go2rtcScriptInjected = true
    }

    // Give the WS + Ring cloud ~5 s to connect before removing the overlay
    const t = setTimeout(() => setShowOverlay(false), 5000)
    return () => clearTimeout(t)
  }, [])

  // Build the WebSocket URL for this stream
  const wsUrl = `wss://${new URL(CAM_STREAM_URL).host}/api/ws?src=${streamName}`

  return (
    <div style={{ position: 'relative', width: '100%', maxWidth: 480, background: '#0f172a' }}>
      {showOverlay && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#0f172a',
            color: '#94a3b8',
            fontSize: '0.75rem',
            zIndex: 1,
            aspectRatio: '16/9',
          }}
        >
          Connecting to {label}…
        </div>
      )}
      {/*
        go2rtc custom element registered by video-stream.js.
        React passes all props as DOM attributes (strings), which go2rtc expects.
        On unmount React removes this element → disconnectedCallback → WS closes.
        mode="mse,webrtc": prefer MSE (works through Cloudflare), fall back to WebRTC (LAN).
      */}
      {/* eslint-disable-next-line react/no-unknown-property */}
      <video-stream
        src={wsUrl}
        mode="mse,webrtc"
        style={{ width: '100%', aspectRatio: '16/9', background: '#000', display: 'block' }}
      />
    </div>
  )
}
