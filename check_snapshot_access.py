"""
Check Ring events via backend API and determine if snapshots are accessible.
"""
import requests
import json

API_BASE = "http://localhost:8000"

def check_ring_events_api():
    """Check Ring events via API."""
    print("=" * 80)
    print("CHECKING RING EVENTS VIA API")
    print("=" * 80)
    
    try:
        response = requests.get(f"{API_BASE}/api/ring-events", params={"limit": 20})
        response.raise_for_status()
        events = response.json()
        
        print(f"\nFound {len(events)} Ring events\n")
        
        snapshot_count = 0
        for event in events:
            if event.get('snapshot_available'):
                snapshot_count += 1
                print(f"Event ID: {event['id']}")
                print(f"  Camera: {event['camera_id']}")
                print(f"  Timestamp: {event['timestamp']}")
                print(f"  Snapshot Size: {event.get('snapshot_size', 'Unknown')} bytes")
                print(f"  Deer Detected: {event.get('deer_detected', 'Not processed')}")
                print()
        
        print(f"Events with snapshots: {snapshot_count}/{len(events)}")
        
        return snapshot_count > 0
        
    except requests.exceptions.ConnectionError:
        print("❌ Backend API not reachable at http://localhost:8000")
        print("   Backend container may not be running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def explain_snapshot_situation():
    """Explain the current snapshot situation."""
    print("\n" + "=" * 80)
    print("RING SNAPSHOT SITUATION")
    print("=" * 80)
    print("""
Current Reality:
----------------
❌ Snapshots are NOT being saved to disk
❌ Only metadata (snapshot_available=True, size) is logged
❌ Snapshot bytes are processed for ML detection then discarded
❌ No snapshot_uuid is captured from Ring API

What This Means:
----------------
• We CANNOT test your model on past snapshots (they weren't saved)
• We CAN modify the system to start saving snapshots NOW
• Ring snapshots ARE available via API but we need to capture them
• We need 24-48 hours of new data collection to build test dataset

Ring Snapshot Sources:
-----------------------
1. INSTANT SNAPSHOTS (what coordinator currently receives):
   - Published to MQTT: ring/{location}/camera/{id}/snapshot/image
   - Binary JPEG data ~24KB
   - Captured at motion detection moment
   - Currently: Sent to ML detector, then discarded ❌

2. SNAPSHOT UUIDs (from Ring API):
   - Included in push notifications: notification.img.snapshot_uuid
   - Can retrieve via: camera.getSnapshotByUuid(uuid)
   - Available for 24-48 hours after event
   - Currently: Not being captured ❌

3. VIDEO FRAMES (what you've trained on):
   - Extracted from Ring recordings (mp4 files)
   - Higher quality, multiple frames per event
   - Currently: Working ✓

The Question You're Asking:
---------------------------
"Will my model work on snapshot images since I only trained on video frames?"

Answer: We don't know yet, but we can find out!

Action Plan:
------------
1. IMMEDIATE (Today):
   - Modify coordinator to save snapshot bytes to disk
   - Add snapshot_path column to ring_events table
   - Start collecting snapshots with each motion event

2. COLLECTION PERIOD (24-48 hours):
   - Let system collect ~20-50 snapshot images
   - Mix of events with/without deer (based on motion triggers)
   - Associate each snapshot with its Ring event

3. TESTING (Day 3):
   - Run your model on collected snapshots
   - Compare confidence scores to video frame results
   - Determine if snapshot quality affects detection
   - Calculate optimal threshold for snapshot images

4. DECISION (Day 3):
   - If model works well on snapshots → Proceed with burst approach ✓
   - If model struggles → May need to retrain with snapshot images
   - If major differences → Adjust thresholds per source type

Would you like me to create the modified coordinator that starts saving
snapshots immediately? This is the first step to answering your question.
""")

if __name__ == "__main__":
    has_snapshots = check_ring_events_api()
    
    if not has_snapshots:
        explain_snapshot_situation()
        
        print("\n" + "=" * 80)
        print("NEXT STEP: Modify Coordinator to Save Snapshots")
        print("=" * 80)
        print("""
I can create a patch for the coordinator that:

1. Creates data/ring_snapshots/ directory
2. Saves every snapshot to: event_{id}_snapshot_{camera}_{timestamp}.jpg
3. Logs snapshot_path in database
4. Preserves current ML detection workflow

After 24-48 hours of collection, we'll have:
- Real snapshot images from your Ring cameras
- Associated with motion events (some with deer, some without)
- Ready to test your model's performance on snapshot data

Ready to proceed? (Y/n)
""")
