# Code Review — Deer Deterrent System
**Date**: 2026-02-08
**Scope**: Full codebase review of backend, database, Docker stack, ML detector, coordinator, and frontend

---

## Summary

| Severity | Found | Fixed | Remaining |
|----------|-------|-------|-----------|
| Critical | 4 | 4 | 0 |
| Moderate | 5 | 5 | 0 |
| Non-Critical | 7 | 6 | 1 |
| **Total** | **16** | **15** | **1** |

---

## Critical Issues (All Fixed)

### 1. SQL Injection in `database.py` — `get_ring_events()`
- **File**: `backend/database.py`, `get_ring_events()` function
- **Problem**: Used Python `.format(hours)` to interpolate user-controlled `hours` parameter directly into SQL query string, enabling SQL injection.
- **Fix**: Changed to parameterized query using `?` placeholder with `params = [f"-{int(hours)}"]`.

### 2. Path Traversal in 4 File-Serving Endpoints
- **File**: `backend/main.py`
- **Endpoints**: `/api/video-frames/{path}`, `/api/training-frames/{path}`, `/app/snapshots/{path}`, `/api/images/{path}`
- **Problem**: User-supplied path parameters were joined directly into filesystem paths without validation, allowing `../../../etc/passwd` style attacks.
- **Fix**: Added `..` component rejection, `Path.resolve()` canonicalization, and prefix validation to ensure resolved paths stay within allowed directories.

### 3. Duplicate `@app.on_event("startup")` Decorators
- **File**: `backend/main.py`
- **Problem**: Two functions both named `startup_event` with `@app.on_event("startup")` decorator. The second shadowed the first, preventing `db.init_database()` from running on startup.
- **Fix**: Renamed the first function to `startup_init_db` to avoid name collision.

### 4. Bare `except: pass` in `broadcast_message()`
- **File**: `backend/main.py`, `broadcast_message()` function
- **Problem**: Bare `except: pass` silently swallowed all exceptions (including `SystemExit`, `KeyboardInterrupt`), and never cleaned up disconnected WebSocket clients from the `active_websockets` list, causing the list to grow indefinitely.
- **Fix**: Changed to `except Exception`, added disconnected client tracking and cleanup after broadcast loop.

---

## Moderate Issues (All Fixed)

### 5. Timezone Defaults Mismatch in `docker-compose.yml`
- **File**: `docker-compose.yml` (6 occurrences)
- **Problem**: Default timezone was `America/New_York` but the Dell server and `.env` use `America/Chicago`. If `.env` was missing, containers would run in the wrong timezone, causing active-hours detection to be off by one hour.
- **Fix**: Changed all 6 default values from `America/New_York` to `America/Chicago`.

### 6. Confidence Threshold Defaults Too Low in `docker-compose.yml`
- **File**: `docker-compose.yml` (ml-detector and coordinator services)
- **Problem**: Default `CONFIDENCE_THRESHOLD` was `0.30`, but production uses `0.55`. If `.env` was missing, the system would generate excessive false positives.
- **Fix**: Changed defaults for both ml-detector and coordinator from `0.30` to `0.55`.

### 7. CLAHE Clip Limit Mismatch in ML Detector
- **File**: `Dockerfile.ml-detector`
- **Problem**: `CLAHE_CLIP_LIMIT` defaulted to `3.0` but the model was trained with `clip_limit=2.0`. Inference-time preprocessing didn't match training-time preprocessing, degrading detection accuracy.
- **Fix**: Changed default from `3.0` to `2.0`.

### 8. Model Version Strings Inconsistent Across Codebase
- **Files**: `Dockerfile.ml-detector`, `Dockerfile.coordinator`, `backend/main.py`, `frontend/src/components/SnapshotViewer.jsx`, `models/registry.json`, `.github/copilot-instructions.md`
- **Problem**: Some files referenced `YOLO26s v2.0` after model was upgraded to v3.0. Inconsistent version strings caused confusion in logs and frontend display.
- **Fix**: Updated all 10 occurrences across 6 files to `YOLO26s v3.0`.

