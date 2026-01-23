# Periodic Snapshot Polling - Feature Request

**Date:** January 22, 2026  
**Status:** Planned (Not Implemented)  
**Priority:** High - Critical for effective deer detection

## Problem Statement

The Side camera has Ring's "Snapshot Capture" feature enabled, taking snapshots every 30 seconds to capture activity between motion events. However, these periodic snapshots are **not** being processed by our deer detection system.

### Discovery
- User found a deer in a periodic snapshot from this morning
- No motion event was logged for this detection
- This deer would have been completely missed by the current motion-only system
- Ring app shows "Snapshot Capture" is enabled with 30-second frequency for Side camera (ID: `10cea9e4511f`)

### Current System Limitation
The coordinator only processes snapshots triggered by **motion events** published to MQTT:
- Motion event → MQTT publishes snapshot → ML detection
- Periodic snapshots (every 30s) → Stored in Ring cloud → **Never processed**

This creates a significant blind spot where deer passing through without triggering motion detection are not deterred.

## Technical Solution

### Approach: MQTT-Based Snapshot Polling

Ring-MQTT supports requesting snapshots on-demand via MQTT command topics. This is simpler than Ring API polling and works with existing infrastructure.

### MQTT Command Flow

1. **Request Snapshot** (Coordinator publishes):
   - Topic: `ring/{location_id}/camera/10cea9e4511f/snapshot/command`
   - Payload: `snap` or empty string
   - Frequency: Every 30-60 seconds (configurable)

2. **Receive Snapshot** (Coordinator subscribes):
   - Topic: `ring/{location_id}/camera/10cea9e4511f/snapshot/image`
   - Payload: Binary JPEG image (~24KB)
   - Process through ML detection pipeline

3. **Log Detection** (if deer detected):
   - Save snapshot to `/app/data/snapshots/`
   - Create database entry with `event_type='periodic_snapshot'`
   - Mark `camera_id='10cea9e4511f'`
   - If confidence > threshold AND in-season: Trigger irrigation

## Implementation Details

### Required Changes

#### 1. Coordinator Service (`Dockerfile.coordinator`)

Add periodic snapshot polling task:

```python
# Configuration additions
CONFIG = {
    ...existing config...,
    "ENABLE_PERIODIC_SNAPSHOTS": os.getenv("ENABLE_PERIODIC_SNAPSHOTS", "true").lower() == "true",
    "PERIODIC_SNAPSHOT_INTERVAL": int(os.getenv("PERIODIC_SNAPSHOT_INTERVAL", "60")),  # seconds
    "PERIODIC_SNAPSHOT_CAMERAS": os.getenv("PERIODIC_SNAPSHOT_CAMERAS", "10cea9e4511f").split(","),
}

# Background task for periodic snapshots
async def periodic_snapshot_poller():
    """Request snapshots from configured cameras at regular intervals."""
    while True:
        try:
            if not CONFIG["ENABLE_PERIODIC_SNAPSHOTS"]:
                await asyncio.sleep(60)
                continue
            
            for camera_id in CONFIG["PERIODIC_SNAPSHOT_CAMERAS"]:
                # Request snapshot via MQTT
                topic = f"ring/{location_id}/camera/{camera_id}/snapshot/command"
                mqtt_client.publish(topic, "snap")
                logger.info(f"Requested periodic snapshot from camera {camera_id}")
            
            await asyncio.sleep(CONFIG["PERIODIC_SNAPSHOT_INTERVAL"])
        except Exception as e:
            logger.error(f"Error in periodic snapshot poller: {e}")
            await asyncio.sleep(60)

# Start task on startup
@app.on_event("startup")
async def startup_event():
    ...existing startup code...
    if CONFIG["ENABLE_PERIODIC_SNAPSHOTS"]:
        asyncio.create_task(periodic_snapshot_poller())
        logger.info("Started periodic snapshot polling")
```

#### 2. MQTT Snapshot Handler

Update existing snapshot handler to track source:

```python
def on_snapshot_message(client, userdata, msg):
    """Handle snapshot image from MQTT."""
    camera_id = extract_camera_id_from_topic(msg.topic)
    snapshot_bytes = msg.payload
    
    # Store snapshot for processing
    camera_snapshots[camera_id] = {
        'bytes': snapshot_bytes,
        'timestamp': datetime.now(),
        'source': 'periodic' if camera_id in CONFIG["PERIODIC_SNAPSHOT_CAMERAS"] else 'motion'
    }
    
    # Queue for processing (ensure we don't overwhelm ML detector)
    event_queue.put({
        'camera_id': camera_id,
        'snapshot_bytes': snapshot_bytes,
        'event_type': 'periodic_snapshot' if camera_id in CONFIG["PERIODIC_SNAPSHOT_CAMERAS"] else 'motion',
        'timestamp': datetime.now().isoformat()
    })
```

