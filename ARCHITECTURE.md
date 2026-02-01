# Deer Deterrent System - Complete Architecture

> **CRITICAL: READ THIS EVERY TIME BEFORE STARTING WORK ON THIS PROJECT**

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└──────────┬──────────────────────────────────┬───────────────────┘
           │                                  │
    ┌──────▼──────────┐              ┌───────▼────────────┐
    │ Firebase Hosting│              │  Cloudflare Edge   │
    │deer-deterrent-rnp│             │  deer-api.rndpig.com│
    └──────┬──────────┘              └───────┬────────────┘
           │                                  │
           │ (Frontend React App)             │ (Cloudflare Tunnel)
           │                                  │
           └──────────────┬───────────────────┘
                          │
                   ┌──────▼──────────────────────────┐
                   │   Dell OptiPlex Server          │
                   │   192.168.7.215 (alias: dilger) │
                   │   Ubuntu 24.04                  │
                   └─────────────────────────────────┘
```

## Component Details

### 1. Frontend (Firebase Hosting)
- **URL**: https://deer-deterrent-rnp.web.app
- **Platform**: React + Vite
- **API URL**: Hardcoded fallback to `https://deer-api.rndpig.com`
- **Auth**: Google OAuth via Firebase Authentication
- **Deployment**: Manual deploy via `firebase deploy --only hosting`
- **Local Dev**: `npm run dev` in `frontend/` directory (port 5173)

**Critical Files:**
- `frontend/src/components/*.jsx` - All use `import.meta.env.VITE_API_URL || 'https://deer-api.rndpig.com'`
- `frontend/.env` - Local dev environment (not used in production)
- `frontend/firebase.json` - Firebase Hosting configuration

### 2. Backend API (Dell OptiPlex Server)

#### 2a. Systemd Service (PRIMARY - Currently Active)
- **Service**: `deer-backend.service`
- **Status**: `sudo systemctl status deer-backend`
- **File**: `/etc/systemd/system/deer-backend.service`
- **User**: `rndpig`
- **Python**: `/usr/bin/python3` (system Python 3.12)
- **Command**: `/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir /home/rndpig/deer-deterrent/backend`
- **Working Directory**: `/home/rndpig/deer-deterrent/backend` ⚠️ CRITICAL
- **Database Location**: `/home/rndpig/deer-deterrent/backend/data/training.db` (4.9MB - THE GOOD ONE)
- **Logs**: `/home/rndpig/logs/backend.log`

**Environment Variables (in service file):**
```
GOOGLE_DRIVE_TRAINING_FOLDER_ID=1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5
GOOGLE_DRIVE_CREDENTIALS_PATH=/home/rndpig/deer-deterrent/configs/google-credentials.json
```

**Packages**: Installed globally with `pip install --break-system-packages`
- fastapi 0.124.4
- uvicorn 0.38.0
- google-api-python-client 2.187.0
- google-auth 2.41.1
- sqlalchemy 2.0.45
- pillow 12.0.0

#### 2b. Docker Container (DISABLED - Do Not Use)
- **Container**: `deer-backend` 
- **Status**: STOPPED and auto-restart DISABLED
- **Image**: `deer-deterrent-backend`
- **Problem**: Was running old code with wrong database path
- **Action**: `docker stop deer-backend && docker update --restart=no deer-backend`

⚠️ **NEVER START THIS CONTAINER** - Use systemd service instead

### 3. Cloudflare Tunnel (Exposes Backend Publicly)
- **Service**: `cloudflared.service` (systemd)
- **Status**: Running since Nov 15 (always-on)
- **Config**: `/etc/cloudflared/config.yml`
- **Tunnel ID**: `48dab637-7544-4bb0-a38a-58e058145490`
- **Public URL**: `https://deer-api.rndpig.com`
- **Internal Target**: `http://localhost:8000` (backend systemd service)
- **Purpose**: Exposes local backend to internet so Vercel can reach it

**Key Points:**
- Cloudflared runs 24/7 and auto-restarts
- Proxies HTTPS requests from `deer-api.rndpig.com` to `localhost:8000`
- Vercel frontend calls `https://deer-api.rndpig.com/api/*`
- If backend returns 0 videos, check: systemd service running AND correct database path

### 4. Other Docker Containers (Supporting Services)

All managed via docker-compose, running 24/7:

