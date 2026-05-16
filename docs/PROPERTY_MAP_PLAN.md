# Property Map Feature — Implementation Plan

**Status:** Ready for implementation
**Owner repo (source of truth):** `deer-deterrent`
**Consumer repo (read-only):** `weather-monitor`
**Created:** 2026-05-15

---

## 1. Goal

Provide a top-down property map (existing landscape rendering, 1782×768 PNG) as a new top-level `Map` tab in both apps. Users can place and reposition overlay elements:

- **Cameras** — point + facing direction + FOV cone (deer app)
- **Irrigation zones** — polygon outlines (deer app, optional layer in weather)
- **Soil/light sensors** — point markers (weather app, optional layer in deer)
- **Structures / labels** — point text annotations (both apps)

Edit mode is gated behind Firebase auth (only the owner). View mode is available to authenticated users only (deer app already requires auth). Weather app frontend reads the property config publicly over CORS.

---

## 2. Architecture summary

```
┌────────────────────────────┐         ┌──────────────────────────┐
│  deer-deterrent backend     │  HTTPS  │   weather-monitor        │
│  (FastAPI, Docker)          │◀────────│   frontend (React)       │
│                             │  read   │   (browser, public)      │
│  Source of truth:           │         └──────────────────────────┘
│   - PNG file                │
│   - overlay JSON in SQLite  │         ┌──────────────────────────┐
│                             │◀────────│   deer-deterrent         │
│  Endpoints:                 │  read   │   frontend (React)       │
│   GET  /api/property-map/.. │  +write │   (Firebase-authed)      │
│   PUT  /api/property-map/.. │         └──────────────────────────┘
└─────────────────────────────┘
```

**Why this shape:** the deer backend already has Firebase auth, CORS middleware, SQLite, and image-serving patterns. Adding a tiny `property_overlay` resource there is cheaper than standing up a third service.

---

## 3. Data model

### 3.1 Overlay JSON (single document, versioned)

```json
{
  "schema_version": 1,
  "updated_at": "2026-05-15T22:14:00-05:00",
  "image": {
    "url": "/api/property-map/image",
    "intrinsic_width": 1782,
    "intrinsic_height": 768
  },
  "layers": [
    {
      "id": "cameras",
      "name": "Cameras",
      "icon": "camera",
      "default_visible_in": ["deer"],
      "items": [
        {
          "id": "cam-side",
          "type": "camera",
          "label": "Side",
          "x": 0.62,
          "y": 0.45,
          "rotation_deg": 0,
          "fov_deg": 110,
          "range": 0.18,
          "color": "#3b82f6",
          "meta": { "ring_camera_id": "c4dbad08f862" }
        }
      ]
    },
    {
      "id": "zones",
      "name": "Irrigation Zones",
      "icon": "droplet-fill",
      "default_visible_in": ["deer"],
      "items": [
        {
          "id": "zone-2",
          "type": "polygon",
          "label": "Garage North",
          "color": "#4ade80",
          "fill_opacity": 0.35,
          "stroke_width": 2,
          "polygon": [[0.55, 0.4], [0.6, 0.42], [0.58, 0.5]],
          "meta": { "rainbird_zone": 2 }
        }
      ]
    },
    {
      "id": "sensors",
      "name": "Sensors",
      "icon": "droplet",
      "default_visible_in": ["weather"],
      "items": [
        {
          "id": "soil-1",
          "type": "marker",
          "label": "Front bed",
          "x": 0.71,
          "y": 0.38,
          "color": "#06b6d4",
          "meta": { "channel": 1, "kind": "soil_moisture" }
        }
      ]
    },
    {
      "id": "labels",
      "name": "Labels",
      "icon": "type",
      "default_visible_in": ["deer", "weather"],
      "items": [
        { "id": "label-house", "type": "label", "label": "House", "x": 0.7, "y": 0.4 }
      ]
    }
  ]
}
```

