import sqlite3
import re
from pathlib import Path
from datetime import datetime

snapshots_dir = Path("/app/snapshots")
conn = sqlite3.connect("/app/data/training.db")
cursor = conn.cursor()

# Pattern: event_20260119_173052_587a624d3fae_snapshot.jpg
pattern = re.compile(r'event_(\d{8})_(\d{6})_([a-f0-9]+)_snapshot\.jpg')

imported = 0
skipped = 0

for snapshot_file in snapshots_dir.glob("event_*_snapshot.jpg"):
    match = pattern.match(snapshot_file.name)
    if not match:
        print(f"Skipping (no match): {snapshot_file.name}")
        skipped += 1
        continue
    
    date_str, time_str, camera_id = match.groups()
    
    # Parse timestamp: 20260119_173052 -> 2026-01-19T17:30:52
    dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
    timestamp = dt.isoformat()
    
    # Check if event already exists for this timestamp and camera
    cursor.execute("""
        SELECT id FROM ring_events 
        WHERE camera_id = ? AND timestamp = ?
    """, (camera_id, timestamp))
    
    if cursor.fetchone():
        print(f"Skipping (exists): {snapshot_file.name}")
        skipped += 1
        continue
    
    # Get file size
    snapshot_size = snapshot_file.stat().st_size
    snapshot_path = f"snapshots/{snapshot_file.name}"
    
    # Insert new event
    cursor.execute("""
        INSERT INTO ring_events (
            camera_id, event_type, timestamp, 
            snapshot_available, snapshot_size, snapshot_path,
            processed, deer_detected
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (camera_id, "motion", timestamp, True, snapshot_size, snapshot_path, False, None))
    
    imported += 1
    print(f"Imported: {snapshot_file.name} -> event ID {cursor.lastrowid}")

conn.commit()
conn.close()

print(f"\n✓ Imported {imported} snapshots, skipped {skipped}")
