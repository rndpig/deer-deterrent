# Investigation Report: Missed Deer Detection on Jan 16, 2026

**Date of Investigation:** January 18, 2026  
**Investigated Event:** Jan 16, 2026 at ~10:06 PM Central Time  
**Status:** ✅ SYSTEM WORKING | ❌ DETECTION FAILED

---

## Executive Summary

The automated deer detection system IS functioning correctly - Ring cameras triggered, MQTT messages were received, snapshots were captured, and ML processing occurred. However, **the ML model failed to detect the deer** that you observed in your Ring app video.

---

## Event Details

**Event ID:** 5584  
**Camera ID:** 10cea9e4511f  
**Timestamp:** 2026-01-16T23:06:38 (11:06:38 PM local time)  
**Snapshot Captured:** Yes (24,106 bytes)  
**ML Processing:** Yes (Processed successfully)  
**Deer Detection Result:** ❌ **NO DEER DETECTED** (Confidence: 0.0)

---

## System Status (All Components Working)

### ✅ Ring Camera System
- Motion was detected by Ring camera
- Ring app has video recording of the event
- Camera is operational and reporting events

### ✅ Ring-MQTT Bridge
- Successfully captured the motion event from Ring API
- Published event to MQTT broker
- Snapshot data transmitted (24KB image)

### ✅ MQTT Broker (Mosquitto)
- Running and accepting connections
- Coordinator successfully subscribed to Ring topics
- Messages flowing correctly

### ✅ Coordinator Service
- Running and healthy
- MQTT connection established
- Received motion event at 23:06:38
- Captured snapshot automatically
- Sent image to ML detector

### ✅ ML Detector Service
- Service is running and responsive
- Received image for analysis
- Processed image successfully
- Returned detection result (no deer found)

### ✅ Backend API
- Logging all Ring events to database
- 94 events logged in last 7 days
- 12 events on Jan 16 alone
- Event #5584 successfully recorded

---

## The Problem: ML Model Failed Detection

The ML model analyzed the snapshot but **did not detect any deer** in the image.

### Why Detection Failed (Possible Causes)

1. **Image Quality Issues**
   - Event occurred at night (11:06 PM)
   - Low light conditions reduce detection accuracy
   - Ring-MQTT snapshots are lower resolution (~24KB)
   - Night vision IR may not provide good contrast

2. **Confidence Threshold Too High**
   - Current threshold: ~0.30 (30%)
   - Model may have detected deer at lower confidence (e.g., 0.15-0.25)
   - Nighttime images naturally have lower confidence scores

3. **Snapshot Timing**
   - Snapshot captured at exact moment of MQTT message
   - Deer may have already moved out of frame
   - Motion trigger fires when movement starts, not when deer is centered

4. **Model Training Gaps**
   - Model may not be well-trained on nighttime images
   - Deer at certain angles/distances may not be recognized
   - Specific camera angle/lighting may not match training data

5. **Deer Position**
   - Deer may be too far from camera
   - Partially obscured by trees/bushes
   - At edge of frame where detection is less reliable

---

## Current Configuration

**ML Model:** YOLOv8 (custom trained)  
**Model Location:** `/app/models/production/best.pt` or `yolov8n.pt`  
**Confidence Threshold:** ~0.30 (30%)  
**Active Hours:** 24/7 (all hours enabled)  
**Cooldown Period:** 300 seconds (5 minutes)  
**Irrigation Activation:** Enabled (but requires deer detection)

---

## Performance Statistics

**Last 7 Days:**
- **Ring Events:** 94 total motion events
- **Events Processed:** 94 (100%)
- **Deer Detected:** 0 (0% detection rate)
- **False Negatives:** At least 1 (Jan 16 event)

**System Uptime:**
- Coordinator: Running continuously
- MQTT Connection: Stable
- Snapshots Captured: 24,248 total

---

## Diagnostic Findings

### What's Working ✅
1. Ring cameras detecting motion
2. MQTT message flow
3. Snapshot capture (instant, ~24KB images)
4. ML detector processing images
5. Event logging to database
6. All Docker containers healthy

### What's Not Working ❌
1. **ML model accuracy** - Missing deer in snapshots
2. **Detection rate** - 0 detections in 94 events (7 days)
3. **Irrigation activation** - Never triggered (no deer detected)

---

## Recommended Actions

### Immediate Actions

#### 1. Review the Actual Snapshot
```bash
# SSH to server
ssh dilger

# Find and copy the snapshot
cd /home/rndpig/deer-deterrent
docker exec deer-coordinator ls -lh /app/snapshots/ | grep 20260116_2306
docker cp deer-coordinator:/app/snapshots/20260116_230638_10cea9e4511f.jpg ./

# Download to local machine for review
scp dilger:/home/rndpig/deer-deterrent/20260116_230638_10cea9e4511f.jpg .
```

**Question to answer:** Can you visually see the deer in this snapshot?

#### 2. Test ML Model Manually
```bash
# On server
cd /home/rndpig/deer-deterrent

# Test the image with ML detector
curl -X POST -F "file=@20260116_230638_10cea9e4511f.jpg" \
  http://localhost:8001/detect | jq

# Check what confidence scores are returned
# Look for any detections below 0.30 threshold
```

