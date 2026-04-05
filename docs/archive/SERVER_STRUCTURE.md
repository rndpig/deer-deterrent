# Server File Structure (Cleaned Dec 13, 2025)

## Active Files on Server (192.168.7.215)

### Backend API
**Location:** `/home/rndpig/deer-deterrent/backend/main.py` (125KB)
- **Purpose:** FastAPI backend serving the web UI
- **Used by:** systemd service `deer-backend`
- **Python:** System Python3 (`/usr/bin/python3`)
- **Packages:** Installed globally with `--break-system-packages`

### ML Training Script  
**Location:** `/home/rndpig/deer-deterrent/src/main.py` (9.8KB)
- **Purpose:** Standalone ML training script for YOLOv8
- **Used by:** Manual training sessions, not the API
- **DO NOT CONFUSE** with backend/main.py

### Database
**Location:** `/home/rndpig/deer-deterrent/backend/data/training.db`
- SQLite database with frames, annotations, detections

### Google Drive Credentials
**Location:** `/home/rndpig/deer-deterrent/configs/google-credentials.json`
- Service account credentials (verified working)
- Folder ID: `1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5`

## Systemd Service Configuration

**File:** `/etc/systemd/system/deer-backend.service`
```
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir /home/rndpig/deer-deterrent/backend
WorkingDirectory=/home/rndpig/deer-deterrent
```

## Python Environment

**Type:** System Python3 (no venv)
- **Path:** `/usr/bin/python3`
- **Reason:** Using system-wide installation with `--break-system-packages`
- **Key Packages:**
  - fastapi 0.124.4
  - uvicorn 0.38.0
  - google-api-python-client 2.187.0
  - sqlalchemy 2.0.45
  - pillow 12.0.0

## Archived/Removed

### Removed Duplicates
- **Archived:** `/home/rndpig/deer-deterrent/archive/old-duplicates-20251213/backend/`
  - Old 215-byte main.py from Nov 9
  - Was causing confusion, not used by service

### Cleaned
- All `__pycache__` directories removed
- All `*.pyc` files deleted

## Deployment Workflow

1. **Edit locally:** `backend/main.py` on Windows
2. **Deploy:** `scp backend/main.py dilger:/home/rndpig/deer-deterrent/backend/`
3. **Restart:** `ssh dilger "sudo systemctl restart deer-backend"`
4. **Verify:** `curl http://192.168.7.215:8000/api/videos`

## File Locations Clarity

```
deer-deterrent/
├── backend/
│   ├── main.py              # ← ACTIVE API SERVER (125KB)
│   ├── database.py          # Database operations
│   ├── Dockerfile           # (not currently used)
│   └── data/
│       └── training.db      # SQLite database
├── src/
│   ├── main.py              # ← ML TRAINING SCRIPT (different purpose!)
│   ├── inference/
│   │   └── detector.py      # YOLO detector class
│   └── services/
│       └── drive_sync.py    # Google Drive integration
├── configs/
│   └── google-credentials.json  # Service account creds
└── archive/
    └── old-duplicates-20251213/  # Old files (safe to delete later)
```

## Important Notes

⚠️ **DO NOT:**
- Mix up `backend/main.py` (API server) with `src/main.py` (training script)
- Create venv on server - using system Python intentionally
- Delete `src/main.py` - it's for training, not the API

✅ **DO:**
- Always deploy to `backend/main.py` for API changes
- Restart service after deploying changes
- Clear __pycache__ if seeing stale behavior