```bash
# Location: /home/rndpig/deer-deterrent
docker-compose ps
```

- **deer-coordinator**: Port 5000 - Orchestration service
- **deer-ml-detector**: Port 8001 - ML detection service  
- **deer-ring-mqtt**: Port 8554, 55123 - Ring camera integration
- **deer-db**: PostgreSQL on port 5432
- **deer-mosquitto**: MQTT broker on ports 1883, 9001

⚠️ **These are SEPARATE from the backend API** - they support real-time detection, not the training UI

## File Structure on Server

```
/home/rndpig/deer-deterrent/
├── backend/
│   ├── main.py                          # FastAPI application (125KB - ACTIVE)
│   ├── database.py                      # SQLite operations
│   ├── data/
│   │   └── training.db                  # 4.9MB - PRIMARY DATABASE ✓
│   └── Dockerfile                       # (not used - systemd instead)
├── src/
│   ├── main.py                          # ML training script (9.8KB - different!)
│   ├── inference/
│   │   └── detector.py                  # YOLO detector
│   └── services/
│       └── drive_sync.py                # Google Drive integration
├── configs/
│   └── google-credentials.json          # Service account credentials (2378 bytes)
├── data/
│   └── training.db                      # 56KB - WRONG/EMPTY DATABASE ✗
├── docker-compose.yml                   # Supporting services
├── deer-backend.service                 # Systemd service file (local copy)
└── archive/
    └── old-duplicates-20251213/         # Cleaned up old files

/etc/systemd/system/
└── deer-backend.service                 # Active systemd service

/etc/cloudflared/
└── config.yml                           # Cloudflare tunnel config
```

## Critical Path Understanding

### Working Directory vs App Directory

**The systemd service has:**
```ini
WorkingDirectory=/home/rndpig/deer-deterrent/backend
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir /home/rndpig/deer-deterrent/backend
```

**What this means:**
- Uvicorn imports `main:app` from `/home/rndpig/deer-deterrent/backend/main.py`
- When Python code does `Path("data/training.db")`, it resolves relative to **WorkingDirectory**
- Therefore: `Path("data/training.db")` = `/home/rndpig/deer-deterrent/backend/data/training.db` ✓

**Previous mistake:**
- Had `WorkingDirectory=/home/rndpig/deer-deterrent` (wrong!)
- This made `Path("data/training.db")` = `/home/rndpig/deer-deterrent/data/training.db` (empty 56KB file)
- Result: Backend ran but returned 0 videos

### Database File Permissions

**Must be owned by rndpig:rndpig:**
```bash
sudo chown rndpig:rndpig /home/rndpig/deer-deterrent/backend/data/training.db
sudo chmod 664 /home/rndpig/deer-deterrent/backend/data/training.db
```

**Current state (correct):**
```
-rw-rw-r-- 1 rndpig rndpig 4.9M Dec 13 11:06 /home/rndpig/deer-deterrent/backend/data/training.db
```

## Common Debugging Commands

### Check Backend Status
```bash
# Service status
ssh dilger "sudo systemctl status deer-backend"

# Is it running?
ssh dilger "sudo systemctl is-active deer-backend"

# Check what's listening on port 8000
ssh dilger "sudo lsof -i :8000"

# Check for rogue Docker containers
ssh dilger "sudo docker ps | grep backend"
```

### Test API Endpoints
```powershell
# Direct IP (bypasses tunnel)
curl.exe -s http://192.168.7.215:8000/api/videos

# Through Cloudflare tunnel (what Vercel uses)
curl.exe -s https://deer-api.rndpig.com/api/videos

# Count videos
curl.exe -s https://deer-api.rndpig.com/api/videos | python -c "import sys,json; print(len(json.load(sys.stdin)))"
```

### Restart Services
```bash
# Restart backend
ssh dilger "sudo systemctl restart deer-backend"

# Restart Cloudflare tunnel (rarely needed)
ssh dilger "sudo systemctl restart cloudflared"

# View logs
ssh dilger "sudo journalctl -u deer-backend -n 50 --no-pager"
```

## Deployment Workflow

### Deploy Backend Changes
```powershell
# 1. Edit locally
code backend/main.py

# 2. Deploy to server
scp backend/main.py dilger:/home/rndpig/deer-deterrent/backend/

# 3. Restart service
ssh dilger "sudo systemctl restart deer-backend"

# 4. Wait 3-5 seconds for startup
Start-Sleep -Seconds 5

# 5. Verify
curl.exe -s https://deer-api.rndpig.com/api/videos | python -c "import sys,json; print(f'{len(json.load(sys.stdin))} videos')"
```

