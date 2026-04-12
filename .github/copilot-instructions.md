# Deer Deterrent System — Chat Instructions for AI Agents
# Last Updated: 2026-04-11

## Project Overview

This is an AI-powered deer detection and deterrent system for a residential property. It monitors 4 Ring security cameras via MQTT, runs YOLO-based deer detection on snapshots, and can activate Rainbird irrigation zones to deter deer. The system runs on a Dell OptiPlex server on the owner's local network with a React dashboard hosted on Firebase.

**Owner**: Single developer ("rndpig" on GitHub, "rndpi" Windows user, "rndpig" Linux user)
**Timezone**: America/Chicago (Central Time)
**Repository**: https://github.com/rndpig/deer-deterrent.git

---

## Server & Network Architecture

### Dell Server ("Dilger")
- **IP**: 192.168.7.215
- **SSH alias**: `dilger` (resolves to rndpig@192.168.7.215)
- **Hardware**: Dell OptiPlex, Intel i7-4790, CPU-only (no GPU)
- **OS**: Ubuntu 24.04, system Python 3.12
- **Project path**: `/home/rndpig/deer-deterrent/`
- **Timezone**: America/Chicago (CST/CDT)

### Public Access
- **Frontend**: https://deer-deterrent-rnp.web.app (Firebase Hosting)
- **API**: https://deer-api.rndpig.com (Cloudflare Tunnel → localhost:8000)
- **Tunnel**: cloudflared.service (systemd), tunnel ID 48dab637-7544-4bb0-a38a-58e058145490

### Local Development
- **Windows machine**: C:\Users\rndpi\Documents\Coding Projects\deer-deterrent
- **Python venv**: .venv/ in project root
- **Frontend dev**: `cd frontend && npm run dev` (port 5173)

---

## Docker Stack (6 Containers)

All services run via `docker compose` on the Dell server. The stack is defined in `docker-compose.yml`.

| Container | Port | Image | Purpose |
|---|---|---|---|
| deer-backend | 8000 | deer-deterrent-backend | FastAPI API server, SQLite DB (ring events + training), WebSocket |
| deer-ml-detector | 8001 | deer-deterrent-ml-detector | YOLO26s inference with CLAHE preprocessing |
| deer-coordinator | 5000 | deer-deterrent-coordinator | Ring MQTT listener, orchestrates detection pipeline, irrigation |
| deer-db | 5432 | postgres:16-alpine | PostgreSQL (legacy — container exists but has no user tables; all data is in SQLite) |
| deer-mosquitto | 1883, 9001 | eclipse-mosquitto:2.0 | MQTT message broker |
| deer-ring-mqtt | 8554, 55123 | tsightler/ring-mqtt | Ring camera → MQTT bridge |

### Container Dependencies
```
mosquitto → ring-mqtt → coordinator
ml-detector → coordinator
backend → coordinator
```

> **Note**: The docker-compose.yml lists `database` (postgres) as a dependency of `backend`, but the backend does NOT use PostgreSQL. All data is stored in SQLite at `backend/data/training.db`. The postgres container is a legacy artifact.

### Key Volume Mounts
- `./backend/data:/app/data` — SQLite DB (ring events + training data; backend + coordinator shared)
- `./dell-deployment/data/snapshots:/app/snapshots` — Motion event snapshots
- `./dell-deployment/models:/app/models` — YOLO model files
- `./backend:/app` — Backend source code (live-mounted)

### Deployment Workflow
```bash
# Standard deploy cycle:
git add <files> && git commit -m "message" && git push
ssh dilger "cd /home/rndpig/deer-deterrent && git pull && docker compose build <services> && docker compose up -d --force-recreate <services>"
```

### Server .env
The server has its own `.env` at `/home/rndpig/deer-deterrent/.env` with production credentials. Key settings that differ from the local `.env.example`:
- `TIMEZONE=America/Chicago`
- `IOU_THRESHOLD=0.65`
- `CONFIDENCE_THRESHOLD=0.55`
- Real Ring token, Rainbird IP, Postgres password, JWT secret

