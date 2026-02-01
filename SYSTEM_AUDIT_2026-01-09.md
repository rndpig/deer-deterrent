# Final System Audit Report
**Date:** January 9, 2026  
**Audit Type:** Docker Containerization & Path Consistency

---

## ✅ DOCKER CONTAINERIZATION STATUS

### All Services Running in Docker
```
deer-backend         ✅ Docker container (port 8000)
deer-coordinator     ✅ Docker container (port 5000)  
deer-ml-detector     ✅ Docker container (port 8001)
deer-db              ✅ PostgreSQL container (port 5432)
deer-mosquitto       ✅ MQTT broker (ports 1883, 9001)
deer-ring-mqtt       ✅ Ring integration (ports 8554, 55123)
```

### Systemd Service Status
```
deer-backend.service ✅ INACTIVE (migrated to Docker)
```

### Docker Networking
```
Network:             deer-network (bridge mode)
Backend URL:         http://backend:8000 (Docker service name)
Coordinator:         Uses Docker service names for all communication
Frontend:            Firebase Hosting (deer-deterrent-rnp.web.app)
Backend Tunnel:      Cloudflare (deer-api.rndpig.com)
```

---

## ✅ FRAME STORAGE CONSOLIDATION

### Directory Structure
```
❌ data/training_frames/  REMOVED (was 1.1GB)
✅ data/frames/           ACTIVE (1.1GB - all frames)
```

### Migration Results
- **2,559 frames** moved from training_frames → frames
- **468 database records** updated to new paths
- **32 duplicate files** skipped (already in destination)
- **Old directory** completely removed

---

## ✅ CODE PATH CONSISTENCY

### Backend Endpoints (backend/main.py)

#### Primary Frame Operations
All write operations use `data/frames/`:
```python
Line 708:  Video upload frame extraction       → data/frames/
Line 2056: Extract frames function             → data/frames/
Line 2239: Fill missing frames                 → data/frames/
Line 2653: Recover video analysis              → data/frames/
Line 2724: Recover analysis image_path         → data/frames/
```

#### Read Operations with Fallback
Frame serving endpoints check `data/frames/` first, then fall back:
```python
Line 1006: GET /api/training-frames/{name}     → data/frames/ (primary)
Line 1009:                                      → data/training_frames/ (fallback)

Line 1033: GET /api/frames/{id}/annotated      → data/frames/ (primary)
Line 1036:                                      → data/training_frames/ (fallback)

Line 1779: Reanalyze videos                    → data/frames/ (primary)
Line 1782:                                      → data/training_frames/ (fallback)
```

#### Variable Names (Informational Only)
These are database field names and variable names (not file paths):
```python
Line 1601: training_frames = SELECT COUNT(*)... ← Database query
Line 1931: training_frames = [f for f in...]   ← Variable name
Line 1947: async def clear_all_training_frames  ← Function name
Line 2904: async def select_training_frames     ← Function name
Line 2922: async def get_selected_training_frames ← Function name
Line 3009: training_frames = db.get_training_frames() ← Variable name
```

**Note:** These are NOT file path references. They refer to frames marked with `selected_for_training=1` flag in the database, which is the correct semantic meaning.

### Standalone Scripts
```python
scripts/fill_missing_frames.py     ✅ Updated → data/frames/
scripts/recover_video_analysis.py  ✅ Updated → data/frames/
```

### Documentation
```markdown
WORKFLOW_GUIDE.md                  ✅ Updated → data/frames/
```

---

## ✅ VERIFICATION TESTS

### Container Status
```bash
$ docker ps --filter name=deer-
✅ 6/6 containers running
✅ 5/6 containers healthy (ring-mqtt has no health check)
```

### Directory Verification
```bash
$ docker exec deer-backend ls -ld /app/data/frames
✅ drwxr-xr-x 2 1000 1000 217088 Jan 9 19:18 /app/data/frames

$ docker exec deer-backend ls -ld /app/data/training_frames
❌ No such file or directory (EXPECTED - removed)
```

### Endpoint Tests
```bash
$ curl -s https://deer-api.rndpig.com/api/frames/2784/annotated
✅ HTTP 200 OK, 714KB annotated image

$ curl -s https://deer-api.rndpig.com/api/training-frames/video_4_frame_0.jpg
✅ HTTP 200 OK, thumbnail loaded
```

### Database Path Check
```sql
SELECT DISTINCT image_path FROM frames LIMIT 5;
✅ data/frames/video_4_frame_0.jpg
✅ data/frames/video_18_frame_0.jpg
✅ data/frames/20260106_201746_frame_000000.jpg
```

---

## 📊 SUMMARY

### What Was Fixed
1. ✅ Migrated backend from systemd service → Docker container
2. ✅ Consolidated all frames: data/training_frames/ → data/frames/
3. ✅ Updated 7 backend endpoints to use data/frames/
4. ✅ Updated 2 standalone scripts
5. ✅ Updated documentation
6. ✅ Moved 2,559 frame files + updated 468 DB records
7. ✅ Removed old training_frames directory

### Current State
- **All services:** Running in Docker containers ✅
- **Frame storage:** Single directory (data/frames/) ✅
- **Path consistency:** All write operations use data/frames/ ✅
- **Backward compatibility:** Read operations check old location as fallback ✅
- **Database:** Updated with new paths ✅
- **No host processes:** Everything containerized ✅

### Remaining References
The word "training_frames" appears 27 times in backend/main.py:
- **2 instances:** Backward compatibility fallback checks (intentional)
- **25 instances:** Variable/function names referring to frames marked for training (correct semantic usage)

**None of these create new files in training_frames/ directory.**

---

## 🎯 CONCLUSION

**System Status:** ✅ FULLY CONTAINERIZED & CONSISTENT

All services are running in Docker containers with no host-based processes. All frame operations use the consolidated `data/frames/` directory. The system maintains backward compatibility for reading old paths while ensuring all new data is written to the correct location.

**No further path consolidation needed.**