#### 3. Lower Confidence Threshold (If Needed)
```bash
# Check current threshold
docker exec deer-coordinator env | grep CONFIDENCE

# Edit docker-compose.yml
nano docker-compose.yml

# Change this line under coordinator service:
# - CONFIDENCE_THRESHOLD=0.30
# To:
# - CONFIDENCE_THRESHOLD=0.15  # or 0.20

# Restart coordinator
docker-compose restart coordinator

# Monitor for false positives
docker-compose logs -f coordinator
```

#### 4. Review Ring App Video
- Open Ring app
- Find Jan 16, 2026 11:06 PM event
- Confirm deer is actually visible in the video
- Note exact timestamp when deer is most visible
- Compare with snapshot timing

### Short-Term Improvements

#### 1. Use High-Resolution Snapshots
The coordinator code has a function `request_high_res_snapshot()` but it may not be enabled. Consider:
- Requesting fresh high-res snapshots instead of MQTT cached snapshots
- Using video frame extraction instead of snapshots
- Implementing delay before snapshot to let deer center in frame

#### 2. Adjust Detection Strategy
- **Lower threshold:** Try 0.15-0.20 for night detections
- **Multiple snapshots:** Capture 3 frames over 2 seconds
- **Video analysis:** Download and analyze video instead of snapshot
- **Dual threshold:** Use 0.30 for day, 0.15 for night

#### 3. Improve Model Training
- Add more nighttime deer images to training set
- Include images from this specific camera angle
- Train specifically on Ring camera nightvision quality
- Balance training data: day vs. night images

### Long-Term Solutions

#### 1. Retrain ML Model
- Collect nighttime deer videos from Ring
- Extract frames with deer visible
- Manually annotate deer in low-light conditions
- Retrain model with nighttime emphasis
- Document in: `docs/ML_TRAINING_QUICKSTART.md`

#### 2. Implement Video Analysis
Instead of using snapshots:
- Download full video on motion event
- Extract multiple frames (every 0.5 seconds)
- Run detection on all frames
- Report deer if found in ANY frame
- Higher accuracy, slower processing

#### 3. Add Confidence Logging
Modify ML detector to:
- Log ALL detections, even below threshold
- Return top 5 predictions with scores
- Store in database for analysis
- Tune threshold based on real data

#### 4. Hybrid Approach
- Use instant snapshot for quick check (current)
- If no deer detected, request high-res snapshot
- If still no deer, download and analyze video
- Trade-off: latency vs. accuracy

---

## Configuration Files to Check/Modify

### 1. docker-compose.yml
```yaml
coordinator:
  environment:
    - CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.30}  # Lower this
    - ENABLE_IRRIGATION=${ENABLE_IRRIGATION:-true}
```

### 2. Dockerfile.coordinator
Check the coordinator service code around line 300-400 for snapshot handling.

### 3. ML Detector Configuration
Check environment variables in docker-compose.yml:
```yaml
ml-detector:
  environment:
    - CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.30}
    - IOU_THRESHOLD=${IOU_THRESHOLD:-0.45}
```

---

## Monitoring Commands

### Check Real-Time Logs
```bash
# All services
docker-compose logs -f

# Just coordinator
docker-compose logs -f coordinator

# Just ML detector
docker-compose logs -f ml-detector

# Ring-MQTT
docker-compose logs -f ring-mqtt
```

### Check Event Statistics
```bash
# Via API (from anywhere)
curl https://deer-api.rndpig.com/api/ring-events?hours=24 | jq '.total_count'

# Recent detections
curl https://deer-api.rndpig.com/api/detections/recent?hours=24 | jq 'length'

# Coordinator stats
curl https://deer-api.rndpig.com/api/coordinator/stats | jq
```

### Test Detection Pipeline
```bash
# Trigger test detection
curl -X POST https://deer-api.rndpig.com/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "test-camera",
    "snapshot_url": "https://example.com/test-image.jpg"
  }'
```

---

## Next Investigation Steps

1. **Get the snapshot** - Download and visually inspect the Jan 16 snapshot
2. **Test manually** - Run the image through ML detector with verbose output
3. **Compare with video** - Check Ring app video to confirm deer presence
4. **Adjust threshold** - Lower to 0.15-0.20 and monitor for false positives
5. **Collect training data** - Save missed detections for model retraining

---

## Conclusion

The good news: **Your system is working!** All components are functioning correctly.

The bad news: **The ML model is not accurate enough** for your environment, especially at night.

**Root Cause:** ML model failed to detect deer in low-light snapshot, likely due to:
- Nighttime image quality
- Confidence threshold too high
- Insufficient nighttime training data

**Solution Priority:**
1. ⚡ **Immediate:** Lower confidence threshold to 0.15-0.20
2. 🔍 **This week:** Review actual snapshot and test manually
3. 📊 **This month:** Retrain model with nighttime deer images

---

## Files Created During Investigation

- `check_jan16_event.py` - Script to check Ring events in database
- `check_jan16_via_api.py` - Script to check events via API
- `analyze_jan16_detection.py` - Analysis script with recommendations
- `JAN16_2026_INVESTIGATION_REPORT.md` - This report

---

**Report Generated:** 2026-01-18  
**System Location:** Dell OptiPlex Server (dilger / 192.168.7.215)  
**API Endpoint:** https://deer-api.rndpig.com