---

## Ring Cameras (5 cameras)

| Camera | Ring-MQTT ID | Product | Detection Enabled |
|---|---|---|---|
| Woods | 10cea9e4511f | Floodlight Cam | YES (moved to barn, formerly Side) |
| Side | c4dbad08f862 | Floodlight Cam Pro (2nd Gen) | YES (new, 4K, 3D radar motion) |
| Driveway | 587a624d3fae | Floodlight Cam | No |
| Front Door | 4439c4de7a79 | Wired Doorbell Plus / Video Doorbell Pro | No |
| Back | f045dae9383a | Floodlight Cam | No |

- Ring-MQTT publishes snapshots to `ring/dp1hu9-2i94c-0/camera/{camera_id}/snapshot/image`
- Motion events come via `ring/+/camera/+/motion` topics
- Periodic snapshot polling runs during active hours (configurable, default 20:00-6:00 CST)
- All 5 cameras are polled for snapshots, but only enabled cameras run through ML detection

---

## Property Layout & Irrigation Zones

**Address**: 1409 Briarwood Lane, Mahomet, IL 61853 (Lot 202)

### Property Dimensions
- **East-West depth**: ~311-313' (varies slightly N to S)
- **North-South width**: 120' frontage on Briarwood Lane
- **Total area**: ~0.86 acres
- **Terrain**: House on east side, large wooded area extending west
- **Neighbors**: Lot 203 (1503) to the north, Lot 201 to the south

### Camera Positions & Orientations

| Camera | Mount Location | Height | Direction | Coverage |
|--------|---------------|--------|-----------|----------|
| Side | Above small garage door, below soffit | ~8' | North | Side yard toward lot 203 (1503), ~20' from property line |
| Driveway | Under soffit, north side of house | ~10' | East-NE | Driveway toward Briarwood Lane |
| Front Door | Doorbell mount | ~3' | East-SE | Front entry, partial street view |
| Back | Gable end of sunroom | ~15' | West-SW | Backyard into wooded area |
| Woods | Above rollup door on yard barn | ~8' | East | Deep in woods, looking back toward house |

### Irrigation Zones (Rainbird ESP-Me Controller)

| Zone | Name | Location | Camera Coverage |
|------|------|----------|-----------------|
| 1 | Driveway North | East side near street (front yard) | Driveway |
| 2 | Garage North | North side near garage, adjacent to Zone 5 | Side |
| 5 | Woods North | NW corner of property | Woods, Side |

*Additional zones (3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14) exist but are not currently mapped to deer detection.*

### Deer Travel Patterns
- **Primary corridor**: West → East from wooded area toward house/street
- **Side cam**: Deer consistently travel left-to-right (West→East) — entering from woods, heading toward street
- **Entry points**: Woods (western 2/3 of property) serves as deer habitat and travel corridor
- **Neighbor concern**: Side cam is ~20' from lot 203 — relevant for ultrasonic deterrent considerations
- **Zone handoff**: Zone 5 (NW) → Zone 2 (Side) → Zone 1 (Driveway) follows deer travel direction

### Camera-to-Zone Mapping
Configured via Settings page (`camera_zones` in `/api/settings`):
- **Side** → Zone 2 (Garage North)
- **Woods** → Zone 5 (Woods North)
- **Driveway** → Zone 1 (Driveway North)
- **Front Door** → (not currently mapped)
- **Back** → (not currently mapped)

---

## Detection Pipeline Flow

```
1. Ring camera detects motion (or periodic poll triggers)
2. Ring-MQTT publishes snapshot via MQTT
3. Coordinator receives snapshot, saves to disk
4. Coordinator sends image to ML-detector API (POST /detect)
5. ML-detector applies CLAHE preprocessing, runs YOLO26s inference
6. ML-detector returns {deer_detected, confidence, bboxes, model_version}
7. If deer_detected and confidence >= threshold:
   a. Coordinator PATCHes backend with results
   b. Coordinator triggers irrigation (if enabled and not in cooldown)
8. Backend stores event in SQLite ring_events table
9. Frontend dashboard shows events via WebSocket push
```

