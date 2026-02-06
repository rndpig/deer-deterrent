"""
Fix Back camera false positives by setting deer_detected=0 directly.
Does NOT mark as false positive (which would send to training set).
"""
import requests

API_BASE = "https://deer-api.rndpig.com"
BACK_CAMERA_ID = "f045dae9383a"

def main():
    print("Fetching Back camera snapshots tagged as deer_detected=1...")
    
    # Get all Back camera snapshots with deer
    response = requests.get(
        f"{API_BASE}/api/snapshots",
        params={
            "limit": 500,
            "with_deer": "true"
        }
    )
    response.raise_for_status()
    
    snapshots = response.json()['snapshots']
    back_camera_snapshots = [s for s in snapshots if s['camera_id'] == BACK_CAMERA_ID]
    
    print(f"\nFound {len(back_camera_snapshots)} Back camera snapshots with deer_detected=1")
    
    if len(back_camera_snapshots) == 0:
        print("No snapshots to fix.")
        return
    
    print("\nSnapshot IDs to fix:")
    for snap in back_camera_snapshots:
        print(f"  #{snap['id']} - {snap['timestamp']} - {snap['detection_confidence']*100:.0f}%")
    
    confirm = input(f"\nSet all {len(back_camera_snapshots)} snapshots to deer_detected=0? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        return
    
    # Need to run this on the server since we need direct database access
    print("\nThis script needs to be run on the Dell server with database access.")
    print("Copy this script to the server and run:")
    print(f"  scp fix_back_camera_false_positives.py rndpig@192.168.7.215:/home/rndpig/deer-deterrent/")
    print(f"  ssh rndpig@192.168.7.215 'cd /home/rndpig/deer-deterrent && python3 fix_back_camera_false_positives.py'")
    
    # Create server-side version
    server_script = """#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("/home/rndpig/deer-deterrent/backend/data/ring_events.db")
BACK_CAMERA_ID = "f045dae9383a"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get count
cursor.execute(
    "SELECT COUNT(*) FROM ring_events WHERE camera_id = ? AND deer_detected = 1",
    (BACK_CAMERA_ID,)
)
count = cursor.fetchone()[0]

print(f"Found {count} Back camera snapshots with deer_detected=1")

if count > 0:
    # Update to deer_detected=0
    cursor.execute(
        "UPDATE ring_events SET deer_detected = 0, detection_confidence = 0.0 WHERE camera_id = ? AND deer_detected = 1",
        (BACK_CAMERA_ID,)
    )
    conn.commit()
    print(f"✅ Updated {count} snapshots to deer_detected=0")
else:
    print("No snapshots to update")

conn.close()
"""
    
    with open("fix_back_camera_on_server.py", "w", encoding="utf-8") as f:
        f.write(server_script)
    
    print("\nCreated fix_back_camera_on_server.py")
    print("Run it on the server with:")
    print("  python3 fix_back_camera_on_server.py")

if __name__ == "__main__":
    main()
