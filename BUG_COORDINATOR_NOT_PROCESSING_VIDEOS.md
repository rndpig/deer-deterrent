# Critical Bug Found: Coordinator Not Processing Ring Videos

## Problem Identified

The coordinator is **ONLY processing instant MQTT snapshots** and **SKIPPING actual video URLs**.

### Code Issue (Dockerfile.coordinator, lines 484-488)

```python
# Handle event_select messages (SLOW - 30-60 seconds, skip for now since we use instant snapshots)
if "event_select" in topic and len(parts) >= 6 and parts[4] == "event_select":
    # Skip processing recording URLs - we already processed instant snapshot
    logger.debug(f"Skipping event_select (already processed instant snapshot): {topic}")
    return  # ❌ THIS IS THE BUG!
```

## What's Happening

### Current Flow (Broken)
1. Motion detected → MQTT `motion/state` = ON
2. Coordinator receives message
3. Grabs cached snapshot from MQTT (~24KB, low-res, **single frame**)
4. Runs ML detection on that one frame
5. **SKIPS** the video URL that arrives 30-60 seconds later
6. Result: Misses deer if they're not in that exact snapshot frame

### What SHOULD Happen
1. Motion detected → MQTT `motion/state` = ON
2. Coordinator receives message
3. Optionally: Quick check with instant snapshot (for speed)
4. Wait for `event_select` message with video URL (30-60 seconds)
5. **Download the actual Ring video**
6. **Extract multiple frames** from video
7. Run ML detection on ALL frames
8. Activate irrigation if deer found in ANY frame

## Why This Causes Missed Detections

### Instant Snapshot Problems
- **Single frame** vs. video with 30-60 frames
- **Low resolution** (~24KB vs full video)
- **Timing issue** - snapshot may be captured:
  - Before deer enters frame
  - After deer exits frame
  - When deer is partially obscured
  - At wrong angle/distance

### Manual Upload Works Because
- Extracts **multiple frames** from video (every N frames)
- More chances to catch deer when centered in frame
- Better image quality from video frames
- Processes the ACTUAL Ring recording, not just a snapshot

## The Fix

We need to modify the coordinator to:
1. **Option A (Recommended):** Process BOTH instant snapshot AND video
   - Fast response with snapshot (1-2 seconds)
   - Comprehensive analysis with video (30-60 seconds)
   - Best of both worlds

2. **Option B:** Skip instant snapshot, wait for video only
   - More accurate
   - Slower response (30-60 second delay)
   - Single comprehensive detection

3. **Option C:** Extract multiple frames from video
   - Download video on motion event
   - Extract frames every 0.5 seconds
   - Run detection on all frames
   - Most thorough but slowest

## Recommended Solution

### Strategy: Dual-Pass Detection

```python
# PASS 1: Instant snapshot for quick response (existing)
if camera_id in camera_snapshots:
    logger.info(f"✓ PASS 1: Quick check with instant snapshot")
    event_queue.put({
        "camera_id": camera_id,
        "snapshot_bytes": camera_snapshots[camera_id],
        "timestamp": datetime.now().isoformat(),
        "source": "instant_snapshot",
        "ring_event_id": ring_event_id
    })

# PASS 2: Video analysis for accuracy (NEW - don't skip!)
if "event_select" in topic and len(parts) >= 6:
    # Parse the event_select payload for video URL
    payload_json = json.loads(payload)
    recording_url = payload_json.get("recording", {}).get("url")
    
    if recording_url:
        logger.info(f"✓ PASS 2: Processing full video for comprehensive detection")
        event_queue.put({
            "camera_id": camera_id,
            "snapshot_url": recording_url,  # This will trigger video download
            "timestamp": datetime.now().isoformat(),
            "source": "video_analysis",
            "ring_event_id": ring_event_id,
            "is_recheck": True  # Flag to indicate this is a second pass
        })
```

### Benefits
- ⚡ Fast initial response (1-2 seconds)
- 🎯 Accurate comprehensive check (30-60 seconds)
- 📊 Two chances to detect deer
- 🔄 Can compare results (snapshot vs video)

## Implementation Plan

### 1. Modify Coordinator Code

Edit `Dockerfile.coordinator` around lines 480-490:

**REMOVE:**
```python
# Skip processing recording URLs - we already processed instant snapshot
logger.debug(f"Skipping event_select (already processed instant snapshot): {topic}")
return
```

**REPLACE WITH:**
```python
# Process video URL for comprehensive analysis
try:
    payload_json = json.loads(payload)
    recording_url = payload_json.get("recording", {}).get("url")
    
    if recording_url:
        logger.info(f"📹 Received video URL, queuing for comprehensive analysis")
        
        # Find the original ring_event_id from recent events
        # (We need to link this video back to the motion event)
        
        event_queue.put({
            "camera_id": camera_id,
            "snapshot_url": recording_url,
            "timestamp": datetime.now().isoformat(),
            "source": "video_comprehensive",
            "ring_event_id": None  # Will need to look up
        })
except Exception as e:
    logger.error(f"Failed to parse event_select: {e}")
```

### 2. Enhance Video Processing

Modify `process_camera_event` function to extract MULTIPLE frames from video:

```python
if snapshot_url and snapshot_url.lower().endswith('.mp4'):
    logger.info(f"Extracting MULTIPLE frames from video for better detection")
    
    # Extract frames every 0.5 seconds
    import subprocess
    result = subprocess.run([
        'ffmpeg', '-i', str(temp_path),
        '-vf', 'fps=2',  # 2 frames per second
        '-f', 'image2',
        str(snapshot_path.parent / f"{camera_id}_%03d.jpg")
    ], capture_output=True, text=True)
    
    # Run detection on ALL extracted frames
    # If deer found in ANY frame, activate irrigation
```

### 3. Update Ring Event Tracking

Add video_url to ring_events table:
- Store video URL when received
- Link video analysis back to original motion event
- Track both snapshot and video detection results

## Testing Plan

### 1. Before Fix
- Upload Jan 16 video manually
- Confirm deer detected in extracted frames
- Document which frames show deer

### 2. Deploy Fix
- Rebuild coordinator Docker image
- Restart coordinator service
- Monitor logs for video processing

### 3. After Fix
- Wait for next motion event
- Verify BOTH snapshot and video are processed
- Check if video analysis detects deer that snapshot missed
- Compare detection rates

## Expected Results

### Before Fix
- Detection rate: ~0% (missing deer in snapshots)
- Processing time: 1-2 seconds
- Accuracy: Low (single frame)

### After Fix
- Detection rate: Should improve significantly
- Processing time: 1-2s (snapshot) + 30-60s (video)
- Accuracy: High (multiple frames)

## Files to Modify

1. `Dockerfile.coordinator` - Main fix (lines 480-490, 300-350)
2. `docker-compose.yml` - May need to rebuild image
3. `backend/database.py` - Add video_url to ring_events table
4. `backend/main.py` - Update API to show video processing results

## Next Steps

1. **Run manual upload test first** (confirm hypothesis)
2. **If deer detected in manual upload:**
   - Proceed with coordinator fix
   - Implement dual-pass detection
   - Test on next live event
3. **If deer NOT detected even in manual upload:**
   - Check ML model threshold
   - Review video quality
   - Consider model retraining

---

**Priority:** 🔴 **CRITICAL** - System is not analyzing Ring videos properly  
**Impact:** Missing most/all deer detections  
**Effort:** Medium (code changes + testing)  
**Risk:** Low (can rollback if needed)