### Threshold Configuration
- **CONFIDENCE_THRESHOLD**: 0.55 (synced from backend settings to ml-detector every 30s)
- **IOU_THRESHOLD**: 0.65 (set via .env, NMS deduplication)
- **SNAPSHOT_FREQUENCY**: 60 (Ring camera capture frequency in seconds; options: 15, 30, 60, 180)
- ML-detector default from .env is overridden by backend settings via `fetch_settings_from_backend()`

### Settings Synchronization
- Coordinator and ML-detector both poll `GET /api/settings` from backend every 30 seconds
- This is how confidence_threshold, enabled_cameras, active_hours, and snapshot_frequency propagate
- Coordinator derives its polling interval as `snapshot_frequency + 10s` buffer
- To change settings: use the frontend Settings page or `PUT /api/settings`

---

## ML Model

### Current Production Model: YOLO26s v4.0
- **Architecture**: YOLO26s (from ultralytics >= 8.4.0)
- **File**: `dell-deployment/models/production/best.pt`
- **Version file**: `dell-deployment/models/production/VERSION` — contains "YOLO26s v4.0", read by ml-detector at startup
- **CLAHE preprocessing**: clip_limit=2.0, tile_grid_size=(8,8) — applied at inference time in ml-detector
- **Test metrics**: mAP50=0.883, mAP50-95=0.498, Precision=0.902, Recall=0.804

### Model Deployment
When deploying a new model:
1. Copy `best.pt` to `dell-deployment/models/production/`
2. Update `dell-deployment/models/production/VERSION` with version string (e.g., "YOLO26s v4.0")
3. Update `models/registry.json` with model metadata
4. Restart ml-detector: `docker compose restart ml-detector`

### Model Registry
See `models/registry.json` for full model history, dataset versions, and deployment history.

### Previous Models
- YOLO26s v3.0 — retired 2026-04-11, mAP50=0.855
- YOLO26s v2.0 (19.35 MB) — retired, see registry.json for details
- YOLOv8n baseline (5.94 MB) — retired 2026-02-07, backed up as `best.pt.backup_yolov8n_20260207`

### Training Pipeline
1. Annotate frames in frontend (bounding box tool)
2. Export dataset: `python3 scripts/export_dataset_v2.py` (on server)
3. Train: `python3 scripts/train_yolo26s_v2.py --data <data.yaml>` (in tmux on server)
4. Deploy: copy best.pt to models/production/, rebuild ml-detector container

---

## Backend API (backend/main.py)

The backend is a large FastAPI application (~4400 lines) serving multiple purposes:

### Core API Groups
- **Ring Events**: POST/GET/PATCH `/api/ring-events` — event ingestion and updates
- **Snapshots**: GET/POST `/api/snapshots` — snapshot viewing, archiving, re-detection
- **Settings**: GET/PUT `/api/settings` — system configuration (threshold, active hours, cameras)
- **Training**: GET/POST `/api/training/*` — annotation export, model training, deployment
- **Videos**: GET/POST/DELETE `/api/videos/*` — video upload, frame extraction, annotation
- **Detections**: GET/POST `/api/detections` — legacy detection history
- **WebSocket**: `/ws` — real-time updates to frontend

### Database
**SQLite** (`backend/data/training.db`): Single database for ALL data — ring events, snapshots, detection results, video frames, annotations, and training data. Despite the `deer-db` PostgreSQL container existing in docker-compose, it has no user tables and is not used.

### ring_events Table Key Columns
| Column | Type | Description |
|---|---|---|
| `deer_detected` | BOOLEAN | 1 if deer present (model or user) |
| `detection_confidence` | REAL | Max confidence from detection (0-1) |
| `detection_bboxes` | TEXT (JSON) | `[{"confidence": float|null, "bbox": {"x1","y1","x2","y2"}}]` — pixel coords for 640x360 images |
| `model_version` | TEXT | e.g. "YOLO26s v4.0", "YOLO26s v4.0 PyTorch (backend)" |
| `false_positive` | BOOLEAN | User marked as false positive |
| `user_confirmed` | BOOLEAN | User reviewed and confirmed/annotated this snapshot (added 2026-03-25) |
| `archived` | BOOLEAN | Moved to archive |