**Conventions:**
- All `x`, `y`, `range`, polygon coords are **normalized 0-1** relative to image width/height.
- `rotation_deg`: 0 = north (up), 90 = east, clockwise positive.
- `color`: hex with `#` prefix.
- `id` values are stable strings (cameras like `cam-side`, zones like `zone-2`, sensors free-form).
- `meta` is an open object — app-specific fields (ring_camera_id, rainbird_zone, sensor channel) live here.
- `default_visible_in` controls which app turns the layer on by default. User can override via toolbar toggle (persisted in localStorage per browser).
- `app_visibility` is **not** restricted — all layers are readable by both apps; visibility is purely a UX default.

### 3.2 Database table (deer-deterrent SQLite)

```sql
CREATE TABLE IF NOT EXISTS property_overlay (
  id           INTEGER PRIMARY KEY CHECK (id = 1),  -- enforce single row
  data_json    TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  updated_by   TEXT
);
```

Single-row table. `data_json` stores the entire document above. On first GET, if no row exists, return the default empty config.

### 3.3 Image asset

- Path on disk: `backend/data/property-map.png`
- Served by backend with `Cache-Control: public, max-age=86400` and an ETag (sha256 of file bytes, computed at startup and on upload).
- Mounted into the backend container via the existing `./backend/data:/app/data` volume.

---

## 4. Backend changes (deer-deterrent)

### 4.1 Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/main.py` | edit | Add 4 endpoints + open paths + CORS update |
| `backend/database.py` | edit | Add `init_property_overlay_table()` + getters/setters |
| `backend/data/property-map.png` | create | Default image bundled in repo (user-attached PNG) |
| `scripts/seed_property_overlays.py` | create | Seed overlays from existing `camera_zones` setting |

### 4.2 Endpoints (all under `/api/property-map`)

| Method | Path | Auth | Response |
|--------|------|------|----------|
| `GET`  | `/image` | open | `image/png` with ETag + Cache-Control |
| `POST` | `/image` | required | multipart `file=<png>`, replaces PNG, returns `{intrinsic_width, intrinsic_height}` |
| `GET`  | `/overlays` | open | Overlay JSON document |
| `PUT`  | `/overlays` | required | Body = full JSON document, replaces row |
| `GET`  | `/health` | open | `{ok, has_image, overlays_count}` |

**Implementation notes:**
- `GET /image`: read file once at startup into memory if <5 MB; otherwise stream from disk. Compute ETag at upload time, store in module-level `_image_etag`.
- `POST /image`: validate `content_type == 'image/png'` and size ≤ 5 MB. Open with Pillow to validate + extract `intrinsic_width/height`. Update overlay JSON's `image.intrinsic_width/height` automatically if they differ.
- `PUT /overlays`: validate schema with a small Pydantic model (next section). Reject if `schema_version != 1`. Set `updated_at = now()`, `updated_by = current user email if available`.
- All four endpoints **must be added to `OPEN_PATHS` selectively** — only `/image`, `/overlays` (GET only), `/health`. PUT/POST go through the existing auth middleware.

### 4.3 Pydantic models

```python
# backend/models_property_map.py (new file, or inline in main.py)
from pydantic import BaseModel, Field, conlist
from typing import Literal, List, Dict, Any, Optional

class Point(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)

class CameraItem(BaseModel):
    id: str
    type: Literal["camera"]
    label: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    rotation_deg: float = 0
    fov_deg: float = Field(default=90, ge=10, le=360)
    range: float = Field(default=0.15, ge=0.01, le=1)
    color: str = "#3b82f6"
    meta: Dict[str, Any] = {}

class PolygonItem(BaseModel):
    id: str
    type: Literal["polygon"]
    label: str
    color: str = "#4ade80"
    fill_opacity: float = 0.35
    stroke_width: float = 2
    polygon: conlist(conlist(float, min_length=2, max_length=2), min_length=3)
    meta: Dict[str, Any] = {}

class MarkerItem(BaseModel):
    id: str
    type: Literal["marker", "label"]
    label: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    color: str = "#06b6d4"
    meta: Dict[str, Any] = {}

class Layer(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    default_visible_in: List[str] = []
    items: List[Any]  # discriminated union below if desired

class OverlayImage(BaseModel):
    url: str = "/api/property-map/image"
    intrinsic_width: int
    intrinsic_height: int

class OverlayDocument(BaseModel):
    schema_version: Literal[1] = 1
    updated_at: Optional[str] = None
    image: OverlayImage
    layers: List[Layer]
```

