# API Auth Implementation Progress

**Branch**: `feature/api-auth` (created from `main` at commit `35c609a`)
**Last Updated**: 2026-04-03 (coordinator + deployment complete)

## Roadmap Context

This is item #1 from the code review roadmap. The full roadmap is stored in:
`code-review-roadmap.md` (in Copilot memory, may get wiped between sessions)

**Roadmap items** (in priority order):
1. **Add API Authentication** ← COMPLETE
2. Enable SQLite WAL Mode + Busy Timeout
3. Fix Temp Video File Leak in Coordinator  
4. Remove Docker Socket Mount + Legacy Postgres Container
5. Extract Coordinator/ML-Detector Code from Dockerfiles

---

## What's Done

### Backend `auth.py` — COMPLETE
- Two auth mechanisms: Firebase ID Token (frontend) + Internal API Key (services)
- `_verify_firebase_token()` — validates via Firebase Admin SDK
- `_verify_api_key()` — constant-time comparison via `hmac.compare_digest()`
- `require_auth` dependency — accepts either mechanism
- `require_service_auth` dependency — API key preferred, Firebase fallback
- Lazy Firebase Admin SDK initialization (with/without service account)
- `firebase-admin>=6.0.0` added to `backend/requirements.txt`

### Backend `main.py` middleware — COMPLETE
- HTTP middleware added that enforces auth on all endpoints by default
- Open paths (no auth): `/`, `/health`, `/api/health`, `/docs`, `/openapi.json`, `/redoc`
- `GET /api/settings` open (coordinator + ml-detector poll this without auth)
- `GET` requests to image/file-serving prefixes open (for `<img>`/`<video>` tags):
  - `/api/snapshots/`, `/api/training-frames/`, `/api/frames/`, `/api/images/`, `/api/videos/`
- `/ws` WebSocket bypasses middleware (handled separately)
- `OPTIONS` always allowed (CORS preflight)
- Sets `request.state.user_id` and `request.state.auth_type` on success
- Returns 401 JSON responses on failure

### Frontend `api.js` + all components — COMPLETE
- Created `frontend/src/api.js` — centralized authenticated fetch wrapper
  - `apiFetch(pathOrUrl, options)` — automatically attaches Firebase ID token via `Authorization: Bearer <token>`
  - Handles both relative paths (`/api/...`) and full URLs (`https://...`)
  - Exports `API_URL` constant for image src attributes
- Updated ALL 13 components to use `apiFetch()` instead of raw `fetch()`
- Image `<img src>` attributes use `${API_URL}/api/snapshots/...` (no auth needed — backend allows GET to image endpoints)
- Build verified: `npx vite build` succeeds

### Coordinator — COMPLETE (2026-04-03)
- Added `INTERNAL_API_KEY` to CONFIG dict with `os.getenv("INTERNAL_API_KEY", "")`
- Created `get_api_headers()` helper that returns `{"Content-Type": "application/json", "X-API-Key": <key>}`
- Updated all backend API calls to include `headers=get_api_headers()`:
  - `log_ring_event()` — POST /api/ring-events
  - `log_to_backend()` — POST /api/detections  
  - PATCH /api/ring-events/{id} (two locations: motion detection + video frames)
  - POST /api/cleanup-old-snapshots

### ML-Detector — N/A (no changes needed)
- ml-detector only calls `GET /api/settings` which is open (no auth required)

### Infrastructure — COMPLETE (2026-04-03)
- Added `INTERNAL_API_KEY=${INTERNAL_API_KEY:-}` to docker-compose.yml:
  - backend service
  - coordinator service
- Added `INTERNAL_API_KEY=` with generation instructions to `.env.example`
- Generated secure key and added to server `.env`: `D__V-h82DeA-pDme5zb562JxPB-RcfEQJkZM6qvzZbc`
- Deployed: backend + coordinator rebuilt and restarted

### Testing — COMPLETE (2026-04-03)
- ✓ Unauthenticated request to /api/ring-events → 401
- ✓ Valid API key with X-API-Key header → 200
- ✓ Coordinator PATCH /api/ring-events → 200 OK (verified in logs)
- ✓ Coordinator POST /api/detections → 200 OK (verified in logs)
- ✓ Settings sync still works (GET /api/settings is open)

---

## Key Design Decisions Made
- **Middleware approach** (not per-route `Depends()`) — simpler, catches everything by default
- **GET /api/settings is open** — coordinator/ml-detector poll it every 30s, simplifies rollout
- **Image-serving GET endpoints are open** — `<img>` tags can't send auth headers; images are just deer photos (low risk); frontend gates access behind Firebase login
- **WebSocket skipped in middleware** — needs separate handling (future: send token as query param)
- **`apiFetch` handles both paths and full URLs** — `pathOrUrl.startsWith('http')` check for backward compatibility
- **ML-detector doesn't need changes** — only calls GET /api/settings which is open

## Remaining Work
- [ ] Test frontend login + API calls work (need to deploy frontend or test locally)
- [ ] Merge `feature/api-auth` branch to `main` after frontend verification
- [ ] (Optional) Add WebSocket authentication (low priority — WS only sends snapshot updates)