### User Confirmation Tracking (2026-03-25)
- `user_confirmed` is set to 1 when:
  - User clicks "yes-deer" in the dashboard (PATCH handler)
  - User draws/saves manual bounding boxes (PUT `/api/snapshots/{id}/bboxes`)
- Manual bboxes are distinguishable by `confidence: null` in the bbox JSON
- The training export script (`scripts/export_dataset_v2.py`) logs user-confirmed counts and includes the flag in the manifest CSV

### PATCH Handler Logic (2026-02-08)
The PATCH `/api/ring-events/{event_id}` endpoint has special logic:
- **User feedback** (clicking "yes-deer" in frontend): sends `{deer_detected: 1}` only → backend re-runs detection at low threshold (0.15) to find bboxes, sets `user_confirmed = 1`
- **Coordinator updates** (after ML detection): sends `{deer_detected, confidence, detection_bboxes, model_version}` → backend stores directly, NO re-detection
- The distinction is: if the update payload contains "confidence" or "detection_bboxes", it's from the coordinator
- **Caveat**: The backend's built-in detector (used for re-detection) does NOT apply CLAHE preprocessing, so it performs worse on dark images than the ml-detector container. At 0.15 threshold it can produce phantom detections in noisy areas (lights, sky). Users should draw manual bboxes rather than rely on re-detection results.

---

## Coordinator (Dockerfile.coordinator)

Single-file Python app embedded in the Dockerfile (~900 lines). Key responsibilities:

1. **MQTT Listener**: Subscribes to Ring motion and snapshot topics
2. **Event Queue**: Queues motion events for processing
4. **Periodic Snapshot Poller**: During active hours, requests snapshots from all 4 cameras at an interval of `snapshot_frequency + 10s` (configurable via Settings page; default 60s = polls every 70s)
4. **Detection Orchestration**: Sends snapshots to ML-detector, reports results to backend
5. **Irrigation Control**: If deer detected, triggers Rainbird zones (with cooldown)
6. **Settings Sync**: Refreshes from backend every 30 seconds
7. **Snapshot Cleanup**: Periodically cleans old snapshot files

### Snapshot Poller Design
- Uses cached MQTT snapshots (not pop-wait-check pattern)
- Requests snapshot via MQTT `command_topic/snapshot/image`
- Waits for fresh image in `latest_snapshots` cache
- Only runs detection on enabled cameras (currently just Side)
- Saves snapshots for all polled cameras regardless

---

## ML Detector (Dockerfile.ml-detector)

Single-file Python app embedded in the Dockerfile (~360 lines). Provides:

- `POST /detect` — Accept image, apply CLAHE, run YOLO, return results
- `GET /health` — Model status, model_version, and current confidence_threshold
- Background settings sync from backend every 30 seconds
- Model version read from `VERSION` file at startup (no hardcoded versions)

---

## Frontend (frontend/)

React + Vite app hosted on Firebase (deer-deterrent-rnp.web.app).

### Key Components
- **Dashboard.jsx**: Main view — shows snapshots, allows deer/no-deer feedback, image upload
- **Settings.jsx**: System settings (threshold, active hours, cameras, irrigation)
- **VideoLibrary.jsx**: Upload and browse Ring videos for annotation
- **AnnotationTool.jsx**: Bounding box annotation on video frames
- **CombinedArchive.jsx**: Browse archived videos and snapshots
- **BoundingBoxImage.jsx**: Renders detection bboxes on snapshot images
- **EarlyReview.jsx**: Review tool for training frame selection

### Auth
- Google OAuth via Firebase Authentication
- Auth state managed by `hooks/useAuth.js`

### API URL
All components use: `import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'`

### Deployment
```bash
cd frontend && npm run build && firebase deploy --only hosting
```

---

## Key Operational Notes