#### 3. Database Schema

Add support for periodic snapshot events:

```sql
-- ring_events table already has event_type column
-- Just need to ensure 'periodic_snapshot' is a valid value

-- Example entry:
INSERT INTO ring_events (
    camera_id, 
    event_type, 
    timestamp, 
    snapshot_available, 
    snapshot_path,
    deer_detected,
    detection_confidence
) VALUES (
    '10cea9e4511f',
    'periodic_snapshot',  -- New event type
    '2026-01-22T20:30:00',
    1,
    'data/snapshots/periodic_20260122_203000_10cea9e4511f.jpg',
    1,
    0.87
);
```

### Configuration via Environment Variables

Add to `docker-compose.yml` or deployment config:

```yaml
services:
  coordinator:
    environment:
      - ENABLE_PERIODIC_SNAPSHOTS=true
      - PERIODIC_SNAPSHOT_INTERVAL=60  # seconds (match or exceed Ring's 30s to avoid overload)
      - PERIODIC_SNAPSHOT_CAMERAS=10cea9e4511f  # Side camera only (comma-separated for multiple)
```

## Benefits

### Detection Coverage
- **Before:** Only captures deer triggering motion events (~30% of passes)
- **After:** Captures all deer in frame every 30-60 seconds (~90%+ of passes)

### Data Collection
- Provides continuous monitoring of Side yard area
- Better training data for model refinement
- Can analyze deer movement patterns over time

### System Load
- Ring-MQTT handles snapshot requests efficiently
- ML detector processes 1 snapshot every 60 seconds = negligible load
- One camera = 1,440 snapshots/day (vs. ~10-20 motion events/day)

## Considerations

### Storage Requirements
- 1 snapshot = ~24KB
- 60-second interval = 1,440 snapshots/day = 34.5 MB/day
- 30-day retention = ~1 GB/month (acceptable)
- Auto-archive after 3 days (existing feature) keeps database manageable

### Rate Limiting
- Set interval to 60 seconds (2x Ring's 30s capture rate)
- Avoids overwhelming Ring API
- Prevents coordinator from queuing too many events

### Battery Cameras
- **Warning:** Periodic polling will drain battery faster
- Side camera should be wired/solar-powered for this feature
- Check camera power source before enabling

### False Positives
- More snapshots = more potential false positives
- Monitor confidence scores and adjust threshold if needed
- Existing cooldown system prevents irrigation spam

## Testing Plan

### Phase 1: Enable Polling (Day 1)
1. Add periodic snapshot polling code to coordinator
2. Deploy updated coordinator
3. Monitor logs for snapshot requests and responses
4. Verify snapshots are saved and processed

### Phase 2: Validate Detections (Days 2-3)
1. Review snapshots in viewer
2. Compare periodic detections vs. motion detections
3. Check for false positives/negatives
4. Adjust confidence threshold if needed

### Phase 3: Monitor System Load (Week 1)
1. Check coordinator resource usage (CPU/memory)
2. Monitor ML detector processing times
3. Verify database growth rate
4. Confirm irrigation cooldowns working properly

## Next Steps

1. **Document current coordinator code structure** (understand where to inject polling task)
2. **Locate Ring-MQTT location ID** (needed for MQTT topics)
3. **Implement periodic snapshot polling** in `Dockerfile.coordinator`
4. **Add configuration** to docker-compose or deployment scripts
5. **Test on dev environment** before production deployment
6. **Monitor for 48 hours** and review captured snapshots
7. **Adjust interval/threshold** based on results

## Open Questions

- [ ] What is the Ring location_id for MQTT topics?
- [ ] Should we enable for other cameras or just Side?
- [ ] What confidence threshold should we use for periodic snapshots?
- [ ] Should periodic detections trigger irrigation or just log for review?
- [ ] How to handle coordinator restart (resume from last snapshot time)?

## References

- Ring-MQTT Documentation: https://github.com/tsightler/ring-mqtt
- Ring "Snapshot Capture" feature: Enabled on Side camera (30-second intervals)
- Current deer detection pipeline: `docs/RING_MOTION_DETECTION_PIPELINE.md`
- Coordinator service: `Dockerfile.coordinator` (lines 30-682)

---

**Implementation Target:** TBD  
**Assigned To:** TBD  
**Estimated Effort:** 4-6 hours (coding + testing)