### 9. Bare `except` Clauses in `database.py` and `main.py`
- **Files**: `backend/database.py` (1), `backend/main.py` (2)
- **Problem**: Bare `except:` catches everything including `SystemExit` and `KeyboardInterrupt`, masking bugs and making debugging difficult.
- **Fix**: Replaced with specific exception types (`json.JSONDecodeError, TypeError, ValueError` for JSON parsing; `ValueError, TypeError, OverflowError` for date parsing).

---

## Non-Critical Issues

### 10. Duplicate `import base64` (Fixed)
- **File**: `backend/main.py`, lines 20 and 108
- **Problem**: `base64` was imported at module level (line 20) and again inside a `try` block for OpenCV imports (line 108). Redundant import.
- **Fix**: Removed the duplicate import inside the `try` block.

### 11. Unauthenticated Debug Endpoint Exposing Environment Variables (Fixed)
- **File**: `backend/main.py`, `/api/debug/env` endpoint
- **Problem**: Exposed `GOOGLE_DRIVE_CREDENTIALS_PATH`, `GOOGLE_DRIVE_TRAINING_FOLDER_ID`, and all `GOOGLE`-prefixed environment variables to any unauthenticated caller. Information disclosure vulnerability.
- **Fix**: Removed the endpoint entirely. (If needed for debugging, should be behind authentication.)

### 12. Unbounded In-Memory `detection_history` List (Fixed)
- **File**: `backend/main.py`
- **Problem**: `detection_history` list grew without bound as detection events accumulated. On a long-running server, this would consume increasing memory.
- **Fix**: Added cap at 1000 entries — when exceeded, the oldest entries are trimmed.

### 13. In-Memory-Only Settings Storage (Not Fixed — Design Decision)
- **File**: `backend/main.py`
- **Problem**: System settings (`SystemSettings` Pydantic model) are stored only in memory. On backend restart, all settings revert to defaults. This includes confidence threshold, active hours, enabled cameras, and snapshot frequency.
- **Impact**: After any container restart, settings must be reconfigured via the frontend Settings page or API.
- **Recommendation**: Persist settings to the PostgreSQL database or a JSON file on the shared volume (`/app/data/settings.json`). Load on startup, write on change.
- **Status**: Not fixed — requires design decision on storage strategy.

### 14. Deprecated `@app.on_event` Usage (Not Fixed — Low Priority)
- **File**: `backend/main.py`
- **Problem**: Uses `@app.on_event("startup")` and `@app.on_event("shutdown")` which are deprecated in newer FastAPI versions. The recommended approach is the `lifespan` context manager.
- **Status**: Not fixed — functional, and migration is a larger refactor.

### 15. Missing Input Validation on Several Endpoints (Not Fixed — Low Priority)
- **File**: `backend/main.py`
- **Problem**: Several endpoints accept arbitrary JSON bodies (`dict` or `Request`) without Pydantic model validation. Examples include `PATCH /api/ring-events/{event_id}`, `POST /api/snapshots/{id}/archive`.
- **Status**: Not fixed — endpoints work correctly, but adding Pydantic request models would improve type safety and auto-documentation.

### 16. Docker Compose Comment Indentation (Not Fixed — Cosmetic)
- **File**: `docker-compose.yml`, line 13
- **Problem**: `  # Coordinator` comment has inconsistent indentation compared to other service-group comments.
- **Status**: Not fixed — purely cosmetic.

---

## Files Modified

| File | Changes |
|------|---------|
| `backend/main.py` | Path traversal fixes (4 endpoints), renamed duplicate startup_event, fixed broadcast_message bare except, removed debug/env endpoint, removed duplicate base64 import, capped detection_history, fixed 2 bare except clauses, updated model version strings |
| `backend/database.py` | SQL injection fix (parameterized query), fixed bare except clause |
| `docker-compose.yml` | Fixed timezone defaults (6x), confidence threshold defaults (2x) |
| `Dockerfile.ml-detector` | Fixed CLAHE clip_limit default, updated model version string |
| `Dockerfile.coordinator` | Updated model version string |
| `frontend/src/components/SnapshotViewer.jsx` | Updated fallback model version string |
| `models/registry.json` | Updated deployment history model version |
| `.github/copilot-instructions.md` | Updated documentation to reflect v3.0 |
