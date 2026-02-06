"""
Mark all Back camera (Backyard) snapshots currently marked as deer=1 to deer=0.
This prevents false positives from contaminating the training dataset.

Camera: Back (Backyard)
Camera ID: f045dae9383a

Usage:
  # On server (with direct database access):
  python mark_back_camera_false_positives.py

  # From local machine (via API):
  python mark_back_camera_false_positives.py --api https://deer-api.rndpig.com
"""

import sqlite3
from pathlib import Path
import argparse
import requests

def mark_via_api(api_url):
    """Update via API by fetching and updating each snapshot"""
    
    print(f"🌐 Using API: {api_url}")
    
    # Fetch all Back camera snapshots with deer=1
    back_camera_id = 'f045dae9383a'
    
    try:
        response = requests.get(f"{api_url}/api/snapshots")
        response.raise_for_status()
        snapshots = response.json()
    except Exception as e:
        print(f"❌ Error fetching snapshots: {e}")
        return
    
    # Filter for Back camera with deer_detected=1
    back_deer_snapshots = [
        s for s in snapshots 
        if s.get('camera_id') == back_camera_id 
        and s.get('deer_detected') == 1
    ]
    
    if not back_deer_snapshots:
        print("✅ No Back camera snapshots with deer_detected=1 found")
        return
    
    count = len(back_deer_snapshots)
    print(f"📊 Found {count} Back camera snapshots marked as deer_detected=1")
    
    # Show samples
    print(f"\n📋 Sample snapshots to be updated:")
    for snapshot in back_deer_snapshots[:5]:
        print(f"  - ID {snapshot['id']}: {snapshot['timestamp']} (confidence: {snapshot['detection_confidence']:.2%})")
    
    # Update each one via API
    updated = 0
    failed = 0
    
    print(f"\n🔄 Updating {count} snapshots...")
    for snapshot in back_deer_snapshots:
        snapshot_id = snapshot['id']
        try:
            response = requests.put(
                f"{api_url}/api/snapshots/{snapshot_id}/feedback",
                json={"is_correct": False}
            )
            response.raise_for_status()
            updated += 1
            if updated % 10 == 0:
                print(f"  ... {updated}/{count} updated")
        except Exception as e:
            print(f"  ⚠️ Failed to update snapshot {snapshot_id}: {e}")
            failed += 1
    
    print(f"\n✅ Updated {updated} snapshots to deer_detected=0")
    if failed > 0:
        print(f"⚠️  {failed} updates failed")

def mark_back_camera_false_positives():
    """Update all Back camera deer detections to false positives (direct database access)"""
    
    # Database path
    db_path = Path(__file__).parent / "data" / "deer_data.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Camera ID for Back/Backyard camera
    back_camera_id = 'f045dae9383a'
    
    # First, check how many will be updated
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ring_events 
        WHERE camera_id = ? 
        AND deer_detected = 1
    """, (back_camera_id,))
    
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("✅ No Back camera snapshots with deer_detected=1 found")
        conn.close()
        return
    
    print(f"📊 Found {count} Back camera snapshots marked as deer_detected=1")
    
    # Get sample IDs for verification
    cursor.execute("""
        SELECT id, timestamp, detection_confidence
        FROM ring_events 
        WHERE camera_id = ? 
        AND deer_detected = 1
        ORDER BY id
        LIMIT 5
    """, (back_camera_id,))
    
    samples = cursor.fetchall()
    print(f"\n📋 Sample snapshots to be updated:")
    for snapshot_id, timestamp, confidence in samples:
        print(f"  - ID {snapshot_id}: {timestamp} (confidence: {confidence:.2%})")
    
    # Perform the update
    cursor.execute("""
        UPDATE ring_events 
        SET deer_detected = 0, 
            detection_confidence = 0.0
        WHERE camera_id = ? 
        AND deer_detected = 1
    """, (back_camera_id,))
    
    conn.commit()
    rows_updated = cursor.rowcount
    
    print(f"\n✅ Updated {rows_updated} snapshots from deer_detected=1 to deer_detected=0")
    print(f"✅ Set detection_confidence to 0.0 for all updated snapshots")
    
    # Verify the update
    cursor.execute("""
        SELECT COUNT(*) 
        FROM ring_events 
        WHERE camera_id = ? 
        AND deer_detected = 1
    """, (back_camera_id,))
    
    remaining = cursor.fetchone()[0]
    
    if remaining == 0:
        print(f"✅ Verification: No Back camera snapshots with deer_detected=1 remaining")
    else:
        print(f"⚠️  Warning: {remaining} Back camera snapshots still marked as deer_detected=1")
    
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Mark Back camera false positives')
    parser.add_argument('--api', help='API URL (e.g., https://deer-api.rndpig.com)', default=None)
    args = parser.parse_args()
    
    print("🔧 Back Camera False Positive Cleanup")
    print("=" * 60)
    print(f"Camera: Back (Backyard)")
    print(f"Camera ID: f045dae9383a")
    print(f"Action: Mark all deer_detected=1 snapshots as deer_detected=0")
    print("=" * 60 + "\n")
    
    if args.api:
        mark_via_api(args.api)
    else:
        mark_back_camera_false_positives()