### 4.4 CORS update

In `backend/main.py`, the `CORSMiddleware` `allow_origins` list must include the weather domain:

```python
allow_origins=[
    "http://localhost:5173",
    "https://deer-deterrent-rnp.web.app",
    "https://weather-monitor-rnp.web.app",  # NEW — read-only access to property map
],
```

### 4.5 Seed script

`scripts/seed_property_overlays.py`:
- Reads `camera_zones` from current settings via `GET /api/settings` (or directly from SQLite)
- Builds a default overlay document with one camera per known Ring ID (positions guessed from the camera layout in copilot-instructions.md) and one zone polygon per Rainbird zone referenced
- Polygons get a tiny triangle as a placeholder; user repositions in the UI
- Writes via `PUT /api/property-map/overlays`

Run once manually after first deploy. Idempotent — overwrites whatever's there.

---

## 5. Frontend changes (deer-deterrent)

### 5.1 New files

```
frontend/src/components/PropertyMap/
├── PropertyMap.jsx         # Container: fetches data, wires save, owns global state
├── MapCanvas.jsx           # The interactive image + SVG overlay
├── MapToolbar.jsx          # Top bar: edit toggle, layer toggles, add menu, save
├── EditorPanel.jsx         # Right-side panel for selected item editing
├── ImageUploadModal.jsx    # Modal to upload a new base PNG
├── propertyMapApi.js       # API client helpers (fetch/put/post)
├── usePointerDrag.js       # Pointer-event drag hook (mouse + touch)
├── coords.js               # Normalized ↔ pixel conversion helpers
└── PropertyMap.css
```

### 5.2 `App.jsx` changes

- Add `import PropertyMap from './components/PropertyMap/PropertyMap'`
- Insert new tab button between Stats and Settings: `<button onClick={() => setActiveTab('map')}>Map</button>`
- Render `{activeTab === 'map' && <PropertyMap />}`

### 5.3 Component contracts

#### `PropertyMap.jsx`
- On mount: parallel fetch `/api/property-map/overlays` and `useAuth()` user
- State: `overlay`, `selectedItemId`, `editMode` (bool), `layerVisibility` (Map<layerId, bool>, init from `default_visible_in` for `deer`, merged with localStorage), `dirty` (bool), `saving`
- Renders `<MapToolbar>` + `<MapCanvas>` + `<EditorPanel>`
- Provides callbacks to children: `updateItem(layerId, itemId, patch)`, `addItem(layerId, item)`, `deleteItem(layerId, itemId)`, `setLayerVisible(layerId, bool)`
- Auto-save: debounced 2s after `dirty` becomes true (only when authenticated). Show "Saving…" / "Saved" indicator in toolbar.

#### `MapCanvas.jsx`
- Props: `overlay`, `visibleLayers`, `selectedItemId`, `editMode`, callbacks
- Layout:
  - Outer `<div class="map-container">` with `position: relative`, `aspect-ratio: <intrinsic_width / intrinsic_height>`
  - `<img>` filling the container
  - `<svg viewBox="0 0 100 100" preserveAspectRatio="none">` absolutely positioned, full size — used for **polygons and camera FOV cones** (scale-invariant via viewBox)
  - HTML `<div>` markers absolutely positioned with `left: ${x*100}%; top: ${y*100}%; transform: translate(-50%, -50%)`
