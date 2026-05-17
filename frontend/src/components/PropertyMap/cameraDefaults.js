// Hardware specs for known Ring cameras on the property.
// Sources: Ring product spec sheets (horizontal FOV).
// `range` is normalized to property width (~311 ft). Ring motion detection
// reliably reaches ~25-30 ft → ~0.08-0.10 normalized. We bump these up
// slightly so cones are clearly visible on the map.
export const CAMERA_MODELS = {
  '10cea9e4511f': { label: 'Woods',      model: 'Floodlight Cam',           fov_deg: 140, range: 0.20 },
  'c4dbad08f862': { label: 'Side',       model: 'Floodlight Cam Pro 2nd Gen', fov_deg: 140, range: 0.25 },
  '587a624d3fae': { label: 'Driveway',   model: 'Floodlight Cam',           fov_deg: 140, range: 0.20 },
  '4439c4de7a79': { label: 'Front Door', model: 'Wired Doorbell Plus',      fov_deg: 150, range: 0.15 },
  'f045dae9383a': { label: 'Back',       model: 'Floodlight Cam',           fov_deg: 140, range: 0.20 },
}

export const CAMERA_ID_LIST = Object.entries(CAMERA_MODELS).map(([id, m]) => ({
  id,
  label: m.label,
  model: m.model,
}))

export function getCameraDefaults(ringCameraId) {
  const m = CAMERA_MODELS[ringCameraId]
  if (!m) return null
  return { fov_deg: m.fov_deg, range: m.range }
}

export function getCameraModelInfo(ringCameraId) {
  return CAMERA_MODELS[ringCameraId] ?? null
}

// Maps Ring camera hex ID → go2rtc stream name (served by the deer-go2rtc relay container)
export const RING_ID_TO_STREAM_NAME = {
  '10cea9e4511f': '10cea9e4511f_live', // Woods
  'c4dbad08f862': 'c4dbad08f862_live', // Side (4K Floodlight Pro)
  '587a624d3fae': '587a624d3fae_live', // Driveway
  '4439c4de7a79': '4439c4de7a79_live', // Front Door
  'f045dae9383a': 'f045dae9383a_live', // Back
}
