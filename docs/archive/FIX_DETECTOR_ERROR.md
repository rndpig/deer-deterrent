# Fix for "Detector not initialized" error during video upload
# Apply this to backend/main.py on the server

## CHANGE 1: Line 729 - Make detector optional instead of failing

### FIND (around line 727-730):
```python
    det = load_detector()
    if not det:
        raise HTTPException(status_code=503, detail="Detector not initialized")
```

### REPLACE WITH:
```python
    det = load_detector()
    detector_available = det is not None
    if not detector_available:
        logger.warning("⚠ Detector not available - frames will be extracted without auto-detection")
        logger.info("   You can manually annotate frames after upload")
```

---

## CHANGE 2: Around line 945-955 - Handle detection conditionally

### FIND (around line 945-955, inside the frame processing loop):
```python
            # Run detection on frame
            results = det.detect(frame)
            detections = results['detections']
            
            has_detections = len(detections) > 0
            if has_detections:
                detection_count += 1
                
            # Save detection results
            for detection in detections:
```

### REPLACE WITH:
```python
            # Run detection on frame (if detector available)
            if detector_available:
                results = det.detect(frame)
                detections = results['detections']
            else:
                detections = []
            
            has_detections = len(detections) > 0
            if has_detections:
                detection_count += 1
                
            # Save detection results
            for detection in detections:
```

---

## How to Apply

### Step 1: SSH to server
```bash
ssh dilger
```

### Step 2: Navigate to backend directory
```bash
cd /home/rndpig/deer-deterrent/backend
```

### Step 3: Backup the original file
```bash
cp main.py main.py.backup.$(date +%Y%m%d_%H%M%S)
```

### Step 4: Edit the file
```bash
nano main.py
```

Use Ctrl+W to search for "Detector not initialized" and make CHANGE 1.
Use Ctrl+W again to search for "det.detect(frame)" and make CHANGE 2.

Save with Ctrl+X, then Y, then Enter.

### Step 5: Restart the backend service
```bash
sudo systemctl restart deer-backend
```

### Step 6: Verify the fix
```bash
# Check logs for any errors
sudo journalctl -u deer-backend -n 20 --no-pager

# Should see:
# "⚠ Detector not available - frames will be extracted without auto-detection"
# This is expected and OK
```

### Step 7: Test upload
Go to https://deer-deterrent-rnp.web.app and try uploading a video again.

---

## What This Fix Does

- **Before:** Upload fails with "Detector not initialized" error
- **After:** Upload succeeds, extracts frames, but skips auto-detection
- **Result:** You can upload videos and manually annotate frames later

The auto-detection isn't critical for training - you're going to manually review and annotate frames anyway!

---

## Alternative: One-Line Fix via SSH

If you want to do this in one command:

```bash
ssh dilger "cd /home/rndpig/deer-deterrent/backend && \
  cp main.py main.py.backup && \
  sed -i '729,730s/raise HTTPException(status_code=503, detail=\"Detector not initialized\")/detector_available = det is not None\\n    if not detector_available:\\n        logger.warning(\"Detector not available - extracting frames only\")/g' main.py && \
  sudo systemctl restart deer-backend && \
  echo 'Fix applied and backend restarted'"
```

(This is a simplified regex approach, manual editing is safer)

---

## Verify It's Working

After applying the fix, check:

```bash
# Check that backend restarted successfully
ssh dilger "sudo systemctl status deer-backend"

# Check logs show the warning (this is expected and OK)
ssh dilger "sudo journalctl -u deer-backend -n 10 --no-pager | grep -i detector"

# Test the upload endpoint
curl -X POST https://deer-api.rndpig.com/api/videos/upload \
  -F "video=@test.mp4" \
  -F "sample_rate=30"
```

Upload should now work!
