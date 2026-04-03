# API Auth Implementation Progress

**Branch**: `feature/api-auth` (created from `main` at commit `35c609a`)
**Last Updated**: 2026-04-02 (evening — frontend complete)

## Roadmap Context

This is item #1 from the code review roadmap. The full roadmap is stored in:
`code-review-roadmap.md` (in Copilot memory, may get wiped between sessions)

**Roadmap items** (in priority order):
1. **Add API Authentication** ← IN PROGRESS
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

---

## What's NOT Done

### Coordinator — NOT STARTED
- [ ] Add `INTERNAL_API_KEY` env var to `Dockerfile.coordinator`
- [ ] Attach `X-API-Key` header to all HTTP calls to backend (POST/PATCH ring-events, GET settings, etc.)
- [ ] Add `INTERNAL_API_KEY` to `docker-compose.yml` environment for coordinator service

### ML-Detector — NOT STARTED
- [ ] Add `INTERNAL_API_KEY` env var to `Dockerfile.ml-detector`
- [ ] Attach `X-API-Key` header to settings sync calls (`GET /api/settings`)
- [ ] Add `INTERNAL_API_KEY` to `docker-compose.yml` environment for ml-detector service

### Infrastructure — NOT STARTED
- [ ] Add `INTERNAL_API_KEY` to `.env.example` (and generate a real value for server `.env`)
- [ ] Add `GOOGLE_APPLICATION_CREDENTIALS` path to docker-compose.yml backend service (optional — works without it)
- [ ] Update `docker-compose.yml` to pass `INTERNAL_API_KEY` env var to backend, coordinator, ml-detector
- [ ] Deploy and test end-to-end

### Testing — NOT STARTED
- [ ] Test: unauthenticated request to protected endpoint → 401
- [ ] Test: valid Firebase token → 200
- [ ] Test: valid API key → 200
- [ ] Test: invalid token/key → 401
- [ ] Test: coordinator can still communicate with backend
- [ ] Test: ml-detector settings sync still works
- [ ] Test: frontend login + API calls work
- [ ] Test: snapshot images still load in frontend

---

## Key Design Decisions Made
- **Middleware approach** (not per-route `Depends()`) — simpler, catches everything by default
- **GET /api/settings is open** — coordinator/ml-detector poll it every 30s, simplifies rollout
- **Image-serving GET endpoints are open** — `<img>` tags can't send auth headers; images are just deer photos (low risk); frontend gates access behind Firebase login
- **WebSocket skipped in middleware** — needs separate handling (future: send token as query param)
- **`apiFetch` handles both paths and full URLs** — `pathOrUrl.startsWith('http')` check for backward compatibility

## Suggested Next Step
Wire up the coordinator and ml-detector services with `X-API-Key` headers, add `INTERNAL_API_KEY` to docker-compose.yml and .env, then deploy and test end-to-end.