- Click on empty canvas → deselect
- In edit mode: pin/vertex pointerdown → start drag via `usePointerDrag`
- Polygon click: select polygon, render vertex handles (small `<circle>`s in SVG) + edge midpoint "+ insert" handles
- Right-click vertex → delete (min 3 enforced)
- Camera item is an SVG group: FOV wedge (`<path>` with arc) + circle + arrow. Drag = move; in edit mode, secondary handle on the arrow tip drags to rotate.

#### `MapToolbar.jsx`
- Left: title "Property Map"
- Center: Layer visibility toggles (chip per layer with icon + label, click to toggle)
- Right:
  - View/Edit mode toggle (only shown if user authenticated; defaults to View)
  - In edit mode: `+ Add` dropdown (Camera / Zone / Sensor / Label), "Upload new base image" button
  - Save status: "Saved" / "Saving…" / "Unsaved changes"

#### `EditorPanel.jsx`
- Hidden when nothing selected or in view mode
- Slides in from right
- For cameras: Label, Color, Rotation slider (-180 to 180), FOV slider (10-360), Range slider (0.01-1), Ring camera ID dropdown, Delete button
- For polygons: Label, Color, Fill opacity slider, Stroke width, Rainbird zone number, Delete
- For markers: Label, Color, Sensor metadata fields, Delete
- For labels: Label text, Delete
- All changes call `updateItem` immediately (no separate "Apply" button)

### 5.4 View-mode interactions (deer app)