### Disk Space
The Dell server has a 98GB root partition. Docker images accumulate quickly. If builds fail with "No space left on device":
```bash
docker image prune -a -f && docker builder prune -a -f
```

### Common SSH Commands
```bash
# Check all containers
ssh dilger "cd /home/rndpig/deer-deterrent && docker compose ps"

# View logs
ssh dilger "cd /home/rndpig/deer-deterrent && docker compose logs <service> --tail 50 --no-log-prefix"

# Check settings
ssh dilger "curl -s http://localhost:8000/api/settings | python3 -m json.tool"

# Check ml-detector health
ssh dilger "curl -s http://localhost:8001/health | python3 -m json.tool"

# Query database (ALL data is in SQLite — there is no PostgreSQL data)
ssh dilger "sqlite3 /home/rndpig/deer-deterrent/backend/data/training.db 'SELECT ...'"  # Direct SQLite access on host
```

### Database Access
- **SQLite** (all data): File at `/home/rndpig/deer-deterrent/backend/data/training.db` — access directly on host via `sqlite3`, NOT inside containers (no sqlite3 binary in container)
- **PostgreSQL** (deer-db container): Exists but has no user tables. Do not use for ring event queries.

### Active Hours
Periodic snapshot polling and detection only run during active hours (configurable via settings). Default is 20:00-6:00 (8 PM to 6 AM CST) — when deer are most active.

---

## Known Issues & Recent Fixes

### Added (2026-03-25): User Confirmation Tracking
Added `user_confirmed` column to `ring_events` table to track snapshots where a human reviewed and confirmed deer presence or drew manual bounding boxes. Previously, manually-drawn bboxes (with `confidence: null`) were indistinguishable from model detections for training purposes. The training export script now reports user-confirmed counts separately.

### Known (2026-03-25): Backend Re-Detection Produces Phantom Bboxes
When a user clicks "yes-deer" on a snapshot the model missed, the PATCH handler re-runs detection at 0.15 threshold using the backend's built-in detector (which lacks CLAHE). This can produce phantom detections in dark images — e.g., detecting "deer" in distant lights or sky. Users should draw manual bboxes to correct these. The manual bboxes overwrite the phantom ones via PUT `/api/snapshots/{id}/bboxes`.

### Fixed (2026-02-08): PATCH Handler Re-Detection Hijacking
Backend PATCH handler was re-detecting ALL events marked as deer, including coordinator submissions. This overwrote valid detection results with the backend's built-in detector output (which lacks CLAHE and often misses). Fixed by checking for "confidence" in the update payload.

### Fixed (2026-02-08): Confidence Threshold Too Low
Threshold was lowered to 0.40 for testing, causing false positives on empty night scenes (model confidence 0.43-0.67). Raised to 0.55 — all genuine deer detections from historical data are above this.

### Fixed (2026-02-07): Snapshot Poller Timing Race
Poller was using pop-wait-check pattern that missed cached snapshots. Changed to use cached MQTT snapshots directly.

### Fixed (2026-02-07): Timezone Mismatch
Server OS runs America/Chicago but .env had America/New_York. Fixed in .env, all containers now use CST.

---

## File Organization

### Core Service Code (Docker-built)
- `backend/main.py` — FastAPI backend (~4400 lines)
- `backend/database.py` — Database operations
- `Dockerfile.coordinator` — Coordinator service (inline Python, ~925 lines)
- `Dockerfile.ml-detector` — ML detector service (inline Python, ~360 lines)

### Configuration
- `.env` — Environment variables (gitignored, different on server vs local)
- `docker-compose.yml` — Service definitions
- `configs/training_config.yaml` — YOLO training hyperparameters
- `configs/zones.yaml` — Camera-to-irrigation zone mapping
- `models/registry.json` — Model version tracking

### Scripts (run on server)
- `scripts/export_dataset_v2.py` — Export training data to YOLO format
- `scripts/train_yolo26s_v2.py` — YOLO26s training script
- `scripts/train_pipeline.sh` — End-to-end training pipeline
- Various analysis/diagnostic scripts

