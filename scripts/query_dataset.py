#!/usr/bin/env python3
"""Query existing dataset to prepare for versioning"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

def query_dataset():
    """Query database for deer snapshots"""
    db_path = "/home/rndpig/deer-deterrent/backend/data/training.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get deer snapshot stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest,
            COUNT(DISTINCT camera_id) as cameras
        FROM ring_events 
        WHERE deer_detected = 1 
        AND snapshot_available = 1
    """)
    
    total, earliest, latest, cameras = cursor.fetchone()
    
    print(f"=== Dataset Statistics ===")
    print(f"Total deer snapshots: {total}")
    print(f"Date range: {earliest} to {latest}")
    print(f"Unique cameras: {cameras}")
    
    # Get snapshots by camera
    cursor.execute("""
        SELECT camera_id, COUNT(*) 
        FROM ring_events 
        WHERE deer_detected = 1 
        AND snapshot_available = 1
        GROUP BY camera_id
    """)
    
    print(f"\n=== Snapshots by Camera ===")
    for camera_id, count in cursor.fetchall():
        print(f"{camera_id}: {count} snapshots")
    
    # Get all deer snapshots with details
    cursor.execute("""
        SELECT 
            id,
            camera_id,
            timestamp,
            snapshot_path,
            detection_confidence
        FROM ring_events 
        WHERE deer_detected = 1 
        AND snapshot_available = 1
        ORDER BY timestamp
    """)
    
    snapshots = cursor.fetchall()
    conn.close()
    
    # Check file existence
    snapshot_dir = Path("/home/rndpig/deer-deterrent/backend/data/snapshots")
    existing_files = 0
    missing_files = []
    
    for event_id, camera_id, timestamp, snapshot_path, confidence in snapshots:
        full_path = snapshot_dir / Path(snapshot_path).name
        if full_path.exists():
            existing_files += 1
        else:
            missing_files.append((event_id, snapshot_path))
    
    print(f"\n=== File Validation ===")
    print(f"Files exist: {existing_files}/{total}")
    print(f"Missing files: {len(missing_files)}")
    
    if missing_files:
        print("\nMissing files:")
        for event_id, path in missing_files[:5]:
            print(f"  Event {event_id}: {path}")
        if len(missing_files) > 5:
            print(f"  ... and {len(missing_files) - 5} more")
    
    return snapshots

if __name__ == "__main__":
    query_dataset()
