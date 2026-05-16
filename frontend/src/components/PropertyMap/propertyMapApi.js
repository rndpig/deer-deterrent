import { API_URL, apiFetch } from '../../api'

export async function fetchOverlays() {
  const res = await fetch(`${API_URL}/api/property-map/overlays`)
  if (!res.ok) throw new Error(`Failed to fetch overlays: ${res.status}`)
  return res.json()
}

export async function putOverlays(doc) {
  const res = await apiFetch('/api/property-map/overlays', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Save failed: ${res.status} ${text}`)
  }
  return res.json()
}

export async function postImage(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetch('/api/property-map/image', {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Upload failed: ${res.status} ${text}`)
  }
  return res.json()
}

export const imageUrl = () => `${API_URL}/api/property-map/image`
