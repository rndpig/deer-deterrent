// Polygon ring helpers — supports both legacy single-polygon items
// (`item.polygon: [[x,y], ...]`) and the new multi-ring format
// (`item.rings: [[[x,y], ...], [[x,y], ...]]`).
//
// On read, both shapes are normalized to an array of rings.
// On write, we always emit `rings` and drop `polygon` so the data model
// converges to MultiPolygon-style storage.

export function getRings(item) {
  if (item && Array.isArray(item.rings) && item.rings.length > 0) {
    return item.rings.filter(r => Array.isArray(r) && r.length >= 3)
  }
  if (item && Array.isArray(item.polygon) && item.polygon.length >= 3) {
    return [item.polygon]
  }
  return []
}

// Build a patch that updates the ring list and clears the legacy field.
export function ringsPatch(rings) {
  return { rings, polygon: undefined }
}

export function replaceRing(rings, ringIdx, newRing) {
  return rings.map((r, i) => (i === ringIdx ? newRing : r))
}

export function removeRing(rings, ringIdx) {
  return rings.filter((_, i) => i !== ringIdx)
}

export function appendRing(rings, newRing) {
  return [...rings, newRing]
}

export function pointsAttr(ring) {
  return ring.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')
}
