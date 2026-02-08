# Deer Deterrent System — Chat Instructions for AI Agents
# Last Updated: 2026-02-08

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
| deer-backend | 8000 | deer-deterrent-backend | FastAPI API server, SQLite training DB, WebSocket |
| deer-ml-detector | 8001 | deer-deterrent-ml-detector | YOLO26s inference with CLAHE preprocessing |
| deer-coordinator | 5000 | deer-deterrent-coordinator | Ring MQTT listener, orchestrates detection pipeline, irrigation |
| deer-db | 5432 | postgres:16-alpine | PostgreSQL for Ring event data |
| deer-mosquitto | 1883, 9001 | eclipse-mosquitto:2.0 | MQTT message broker |
| deer-ring-mqtt | 8554, 55123 | tsightler/ring-mqtt | Ring camera → MQTT bridge |

### Container Dependencies
```
database (postgres) → backend → coordinator
mosquitto → ring-mqtt → coordinator
ml-detector → coordinator
```

### Key Volume Mounts
- `./backend/data:/app/data` — SQLite training DB (backend + coordinator shared)
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

## Ring Cameras (4 cameras)

| Camera | Ring-MQTT ID | Name | Detection Enabled |
|---|---|---|---|
| Side | 10cea9e4511f | Side | YES (primary) |
| Driveway | 587a624d3fae | Driveway | No |
| Front Door | 4439c4de7a79 | Front Door | No |
| Back | f045dae9383a | Back | No |

- Ring-MQTT publishes snapshots to `ring/dp1hu9-2i94c-0/camera/{camera_id}/snapshot/image`
- Motion events come via `ring/+/camera/+/motion` topics
- Periodic snapshot polling runs during active hours (configurable, default 20:00-6:00 CST)
- All 4 cameras are polled for snapshots, but only the Side camera runs through ML detection

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
8. Backend stores event in PostgreSQL ring_events table
9. Frontend dashboard shows events via WebSocket push
```

### Threshold Configuration
- **CONFIDENCE_THRESHOLD**: 0.55 (synced from backend settings to ml-detector every 30s)
- **IOU_THRESHOLD**: 0.65 (set via .env, NMS deduplication)
- ML-detector default from .env is overridden by backend settings via `fetch_settings_from_backend()`

### Settings Synchronization
- Coordinator and ML-detector both poll `GET /api/settings` from backend every 30 seconds
- This is how confidence_threshold, enabled_cameras, and active_hours propagate
- To change settings: use the frontend Settings page or `PUT /api/settings`

---

## ML Model

### Current Production Model: YOLO26s v2.0
- **Architecture**: YOLO26s (from ultralytics >= 8.4.0)
- **File**: `dell-deployment/models/production/best.pt` (19.35 MB)
- **MD5**: cb50366cac8b5a5f5a445f3c85277da6
- **Training**: Two-phase (20 frozen + 97 full) on Dell i7-4790 CPU
- **Dataset v2.0**: 401 images (258 video frames + 3 Ring snapshots + 140 hard negatives), CLAHE preprocessed
- **Metrics**: mAP50=0.806, Precision=0.836, Recall=0.765 (test set)
- **Inference**: ~162ms on i7-4790 CPU (~6 FPS)
- **CLAHE preprocessing**: clip_limit=2.0, tile_grid_size=(8,8) — applied at inference time in ml-detector

### Model Registry
See `models/registry.json` for full model history, dataset versions, and deployment history.

### Previous Model
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

### Databases
1. **PostgreSQL** (deer-db container): Ring events, snapshots, detection results
2. **SQLite** (`backend/data/training.db`): Video frames, annotations, training data

### PATCH Handler Bug Fix (2026-02-08)
The PATCH `/api/ring-events/{event_id}` endpoint has special logic:
- **User feedback** (clicking "yes-deer" in frontend): sends `{deer_detected: 1}` only → backend re-runs detection at low threshold (0.15) to find bboxes
- **Coordinator updates** (after ML detection): sends `{deer_detected, confidence, detection_bboxes, model_version}` → backend stores directly, NO re-detection
- The distinction is: if the update payload contains "confidence" or "detection_bboxes", it's from the coordinator

---

## Coordinator (Dockerfile.coordinator)

Single-file Python app embedded in the Dockerfile (~900 lines). Key responsibilities:

1. **MQTT Listener**: Subscribes to Ring motion and snapshot topics
2. **Event Queue**: Queues motion events for processing
3. **Periodic Snapshot Poller**: During active hours, requests snapshots from all 4 cameras every 25 seconds via MQTT
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
- `GET /health` — Model status and current confidence_threshold
- Background settings sync from backend every 30 seconds
- Returns `model_version: "YOLO26s v2.0"` in detection responses

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

# Query database
ssh dilger "python3 -c 'import sqlite3; ...'"  # For SQLite training DB
ssh dilger "docker exec deer-db psql -U deeruser -d deer_deterrent -c 'SELECT ...'"  # For PostgreSQL
```

### Database Access
- **PostgreSQL** (ring events): Access via `docker exec deer-db psql -U deeruser -d deer_deterrent`
- **SQLite** (training data): File at `/home/rndpig/deer-deterrent/backend/data/training.db` — access directly on host, NOT inside containers (no sqlite3 binary in container)

### Active Hours
Periodic snapshot polling and detection only run during active hours (configurable via settings). Default is 20:00-6:00 (8 PM to 6 AM CST) — when deer are most active.

---

## Known Issues & Recent Fixes

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
- Ring events live in PostgreSQL (`ring_events` table)
- Training annotations live in SQLite (`backend/data/training.db`)
- Use the backend API for reads when possible; direct DB access for bulk operations
- SQLite must be accessed on the host filesystem, not inside containers

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
3. **Two databases** — PostgreSQL for runtime Ring events, SQLite for training data. Don't confuse them.
4. **Coordinator and ml-detector are Dockerfile-embedded** — Their Python code is written inline in the Dockerfile via heredoc (`RUN cat > /app/service.py << 'EOF'`). Edits go in the Dockerfile, not separate .py files.
5. **Settings sync delay** — After changing backend settings, wait up to 30 seconds for coordinator and ml-detector to pick up changes.
6. **Server disk fills up** — Docker image cache grows quickly on the 98GB drive. Run `docker image prune -a -f` before builds if space is low.
7. **.env differs between local and server** — The local .env has placeholder values. The server .env has real credentials and may have different threshold values.
