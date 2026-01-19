# Quick Fix Script - Lower ML Confidence Threshold

## Problem
ML model is missing deer detections because confidence threshold (0.30) is too high for nighttime images.

## Solution
Lower the threshold to 0.15 or 0.20 to improve detection sensitivity.

## Instructions

### Option 1: Lower to 0.20 (Balanced)
Recommended for first attempt - reduces false negatives while minimizing false positives.

### Option 2: Lower to 0.15 (Aggressive)
More sensitive - will detect more deer but may have more false positives.

## Steps to Implement

### 1. SSH to Server
```powershell
ssh dilger
```

### 2. Navigate to Project
```bash
cd /home/rndpig/deer-deterrent
```

### 3. Check Current Configuration
```bash
# View current threshold
docker exec deer-coordinator env | grep CONFIDENCE
docker exec deer-ml-detector env | grep CONFIDENCE

# Should show:
# CONFIDENCE_THRESHOLD=0.30
```

### 4. Edit docker-compose.yml
```bash
nano docker-compose.yml
```

Find these sections and change the threshold:

#### For Coordinator (around line 245):
```yaml
coordinator:
  environment:
    - CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.20}  # Changed from 0.30
```

#### For ML Detector (around line 185):
```yaml
ml-detector:
  environment:
    - CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.20}  # Changed from 0.30
```

Save and exit: `Ctrl+X`, then `Y`, then `Enter`

### 5. Restart Services
```bash
# Restart both services to pick up new config
docker-compose restart coordinator ml-detector

# Verify they restarted successfully
docker-compose ps

# Check logs for any errors
docker-compose logs --tail=20 coordinator
docker-compose logs --tail=20 ml-detector
```

### 6. Verify New Configuration
```bash
# Confirm new threshold is loaded
docker exec deer-coordinator env | grep CONFIDENCE
docker exec deer-ml-detector env | grep CONFIDENCE

# Should now show:
# CONFIDENCE_THRESHOLD=0.20
```

### 7. Monitor for Results
```bash
# Watch coordinator logs in real-time
docker-compose logs -f coordinator

# Wait for next motion event
# Look for detection results with confidence scores

# Press Ctrl+C to stop watching logs
```

## Alternative: Edit .env File

If you have a `.env` file, you can edit it instead:

```bash
nano .env
```

Add or change:
```
CONFIDENCE_THRESHOLD=0.20
```

Then restart services:
```bash
docker-compose restart coordinator ml-detector
```

## Testing the Change

### Test with Existing Snapshot

```bash
# Find a recent snapshot
docker exec deer-coordinator ls -lth /app/snapshots/ | head -10

# Test it with ML detector
docker cp deer-coordinator:/app/snapshots/20260116_230638_10cea9e4511f.jpg /tmp/test.jpg
curl -X POST -F "file=@/tmp/test.jpg" http://localhost:8001/detect

# Check output for detections and confidence scores
```

### Wait for Next Event

The next time a Ring camera detects motion:
1. Coordinator will capture snapshot
2. ML detector will analyze with new 0.20 threshold
3. If deer confidence is between 0.20-0.29, it will now be detected!
4. Event will be logged to database

### Check Results via API

From your Windows machine:

```powershell
# Check recent detections
curl https://deer-api.rndpig.com/api/detections/recent?hours=24 | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Check recent Ring events
curl https://deer-api.rndpig.com/api/ring-events?hours=24 | ConvertFrom-Json | Select-Object -ExpandProperty events | Format-Table -Property timestamp, camera_id, deer_detected, detection_confidence
```

## Expected Results

### Before (Threshold 0.30)
- Deer detections: 0 in last 7 days
- False negatives: High (missed deer on Jan 16)
- False positives: Low (no spurious detections)

### After (Threshold 0.20)
- Deer detections: Should increase
- False negatives: Lower (catch more real deer)
- False positives: Slightly higher (may detect shadows, cars, etc.)

## Monitoring for False Positives

After lowering threshold, monitor for a few days:

```bash
# Check all recent detections
curl https://deer-api.rndpig.com/api/ring-events?hours=72 | jq '.events[] | select(.deer_detected == true)'
```

If you see false positives (non-deer detections):
1. Review the snapshots
2. Consider raising threshold slightly (e.g., 0.20 → 0.22)
3. Or retrain model with better negative examples

## Rollback (If Needed)

If you get too many false positives:

```bash
# Edit docker-compose.yml
nano docker-compose.yml

# Change back to:
# CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.25}  # Or 0.30

# Restart
docker-compose restart coordinator ml-detector
```

## Advanced: Different Thresholds for Day/Night

Future enhancement - modify coordinator code to use:
- 0.30 during daytime (6 AM - 6 PM)
- 0.20 during nighttime (6 PM - 6 AM)

This requires code changes in `Dockerfile.coordinator`.

---

## Quick Commands Summary

```bash
# SSH to server
ssh dilger

# Edit config
cd /home/rndpig/deer-deterrent
nano docker-compose.yml  # Change 0.30 to 0.20

# Restart
docker-compose restart coordinator ml-detector

# Verify
docker exec deer-coordinator env | grep CONFIDENCE

# Monitor
docker-compose logs -f coordinator
```

---

**Time Required:** 5-10 minutes  
**Downtime:** ~5 seconds (service restart)  
**Risk:** Low (easily reversible)  
**Expected Improvement:** Should catch nighttime deer previously missed
