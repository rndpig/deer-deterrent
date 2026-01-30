#!/usr/bin/env python3
"""
Cleanup false positives from Driveway camera.
Untags all Driveway camera snapshots that were marked as having deer.
"""

import sqlite3
from datetime import datetime

# Database path
DB_PATH = '/home/rndpig/deer-deterrent/backend/data/training.db'

def cleanup_driveway_detections():
    """Untag all Driveway camera detections."""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find all Driveway detections with deer_detected=1
    cursor.execute("""
        SELECT id, camera_id, timestamp, detection_confidence 
        FROM ring_events 
        WHERE camera_id = '587a624d3fae' 
        AND deer_detected = 1
        ORDER BY timestamp DESC
    """)
    
    driveway_detections = cursor.fetchall()
    
    if not driveway_detections:
        print("✅ No Driveway false positives found!")
        conn.close()
        return
    
    print(f"\n🔍 Found {len(driveway_detections)} Driveway detections tagged as deer")
    print("\nSample of detections to be cleaned up:")
    for i, (id, camera_id, timestamp, confidence) in enumerate(driveway_detections[:10]):
        print(f"  ID {id}: {timestamp} (confidence: {confidence})")
        if i == 9 and len(driveway_detections) > 10:
            print(f"  ... and {len(driveway_detections) - 10} more")
    
    confirm = input(f"\n⚠️  This will untag {len(driveway_detections)} Driveway detections. Continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("❌ Cancelled")
        conn.close()
        return
    
    # Untag all Driveway detections
    cursor.execute("""
        UPDATE ring_events 
        SET deer_detected = 0,
            detection_confidence = NULL
        WHERE camera_id = '587a624d3fae' 
        AND deer_detected = 1
    """)
    
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"\n✅ Successfully untagged {updated} Driveway false positives!")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    cleanup_driveway_detections()
