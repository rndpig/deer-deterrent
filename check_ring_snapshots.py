"""
Check Ring events with snapshots and test model performance on snapshot images vs video frames.
"""
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_ring_snapshots():
    """Check what Ring events we have with snapshots available."""
    conn = sqlite3.connect('data/training.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get events with snapshots
    c.execute("""
        SELECT camera_id, event_type, timestamp, snapshot_available, 
               snapshot_size, recording_url, deer_detected, detection_confidence
        FROM ring_events 
        WHERE snapshot_available = 1
        ORDER BY timestamp DESC
        LIMIT 20
    """)
    
    events_with_snapshots = c.fetchall()
    
    print("=" * 80)
    print("RING EVENTS WITH SNAPSHOTS AVAILABLE")
    print("=" * 80)
    print(f"\nFound {len(events_with_snapshots)} events with snapshots in database\n")
    
    if events_with_snapshots:
        for event in events_with_snapshots:
            print(f"Event ID: {event['id']}")
            print(f"  Camera: {event['camera_id']}")
            print(f"  Type: {event['event_type']}")
            print(f"  Timestamp: {event['timestamp']}")
            print(f"  Snapshot Size: {event['snapshot_size']:,} bytes" if event['snapshot_size'] else "  Snapshot Size: Unknown")
            print(f"  Recording URL: {event['recording_url'][:50]}..." if event['recording_url'] else "  Recording URL: None")
            print(f"  Deer Detected: {event['deer_detected']}")
            print(f"  Confidence: {event['detection_confidence']}")
            print()
    else:
        print("⚠️  No events with snapshots found in database")
        print("   This means snapshots are NOT being saved currently")
        print("   Only snapshot metadata (size, availability) is logged\n")
    
    # Check total events
    c.execute("SELECT COUNT(*) as total FROM ring_events")
    total = c.fetchone()['total']
    
    c.execute("SELECT COUNT(*) as with_snapshot FROM ring_events WHERE snapshot_available = 1")
    with_snapshot = c.fetchone()['with_snapshot']
    
    print(f"Summary:")
    print(f"  Total Ring Events: {total}")
    print(f"  Events with Snapshots: {with_snapshot} ({with_snapshot/total*100:.1f}%)" if total > 0 else "  Events with Snapshots: 0")
    
    conn.close()
    
    return len(events_with_snapshots) > 0

def check_ring_api_access():
    """Check if we can access Ring snapshots via API."""
    print("\n" + "=" * 80)
    print("RING API SNAPSHOT ACCESS")
    print("=" * 80)
    print("""
Ring snapshots ARE available via API, but NOT currently being saved.

According to Ring API documentation:
1. Snapshots have UUIDs included in push notifications: notification.img.snapshot_uuid
2. Snapshots can be retrieved via API: camera.getSnapshotByUuid(uuid)
3. Snapshots are stored on Ring servers for at least 24-48 hours
4. Even without Ring Protect, snapshots from motion events are accessible

Current System Status:
❌ Coordinator receives snapshot bytes but doesn't save them to disk
❌ Database only logs snapshot_available=True and size, not the image
❌ No snapshot_uuid is being captured from MQTT messages

To Access Snapshots:
1. Modify coordinator to save snapshot bytes to disk when received
2. Capture snapshot_uuid from Ring-MQTT event_select messages  
3. Use Ring API to retrieve snapshots by UUID for older events
4. Save snapshots with video_id reference for training comparison
""")

def propose_solution():
    """Propose how to access and test snapshots."""
    print("\n" + "=" * 80)
    print("SOLUTION: ACCESS RING SNAPSHOTS FOR MODEL TESTING")
    print("=" * 80)
    print("""
PHASE 1: Modify Coordinator to Save Snapshots (Immediate)
----------------------------------------------------------
File: Dockerfile.coordinator

Current (line ~450-470):
    if camera_id in camera_snapshots:
        snapshot_bytes = camera_snapshots[camera_id]
        # Snapshot sent to ML but NOT saved to disk

Modified:
    if camera_id in camera_snapshots:
        snapshot_bytes = camera_snapshots[camera_id]
        
        # Save snapshot to disk with ring_event_id reference
        snapshot_dir = Path("data/ring_snapshots")
        snapshot_dir.mkdir(exist_ok=True)
        snapshot_path = snapshot_dir / f"event_{ring_event_id}_snapshot.jpg"
        snapshot_path.write_bytes(snapshot_bytes)
        
        # Update database with snapshot path
        log_ring_event(..., snapshot_path=str(snapshot_path))


PHASE 2: Capture Snapshot UUIDs from MQTT (Immediate)
------------------------------------------------------
Ring-MQTT publishes snapshot UUIDs in event_select messages.

Modify coordinator to:
1. Parse event_select payload for img.snapshot_uuid
2. Store snapshot_uuid in ring_events table
3. Create function to download snapshot by UUID from Ring API


PHASE 3: Retrieve Historical Snapshots (Optional)
--------------------------------------------------
For events in the last 24-48 hours, we can:
1. Query ring_events for recent events
2. Use Ring API to fetch videos with: camera.getEvents(limit=100)
3. Extract snapshot_uuid from each event
4. Download snapshots: camera.getSnapshotByUuid(uuid)
5. Associate with existing training videos


PHASE 4: Test Model on Snapshots vs Video Frames
-------------------------------------------------
Once we have snapshots saved:

1. Create test dataset:
   - 50 snapshots from motion events with deer
   - 50 snapshots from motion events without deer
   - Compare to video frames from same events

2. Run inference comparison:
   - Model confidence on snapshot vs video frame
   - False positive/negative rates
   - Optimal threshold for snapshots

3. Results will tell us:
   - Do we need to retrain model with snapshot images?
   - Should snapshot threshold differ from video threshold?
   - Is burst approach viable or do we need video-only?


IMMEDIATE ACTION: Run coordinator modification script
------------------------------------------------------
I can create a modified coordinator that saves snapshots starting NOW,
then we can collect real snapshot data over the next 24-48 hours and
test your model's performance on them.

Would you like me to:
1. Create modified coordinator that saves snapshots? (5 minutes)
2. Add snapshot_uuid tracking to database? (5 minutes)
3. Create script to test model on saved snapshots? (10 minutes)
""")

if __name__ == "__main__":
    has_snapshots = check_ring_snapshots()
    check_ring_api_access()
    propose_solution()
    
    if not has_snapshots:
        print("\n" + "!" * 80)
        print("⚠️  ACTION REQUIRED: Modify coordinator to save snapshots")
        print("!" * 80)