### Deploy Frontend Changes
```powershell
# 1. Commit and push
git add frontend/src/
git commit -m "Update frontend"
git push

# 2. Vercel auto-deploys in ~30-60 seconds
# 3. Check: https://deer-deterrent-rnp.web.app
```

### Deploy Systemd Service Changes
```powershell
# 1. Edit local copy
code deer-backend.service

# 2. Deploy
scp deer-backend.service dilger:/tmp/
ssh dilger "sudo mv /tmp/deer-backend.service /etc/systemd/system/"

# 3. Reload and restart
ssh dilger "sudo systemctl daemon-reload && sudo systemctl restart deer-backend"
```

## Troubleshooting Checklist

### Videos Not Loading in UI

1. **Check Frontend API URL**: Should be `https://deer-api.rndpig.com`
2. **Test Tunnel**: `curl https://deer-api.rndpig.com/api/videos`
3. **Check Backend Service**: `ssh dilger "sudo systemctl status deer-backend"`
4. **Check Docker**: `ssh dilger "sudo docker ps | grep backend"` (should be empty!)
5. **Check Database Path**: Service `WorkingDirectory=/home/rndpig/deer-deterrent/backend`
6. **Check Database Permissions**: Owned by `rndpig:rndpig`

### Backend Returning Empty Data

1. **Check which process is running**: `ssh dilger "ps aux | grep uvicorn"`
2. **Should see**: `/usr/bin/python3 -m uvicorn` (NOT `/usr/local/bin/python3.11`)
3. **Check working directory**: `WorkingDirectory=/home/rndpig/deer-deterrent/backend`
4. **Check database size**: Should be ~4.9MB, not 56KB

### Train Model Button Fails

1. **Check Google credentials**: `ssh dilger "test -r /home/rndpig/deer-deterrent/configs/google-credentials.json && echo OK"`
2. **Check Python packages**: `ssh dilger "python3 -c 'import google.auth; print(\"OK\")'"`
3. **Install if missing**: `ssh dilger "sudo python3 -m pip install --break-system-packages google-auth google-api-python-client"`
4. **Check environment variables in service file**

## Package Installation

### System Python (Preferred Method)
```bash
ssh dilger "sudo python3 -m pip install --break-system-packages [package-name]"
```

### Currently Installed Packages
```
fastapi==0.124.4
uvicorn==0.38.0
google-api-python-client==2.187.0
google-auth==2.41.1
google-auth-httplib2==0.2.1
google-auth-oauthlib==1.2.3
sqlalchemy==2.0.45
pillow==12.0.0
python-multipart==0.0.20
```

## Critical Rules

1. ✅ **ALWAYS** use systemd service, NEVER Docker container for backend
2. ✅ **ALWAYS** check `WorkingDirectory` matches `/home/rndpig/deer-deterrent/backend`
3. ✅ **ALWAYS** verify database is 4.9MB, not 56KB
4. ✅ **ALWAYS** test through `deer-api.rndpig.com` (what Vercel uses)
5. ✅ **ALWAYS** check for rogue Docker containers before troubleshooting
6. ⛔ **NEVER** modify `/home/rndpig/deer-deterrent/data/training.db` (wrong database)
7. ⛔ **NEVER** use `pkill -9 python3` (kills everything, causes chaos)
8. ⛔ **NEVER** assume localhost works the same as the tunnel

## Data Locations

### Training Data
- **Database**: `/home/rndpig/deer-deterrent/backend/data/training.db` (4.9MB)
- **Videos**: `/home/rndpig/deer-deterrent/data/video_archive/`
- **Frames**: Extracted to temp directories during annotation
- **Exports**: `/home/rndpig/deer-deterrent/temp/training_export/`

### Google Drive
- **Credentials**: `/home/rndpig/deer-deterrent/configs/google-credentials.json`
- **Folder ID**: `1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5`
- **Folder Name**: "Deer video detection"

## Before Making Changes

1. Read this document
2. Verify current system state matches this document
3. Check for any running Docker containers
4. Verify database location and permissions
5. Test current functionality before changing anything

## Last Updated
December 13, 2025 - After cleanup and systemd service fixes