### Frontend
- `frontend/src/App.jsx` — Main app with tab routing
- `frontend/src/components/Dashboard.jsx` — Snapshot review and feedback
- `frontend/src/components/Settings.jsx` — System settings UI
- `frontend/src/components/AnnotationTool.jsx` — Bounding box annotation
- `frontend/firebase.json` — Firebase hosting config

### Root-Level Scripts (mostly one-off utilities)
The project root contains many one-off Python scripts (check_*.py, fix_*.py, cleanup_*.py, diagnose_*.py) that were used for data cleanup, debugging, and migrations. These are historical artifacts — the important operational scripts are in `scripts/`.

### Documentation
- `ARCHITECTURE.md` — System architecture (partially outdated — written Dec 2025, before Docker migration)
- `README.md` — Project overview and quick start
- `docs/RING_MOTION_DETECTION_PIPELINE.md` — Detailed Ring integration documentation
- Various investigation reports and fix documentation

---

## Development Patterns

### Testing Preference
**IMPORTANT**: The owner does NOT test locally. All frontend changes must be deployed to Firebase for live testing. All backend changes must be deployed to the Dell server. Never suggest running `npm run dev` or local test commands — always deploy to production:
- **Frontend**: `cd frontend && npm run build && firebase deploy --only hosting`
- **Backend/Coordinator/ML-detector**: SSH to server, git pull, rebuild containers

### Making Code Changes
1. Edit files locally (backend/main.py, Dockerfile.coordinator, Dockerfile.ml-detector)
2. Commit and push to GitHub
3. SSH to server, pull, rebuild affected containers, recreate
4. Verify with `docker compose ps` and log inspection

### Changing Configuration
- **Thresholds, active hours, cameras**: Use `PUT /api/settings` or the frontend Settings page. Changes propagate to coordinator and ml-detector within 30 seconds.
- **Environment variables**: Edit server `.env`, then `docker compose up -d --force-recreate <service>`
- **Code default changes**: Also update the Pydantic model default in `backend/main.py` class `SystemSettings`

### Working with the Database
- ALL data lives in SQLite (`backend/data/training.db`) — ring events, training annotations, video frames, everything
- Use the backend API for reads when possible; direct DB access for bulk operations
- SQLite must be accessed on the host filesystem, not inside containers (no sqlite3 in container images)
- The `user_confirmed` column tracks human-reviewed snapshots — useful for prioritizing training data

### Training a New Model
1. Get more annotated data (user feedback in dashboard + annotation tool)
2. Run `scripts/export_dataset_v2.py` on the server to export YOLO format dataset
3. Run `scripts/train_yolo26s_v2.py` in tmux (CPU training takes 30-50 hours)
4. Copy best.pt to `dell-deployment/models/production/`
5. Rebuild ml-detector: `docker compose build ml-detector && docker compose up -d --force-recreate ml-detector`
6. Update `models/registry.json` with new model metadata

---

## Important Warnings

1. **ARCHITECTURE.md is outdated** — It describes a systemd-based backend deployment from Dec 2025. The current system uses Docker for ALL services. Do not follow its instructions for backend deployment.
2. **Root-level scripts are mostly historical** — The 60+ Python scripts in the project root were one-off utilities. Don't assume they reflect current system behavior.
3. **Single database** — ALL data (ring events, training annotations, video frames) lives in SQLite at `backend/data/training.db`. The PostgreSQL container (`deer-db`) exists in docker-compose but has no user tables and is not used. Do not attempt to query ring events from PostgreSQL.
4. **Coordinator and ml-detector are Dockerfile-embedded** — Their Python code is written inline in the Dockerfile via heredoc (`RUN cat > /app/service.py << 'EOF'`). Edits go in the Dockerfile, not separate .py files.
5. **Settings sync delay** — After changing backend settings, wait up to 30 seconds for coordinator and ml-detector to pick up changes.
6. **Server disk fills up** — Docker image cache grows quickly on the 98GB drive. Run `docker image prune -a -f` before builds if space is low.
7. **.env differs between local and server** — The local .env has placeholder values. The server .env has real credentials and may have different threshold values.