- Click camera → open small popover showing latest snapshot from `/api/snapshots?camera_id={ring_camera_id}&limit=1`, with "View all" link to Dashboard pre-filtered to that camera
- Click polygon → confirmation dialog "Run zone X for 30 seconds?" → POST to existing `/api/test-irrigation` with `{zones: [n], duration: 30}`
- Click marker (sensor) in deer app → tooltip only (sensors aren't actionable here)
- Click label → no-op

### 5.5 Coordinate helpers

```js
// coords.js
export const pixelToNormalized = (px, py, rect) => ({
  x: clamp01((px - rect.left) / rect.width),
  y: clamp01((py - rect.top) / rect.height),
});
export const normalizedToPercent = (n) => `${n * 100}%`;
const clamp01 = (v) => Math.max(0, Math.min(1, v));
```

### 5.6 Drag hook

```js
// usePointerDrag.js — captures pointer events on a target element
// Returns onPointerDown(e) — caller binds; hook calls onMove(normalizedPos) during drag
```

Use `setPointerCapture` so drags continue even if the cursor leaves the element.

### 5.7 Polygon editor algorithm

- Vertex move: drag handle → update `polygon[i] = [newX, newY]`
- Vertex add: click midpoint handle between vertex `i` and `i+1` → insert new vertex at midpoint into array at `i+1`
- Vertex delete: right-click handle → remove from array (reject if `polygon.length <= 3`)
- New polygon spawn: drop a default triangle near image center: `[[0.45,0.45],[0.55,0.45],[0.5,0.55]]`

---

## 6. Frontend changes (weather-monitor)

### 6.1 New files

```
frontend/src/components/PropertyMap/
├── PropertyMap.tsx         # Read-only viewer
├── MapCanvas.tsx           # Same rendering as deer, no edit logic
├── propertyMapApi.ts       # Fetches from deer backend
├── coords.ts
└── PropertyMap.css
```

Port from deer-deterrent JSX → TypeScript. The viewer is roughly 40% of the code of the editor (no drag, no editor panel, no save).

### 6.2 Configuration

- New env var: `VITE_PROPERTY_MAP_BASE_URL` — defaults to `https://deer-api.rndpig.com`
- Fetch `${BASE_URL}/api/property-map/overlays` and `${BASE_URL}/api/property-map/image`
- No write access — no edit UI surfaced

### 6.3 `App.tsx` changes

- Add Map tab (or render alongside Dashboard cards — recommend new tab for parity with deer)
- Layer defaults: sensors on, cameras off, zones off (toolbar toggles persist in localStorage)

### 6.4 View-mode interactions (weather app)

- Click sensor marker → popover showing current reading from existing weather endpoints + 24h sparkline
  - For soil moisture: read `/api/current` and pull the relevant `soilhum1..soilhum8` channel matched via `meta.channel`
  - For light sensors: read `/api/light/current` matched via `meta.name`
- Click camera → display label only (cameras are informational in weather context)
- Click zone → display label only

---

## 7. Deployment steps (for the implementing agent)

### 7.1 Deer-deterrent (backend + frontend)

```powershell
# 1. Place the user's PNG locally
# (User has attached property-map.png; copy to backend/data/property-map.png)

# 2. After implementing code:
git add backend/main.py backend/database.py backend/data/property-map.png `
        frontend/src/App.jsx frontend/src/components/PropertyMap/ `
        scripts/seed_property_overlays.py docs/PROPERTY_MAP_PLAN.md
git commit -m "feat: property map with cameras, zones, sensors, labels (deer)"
git push

# 3. Deploy backend
ssh dilger 'cd /home/rndpig/deer-deterrent && git pull && docker compose up -d --force-recreate backend'

# 4. Copy PNG into the backend's data volume (the file is in git, so this happens automatically via the bind mount)
ssh dilger 'ls -la /home/rndpig/deer-deterrent/backend/data/property-map.png'

# 5. Verify endpoints
ssh dilger 'curl -s http://localhost:8000/api/property-map/health | python3 -m json.tool'
ssh dilger 'curl -sI http://localhost:8000/api/property-map/image | head -10'

# 6. Seed overlays
ssh dilger 'cd /home/rndpig/deer-deterrent && python3 scripts/seed_property_overlays.py'

# 7. Build + deploy frontend
cd frontend; npm run build; firebase deploy --only hosting
```

### 7.2 Weather-monitor (frontend only)

```powershell
# 1. After implementing code:
git add frontend/src/App.tsx frontend/src/components/PropertyMap/
git commit -m "feat: property map read-only viewer with sensor overlay"
git push

# 2. Build + deploy
cd frontend; npm run build; firebase deploy --only hosting
```

No weather backend changes needed.

---

## 8. Testing checklist (manual — no automated tests per project convention)

### Deer-deterrent
- [ ] Map tab renders the PNG at correct aspect ratio
- [ ] Cameras appear at their saved positions with correct rotation
- [ ] Zones render as filled polygons with correct colors
- [ ] Edit mode toggle appears only when logged in
- [ ] Drag a camera → position updates, auto-saves within 2s
- [ ] Rotate a camera via the arrow handle → FOV cone updates live
- [ ] Add a new zone → triangle appears at center, vertices draggable
- [ ] Insert a vertex via midpoint handle
- [ ] Delete a vertex (right-click) — blocked at 3 vertices
- [ ] Layer toggles hide/show items; persists across page reload
- [ ] View mode: click camera → latest snapshot popover loads
- [ ] View mode: click zone → "Run zone X for 30s" confirmation works
- [ ] Upload a new base image → intrinsic dimensions update, overlays preserved (positions still valid since normalized)
- [ ] Unauthenticated GET to `/api/property-map/overlays` returns data (open path)
- [ ] Unauthenticated PUT returns 401

### Weather-monitor
- [ ] Map tab loads from deer backend without CORS errors
- [ ] Sensor markers appear at correct positions
- [ ] Click sensor → current reading + sparkline displayed
- [ ] Layer toggles work, persist
- [ ] No edit controls visible

---

## 9. Out of scope (do not implement)

- Snap-to-grid in edit mode
- Undo/redo
- Multi-user collaborative editing
- Image cropping / rotation tools
- Camera FOV calibration via reference images
- Heatmap overlay of deer detections (could come later as a new layer type)
- Mobile-specific gestures beyond basic touch drag (pinch-zoom, two-finger pan)
- Polygon self-intersection detection

---

## 10. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| CORS misconfiguration blocks weather frontend | Implementer must update `allow_origins` in `main.py`; verify with browser devtools |
| Image too large (>5 MB) | Backend rejects upload with 413; UI shows a clear error |
| Schema drift between apps | Schema is centralized in deer backend; weather only reads. If the schema must change, bump `schema_version`. |
| User accidentally deletes an item | Auto-save means there's no undo. Mitigation: show a confirmation dialog on Delete in the EditorPanel. |
| Polygon with <3 vertices saved | Pydantic `min_length=3` enforces server-side |
| Existing `camera_zones` setting and overlay JSON drift | Seed script (`scripts/seed_property_overlays.py`) re-syncs on demand. Document this in the seed script's docstring. |

---

## 11. Open questions for the implementing agent

These are minor — the agent should pick reasonable defaults and flag in the PR description:

1. Snap drag positions to nearest 0.5% increment? (Recommend yes, for cleaner visuals)
2. Show coordinate readout (`x: 0.62, y: 0.45`) in EditorPanel? (Recommend yes during MVP for debugging)
3. Confirmation dialog on Delete? (Recommend yes)
4. Auto-save delay: 2s after last edit, or explicit Save button? (Recommend auto-save + visible status)
5. Layer toggle persistence: localStorage per browser, or per-user via a settings endpoint? (Recommend localStorage; the only user is the owner anyway)

---

## 12. File-by-file summary for the implementing agent

### Deer-deterrent — create
- `backend/data/property-map.png` (place the user's PNG here; commit to git)
- `backend/models_property_map.py` (or inline models in `main.py`)
- `scripts/seed_property_overlays.py`
- `frontend/src/components/PropertyMap/PropertyMap.jsx`
- `frontend/src/components/PropertyMap/MapCanvas.jsx`
- `frontend/src/components/PropertyMap/MapToolbar.jsx`
- `frontend/src/components/PropertyMap/EditorPanel.jsx`
- `frontend/src/components/PropertyMap/ImageUploadModal.jsx`
- `frontend/src/components/PropertyMap/propertyMapApi.js`
- `frontend/src/components/PropertyMap/usePointerDrag.js`
- `frontend/src/components/PropertyMap/coords.js`
- `frontend/src/components/PropertyMap/PropertyMap.css`

### Deer-deterrent — edit
- `backend/main.py` — 4 endpoints, CORS update, open paths additions
- `backend/database.py` — `property_overlay` table init + getters/setters
- `frontend/src/App.jsx` — new tab

### Weather-monitor — create
- `frontend/src/components/PropertyMap/PropertyMap.tsx`
- `frontend/src/components/PropertyMap/MapCanvas.tsx`
- `frontend/src/components/PropertyMap/propertyMapApi.ts`
- `frontend/src/components/PropertyMap/coords.ts`
- `frontend/src/components/PropertyMap/PropertyMap.css`

### Weather-monitor — edit
- `frontend/src/App.tsx` — new tab
- `frontend/.env.example` — document `VITE_PROPERTY_MAP_BASE_URL`

---

## 13. Acceptance criteria

The feature is complete when:

1. Both apps show a working Map tab with the base PNG and overlays.
2. In the deer app, an authenticated user can drag cameras/zones/markers and changes auto-save.
3. Polygon zones can be added, with vertices added/moved/deleted.
4. View-mode clicks on cameras open the latest snapshot.
5. View-mode clicks on zones trigger a confirmation to run irrigation.
6. The weather app reads the overlay over CORS without errors and shows sensor markers with live readings.
7. Layer visibility toggles work in both apps and persist across reloads.
8. Unauthenticated PUT/POST returns 401; unauthenticated GET works.
