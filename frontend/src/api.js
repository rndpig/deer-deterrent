import { auth } from './firebase'

export const API_URL = import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'

async function getAuthHeaders() {
  const user = auth.currentUser
  if (!user) return {}
  try {
    const token = await user.getIdToken()
    return { 'Authorization': `Bearer ${token}` }
  } catch {
    return {}
  }
}

export async function apiFetch(pathOrUrl, options = {}) {
  const authHeaders = await getAuthHeaders()
  const { headers: optionHeaders, ...rest } = options
  const url = pathOrUrl.startsWith('http') ? pathOrUrl : `${API_URL}${pathOrUrl}`
  const response = await fetch(url, {
    ...rest,
    headers: { ...authHeaders, ...optionHeaders },
  })
  return response
}
